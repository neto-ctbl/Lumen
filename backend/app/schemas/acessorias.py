from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class AcessoriasSyncRequest(BaseModel):
    period: str
    company_id: int | None = Field(default=None)
    dry_run: bool = Field(default=False)
    sync_companies: bool = Field(default=True)
    sync_deliveries: bool = Field(default=True)

    @field_validator("period")
    @classmethod
    def validate_period(cls, value: str) -> str:
        if len(value) != 7 or value[4] != "-" or not value[:4].isdigit() or not value[5:].isdigit():
            raise ValueError("period must use YYYY-MM format.")
        month = int(value[5:])
        if month < 1 or month > 12:
            raise ValueError("period month must be between 01 and 12.")
        return value


class AcessoriasSyncResponse(BaseModel):
    run_id: int | None
    status: str
    dry_run: bool
    summary: dict[str, int | str | list[str] | dict[str, int]]
    errors: list[dict[str, str | int | None]]
