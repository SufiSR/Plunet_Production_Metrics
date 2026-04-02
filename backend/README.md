# Backend Baseline

Python backend baseline for DORA Metrics.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Quality Checks

```powershell
ruff check .
mypy app
```

## Notes

- Dependencies are managed with `requirements.txt` (no Poetry).
- Linting and static typing are configured in `pyproject.toml`.
- Configuration schema baseline is in `app/config_schema.py`.
- Runtime config load order is: defaults -> `configuration.yml` (path from `DORA_CONFIG_PATH`, default: repo-root file next to `backend/`) -> `app_configuration` -> env overrides.
- Application logs: set `DORA_LOG_LEVEL` to `INFO` (default) or `DEBUG` so pipeline messages from `app.*` appear in Docker / uvicorn output (the root logger defaults to WARNING otherwise).
- Docker Compose mounts repo `configuration.yml` and sets `DORA_CONFIG_PATH=/app/configuration.yml` (see root `docker-compose.yml`).
- Collector runs load effective config via `app/services/config_service.py`; after `PATCH /admin/config`, trigger a reload in-process or restart the backend process.
