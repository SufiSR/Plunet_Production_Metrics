"""Fetch Jira workflow definitions and project→workflow mappings only.

Does not run issue search, worklogs, changelog, allocation, or feature membership.

Examples:
    python scripts/run_jira_workflows_sync.py
    python scripts/run_jira_workflows_sync.py --env-file ../.env
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync Jira workflows only (scheme + definitions).")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=_backend_root().parent / ".env",
        help="Path to .env file. Default: repository .env.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Python logging level. Default: INFO.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _apply_env(_load_env_file(args.env_file))

    backend_root = _backend_root()
    sys.path.insert(0, str(backend_root))

    from app.database import SessionLocal
    from app.jira_analytics.client import JiraAnalyticsClient
    from app.jira_analytics.workflow.workflow_sync import sync_jira_workflows
    from app.services.config_service import load_runtime_config

    if not (os.getenv("DATABASE_URL") or "").strip():
        logging.error("DATABASE_URL is not set")
        return 1

    with SessionLocal() as db:
        runtime = load_runtime_config(db)
        token = (runtime.jira_token or "").strip()
        if not token:
            logging.error("Jira token is not configured (env or app_configuration)")
            return 1

        with JiraAnalyticsClient(
            runtime.settings.jira.base_url,
            token,
            user_email=runtime.jira_user_email,
        ) as client:
            counts = sync_jira_workflows(db, client)
        db.commit()

    ok = counts.workflows_upserted > 0 and counts.mappings_upserted > 0 and not counts.errors
    summary = {
        "ok": ok,
        "records": counts.as_records_processed(),
        "errors": counts.errors,
    }
    print(json.dumps(summary, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
