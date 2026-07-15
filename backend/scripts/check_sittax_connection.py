from __future__ import annotations

import argparse
from pathlib import Path

from backend.app.core.config import get_settings
from backend.app.core.security import mask_value
from backend.app.services.integrations.sittax import FixtureSittaxClient, SittaxClient, SittaxSession
from backend.app.services.integrations.sittax.errors import SittaxError


FIXTURE_DIR = Path("backend/tests/fixtures/sittax")
DEFAULT_LOGIN_FIXTURE = FIXTURE_DIR / "login_success.json"
DEFAULT_COMPANIES_FIXTURE = FIXTURE_DIR / "companies_success.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate read-only Sittax login and companies listing.")
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--companies-fixture", type=str, required=False)
    return parser


def run_check(*, fixture: bool, companies_fixture: str | None = None) -> int:
    settings = get_settings()
    session = SittaxSession.from_settings(settings)
    client: SittaxClient | FixtureSittaxClient
    if fixture:
        client = FixtureSittaxClient.from_files(
            session=session,
            login_path=DEFAULT_LOGIN_FIXTURE,
            companies_path=companies_fixture or DEFAULT_COMPANIES_FIXTURE,
        )
    else:
        client = SittaxClient(session=session)
    try:
        with session.exclusive():
            if fixture:
                client.authenticate_with_settings(settings)
            else:
                client.authenticate_with_settings(settings)
            companies = client.list_companies()

        office_display = "YES"
        if session.office_id:
            office_display = f"YES ({mask_value(session.office_id, visible_prefix=2, visible_suffix=2)})"

        print("Sittax authentication: OK")
        print(f"Office resolved: {office_display}")
        print(f"Companies returned: {len(companies)}")
        print("Read-only validation: OK")
        return 0
    finally:
        session.close()


def main() -> None:
    args = build_parser().parse_args()
    try:
        raise SystemExit(run_check(fixture=args.fixture, companies_fixture=args.companies_fixture))
    except SittaxError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
