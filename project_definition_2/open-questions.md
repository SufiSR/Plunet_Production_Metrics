# Open Questions

This file collects all unresolved questions that need decisions before or during implementation. Each question is tagged with a category and a priority (`P1` = blocks progress, `P2` = important, `P3` = nice-to-have / later).

Questions marked **[RESOLVED]** have been answered through POC work or explicit decision. Questions marked **[NEW]** emerged from POC findings.

---

## A. Architecture & Infrastructure

### A1 [P1] [RESOLVED] Collector vs API: same process or separate containers?

**Decision:** Single container (FastAPI + APScheduler lifespan). The nightly job is the only schedule; no Celery/Redis overhead needed.

### A2 [P1] [RESOLVED] Docker Compose layout

**Decision:** `db`, `backend`, `frontend`. No nginx in Compose; SSL and proxying handled by Caddy on host. No separate collector container. Optional pgAdmin remote access user for DB.

### A3 [P2] [RESOLVED] Reverse proxy

**Decision:** No nginx. Caddy on host handles SSL + port passthrough for frontend.

### A4 [P2] [RESOLVED] Port strategy

**Decision:** Backend on `8000`, frontend on `3000`. Customizable in `docker-compose.yml`.

### A5 [P2] [RESOLVED] Environment variable management

**Decision:** `.env` file on host. Secrets never committed to VCS.

### A6 [P3] [RESOLVED] Persistent volumes and backup

**Decision:** Scheduled `pg_dump` to mounted volume. Retention period (in months) configurable in `configuration.yml`. Value `0` = no deletion. Runs as additional APScheduler job if set. GitLab and Jira config also in `configuration.yml` alongside `.env`.

---

## B. Database & Migrations

### B1 [P1] [RESOLVED] Migration strategy on deployment

**Decision:** `alembic upgrade head` in Docker entrypoint before FastAPI starts.

### B2 [P1] [RESOLVED] Async vs sync SQLAlchemy

**Decision:** Sync SQLAlchemy with psycopg2. Simpler to reason about; async not needed given batch-write + simple-read workload pattern.

### B3 [P2] [RESOLVED] Connection pooling

**Decision:** SQLAlchemy built-in pool is sufficient for this load.

### B4 [P2] [RESOLVED] Database user permissions

**Decision:** Single shared DB user (`backend`). No separate API/collector users since they run in the same process.

### B5 [P3] [RESOLVED] Data retention enforcement

**Decision:** Admin sets retention period in months in `configuration.yml`. `0` or unset = no deletion. Otherwise, an additional APScheduler job handles pruning.

---

## C. GitLab Integration

### C1 [P1] [RESOLVED] GitLab API: group vs project enumeration

**Decision:** Static list of project paths in `configuration.yml` (`gitlab_project_paths`). Project paths are the source of truth; repos may live in different groups.

### C2 [P1] [RESOLVED] GitLab API version

**Decision:** REST API v4 via raw `httpx`.

### C3 [P1] [RESOLVED] Protected branches API availability

**Decision:** Available on GitLab Free tier. However, POC established that target branches are better configured explicitly (`master`, `9.x`, `10.x`, `11.x`) rather than queried dynamically. The `target_branches` list in `configuration.yml` is the authoritative source.

### C4 [P1] [RESOLVED] Python GitLab client library

**Decision:** Raw `httpx` for all GitLab calls. POC confirmed all required endpoints are straightforward REST calls; no added value from `python-gitlab` library.

### C5 [P1] [RESOLVED] Commit-to-release mapping algorithm

**Decision (updated from POC):** For lead-time, use the GitLab commit refs API (`/repository/commits/:sha/refs?type=tag`) to find all tags referencing the MR's `effective_commit_sha`, then pick the earliest `customer_release = true` tag whose `committed_date >= merged_at`. Match rate in POC: **98.7%** (1415/1433).

`effective_commit_sha` = `merge_commit_sha` if present, otherwise `squash_commit_sha`.

### C6 [P2] [RESOLVED] GitLab API rate limits

**Decision:** Rate limit is 20 req/s. Simple cooldown between requests; no aggressive throttling for MVP.

### C7 [P2] [RESOLVED] GitLab token type and rotation

**Decision:** Personal Access Token (PAT) in `.env`. Token rotation is a manual task. All sync errors sent to a configurable webhook URL in `configuration.yml`.

### C8 [P3] [RESOLVED] GitLab pagination strategy

**Decision:** Page-based offset pagination (`page` / `per_page`) as used in POC. Works reliably for all endpoints used.

