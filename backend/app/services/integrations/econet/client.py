from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit

from bs4 import BeautifulSoup
import httpx

from backend.app.core.config import Settings

from .assisted_session import get_econet_assisted_session
from .encoding import decode_econet_html
from .errors import (
    EconetHtmlDecodingError,
    EconetSessionDisabledError,
    EconetSessionExpiredError,
    EconetSessionInvalidError,
    EconetTransportError,
    EconetUnexpectedContentTypeError,
    EconetUnexpectedRedirectError,
    EconetUnexpectedResponseError,
)


SEARCH_PATH = "/ferramentas/regimes_cnae/buscaCnae.php"
INDEX_PATH = "/ferramentas/regimes_cnae/index.php"
SUB_ABAS_PATH = "/ferramentas/regimes_cnae/subAbas.php"
ABAS_PATH = "/ferramentas/regimes_cnae/abas.php"
ALLOWED_ABAS = {
    "lucroPresumido",
    "lucroRealTrimestral",
    "lucroRealEstimativa",
    "simplesNacionalTributacao",
    "empreendedorIndividual",
    "pjGeral",
    "optanteSimplesNacional",
    "optanteSimei",
    "obrigacoes",
}
ABA_EXPECTED_MARKERS = {
    "lucroPresumido": ("lucro presumido",),
    "lucroRealTrimestral": ("lucro real", "regime opcional"),
    "lucroRealEstimativa": ("lucro real", "regime opcional"),
    "simplesNacionalTributacao": ("simples nacional", "anexo"),
    "empreendedorIndividual": ("mei", "microempreendedor individual", "enquadramento"),
    "pjGeral": ("pj em geral", "obrigacao"),
    "optanteSimplesNacional": ("simples nacional", "obrigacao"),
    "optanteSimei": ("microempreendedor individual", "simei"),
    "obrigacoes": ("pj em geral", "optante simples nacional", "optante simei"),
}
ALLOWED_REDIRECT_HOSTS = {"www.econeteditora.com.br", "econeteditora.com.br"}


