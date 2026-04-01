# Database Schema – Documentation

## Tooling

| Tool | Purpose |
| --- | --- |
| SQLAlchemy 2.x | ORM models (declarative base, sync session) |
| psycopg2 | Sync PostgreSQL driver (decided over asyncpg; see open-questions B2) |
| Alembic | Database migration management |

All models live in `backend/app/models/`. Each model inherits from a shared `Base = DeclarativeBase()`.  
Alembic env is configured with a sync engine.

---

## Data lifecycle and daily refresh

- **Raw tables** (`release`, `merge_request`, `production_bug`, …) are populated by collectors during **`run_nightly_sync`** (default once per day). Rows are **upserted** by natural keys (e.g. `jira_key`, `gitlab_mr_id`, `repository_id` + `tag_name`).
- **Derived fields** on `merge_request` (lead time, release wait, `first_commit_at`) and on `production_bug` (**`mttr_alpha_*`**) are recomputed in the same run after both GitLab and Jira steps complete (where applicable).
- **`metric_snapshot`** holds pre-aggregated KPIs per period. The snapshot step **runs after** raw + derived updates. Rows for the **current** incomplete period are **overwritten** on each successful run so the API always serves numbers consistent with the latest sync. API `generated_at` is sourced from `metric_snapshot.created_at`.
- **Retention**: configurable pruning of old raw rows (see `configuration.yml`); snapshots may be kept indefinitely (low volume).

---

## ER Diagram

```
┌─────────────────┐       ┌──────────────────────────┐
│   repository    │       │         release          │
├─────────────────┤       ├──────────────────────────┤
│ id (PK)         │       │ id (PK)                  │
│ gitlab_id       │◄──────┤ repository_id (FK)       │
│ name            │       │ tag_name                 │
│ path            │       │ version_major            │
│ default_branch  │       │ version_minor            │
│ active          │       │ version_patch            │
│ created_at      │       │ pre_release              │  ← NULL = customer release
│ updated_at      │       │ customer_release (bool)  │  ← derived from tag name
└─────────────────┘       │ commit_sha               │
                          │ committed_at             │  ← tag commit committed_date
                          │ created_at               │
                          └──────────────────────────┘
                                    │
                                    ▼
┌──────────────────────────┐    ┌─────────────────────┐
│      merge_request       │    │   release_commit    │
├──────────────────────────┤    ├─────────────────────┤
│ id (PK)                  │    │ release_id (FK, PK) │
│ repository_id (FK)       │    │ commit_sha (FK, PK) │
│ gitlab_mr_id             │    └─────────────────────┘
│ title                    │              ▲
│ source_branch            │              │
│ target_branch            │    ┌─────────────────────┐
│ merged_at                │    │       commit        │
│ merge_commit_sha         │    ├─────────────────────┤
│ squash_commit_sha        │    │ sha (PK)            │
│ effective_commit_sha     │────┤ repository_id (FK)  │
│ jira_key                 │    │ author              │  ← extracted from title/branch/description
│ jira_key_source          │    │ committed_at        │  ← 'title'|'branch'|'description'|NULL
│ first_customer_tag       │    │ created_at          │
│ first_customer_tag_date  │    └─────────────────────┘
│ release_wait_time_hours  │  ← merged_at → first_customer_tag_date
│ lead_time_hours          │  ← first_commit_at → first_customer_tag_date (NULL if first_commit_at missing)
│ lead_time_match_status   │
│ created_at               │
└──────────────────────────┘

┌──────────────────────────────┐       ┌─────────────────────┐
│       production_bug         │       │     bug_release     │
├──────────────────────────────┤       ├─────────────────────┤
│ id (PK)                      │◄──────┤ bug_id (FK, PK)     │
│ jira_key                     │       │ release_id (FK, PK) │
│ summary                      │       └─────────────────────┘
│ issue_type                   │
│ status                       │
| priority                     |  <- Critical | Blocker | ... (MTTR Alpha filter)
│ created_at                   │
│ updated_at                   │
│ closed_at                    │
│ mttr_minutes                 │
| mttr_alpha_minutes           |  <- created_at -> first_fix_release_date (Critical+ only; NULL if unresolved)
| first_fix_release_tag        |  <- tag name of first release containing the fix
| first_fix_release_date       |  <- committed_date of that tag
| mttr_alpha_resolution_path   |  <- 'mr_jira_key' | 'fix_version' | NULL
│ components                   │  ← JSON array of component names
│ affects_versions             │  ← JSON array
│ fix_versions                 │  ← JSON array
│ parent_key                   │
│ parent_type                  │
│ indicator_cf10114            │  ← EXALATE value (text)
│ indicator_cf10123            │  ← CUSTOMERNAME value (text)
│ healthy (bool)               │  ← true = post-production, false = unresolved
│ healthmemo                   │  ← classification reason string
└──────────────────────────────┘

┌─────────────────────┐
│   metric_snapshot   │
├─────────────────────┤
│ id (PK)             │
│ repository_id (FK)  │  ← NULL = aggregated across all repos
│ period_start        │
│ period_end          │
│ period_type         │  ← WEEK | MONTH | QUARTER
│ deployment_freq     │
│ lead_time_minutes   │
│ release_wait_median_mins │  ← median merged_at → tag (optional Phase 1)
│ change_failure_rate │
│ mttr_minutes        │  ← optional Jira lifecycle statistic
│ mttr_alpha_minutes  │  ← median MTTR Alpha (Critical+ resolved in period)
│ created_at          │
└─────────────────────┘

┌──────────────────────────┐
│    app_configuration   │  ← singleton (id=1); runtime Admin UI + encrypted tokens
├──────────────────────────┤
│ id (PK)                  │
│ settings_json            │  ← non-secret structured config (paths, branches, cron, …)
│ gitlab_token_enc         │  ← optional Fernet blob
│ jira_token_enc           │
│ updated_at               │
└──────────────────────────┘

┌─────────────────────┐
│      sync_log       │
├─────────────────────┤
│ id (PK)             │
│ source              │  ← GITLAB | JIRA
│ started_at          │
│ finished_at         │
│ status              │  ← SUCCESS | FAILED
│ records_processed   │
│ error_message       │
└─────────────────────┘
```

