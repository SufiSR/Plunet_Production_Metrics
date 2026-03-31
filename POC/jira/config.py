import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

_CONFIG_FILE = Path(__file__).parent / "configuration.yml"


def _load_yaml() -> dict:
    if not _CONFIG_FILE.exists():
        return {}
    with open(_CONFIG_FILE, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def get_config() -> dict:
    required = ["JIRA_URL", "JIRA_USERNAME", "JIRA_TOKEN"]
    config = {}

    missing = []
    for key in required:
        value = os.getenv(key)
        if not value:
            missing.append(key)
        config[key] = value

    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in your values."
        )

    yaml_cfg = _load_yaml()
    jira_cfg = yaml_cfg.get("jira", {}) or {}
    config["lookback_years"] = jira_cfg.get("lookback_years", 3)
    config["production_bug_indicator_cf_ids"] = jira_cfg.get(
        "production_bug_indicator_cf_ids",
        [10114],
    )
    config["excluded_projects"] = jira_cfg.get("excluded_projects", [])
    return config