class EconetClient:
    def __init__(
        self,
        *,
        settings: Settings,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self.session = get_econet_assisted_session(settings)
        self._owns_client = http_client is None
        self._http_client = http_client or httpx.Client(
            base_url=settings.econet_base_url,
            timeout=settings.econet_timeout_seconds,
            follow_redirects=False,
            headers={"Accept": "text/html, text/plain;q=0.9"},
        )

    def close(self) -> None:
        if self._owns_client:
            self._http_client.close()

    def __enter__(self) -> "EconetClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def probe_session(self) -> dict[str, str]:
        self._request_html(INDEX_PATH, params=None, expected_markers=("consulta por cnae", "cnae"))
        return self.session.mark_valid()

    def search_cnae(self, term: str) -> str:
        clean_term = term.strip()
        if not clean_term or len(clean_term) > 80:
            raise EconetSessionInvalidError("Econet CNAE search term must have between 1 and 80 characters.")
        return self._request_html(SEARCH_PATH, params={"busca": clean_term}, expected_markers=("idcnae", "cnae"))

    def get_cnae_detail(self, econet_id_cnae: str) -> str:
        return self._request_html(
            INDEX_PATH,
            params={"idcnae": self._normalize_econet_id(econet_id_cnae), "acao": "abrir"},
            expected_markers=("consulta por cnae", "cnae:", "regimes tribut", "pessoa jurid"),
        )

    def get_lucro_presumido(self, econet_id_cnae: str) -> str:
        return self._get_sub_aba("lucroPresumido", econet_id_cnae)

    def get_lucro_real_trimestral(self, econet_id_cnae: str) -> str:
        return self._get_sub_aba("lucroRealTrimestral", econet_id_cnae)

    def get_lucro_real_estimativa(self, econet_id_cnae: str) -> str:
        return self._get_sub_aba("lucroRealEstimativa", econet_id_cnae)

    def get_simples_nacional(self, econet_id_cnae: str) -> str:
        return self._get_sub_aba("simplesNacionalTributacao", econet_id_cnae)

    def get_empreendedor_individual(self, econet_id_cnae: str) -> str:
        return self._get_sub_aba("empreendedorIndividual", econet_id_cnae)

    def get_obligation_tabs(self, econet_id_cnae: str) -> str:
        return self._request_html(
            ABAS_PATH,
            params={"aba": "obrigacoes", "idCnae": self._normalize_econet_id(econet_id_cnae)},
            expected_markers=("pj em geral", "optante simples nacional", "optante simei"),
        )

    def get_obligations_general(self, econet_id_cnae: str) -> str:
        return self._get_sub_aba("pjGeral", econet_id_cnae)

    def get_obligations_simples(self, econet_id_cnae: str) -> str:
        return self._get_sub_aba("optanteSimplesNacional", econet_id_cnae)

    def get_obligations_simei(self, econet_id_cnae: str) -> str:
        return self._get_sub_aba("optanteSimei", econet_id_cnae)

    def _get_sub_aba(self, aba: str, econet_id_cnae: str) -> str:
        if aba not in ALLOWED_ABAS:
            raise EconetSessionInvalidError("Econet sub-tab is not allowlisted.")
        return self._request_html(
            SUB_ABAS_PATH,
            params={"aba": aba, "idCnae": self._normalize_econet_id(econet_id_cnae)},
            expected_markers=ABA_EXPECTED_MARKERS[aba],
        )

    def _request_html(
        self,
        path: str,
        *,
        params: dict[str, str] | None,
        expected_markers: Iterable[str],
    ) -> str:
        if not self.settings.econet_assisted_session_enabled:
            raise EconetSessionDisabledError("Econet assisted session is disabled.")
        if path not in {SEARCH_PATH, INDEX_PATH, SUB_ABAS_PATH, ABAS_PATH}:
            raise EconetSessionInvalidError("Econet client rejected an arbitrary path.")

        with self.session.exclusive():
            cookies = self.session.build_cookie_jar()
            self._http_client.cookies.clear()
            self._http_client.cookies.update(cookies)
            try:
                response = self._http_client.get(path, params=params)
            except httpx.TimeoutException as exc:
                self.session.mark_error("timeout")
                raise EconetTransportError("Timeout while calling Econet.") from exc
            except httpx.TransportError as exc:
                self.session.mark_error("transport_error")
                raise EconetTransportError("Transport error while calling Econet.") from exc

            if 300 <= response.status_code < 400:
                self._handle_redirect(response)
            if response.status_code in {401, 403}:
                self.session.mark_expired(f"http_{response.status_code}")
                raise EconetSessionExpiredError("Econet session expired.")
            if response.status_code >= 400:
                self.session.mark_error(f"http_{response.status_code}")
                raise EconetUnexpectedResponseError(f"Econet returned HTTP {response.status_code}.")

            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type and "text/plain" not in content_type:
                self.session.mark_error("unexpected_content_type")
                raise EconetUnexpectedContentTypeError("Econet returned unexpected content type.")

            try:
                body = self._decode_html_response(response)
            except EconetHtmlDecodingError:
                self.session.mark_error("decode_error")
                raise
            self._ensure_authenticated_html(body)
            self._ensure_expected_markers(body, expected_markers)
            return body

    def _handle_redirect(self, response: httpx.Response) -> None:
        location = response.headers.get("location", "")
        target = urlsplit(location)
        if target.scheme and target.scheme != "https":
            self.session.mark_invalid("redirect_scheme")
            raise EconetUnexpectedRedirectError("Econet returned an unsafe redirect.")
        if target.hostname and target.hostname not in ALLOWED_REDIRECT_HOSTS:
            self.session.mark_invalid("redirect_external_host")
            raise EconetUnexpectedRedirectError("Econet returned an external redirect.")
        lowered = f"{target.path}?{target.query}".lower()
        if "login" in lowered or "autentic" in lowered or "captcha" in lowered:
            self.session.mark_expired("redirect_login")
            raise EconetSessionExpiredError("Econet session expired.")
        self.session.mark_error("unexpected_redirect")
        raise EconetUnexpectedRedirectError("Econet returned an unexpected redirect.")

    def _ensure_authenticated_html(self, html: str) -> None:
        text = " ".join(BeautifulSoup(html, "lxml").get_text(" ", strip=True).lower().split())
        if "captcha" in text or "g recaptcha" in text or ("login" in text and "consulta por cnae" not in text):
            self.session.mark_expired("authentication_page")
            raise EconetSessionExpiredError("Econet session expired.")

    def _ensure_expected_markers(self, html: str, markers: Iterable[str]) -> None:
        text = " ".join(BeautifulSoup(html, "lxml").get_text(" ", strip=True).lower().split())
        if not any(marker.lower() in text for marker in markers):
            self.session.mark_error("unexpected_contract")
            raise EconetUnexpectedResponseError("Econet returned an unexpected HTML contract.")

    @staticmethod
    def _decode_html_response(response: httpx.Response) -> str:
        return decode_econet_html(response.content, response.headers.get("content-type"))

    @staticmethod
    def _normalize_econet_id(value: str) -> str:
        clean_value = value.strip()
        if not clean_value or len(clean_value) > 32 or not clean_value.replace("-", "").replace("_", "").isalnum():
            raise EconetSessionInvalidError("Econet idcnae is invalid.")
        return clean_value
