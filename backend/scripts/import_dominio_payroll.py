from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.db.session import SessionLocal
from backend.app.services.integrations.dominio.importer import import_dominio_payroll_file
from backend.app.services.integrations.econtrole.sync import resolve_target_organization


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import a Dominio payroll PDF into Lumen.")
    parser.add_argument("--organization-slug", type=str, required=True)
    parser.add_argument("--file", type=str, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def run_import(*, organization_slug: str, file_path: str, dry_run: bool, output_json: bool) -> int:
    session = SessionLocal()
    try:
        organization = resolve_target_organization(session, organization_slug)
        result = import_dominio_payroll_file(
            session,
            organization=organization,
            file_path=Path(file_path),
            dry_run=dry_run,
        )
        payload = result.to_public_dict()
        if output_json:
            print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            for key in (
                "status",
                "duplicate",
                "dry_run",
                "selection_scope",
                "source_filter_name",
                "target_company_count",
                "target_list_sha256",
                "file_sha256",
                "physical_page_count",
                "source_competences",
                "assessment_competences",
                "total_companies",
                "total_matched",
                "total_unmatched",
                "total_invalid_cnpj",
                "total_missing_cnpj",
                "total_ambiguous",
                "total_warnings",
                "total_errors",
            ):
                print(f"{key}={payload[key]}")
        return 1 if result.status == "FAILED" else 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        session.close()


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(
        run_import(
            organization_slug=args.organization_slug,
            file_path=args.file,
            dry_run=args.dry_run,
            output_json=args.json,
        )
    )


if __name__ == "__main__":
    main()
