# Engineering Analytics Platform

This repository contains an internal engineering analytics platform for delivery performance, portfolio investment, workflow bottlenecks, team capacity, and data quality. The original DORA dashboard is now one module inside a larger application that combines data from GitLab, Jira, and HRWorks.

The project has changed enough that it should be treated as a new application when publishing to remote hosting. Prefer creating new GitLab/GitHub projects and pushing a clean baseline there instead of overwriting the old DORA-only repositories.

## Product Scope

The application answers operational and leadership questions such as:

- How frequently do customer releases ship, and how long do changes take to reach customers?
- Which releases are associated with production failures, and how quickly are high-priority failures restored?
- Where is engineering capacity going by feature, feature family, theme, team, customer, and investment category?
- Which workflow states create the most waiting time, passive time, thrashing, or delivery risk?
- How do HRWorks availability and forecasted capacity compare with Jira-booked work?
- Can the underlying analytics data be trusted for decision making?

## Main Modules

- **DORA analytics**: deployment frequency, lead time, change failure rate, MTTR Alpha, release drilldowns, worklog hours, and linkage health.
- **Jira Analytics**: issue warehouse, worklog allocation, feature and feature-family costing, portfolio investment reports, workflow bottleneck analysis, team execution reports, customer effort, and data-quality checks.
- **HRWorks capacity**: roster and monthly availability ingestion used by team capacity, utilization, and forecast reports.
- **Admin console**: scheduler settings, credentials, manual ingestion triggers, sync progress, data health, raw table inspection, Jira user/team assignments, and feature-family management.

## Technology Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, APScheduler, httpx, PostgreSQL.
- **Frontend**: Next.js 14 App Router, React 18, TypeScript, TanStack Query, Zustand, Recharts, Tailwind CSS.
- **Data store**: PostgreSQL 16.
- **Runtime**: Docker Compose for local/runtime orchestration; Caddy or another reverse proxy can sit in front for TLS.

## Architecture

The platform uses three scheduled ingestion paths:

1. **DORA nightly pipeline** pulls GitLab releases/tags/MRs and Jira production-bug context, derives cross-system relationships, and refreshes metric snapshots.
2. **Jira Analytics sync** builds and updates the Jira analytics warehouse for issues, fields, worklogs, sprints, transitions, relationships, workflow classifications, feature memberships, and allocation outputs.
3. **HRWorks sync** imports person roster and monthly availability so Jira-booked effort can be compared with real capacity.

APIs are mounted under `/api`. Public analytics endpoints support dashboards and embedded views. Admin endpoints require the configured admin session.

For implementation details, see:

- `documentation/APPLICATION_DOCUMENTATION.md`
- `documentation/PIPELINE_AND_METRICS_DEEP_DIVE.md`
- `documentation/PROJECT_DEFINITION_2_REVIEW.md`

## Project Structure

```text
dora-metrics-server/
├── backend/
│   ├── alembic/                 # Database migrations
│   ├── app/
│   │   ├── api/                 # FastAPI routers
│   │   ├── hrworks/             # HRWorks client, extraction, roster, sync pipeline
│   │   ├── jira_analytics/      # Jira warehouse, allocation, workflow, report services
│   │   ├── models/              # Core DORA models
│   │   ├── schemas/             # API schemas
│   │   └── services/            # DORA pipeline, config, health, metric services
│   ├── scripts/                 # Manual ingestion helpers
│   └── tests/
├── frontend/
│   ├── app/
│   │   ├── admin/               # Current admin console
│   │   ├── admin_legacy/        # Legacy admin screens retained for reference/use
│   │   ├── analytics/           # Jira Analytics and DORA report pages
│   │   ├── embed/               # Iframe-friendly dashboard
│   │   └── components/
│   ├── lib/
│   └── types/
├── documentation/               # Current implementation documentation
├── project_definition_2/        # Historical planning/spec artifacts
├── configuration.yml            # Non-secret bootstrap defaults
└── docker-compose.yml
```

## Local Development

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16, or Docker Compose
- GitLab, Jira, and HRWorks credentials when running real ingestion

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

On macOS/Linux, activate the environment with `source venv/bin/activate`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on `http://localhost:3000` by default. The backend runs on `http://localhost:8000`.

### Docker Compose

```bash
cp .env.docker.example .env
docker compose up --build
```

Fill `.env` with real secrets locally. Do not commit populated environment files.

## Configuration and Secrets

Non-secret defaults live in `configuration.yml`. Runtime configuration can also come from database-backed admin settings and environment variables. Secrets such as GitLab tokens, Jira credentials, HRWorks credentials, admin password, and session keys must be provided through environment variables or encrypted admin configuration.

Configuration precedence is documented in `documentation/APPLICATION_DOCUMENTATION.md`.

## Important Routes

- `/` and `/embed`: DORA-oriented dashboard and embeddable view.
- `/analytics`: analytics command center.
- `/analytics/dora/*`: DORA report pages.
- `/analytics/investment/*`, `/analytics/features/*`, `/analytics/flow/*`, `/analytics/bottlenecks/*`, `/analytics/teams/*`, `/analytics/customers/*`: Jira Analytics report families.
- `/analytics/data-quality`: analytics trust and quality checks.
- `/admin`: current operations console.
- `/admin/ingestion/dora`, `/admin/ingestion/jira-analytics`, `/admin/ingestion/hrworks`: manual sync and progress screens.
- `/admin/schedulers`, `/admin/secrets`, `/admin/jira-analytics/assignments`, `/admin/jira-analytics/feature-families`, `/admin/dora/linkage-health`, `/admin/dora/raw-tables`: admin setup and diagnostics.

## Testing

Backend:

```bash
cd backend
pytest
```

Frontend:

```bash
cd frontend
npm run typecheck
npm test
```

Run focused tests when changing a narrow area. Run broader backend/frontend suites before publishing a new baseline.

## Repository Publishing Guidance

Because this codebase is no longer the old DORA-only application, do not push it blindly to the old GitLab/GitHub remotes. Recommended publication flow:

1. Create new GitLab and GitHub projects for the new platform.
2. Review and rename project metadata where needed.
3. Confirm `.env`, credentials, local database dumps, and generated artifacts are ignored.
4. Create a clean baseline commit.
5. Add the new remotes and push the baseline branch.

Keep the old repositories available as historical reference and rollback context.
