# API Specification – Documentation

## Base URL

```
http://{host}:{port}/api
```

FastAPI automatically generates interactive docs at `/docs` (Swagger UI) and `/redoc`.

---

## Data freshness (daily pipeline)

All metric endpoints return values computed from `**metric_snapshot**` (and raw tables) that were last written by `**run_nightly_sync**`. The application **guarantees a full refresh path once per day** by default (scheduled **02:00**, configurable — see `backend-components-documentation.md`).


| Field / concept                      | Meaning                                                                                                                            |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
| `generated_at` (on metric responses) | UTC timestamp when the snapshot row backing this response was produced (end of snapshot step).                                     |
| `GET /sync/status`                   | Last run **start** / **finish**, per-collector status, snapshot count, **next scheduled** run.                                     |
| Stale data                           | If the sync job failed all night, `generated_at` is unchanged; the UI should surface `**SYNC_COMPLETE_FAILURE`** from sync status. |


Phase 1 may map `**mttr`** in the public API to **MTTR Alpha** (minutes) for the primary card, or expose both **lifecycle MTTR** and **MTTR Alpha** as separate optional `MetricValue` fields — see `CurrentMetricsResponse` below.

---

## Endpoints Overview

### Public (no authentication)


| Method | Path                       | Description                              | Paginated |
| ------ | -------------------------- | ---------------------------------------- | --------- |
| GET    | `/metrics/current`         | Current aggregated metrics + DORA levels | No        |
| GET    | `/metrics/history`         | Historical time series + DORA levels     | Yes       |
| GET    | `/metrics/repository/{id}` | Repository-specific current metrics      | No        |
| GET    | `/repositories`            | List of monitored repositories           | No        |
| GET    | `/sync/status`             | Status of last synchronization           | No        |
| GET    | `/metrics/releases/worklog-hours` | Aggregate worklog hours for bugs linked to tag (`repository_id`,`tag_name`); by role & team | No        |
| GET    | `/health`                  | Health check                             | No        |


### Admin (authentication required)


| Method | Path            | Description                                                                                               |
| ------ | --------------- | --------------------------------------------------------------------------------------------------------- |
| POST   | `/auth/login`   | Admin login; sets session cookie or returns JWT                                                           |
| POST   | `/auth/logout`  | Invalidate session / clear cookie                                                                         |
| GET    | `/auth/me`      | Current principal (`role`: `viewer` is unauthenticated default when not used; `admin` when session valid) |
| GET    | `/admin/config` | Full effective config for forms; **secrets masked**                                                       |
| PATCH  | `/admin/config` | Partial update of GitLab/Jira/scheduler settings; new tokens replace stored secrets; optionally `jira_worklog_user_assignments` and `jira_worklog_author_denylist` (see below)                       |
| GET    | `/admin/jira/worklog-authors` | Distinct worklog authors from `issue_worklog` excluding denylisted Jira account IDs (paginated)          |


**Rules:** `GET/PATCH /admin/config` and `POST /auth/logout` require a valid **Admin** session. Unauthenticated requests receive **401 Unauthorized**. Viewers never call these routes from the main dashboard.

### Jira worklog assignment settings (persisted in `AppConfiguration.settings_json`)

These keys live under **`jira`** in `settings_json` (not necessarily mirrored in YAML env defaults):

| Key | Shape | Purpose |
| --- | ----- | ------- |
| `jira_worklog_user_assignments` | Array of `{ "jira_account_id": string, "role": "pm" \| "dev" \| "qa", "team": string }`; **unique `jira_account_id`** per array | Maps Jira authors to department role and team for aggregations. |
| `jira_worklog_author_denylist` | Array of Jira **`accountId`** strings (exact match) | Service/automation authors: omitted from **`GET /admin/jira/worklog-authors`** and **excluded entirely** from **`GET /metrics/releases/worklog-hours`** totals when `jira_account_id` matches. |

Semantics: aggregates include **all** worklog seconds on bugs linked via `BugRelease` to the tag (no calendar window). If one bug maps to **multiple** releases, each tag view includes **full** worklog on that bug (expected double-count **across** tags).

---

## Pydantic Schemas

### Shared Types

```python
from enum import Enum

class Trend(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    STABLE = "STABLE"

class PerformanceLevel(str, Enum):
    ELITE = "ELITE"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class PeriodType(str, Enum):
    WEEK = "WEEK"
    MONTH = "MONTH"
    QUARTER = "QUARTER"

class SyncStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"
    FAILED = "FAILED"

class UserRole(str, Enum):
    ADMIN = "admin"
```

### Authentication (Admin)

```python
class LoginRequest(BaseModel):
    username: str  # or email; single admin user acceptable for v1
    password: str

class LoginResponse(BaseModel):
    role: UserRole
    expires_at: datetime | None = None

class MeResponse(BaseModel):
    role: UserRole | None  # None when unauthenticated
    username: str | None = None
```

### `AdminConfigResponse` (excerpt)

Structured mirror of `configuration.yml` + secrets metadata. **Never** return raw PAT/API tokens; use `secret_hint: str | None` (e.g. `glpat-****…last4`).

