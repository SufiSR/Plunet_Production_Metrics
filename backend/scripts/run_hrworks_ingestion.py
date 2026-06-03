"""Run HRworks monthly hours ingestion from the command line.

Examples:
    python scripts/run_hrworks_ingestion.py
    python scripts/run_hrworks_ingestion.py
    python scripts/run_hrworks_ingestion.py --start-date 2024-06-01 --end-date 2024-06-30
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _strip_env_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        if key:
            values[key] = _strip_env_value(value)
    return values


def _apply_env(values: dict[str, str]) -> None:
    for key, value in values.items():
        os.environ.setdefault(key, value)

    if os.getenv("DATABASE_URL"):
        return

    user = values.get("POSTGRES_USER") or os.getenv("POSTGRES_USER")
    password = values.get("POSTGRES_PASSWORD") or os.getenv("POSTGRES_PASSWORD")
    database = values.get("POSTGRES_DB") or os.getenv("POSTGRES_DB")
    if user and password and database:
        os.environ["DATABASE_URL"] = (
            f"postgresql+psycopg2://{user}:{password}@localhost:5433/{database}"
        )


def _configure_logging(level_name: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level_name.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _print_summary(result: dict[str, Any]) -> None:
    phases = result.get("pipeline_runtime", {}).get("phases", {})
    summary = {
        "status": result.get("status"),
        "duration_seconds": result.get("duration_seconds"),
        "month_windows": result.get("pipeline_runtime", {}).get("month_windows"),
        "records_processed": phases.get("complete", {}).get("records_processed", {}),
        "phases": {
            name: {
                "status": phase.get("status"),
                "duration_seconds": phase.get("duration_seconds"),
                "records_processed": phase.get("records_processed"),
            }
            for name, phase in phases.items()
            if isinstance(phase, dict)
        },
    }
    print(json.dumps(summary, indent=2, default=str))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run HRworks monthly hours ingestion.")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help=(
            "Rolling window from configuration: past incremental_months_back months, "
            "current month, and incremental_forecast_months ahead. Without this flag, "
            "uses the full backfill window (2024-2025, YTD, forecast)."
        ),
    )
    parser.add_argument("--start-date", help="Inclusive month start date (YYYY-MM-DD).")
    parser.add_argument("--end-date", help="Inclusive month end date (YYYY-MM-DD).")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=_backend_root().parent / ".env",
        help="Path to .env file. Default: repository .env.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level for visible progress. Default: INFO.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _configure_logging(str(args.log_level))
    _apply_env(_load_env_file(args.env_file))

    backend_root = _backend_root()
    sys.path.insert(0, str(backend_root))

    from app.hrworks.periods import parse_iso_date
    from app.hrworks.sync_pipeline import run_hrworks_sync

    start_date = parse_iso_date(args.start_date) if args.start_date else None
    end_date = parse_iso_date(args.end_date) if args.end_date else None
    logging.getLogger(__name__).info(
        "starting HRworks ingestion (incremental=%s start=%s end=%s)",
        args.incremental,
        start_date,
        end_date,
    )
    result = run_hrworks_sync(
        trigger="manual-script",
        incremental=bool(args.incremental),
        start_date=start_date,
        end_date=end_date,
    )
    _print_summary(result)
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
