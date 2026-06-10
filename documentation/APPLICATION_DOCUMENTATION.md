# Engineering Analytics Platform Documentation

## 1) Purpose and Current Scope

The application is now an internal engineering analytics platform, not only a DORA metrics server. It combines GitLab, Jira, and HRWorks data to provide delivery, investment, workflow, team-capacity, customer-effort, and data-quality reporting.

Primary goals:

- Give leadership and teams a reliable command center for engineering delivery health.
- Preserve the original DORA reporting while adding Jira Analytics and HRWorks capacity context.
- Make analytics explainable through drilldowns, raw records, sync logs, and data-quality warnings.
- Allow admins to configure credentials, schedules, assignments, and feature families without redeploying.

Current architecture:

- Backend: FastAPI, SQLAlchemy 2.x, Alembic, APScheduler, PostgreSQL, httpx.
- Frontend: Next.js App Router, React, TypeScript, TanStack Query, Zustand, Recharts, Tailwind CSS.
- Storage: PostgreSQL with core DORA tables plus a Jira Analytics warehouse.

## 2) Product Areas

### DORA Analytics

DORA remains available as a first-class module:

- Deployment frequency.
- Median lead time from commit/MR context to customer release.
- Change failure rate based on production-bug-to-release linkage.
- MTTR Alpha based on high-priority production issue creation to first fix release.
- Release timeline, customer-release drilldowns, failed-release issue lists, MTTR Alpha incident/release drilldowns, and release worklog hours.

### Jira Analytics

Jira Analytics is the larger reporting layer built from Jira issues, fields, worklogs, sprints, relationships, feature memberships, workflow transitions, workflow classifications, and allocation outputs.

Report families:

- Portfolio investment: investment categories, feature ranking, feature investment audit, investment by theme.
- Features: feature worklog hours, feature-family hours, issues without feature, feature delivery risk.
- Flow: lifecycle funnel, promised vs actual, idea aging, size vs speed, roadmap reliability.
- Bottlenecks: status waiting time, active vs passive time, active/passive trend, workflow thrashing.
- Teams: allocation heatmap, roadmap focus, capacity utilization, capacity forecast, interruption ratio, throughput stability, bus factor, engineering health, team comparison.
- Customers: customer-specific effort.
- Quality: data-quality dashboard and user-level drilldowns.

### HRWorks Capacity

HRWorks ingestion provides person roster and monthly availability/forecast data. Jira Analytics uses this to compare booked Jira work with real team availability and forward-looking capacity.

### Admin Console

The current admin console covers:

- Sync status for all pipelines.
- Manual ingestion triggers for DORA, Jira Analytics, and HRWorks.
- Scheduler settings for all scheduled jobs.
- Secrets and credentials.
- Jira user/team/role assignment management.
- Feature-family administration and suggestions.
- DORA linkage health and raw table inspection.

Legacy admin screens remain under `/admin_legacy` while current admin operations live under `/admin`.

## 3) System Architecture

The application has five main layers:

1. **Source collection**
   - GitLab releases, tags, merge requests, commits, and tag refs.
   - Jira production bugs for DORA.
   - Jira warehouse entities for analytics: projects, issues, details, field values, worklogs, sprints, transitions, relationships, users, workflows, and classifications.
   - HRWorks person roster and monthly availability.
2. **Normalization and derivation**
   - DORA bug-release links, MR-to-release links, lead-time components, MTTR Alpha fix-release resolution.
   - Jira feature membership, feature-family grouping, topic classification, workflow normalization, waiting/active/passive classification, thrash detection.
   - User/team/role assignment and HRWorks person mapping.
3. **Allocation and aggregation**
   - Monthly allocated effort and monthly topic effort bases.
   - Feature, family, team, customer, workflow, and portfolio rollups.
   - DORA metric snapshots.
4. **API layer**
   - Public analytics APIs for dashboards.
   - Admin APIs protected by session auth.
5. **Presentation layer**
   - Public dashboard and embed view.
   - Analytics command center and report library.
   - Admin console for operations and governance.

## 4) Data Model Overview

Core DORA tables/entities:

- `app_configuration`: runtime configuration and encrypted secrets.
- `repository`: tracked GitLab repositories/projects.
- `release`: GitLab tag/release data.
- `merge_request`: MR metadata, Jira key extraction, first customer release mapping, lead-time fields.
- `production_bug`: Jira production incident/bug records and MTTR fields.
- `issue_worklog`: DORA-side worklog records.
- `bug_release`: production-bug to release links.
- `metric_snapshot`: precomputed DORA KPI snapshots by repository and period.
- `sync_log`: status and details for DORA, Jira Analytics, HRWorks, and rebuild operations.

Jira Analytics tables/entities include:

