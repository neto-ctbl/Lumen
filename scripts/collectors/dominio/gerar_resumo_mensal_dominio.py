from __future__ import annotations

"""
Automação do Domínio Folha para geração do relatório "Resumo Mensal" em PDF.

Fluxo:
1. Abre C:\\Contabil\\contabil.exe /folha.
2. Realiza o login usando DOMINIO_PASSWORD do arquivo .env.
3. Acessa Relatórios > Folha > Resumo.
4. Preenche as competências "De" e "Até".
5. Seleciona somente empresas ativas.
6. Gera o relatório e aguarda o processamento terminar.
7. Abre a exportação em PDF, preferencialmente pelo atalho Ctrl+D.
8. Salva o arquivo e confirma que ele foi criado.

Exemplos:
    python gerar_resumo_mensal_dominio.py
    python gerar_resumo_mensal_dominio.py --competencia 07/2026
    python gerar_resumo_mensal_dominio.py --de 01/2026 --ate 07/2026
    python gerar_resumo_mensal_dominio.py --saida "G:\\RELATORIOS\\Resumo.pdf"
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import win32clipboard
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
from pypdf import PdfReader
import comtypes.gen
from pywinauto import Application, Desktop
from pywinauto.keyboard import send_keys


# -----------------------------------------------------------------------------
# Constantes dos controles mapeados no Domínio
# -----------------------------------------------------------------------------

LOGIN_TITLE_RE = r"Conectando.*"
MAIN_TITLE_RE = r"Domínio Folha.*"
MAIN_WINDOW_CLASS = "FNWND3190"
REPORT_TITLE = "Resumo Mensal"
REPORT_AUTO_ID = "202"
SELECT_COMPANIES_TITLE = "Selecionar Empresas"
SAVE_PDF_TITLE = "Salvar em PDF"

LOGIN_PASSWORD_AUTO_ID = "1007"
LOGIN_BUTTON_AUTO_ID = "1003"

COMPETENCIA_DE_AUTO_ID = "1012"
COMPETENCIA_ATE_AUTO_ID = "1004"
EMPRESAS_BUTTON_AUTO_ID = "1000"

SELECT_COMPANIES_OK_AUTO_ID = "1009"
GENERATE_REPORT_OK_AUTO_ID = "1000"

PDF_PANEL_AUTO_ID = "1016"
PDF_ICON_AUTO_ID = "1000"

SAVE_FILENAME_AUTO_ID = "1148"
SAVE_BUTTON_AUTO_ID = "1"

PROCESSING_TEXT = "Processando, Aguarde..."
PROCESSING_TEXT_AUTO_ID = "1001"
WORKSPACE_AUTO_ID = "2000"
WORKSPACE_NAME = "Espaço de trabalho"
WARNING_DIALOG_TITLE = "Atenção"
WARNING_DIALOG_CLASS = "#32770"
WARNING_OK_AUTO_ID = "2"
EXPIRATION_TITLE = "Avisos de Vencimento"
EXPIRATION_AUTO_ID = "200"
EXPIRATION_CLOSE_AUTO_ID = "Close"
FAST_EXISTS_TIMEOUT = 0.2
COMPETENCIA_RE = re.compile(r"^(0[1-9]|1[0-2])/(\d{4})$")
COMPETENCIA_IN_TEXT_RE = re.compile(r"\b(0[1-9]|1[0-2])/\d{4}\b")
CNPJ_IN_TEXT_RE = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
DEFAULT_EXPORT_RETRIES = 3
LOCK_FILE_NAME = "gerar_resumo_mensal_dominio.lock"
MANIFEST_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Config:
    dominio_exe: Path
    password: str
    competencia_de: str
    competencia_ate: str
    output_path: Path
    login_timeout: int
    report_timeout: int
    save_timeout: int
    overwrite_pdf: bool
    close_dominio_after: bool
    log_path: Path
    lock_path: Path
    export_retries: int


@dataclass(frozen=True)
class PdfValidationResult:
    page_count: int
    sha256: str
    size_bytes: int


class CollectorLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.fd: int | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "created_at": datetime.now().astimezone().isoformat(),
        }
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            details = ""
            try:
                details = self.path.read_text(encoding="utf-8").strip()
            except OSError:
                details = "lock already exists"
            raise RuntimeError(
                f"Another collector instance appears to be running: {self.path} | {details}"
            ) from exc

        with os.fdopen(self.fd, "w", encoding="utf-8", closefd=False) as handle:
            json.dump(payload, handle, ensure_ascii=True, sort_keys=True)
            handle.write("\n")

    def release(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            logging.warning("Could not remove collector lock: %s", self.path)


# -----------------------------------------------------------------------------
# Configuração e validações
# -----------------------------------------------------------------------------


def parse_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


def previous_month_competencia() -> str:
    previous_month = date.today().replace(day=1) - relativedelta(months=1)
    return previous_month.strftime("%m/%Y")


def validate_competencia(value: str) -> str:
    value = value.strip()
    match = COMPETENCIA_RE.fullmatch(value)
    if not match:
        raise ValueError(
            f"Competência inválida: {value!r}. Use o formato MM/AAAA, por exemplo 07/2026."
        )
    return value


def competencia_for_filename(value: str) -> str:
    return value.replace("/", "-")


def normalize_payroll_competence(value: str) -> str:
    competencia = validate_competencia(value)
    month, year = competencia.split("/")
    return f"{int(year):04d}-{int(month):02d}"


def map_payroll_to_assessment_competence(value: str) -> tuple[str, str]:
    payroll_competence = normalize_payroll_competence(value)
    year = int(payroll_competence[:4])
    month = int(payroll_competence[5:7])
    if month == 12:
        return payroll_competence, f"{year + 1:04d}-01"
    return payroll_competence, f"{year:04d}-{month + 1:02d}"


def build_partial_pdf_path(output_path: Path) -> Path:
    return output_path.with_suffix(".partial.pdf")


def build_manifest_path(output_path: Path) -> Path:
    return output_path.with_suffix(".manifest.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gera o relatório Resumo Mensal do Domínio Folha em PDF."
    )
    parser.add_argument(
        "--competencia",
        help="Usa a mesma competência nos campos De e Até, no formato MM/AAAA.",
    )
    parser.add_argument("--de", dest="competencia_de", help="Competência inicial MM/AAAA.")
    parser.add_argument("--ate", dest="competencia_ate", help="Competência final MM/AAAA.")
    parser.add_argument(
        "--saida",
        help="Caminho completo do PDF. Se omitido, usa OUTPUT_DIR do .env.",
    )
    parser.add_argument(
        "--nao-sobrescrever",
        action="store_true",
        help="Interrompe se o PDF já existir.",
    )
    parser.add_argument(
        "--fechar-dominio",
        action="store_true",
        help="Fecha o Domínio ao final de uma execução bem-sucedida.",
    )
    return parser


def load_config(args: argparse.Namespace) -> Config:
    def getenv_compat(*names: str, default: str | None = None) -> str | None:
        for name in names:
            value = os.getenv(name)
            if value is not None:
                return value
        return default

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parents[2]
    root_env_path = repo_root / ".env"
    local_env_path = script_dir / ".env"

    # Ordem de carga:
    # 1. variaveis ja definidas no ambiente do processo
    # 2. .env central da raiz do Lumen
    # 3. .env local ao lado do coletor, apenas como fallback opcional
    if root_env_path.exists():
        load_dotenv(dotenv_path=root_env_path, override=False)
    if local_env_path.exists():
        load_dotenv(dotenv_path=local_env_path, override=False)

    password = os.getenv("DOMINIO_PASSWORD", "").strip()
    if not password:
        raise RuntimeError(
            "A variável DOMINIO_PASSWORD não foi encontrada. "
            f"Defina DOMINIO_PASSWORD no ambiente, em {root_env_path} "
            f"ou, opcionalmente, em {local_env_path}."
        )

    default_comp = previous_month_competencia()
    env_single_competencia = os.getenv("COMPETENCIA", "").strip()

    if args.competencia:
        competencia_de = args.competencia
        competencia_ate = args.competencia
    else:
        competencia_de = (
            args.competencia_de
            or os.getenv("COMPETENCIA_DE")
            or env_single_competencia
            or default_comp
        )
        competencia_ate = (
            args.competencia_ate
            or os.getenv("COMPETENCIA_ATE")
            or env_single_competencia
            or default_comp
        )

    competencia_de = validate_competencia(competencia_de)
    competencia_ate = validate_competencia(competencia_ate)

    dominio_exe = Path(getenv_compat("DOMINIO_EXE", default=r"C:\Contabil\contabil.exe"))

    output_dir = Path(
        getenv_compat(
            "DOMINIO_OUTPUT_DIR",
            "OUTPUT_DIR",
            default=str(script_dir / "Relatorios_Dominio"),
        )
    )

    if args.saida:
        output_path = Path(args.saida)
    else:
        if competencia_de == competencia_ate:
            filename = f"Resumo_Mensal_{competencia_for_filename(competencia_de)}.pdf"
        else:
            filename = (
                "Resumo_Mensal_"
                f"{competencia_for_filename(competencia_de)}_a_"
                f"{competencia_for_filename(competencia_ate)}.pdf"
            )
        output_path = output_dir / filename

    if output_path.suffix.lower() != ".pdf":
        output_path = output_path.with_suffix(".pdf")

    overwrite_pdf = not args.nao_sobrescrever
    overwrite_pdf_env = getenv_compat("DOMINIO_OVERWRITE_PDF", "OVERWRITE_PDF")
    if overwrite_pdf_env is not None:
        overwrite_pdf = parse_bool(overwrite_pdf_env, default=True)
    if args.nao_sobrescrever:
        overwrite_pdf = False

    close_dominio_after = parse_bool(
        getenv_compat("DOMINIO_CLOSE_DOMINIO_AFTER", "CLOSE_DOMINIO_AFTER"),
        default=False,
    ) or args.fechar_dominio

    log_path = Path(
        getenv_compat(
            "DOMINIO_LOG_PATH",
            "LOG_PATH",
            default=str(script_dir / "logs" / "gerar_resumo_mensal_dominio.log"),
        )
    )
    lock_path = script_dir / LOCK_FILE_NAME

    return Config(
        dominio_exe=dominio_exe,
        password=password,
        competencia_de=competencia_de,
        competencia_ate=competencia_ate,
        output_path=output_path,
        login_timeout=int(getenv_compat("DOMINIO_LOGIN_TIMEOUT", "LOGIN_TIMEOUT", default="90")),
        report_timeout=int(getenv_compat("DOMINIO_REPORT_TIMEOUT", "REPORT_TIMEOUT", default="1200")),
        save_timeout=int(getenv_compat("DOMINIO_SAVE_TIMEOUT", "SAVE_TIMEOUT", default="180")),
        overwrite_pdf=overwrite_pdf,
        close_dominio_after=close_dominio_after,
        log_path=log_path,
        lock_path=lock_path,
        export_retries=max(
            1,
            int(
                getenv_compat(
                    "DOMINIO_EXPORT_RETRIES",
                    "EXPORT_RETRIES",
                    default=str(DEFAULT_EXPORT_RETRIES),
                )
            ),
        ),
    )


def configure_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


def compute_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_text(path: Path, content: str) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    os.replace(temp_path, path)


def validate_pdf_file(path: Path, *, competencia: str) -> PdfValidationResult:
    if not path.exists():
        raise FileNotFoundError(f"Temporary PDF not found: {path}")
    if path.stat().st_size <= 0:
        raise ValueError(f"Temporary PDF is empty: {path}")
    with path.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            raise ValueError(f"Generated file is not a valid PDF: {path}")

    reader = PdfReader(str(path))
    if reader.is_encrypted:
        raise ValueError("Generated PDF is encrypted.")
    if len(reader.pages) < 1:
        raise ValueError("Generated PDF has no pages.")

    extracted_parts: list[str] = []
    for page in reader.pages:
        extracted_parts.append((page.extract_text() or "").strip())
    full_text = "\n".join(part for part in extracted_parts if part)
    if not full_text.strip():
        raise ValueError("Generated PDF does not contain extractable text.")
    upper_text = full_text.upper()
    if "RESUMO DA FOLHA" not in upper_text:
        raise ValueError("Generated PDF does not contain 'RESUMO DA FOLHA'.")
    if COMPETENCIA_IN_TEXT_RE.search(full_text) is None:
        raise ValueError("Generated PDF does not contain any recognizable competence.")
    if competencia not in full_text:
        logging.warning("Requested competence %s not found literally in extracted text.", competencia)
    if CNPJ_IN_TEXT_RE.search(full_text) is None:
        raise ValueError("Generated PDF does not contain any recognizable CNPJ.")

    return PdfValidationResult(
        page_count=len(reader.pages),
        sha256=compute_file_sha256(path),
        size_bytes=path.stat().st_size,
    )


def write_manifest(
    *,
    manifest_path: Path,
    output_path: Path,
    competencia_de: str,
    competencia_ate: str,
    validation: PdfValidationResult,
) -> None:
    payroll_competence, assessment_competence = map_payroll_to_assessment_competence(competencia_de)
    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "source": "DOMINIO_FOLHA_RESUMO",
        "evidence_source": "DOMINIO_FOLHA_PDF",
        "selection_scope": "ATIVAS",
        "payroll_competence": payroll_competence,
        "assessment_competence": assessment_competence,
        "generated_at": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(),
        "pdf_file_name": output_path.name,
        "pdf_sha256": validation.sha256,
        "pdf_size_bytes": validation.size_bytes,
        "pdf_page_count": validation.page_count,
        "status": "SUCCESS",
    }
    if competencia_ate != competencia_de:
        payroll_competence_end, assessment_competence_end = map_payroll_to_assessment_competence(competencia_ate)
        payload["range_mode"] = True
        payload["payroll_competence_end"] = payroll_competence_end
        payload["assessment_competence_end"] = assessment_competence_end

    atomic_write_text(
        manifest_path,
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
    )


# -----------------------------------------------------------------------------
# Utilitários UIA
# -----------------------------------------------------------------------------


def clipboard_paste(text: str) -> None:
    """Coloca o texto na área de transferência e envia Ctrl+V."""
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
    finally:
        win32clipboard.CloseClipboard()
    send_keys("^v")


def safe_set_text(control_spec, value: str) -> None:
    """Preenche controles PowerBuilder com fallback por teclado."""
    control_spec.wait("exists visible enabled", timeout=20)
    wrapper = control_spec.wrapper_object()

    try:
        if hasattr(wrapper, "set_edit_text"):
            wrapper.set_edit_text(value)
            current = ""
            try:
                current = str(wrapper.get_value()).strip()
            except Exception:
                pass
            if current == value:
                return
    except Exception:
        pass

    wrapper.click_input()
    send_keys("^a")
    clipboard_paste(value)


def wait_window_gone(window_spec, timeout: int) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if not window_spec.exists(timeout=0.5):
                return
        except Exception:
            return
        time.sleep(0.5)
    raise TimeoutError(f"A janela não fechou dentro de {timeout} segundos.")


def wait_for_save_dialog(app: Application, timeout: int = 20):
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            for wrapper in Desktop(backend="uia").windows(visible_only=True):
                info = wrapper.element_info
                if (
                    info.control_type == "Window"
                    and (info.name or "") == SAVE_PDF_TITLE
                    and info.class_name == "#32770"
                ):
                    return wrapper
        except Exception:
            pass

        dialog = find_window_in_process(
            app,
            title=SAVE_PDF_TITLE,
            class_name="#32770",
            main_win=find_main_window(app),
        )
        if dialog is not None:
            return dialog

        try:
            dialog = Desktop(backend="uia").window(
                title=SAVE_PDF_TITLE,
                class_name="#32770",
                control_type="Window",
            )
            if dialog.exists(timeout=FAST_EXISTS_TIMEOUT):
                return dialog
        except Exception:
            pass

        time.sleep(0.2)

    raise TimeoutError("A janela 'Salvar em PDF' não abriu.")


def connect_to_existing_dominio():
    try:
        main_win = Desktop(backend="uia").window(
            title_re=MAIN_TITLE_RE,
            class_name=MAIN_WINDOW_CLASS,
            control_type="Window",
        )
        if not main_win.exists(timeout=2):
            return None, None

        wrapper = main_win.wrapper_object()
        app = Application(backend="uia").connect(process=wrapper.process_id())
        logging.info("Reutilizando instância já aberta do Domínio Folha.")
        return app, app.window(handle=wrapper.handle)
    except Exception:
        return None, None


def find_main_window(app: Application):
    try:
        main_win = app.window(
            title_re=MAIN_TITLE_RE,
            class_name=MAIN_WINDOW_CLASS,
            control_type="Window",
        )
        if main_win.exists(timeout=FAST_EXISTS_TIMEOUT):
            return main_win
    except Exception:
        pass

    try:
        fallback = None
        for wrapper in Desktop(backend="uia").windows(visible_only=True):
            info = wrapper.element_info
            if info.process_id != app.process:
                continue
            if info.control_type != "Window":
                continue
            if info.class_name != MAIN_WINDOW_CLASS:
                continue
            if re.match(MAIN_TITLE_RE, info.name or ""):
                return app.window(handle=wrapper.handle)
            if fallback is None:
                fallback = wrapper
        if fallback is not None:
            return app.window(handle=fallback.handle)
    except Exception:
        pass

    return None


def wait_for_main_window(app: Application, timeout: int):
    deadline = time.time() + timeout
    while time.time() < deadline:
        close_startup_popups(timeout=0.2, app=app)
        main_win = find_main_window(app)
        if main_win is not None:
            return main_win
        time.sleep(0.2)
    raise TimeoutError("A janela principal do Domínio Folha não ficou disponível dentro do prazo.")


def get_workspace_pane(main_win):
    try:
        pane = main_win.child_window(
            auto_id=WORKSPACE_AUTO_ID,
            title=WORKSPACE_NAME,
            control_type="Pane",
        )
        if pane.exists(timeout=FAST_EXISTS_TIMEOUT):
            return pane
    except Exception:
        pass

    try:
        pane = main_win.child_window(
            auto_id=WORKSPACE_AUTO_ID,
            control_type="Pane",
        )
        if pane.exists(timeout=FAST_EXISTS_TIMEOUT):
            return pane
    except Exception:
        pass

    return main_win


def iter_process_windows(app: Application, main_win=None):
    seen_handles = set()

    try:
        for wrapper in Desktop(backend="uia").windows(visible_only=True):
            info = wrapper.element_info
            if info.process_id != app.process:
                continue
            handle = getattr(wrapper, "handle", None)
            if handle in seen_handles:
                continue
            seen_handles.add(handle)
            yield wrapper
    except Exception:
        pass

    if main_win is None:
        main_win = find_main_window(app)

    if main_win is None:
        return

    try:
        for wrapper in main_win.children(control_type="Window"):
            handle = getattr(wrapper, "handle", None)
            if handle in seen_handles:
                continue
            seen_handles.add(handle)
            yield wrapper
    except Exception:
        pass

    try:
        workspace = get_workspace_pane(main_win)
        for wrapper in workspace.children(control_type="Window"):
            handle = getattr(wrapper, "handle", None)
            if handle in seen_handles:
                continue
            seen_handles.add(handle)
            yield wrapper
    except Exception:
        pass


def resolve_report_window_from_control(control_wrapper, app: Application):
    current = control_wrapper
    for _ in range(8):
        if current is None:
            break
        try:
            info = current.element_info
            if (
                info.control_type == "Window"
                and info.class_name == MAIN_WINDOW_CLASS
                and (info.name or "") == REPORT_TITLE
            ):
                return app.window(handle=current.handle)
        except Exception:
            pass
        try:
            current = current.parent()
        except Exception:
            break
    return None


def find_descendant_button(container, title: str, auto_id: Optional[str] = None):
    try:
        button = container.child_window(
            title=title,
            auto_id=auto_id,
            control_type="Button",
        )
        if button.exists(timeout=1):
            return button
    except Exception:
        pass

    try:
        for button in container.descendants(control_type="Button"):
            info = button.element_info
            if (info.name or "") != title:
                continue
            if auto_id is not None and str(info.automation_id or "") != str(auto_id):
                continue
            return container.child_window(handle=button.handle)
    except Exception:
        pass

    return None


def find_descendant_combobox(container, auto_id: Optional[str] = None):
    try:
        combo = container.child_window(
            auto_id=auto_id,
            control_type="ComboBox",
        )
        if combo.exists(timeout=1):
            return combo
    except Exception:
        pass

    try:
        for combo in container.descendants(control_type="ComboBox"):
            info = combo.element_info
            if auto_id is not None and str(info.automation_id or "") != str(auto_id):
                continue
            return container.child_window(handle=combo.handle)
    except Exception:
        pass

    return None


def find_window_in_process(
    app: Application,
    title: str,
    class_name: Optional[str] = None,
    main_win=None,
):
    for wrapper in iter_process_windows(app, main_win):
        try:
            info = wrapper.element_info
            if info.control_type != "Window":
                continue
            if (info.name or "") != title:
                continue
            if class_name is not None and info.class_name != class_name:
                continue
            return app.window(handle=wrapper.handle)
        except Exception:
            continue
    return None


def wait_for_named_window(
    app: Application,
    title: str,
    timeout: int,
    class_name: Optional[str] = None,
    main_win=None,
):
    deadline = time.time() + timeout
    while time.time() < deadline:
        window = find_window_in_process(
            app,
            title=title,
            class_name=class_name,
            main_win=main_win,
        )
        if window is not None:
            return window

        try:
            desktop_window = Desktop(backend="uia").window(
                title=title,
                class_name=class_name,
                control_type="Window",
            )
            if desktop_window.exists(timeout=0.3):
                return desktop_window
        except Exception:
            pass

        time.sleep(0.3)

    raise TimeoutError(f"A janela '{title}' não abriu.")


def dismiss_dashboard_warning() -> bool:
    try:
        dialog = None
        for wrapper in Desktop(backend="uia").windows(visible_only=True):
            info = wrapper.element_info
            if (
                info.control_type == "Window"
                and info.class_name == WARNING_DIALOG_CLASS
                and (info.name or "") == WARNING_DIALOG_TITLE
            ):
                dialog = wrapper
                break
        if dialog is None:
            return False
        ok_button = dialog.child_window(
            auto_id=WARNING_OK_AUTO_ID,
            title="OK",
            control_type="Button",
        )
        ok_button.wait("exists visible enabled", timeout=5)
        ok_button.click_input()
        logging.info("Aviso inicial do dashboard fechado.")
        wait_window_gone(dialog, timeout=10)
        return True
    except Exception:
        return False


def dismiss_expiration_warning() -> bool:
    try:
        dialog = None
        for wrapper in Desktop(backend="uia").windows(visible_only=True):
            info = wrapper.element_info
            if (
                info.control_type == "Window"
                and (info.name or "") == EXPIRATION_TITLE
                and str(info.automation_id or "") == EXPIRATION_AUTO_ID
            ):
                dialog = wrapper
                break
        if dialog is None:
            return False
        close_button = dialog.child_window(
            auto_id=EXPIRATION_CLOSE_AUTO_ID,
            title="Fechar",
            control_type="Button",
        )
        close_button.wait("exists visible enabled", timeout=5)
        close_button.click_input()
        logging.info("Janela de avisos de vencimento fechada.")
        wait_window_gone(dialog, timeout=10)
        return True
    except Exception:
        try:
            dialog.close()
            logging.info("Janela de avisos de vencimento fechada pelo botão padrão da janela.")
            return True
        except Exception:
            pass
        return False


def dismiss_process_popups(app: Application, main_win=None) -> bool:
    handled = False

    for wrapper in iter_process_windows(app, main_win):
        try:
            info = wrapper.element_info
            if (info.name or "") == EXPIRATION_TITLE:
                close_button = wrapper.child_window(
                    auto_id=EXPIRATION_CLOSE_AUTO_ID,
                    title="Fechar",
                    control_type="Button",
                )
                close_button.wait("exists visible enabled", timeout=2)
                close_button.click_input()
                logging.info("Janela de avisos de vencimento fechada dentro do workspace.")
                handled = True
                continue
        except Exception:
            pass

        try:
            info = wrapper.element_info
            if (info.name or "") == WARNING_DIALOG_TITLE:
                try:
                    wrapper.set_focus()
                    send_keys("{ENTER}")
                    logging.info("Aviso inicial do dashboard fechado com Enter.")
                    handled = True
                    continue
                except Exception:
                    pass
                ok_button = wrapper.child_window(
                    auto_id=WARNING_OK_AUTO_ID,
                    title="OK",
                    control_type="Button",
                )
                ok_button.wait("exists visible enabled", timeout=2)
                try:
                    ok_button.wrapper_object().invoke()
                except Exception:
                    ok_button.click_input()
                logging.info("Aviso inicial do dashboard fechado dentro do workspace.")
                handled = True
        except Exception:
            pass

    return handled


def close_foreground_popup_with_alt_f4() -> bool:
    try:
        active = Desktop(backend="uia").get_active()
        if active is None:
            return False
        name = active.element_info.name or ""
        if name not in {WARNING_DIALOG_TITLE, EXPIRATION_TITLE}:
            return False
        active.set_focus()
        send_keys("%{F4}")
        logging.info("Popup fechado com Alt+F4: %s", name)
        return True
    except Exception:
        return False


def close_startup_popups(timeout: int = 20, app: Optional[Application] = None, main_win=None) -> None:
    deadline = time.time() + timeout

    while time.time() < deadline:
        handled = False
        if dismiss_dashboard_warning():
            handled = True
        if dismiss_expiration_warning():
            handled = True
        if app is not None and dismiss_process_popups(app, main_win):
            handled = True
        if close_foreground_popup_with_alt_f4():
            handled = True
        if not handled:
            return


def find_existing_report_window(app: Application, main_win=None):
    if main_win is None:
        main_win = find_main_window(app)

    try:
        report_win = app.window(
            title=REPORT_TITLE,
            auto_id=REPORT_AUTO_ID,
            class_name=MAIN_WINDOW_CLASS,
            control_type="Window",
        )
        if report_win.exists(timeout=FAST_EXISTS_TIMEOUT):
            return report_win
    except Exception:
        pass

    try:
        if main_win is not None:
            workspace = get_workspace_pane(main_win)
            for wrapper in workspace.children(control_type="Window"):
                info = wrapper.element_info
                if (
                    (info.name or "") == REPORT_TITLE
                    and info.class_name == MAIN_WINDOW_CLASS
                    and str(info.automation_id or "") in {"", REPORT_AUTO_ID}
                ):
                    return app.window(handle=wrapper.handle)
    except Exception:
        pass

    try:
        if main_win is not None:
            workspace = get_workspace_pane(main_win)
            report_controls = workspace.descendants(
                title="Empresas...",
                control_type="Button",
            )
            for control in report_controls:
                report_win = resolve_report_window_from_control(control, app)
                if report_win is not None:
                    return report_win
    except Exception:
        pass

    try:
        if main_win is not None:
            workspace = get_workspace_pane(main_win)
            for button_name in ("Empresas...", "Concluir Atividade...", "OK", "Fechar"):
                report_controls = workspace.descendants(
                    title=button_name,
                    control_type="Button",
                )
                for control in report_controls:
                    report_win = resolve_report_window_from_control(control, app)
                    if report_win is not None:
                        return report_win
    except Exception:
        pass

    return None


def find_report_preview(app: Application, timeout: int):
    """Localiza a janela do relatório gerado."""
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            windows = list(iter_process_windows(app))
        except Exception:
            windows = []

        for wrapper in windows:
            try:
                info = wrapper.element_info
                if info.control_type != "Window":
                    continue
                if (info.name or "") != REPORT_TITLE:
                    continue

                for elem in wrapper.descendants():
                    child_info = elem.element_info
                    if (
                        child_info.control_type == "Pane"
                        and (
                            str(child_info.automation_id or "") == PDF_PANEL_AUTO_ID
                            or (
                                str(child_info.automation_id or "") == "1002"
                                and child_info.class_name == "pbdw190"
                            )
                        )
                    ):
                        return app.window(handle=wrapper.handle)
            except Exception:
                continue

        time.sleep(0.3)

    raise TimeoutError(
        "A visualização do relatório não ficou disponível dentro do prazo."
    )


# -----------------------------------------------------------------------------
# Domínio: inicialização e login
# -----------------------------------------------------------------------------


def start_dominio_folha(config: Config) -> Application:
    if not config.dominio_exe.exists():
        raise FileNotFoundError(
            f"Executável do Domínio não encontrado: {config.dominio_exe}"
        )

    command_line = f'"{config.dominio_exe}" /folha'
    logging.info("Iniciando o módulo Folha do Domínio.")

    app = Application(backend="uia").start(
        command_line,
        timeout=config.login_timeout,
    )
    return app


def login_dominio(app: Application, config: Config):
    logging.info("Aguardando a janela de login.")
    login_win = app.window(title_re=LOGIN_TITLE_RE)
    login_win.wait("exists visible enabled", timeout=config.login_timeout)
    login_win.set_focus()

    password_field = login_win.child_window(
        auto_id=LOGIN_PASSWORD_AUTO_ID,
        control_type="Edit",
    )
    password_field.wait("exists visible enabled", timeout=30)
    password_field.click_input()
    send_keys("^a")
    password_field.type_keys(config.password, with_spaces=True)

    login_button = login_win.child_window(
        auto_id=LOGIN_BUTTON_AUTO_ID,
        control_type="Button",
    )
    login_button.wait("exists visible enabled", timeout=20)
    login_button.click_input()

    logging.info("Credenciais enviadas; aguardando a janela principal.")
    main_win = wait_for_main_window(app, timeout=config.login_timeout)
    close_startup_popups(timeout=0.2, app=app, main_win=main_win)
    main_win.set_focus()

    logging.info("Login confirmado no módulo Folha.")
    return main_win


# -----------------------------------------------------------------------------
# Domínio: navegação e geração do relatório
# -----------------------------------------------------------------------------


def open_resumo_mensal(app: Application, main_win, skip_existing_check: bool = False):
    if not skip_existing_check:
        existing_report = find_existing_report_window(app, main_win)
        if existing_report is not None:
            logging.info("Janela 'Resumo Mensal' já estava aberta.")
            existing_report.set_focus()
            return existing_report

    logging.info("Abrindo Relatórios > Folha > Resumo.")
    main_win.set_focus()
    close_startup_popups(timeout=0.2, app=app, main_win=main_win)

    # Estratégia principal: atalhos definidos pelo próprio menu.
    try:
        send_keys("%r")  # Alt+R: Relatórios
        time.sleep(0.2)
        send_keys("f")   # Folha
        time.sleep(0.2)
        send_keys("r")   # Resumo
    except Exception as exc:
        logging.warning("Falha na navegação por teclado: %s", exc)

    deadline = time.time() + 8
    while time.time() < deadline:
        close_startup_popups(timeout=1, app=app, main_win=main_win)
        report_win = find_existing_report_window(app, main_win)
        if report_win is not None:
            logging.info("Janela 'Resumo Mensal' aberta.")
            return report_win
        time.sleep(0.3)

    logging.warning(
        "A janela não abriu pelos atalhos. Tentando clicar nos menus via UIA."
    )

    # Fallback UIA para menus que estejam expostos na árvore de acessibilidade.
    main_win.set_focus()
    close_startup_popups(timeout=0.2, app=app, main_win=main_win)

    report_win = find_existing_report_window(app, main_win)
    if report_win is not None:
        logging.info("Janela 'Resumo Mensal' encontrada antes do fallback UIA.")
        report_win.set_focus()
        return report_win

    # O fallback por menu UIA global tem sido instável. Reaplica os atalhos
    # com o foco saneado e prioriza a detecção do formulário já aberto.
    send_keys("%r")
    time.sleep(0.2)
    send_keys("f")
    time.sleep(0.2)
    send_keys("r")

    deadline = time.time() + 8
    report_win = None
    while time.time() < deadline:
        close_startup_popups(timeout=1, app=app, main_win=main_win)
        report_win = find_existing_report_window(app, main_win)
        if report_win is not None:
            break
        time.sleep(0.3)
    if report_win is None:
        raise TimeoutError("A janela 'Resumo Mensal' não foi localizada após o fallback UIA.")
    logging.info("Janela 'Resumo Mensal' aberta pelo fallback UIA.")
    return report_win


def fill_competencias(report_win, config: Config) -> None:
    logging.info(
        "Preenchendo competências: de %s até %s.",
        config.competencia_de,
        config.competencia_ate,
    )

    field_de = report_win.child_window(
        auto_id=COMPETENCIA_DE_AUTO_ID,
        control_type="Edit",
        class_name="PBEDIT190",
    )
    field_ate = report_win.child_window(
        auto_id=COMPETENCIA_ATE_AUTO_ID,
        control_type="Edit",
        class_name="PBEDIT190",
    )

    safe_set_text(field_de, config.competencia_de)
    safe_set_text(field_ate, config.competencia_ate)


def select_active_companies(app: Application, report_win, main_win=None) -> None:
    logging.info("Abrindo o filtro de empresas.")
    report_win.set_focus()
    send_keys("%e")
    time.sleep(0.5)

    selector = None
    try:
        selector = wait_for_named_window(
            app,
            title=SELECT_COMPANIES_TITLE,
            class_name="FNWNS3190",
            timeout=3,
            main_win=main_win,
        )
        selector.set_focus()
    except Exception:
        selector = None

    if selector is not None:
        combo = find_descendant_combobox(selector, auto_id="1010")
        if combo is not None:
            try:
                combo.wait("exists visible enabled", timeout=3)
                combo.set_focus()
            except Exception:
                try:
                    combo.click_input()
                except Exception:
                    pass

    send_keys("%{DOWN}")
    time.sleep(0.2)
    send_keys("ativas", with_spaces=True)
    send_keys("{ENTER}")

    logging.info("Filtro 'Ativas' selecionado.")

    send_keys("%o")

    if selector is not None:
        try:
            wait_window_gone(selector, timeout=10)
        except Exception:
            pass

    logging.info("Seleção de empresas confirmada.")


def generate_report(report_win) -> None:
    logging.info("Iniciando a geração do relatório.")
    report_win.set_focus()
    send_keys("%o")


def wait_report_processing(app: Application, timeout: int) -> None:
    logging.info("Aguardando o processamento do relatório.")
    def processing_popup_exists() -> bool:
        for wrapper in iter_process_windows(app):
            try:
                info = wrapper.element_info
                if info.control_type != "Window" or info.class_name != "FNWNS3190":
                    continue
                if (info.name or "") not in {"", PROCESSING_TEXT}:
                    continue
                for child in wrapper.descendants():
                    child_info = child.element_info
                    if (
                        child_info.control_type == "Text"
                        and (child_info.name or "") == PROCESSING_TEXT
                    ):
                        return True
            except Exception:
                continue
        return False

    def generated_report_exists() -> bool:
        for wrapper in iter_process_windows(app):
            try:
                for child in wrapper.descendants(control_type="Pane"):
                    info = child.element_info
                    if (
                        str(info.automation_id or "") == "1002"
                        and info.class_name == "pbdw190"
                    ):
                        return True
            except Exception:
                continue
        return False

    appeared = False
    appearance_deadline = time.time() + min(20, timeout)
    while time.time() < appearance_deadline:
        if processing_popup_exists():
            appeared = True
            logging.info("Mensagem de processamento identificada.")
            break
        if generated_report_exists():
            logging.info("Visualização do relatório identificada sem popup de processamento.")
            return
        time.sleep(0.3)

    deadline = time.time() + timeout
    while time.time() < deadline:
        if appeared and not processing_popup_exists():
            logging.info("Processamento concluído.")
            time.sleep(1)
            return
        if generated_report_exists():
            logging.info("Visualização do relatório identificada.")
            return
        time.sleep(1)

    raise TimeoutError(
        f"O relatório não concluiu o processamento em {timeout} segundos."
    )


# -----------------------------------------------------------------------------
# Domínio: exportação e validação do PDF
# -----------------------------------------------------------------------------


def open_pdf_export(app: Application, report_preview, timeout: int = 30):
    # Evita disparar novamente caso o diálogo já esteja aberto.
    existing_dialog = Desktop(backend="uia").window(
        title=SAVE_PDF_TITLE,
        class_name="#32770",
        control_type="Window",
    )
    if existing_dialog.exists(timeout=1):
        return existing_dialog

    # 1. Estratégia principal: atalho oficial Ctrl+D.
    try:
        logging.info("Abrindo a exportação em PDF com Ctrl+D.")
        report_preview.set_focus()
        time.sleep(0.2)
        send_keys("^d")
        return wait_for_save_dialog(app, timeout=min(5, timeout))
    except Exception as exc:
        logging.warning("Ctrl+D não abriu o diálogo de PDF: %s", exc)

    # 2. Ícone interno: Image, auto_id 1000, class_name Button.
    try:
        logging.info("Tentando acionar diretamente o ícone PDF via UIA.")
        pdf_panel = report_preview.child_window(
            auto_id=PDF_PANEL_AUTO_ID,
            control_type="Pane",
            class_name="FNUDO3190",
        )
        pdf_panel.wait("exists visible enabled", timeout=15)

        pdf_icon = pdf_panel.child_window(
            auto_id=PDF_ICON_AUTO_ID,
            control_type="Image",
            class_name="Button",
        )
        pdf_icon.wait("exists visible enabled", timeout=15)
        icon_wrapper = pdf_icon.wrapper_object()

        try:
            icon_wrapper.invoke()
        except Exception:
            icon_wrapper.click_input()

        return wait_for_save_dialog(app, timeout=min(5, timeout))
    except Exception as exc:
        logging.warning("O ícone PDF não pôde ser acionado: %s", exc)

    # 3. Último recurso: clicar no painel externo 1016.
    try:
        logging.info("Tentando clicar no painel externo do botão PDF.")
        pdf_panel = report_preview.child_window(
            auto_id=PDF_PANEL_AUTO_ID,
            control_type="Pane",
            class_name="FNUDO3190",
        )
        pdf_panel.wait("exists visible enabled", timeout=15)
        pdf_panel.click_input()
        return wait_for_save_dialog(app, timeout=min(5, timeout))
    except Exception as exc:
        raise RuntimeError(
            "Não foi possível abrir a exportação em PDF por Ctrl+D, "
            "pelo ícone UIA ou pelo painel externo."
        ) from exc


def open_pdf_export_with_retry(app: Application, report_preview, *, retries: int, timeout: int = 30):
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            logging.info("PDF export attempt %d/%d.", attempt, retries)
            report_preview.set_focus()
            time.sleep(0.3)
            return open_pdf_export(app, report_preview, timeout=timeout)
        except Exception as exc:
            last_error = exc
            logging.warning("PDF export attempt %d/%d failed: %s", attempt, retries, exc)
            try:
                report_preview = find_report_preview(app, timeout=10)
                report_preview.set_focus()
            except Exception as focus_exc:
                logging.warning("Could not relocate report preview after export failure: %s", focus_exc)
            time.sleep(1)
    raise RuntimeError(f"PDF export failed after {retries} attempts.") from last_error


def prepare_output_file(config: Config) -> None:
    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    config.log_path.parent.mkdir(parents=True, exist_ok=True)

    if config.output_path.exists() and not config.overwrite_pdf:
        raise FileExistsError(
            f"O PDF já existe e a sobrescrita está desativada: {config.output_path}"
        )

    build_partial_pdf_path(config.output_path).unlink(missing_ok=True)


def finalize_valid_pdf(config: Config, partial_path: Path, validation: PdfValidationResult) -> Path:
    logging.info(
        "Validated temporary PDF with %d page(s), %d bytes and SHA-256 %s.",
        validation.page_count,
        validation.size_bytes,
        validation.sha256,
    )
    os.replace(partial_path, config.output_path)
    logging.info("Updated final PDF atomically: %s", config.output_path)
    return config.output_path


def save_pdf(save_dialog, output_path: Path) -> None:
    logging.info("Salvando PDF em: %s", output_path)
    save_dialog.set_focus()
    send_keys("%n")
    time.sleep(0.2)
    send_keys("^a")
    clipboard_paste(str(output_path))
    time.sleep(0.2)
    send_keys("%l")


def wait_pdf_created(path: Path, timeout: int) -> Path:
    deadline = time.time() + timeout
    last_size = -1
    stable_checks = 0

    while time.time() < deadline:
        if path.exists():
            try:
                size = path.stat().st_size
            except OSError:
                size = 0

            if size > 0 and size == last_size:
                stable_checks += 1
            else:
                stable_checks = 0

            last_size = size

            # Duas verificações consecutivas com o mesmo tamanho indicam que a
            # gravação terminou, inclusive em pasta de rede.
            if size > 0 and stable_checks >= 2:
                logging.info("PDF criado com sucesso: %s (%d bytes)", path, size)
                return path

        time.sleep(1)

    raise TimeoutError(
        f"O arquivo PDF não foi criado ou não terminou de gravar em {timeout} segundos: {path}"
    )


# -----------------------------------------------------------------------------
# Execução principal
# -----------------------------------------------------------------------------


def run(config: Config) -> Path:
    prepare_output_file(config)

    app: Optional[Application] = None
    success = False
    started_new_instance = False
    partial_path = build_partial_pdf_path(config.output_path)
    manifest_path = build_manifest_path(config.output_path)

    try:
        app, main_win = connect_to_existing_dominio()
        if app is None or main_win is None:
            app = start_dominio_folha(config)
            started_new_instance = True
            main_win = login_dominio(app, config)
        else:
            close_startup_popups(timeout=10, app=app, main_win=main_win)
            main_win.set_focus()

        report_form = open_resumo_mensal(
            app,
            main_win,
            skip_existing_check=started_new_instance,
        )
        fill_competencias(report_form, config)
        select_active_companies(app, report_form, main_win)
        generate_report(report_form)

        wait_report_processing(app, timeout=config.report_timeout)
        report_preview = find_report_preview(app, timeout=config.report_timeout)

        save_dialog = open_pdf_export_with_retry(
            app,
            report_preview,
            retries=config.export_retries,
            timeout=30,
        )
        save_pdf(save_dialog, partial_path)

        pdf_path = wait_pdf_created(partial_path, timeout=config.save_timeout)
        validation = validate_pdf_file(pdf_path, competencia=config.competencia_de)
        final_path = finalize_valid_pdf(config, partial_path, validation)
        write_manifest(
            manifest_path=manifest_path,
            output_path=final_path,
            competencia_de=config.competencia_de,
            competencia_ate=config.competencia_ate,
            validation=validation,
        )
        success = True
        return final_path

    finally:
        if not success:
            partial_path.unlink(missing_ok=True)
        if app is not None and success and config.close_dominio_after and started_new_instance:
            try:
                logging.info("Fechando o Domínio.")
                app.kill()
            except Exception as exc:
                logging.warning("Não foi possível fechar o Domínio: %s", exc)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    lock: CollectorLock | None = None

    try:
        config = load_config(args)
        configure_logging(config.log_path)
        lock = CollectorLock(config.lock_path)
        lock.acquire()

        logging.info("=" * 72)
        logging.info("Automação Domínio Folha - Resumo Mensal")
        logging.info("Competência inicial: %s", config.competencia_de)
        logging.info("Competência final: %s", config.competencia_ate)
        logging.info("Destino: %s", config.output_path)
        if config.competencia_de == config.competencia_ate:
            payroll_competence, assessment_competence = map_payroll_to_assessment_competence(config.competencia_de)
            logging.info(
                "Preferred monthly flow: payroll %s -> assessment %s.",
                payroll_competence,
                assessment_competence,
            )
        else:
            logging.warning(
                "Range mode enabled from %s to %s. Lumen should prefer a single competence per PDF.",
                config.competencia_de,
                config.competencia_ate,
            )

        pdf_path = run(config)
        logging.info("Execução concluída: %s", pdf_path)
        return 0

    except KeyboardInterrupt:
        logging.error("Execução cancelada pelo usuário.")
        return 130
    except Exception:
        # Se o logging ainda não tiver sido configurado, basicConfig garante
        # que a exceção continue visível no terminal.
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO)
        logging.exception("A automação foi encerrada com erro.")
        return 1
    finally:
        if lock is not None:
            lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
