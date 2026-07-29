from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
import re
from time import perf_counter
from typing import Any, Sequence

from pypdf import PdfReader

from backend.app.services.integrations.dominio.competence import map_payroll_to_assessment_competence
from backend.app.services.integrations.dominio.contracts import (
    DominioCnpjStatus,
    DominioDocumentContract,
    DominioEvidenceSource,
    DominioInformedValueKind,
    DominioParserConfidence,
    DominioPayrollBlock,
    DominioPayrollBlockType,
    DominioPayrollCompany,
    DominioPayrollReport,
    DominioPayrollRubric,
    DominioPayrollSection,
    DominioPayrollSectionType,
    DominioPayrollSignalEvidence,
    DominioPayrollWarning,
    DominioPayrollWarningCode,
)
from backend.app.services.integrations.dominio.normalization import (
    DominioNormalizedCnpj,
    normalize_cnpj_for_dominio,
    normalize_dominio_text,
    parse_brazilian_date_to_iso,
    parse_brazilian_decimal,
    parse_competence_header_to_iso,
    parse_informed_value,
)
from backend.app.services.integrations.dominio.rubrics import classify_rubric_signals


DOMINIO_PAYROLL_PARSER_VERSION = "dominio-payroll-s9.1"
PDF_SIGNATURE = b"%PDF-"

PAGE_LABEL_RE = re.compile(r"(?P<current>\d+)/(?P<total>\d+)P(?:agina|ágina):")
COMPANY_LINE_RE = re.compile(r"^Empresa:\s*(?P<company>.+)$", flags=re.IGNORECASE)
COMPANY_CODE_RE = re.compile(r"^(?P<code>\d+)\s*-\s*(?P<name>.+)$")
CNPJ_LINE_RE = re.compile(
    r"CNPJ:\s*(?P<cnpj>\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{14})",
    flags=re.IGNORECASE,
)
CALCULATION_RE = re.compile(r"C(?:alculo|álculo):\s*(?P<value>.+?)\s+Hora:", flags=re.IGNORECASE)
COMPETENCE_RE = re.compile(r"Compet(?:encia|ência):\s*(?P<value>\d{2}/\d{4})", flags=re.IGNORECASE)
HEADER_FILTER_RE = re.compile(
    r"^(?:\d+/\d+P(?:agina|ágina):|RESUMO DA FOLHA|Empresa:|CNPJ:|Emiss(?:ao|ão):|C(?:alculo|álculo):|Compet(?:encia|ência):|Complemento de c(?:alculo|álculo):|Nº Empregados/ContribuintesNome da RubricaRubrica Valor informado Valor Calculado|Sistema licenciado para )",
    flags=re.IGNORECASE,
)
RUBRIC_RE = re.compile(
    r"^(?P<prefix>.+?)\s+(?P<count>\d+)\s+(?P<informed>[0-9:.,]+)\s+(?P<calculated>[0-9.,]+)\s*(?P<asterisk>\*)?$"
)
RUBRIC_CODE_SUFFIX_RE = re.compile(r"^(?P<name>.+?)\s*(?P<code>\d{1,5})$")
RUBRIC_CODE_PREFIX_RE = re.compile(r"^(?P<code>\d{1,5})\s+(?P<name>.+)$")
TOTAL_RE = re.compile(r"^(?P<value>[0-9.,]+)Total:$", flags=re.IGNORECASE)
NET_TOTAL_RE = re.compile(r"^(?P<value>[0-9.,]+)L(?:iquido|íquido|\?quido) Geral:$", flags=re.IGNORECASE)
BLOCK_SALARY_RE = re.compile(
    r"^Comp\s+(?P<competence>\d{2}/\d{4})\s+-\s+Altera(?:cao|ção|\?\?o) salarial\s+(?P<event_date>\d{2}/\d{2}/\d{4})$",
    flags=re.IGNORECASE,
)
BLOCK_PAYMENT_RE = re.compile(
    r"^Comp\s+(?P<competence>\d{2}/\d{4})\s+-\s+Data pagto\s+(?P<payment_date>\d{2}/\d{2}/\d{4})\s+-\s+Lan(?:camento|çamento|\?amento)$",
    flags=re.IGNORECASE,
)
BLOCK_COMPLEMENTARY_RE = re.compile(
    r"^Comp\s+(?P<competence>\d{2}/\d{4})\s+-\s+Data complemento\s+(?P<event_date>\d{2}/\d{2}/\d{4})\s+-\s+(?P<description>.+)$",
    flags=re.IGNORECASE,
)
FILE_COMPETENCE_RE = re.compile(r"(?P<month>0[1-9]|1[0-2])[-_/](?P<year>\d{4})")


class DominioPayrollParserError(RuntimeError):
    pass


