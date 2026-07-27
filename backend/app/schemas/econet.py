from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EconetSessionCookieInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=4096, repr=False)
    domain: str = Field(min_length=1, max_length=255)
    path: str = Field(min_length=1, max_length=255, default="/")
    expires: int | float | None = None
    httpOnly: bool = False
    secure: bool = False
    sameSite: str | None = Field(default="Lax", max_length=20)


class EconetSessionImportRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cookies: list[EconetSessionCookieInput]

    @field_validator("cookies")
    @classmethod
    def validate_non_empty(cls, value: list[EconetSessionCookieInput]) -> list[EconetSessionCookieInput]:
        if not value:
            raise ValueError("cookies must not be empty.")
        return value


class EconetSessionStatusResponse(BaseModel):
    status: str
    cookie_count: int
    cookie_names: list[str]
    loaded_at: str | None
    validated_at: str | None
    expires_at: str | None
    last_error_kind: str | None
    generation: int
    message: str | None = None


class EconetSessionProbeResponse(EconetSessionStatusResponse):
    pass


class EconetSessionClearResponse(EconetSessionStatusResponse):
    pass


class EconetEnrichmentRequest(BaseModel):
    organization_slug: str | None = None
    company_ids: list[int] | None = None
    cnaes: list[str] | None = None
    limit: int | None = Field(default=None, ge=1, le=50)
    dry_run: bool = False
    cache_only: bool = False
    force_refresh: bool = False
    sync_catalog: bool = True
    classify_companies: bool = True


class EconetEnrichmentItemResponse(BaseModel):
    cnae: str
    status: str
    cache_record_id: int | None = None
    parse_status: str | None = None
    message: str | None = None


class EconetEnrichmentResponse(BaseModel):
    run_id: int | None = None
    status: str
    dry_run: bool
    summary: dict[str, object]
    items: list[EconetEnrichmentItemResponse]
    catalog_summary: dict[str, object] | None = None


class CompanyCnaeItemResponse(BaseModel):
    cnae: str
    cnae_formatted: str
    is_primary: bool
    source: str
    active: bool
    first_seen_at: str
    last_seen_at: str
    deactivated_at: str | None = None


class CompanyCnaeListResponse(BaseModel):
    items: list[CompanyCnaeItemResponse]


class FactorRPotentialResponse(BaseModel):
    company_id: int
    status: str
    factor_r_potential: bool | None
    cnaes_total: int
    cnaes_with_cache: int
    positive_cnaes: list[str]
    negative_cnaes: list[str]
    missing_cnaes: list[str]
    annex_default: str | None = None
    annex_conditional: str | None = None
    factor_r_threshold: Decimal | None = None
