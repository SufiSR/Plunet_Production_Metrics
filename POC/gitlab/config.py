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
    required = ["GITLAB_URL", "GITLAB_TOKEN"]
    config: dict = {}
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
    gl = yaml_cfg.get("gitlab", {}) or {}
    config["project_path"] = gl.get("project_path", "dev/plunet")
    config["per_page"] = int(gl.get("per_page", 100))
    config["lookback_years"] = int(gl.get("lookback_years", 2))
    raw_branches = gl.get("target_branches")
    if raw_branches is None:
        raw_branches = [gl.get("target_branch", "master")]
    if isinstance(raw_branches, str):
        raw_branches = [raw_branches]
    config["target_branches"] = [str(b).strip() for b in raw_branches if str(b).strip()]
    if not config["target_branches"]:
        config["target_branches"] = ["master"]
    markers = gl.get("non_customer_release_markers") or ["rc", "beta"]
    config["non_customer_release_markers"] = [
        str(m).strip().lower() for m in markers if str(m).strip()
    ]
    if not config["non_customer_release_markers"]:
        config["non_customer_release_markers"] = ["rc", "beta"]

    return config