class DominioPayrollFileNotFoundError(DominioPayrollParserError, FileNotFoundError):
    pass


class DominioPayrollInvalidPdfError(DominioPayrollParserError, ValueError):
    pass


class DominioPayrollEncryptedPdfError(DominioPayrollParserError):
    pass


class DominioPayrollPdfReadError(DominioPayrollParserError):
    pass


class DominioPayrollTextLayerMissingError(DominioPayrollParserError):
    pass


class DominioPayrollNoCompanyBlocksFoundError(DominioPayrollParserError):
    pass


@dataclass(slots=True)
class _PageHeader:
    physical_page_number: int
    declared_page_number: int | None
    declared_page_count: int | None
    dominio_company_code: str | None
    company_name: str | None
    company_cnpj: DominioNormalizedCnpj
    source_payroll_competence: str | None
    assessment_competence: str | None
    calculation_type: str | None
    is_complete: bool
    warnings: list[DominioPayrollWarning]


@dataclass(slots=True)
class _ParsedPage:
    header: _PageHeader
    lines: list[str]
    raw_text: str


@dataclass(slots=True)
class _CompanyGroup:
    key: str
    pages: list[_ParsedPage] = field(default_factory=list)


@dataclass(slots=True)
class _SectionBuilder:
    section_type: DominioPayrollSectionType
    rubrics: list[DominioPayrollRubric] = field(default_factory=list)
    declared_total: Decimal | None = None
    warnings: list[DominioPayrollWarning] = field(default_factory=list)


@dataclass(slots=True)
class _BlockBuilder:
    block_type: DominioPayrollBlockType
    description: str
    source_competence: str | None
    event_date: str | None
    payment_date: str | None
    sections: list[DominioPayrollSection] = field(default_factory=list)
    rubrics: list[DominioPayrollRubric] = field(default_factory=list)
    declared_totals: dict[str, Decimal] = field(default_factory=dict)
    warnings: list[DominioPayrollWarning] = field(default_factory=list)


def parse_dominio_payroll_pdf(path: Path) -> DominioPayrollReport:
    pdf_path = Path(path)
    if not pdf_path.exists():
        raise DominioPayrollFileNotFoundError(f"Payroll PDF not found: {pdf_path}")
    if not pdf_path.is_file():
        raise DominioPayrollFileNotFoundError(f"Payroll PDF path is not a file: {pdf_path}")

    try:
        with pdf_path.open("rb") as handle:
            signature = handle.read(len(PDF_SIGNATURE))
        if signature != PDF_SIGNATURE:
            raise DominioPayrollInvalidPdfError("Payroll file is missing the PDF signature.")
        reader = PdfReader(str(pdf_path))
    except DominioPayrollParserError:
        raise
    except Exception as exc:
        raise DominioPayrollPdfReadError("Unable to read payroll PDF.") from exc

    if reader.is_encrypted:
        raise DominioPayrollEncryptedPdfError("Payroll PDF is encrypted.")
    if len(reader.pages) == 0:
        raise DominioPayrollInvalidPdfError("Payroll PDF does not contain any page.")

    extracted_pages: list[str] = []
    has_text = False
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise DominioPayrollPdfReadError("Unable to extract text from payroll PDF page.") from exc
        if text.strip():
            has_text = True
        extracted_pages.append(text)

    if not has_text:
        raise DominioPayrollTextLayerMissingError("Payroll PDF does not contain an extractable text layer.")

    return parse_dominio_payroll_pages(extracted_pages, source_file_name=pdf_path.name)