- `jira_project`, `jira_issue`, `jira_issue_detail`, `jira_issue_field_value`.
- `jira_worklog`, `jira_sprint`, `jira_issue_sprint`, `jira_issue_relation`.
- `jira_issue_status_transition`, `jira_workflow`, `jira_project_workflow_mapping`, `workflow_status_classification`.
- `jira_user`, `jira_user_role_assignment`, `allocation_role_rule`.
- `jira_feature_root`, `jira_feature_membership`, `jira_feature_family`, `jira_feature_family_member`, `jira_feature_family_suggestion_decision`.
- `hrworks_person_roster`, `jira_user_monthly_hrworks_hours`.
- `monthly_allocated_effort`, `monthly_topic_effort_base`.
- `jira_data_quality_user_ignore`.

Design characteristics:

- Collectors are written to be idempotent through upsert-style persistence.
- Derived data can be rebuilt after source syncs.
- Admin-facing raw table access is controlled and read-only.
- Data-quality checks are part of the product surface, not a hidden maintenance task.

## 5) Configuration and Secret Handling

Configuration precedence, from lowest to highest:

1. Schema defaults in `backend/app/config_schema.py`.
2. `configuration.yml`.
3. Database overrides in `app_configuration.settings_json`.
4. Environment variable overrides.

Configuration domains:

- `backend`: host, port, log level, DORA sync schedule, DORA lookback.
- `gitlab`: host, project paths, release branch settings, non-customer release markers, lead-time exclusions.
- `jira`: host, excluded projects, Ready for QA statuses, production-bug indicator fields, MTTR Alpha priorities.
- `jira_analytics`: analytics sync schedule and scheduled lookback.
- `hrworks`: API URL, weekly sync schedule, backfill and incremental windows, roster refresh, denied person IDs.
- `notifications`: webhook URL.

Secrets:

- GitLab, Jira, HRWorks, admin credentials, session secret, and database credentials must not be committed.
- API responses mask encrypted or sensitive values.
- Local `.env` files are runtime inputs only.

## 6) Authentication and RBAC

Session model:

- Cookie-based admin session.
- Login validates configured admin credentials.
- Logout clears the session.
- Cookie-based people-data session for individual-level analytics drilldowns.
- Admins manage people-data viewer accounts from the admin UI; viewers can change their own people-data password after sign-in.

RBAC boundary:

- Public analytics routes and health/status endpoints are readable without admin auth.
- Public analytics responses must redact person names and per-person hours unless the session has people-data access.
- People-data access is granted by either an active admin session or an active people-data user session.
- Admin routes require an active admin session.
- Frontend middleware protects admin UX routes.
- Backend dependencies are the authorization source of truth.
- Feature Audit Report remains explicitly excluded from people-data redaction.

## 7) Scheduled Jobs and Sync Lifecycle

The scheduler runs in the backend process with UTC cron triggers:

- `nightly_sync`: DORA pipeline from `backend.sync_cron_hour` and `backend.sync_cron_minute`.
- `jira_analytics_sync`: Jira Analytics warehouse sync from `jira_analytics.sync_cron_hour` and `jira_analytics.sync_cron_minute`.
- `hrworks_weekly_sync`: HRWorks incremental sync from `hrworks.sync_cron_day_of_week`, `hrworks.sync_cron_hour`, and `hrworks.sync_cron_minute`.

Manual triggers are available from admin APIs and admin UI pages.

Sync state is tracked in `sync_log`; long-running pipelines expose latest status, timings, records processed, errors, and details JSON. The frontend uses this state for live progress and operational status cards.

## 8) Backend API Surface

Base routing is mounted under `/api`.