### C9 [NEW][P1] Customer release naming convention

POC uses a regex on tag names to determine `customer_release` (`-rc...` / `-beta...` patterns excluded). The configurable list `non_customer_release_markers` defaults to `[rc, beta]`.

**Open:** Are there any other pre-release naming patterns in use (e.g. `-alpha`, `-hotfix`, `-SNAPSHOT`)? If yes, add to `configuration.yml` defaults.

### C10 [NEW][P2] Lead-time MR branch scope

POC fetches MRs merged into `master`, `9.x`, `10.x`, `11.x`. MRs targeting feature/release-prep branches are excluded.

**Open:** Should release-branch MRs (e.g. `10.24.x-release`) be included in the lead-time calculation, or only the integration/main branches? Recommendation: keep current scope for simplicity.

### C11 [NEW][P2] Unmatched lead-time MRs (1.3%)

18 MRs in the 2-year window could not be matched to a `customer_release` tag. Likely cause: very recent MRs with no tag yet, or cherry-picked/rebased commits whose SHA changed.

**Open:** Define handling policy — exclude from lead-time average, flag in data health view, or investigate individually.

---

## D. Jira Integration

### D1 [P1] [RESOLVED] Jira REST API version

**Decision:** v3 via `atlassian-python-api` 4.0.7+ (cursor-based pagination using `enhanced_jql`).

### D2 [P1] [RESOLVED] "External Ticket Links" custom field ID

**Decision (from POC):**
- `cf[10114]` (`customfield_10114`) = EXALATE / ServiceDesk link (set by Exalate integration)
- `cf[10123]` (`customfield_10123`) = CUSTOMERNAME (manual customer name fallback)
- JQL syntax for custom fields must use `cf[NNNNN]` format, not `"customfield_NNNNN"`.

### D3 [P1] [RESOLVED] "Affects Versions" to tag name mapping

**Decision:** Versions should be named identically in both systems. Mismatches flagged in a "Data Integrity" view in the dashboard.

### D4 [P1] [RESOLVED] Jira authentication type

**Decision:** API token (basic auth, username + token). No OAuth needed.

### D5 [P2] [RESOLVED] Jira Python client library

**Decision:** `atlassian-python-api` for all Jira calls.

### D6 [P2] [RESOLVED] Jira pagination

**Decision:** Cursor-based pagination via `enhanced_jql` (Jira Cloud REST v3 `/search/jql`). No offset-shift risk.

### D7 [P2] [RESOLVED] Scope of Jira project(s)

**Decision:** All projects within lookback window, minus explicitly excluded projects (`excluded_projects` list in `configuration.yml`). Current defaults: `JIRATESTS`, `DEVOPS`. Filtering by affected/fix version is handled via the health evaluation, not JQL.

### D8 [P3] [RESOLVED] Jira bug subtasks

**Decision (from POC):** Bug Subtasks are included. They have their own unique key and can carry `affects_version` and indicator fields. The POC includes a second-pass health re-evaluation for Bug Subtasks with a Bug parent.

### D9 [NEW][P1] Production bug health rule set

The original single-field criterion (`External Ticket Links` is set) has been replaced by a multi-rule health evaluation system. Full rule set documented in `jira-production-bug-filter-decision.md`.

**Current data quality baseline (2-year lookback):**
- `healthy = true`: 970 issues (66.6%)
- `healthy = false`: 486 issues (33.4%) — mostly `affected_version missing`

**Recommended actions:**
1. Make `Affects Versions` mandatory on issue creation in Jira
2. Make `fixVersion` mandatory on resolution
3. Enforce customer indicator (`cf[10114]` or `cf[10123]`) for production incidents

### D10 [NEW][P2] "Customer set to Plunet only" classification

Bugs where `cf[10114]` is empty and all `cf[10123]` values contain "plunet" are classified as `unhealthy - Customer set to Plunet only`.

**Open:** Should these be reclassified as post-production with a lower confidence level, or remain unhealthy? Current decision: unhealthy until `cf[10114]` is set.

---

## E. Business Logic & Data

### E1 [P1] [RESOLVED] Lead time: first_commit_at → first tag containing the commit