def parse_dominio_payroll_pages(
    pages: Sequence[str],
    *,
    source_file_name: str = "<memory>",
) -> DominioPayrollReport:
    if len(pages) == 0:
        raise DominioPayrollInvalidPdfError("Payroll PDF does not contain any page.")
    if not any(normalize_dominio_text(page) for page in pages):
        raise DominioPayrollTextLayerMissingError("Payroll PDF does not contain an extractable text layer.")

    parsed_pages = [_parse_page(text, physical_page_number=index + 1) for index, text in enumerate(pages)]
    global_warnings = [warning for page in parsed_pages for warning in page.header.warnings]
    groups = _group_pages(parsed_pages, global_warnings)
    if not groups:
        raise DominioPayrollNoCompanyBlocksFoundError("Payroll PDF does not contain any recognizable company block.")

    companies = tuple(_parse_company_group(group) for group in groups)

    detected_source_competences = tuple(
        sorted({company.source_payroll_competence for company in companies if company.source_payroll_competence is not None})
    )
    detected_assessment_competences = tuple(
        sorted({company.assessment_competence for company in companies if company.assessment_competence is not None})
    )

    if len(detected_source_competences) > 1:
        global_warnings.append(
            DominioPayrollWarning(
                code=DominioPayrollWarningCode.MULTIPLE_COMPETENCES_IN_FILE,
                message="The payroll file contains more than one source payroll competence.",
                context={"competences": detected_source_competences},
            )
        )

    file_name_competence = _extract_competence_from_file_name(source_file_name)
    if file_name_competence is not None and len(detected_source_competences) == 1:
        declared_competence = detected_source_competences[0]
        if file_name_competence != declared_competence:
            global_warnings.append(
                DominioPayrollWarning(
                    code=DominioPayrollWarningCode.FILE_NAME_COMPETENCE_MISMATCH,
                    message="The source file name competence does not match the PDF content competence.",
                    context={"file_name_competence": file_name_competence, "pdf_competence": declared_competence},
                )
            )

    return DominioPayrollReport(
        source_file_name=source_file_name,
        source=DominioDocumentContract.DOMINIO_FOLHA_RESUMO,
        evidence_source=DominioEvidenceSource.DOMINIO_FOLHA_PDF,
        parser_version=DOMINIO_PAYROLL_PARSER_VERSION,
        physical_page_count=len(pages),
        detected_source_competences=detected_source_competences,
        detected_assessment_competences=detected_assessment_competences,
        companies=companies,
        warnings=tuple(global_warnings),
    )


def summarize_report_for_validation(report: DominioPayrollReport) -> dict[str, Any]:
    warning_codes = Counter(warning.code.value for warning in report.warnings)
    company_warning_codes = Counter(
        warning.code.value
        for company in report.companies
        for warning in company.warnings
    )
    signal_counts = {
        "payroll": sum(company.has_payroll for company in report.companies),
        "employee": sum(company.has_employee for company in report.companies),
        "pro_labore": sum(company.has_pro_labore for company in report.companies),
        "autonomous": sum(company.has_autonomous for company in report.companies),
        "inss": sum(company.has_inss for company in report.companies),
        "fgts": sum(company.has_fgts for company in report.companies),
        "termination": sum(company.has_termination for company in report.companies),
        "vacation": sum(company.has_vacation for company in report.companies),
        "leave": sum(company.has_leave for company in report.companies),
    }
    return {
        "file": report.source_file_name,
        "physical_page_count": report.physical_page_count,
        "companies": len(report.companies),
        "source_competences": list(report.detected_source_competences),
        "assessment_competences": list(report.detected_assessment_competences),
        "warning_codes": dict(sorted(warning_codes.items())),
        "company_warning_codes": dict(sorted(company_warning_codes.items())),
        "signals": signal_counts,
    }


def timed_parse_dominio_payroll_pdf(path: Path) -> tuple[DominioPayrollReport, float]:
    started = perf_counter()
    report = parse_dominio_payroll_pdf(path)
    return report, perf_counter() - started


def _parse_page(text: str, *, physical_page_number: int) -> _ParsedPage:
    normalized_text = text or ""
    lines = [normalize_dominio_text(line) for line in normalized_text.splitlines()]
    lines = [line for line in lines if line]

    warnings: list[DominioPayrollWarning] = []
    page_label_match = PAGE_LABEL_RE.search(normalized_text)
    company_line = next((line for line in lines if line.startswith("Empresa:")), None)
    cnpj_line = next((line for line in lines if line.startswith("CNPJ:")), None)
    calculation_line = next((line for line in lines if line.startswith("Cálculo:") or line.startswith("Calculo:")), None)
    competence_line = next((line for line in lines if line.startswith("Competência:") or line.startswith("Competencia:")), None)

    declared_page_number = int(page_label_match.group("current")) if page_label_match is not None else None
    declared_page_count = int(page_label_match.group("total")) if page_label_match is not None else None

    if page_label_match is None:
        warnings.append(
            DominioPayrollWarning(
                code=DominioPayrollWarningCode.PAGE_HEADER_MISSING,
                message="Payroll page header is missing the declared page marker.",
                physical_page_number=physical_page_number,
            )
        )

    dominio_company_code: str | None = None
    company_name: str | None = None
    if company_line is not None:
        company_match = COMPANY_LINE_RE.fullmatch(company_line)
        if company_match is not None:
            company_payload = company_match.group("company")
            code_match = COMPANY_CODE_RE.fullmatch(company_payload)
            if code_match is not None:
                dominio_company_code = code_match.group("code")
                company_name = code_match.group("name").strip()

    cnpj = normalize_cnpj_for_dominio(cnpj_line or "")
    if cnpj_line is not None:
        cnpj_match = CNPJ_LINE_RE.search(cnpj_line)
        if cnpj_match is not None:
            cnpj = normalize_cnpj_for_dominio(cnpj_match.group("cnpj"))

    source_payroll_competence: str | None = None
    assessment_competence: str | None = None
    if competence_line is not None:
        competence_match = COMPETENCE_RE.search(competence_line)
        if competence_match is not None:
            try:
                mapping = map_payroll_to_assessment_competence(competence_match.group("value"))
            except ValueError:
                warnings.append(
                    DominioPayrollWarning(
                        code=DominioPayrollWarningCode.INVALID_COMPETENCE,
                        message="Payroll page header contains an invalid competence value.",
                        physical_page_number=physical_page_number,
                        line=competence_line,
                    )
                )
            else:
                source_payroll_competence = mapping.source_payroll_competence
                assessment_competence = mapping.target_assessment_competence

    calculation_type: str | None = None
    if calculation_line is not None:
        calculation_match = CALCULATION_RE.search(calculation_line)
        if calculation_match is not None:
            calculation_type = calculation_match.group("value").strip()

    is_complete = (
        dominio_company_code is not None
        and company_name is not None
        and source_payroll_competence is not None
    )
    if not is_complete:
        warnings.append(
            DominioPayrollWarning(
                code=DominioPayrollWarningCode.COMPANY_HEADER_INCOMPLETE,
                message="Payroll page header is missing one or more required company fields.",
                physical_page_number=physical_page_number,
                line=company_line,
            )
        )

    body_lines = [line for line in lines if not HEADER_FILTER_RE.match(line)]
    return _ParsedPage(
        header=_PageHeader(
            physical_page_number=physical_page_number,
            declared_page_number=declared_page_number,
            declared_page_count=declared_page_count,
            dominio_company_code=dominio_company_code,
            company_name=company_name,
            company_cnpj=cnpj,
            source_payroll_competence=source_payroll_competence,
            assessment_competence=assessment_competence,
            calculation_type=calculation_type,
            is_complete=is_complete,
            warnings=warnings,
        ),
        lines=body_lines,
        raw_text="\n".join(body_lines),
    )


