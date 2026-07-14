from __future__ import annotations

from pydantic import BaseModel


class DashboardKpis(BaseModel):
    companies_total: int
    obligations_total: int
    delivered_total: int
    pending_total: int
    divergences_total: int
    evidences_total: int
    installments_total: int


class DashboardDepartmentSummary(BaseModel):
    department: str
    total: int


class DashboardStatusSummary(BaseModel):
    status: str
    total: int


class DashboardResponse(BaseModel):
    period: str
    kpis: DashboardKpis
    department_totals: list[DashboardDepartmentSummary]
    status_totals: list[DashboardStatusSummary]