**Decision (updated):** Lead Time for Changes = `first_commit_at` (earliest `committed_date` across all commits in the MR, fetched via `GET /merge_requests/:iid/commits`) → `committed_date` of the earliest `customer_release = true` tag that references the MR's `effective_commit_sha` (via `/commits/:sha/refs?type=tag`).\n\nRelease Wait Time (sub-metric) = `merged_at` → same first release tag. Both values are stored on `merge_request` (`lead_time_hours` and `release_wait_time_hours`). `first_commit_at` is nullable; lead time falls back to NULL when the commit list is empty.

### E2 [P1] [RESOLVED] MR → commit SHA mapping

**Decision (from POC):** Use `merge_commit_sha` as primary. Fall back to `squash_commit_sha` if `merge_commit_sha` is null. This is stored as `effective_commit_sha` in the DB.

### E3 [P1] [RESOLVED] Deployment Frequency: branch scope

**Decision (from POC):** Tags collected from project-wide Tags API. `customer_release` flag determined by name pattern. No per-branch restriction at tag level — all customer-release tags from the project count.

### E4 [P2] [RESOLVED] RC tag naming convention

**Decision (from POC):** Configurable via `non_customer_release_markers` in `configuration.yml`. Defaults: `rc`, `beta`. Applied as regex `-(?:rc|beta)(?:[.\d]|$)` on tag name.

### E5 [P2] Deployment deleted after creation

**Open:** If a GitLab tag is deleted after sync, should it be removed from DB? Recommendation for MVP: out of scope; flag for Phase 2.

### E6 [P2] [RESOLVED] Bug never closed (no `closed_at`)

**Decision:** `mttr_minutes` (Jira lifecycle = `closed_at - created_at`) is `NULL` for open bugs — excluded from MTTR average; open count surfaced in data health view.

`mttr_alpha_minutes` is independent of `closed_at`: it is resolved the moment a fix release tag is identified (via MR jira_key or fix_version path). A bug can have a valid `mttr_alpha_minutes` even while still open in Jira.

### E7 [P2] [RESOLVED] Historical data before initial load date

**Decision:** Lookback period configurable (`lookback_years`, default 2). Set in `configuration.yml`. Initial DB load uses the same window.

### E8 [P2] Metric snapshots on initial load

**Open:** On first run, no previous period for trend. Return `null` for `trend` and `trend_percentage`. Stable baseline established after first complete period.

### E9 [P3] [RESOLVED] Multiple bugs on one release

**Decision:** CFR uses binary model per release — a release either has ≥1 `healthy = true` production bug or not. Multiple bugs on one release = 1 failed release.

### E10 [P3] Snapshot regeneration

**Open:** Nightly job overwrites existing snapshots for current period and writes new ones for completed periods. Historical snapshots (prior completed periods) are not recalculated unless triggered manually.

### E11 [NEW][P2] Lead-time outliers

POC shows median 16 days, P90 ~207 days. High P90 likely caused by long-lived feature branches or MRs merged to older maintenance branches (`9.x`) and tagged much later.

**Open:** Should lead time > X days be capped or flagged as outlier in the dashboard? Recommendation: surface P50/P90 separately; let users interpret context.

### E13 [NEW][P2] MR → Jira Bug linkage via key extraction

MR titles and source branch names follow a Jira-key naming convention (e.g. `BM-33279`). The `jira_key` field is extracted via regex from `title` (primary) and `source_branch` (fallback) and stored on the `merge_request` record. Coverage: 66.4% of MRs in the 2-year window; uncovered MRs are structural merge commits.

This creates a direct join path: `production_bug.jira_key` → `merge_request.jira_key` → first `customer_release` tag.

**Open:** Should this be used as the **primary** CFR linking mechanism (replacing `affects_version` matching), or as a **supplementary / verification path** alongside `affects_version`?

Recommendation: use as supplementary path for Phase 1. The `affects_version` path is more explicit; the MR-key path can validate and fill gaps, but 33.6% MR coverage gaps make it unsuitable as the sole mechanism.

**Also open:** Are Jira projects other than `BM` (e.g. `API`, `REST`, `MEM`, `GRP`) relevant for DORA production bug tracking, or only `BM`? If only `BM`, the linkage coverage improves to near-100% for real feature/bug MRs.

### E12 [NEW][P2] [RESOLVED] Lead-time per-branch breakdown

POC data shows significantly different lead-time distributions per target branch:
- `9.x`: median 103h, P90 868h
- `10.x`: median 114h, P90 3791h
- `master`: median 672h, P90 5480h

**Decision:** Dashboard exposes both an aggregate lead time and a per-branch breakdown. `master` MRs represent feature delivery; `9.x`/`10.x`/`11.x` MRs represent patch/hotfix delivery — two fundamentally different delivery rhythms that must not be conflated into a single number without context.

