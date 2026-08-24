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
from backend.app.services.integrations.dominio.enrichment import enrich_dominio_payroll_monetary_summary
from backend.app.services.integrations.econtrole.sync import resolve_target_organization


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Enrich persisted Dominio payroll movements with monetary summary schema v2.")
    parser.add_argument("--organization-slug", type=str, required=True)
    parser.add_argument("--file", type=str)
    parser.add_argument("--directory", type=str)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser


def run_enrichment(
    *,
    organization_slug: str,
    file_path: str | None,
    directory_path: str | None,
    dry_run: bool,
    output_json: bool,
) -> int:
    if bool(file_path) == bool(directory_path):
        print("Exactly one of --file or --directory is required.", file=sys.stderr)
        return 2

    session = SessionLocal()
    try:
        organization = resolve_target_organization(session, organization_slug)
        files = _resolve_files(file_path=file_path, directory_path=directory_path)
        results = [
            enrich_dominio_payroll_monetary_summary(
                session,
                organization=organization,
                file_path=path,
                dry_run=dry_run,
            )
            for path in files
        ]
        payload = _build_payload(results=results, dry_run=dry_run)
        if output_json:
            print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
        else:
            for key, value in payload.items():
                if key == "files":
                    continue
                print(f"{key}={value}")
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        session.rollback()
        return 2
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        session.rollback()
        return 2
    finally:
        session.close()


def _resolve_files(*, file_path: str | None, directory_path: str | None) -> list[Path]:
    if file_path is not None:
        return [Path(file_path)]
    directory = Path(directory_path or "")
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Directory was not found: {directory}")
    files = sorted(directory.glob("Resumo_Mensal_*.pdf"))
    if not files:
        raise FileNotFoundError(f"No payroll PDFs were found in: {directory}")
    return files


def _build_payload(*, results: list, dry_run: bool) -> dict[str, object]:
    changed_key = "movements_would_update" if dry_run else "movements_updated"
    payload: dict[str, object] = {
        "imports_found": sum(item.imports_found for item in results),
        "movements_parsed": sum(item.movements_parsed for item in results),
        "movements_matched": sum(item.movements_matched for item in results),
        changed_key: sum(item.movements_changed for item in results),
        "schema_v2": sum(item.schema_v2 for item in results),
        "complete": sum(item.complete for item in results),
        "partial": sum(item.partial for item in results),
        "insufficient": sum(item.insufficient for item in results),
        "unclassified_monetary_movements": sum(item.unclassified_monetary_movements for item in results),
        "already_enriched": sum(item.already_enriched for item in results),
        "files": [item.to_public_dict() for item in results],
    }
    return payload


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(
        run_enrichment(
            organization_slug=args.organization_slug,
            file_path=args.file,
            directory_path=args.directory,
            dry_run=args.dry_run,
            output_json=args.json,
        )
    )


if __name__ == "__main__":
    main()
