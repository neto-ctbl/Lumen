"""Content-first parser for the structured MIT JSON document."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import Enum
import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent.parsers.contracts import (
    DocumentContext,
    DocumentSignal,
    ExtractionStatus,
    ParserExtraction,
    SignalProvenance,
    TechnicalFormat,
)
from agent.parsers.guide_common import digits, valid_cpf
from agent.parsers.layout_framework import (
    ClassificationResult,
    ComposableDocumentParser,
    LayoutExtractionFailure,
)
from agent.parsers.mit_revenue_codes import (
    lookup_mit_revenue_code,
    normalize_mit_revenue_code,
)
from agent.parsers.runtime import DocumentParserRuntime, ParserRegistry

MIT_JSON_LAYOUT_ID = "DOMINIO_MIT_JSON"
MIT_JSON_PARSER_NAME = "lumen.mit-json"
MIT_JSON_PARSER_VERSION = "1"

_INITIAL_SIGNATURE_KEYS = frozenset(
    {"QualificacaoPj", "TributacaoLucro", "RegimePisCofins", "ResponsavelApuracao"}
)
_KNOWN_INITIAL_KEYS = _INITIAL_SIGNATURE_KEYS | {"SemMovimento", "VariacoesMonetarias"}
_KNOWN_TOP_LEVEL_KEYS = frozenset(
    {
        "PeriodoApuracao",
        "ListaEventosEspeciais",
        "DadosIniciais",
        "Debitos",
        "ListaSuspensoes",
    }
)
_TAX_BY_GROUP = {
    "Irpj": "IRPJ",
    "Csll": "CSLL",
    "Irrf": "IRRF",
    "Ipi": "IPI",
    "Iof": "IOF",
    "PisPasep": "PIS",
    "Cofins": "COFINS",
    "ContribuicoesDiversas": "CONTRIBUICOES_DIVERSAS",
    "Cpss": "CPSS",
    "RetPagamentoUnificado": "RET_PAGAMENTO_UNIFICADO",
}
_KNOWN_DEBIT_KEYS = frozenset(
    {
        "IdDebito",
        "IdEventoDebito",
        "CodigoDebito",
        "DescricaoDebito",
        "AnoPostergado",
        "TrimPostergado",
        "AnoDebito",
        "PaDebito",
        "CnpjScp",
        "CnpjEstabelecimento",
        "CodigoMunicipioOuro",
        "CnpjIncorporacao",
        "ValorDebito",
    }
)
_KNOWN_DEBIT_LISTS = ("ListaDebitos", "ListaDebitosAposEvento")


class MitModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MitPeriodKind(str, Enum):
    MONTH = "MONTH"
    QUARTER = "QUARTER"
    YEAR = "YEAR"


class MitDebitListKind(str, Enum):
    STANDARD = "STANDARD"
    AFTER_EVENT = "AFTER_EVENT"


class MitAssessmentPeriod(MitModel):
    kind: MitPeriodKind
    year: int = Field(ge=1900, le=9999)
    month: int | None = Field(default=None, ge=1, le=12)
    quarter: int | None = Field(default=None, ge=1, le=4)
    period: str


class MitPhone(MitModel):
    area_code: str | None = None
    number: str | None = None


class MitCrcRegistration(MitModel):
    state: str | None = None
    number: str | None = None


class MitAssessmentResponsible(MitModel):
    cpf: str | None = None
    cpf_structure_valid: bool | None = None
    phone: MitPhone | None = None
    email: str | None = None
    crc_registration: MitCrcRegistration | None = None
    unknown_fields: tuple[str, ...] = ()


class MitInitialData(MitModel):
    no_activity: bool | None = None
    legal_entity_qualification: int | None = None
    profit_taxation: int | None = None
    monetary_variations: int | None = None
    pis_cofins_regime: int | None = None
    assessment_responsible: MitAssessmentResponsible | None = None
    unknown_fields: tuple[str, ...] = ()


class MitSpecialEvent(MitModel):
    event_id: int | None = None
    day: int | None = None
    event_type: int | None = None
    unknown_fields: tuple[str, ...] = ()


class MitDebitIdentifiers(MitModel):
    debit_id: str | None = None
    event_id: str | None = None
    scp_taxpayer_id: str | None = None
    establishment_taxpayer_id: str | None = None
    gold_municipality_code: str | None = None
    incorporation_taxpayer_id: str | None = None


class MitDebit(MitModel):
    tax: str
    raw_group: str
    list_kind: MitDebitListKind
    revenue_code: str | None = None
    normalized_revenue_code: str | None = None
    revenue_code_catalog_known: bool | None = None
    revenue_code_periodicity: str | None = None
    description: str | None = None
    assessment_period: MitAssessmentPeriod | None = None
    pa_debit: int | None = None
    postponed_year: int | None = None
    postponed_quarter: int | None = None
    debit_year: int | None = None
    principal: Decimal | None = None
    identifiers: MitDebitIdentifiers
    unknown_fields: tuple[str, ...] = ()


class MitSuspendedDebit(MitModel):
    debit_id: str | None = None
    suspended_amount: Decimal | None = None
    unknown_fields: tuple[str, ...] = ()


class MitSuspension(MitModel):
    suspension_type: int | None = None
    reason: int | None = None
    with_deposit: bool | None = None
    process_number: str | None = None
    third_party_process: bool | None = None
    decision_date: int | None = None
    judicial_court: int | None = None
    judicial_municipality_code: str | None = None
    suspended_debits: tuple[MitSuspendedDebit, ...] = ()
    unknown_fields: tuple[str, ...] = ()


class MitValidation(MitModel):
    debit_count: int = Field(ge=0)
    known_debit_groups_count: int = Field(ge=0)
    unknown_debit_groups_count: int = Field(ge=0)
    has_assessment_period: bool


class MitDocument(MitModel):
    layout_id: str = MIT_JSON_LAYOUT_ID
    initial_data: MitInitialData
    assessment_period: MitAssessmentPeriod | None = None
    special_events: tuple[MitSpecialEvent, ...] = ()
    balance_reduction_or_suspension: bool | None = None
    debits: tuple[MitDebit, ...]
    suspensions: tuple[MitSuspension, ...] = ()
    validation: MitValidation
    empty_debit_sections: tuple[str, ...] = ()
    unknown_debits_fields: tuple[str, ...] = ()
    unknown_top_level_fields: tuple[str, ...] = ()
    warning_codes: tuple[str, ...] = ()


class MitJsonLayoutExtractor:
    layout_id = MIT_JSON_LAYOUT_ID

    def supports_layout(self, context: DocumentContext) -> bool:
        if context.technical_format is not TechnicalFormat.JSON:
            return False
        try:
            payload = _load_json(context.file_path)
        except (JSONDecodeError, UnicodeError, ValueError):
            return True
        return _recognizes_mit_structure(payload)

    def extract(self, context: DocumentContext) -> MitDocument:
        try:
            payload = _load_json(context.file_path)
        except (JSONDecodeError, UnicodeError, ValueError) as exc:
            raise LayoutExtractionFailure(ExtractionStatus.INVALID, "MIT_JSON_INVALID") from exc
        if not _recognizes_mit_structure(payload):
            raise LayoutExtractionFailure(ExtractionStatus.UNSUPPORTED, "UNKNOWN_JSON_LAYOUT")
        assert isinstance(payload, dict)
        initial_payload = payload["DadosIniciais"]
        debits_payload = payload.get("Debitos", {})
        if not isinstance(initial_payload, dict) or not isinstance(debits_payload, dict):
            raise LayoutExtractionFailure(
                ExtractionStatus.INCONCLUSIVE, "MIT_STRUCTURE_INCONCLUSIVE"
            )

        warnings: list[str] = []
        assessment_period = _parse_file_period(payload.get("PeriodoApuracao"))
        if assessment_period is None:
            warnings.append("MIT_ASSESSMENT_PERIOD_MISSING")
        initial_data = _parse_initial_data(initial_payload)
        special_events = _parse_special_events(payload.get("ListaEventosEspeciais"))
        suspensions = _parse_suspensions(payload.get("ListaSuspensoes"))

        balance = debits_payload.get("BalancoLucroReal")
        if "BalancoLucroReal" in debits_payload and not isinstance(balance, bool):
            raise LayoutExtractionFailure(
                ExtractionStatus.INCONCLUSIVE, "MIT_STRUCTURE_INCONCLUSIVE"
            )
        balance_reduction_or_suspension = balance if isinstance(balance, bool) else None
        debits: list[MitDebit] = []
        known_groups = 0
        unknown_groups = 0
        empty_debit_sections: list[str] = []
        unknown_debits_fields: list[str] = []

        for raw_group, group_payload in debits_payload.items():
            if raw_group == "BalancoLucroReal":
                if not isinstance(group_payload, bool):
                    unknown_debits_fields.append(raw_group)
                    warnings.append("MIT_UNKNOWN_DEBITS_FIELD")
                continue
            if not isinstance(group_payload, dict):
                if group_payload is None or isinstance(group_payload, (bool, int, str, Decimal)):
                    unknown_debits_fields.append(raw_group)
                    warnings.append("MIT_UNKNOWN_DEBITS_FIELD")
                    continue
                raise LayoutExtractionFailure(
                    ExtractionStatus.INCONCLUSIVE, "MIT_STRUCTURE_INCONCLUSIVE"
                )

            tax = _TAX_BY_GROUP.get(raw_group, "UNKNOWN")
            if tax == "UNKNOWN":
                unknown_groups += 1
                warnings.append("MIT_UNKNOWN_DEBIT_GROUP")
            else:
                known_groups += 1

            present_lists = [name for name in _KNOWN_DEBIT_LISTS if name in group_payload]
            if not present_lists:
                if group_payload:
                    raise LayoutExtractionFailure(
                        ExtractionStatus.INCONCLUSIVE, "MIT_STRUCTURE_INCONCLUSIVE"
                    )
                empty_debit_sections.append(raw_group)
                continue
            for list_name in present_lists:
                items = group_payload[list_name]
                if not isinstance(items, list):
                    raise LayoutExtractionFailure(
                        ExtractionStatus.INCONCLUSIVE, "MIT_STRUCTURE_INCONCLUSIVE"
                    )
                list_kind = (
                    MitDebitListKind.STANDARD
                    if list_name == "ListaDebitos"
                    else MitDebitListKind.AFTER_EVENT
                )
                for item in items:
                    if not isinstance(item, dict):
                        raise LayoutExtractionFailure(
                            ExtractionStatus.INCONCLUSIVE, "MIT_STRUCTURE_INCONCLUSIVE"
                        )
                    debit, debit_warnings = _parse_debit(
                        item, raw_group=raw_group, tax=tax, list_kind=list_kind
                    )
                    debits.append(debit)
                    warnings.extend(debit_warnings)

        if not debits:
            warnings.append("MIT_NO_DEBITS")
        warning_codes = tuple(dict.fromkeys(warnings))
        return MitDocument(
            initial_data=initial_data,
            assessment_period=assessment_period,
            special_events=special_events,
            balance_reduction_or_suspension=balance_reduction_or_suspension,
            debits=tuple(debits),
            suspensions=suspensions,
            validation=MitValidation(
                debit_count=len(debits),
                known_debit_groups_count=known_groups,
                unknown_debit_groups_count=unknown_groups,
                has_assessment_period=assessment_period is not None,
            ),
            empty_debit_sections=tuple(empty_debit_sections),
            unknown_debits_fields=tuple(unknown_debits_fields),
            unknown_top_level_fields=_unknown_keys(payload, _KNOWN_TOP_LEVEL_KEYS),
            warning_codes=warning_codes,
        )


class MitDocumentClassifier:
    def classify(
        self, extracted: MitDocument, context: DocumentContext
    ) -> ClassificationResult:
        warnings = list(extracted.warning_codes)
        signals: list[DocumentSignal] = [
            DocumentSignal(
                name="mit_structure_recognized",
                value=True,
                provenance=SignalProvenance.FILE_STRUCTURE,
                confidence=0.99,
            ),
            DocumentSignal(
                name="mit_debits_count",
                value=len(extracted.debits),
                provenance=SignalProvenance.CONTENT,
                confidence=0.99,
            ),
        ]
        if extracted.assessment_period is not None:
            signals.append(
                DocumentSignal(
                    name="period_from_content",
                    value=extracted.assessment_period.period,
                    provenance=SignalProvenance.CONTENT,
                    confidence=0.99,
                )
            )
            if any(
                signal.name in {"period_from_filename", "period_from_path"}
                and signal.value != extracted.assessment_period.period
                for signal in context.context_signals
            ):
                warnings.append("MIT_PERIOD_CONFLICT")
        return ClassificationResult(
            classification_id="MIT",
            classification_known=True,
            document_family="MIT",
            document_kind="MIT",
            confidence=0.99,
            signals=tuple(signals),
            warnings=tuple(dict.fromkeys(warnings)),
        )


class MitJsonParser:
    """Claim JSON routing, then apply structure -> extraction -> classification."""

    name = MIT_JSON_PARSER_NAME
    version = MIT_JSON_PARSER_VERSION
    supported_formats = frozenset({TechnicalFormat.JSON})

    def __init__(self) -> None:
        self._pipeline = ComposableDocumentParser(
            name=self.name,
            version=self.version,
            supported_formats=self.supported_formats,
            extractor=MitJsonLayoutExtractor(),
            classifier=MitDocumentClassifier(),
            serialize_extracted=lambda extracted: extracted.model_dump(mode="json"),
            unknown_layout_warning="UNKNOWN_JSON_LAYOUT",
        )

    def supports(self, document: DocumentContext) -> bool:
        return document.technical_format is TechnicalFormat.JSON

    def parse(self, document: DocumentContext) -> ParserExtraction:
        return self._pipeline.parse(document)


class SanitizedMitJsonProbe(MitModel):
    family: str
    layout_id: str
    layout_known: bool
    matched: bool
    extraction_status: ExtractionStatus
    debits_count: int = Field(ge=0)
    taxes: tuple[str, ...] = ()
    has_taxpayer_id: bool = False
    has_assessment_period: bool = False
    unknown_debit_groups_count: int = Field(default=0, ge=0)
    warning_codes: tuple[str, ...] = ()


def sanitized_mit_json_probe(file_path: str | Path) -> SanitizedMitJsonProbe:
    """Read-only, allowlisted probe. Never returns source content, identity or values."""
    result = DocumentParserRuntime(ParserRegistry((MitJsonParser(),))).run_file(file_path)
    signals = {signal.name: signal.value for signal in result.signals}
    layout_id = str(signals.get("layout_id", "UNKNOWN"))
    document: MitDocument | None = None
    if result.extraction_status is ExtractionStatus.MATCHED:
        document = MitDocument.model_validate(result.structured_data)
    return SanitizedMitJsonProbe(
        family=result.document_family,
        layout_id=layout_id,
        layout_known=layout_id == MIT_JSON_LAYOUT_ID,
        matched=result.extraction_status is ExtractionStatus.MATCHED,
        extraction_status=result.extraction_status,
        debits_count=len(document.debits) if document else 0,
        taxes=tuple(sorted({debit.tax for debit in document.debits})) if document else (),
        has_taxpayer_id=False,
        has_assessment_period=bool(document and document.assessment_period),
        unknown_debit_groups_count=(
            document.validation.unknown_debit_groups_count if document else 0
        ),
        warning_codes=result.warnings,
    )


def _load_json(path: Path) -> Any:
    raw = path.read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    return json.loads(
        raw.decode(encoding),
        parse_float=Decimal,
        parse_int=int,
        parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("non-finite number")),
    )


def _recognizes_mit_structure(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    period = payload.get("PeriodoApuracao")
    initial = payload.get("DadosIniciais")
    debits = payload.get("Debitos")
    if not isinstance(period, dict) or not isinstance(initial, dict):
        return False
    # Keep a recognized document parseable when its period object is incomplete,
    # so the extractor can emit MIT_ASSESSMENT_PERIOD_MISSING.
    period_signature = True
    initial_signature = (
        isinstance(initial.get("SemMovimento"), bool)
        and bool(_INITIAL_SIGNATURE_KEYS & initial.keys())
    )
    if not (period_signature and initial_signature):
        return False
    if "Debitos" not in payload:
        return initial.get("SemMovimento") is True
    if not isinstance(debits, dict):
        return True
    return not debits or "BalancoLucroReal" in debits or any(
        isinstance(group, dict) and bool(set(_KNOWN_DEBIT_LISTS) & group.keys())
        for group in debits.values()
    )


def _parse_initial_data(payload: dict[str, Any]) -> MitInitialData:
    responsible_payload = payload.get("ResponsavelApuracao")
    responsible = None
    if isinstance(responsible_payload, dict):
        cpf_value = _optional_identifier(responsible_payload.get("CpfResponsavel"))
        cpf_digits = digits(cpf_value) if cpf_value else None
        phone_payload = responsible_payload.get("TelResponsavel")
        crc_payload = responsible_payload.get("RegistroCrc")
        responsible = MitAssessmentResponsible(
            cpf=cpf_digits,
            cpf_structure_valid=valid_cpf(cpf_digits) if cpf_digits else None,
            phone=(
                MitPhone(
                    area_code=_optional_text(phone_payload.get("Ddd")),
                    number=_optional_text(phone_payload.get("NumTelefone")),
                )
                if isinstance(phone_payload, dict)
                else None
            ),
            email=_optional_text(responsible_payload.get("EmailResponsavel")),
            crc_registration=(
                MitCrcRegistration(
                    state=_optional_text(crc_payload.get("UfRegistro")),
                    number=_optional_text(crc_payload.get("NumRegistro")),
                )
                if isinstance(crc_payload, dict)
                else None
            ),
            unknown_fields=_unknown_keys(
                responsible_payload,
                frozenset(
                    {"CpfResponsavel", "TelResponsavel", "EmailResponsavel", "RegistroCrc"}
                ),
            ),
        )
    return MitInitialData(
        no_activity=(
            payload.get("SemMovimento")
            if isinstance(payload.get("SemMovimento"), bool)
            else None
        ),
        legal_entity_qualification=_optional_int(payload.get("QualificacaoPj")),
        profit_taxation=_optional_int(payload.get("TributacaoLucro")),
        monetary_variations=_optional_int(payload.get("VariacoesMonetarias")),
        pis_cofins_regime=_optional_int(payload.get("RegimePisCofins")),
        assessment_responsible=responsible,
        unknown_fields=_unknown_keys(payload, _KNOWN_INITIAL_KEYS),
    )


def _parse_special_events(value: Any) -> tuple[MitSpecialEvent, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise LayoutExtractionFailure(ExtractionStatus.INCONCLUSIVE, "MIT_STRUCTURE_INCONCLUSIVE")
    events: list[MitSpecialEvent] = []
    for item in value:
        if not isinstance(item, dict):
            raise LayoutExtractionFailure(
                ExtractionStatus.INCONCLUSIVE, "MIT_STRUCTURE_INCONCLUSIVE"
            )
        events.append(
            MitSpecialEvent(
                event_id=_optional_int(item.get("IdEvento")),
                day=_optional_int(item.get("DiaEvento")),
                event_type=_optional_int(item.get("TipoEvento")),
                unknown_fields=_unknown_keys(
                    item, frozenset({"IdEvento", "DiaEvento", "TipoEvento"})
                ),
            )
        )
    return tuple(events)


def _parse_debit(
    item: dict[str, Any],
    *,
    raw_group: str,
    tax: str,
    list_kind: MitDebitListKind,
) -> tuple[MitDebit, tuple[str, ...]]:
    warnings: list[str] = []
    revenue_code = _optional_identifier(item.get("CodigoDebito"))
    normalized_code = normalize_mit_revenue_code(revenue_code) if revenue_code else None
    catalog_entry = lookup_mit_revenue_code(revenue_code) if revenue_code else None
    catalog_known: bool | None = None
    if revenue_code is not None:
        catalog_known = catalog_entry is not None
        if normalized_code is None:
            warnings.append("MIT_REVENUE_CODE_INVALID")
        elif catalog_entry is None:
            warnings.append("MIT_REVENUE_CODE_UNKNOWN")
        elif tax != "UNKNOWN" and catalog_entry.group != tax:
            warnings.append("MIT_REVENUE_CODE_GROUP_CONFLICT")

    postponed_year = _optional_int(item.get("AnoPostergado"))
    postponed_quarter = _optional_int(item.get("TrimPostergado"))
    debit_year = _optional_int(item.get("AnoDebito"))
    if (postponed_year is None) != (postponed_quarter is None):
        warnings.append("MIT_DEBIT_PERIOD_MISSING")
    return (
        MitDebit(
            tax=tax,
            raw_group=raw_group,
            list_kind=list_kind,
            revenue_code=revenue_code,
            normalized_revenue_code=normalized_code,
            revenue_code_catalog_known=catalog_known,
            revenue_code_periodicity=(catalog_entry.periodicity if catalog_entry else None),
            description=_optional_text(item.get("DescricaoDebito")),
            assessment_period=_parse_debit_period(
                postponed_year, postponed_quarter, debit_year
            ),
            pa_debit=_optional_int(item.get("PaDebito")),
            postponed_year=postponed_year,
            postponed_quarter=postponed_quarter,
            debit_year=debit_year,
            principal=_optional_decimal(item.get("ValorDebito")),
            identifiers=MitDebitIdentifiers(
                debit_id=_optional_identifier(item.get("IdDebito")),
                event_id=_optional_identifier(item.get("IdEventoDebito")),
                scp_taxpayer_id=_optional_identifier(item.get("CnpjScp")),
                establishment_taxpayer_id=_optional_identifier(
                    item.get("CnpjEstabelecimento")
                ),
                gold_municipality_code=_optional_identifier(
                    item.get("CodigoMunicipioOuro")
                ),
                incorporation_taxpayer_id=_optional_identifier(
                    item.get("CnpjIncorporacao")
                ),
            ),
            unknown_fields=_unknown_keys(item, _KNOWN_DEBIT_KEYS),
        ),
        tuple(warnings),
    )


def _parse_suspensions(value: Any) -> tuple[MitSuspension, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise LayoutExtractionFailure(ExtractionStatus.INCONCLUSIVE, "MIT_STRUCTURE_INCONCLUSIVE")
    suspensions: list[MitSuspension] = []
    known = frozenset(
        {
            "TipoSuspensao",
            "MotivoSuspensao",
            "ComDeposito",
            "NumeroProcesso",
            "ProcessoTerceiro",
            "DataDecisao",
            "VaraJudiciaria",
            "CodigoMunicipioSj",
            "ListaDebitosSuspensos",
        }
    )
    for item in value:
        if not isinstance(item, dict):
            raise LayoutExtractionFailure(
                ExtractionStatus.INCONCLUSIVE, "MIT_STRUCTURE_INCONCLUSIVE"
            )
        suspended_payload = item.get("ListaDebitosSuspensos", [])
        if not isinstance(suspended_payload, list):
            raise LayoutExtractionFailure(
                ExtractionStatus.INCONCLUSIVE, "MIT_STRUCTURE_INCONCLUSIVE"
            )
        suspended_debits: list[MitSuspendedDebit] = []
        for suspended in suspended_payload:
            if not isinstance(suspended, dict):
                raise LayoutExtractionFailure(
                    ExtractionStatus.INCONCLUSIVE, "MIT_STRUCTURE_INCONCLUSIVE"
                )
            suspended_debits.append(
                MitSuspendedDebit(
                    debit_id=_optional_identifier(suspended.get("IdDebitoSuspenso")),
                    suspended_amount=_optional_decimal(suspended.get("ValorSuspenso")),
                    unknown_fields=_unknown_keys(
                        suspended, frozenset({"IdDebitoSuspenso", "ValorSuspenso"})
                    ),
                )
            )
        suspensions.append(
            MitSuspension(
                suspension_type=_optional_int(item.get("TipoSuspensao")),
                reason=_optional_int(item.get("MotivoSuspensao")),
                with_deposit=(
                    item.get("ComDeposito")
                    if isinstance(item.get("ComDeposito"), bool)
                    else None
                ),
                process_number=_optional_identifier(item.get("NumeroProcesso")),
                third_party_process=(
                    item.get("ProcessoTerceiro")
                    if isinstance(item.get("ProcessoTerceiro"), bool)
                    else None
                ),
                decision_date=_optional_int(item.get("DataDecisao")),
                judicial_court=_optional_int(item.get("VaraJudiciaria")),
                judicial_municipality_code=_optional_identifier(
                    item.get("CodigoMunicipioSj")
                ),
                suspended_debits=tuple(suspended_debits),
                unknown_fields=_unknown_keys(item, known),
            )
        )
    return tuple(suspensions)


def _parse_file_period(value: Any) -> MitAssessmentPeriod | None:
    if not isinstance(value, dict):
        return None
    year = _optional_int(value.get("AnoApuracao"))
    month = _optional_int(value.get("MesApuracao"))
    if year is None or month is None or not 1 <= month <= 12:
        return None
    return MitAssessmentPeriod(
        kind=MitPeriodKind.MONTH,
        year=year,
        month=month,
        period=f"{year:04d}-{month:02d}",
    )


def _parse_debit_period(
    postponed_year: int | None,
    postponed_quarter: int | None,
    debit_year: int | None,
) -> MitAssessmentPeriod | None:
    if (
        postponed_year is not None
        and postponed_quarter is not None
        and 1 <= postponed_quarter <= 4
    ):
        return MitAssessmentPeriod(
            kind=MitPeriodKind.QUARTER,
            year=postponed_year,
            quarter=postponed_quarter,
            period=f"{postponed_year:04d}-Q{postponed_quarter}",
        )
    if debit_year is not None:
        return MitAssessmentPeriod(
            kind=MitPeriodKind.YEAR,
            year=debit_year,
            period=f"{debit_year:04d}",
        )
    return None


def _optional_decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (Decimal, int, str)):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    return None


def _optional_identifier(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (str, int)):
        text = str(value).strip()
        return text or None
    return None


def _optional_text(value: Any) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def _optional_int(value: Any) -> int | None:
    return value if type(value) is int else None


def _unknown_keys(payload: dict[str, Any], known: frozenset[str]) -> tuple[str, ...]:
    return tuple(sorted(str(key) for key in payload if key not in known))