### E14 [NEW][P1] [RESOLVED] MTTR Alpha: priority filter and computation

MTTR Alpha measures DEV-owned incident response: `bug.created_at` → first customer release containing the fix. Separate from MTTR Beta (full ServiceDesk cycle, not in scope now).

**Decisions:**

1. **Priority field**: `priority` (Jira `fields.priority.name`) added to Jira collector and `production_bug` table. Eligible scope = `healthy = true` AND `priority in {Critical, Blocker}`. Priority list is configurable.

2. **Computation (two-path)**:
   - **Path 1 — MR jira_key** (primary): find MR where `merge_request.jira_key = bug.jira_key`; use its `first_customer_tag_date`. Most accurate; relies on jira_key coverage (~66% of all MRs, ~100% for real dev MRs).
   - **Path 2 — fix_version** (fallback): match `bug.fix_versions` values against `release.tag_name` (with/without leading `v`); use earliest matching tag's `committed_date`. Covers cases where no MR link exists.
   - `mttr_alpha_resolution_path` stores which path resolved (`mr_jira_key` | `fix_version` | NULL).

3. **Storage**: `first_fix_release_tag`, `first_fix_release_date`, `mttr_alpha_resolution_path`, `mttr_alpha_minutes` stored on `production_bug`. Populated by `resolve_mttr_alpha_fix_releases()` after both collectors complete.

4. **Independence from `closed_at`**: `mttr_alpha_minutes` is set as soon as a fix release is identified, regardless of Jira status. A bug can be "open" in Jira but have a valid MTTR Alpha.

### E15 [NEW][P2] MTTR Alpha: fix_version path coverage

The fix_version fallback path depends on teams correctly setting `fix_versions` in Jira. Current data quality: ~33.4% of bugs are `healthy=false` (mostly missing `affects_version`). `fix_versions` completeness for Critical+ healthy bugs is unknown until first POC run with priority data.

**Open:** Run the MTTR Alpha POC with the new data and measure `coverage_pct`. If below ~70%, consider whether to prompt for better Jira data hygiene (analogous to E9 recommendation for `affects_version`).

---

## F. Backend / FastAPI

### F1 [P1] [RESOLVED] Python version and base Docker image

**Decision:** Python 3.12 on `python:3.12-slim`.

### F2 [P1] [RESOLVED] Pydantic v1 or v2

**Decision:** Pydantic v2.

### F3 [P2] [RESOLVED] FastAPI lifespan

**Decision:** Use `lifespan` context manager (FastAPI ≥ 0.93). No deprecated `@app.on_event`.

### F4 [P2] CORS: allowed origins

**Open:** MVP uses `allow_origins=["*"]` on internal network. Tighten to Confluence domain + frontend host in Phase 2.

### F5 [P2] API versioning

**Open:** Routes prefixed with `/api/v1/` for future compatibility.

### F6 [P3] Structured logging

**Open:** Use Python standard `logging` for MVP; migrate to `structlog` if log aggregation becomes a requirement.

### F7 [P3] OpenAPI schema generation

**Open:** FastAPI auto-generates OpenAPI 3.x. Export as static file during CI in Phase 2.

---

## G. Frontend / Next.js

### G1 [P1] [RESOLVED] `NEXT_PUBLIC_API_URL` at build vs runtime

**Decision:** Baked at build time via `NEXT_PUBLIC_API_URL` in Docker Compose. Acceptable for MVP since backend URL is stable per deployment.

### G2 [P1] [RESOLVED] Next.js App Router vs Pages Router

**Decision:** App Router (Next.js 14).

### G3 [P2] [RESOLVED] Chart library

**Decision:** Recharts. React-native, good TypeScript support.

### G4 [P2] TanStack Query polling frequency

**Open:** Data refreshed on page load only. Since nightly updates, no active polling needed in MVP. May revisit for Phase 2 live refresh.

### G5 [P2] iframe auto-height in Confluence

**Open:** Test in actual Confluence instance. Fallback: fixed height (e.g. 900px).

### G6 [P2] [RESOLVED] Node.js version

**Decision:** Node 20 LTS on `node:20-alpine`.

### G7 [P3] CSS framework

**Decision:** Tailwind CSS v3 (stable).

### G8 [P3] Error boundary handling

**Open:** Inline error state per component for MVP. `error.tsx` boundaries for Phase 2.

---

## H. Testing

### H1 [P1] Test database isolation

