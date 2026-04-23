# DORA Metrics Server

An automated platform for measuring, aggregating, and visualizing DORA-style software delivery performance metrics. The application combines data from **GitLab** (commits, merge requests, tags/releases) and **Jira** (bugs, incidents, worklogs) to generate daily-updated dashboards that can be embedded into Confluence or viewed standalone.

## 📊 Overview

The DORA Metrics Server calculates both core DORA metrics and customized extended KPIs tailored to the organization's delivery process:

### Core Metrics

- **Deployment Frequency**: How often customer releases are created.
- **Lead Time for Changes**: The time from the first commit to the first customer release (measured per target branch).
- **Change Failure Rate (CFR)**: The percentage of customer releases that result in healthy production bugs.
- **MTTR Alpha (Mean Time to Recovery)**: The time from the creation of a Critical/Blocker production bug to the deployment of its fix in a customer release.

### Extended Metrics

- **Release Wait Time**: The time from a Merge Request being merged to its inclusion in a customer release.
- **Lead Post-Production**: The time from a Jira issue being marked "Ready for QA" to the Merge Request being merged.
- **Work vs Waited**: Comparison between logged work time (`total_worklog_seconds`) and calendar elapsed time.
- **Rework Rate**: (Planned) Comparison of patch density per minor release against a baseline.

## 🛠 Technology Stack

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.x (Sync), APScheduler, httpx, Alembic
- **Database**: PostgreSQL 16
- **Frontend**: Next.js 14 (App Router), React 18, TanStack Query v5, Recharts, Tailwind CSS
- **Deployment**: Docker, Docker Compose, Caddy (for TLS/Reverse Proxy)

## 🏗 Architecture & Data Flow

The system runs a **Daily Data Refresh** (typically scheduled for 02:00 AM) that pulls data to ensure the dashboard reflects the latest state without hammering source APIs continuously:

1. **GitLab Sync**: Fetches repositories, tags, and merged MRs.
2. **Jira Sync**: Fetches production bugs, worklogs, and changelog events.
3. **Cross-System Resolution**: Maps Jira bugs to GitLab releases for CFR and MTTR metrics.
4. **Snapshot Generation**: Pre-calculates metric snapshots for the dashboard to read efficiently.

## 🗂 Project Structure

```text
dora-metrics-server/
├── backend/                  # Python backend API & data collectors
│   ├── app/                  # FastAPI app, models, schemas, services
│   ├── alembic/              # Database migration scripts
│   ├── tests/                # Unit and integration tests
│   ├── requirements.txt      # Python dependencies
│   └── pyproject.toml        # Build system and linting configurations
├── frontend/                 # Next.js web dashboard
│   ├── app/                  # Next.js App Router pages and components
│   ├── lib/                  # Utilities, hooks, and API client
│   └── types/                # TypeScript type definitions
├── project_definition_2/     # Canonical architecture and specification docs
├── configuration.yml         # Application bootstrap configuration
└── docker-compose.yml        # Local development and deployment orchestration
```

## 🔐 Access Control (RBAC)

- **Viewer (Default/Unauthenticated)**: Full read-only access to the main dashboard, metric cards, and trend charts. Designed to be safely embedded within Confluence iframes without requiring SSO.
- **Admin (Authenticated)**: Access to the protected `/admin/config` route to configure GitLab/Jira integrations, API tokens, webhook destinations, and sync schedules. Admin configuration is securely stored in the database.

## 🚀 Local Development

### Prerequisites

- Python 3.12+
- Node.js 20+
- PostgreSQL 16
- Docker & Docker Compose (optional, but recommended for local DB)

### Backend Setup

1. Navigate to the backend directory:
  ```bash
   cd backend
  ```
2. Create and activate a virtual environment:
  ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
  ```
3. Install dependencies:
  ```bash
   pip install -r requirements.txt
  ```
4. Copy the environment template and configure your local PostgreSQL credentials:
  ```bash
   cp ../.env.example .env
  ```
5. Run database migrations:
  ```bash
   alembic upgrade head
  ```
6. Start the development server:
  ```bash
   uvicorn app.main:app --reload
  ```

### Frontend Setup

1. Navigate to the frontend directory:
  ```bash
   cd frontend
  ```
2. Install dependencies:
  ```bash
   npm install
  ```
3. Start the development server:
  ```bash
   npm run dev
  ```

The frontend will be available at `http://localhost:3000`.

## 📖 Documentation Reference

The active product specification, database schema, and architectural decisions are thoroughly documented in the `project_definition_2/` directory. When contributing, always refer to these documents as the source of truth:

- `project_definition_2/README.md`
- `project_definition_2/dora-metrics-app-documentation.md`
- `project_definition_2/api-specification-documentation.md`
- `project_definition_2/database-schema-documentation.md`
- `project_definition_2/new_kpis.md`
- `project_definition_2/testing-strategy-documentation.md`

## 🤝 Contributing

This repository follows a strict Jira-driven workflow.

- Always branch and commit against a Jira Epic/Issue (e.g., `git commit -m "DEVOPS-430 <summary>"`).
- Run the local backend tests (`pytest`) and frontend linting/tests before merging.
- Database schema changes require an `alembic` migration.
- Code changes must adhere to the rules outlined in `AGENTS.md` and the existing testing strategies.

