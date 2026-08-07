from __future__ import annotations

# ruff: noqa: E402

import argparse
import csv
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.db.session import SessionLocal
from backend.app.services.integrations.dominio.factor_r_targets import build_dominio_factor_r_targets
from backend.app.services.integrations.econtrole.sync import resolve_target_organization


CSV_HEADERS = (
    "dominio_company_code",
    "company_cnpj",
    "company_name",
    "is_active",
    "tax_regime",
    "is_mei",
    "factor_r_potential",
    "factor_r_effectively_used",
    "factor_r_cnae_codes",
    "factor_r_reason",
    "filter_action",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export the Dominio Factor R target universe.")
    parser.add_argument("--organization-slug", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--json-summary", type=str, required=True)
    return parser


def run_export(*, organization_slug: str, output_path: str, json_summary_path: str) -> int:
    session = SessionLocal()
    try:
        organization = resolve_target_organization(session, organization_slug)
        export = build_dominio_factor_r_targets(session, organization=organization)
        output = Path(output_path)
        summary = Path(json_summary_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        summary.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
            writer.writeheader()
            for row in export.rows:
                writer.writerow(row.to_csv_row())
        summary.write_text(
            json.dumps(export.summary_payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(export.terminal_summary(), ensure_ascii=True, sort_keys=True))
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    finally:
        session.close()


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(
        run_export(
            organization_slug=args.organization_slug,
            output_path=args.output,
            json_summary_path=args.json_summary,
        )
    )


if __name__ == "__main__":
    main()
