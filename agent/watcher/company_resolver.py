"""Extract the observed company-folder signal without resolving any database ID."""

from __future__ import annotations

from agent.watcher.path_contract import FiscalPath


def folder_company_from_path(fiscal_path: FiscalPath) -> str:
    return fiscal_path.folder_company