```python
class AdminConfigResponse(BaseModel):
    gitlab_url: str
    gitlab_token_hint: str | None  # masked
    gitlab_project_paths: list[str]
    target_branches: list[str]
    non_customer_release_markers: list[str]
    jira_url: str
    jira_username: str
    jira_token_hint: str | None
    excluded_projects: list[str]
    sync_cron_hour: int
    sync_cron_minute: int
    # ... remaining keys from configuration.yml
```

`PATCH` body: same fields optional; omit a secret field to leave unchanged; send new value to rotate token.

### `MetricValue`

```python
class MetricValue(BaseModel):
    value: float | None
    unit: str
    display_value: str | None = None
    trend: Trend | None = None
    trend_percentage: float | None = None
    performance_level: PerformanceLevel | None = None
```

### `CurrentMetricsResponse`

```python
class CurrentMetricsResponse(BaseModel):
    deployment_frequency: MetricValue
    lead_time: MetricValue
    change_failure_rate: MetricValue
    mttr: MetricValue  # Primary card: recommend MTTR Alpha (Critical/Blocker) once implemented
    overall_performance_level: PerformanceLevel | None
    period_start: date
    period_end: date
    repository_count: int
    generated_at: datetime
    # Extended (optional; omit or null until dashboard panels exist)
    mttr_alpha: MetricValue | None = None
    release_wait_time: MetricValue | None = None
```

### `HistoryDataPoint`

```python
class PerformanceLevels(BaseModel):
    overall: PerformanceLevel | None
    deployment_frequency: PerformanceLevel | None
    lead_time: PerformanceLevel | None
    change_failure_rate: PerformanceLevel | None
    mttr: PerformanceLevel | None

class HistoryDataPoint(BaseModel):
    period_start: date
    period_end: date
    deployment_frequency: float | None
    lead_time_minutes: int | None
    change_failure_rate: float | None
    mttr_minutes: int | None
    mttr_alpha_minutes: int | None = None
    release_wait_median_minutes: int | None = None
    performance_level: PerformanceLevels
```

### `HistoryResponse`

```python
class Pagination(BaseModel):
    page: int
    size: int
    total_elements: int
    total_pages: int
    has_next: bool
    has_previous: bool

class HistoryResponse(BaseModel):
    period_type: PeriodType
    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")
    repository_id: int | None
    data: list[HistoryDataPoint]
    pagination: Pagination
```

### `RepositoryResponse`

```python
class RepositoryItem(BaseModel):
    id: int
    gitlab_id: int
    name: str
    path: str
    default_branch: str
    active: bool

class RepositoriesResponse(BaseModel):
    repositories: list[RepositoryItem]
    total: int
```

---

## GET /metrics/current

Returns current DORA metrics aggregated across all repositories (latest completed period).

**Response 200** – `CurrentMetricsResponse`

```json
{
  "deployment_frequency": {
    "value": 4.2,
    "unit": "DEPLOYMENTS_PER_WEEK",
    "trend": "UP",
    "trend_percentage": 12.5,
    "performance_level": "HIGH"
  },
  "lead_time": {
    "value": 2880,
    "unit": "MINUTES",
    "display_value": "2 days",
    "trend": "DOWN",
    "trend_percentage": -8.3,
    "performance_level": "MEDIUM"
  },
  "change_failure_rate": {
    "value": 0.12,
    "unit": "RATIO",
    "display_value": "12%",
    "trend": "STABLE",
    "trend_percentage": 0.5,
    "performance_level": "HIGH"
  },
  "mttr": {
    "value": 480,
    "unit": "MINUTES",
    "display_value": "8 hours",
    "trend": "DOWN",
    "trend_percentage": -15.2,
    "performance_level": "HIGH"
  },
  "overall_performance_level": "MEDIUM",
  "period_start": "2025-01-06",
  "period_end": "2025-01-12",
  "repository_count": 26,
  "generated_at": "2025-01-13T02:15:00Z",
  "mttr_alpha": {
    "value": 360,
    "unit": "MINUTES",
    "display_value": "6 hours",
    "trend": "DOWN",
    "performance_level": "HIGH"
  },
  "release_wait_time": {
    "value": 720,
    "unit": "MINUTES",
    "display_value": "12 hours",
    "trend": "STABLE",
    "performance_level": "MEDIUM"
  }
}
```

`mttr_alpha` and `release_wait_time` may be `null` until the snapshot schema and UI panels ship.

---

## GET /metrics/history

Returns historical time series of metrics.

**Query Parameters**


| Parameter       | Type    | Required | Default      | Description                   |
| --------------- | ------- | -------- | ------------ | ----------------------------- |
| `period_type`   | string  | No       | `WEEK`       | `WEEK`, `MONTH`, or `QUARTER` |
| `from`          | date    | No       | 12 weeks ago | Start date (ISO 8601)         |
| `to`            | date    | No       | today        | End date (ISO 8601)           |
| `repository_id` | integer | No       | null         | Filter by repository          |
| `page`          | integer | No       | 0            | Zero-based page number        |
| `size`          | integer | No       | 20           | Page size (max 100)           |


**Request Example**