---

## SQLAlchemy Model Notes

### `Repository`

```python
class Repository(Base):
    __tablename__ = "repository"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    gitlab_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

### `Release`

```python
class Release(Base):
    __tablename__ = "release"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("repository.id"), nullable=False)
    tag_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version_major: Mapped[int]
    version_minor: Mapped[int]
    version_patch: Mapped[int]
    pre_release: Mapped[str | None] = mapped_column(String(50))        # e.g. "rc.1"; NULL = stable
    customer_release: Mapped[bool] = mapped_column(Boolean, nullable=False)  # derived from tag name
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)  # tag commit date
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### `Commit`

```python
class Commit(Base):
    __tablename__ = "commit"

    sha: Mapped[str] = mapped_column(String(40), primary_key=True)
    repository_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("repository.id"), nullable=False)
    author: Mapped[str] = mapped_column(String(255))
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### `ReleaseCommit` (association table)

```python
class ReleaseCommit(Base):
    __tablename__ = "release_commit"

    release_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("release.id"), primary_key=True)
    commit_sha: Mapped[str] = mapped_column(String(40), ForeignKey("commit.sha"), primary_key=True)
```

### `MergeRequest`

```python
class MergeRequest(Base):
    __tablename__ = "merge_request"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("repository.id"), nullable=False)
    gitlab_mr_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(1024))
    description: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255))               # GitLab username
    source_branch: Mapped[str] = mapped_column(String(255))
    target_branch: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_commit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # earliest commit in MR; Lead Time start
    merged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    head_sha: Mapped[str | None] = mapped_column(String(40))              # MR branch HEAD at merge time
    merge_commit_sha: Mapped[str | None] = mapped_column(String(40))
    squash_commit_sha: Mapped[str | None] = mapped_column(String(40))
    effective_commit_sha: Mapped[str | None] = mapped_column(String(40))  # merge or squash sha
    jira_key: Mapped[str | None] = mapped_column(String(50))              # extracted from title / branch / description
    jira_key_source: Mapped[str | None] = mapped_column(String(15))       # 'title' | 'branch' | 'description' | NULL
    # Lead-time fields populated after tag matching
    first_customer_tag: Mapped[str | None] = mapped_column(String(255))
    first_customer_tag_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    release_wait_time_hours: Mapped[float | None] = mapped_column(Numeric(10, 2))   # merged_at → first_customer_tag_date
    lead_time_hours: Mapped[float | None] = mapped_column(Numeric(10, 2))            # first_commit_at → first_customer_tag_date
    lead_post_production_hours: Mapped[float | None] = mapped_column(Numeric(10, 2))  # merged_at − linked bug.ready_for_qa_at
    lead_time_match_status: Mapped[str | None] = mapped_column(String(50))  # matched | no_customer_tag_ref_found | ...
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
```

### `ProductionBug`

```python
class ProductionBug(Base):
    __tablename__ = "production_bug"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    jira_key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    summary: Mapped[str] = mapped_column(String(1024))
    issue_type: Mapped[str | None] = mapped_column(String(100))          # Bug | Bug Subtask
    status: Mapped[str | None] = mapped_column(String(100))
    priority: Mapped[str | None] = mapped_column(String(50))             # Critical | Blocker | Major | ...
    components: Mapped[list | None] = mapped_column(JSON)                # list of component names
    affects_versions: Mapped[list | None] = mapped_column(JSON)          # list of version strings
    fix_versions: Mapped[list | None] = mapped_column(JSON)              # list of version strings
    parent_key: Mapped[str | None] = mapped_column(String(50))
    parent_type: Mapped[str | None] = mapped_column(String(100))
    indicator_cf10114: Mapped[str | None] = mapped_column(Text)          # EXALATE link
    indicator_cf10123: Mapped[str | None] = mapped_column(Text)          # CUSTOMERNAME
    healthy: Mapped[bool] = mapped_column(Boolean, nullable=False)       # true = post-production
    healthmemo: Mapped[str | None] = mapped_column(String(512))          # classification reason
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mttr_minutes: Mapped[int | None]                                     # closed_at - created_at (Jira lifecycle)
    # MTTR Alpha fields — populated by cross-referencing GitLab release data
    first_fix_release_tag: Mapped[str | None] = mapped_column(String(255))       # tag name containing the fix
    first_fix_release_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    mttr_alpha_resolution_path: Mapped[str | None] = mapped_column(String(20))   # 'mr_jira_key' | 'fix_version' | NULL
    mttr_alpha_minutes: Mapped[int | None]                               # first_fix_release_date - created_at
    ready_for_qa_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # first changelog transition to configured status
    total_worklog_seconds: Mapped[int | None] = mapped_column(BigInteger)  # sum of issue_worklog.time_spent_seconds