def _group_pages(
    pages: Sequence[_ParsedPage],
    global_warnings: list[DominioPayrollWarning],
) -> list[_CompanyGroup]:
    groups: list[_CompanyGroup] = []
    current_group: _CompanyGroup | None = None

    for page in pages:
        header = page.header
        if header.is_complete:
            current_key = _build_company_group_key(
                dominio_company_code=header.dominio_company_code or "missing-code",
                company_cnpj=header.company_cnpj.normalized or header.company_cnpj.raw or "missing-cnpj",
                source_payroll_competence=header.source_payroll_competence or "missing-competence",
            )
            if current_group is None or current_group.key != current_key:
                current_group = _CompanyGroup(key=current_key)
                groups.append(current_group)
            current_group.pages.append(page)
            continue

        if current_group is not None:
            current_group.pages.append(page)
        else:
            global_warnings.append(
                DominioPayrollWarning(
                    code=DominioPayrollWarningCode.PAGE_HEADER_MISSING,
                    message="A page without a recognizable company header could not be attached to any company block.",
                    physical_page_number=header.physical_page_number,
                )
            )

    return groups


def _parse_company_group(group: _CompanyGroup) -> DominioPayrollCompany:
    first_header = next(page.header for page in group.pages if page.header.dominio_company_code is not None)
    warnings: list[DominioPayrollWarning] = []
    block_builders: list[_BlockBuilder] = []
    current_block: _BlockBuilder | None = None
    current_section: _SectionBuilder | None = None
    line_order = 0
    raw_fragments: list[str] = []
    net_total: Decimal | None = None
    signal_sources: dict[str, set[str]] = {
        "has_payroll": set(),
        "has_employee": set(),
        "has_pro_labore": set(),
        "has_autonomous": set(),
        "has_inss": set(),
        "has_fgts": set(),
        "has_termination": set(),
        "has_vacation": set(),
        "has_leave": set(),
    }
    all_rubrics: list[DominioPayrollRubric] = []

    for page in group.pages:
        if not page.lines:
            warnings.append(
                DominioPayrollWarning(
                    code=DominioPayrollWarningCode.CONTINUATION_PAGE_EMPTY,
                    message="A continuation payroll page does not contain any useful body line.",
                    physical_page_number=page.header.physical_page_number,
                    company_key=group.key,
                )
            )
            continue

        raw_fragments.extend(page.lines)

        for line in page.lines:
            block_type, description, block_source_competence, event_date, payment_date = _parse_block_heading(line)
            if description is not None:
                assert block_type is not None
                current_section = _finalize_section(current_section, current_block, warnings)
                current_block = _start_block(
                    current_block=current_block,
                    block_builders=block_builders,
                    block_type=block_type,
                    description=description,
                    source_competence=block_source_competence,
                    event_date=event_date,
                    payment_date=payment_date,
                    warnings=warnings,
                    company_key=group.key,
                    physical_page_number=page.header.physical_page_number,
                    line=line,
                )
                continue

            section_type = _parse_section_heading(line)
            if section_type is not None:
                if current_block is None:
                    current_block = _start_implicit_unknown_block(block_builders)
                current_section = _finalize_section(current_section, current_block, warnings)
                current_section = _SectionBuilder(section_type=section_type)
                continue

            total_match = TOTAL_RE.fullmatch(line)
            if total_match is not None:
                try:
                    total_value = parse_brazilian_decimal(total_match.group("value"))
                except ValueError:
                    total_value = None
                if current_section is None:
                    warnings.append(
                        DominioPayrollWarning(
                            code=DominioPayrollWarningCode.SECTION_TOTAL_WITHOUT_SECTION,
                            message="A declared section total was found without an active section.",
                            physical_page_number=page.header.physical_page_number,
                            company_key=group.key,
                            line=line,
                        )
                    )
                else:
                    current_section.declared_total = total_value
                continue

            net_total_match = NET_TOTAL_RE.fullmatch(line)
            if net_total_match is not None:
                try:
                    net_total = parse_brazilian_decimal(net_total_match.group("value"))
                except ValueError:
                    warnings.append(
                        DominioPayrollWarning(
                            code=DominioPayrollWarningCode.CALCULATED_VALUE_UNPARSED,
                            message="The company net total line could not be parsed as a Brazilian decimal value.",
                            physical_page_number=page.header.physical_page_number,
                            company_key=group.key,
                            line=line,
                        )
                    )
                continue

            rubric = _parse_rubric_line(
                line,
                company_key=group.key,
                block_type=current_block.block_type if current_block is not None else DominioPayrollBlockType.UNKNOWN,
                section_type=current_section.section_type if current_section is not None else None,
                physical_page_number=page.header.physical_page_number,
                line_order=line_order + 1,
            )
            if rubric is None:
                if line.startswith("Comp "):
                    warnings.append(
                        DominioPayrollWarning(
                            code=DominioPayrollWarningCode.UNKNOWN_BLOCK_HEADING,
                            message="The parser found an unknown payroll block heading and preserved it as an unknown block.",
                            physical_page_number=page.header.physical_page_number,
                            company_key=group.key,
                            line=line,
                        )
                    )
                    current_section = _finalize_section(current_section, current_block, warnings)
                    current_block = _start_block(
                        current_block=current_block,
                        block_builders=block_builders,
                        block_type=DominioPayrollBlockType.UNKNOWN,
                        description=line,
                        source_competence=None,
                        event_date=None,
                        payment_date=None,
                        warnings=warnings,
                        company_key=group.key,
                        physical_page_number=page.header.physical_page_number,
                        line=line,
                    )
                continue

            line_order += 1
            if current_block is None:
                current_block = _start_implicit_unknown_block(block_builders)
            if current_section is None:
                current_section = _SectionBuilder(section_type=DominioPayrollSectionType.INFORMATIONAL)
            current_block.rubrics.append(rubric)
            current_section.rubrics.append(rubric)
            all_rubrics.append(rubric)
            signal_sources["has_payroll"].add(rubric.code)
            rubric_signals = classify_rubric_signals(rubric.code, rubric.original_name)
            for signal in rubric_signals.signals:
                signal_sources[signal].add(rubric.code)
            warnings.extend(rubric.warnings)

    current_section = _finalize_section(current_section, current_block, warnings)
    if current_block is not None and current_block not in block_builders:
        block_builders.append(current_block)

    blocks = tuple(
        DominioPayrollBlock(
            block_type=builder.block_type,
            description=builder.description,
            source_competence=builder.source_competence,
            event_date=builder.event_date,
            payment_date=builder.payment_date,
            sections=tuple(builder.sections),
            rubrics=tuple(builder.rubrics),
            declared_totals=dict(builder.declared_totals),
            warnings=tuple(builder.warnings),
        )
        for builder in block_builders
    )

    if net_total is None:
        warnings.append(
            DominioPayrollWarning(
                code=DominioPayrollWarningCode.NET_TOTAL_MISSING,
                message="The company block does not contain any declared net total line.",
                company_key=group.key,
            )
        )

    company_cnpj = first_header.company_cnpj
    if company_cnpj.status == DominioCnpjStatus.MISSING:
        warnings.append(
            DominioPayrollWarning(
                code=DominioPayrollWarningCode.MISSING_CNPJ,
                message="The company header does not contain any CNPJ.",
                company_key=group.key,
            )
        )
    elif company_cnpj.status == DominioCnpjStatus.INVALID:
        warnings.append(
            DominioPayrollWarning(
                code=DominioPayrollWarningCode.INVALID_CNPJ,
                message="The company header contains an invalid CNPJ.",
                company_key=group.key,
                context={
                    "digit_length_valid": company_cnpj.is_digit_length_valid,
                    "check_digits_valid": company_cnpj.is_check_digits_valid,
                },
            )
        )

    declared_page_numbers = tuple(
        page.header.declared_page_number
        for page in group.pages
        if page.header.declared_page_number is not None
    )
    declared_page_count = first_header.declared_page_count
    if (
        declared_page_numbers
        and tuple(range(1, len(declared_page_numbers) + 1)) != declared_page_numbers
    ):
        warnings.append(
            DominioPayrollWarning(
                code=DominioPayrollWarningCode.DECLARED_PAGE_SEQUENCE_MISMATCH,
                message="Declared payroll page numbers do not follow a contiguous sequence.",
                company_key=group.key,
                context={"declared_pages": declared_page_numbers},
            )
        )
    if declared_page_count is not None and declared_page_numbers and declared_page_numbers[-1] != declared_page_count:
        warnings.append(
            DominioPayrollWarning(
                code=DominioPayrollWarningCode.DECLARED_PAGE_SEQUENCE_MISMATCH,
                message="Declared payroll page count does not match the last observed declared page number.",
                company_key=group.key,
                context={"declared_pages": declared_page_numbers, "declared_page_count": declared_page_count},
            )
        )

    gross_total = _sum_company_section_totals(blocks, DominioPayrollSectionType.EARNINGS)
    discount_total = _sum_company_section_totals(blocks, DominioPayrollSectionType.DEDUCTIONS)
    informative_total = _sum_company_section_totals(blocks, DominioPayrollSectionType.INFORMATIONAL)

    confidence = _compute_company_confidence(
        cnpj_status=company_cnpj.status,
        has_blocks=bool(blocks),
        has_net_total=net_total is not None,
        warnings=warnings,
    )

    return DominioPayrollCompany(
        dominio_company_code=first_header.dominio_company_code or "missing-code",
        company_cnpj=company_cnpj.normalized if company_cnpj.status != DominioCnpjStatus.MISSING else None,
        company_cnpj_raw=company_cnpj.raw,
        company_cnpj_status=company_cnpj.status,
        company_name=first_header.company_name or "missing-company-name",
        source_payroll_competence=first_header.source_payroll_competence,
        assessment_competence=first_header.assessment_competence,
        calculation_type=first_header.calculation_type,
        physical_page_numbers=tuple(page.header.physical_page_number for page in group.pages),
        declared_page_numbers=declared_page_numbers,
        declared_page_count=declared_page_count,
        blocks=blocks,
        rubrics=tuple(all_rubrics),
        has_payroll=bool(signal_sources["has_payroll"] or gross_total or discount_total or informative_total),
        has_employee=bool(signal_sources["has_employee"]),
        has_pro_labore=bool(signal_sources["has_pro_labore"]),
        has_autonomous=bool(signal_sources["has_autonomous"]),
        has_inss=bool(signal_sources["has_inss"]),
        has_fgts=bool(signal_sources["has_fgts"]),
        has_termination=bool(signal_sources["has_termination"]),
        has_vacation=bool(signal_sources["has_vacation"]),
        has_leave=bool(signal_sources["has_leave"]),
        gross_total=gross_total,
        discount_total=discount_total,
        informative_total=informative_total,
        net_total=net_total,
        raw_text="\n".join(raw_fragments),
        confidence=confidence,
        warnings=tuple(warnings),
        signal_sources=tuple(
            DominioPayrollSignalEvidence(
                signal=signal,
                value=bool(rubric_codes),
                rubric_codes=tuple(sorted(rubric_codes)),
            )
            for signal, rubric_codes in signal_sources.items()
        ),
    )


