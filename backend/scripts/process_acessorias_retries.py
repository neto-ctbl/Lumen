from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.db.session import SessionLocal  # noqa: E402
from backend.app.services.integrations.econtrole.webhook_completion import process_due_acessorias_retries  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Processa retries pendentes da Acessorias.")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    session = SessionLocal()
    try:
        result = process_due_acessorias_retries(session, limit=args.limit)
        payload = {
            "selected": result.selected,
            "processed": result.processed,
            "succeeded": result.succeeded,
            "rescheduled": result.rescheduled,
            "exhausted": result.exhausted,
            "cancelled": result.cancelled,
            "failed": result.failed,
            "details": result.details,
            "dry_run": args.dry_run,
        }
        if args.dry_run:
            session.rollback()
        else:
            session.commit()
    finally:
        session.close()
    print(json.dumps(payload, ensure_ascii=True))


if __name__ == "__main__":
    main()