```

### `IssueWorklog` (Jira gebuchte Zeiten, 1:n pro Bug)

```python
class IssueWorklog(Base):
    __tablename__ = "issue_worklog"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bug_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("production_bug.id"), nullable=False)
    jira_worklog_id: Mapped[str] = mapped_column(String(32), nullable=False)  # Jira worklog id (string)
    author: Mapped[str | None] = mapped_column(String(255))
    started: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    time_spent_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### `BugRelease` (association table)

```python
class BugRelease(Base):
    __tablename__ = "bug_release"

    bug_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("production_bug.id"), primary_key=True)
    release_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("release.id"), primary_key=True)
```

### `MetricSnapshot`

```python
class MetricSnapshot(Base):
    __tablename__ = "metric_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    repository_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("repository.id"))
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    period_type: Mapped[str] = mapped_column(String(10), nullable=False)  # WEEK | MONTH | QUARTER
    deployment_freq: Mapped[float | None] = mapped_column(Numeric(10, 4))
    lead_time_minutes: Mapped[int | None]                    # median (or agreed stat) first_commit → tag
    release_wait_median_minutes: Mapped[int | None] = None  # median merged_at → tag
    change_failure_rate: Mapped[float | None] = mapped_column(Numeric(5, 4))
    mttr_minutes: Mapped[int | None]                        # optional: Jira lifecycle MTTR
    mttr_alpha_minutes: Mapped[int | None] = None           # median MTTR Alpha (Critical+ subset)
    lead_post_production_median_minutes: Mapped[int | None] = None  # median ready_for_qa → merge (MR subset with data)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

`created_at` on `metric_snapshot` is the canonical persistence field behind API freshness timestamps (`generated_at`).

### `AppConfiguration` (runtime settings managed by Admin UI)

Single-row or key-value table holding **non-secret** and **encrypted secret** fields edited via **`PATCH /admin/config`**. Bootstrap uses `configuration.yml` + `.env` until first save.

```python
class AppConfiguration(Base):
    __tablename__ = "app_configuration"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)  # singleton id = 1
    settings_json: Mapped[dict] = mapped_column(JSON)  # gitlab_project_paths, target_branches, excluded_projects, cron, ...
    gitlab_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary)  # Fernet blob or NULL if env-only
    jira_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