def _parse_block_heading(line: str) -> tuple[DominioPayrollBlockType | None, str | None, str | None, str | None, str | None]:
    if line == "Folha Mensal":
        return DominioPayrollBlockType.MONTHLY_PAYROLL, line, None, None, None

    salary_match = BLOCK_SALARY_RE.fullmatch(line)
    if salary_match is not None:
        return (
            DominioPayrollBlockType.SALARY_ADJUSTMENT,
            line,
            parse_competence_header_to_iso(salary_match.group("competence")),
            parse_brazilian_date_to_iso(salary_match.group("event_date")),
            None,
        )

    payment_match = BLOCK_PAYMENT_RE.fullmatch(line)
    if payment_match is not None:
        return (
            DominioPayrollBlockType.PAYMENT_ENTRY,
            line,
            parse_competence_header_to_iso(payment_match.group("competence")),
            None,
            parse_brazilian_date_to_iso(payment_match.group("payment_date")),
        )

    complementary_match = BLOCK_COMPLEMENTARY_RE.fullmatch(line)
    if complementary_match is not None:
        return (
            DominioPayrollBlockType.COMPLEMENTARY,
            line,
            parse_competence_header_to_iso(complementary_match.group("competence")),
            parse_brazilian_date_to_iso(complementary_match.group("event_date")),
            None,
        )

    return None, None, None, None, None