### Auth

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`

### Public DORA Metrics

- `GET /api/metrics/current`
- `GET /api/metrics/history`
- `GET /api/metrics/repository/{repository_id}`
- `GET /api/metrics/releases/timeline`
- `GET /api/metrics/releases/worklog-hours`
- `GET /api/metrics/releases/customer/drilldown`
- `GET /api/metrics/releases/customer/merge-requests`
- `GET /api/metrics/releases/customer/failed-drilldown`
- `GET /api/metrics/releases/customer/failed/issues`
- `GET /api/metrics/bugs/mttr-alpha/summary`
- `GET /api/metrics/bugs/mttr-alpha/incidents`
- `GET /api/metrics/bugs/mttr-alpha/releases`

### Public Analytics and Status

- `GET /api/jira-analytics/feature-hours/matrix`
- `GET /api/jira-analytics/feature-hours/{row_id}/drilldown`
- `GET /api/jira-analytics/feature-families/matrix`
- `GET /api/jira-analytics/feature-families/{family_id}/drilldown`
- `GET /api/jira-analytics/data-quality`
- `GET /api/jira-analytics/data-quality/checks/{check_id}/users`
- `GET /api/jira-analytics/drilldown/topics`
- `GET /api/jira-analytics/drilldown/issues`
- `GET /api/jira-analytics/drilldown/people-worklogs`
- `GET /api/jira-analytics/allocation/explain`
- Report endpoints under `/api/jira-analytics/capacity/*`, `/features/*`, `/issues/*`, `/work-allocation/*`, `/teams/*`, `/workflow/*`, `/customers/*`, `/product/*`, `/risks/*`, `/executive/*`, `/release/*`, and `/quality/*`.
- `GET /api/repositories`
- `GET /api/sync/status`
- `GET /api/health`

### Admin

- `GET /api/admin/config`
- `PATCH /api/admin/config`
- `POST /api/admin/config/webhook/test`
- `POST /api/admin/sync/trigger`
- `GET /api/admin/data-health`
- `GET /api/admin/raw-tables/{table_name}`
- `POST /api/admin/jira-analytics/sync/trigger`
- `GET /api/admin/jira-analytics/sync/latest`
- `POST /api/admin/jira-analytics/rebuild-allocation`
- `GET /api/admin/jira-analytics/rebuild-allocation/status`
- `POST /api/admin/hrworks/sync/trigger`
- `GET /api/admin/hrworks/sync/latest`
- `GET /api/admin/jira-users`
- `PATCH /api/admin/jira-users/{user_id}`
- `GET /api/admin/jira-users/allocation-role-rules`
- `GET/POST/PATCH /api/admin/jira-feature-families*`

## 9) Frontend Routes

Main public routes:

- `/`: DORA-oriented landing/dashboard.
- `/embed`: iframe-friendly dashboard.
- `/analytics`: analytics command center.
- `/analytics/dora/*`: DORA report pages.
- `/analytics/investment/*`: portfolio investment reports.
- `/analytics/features/*`: feature and feature-family analytics.
- `/analytics/flow/*`: feature flow and roadmap reliability.
- `/analytics/bottlenecks/*`: workflow waiting, passive time, and thrashing.
- `/analytics/teams/*`: team execution, capacity, health, and comparison.
- `/analytics/customers/effort`: customer effort.
- `/analytics/data-quality`: analytics data quality.

Admin routes:

- `/admin/login`
- `/admin`
- `/admin/ingestion/dora`
- `/admin/ingestion/jira-analytics`
- `/admin/ingestion/hrworks`
- `/admin/schedulers`
- `/admin/secrets`
- `/admin/jira-analytics/assignments`
- `/admin/jira-analytics/feature-families`
- `/admin/dora/linkage-health`
- `/admin/dora/raw-tables`

Legacy admin:

- `/admin_legacy/*`

## 10) Reporting Semantics

DORA metric semantics are detailed in `PIPELINE_AND_METRICS_DEEP_DIVE.md`.

Jira Analytics reports generally derive from:

- Jira worklogs for effort.
- Jira issue hierarchy, feature fields, feature memberships, and feature families for product/feature attribution.
- User assignments and allocation rules for team/role attribution.
- HRWorks availability for capacity comparison.
- Status transitions and workflow classification for waiting, active/passive, lifecycle, and thrashing reports.
- Data-quality checks for trust warnings and missing mapping visibility.

Reports should expose enough drilldown context for users to trace aggregate values back to issues, topics, people, worklogs, months, or workflow states.

## 11) Reliability, Error Handling, and Observability

Reliability model:

- Pipeline-level sync logs record status, duration, records processed, error messages, and structured details.
- Scheduled jobs use `max_instances=1` and `coalesce=True` to avoid overlapping runs.
- DORA derivations intentionally gate snapshot refreshes when required source/derivation consistency is not available.
- Jira Analytics allocation and derived report bases can be rebuilt.

Observability surfaces:

- Admin overview status cards.
- Ingestion-specific progress pages.
- Public sync status for DORA dashboard freshness.
- Data-health and data-quality pages.
- Raw table explorer for admin diagnostics.

## 12) Testing and Quality Coverage

Backend coverage includes:

- Services, collectors, schedulers, config, sync status, data health, migrations, DORA metrics, Jira Analytics allocation/reports/data quality/workflow, HRWorks ingestion, and admin APIs.

Frontend coverage includes:

- Admin pages and API client behavior.
- Analytics pages/components such as shell, period selector, sorting, normalized cost, embed styling, and data-quality views.

Recommended validation:

- Run focused backend tests for touched services/APIs.
- Run focused frontend tests for touched pages/components.
- Run `pytest` and frontend `npm run typecheck` / `npm test` before publishing a new baseline.

## 13) Deployment and Runtime Notes

Runtime expectations:

- PostgreSQL is available and migrations have been applied.
- Backend has access to runtime config and required secrets.
- Scheduler runs in exactly one backend process for production-style deployment.
- Frontend can reach backend through `NEXT_PUBLIC_API_URL` or the Next.js rewrite setup.

Containerization:

- `docker-compose.yml` starts PostgreSQL, backend, and frontend.
- Caddy or another reverse proxy may provide TLS and public routing.

Security:

- Do not commit credentials or local `.env` files.
- Use strong admin and session secrets.
- Treat raw table and admin routes as privileged operational surfaces.

## 14) Documentation Positioning

This `documentation/` folder is the current implementation reference.

`project_definition_2/` is historical planning context. Some KPI ideas and domain rationale remain useful, but its implementation details should not be treated as authoritative for current code.

Update this documentation whenever endpoint contracts, metric semantics, pipeline ordering, source mappings, admin behavior, or report categories change.
