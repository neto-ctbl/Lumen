from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


def _normalize_cnae(value: str | None) -> str | None:
    if value is None:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return None
    if len(digits) != 7:
        raise ValueError("CNAE must contain exactly 7 digits.")
    return digits


class NfsePartySummary(BaseModel):
    document: str | None = None
    name: str | None = None


class NfseCancellationInfo(BaseModel):
    cancelled: bool = False
    substituted_by_key: str | None = None


class NfseNormalizedDocument(BaseModel):
    source_layout: str = Field(pattern="^(NFSE_ABRASF_204|NFSE_NACIONAL_101)$")
    document_key: str
    issued_at: str
    service_period: str = Field(pattern=r"^\d{4}-\d{2}$")
    service_amount: Decimal
    cnae: str | None = None
    municipal_tax_code: str | None = None
    municipal_tax_description: str | None = None
    provider: NfsePartySummary
    taker: NfsePartySummary | None = None
    cancellation: NfseCancellationInfo = Field(default_factory=NfseCancellationInfo)

    @field_validator("cnae")
    @classmethod
    def normalize_cnae(cls, value: str | None) -> str | None:
        return _normalize_cnae(value)

    def can_count_as_revenue(self) -> bool:
        return not self.cancellation.cancelled and not self.cancellation.substituted_by_key
