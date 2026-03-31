# Backend Components — Documentation

## Technology Mapping (Spring Boot → Python)

| Spring Boot concept | Python equivalent |
| --- | --- |
| `@RestController` | FastAPI `APIRouter` |
| `@Service` / `@Component` | Plain Python classes (injected via `Depends`) |
| `@Scheduled` | APScheduler `AsyncIOScheduler` |
| Spring Retry | Tenacity (`@retry` decorator) |
| `application.yml` | pydantic-settings `BaseSettings` + `.env` + `configuration.yml` |
| Spring Data JPA | **SQLAlchemy 2.x sync** sessions (see `database-schema-documentation.md`) |
| Hibernate | SQLAlchemy ORM declarative models |
| Testcontainers | testcontainers-python |
| WireMock | respx |

**Note:** The persistence layer is **synchronous** (psycopg2). If collector methods are `async`, use `asyncio.to_thread()` for DB-bound work, or keep collectors synchronous and invoke them from the scheduler on a thread pool. The invariant is: **one writer pipeline per nightly run**, no concurrent ORM sessions racing on the same rows.

---

## Component Overview

```
backend/app/
├── main.py                  # FastAPI app + lifespan (starts scheduler)
├── config.py                # BaseSettings: env vars, defaults
├── database.py              # Sync engine, session factory (SQLAlchemy 2.x)
├── models/                  # SQLAlchemy ORM models
│   ├── repository.py
│   ├── release.py
│   ├── commit.py
│   ├── merge_request.py
│   ├── production_bug.py
│   ├── metric_snapshot.py
│   ├── sync_log.py
│   └── app_configuration.py # runtime Admin-edited settings + encrypted secrets
├── schemas/                 # Pydantic v2 models (API I/O)
├── api/                     # FastAPI routers
│   ├── metrics.py
│   ├── repositories.py
│   ├── sync.py
│   ├── health.py
│   ├── auth.py              # login / logout / me
│   └── admin_config.py      # GET/PATCH config (Admin only)
├── collectors/
│   ├── gitlab_collector.py
│   └── jira_collector.py
├── services/
│   ├── metric_service.py
│   ├── snapshot_service.py
│   ├── release_service.py
│   ├── bug_service.py
│   └── config_service.py    # effective config merge + admin CRUD
├── scheduler.py             # APScheduler: nightly + optional retention/backup jobs
└── webhook.py               # Webhook notification logic
```

---

## Collectors

External calls use **httpx** (sync or async) with **Tenacity** retries on transient failures. Rate limits: stay within GitLab (~20 req/s); backoff on HTTP 429.

### `gitlab_collector.py`

| Function | Description |
| --- | --- |
| `sync_repositories()` | Resolve configured projects; upsert `Repository` |
| `sync_tags()` | List tags; upsert `Release` with `customer_release`, version parse, `committed_at` |
| `sync_merge_requests()` | Merged MRs per `target_branch`; upsert `MergeRequest` with `merged_at`, SHAs, `jira_key` |
| `sync_mr_first_commit_timestamps()` | For MRs with `first_commit_at IS NULL`, `GET /merge_requests/:iid/commits`, set earliest `committed_date` |
| `map_mrs_to_customer_releases()` | Commit refs API; set `first_customer_tag`, `first_customer_tag_date`, `lead_time_hours`, `release_wait_time_hours`, `lead_time_match_status` |
| `sync_commits()` | Optional: enrich `Commit` table for traceability |

**Order:** tags and MRs should be current **before** lead-time mapping. First-commit fetch must run **after** MR upsert, **before** or alongside lead-time mapping (lead time needs `first_commit_at` for full DORA lead time).

### `jira_collector.py`

| Function | Description |
| --- | --- |
| `sync_production_bugs()` | JQL pull; upsert `ProductionBug` including **`priority`**, versions, health, indicators |
| `sync_issue_worklogs()` | Per issue: worklog API; upsert `issue_worklog`; refresh **`total_worklog_seconds`** on `production_bug` |
| `sync_ready_for_qa_timestamp()` | Changelog API; first transition to a status in **`ready_for_qa_status_names`** → **`ready_for_qa_at`** |
| `map_bugs_to_releases()` | Populate `bug_release` / CFR links from `affects_version` ↔ `Release` |
| `resolve_mttr_alpha_fix_releases()` | For each eligible bug (`healthy`, Critical/Blocker): path (1) MR by `jira_key`; path (2) `fix_versions` → tag; set `mttr_alpha_*` columns |
| `compute_lead_post_production()` | Set **`lead_post_production_hours`** on `merge_request` from linked bug **`ready_for_qa_at`** |
| `derive_mttr_minutes()` | Optional: set `mttr_minutes = closed_at - created_at` when issue closed |

`resolve_mttr_alpha_fix_releases()` and **`compute_lead_post_production()`** run after GitLab MR data and Jira bug/worklog/changelog data are present.

---

## Services

### `metric_service.py`

| Function | Description |
| --- | --- |
| `calculate_deployment_frequency(session, period)` | Count `customer_release` tags in window |
| `calculate_lead_time(session, period)` | Median/P75/P90 of `lead_time_hours` (`first_commit_at` → tag), per branch / stream |
| `calculate_release_wait_time(session, period)` | Median/P75/P90 of `release_wait_time_hours` (`merged_at` → tag) |
| `calculate_change_failure_rate(session, period)` | Binary failed releases / eligible releases |
| `calculate_mttr(session, period)` | Legacy Jira lifecycle: closed−created for closed bugs (optional KPI) |
| `calculate_mttr_alpha(session, period)` | Median/P75/P90 of `mttr_alpha_minutes` where resolved |
| `calculate_rework_rate(session, period)` | Phase 1+: patch vs minor structure from tags |

