"""Fiscal watcher period grammar, deliberately independent from Dominio payroll."""

from __future__ import annotations

from agent.watcher.path_contract import folder_period_to_competence


def folder_period_from_path(folder_period: str) -> str:
    return folder_period_to_competence(folder_period)