```
GET /api/metrics/history?period_type=WEEK&from=2024-01-01&to=2025-01-15&page=0&size=20
```

**Response 200** – `HistoryResponse`

---

## GET /metrics/repository/{id}

Returns current metrics for a specific repository.

**Path Parameters**


| Parameter | Type    | Description            |
| --------- | ------- | ---------------------- |
| `id`      | integer | Internal repository ID |


**Response 200** – `CurrentMetricsResponse` (scoped to one repository)

**Response 404**

```json
{ "error": "NOT_FOUND", "message": "Repository with id 42 not found", "timestamp": "..." }
```

---

## GET /repositories

Returns all monitored repositories.

**Query Parameters**


| Parameter | Type    | Required | Default | Description             |
| --------- | ------- | -------- | ------- | ----------------------- |
| `active`  | boolean | No       | `true`  | Filter by active status |


**Response 200** – `RepositoriesResponse`

---

## GET /sync/status

Returns status of the most recent synchronization run **and** the next scheduled **daily** run. Clients use this to show whether metrics are up to date (last successful pipeline).

**Response 200**

```json
{
  "last_sync": {
    "started_at": "2025-01-13T02:00:00Z",
    "finished_at": "2025-01-13T02:15:00Z",
    "duration_seconds": 900,
    "status": "SUCCESS",
    "collectors": {
      "gitlab": {
        "status": "SUCCESS",
        "records_processed": {
          "repositories": 26,
          "releases": 12,
          "merge_requests": 1425,
          "merge_requests_first_commit_enriched": 1425
        }
      },
      "jira": {
        "status": "SUCCESS",
        "records_processed": { "bugs": 1456, "mttr_alpha_resolved": 42 }
      }
    },
    "snapshots_generated": 54,
    "snapshot_generated_at": "2025-01-13T02:14:30Z"
  },
  "last_successful_sync_at": "2025-01-13T02:15:00Z",
  "next_scheduled_sync": "2025-01-14T02:00:00Z",
  "sync_schedule_cron": "0 2 * * *"
}
```


| Field                     | Description                                                                                           |
| ------------------------- | ----------------------------------------------------------------------------------------------------- |
| `last_successful_sync_at` | Convenience copy of `last_sync.finished_at` when `status` is success or partial with usable snapshots |
| `snapshot_generated_at`   | When `metric_snapshot` writes for this run completed                                                  |
| `sync_schedule_cron`      | Human/debug hint; authoritative schedule is server config                                             |


---

## GET /health

Health check endpoint.

**Response 200**

```json
{
  "status": "UP",
  "components": {
    "database": { "status": "UP" },
    "gitlab": { "status": "UP", "last_successful_connection": "2025-01-13T02:00:00Z" },
    "jira": { "status": "UP", "last_successful_connection": "2025-01-13T02:10:00Z" }
  }
}
```

**Response 503** – same shape with `"status": "DOWN"` and per-component errors.

---

## Error Format

All error responses share a consistent Pydantic model:

```python
class ErrorResponse(BaseModel):
    error: str
    message: str
    timestamp: datetime
```


| Status Code | `error` value    | When                                                        |
| ----------- | ---------------- | ----------------------------------------------------------- |
| 400         | `BAD_REQUEST`    | Invalid query parameters                                    |
| 401         | `UNAUTHORIZED`   | Missing or invalid session (admin routes)                   |
| 403         | `FORBIDDEN`      | Authenticated but not Admin (if multiple roles exist later) |
| 404         | `NOT_FOUND`      | Resource does not exist                                     |
| 500         | `INTERNAL_ERROR` | Unexpected server error                                     |


FastAPI exception handlers are registered in `main.py` to convert `ValueError`, `RequestValidationError`, and unhandled exceptions to this format.

---

## CORS Configuration

Since the Next.js frontend may be served from a different origin (or embedded in Confluence), CORS is configured explicitly. **Public** routes allow anonymous `GET`. **Admin** login and config use `**POST`/`PATCH`** and may send **cookies** or `**Authorization`** headers.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dashboard.internal.example", "https://confluence.example.com"],  # explicit list in production
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,   # required if session cookie is used cross-origin; align origins strictly
)
```

- **Confluence iframe + cookie auth:** Prefer **same-site** deployment (dashboard hostname trusted) or **JWT in `Authorization`** from the Admin SPA to avoid third-party cookie issues.
- **Phase 1 dev:** `allow_origins=["*"]` with `allow_credentials=False` is acceptable **only** without cookies; use Bearer token for Admin in that mode.

---

## DORA Performance Level Classification


| Level  | Deployment Frequency | Lead Time        | Change Failure Rate | MTTR           |
| ------ | -------------------- | ---------------- | ------------------- | -------------- |
| ELITE  | Multiple per day     | < 1 hour         | < 5%                | < 1 hour       |
| HIGH   | Daily to weekly      | 1 day – 1 week   | 5% – 10%            | < 1 day        |
| MEDIUM | Weekly to monthly    | 1 week – 1 month | 10% – 15%           | 1 day – 1 week |
| LOW    | Monthly or slower    | > 1 month        | > 15%               | > 1 week       |


Overall level = lowest individual level across all four metrics.