**Open:** Use shared `testcontainers-python` container with transaction rollbacks between tests. Fastest approach for CI.

### H2 [P2] Mock API for E2E tests

**Open:** Custom FastAPI mock server for GitLab and Jira API simulation. Simplest to maintain in the same Python ecosystem.

### H3 [P2] Frontend test runner: Jest vs Vitest

**Open:** Vitest (faster, native ESM). Decision before writing frontend tests.

### H4 [P3] mypy strictness level

**Open:** Relaxed config for MVP. Migrate to `--strict` in Phase 2.

### H5 [P3] Coverage enforcement in CI

**Open:** Target 80% backend, 70% frontend. Enforce in CI from Phase 2.

---

## I. Security & Operations

### I1 [P1] [RESOLVED] Secret management

**Decision:** `.env` file on host, never committed. `.gitignore` enforced.

### I2 [P2] [SUPERSEDED] Internal network assumption

**Original decision:** No FastAPI auth for MVP.

**Superseded by I6:** Anonymous read remains; Admin routes require authentication.

### I6 [P1] [RESOLVED] RBAC — viewers vs admins

**Decision:**

- **Viewers:** No login. `GET` metrics, repositories, sync status, health — unchanged for Confluence embed.
- **Admins:** Authenticated access to **`/admin/config`** (UI) and **`/api/admin/config`**, **`/api/auth/*`**. All other users cannot read or write integration settings.
- Implementation: session cookie or JWT; see `api-specification-documentation.md` and `backend-components-documentation.md` (Authentication & admin configuration).

### I7 [P2] [OPEN] Admin bootstrap & password storage

**Open:** Bootstrap first admin via **`DORA_ADMIN_PASSWORD`** (env only) vs **`admin_user`** table with bcrypt hashes. Recommendation: DB table for auditability if multiple admins are ever needed.

### I8 [P2] [OPEN] Session cookie vs JWT for Admin (iframe context)

**Open:** Browsers may restrict **third-party cookies** when the app is embedded. Options: (a) Admin UI only on **top-level** dashboard origin (no iframe); (b) **Bearer JWT** stored in memory for Admin API calls. Validate in Confluence + staging.

### I3 [P2] Health check in Docker Compose

**Open:** `healthcheck:` defined per service so dependent services wait for readiness.

### I4 [P3] Monitoring and alerting

**Open:** Webhook for sync failures (configurable URL). No external monitoring in MVP.

### I5 [P3] Log retention

**Open:** Stdout only (Docker default). Mount volume if log retention needed.

---

## J. Confluence Integration

### J1 [P1] [RESOLVED] Network routing

**Decision:** iframe `src` points to internal host. Reachable from user browsers on internal network.

### J2 [P1] [RESOLVED] Confluence iframe macro

**Decision:** HTML Macro or Widget Connector Macro. IT approval required for HTML Macro permissions.

### J3 [P2] CSP / X-Frame-Options headers

**Open:** Next.js `next.config.ts` must set `X-Frame-Options: ALLOWALL` (or equivalent `frame-ancestors` CSP). Must be validated in actual Confluence tenant.

### J4 [P3] iframe height and scrollbars

**Open:** Start with fixed height (e.g. 900px). Test auto-resize via `postMessage` in actual Confluence.

---

## K. Project & Process

### K1 [P1] [RESOLVED] Git repository structure

**Decision:** Monorepo with `backend/` and `frontend/` subdirectories.

### K2 [P2] Branching strategy

**Decision:** Feature branches + MRs into `main` for this repo.
**Decision:** All commits are versioned in GitLab at `https://gitlab.plunet.com/operations/dora-metrics.git`.
**Decision:** Commit message format uses the active Jira key, e.g. `git commit -m "DEVOPS-430 <summary>"`; for epic-level work use `git commit -m "DEVOPS-429 DORA Metrics App"`.

### K3 [P2] GitLab CI/CD configuration

**Decision (MVP):** No mandatory `.gitlab-ci.yml` quality gates in MVP. GitLab is used for repository hosting + versioning; lint/tests are executed locally before push/merge.
**Phase 2 option:** Add `.gitlab-ci.yml` for lint, test, and Docker image build once automated gates are required.

### K4 [P2] Docker image registry

**Decision (MVP):** Build and validate locally.
**Phase 2 option:** Use GitLab Container Registry when CI/CD automation is introduced.

### K5 [P3] Developer onboarding

**Open:** `Makefile` with common dev commands (`make up`, `make test`, `make migrate`).


