from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SittaxOfficeReference(BaseModel):
    id: str
    name: str | None = None


class SittaxCompanyItem(BaseModel):
    external_id: str
    cnpj: str
    legal_name: str
    trade_name: str | None = None
    state_registration: str | None = None
    state: str | None = None
    status: str | None = None
    homologated: bool | None = None
    cash_regime: bool | None = None
    raw_payload: dict[str, Any] = Field(repr=False)