def _parse_section_heading(line: str) -> DominioPayrollSectionType | None:
    if line == "PROVENTOS":
        return DominioPayrollSectionType.EARNINGS
    if line == "DESCONTOS":
        return DominioPayrollSectionType.DEDUCTIONS
    if line == "INFORMATIVA":
        return DominioPayrollSectionType.INFORMATIONAL
    return None


def _parse_rubric_line(
    line: str,
    *,
    company_key: str,
    block_type: DominioPayrollBlockType,
    section_type: DominioPayrollSectionType | None,
    physical_page_number: int,
    line_order: int,
) -> DominioPayrollRubric | None:
    if section_type is None:
        return None

    match = RUBRIC_RE.fullmatch(line)
    if match is None:
        return None

    prefix = match.group("prefix").strip()
    code: str | None = None
    original_name: str | None = None

    suffix_match = RUBRIC_CODE_SUFFIX_RE.fullmatch(prefix)
    if suffix_match is not None:
        code = suffix_match.group("code")
        original_name = suffix_match.group("name").strip()
    else:
        prefix_match = RUBRIC_CODE_PREFIX_RE.fullmatch(prefix)
        if prefix_match is not None:
            code = prefix_match.group("code")
            original_name = prefix_match.group("name").strip()

    if code is None or original_name is None:
        return DominioPayrollRubric(
            code="",
            original_name=prefix,
            normalized_name="",
            contributors_count=int(match.group("count")),
            informed_value_raw=match.group("informed"),
            informed_value_kind=DominioInformedValueKind.UNKNOWN,
            informed_value_decimal=None,
            informed_value_minutes=None,
            calculated_value=None,
            marked_with_asterisk=bool(match.group("asterisk")),
            section=section_type,
            block_type=block_type,
            physical_page_number=physical_page_number,
            line_order=line_order,
            warnings=(
                DominioPayrollWarning(
                    code=DominioPayrollWarningCode.RUBRIC_LINE_UNPARSED,
                    message="The payroll rubric line could not be split into code and name deterministically.",
                    physical_page_number=physical_page_number,
                    company_key=company_key,
                    line=line,
                ),
            ),
        )

    parsed_informed = parse_informed_value(match.group("informed"))
    rubric_warnings: list[DominioPayrollWarning] = []
    if parsed_informed.kind == DominioInformedValueKind.UNKNOWN:
        rubric_warnings.append(
            DominioPayrollWarning(
                code=DominioPayrollWarningCode.INFORMED_VALUE_UNPARSED,
                message="The payroll rubric informed value could not be classified as hours or decimal.",
                physical_page_number=physical_page_number,
                company_key=company_key,
                line=line,
            )
        )

    try:
        calculated_value = parse_brazilian_decimal(match.group("calculated"))
    except ValueError:
        calculated_value = None
        rubric_warnings.append(
            DominioPayrollWarning(
                code=DominioPayrollWarningCode.CALCULATED_VALUE_UNPARSED,
                message="The payroll rubric calculated value could not be parsed as a Brazilian decimal.",
                physical_page_number=physical_page_number,
                company_key=company_key,
                line=line,
            )
        )

    normalized_name = classify_rubric_signals(code, original_name).normalized_name
    return DominioPayrollRubric(
        code=code,
        original_name=original_name,
        normalized_name=normalized_name,
        contributors_count=int(match.group("count")),
        informed_value_raw=parsed_informed.raw,
        informed_value_kind=parsed_informed.kind,
        informed_value_decimal=parsed_informed.decimal_value,
        informed_value_minutes=parsed_informed.minutes_value,
        calculated_value=calculated_value,
        marked_with_asterisk=bool(match.group("asterisk")),
        section=section_type,
        block_type=block_type,
        physical_page_number=physical_page_number,
        line_order=line_order,
        warnings=tuple(rubric_warnings),
    )