### `snapshot_service.py`

Writes **`metric_snapshot`** rows for `WEEK` / `MONTH` / `QUARTER`. After each successful nightly pipeline (when snapshots run), **overwrite** snapshots for the **current** incomplete period so dashboard totals match latest GitLab/Jira data.

### `release_service.py` / `bug_service.py`

Version parsing, RC detection, affected-release resolution — shared by collectors and metrics.

---

## Authentication & admin configuration

### `auth.py` / `dependencies.py`

| Piece | Description |
| --- | --- |
| `verify_admin_session` | FastAPI dependency: validates session cookie or JWT; raises **401** if missing/invalid. |
| Password verify | Compare `LoginRequest.password` to `DORA_ADMIN_PASSWORD` (env) **or** bcrypt hash in `admin_user` table (preferred for production). |
| Session store | Signed cookie (`SessionMiddleware`) **or** server-side session row with opaque `session_id` cookie. |

### `config_service.py` / `admin_config_repository.py`

| Piece | Description |
| --- | --- |
| Load effective config | Merge order: **defaults** → **`configuration.yml`** → **`app_configuration` DB** (if present). Env vars may still override Docker bootstrap. |
| `get_admin_config()` | Return DTO with **masked** secrets for `GET /admin/config`. |
| `patch_admin_config()` | Validate fields; encrypt tokens (e.g. **Fernet** via `CONFIG_ENCRYPTION_KEY`); trigger **config reload** so collectors pick up new URLs/tokens (hot-reload or process restart — implementation choice). |
| Audit (optional) | `config_audit_log` table: actor, timestamp, changed keys (not secret values). |

**Security:** Never log raw tokens. Document key rotation for `CONFIG_ENCRYPTION_KEY`.

---

## Scheduler

```python
# scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = AsyncIOScheduler()

scheduler.add_job(
    run_nightly_sync,
    trigger=CronTrigger(hour=2, minute=0),
    id="nightly_sync",
    replace_existing=True,
)
```

`run_nightly_sync` is the **only** mandatory recurring job for data freshness. Optional jobs: DB retention prune, `pg_dump` backup, telemetry.

### `run_nightly_sync()` — detailed flow

```
run_nightly_sync()
│
├── sync_log: start entry (GITLAB+JIRA combined run id)
│
├── [GitLab] try:
│       sync_repositories()
│       sync_tags()
│       sync_merge_requests()
│       sync_mr_first_commit_timestamps()
│       map_mrs_to_customer_releases()
│   catch → log; gitlab_ok = false
│
├── [Jira] try:
│       sync_production_bugs()
│       map_bugs_to_releases()
│   catch → jira_ok = false
│
├── if gitlab_ok AND jira_ok:
│       resolve_mttr_alpha_fix_releases()
│   elif jira_ok only:
│       skip MTTR Alpha (or partial: fix_version path only if tags already in DB from previous day)
│       — implementation choice: prefer strict consistency, skip if GitLab failed
│
├── if gitlab_ok OR jira_ok:
│       snapshot_service.generate_snapshots()
│   else:
│       skip snapshots
│
├── sync_log: finish + status (SUCCESS | PARTIAL_FAILURE | FAILED)
│
└── webhook.notify(...)
```

**Guarantee:** Under normal operation (both APIs up), **every calendar day** produces at least one full pass: raw data + cross-links + snapshots. Clock skew and job duration imply “data as of ~02:00 + runtime,” not millisecond realtime.

### Error handling summary

| Outcome | Snapshots | MTTR Alpha |
| --- | --- | --- |
| Both collectors OK | Yes | Yes |
| GitLab only | Yes (GitLab-heavy metrics fresh; CFR/Alpha partial) | Skip or best-effort per policy |
| Jira only | Yes (Jira-only fields) | Skip |
| Both fail | No | No |

Document the chosen partial policy in release notes; **recommended:** skip `resolve_mttr_alpha_fix_releases` unless GitLab **and** Jira succeeded.

---

## Retry strategy (Tenacity)

| Error | Retry |
| --- | --- |
| HTTP 429, 5xx | Yes (bounded) |
| Timeout | Yes |
| HTTP 401, 404, 400 | No |

Default: 3 attempts, exponential backoff, cap 60 s.

---

## Webhook notifications

| Event | When |
| --- | --- |
| `SYNC_SUCCESS` | All collectors OK |
| `SYNC_PARTIAL_FAILURE` | One collector failed |
| `SYNC_COMPLETE_FAILURE` | All failed |

Payload includes counts (repos, releases, MRs, bugs, snapshots written) and error messages.

---

## Configuration (`config.py` excerpt)

```python
class Settings(BaseSettings):
    gitlab_url: str
    gitlab_token: str
    jira_url: str
    jira_username: str
    jira_token: str

    sync_cron_hour: int = 2
    sync_cron_minute: int = 0

    database_url: str  # postgresql+psycopg2://user:pass@db:5432/dora

    webhook_enabled: bool = True
    webhook_url: str = ""

    class Config:
        env_file = ".env"
```

---

## Initial data load

First deployment: collectors backfill from `lookback_from` / `initial_load_from` in config. Subsequent nights **incrementally** upsert; snapshots always recomputed from current DB state.
