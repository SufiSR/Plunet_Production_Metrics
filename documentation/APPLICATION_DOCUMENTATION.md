# DORA Metrics Application Documentation

## 1) Purpose and Product Scope

The DORA Metrics application aggregates delivery and reliability signals from GitLab and Jira, computes standardized and custom engineering metrics, and serves them through a public dashboard plus protected admin tooling.

Primary goals:

- Provide daily-refreshed metric snapshots for leadership and teams.
- Keep freshness and sync health visible.
- Allow controlled runtime configuration without redeploying.
- Expose detailed drilldowns for traceability behind aggregate KPI values.

Current architecture:

- Backend: FastAPI + APScheduler + SQLAlchemy 2.x (sync) + PostgreSQL.
- Frontend: Next.js App Router + React + TanStack Query + Zustand + Recharts.

---

## 2) System Architecture

The application has four main layers:

1. **Collection layer**
  - Pulls releases and merge request context from GitLab.
  - Pulls production bug and issue/worklog context from Jira.
2. **Derivation layer**
  - Links bugs to releases.
  - Resolves fix release data for MTTR Alpha.
  - Hydrates MR and ticket relationships used in lead-time logic.
3. **Snapshot layer**
  - Computes weekly/monthly/quarterly metric snapshots per repository.
  - Stores derived KPI values into `metric_snapshot`.
4. **Presentation layer**
  - Public API endpoints and dashboard views for metrics.
  - Admin API + admin UI for configuration and operations.

---

## 3) Data Model

Core tables/entities:

- `app_configuration`: runtime configuration and encrypted secrets.
- `repository`: tracked repositories/projects.
- `release`: GitLab release and tag data.
- `merge_request`: merge request metadata used in lead-time and release analysis.
- `production_bug`: Jira production incident issues.
- `issue_worklog`: Jira worklog records used for comparative/auxiliary analytics.
- `bug_release`: many-to-many link between bugs and releases.
- `metric_snapshot`: computed KPI values for a period and repository.
- `sync_log`: audit trail for collectors, full nightly runs, and runtime phases.

Design characteristics:

- Idempotent upsert approach for collector persistence.
- Indexed query paths for metrics and timeline workloads.
- Snapshot overwrite semantics by `(repository_id, period_type, period_start)`.

---

## 4) Configuration and Secret Handling

Configuration precedence (lowest to highest):

1. Schema defaults
2. `configuration.yml`
3. Database overrides (`app_configuration.settings_json`)
4. Environment variable overrides

Secrets:

- GitLab and Jira tokens can come from environment variables or encrypted DB fields.
- Encrypted values are masked in API responses; raw secrets are never returned.

Admin config behavior:

- Config patch persists changes.
- Scheduler is rescheduled when cron values change.
- Webhook test endpoint sends a verification payload without waiting for nightly sync.

---

## 5) Authentication and RBAC

Session model:

- Cookie-based admin session (`dora_session`).
- Login validates against configured admin credentials.
- Logout clears session.

RBAC boundary:

- Public routes (dashboard/metrics/repository/sync-status/health) are unauthenticated.
- Admin routes require active admin session.
- Frontend middleware protects `/admin` routes (except `/admin/login`) for UX.
- Backend dependency checks remain the source of truth for authorization.

---

## 6) Nightly Pipeline and Sync Lifecycle

The nightly orchestration coordinates collectors and derivations with explicit phase tracking.

Standard high-level order:

1. GitLab release/tag and MR synchronization.
2. Jira production bug synchronization.
3. Derivation/linking steps:
  - Bug-release mapping
  - MTTR Alpha release resolution
  - Ready-for-QA hydration for lead-time context
  - Post-production lead-time derivation support
4. Snapshot generation (when allowed by pipeline state).
5. Sync finalization and webhook notification.

Failure and partial behavior:

- GitLab and Jira collectors are fault-isolated.
- One collector failure does not automatically block the other.
- Derivations require both collector domains to be sufficiently available.
- Snapshots are skipped when derivation consistency cannot be guaranteed.
- `sync_log` stores runtime status, timings, errors, and phase transitions.

Freshness semantics:

- Dashboard status and banners derive from latest sync status and timestamp.
- Stale conditions surface when no healthy recent sync exists.

---

## 7) Metric Semantics

The application computes DORA and extended indicators from collected and linked data.

Primary dashboard metrics:

1. **Deployment Frequency**
  - Rate of customer-impacting release events in the selected period.
2. **Median Lead Time**
  - End-to-end delivery latency from development events to customer release, with additional breakdown support (for example dev/review versus release wait components).
3. **Change Failure Rate (CFR)**
  - Ratio/percentage of changes/releases associated with production issues under configured classification rules.
4. **MTTR Alpha**
  - Repair/restoration duration metric based on incident-to-fix-release semantics and configured incident filters.

Additional metric and drilldown capabilities:

- Release timeline and customer release drilldowns.
- Failed release issue drilldowns.
- MTTR Alpha summary/incidents/releases drilldowns.
- Lead-time diagnostics and sampled composition fields.

Important metric controls:

- Branch targeting and additional merge branches are configurable.
- Pre-release marker exclusions are configurable.
- Jira production bug classification fields are configurable.
- QA status filters and related lead-time boundaries are configurable.