```

**Alternative:** store only encrypted blobs in DB and keep structured YAML in `settings_json` without secrets.

### `SyncLog`

```python
class SyncLog(Base):
    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # GITLAB | JIRA
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # SUCCESS | FAILED
    records_processed: Mapped[int | None]
    error_message: Mapped[str | None] = mapped_column(Text)
```

---

## Alembic Setup

- `alembic init alembic` in the `backend/` directory
- `env.py` uses sync engine (psycopg2)
- Migration files generated via `alembic revision --autogenerate -m "description"`
- Applied on container startup via Docker entrypoint: `alembic upgrade head && uvicorn ...`

---

## Indexes

| Table | Index | Rationale |
| --- | --- | --- |
| `release` | `(repository_id, committed_at)` | Time-range queries per repo |
| `release` | `(customer_release, committed_at)` | Deployment frequency filter |
| `metric_snapshot` | `(repository_id, period_type, period_start)` | Dashboard filter queries |
| `merge_request` | `(repository_id, first_commit_at)` | Lead Time for Changes queries |
| `merge_request` | `(repository_id, merged_at)` | Release Wait Time queries |
| `merge_request` | `(repository_id, target_branch, merged_at)` | Per-branch lead time breakdown |
| `merge_request` | `(effective_commit_sha)` | Commit-to-tag matching lookup |
| `merge_request` | `(jira_key)` | MR ↔ Jira bug join |
| `production_bug` | `(created_at, closed_at)` | MTTR window queries |
| `production_bug` | `(healthy, created_at)` | CFR / health view queries |
| `production_bug` | `(healthy, priority, created_at)` | MTTR Alpha filter (Critical+ healthy bugs) |
| `issue_worklog` | `(bug_id)` | Worklog aggregation per bug |
| `sync_log` | `(source, started_at DESC)` | Latest sync status lookups |

---

## Data Retention Policy

| Data | Retention | Rationale |
| --- | --- | --- |
| Raw data (commits, MRs) | 2 years | Trend analysis and traceability |
| Releases, bugs | Unlimited | Low volume, high historical value |
| Metric snapshots | Unlimited | Compact; basis for long-term dashboards |

Retention pruning can be implemented as an additional scheduled job or a PostgreSQL cron extension.

---

## RC / Pre-Release Handling

| Metric | Pre-release Tags |
| --- | --- |
| Deployment Frequency | Excluded (`customer_release = false`) |
| Lead Time for Changes | Excluded from target tags (`customer_release = true` tags only) |
| Change Failure Rate | Excluded from release denominator |
| MTTR | Not affected (bug-based, not release-based) |

## Production Bug Health Logic

Only bugs with `healthy = true` enter CFR and MTTR calculations.

| `healthmemo` prefix | Meaning | Included in KPIs |
| --- | --- | --- |
| `post-production` | Confirmed production bug | Yes |
| `post-production due to ...` | Rescued by version / parent heuristic | Yes |
| `pre-production - parent is ...` | Internal/QA context | No |
| `pre-production due to parent` | Parent confirmed pre-production | No |
| `unhealthy - ...` | Data quality gap | No (visible in health view) |

See `jira-production-bug-filter-decision.md` for complete rule set.


