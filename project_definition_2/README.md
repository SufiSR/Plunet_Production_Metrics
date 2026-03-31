# DORA Metrics App — Project Definition

Authoritative specification for the **DORA Metrics** application: collectors, database, API, dashboard (Confluence iframe), and **operational guarantees** (especially **daily data refresh**).

---

## Purpose

Measure engineering delivery health by combining **GitLab** (releases, merge requests, commits) and **Jira** (bugs, versions, priority) into a single PostgreSQL store and a **Next.js** dashboard. The canonical list of KPI semantics—lead time from first commit, release wait, MTTR Alpha, CFR, deployment frequency, rework—is aligned with `new_kpis.md` in this folder.

For **MVP delivery process**, GitLab is used as repository + versioning system. Build/test verification runs locally before push/merge; mandatory CI/CD pipeline gates are deferred to Phase 2. All commits are tracked in `https://gitlab.plunet.com/operations/dora-metrics.git` and should use Jira-key commit messages (for example `git commit -m "DEVOPS-430 <summary>"`).

---

## Technology Stack

| Layer | Technology |
| --- | --- |
| Backend + collector | Python 3.12 · FastAPI · APScheduler · Tenacity · httpx |
| ORM / migrations | **SQLAlchemy 2.x (sync)** · psycopg2 · Alembic |
| Database | PostgreSQL 16 |
| Frontend | Next.js 14 (App Router) · React 18 · TanStack Query v5 · Recharts |
| Styling | Tailwind CSS |
| Jira client | `atlassian-python-api` (REST v3) |
| Deployment | Docker · Docker Compose · Caddy on host (TLS / reverse proxy) |

---

## KPI Coverage (Summary)

| Tier | Metric | Summary |
| --- | --- | --- |
| Core DORA | Deployment frequency | Count of `customer_release` tags per period (RC/Beta excluded by pattern). |
| Core DORA | Lead time for changes | `first_commit_at` → first customer release tag containing the MR; **per target branch** (`master` vs `9.x` / `10.x` / `11.x`). |
| Core DORA | Change failure rate | Share of customer releases with ≥1 `healthy=true` production bug (affects_version ↔ tag). |
| Core DORA | MTTR Alpha | For Critical/Blocker + `healthy=true`: `created_at` → first fix release tag (MR `jira_key` path, then `fix_versions` fallback). |
| Extended | Release wait time | `merged_at` → first customer release tag (sub-metric of delivery). |
| Extended | Rework rate | Patches per minor vs “normal” minors (GitLab tags / version parsing); visualization TBD. |
| Extended | **Lead Post-Production** | **Ready for QA → `merged_at`** (Jira Changelog + GitLab MR); **Erstimplementierung**. |
| Extended | **Jira worklogs** | Gebuchte Zeit pro Vorgang (`issue_worklog`); Vergleich zu Kalender-/Wartezeit — **Erstimplementierung**. |
| Out of scope (v1) | MTTR Beta | Full ServiceDesk cycle — see `new_kpis.md`. |

Detailed definitions: **`dora-metrics-app-documentation.md`** and **`new_kpis.md`**.

---

## Daily Data Refresh (Guarantee)

**All production metrics are driven from database state that is refreshed at least once per calendar day** by a scheduled job inside the backend process (default **02:00** server time, configurable).

1. **GitLab sync** — repositories, tags, merged MRs (per configured target branches), `first_commit_at` for MRs that need it, commit→tag resolution for lead time and release wait, `effective_commit_sha` rules unchanged.  
2. **Jira sync** — bugs (including **priority**), health, versions, indicators.  
3. **Cross-system resolution** — `map_bugs_to_releases`, **`resolve_mttr_alpha_fix_releases`** (depends on GitLab + Jira data).  
4. **Snapshot generation** — recompute `metric_snapshot` rows for configured period types so the API and UI always read **pre-aggregated** values consistent with the latest raw data.  
5. **Sync log + webhook** — record outcome; notify on failure per config.

If one collector fails, the other still runs; snapshots run when **at least one** collector succeeded (exact rules in **`backend-components-documentation.md`**). The UI shows **last successful sync** and **`generated_at`** so users know how fresh numbers are.

---

## Document Map

| File | Contents |
| --- | --- |
| `dora-metrics-app-documentation.md` | Goals, KPIs, **RBAC**, **visualization scope**, **daily refresh**, operations, roadmap. |
| `new_kpis.md` | Business definitions and dashboard expectations (source of truth for naming). |
| `database-schema-documentation.md` | ER model, **`app_configuration`**, metrics tables, indexes. |
| `backend-components-documentation.md` | Collectors, **`run_nightly_sync`**, **auth & admin config**, scheduler, retries. |
| `api-specification-documentation.md` | **Public vs admin routes**, auth, **data freshness**, CORS/credentials. |
| `frontend-components-documentation.md` | Next.js structure, **visualization scope**, Confluence embed, **RBAC & admin config UI**, sync status. |
| `jira-production-bug-filter-decision.md` | Health / production-bug rules. |
| `testing-strategy-documentation.md` | pytest, integration, frontend tests, **nightly job tests**. |
| `open-questions.md` | Resolved and open decisions for implementation backlog. |
| **`jira-backlog-dora-metrics-app.md`** | **Epic „DORA Metrics App“** — Stories & Subtasks für Jira-Anlage. |

---

## What is still open / planned (gap summary)

| Area | Status | Notes |
| --- | --- | --- |
| **Dashboard visuals** | Partially specified | Core cards + trend charts are in scope; **full visual catalog** (per-branch lead time, feature vs patch, CFR drill-down, rework charts, data-health panels) is documented in **`frontend-components-documentation.md`** → *Visualization & dashboard scope*. |
| **RBAC** | **To implement** | **Anonymous read** for all metric/dashboard routes; **Admin** (authenticated) gets **`/admin/config`** to edit GitLab/Jira settings and API credentials. See **`dora-metrics-app-documentation.md`** → *Access control & administration*. |
| **Runtime configuration UI** | **To implement** | Replaces hand-editing `configuration.yml` / `.env` for operators; persists to DB + encrypted secrets (see **`backend-components-documentation.md`**). |

---

## Legacy Reference

Older Java/Vue notes: `../project_definition/`.  
This folder (`project_definition_2`) is the **active** specification for the Python/Next.js implementation.
