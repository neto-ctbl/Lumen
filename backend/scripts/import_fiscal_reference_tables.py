from __future__ import annotations

import argparse
from pathlib import Path

from backend.app.db.session import SessionLocal
from backend.app.services.fiscal_reference import (
    CNAE_LC116,
    LC116_NBS_IBSCBS,
    TRIBNAC_NBS_IBSCBS,
    import_reference_files,
    json_result,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import global fiscal reference XLSX files.")
    parser.add_argument("--cnae-lc116", type=Path)
    parser.add_argument("--lc116-nbs", type=Path)
    parser.add_argument("--tribnac-nbs", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    paths = {kind: path for kind, path in {
        CNAE_LC116: args.cnae_lc116,
        LC116_NBS_IBSCBS: args.lc116_nbs,
        TRIBNAC_NBS_IBSCBS: args.tribnac_nbs,
    }.items() if path is not None}
    with SessionLocal() as db:
        print(json_result(import_reference_files(db, paths, dry_run=args.dry_run)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