def _start_block(
    *,
    current_block: _BlockBuilder | None,
    block_builders: list[_BlockBuilder],
    block_type: DominioPayrollBlockType,
    description: str,
    source_competence: str | None,
    event_date: str | None,
    payment_date: str | None,
    warnings: list[DominioPayrollWarning],
    company_key: str,
    physical_page_number: int,
    line: str,
) -> _BlockBuilder:
    if current_block is not None and current_block not in block_builders:
        block_builders.append(current_block)
    if block_type == DominioPayrollBlockType.UNKNOWN:
        warning = DominioPayrollWarning(
            code=DominioPayrollWarningCode.UNKNOWN_BLOCK_HEADING,
            message="The parser found an unknown payroll block heading and preserved it as UNKNOWN.",
            physical_page_number=physical_page_number,
            company_key=company_key,
            line=line,
        )
        warnings.append(warning)
        builder = _BlockBuilder(
            block_type=block_type,
            description=description,
            source_competence=source_competence,
            event_date=event_date,
            payment_date=payment_date,
            warnings=[warning],
        )
        return builder
    return _BlockBuilder(
        block_type=block_type,
        description=description,
        source_competence=source_competence,
        event_date=event_date,
        payment_date=payment_date,
    )


def _start_implicit_unknown_block(block_builders: list[_BlockBuilder]) -> _BlockBuilder:
    builder = _BlockBuilder(
        block_type=DominioPayrollBlockType.UNKNOWN,
        description="Implicit block",
        source_competence=None,
        event_date=None,
        payment_date=None,
    )
    if builder not in block_builders:
        block_builders.append(builder)
    return builder


