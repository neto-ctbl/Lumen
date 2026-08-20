from __future__ import annotations

import argparse
import json

from backend.app.db.session import SessionLocal
from backend.app.services.integrations.econtrole.webhook_completion import process_due_acessorias_retries


def main() -> int:
    parser = argparse.ArgumentParser(description="Lumen worker")
    parser.add_argument("--once", action="store_true", help="Run available retry processors once and exit")
    parser.add_argument("--retry-limit", type=int, default=100, help="Maximo de retries da Acessorias por execucao.")
    args = parser.parse_args()

    session = SessionLocal()
    try:
        result = process_due_acessorias_retries(session, limit=args.retry_limit)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    print(json.dumps(
        {
            "worker": "lumen",
            "once": args.once,
            "acessorias_retry": {
                "selected": result.selected,
                "processed": result.processed,
                "succeeded": result.succeeded,
                "rescheduled": result.rescheduled,
                "exhausted": result.exhausted,
                "cancelled": result.cancelled,
                "failed": result.failed,
            },
        },
        ensure_ascii=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
