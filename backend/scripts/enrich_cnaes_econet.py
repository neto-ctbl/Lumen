from __future__ import annotations

import argparse
import json
import os

import requests


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Call the local Lumen Econet enrichment API.")
    parser.add_argument("--api-base-url", default="http://localhost:8000")
    parser.add_argument("--org-slug", required=False)
    parser.add_argument("--company-id", action="append", type=int, dest="company_ids")
    parser.add_argument("--cnae", action="append", dest="cnaes")
    parser.add_argument("--limit", type=int, required=False)
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cache-only", action="store_true")
    parser.add_argument("--force-refresh", action="store_true")
    parser.add_argument("--no-sync-catalog", action="store_true")
    parser.add_argument("--no-classify", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    token = os.getenv("LUMEN_API_TOKEN")
    if not token:
        raise SystemExit("LUMEN_API_TOKEN is required.")
    payload = {
        "organization_slug": args.org_slug,
        "company_ids": args.company_ids,
        "cnaes": args.cnaes,
        "limit": args.limit,
        "dry_run": args.dry_run,
        "cache_only": args.cache_only,
        "force_refresh": args.force_refresh,
        "sync_catalog": not args.no_sync_catalog,
        "classify_companies": not args.no_classify,
    }
    response = requests.post(
        f"{args.api_base_url.rstrip('/')}/api/v1/integrations/econet/enrich",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
        timeout=args.timeout_seconds,
    )
    try:
        body = response.json()
    except ValueError:
        body = {"status_code": response.status_code}
    print(json.dumps(body, ensure_ascii=True))
    if response.status_code >= 400:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