def _finalize_section(
    current_section: _SectionBuilder | None,
    current_block: _BlockBuilder | None,
    warnings: list[DominioPayrollWarning],
) -> _SectionBuilder | None:
    if current_section is None or current_block is None:
        return None

    calculated_total = _calculate_section_total(current_section)
    if current_section.declared_total is not None:
        current_block.declared_totals[current_section.section_type.value] = current_section.declared_total
        if current_section.declared_total != calculated_total:
            mismatch_warning = DominioPayrollWarning(
                code=DominioPayrollWarningCode.SECTION_TOTAL_MISMATCH,
                message="Declared payroll section total does not match the calculated rubric sum.",
                context={
                    "section_type": current_section.section_type.value,
                    "declared_total": format(current_section.declared_total, "f"),
                    "calculated_total": format(calculated_total, "f"),
                },
            )
            current_section.warnings.append(mismatch_warning)
            current_block.warnings.append(mismatch_warning)
            warnings.append(mismatch_warning)

    current_block.sections.append(
        DominioPayrollSection(
            section_type=current_section.section_type,
            physical_page_numbers=tuple(sorted({rubric.physical_page_number for rubric in current_section.rubrics})),
            line_orders=tuple(rubric.line_order for rubric in current_section.rubrics),
            declared_total=current_section.declared_total,
            calculated_total=calculated_total,
            rubric_codes=tuple(rubric.code for rubric in current_section.rubrics if rubric.code),
            warnings=tuple(current_section.warnings),
        )
    )
    return None


def _calculate_section_total(section: _SectionBuilder) -> Decimal:
    total = Decimal("0.00")
    for rubric in section.rubrics:
        if rubric.calculated_value is None:
            continue
        if section.section_type != DominioPayrollSectionType.INFORMATIONAL and rubric.marked_with_asterisk:
            continue
        total += rubric.calculated_value
    return total.quantize(Decimal("0.01"))


def _sum_company_section_totals(
    blocks: Sequence[DominioPayrollBlock],
    section_type: DominioPayrollSectionType,
) -> Decimal | None:
    values = [section.declared_total for block in blocks for section in block.sections if section.section_type == section_type and section.declared_total is not None]
    if not values:
        return None
    return sum(values, Decimal("0.00")).quantize(Decimal("0.01"))


def _compute_company_confidence(
    *,
    cnpj_status: DominioCnpjStatus,
    has_blocks: bool,
    has_net_total: bool,
    warnings: Sequence[DominioPayrollWarning],
) -> DominioParserConfidence:
    if cnpj_status == DominioCnpjStatus.INVALID or not has_blocks or not has_net_total:
        return DominioParserConfidence.LOW

    low_codes = {
        DominioPayrollWarningCode.DECLARED_PAGE_SEQUENCE_MISMATCH,
        DominioPayrollWarningCode.PAGE_HEADER_MISSING,
        DominioPayrollWarningCode.COMPANY_HEADER_INCOMPLETE,
    }
    if any(warning.code in low_codes for warning in warnings):
        return DominioParserConfidence.LOW
    if warnings:
        return DominioParserConfidence.MEDIUM
    return DominioParserConfidence.HIGH


def _extract_competence_from_file_name(source_file_name: str) -> str | None:
    match = FILE_COMPETENCE_RE.search(source_file_name)
    if match is None:
        return None
    month = int(match.group("month"))
    year = int(match.group("year"))
    return f"{year:04d}-{month:02d}"


def _build_company_group_key(
    *,
    dominio_company_code: str,
    company_cnpj: str,
    source_payroll_competence: str,
) -> str:
    return f"{dominio_company_code}|{company_cnpj}|{source_payroll_competence}"
