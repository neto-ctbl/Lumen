from __future__ import annotations

# ruff: noqa: E402

import argparse
import json
from pathlib import Path
import sys
import time

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.db.session import SessionLocal
from backend.app.services.integrations.dominio.watcher import run_dominio_payroll_watcher_once
from backend.app.services.integrations.econtrole.sync import resolve_target_organization


def main() -> None:
    parser = argparse.ArgumentParser(description="Observe canonical Domínio payroll reports and import only new valid files.")
    parser.add_argument("--organization-slug", required=True)
    parser.add_argument("--directory", default="scripts/collectors/dominio/Relatorios_Dominio")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--once", action="store_true", help="Run one local scan.")
    mode.add_argument("--watch", action="store_true", help="Run local scans continuously until interrupted.")
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.interval_seconds < 10:
        parser.error("--interval-seconds must be at least 10.")
    try:
        while True:
            session = SessionLocal()
            try:
                organization = resolve_target_organization(session, args.organization_slug)
                result = run_dominio_payroll_watcher_once(
                    session, organization=organization, directory=args.directory, dry_run=args.dry_run
                )
                payload = result.to_dict()
                print(json.dumps(payload, ensure_ascii=True, sort_keys=True) if args.json else "\n".join(f"{k}={v}" for k, v in payload.items()))
            finally:
                session.close()
            if args.once:
                return
            time.sleep(args.interval_seconds)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