---

## 8) Backend API Surface

Base routing is mounted under `/api`.

### Auth endpoints

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

### Public metrics endpoints

- `GET /api/metrics/current`
- `GET /api/metrics/history`
- `GET /api/metrics/repository/{repository_id}`
- `GET /api/metrics/releases/timeline`
- `GET /api/metrics/releases/customer/drilldown`
- `GET /api/metrics/releases/customer/merge-requests`
- `GET /api/metrics/releases/customer/failed-drilldown`
- `GET /api/metrics/releases/customer/failed/issues`
- `GET /api/metrics/bugs/mttr-alpha/summary`
- `GET /api/metrics/bugs/mttr-alpha/incidents`
- `GET /api/metrics/bugs/mttr-alpha/releases`

### Public repository/sync/health endpoints

- `GET /api/repositories`
- `GET /api/sync/status`
- `GET /api/health`

### Admin endpoints

- `GET /api/admin/config`
- `PATCH /api/admin/config`
- `POST /api/admin/config/webhook/test`
- `POST /api/admin/sync/trigger`
- `GET /api/admin/data-health`
- `GET /api/admin/raw-tables/{table_name}`

API principles:

- Input validation through typed schemas/models.
- Additive response evolution where possible.
- Sensitive values masked before transmission.

---

## 9) Frontend Application Behavior

Main routes:

- `/`: primary dashboard experience.
- `/embed`: compact iframe-friendly dashboard.
- `/admin/login`: admin authentication.
- `/admin/config`: runtime configuration and operations.
- `/admin/data-health`: data quality and data-state inspection.
- `/admin/raw-tables`: table-level inspection utilities.

Dashboard UX:

- Metric cards with formatted KPI values and trend indicators.
- Trend chart section with metric-aware visualization modes.
- Modal and drilldown components for deeper analysis.
- Stale/failure banners and sync-status indicators.

State and data strategy:

- TanStack Query for server-state caching and refetching.
- Explicit query keys and API client normalization.
- Zustand for local/global UI selection state.
- Long default staleness window aligned to daily sync cadence.

Frontend API clients:

- Public client for dashboard metrics/repository/sync reads.
- Admin client with credentialed requests for auth/config/ops routes.

---

## 10) Admin Features (Detailed)

Admin UI supports operation and governance of runtime behavior:

1. **Authentication**
  - Login/logout and current-session checks.
2. **Configuration Management**
  - GitLab settings: host/token/projects/branch patterns/release filtering.
  - Jira settings: host/credentials/project and classification controls.
  - Scheduler settings: cron hour/minute and lookback scope.
  - Webhook settings and send-test action.
3. **Manual Operations**
  - Trigger sync pipeline manually.
  - Observe near-real-time phase/status progress from sync status data.
4. **Data Observability**
  - Data-health views for ingestion integrity and consistency checks.
  - Raw table explorer for controlled, admin-only data inspection.
5. **Editor UX safeguards**
  - Unsaved change tracking.
  - Draft patching with save/discard flows.

---

## 11) Reliability, Error Handling, and Observability

Reliability model:

- Collector-level retry/backoff for retryable transport/API failures.
- Partial-failure tolerance between source systems.
- Recovery handling for stale in-progress sync records on restart.

Observability:

- Structured logs for collectors and sync orchestration.
- Rich `sync_log` records for status, duration, phase outcomes, and error details.
- Webhook notifications for successful, partial, failed, and test events.

Operational intent:

- Keep system state explainable without digging through raw logs only.
- Make freshness and pipeline health visible in both API and UI.

---

## 12) Testing and Quality Coverage

Backend test shape:

- Unit tests for services, collectors, scheduler behavior, and metric logic.
- Integration tests on PostgreSQL-backed flows and auth/public API behavior.
- Migration-related validation for schema evolution.

Frontend test shape:

- Unit tests for API client normalization and utility logic.
- Component/page tests for admin features and selected UI components.
- Jest + jsdom based setup.

Known strategic test improvements:

- Broader dashboard interaction and drilldown scenario coverage.
- Middleware-specific frontend auth path tests.
- Additional end-to-end style checks for sync polling and status transitions.

---

## 13) Deployment and Runtime Notes

Runtime expectations:

- PostgreSQL connectivity and migrations available.
- Scheduler runs in application process with configured cron.
- Environment variables support secret/config overrides.

Containerization/orchestration:

- Repository includes Docker compose and env examples for local/runtime setups.

Security and compliance considerations:

- Do not commit credentials or token values.
- Keep session secret strong and private.
- Preserve RBAC boundary between public and admin capabilities.

---

## 14) Legacy Documentation Positioning

`project_definition_2/` remains useful as historical/product context, especially for KPI intent and backlog rationale, but implementation has evolved.

This `documentation/` folder is now intended as the current implementation reference.

For exhaustive implementation-level details of mapping and calculation logic, see:

- `documentation/PIPELINE_AND_METRICS_DEEP_DIVE.md`

Recommended maintenance process:

- Update these docs when endpoint contracts, metric semantics, pipeline ordering, or admin behavior changes.
- Keep docs changes in the same PR as behavior changes whenever feasible.