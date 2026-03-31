from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from app.config_schema import ConfigurationSchema


def _default_config_path() -> Path:
    return Path(__file__).resolve().parents[2] / "configuration.yml"


def load_configuration() -> ConfigurationSchema:
    config_path = Path(os.getenv("DORA_CONFIG_PATH", str(_default_config_path())))
    if not config_path.exists():
        return ConfigurationSchema()

    payload: Any
    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, dict):
        return ConfigurationSchema()
    return ConfigurationSchema.model_validate(payload)
