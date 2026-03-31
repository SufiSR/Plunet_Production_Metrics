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
