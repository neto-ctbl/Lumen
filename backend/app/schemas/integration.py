from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class IntegrationHealthItem(BaseModel):
    provider: str
    label: str
    status: str
    account_status: str | None
    last_run_status: str | None
    last_run_at: str | None
    processed_count: int
    error_count: int
    note: str
    snapshot_counts: dict[str, int] | None = None
    active_run_status: str | None = None
    active_run_started_at: str | None = None
    stale_warning: str | None = None
    session_status: str | None = None
    session_loaded_at: str | None = None
    session_validated_at: str | None = None
    session_expires_at: str | None = None
    cache_items: int | None = None
    cache_expired_items: int | None = None
    cache_outdated_parser_items: int | None = None
    cache_last_refresh: str | None = None
    watcher_latest_detected_at: str | None = None
    watcher_latest_import_at: str | None = None


class IntegrationHealthResponse(BaseModel):
    items: list[IntegrationHealthItem]


class SittaxSyncRequest(BaseModel):
    period: str
    company_id: int | None = None
    limit: int | None = None
    scope: str = "ALL"
    max_pages: int = 100
    dry_run: bool = False


class SittaxSyncResponse(BaseModel):
    run_id: int | None
    status: str
    dry_run: bool
    summary: dict[str, Any] = Field(default_factory=dict)
    errors: list[dict[str, Any]] = Field(default_factory=list)
