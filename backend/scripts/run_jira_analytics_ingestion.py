"""Run Jira analytics ingestion from the command line.

Examples:
    python scripts/run_jira_analytics_ingestion.py --days 90
    python scripts/run_jira_analytics_ingestion.py --jql "updated >= -90d ORDER BY updated DESC"
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


def _build_jql(args: argparse.Namespace) -> str:
    if args.jql:
        return str(args.jql)
    return f"updated >= -{args.days}d ORDER BY updated DESC"


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
        "records_processed": result.get("pipeline_runtime", {})
        .get("phases", {})
        .get("complete", {})
        .get("records_processed", {}),
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
    parser = argparse.ArgumentParser(description="Run Jira analytics ingestion.")
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="Look back this many days using Jira updated timestamp. Default: 90.",
    )
    parser.add_argument(
        "--jql",
        help="Explicit Jira JQL to run. Overrides --days.",
    )
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

    from app.jira_analytics.sync_pipeline import run_jira_analytics_sync

    jql = _build_jql(args)
    logging.getLogger(__name__).info("starting Jira analytics ingestion: %s", jql)
    result = run_jira_analytics_sync(trigger="manual-script", jql=jql)
    _print_summary(result)
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
