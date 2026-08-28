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


class DashboardDctfwebSummary(BaseModel):
    evaluated: int = 0
    dp: int = 0
    fiscal: int = 0
    shared: int = 0
    undetermined: int = 0


class DashboardFactorRSummary(BaseModel):
    targets: int = 0
    effective: int = 0
    review: int = 0
    calculated: int = 0
    threshold_divergences: int = 0
    incomplete: int = 0


class DashboardResponse(BaseModel):
    period: str
    kpis: DashboardKpis
    department_totals: list[DashboardDepartmentSummary]
    status_totals: list[DashboardStatusSummary]
    dctfweb: DashboardDctfwebSummary = DashboardDctfwebSummary()
    factor_r: DashboardFactorRSummary = DashboardFactorRSummary()
