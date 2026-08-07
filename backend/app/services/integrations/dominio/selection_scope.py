from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from backend.app.services.integrations.dominio.contracts import DominioSelectionScope


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class DominioManifestSelectionMetadata:
    selection_scope: str
    source_filter_name: str | None
    target_company_count: int | None
    target_list_sha256: str | None
    original_selection_scope: str | None


def normalize_selection_scope(value: str | None) -> tuple[str, str | None]:
    original = None if value is None else str(value).strip() or None
    normalized = normalize_text_token(original)
    if normalized in {"ATIVAS", "ACTIVE", "ACTIVE COMPANIES"}:
        return DominioSelectionScope.ACTIVE_COMPANIES.value, original
    if normalized in {"FACTOR_R", "FACTOR R"}:
        return DominioSelectionScope.FACTOR_R.value, original
    if normalized == "CUSTOM":
        return DominioSelectionScope.CUSTOM.value, original
    if normalized == "UNKNOWN":
        return DominioSelectionScope.UNKNOWN.value, original
    return DominioSelectionScope.UNKNOWN.value, original


def normalize_company_filter_name(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = normalize_text_token(text)
    if normalized == "ATIVAS":
        return "Ativas"
    if normalized == "FATOR R":
        return "Fator R"
    return text


def selection_scope_from_company_filter(value: str | None) -> str:
    normalized = normalize_text_token(value)
    if normalized in {"ATIVAS", "ACTIVE", "ACTIVE COMPANIES"}:
        return DominioSelectionScope.ACTIVE_COMPANIES.value
    if normalized == "FATOR R":
        return DominioSelectionScope.FACTOR_R.value
    if normalized:
        return DominioSelectionScope.CUSTOM.value
    return DominioSelectionScope.UNKNOWN.value


def build_manifest_selection_metadata(
    *,
    selection_scope: str | None,
    source_filter_name: str | None,
    target_company_count: int | None,
    target_list_sha256: str | None,
) -> DominioManifestSelectionMetadata:
    normalized_filter_name = normalize_company_filter_name(source_filter_name)
    normalized_scope, original_scope = normalize_selection_scope(selection_scope)
    if normalized_scope == DominioSelectionScope.UNKNOWN.value:
        inferred_scope = selection_scope_from_company_filter(normalized_filter_name)
        if inferred_scope != DominioSelectionScope.CUSTOM.value:
            normalized_scope = inferred_scope
    normalized_target_company_count = normalize_target_company_count(target_company_count)
    normalized_target_list_sha256 = normalize_target_list_sha256(target_list_sha256)
    if normalized_scope != DominioSelectionScope.FACTOR_R.value:
        normalized_target_company_count = None
        normalized_target_list_sha256 = None
    return DominioManifestSelectionMetadata(
        selection_scope=normalized_scope,
        source_filter_name=normalized_filter_name,
        target_company_count=normalized_target_company_count,
        target_list_sha256=normalized_target_list_sha256,
        original_selection_scope=original_scope,
    )


def normalize_target_company_count(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def normalize_target_list_sha256(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text or not SHA256_RE.fullmatch(text):
        return None
    return text


def normalize_text_token(value: object) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value).strip())
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(ascii_text.upper().replace("_", " ").split())
