# AGENTS.md

This file defines how AI coding agents should work in this repository.

## Mission

Build and maintain the DORA Metrics application to satisfy the active specification and Jira execution plan:
- Python backend (`FastAPI`, `APScheduler`, `SQLAlchemy 2.x sync`, `PostgreSQL`)
- Next.js frontend (`App Router`, `React`, `TanStack Query`, `Recharts`, `Tailwind`)
- Daily scheduled data refresh with reliable snapshots and visible freshness metadata

When requirements conflict, use Jira epic/backlog as primary for implementation scope and `project_definition_2/` as architecture/domain baseline.

## Source of Truth

Primary (most up to date):
- Jira epic `DEVOPS-429` and its child issues (implementation source of truth)

Secondary (architecture/domain reference):
- `project_definition_2/README.md`
- `project_definition_2/dora-metrics-app-documentation.md`
- `project_definition_2/backend-components-documentation.md`
- `project_definition_2/api-specification-documentation.md`
- `project_definition_2/database-schema-documentation.md`
- `project_definition_2/frontend-components-documentation.md`
- `project_definition_2/testing-strategy-documentation.md`
- `project_definition_2/new_kpis.md`

If Jira issue details diverge from `project_definition_2`, prefer Jira and capture the divergence in issue comments/considerations.

## Jira-Driven Delivery Workflow (Mandatory)

For each Jira issue, process one by one:

1) Planning and approval first
- Before implementation, produce an implementation plan for the current issue.
- Ask the user for explicit approval of the plan.
- Include a human time estimate (best-effort engineering estimate).
- After approval, add the approved plan + estimate to Jira:
  - Preferred: issue comment.
  - If decomposition is needed: create sub-issue(s) and include the plan there.
- ALWAYS set the Jira **Original Estimate** field when planning is finished.
- Set the expected time to the same value as the approved estimate.
- Do NOT pre-book that estimate as worked time in the worklog.
- At planning stage, log only the actual time spent planning (for example, 1 minute if planning took 1 minute).

2) Implement after plan approval
- Start coding only after plan approval is confirmed.
- Keep the work scoped to the current issue acceptance criteria.

3) Post-implementation approval and solution capture
- After implementation, request user approval before final Jira closure updates.
- Once approved, execute this post-process in order:
  1. create and push the git commit for the implemented scope,
  2. update the Jira issue "solution" field with what was implemented,
  3. add any missing active-work time to Jira worklog.
- In this Jira project, the solution field is `customfield_10108` ("Solution").
- After the post-process, transition directly to Done (no intermediate code-review status transition).
- The user will set/adjust the final resolution manually when needed.
- Add implementation considerations, constraints, trade-offs, and follow-up notes in issue comments.

4) Time tracking requirements
- Track actual development time per issue using Cursor WakaTime when possible.
- Track only active work time (while the agent is actively doing implementation/debugging/validation).
- Add tracked time details to the Jira issue (worklog/comment as configured).
- Worklog entries must always represent actual elapsed active work, never estimates.
- Never log forecast/expected hours as worklog time.

5) Status-driven progress
- Use Jira issue status transitions to reflect real project progress.
- Keep statuses current across ready-to-start/ready-for-development, in-progress, and done.
- Do not use "Ready for code review" status in this repository workflow.

## Child Backlog Context (DEVOPS-429)

The current epic child scope includes:
- `DEVOPS-430` to `DEVOPS-450` (monorepo/tooling, schema, collectors, scheduler, mappings, API, frontend, admin, testing, CI/CD, operations, handoff, and phase 1.5/roadmap items).

Agents must verify the active child issue details in Jira before each implementation session.

## Project Definition References

Use these documents as canonical references before changing behavior:

- `project_definition_2/README.md`
- `project_definition_2/dora-metrics-app-documentation.md`
- `project_definition_2/backend-components-documentation.md`
- `project_definition_2/api-specification-documentation.md`
- `project_definition_2/database-schema-documentation.md`
- `project_definition_2/frontend-components-documentation.md`
- `project_definition_2/testing-strategy-documentation.md`
- `project_definition_2/new_kpis.md`

## Hard Product Requirements (Must Not Regress)

1) Daily refresh guarantee
- The nightly sync pipeline must continue to run at least once per day (default 02:00, configurable).
- Pipeline ordering must remain consistent with spec: GitLab sync -> first commit enrichment -> MR/tag mapping -> Jira sync -> cross-system linking/resolution -> snapshot generation -> sync log/webhook.
- If one collector fails, the other should still run; snapshot policy follows spec.

2) Data freshness visibility
- Keep and expose freshness metadata (`generated_at`, sync status, last successful run).
- Avoid changes that hide staleness or make freshness unverifiable.

3) RBAC boundary
- Viewer reads remain unauthenticated for dashboard/metrics/sync-status paths (per spec).
- Admin-only configuration/auth routes must stay protected.
- Never expose secrets in API responses; only masked values are allowed.

4) Metrics semantics
- Preserve metric definitions (deployment frequency, lead time, release wait, CFR, MTTR Alpha, lead post-production, worklog-based comparisons) from the project docs.
- Do not silently change formulas, filters, or branch scope without updating docs and tests.

5) Branch and release conventions
- The canonical repository branch is always `main`; do not create or use `master`.
- Do not drop required target branches (`master`, maintenance branches like `9.x`, `10.x`, `11.x`) unless intentionally reconfigured.
- Continue excluding pre-release markers from customer-release metrics according to configurable rules.
- All commits must be pushed to GitLab repository `https://gitlab.plunet.com/operations/dora-metrics.git`.
- If the local workspace is not yet a Git repository, initialize Git and set `origin` to `https://gitlab.plunet.com/operations/dora-metrics.git` before the first commit.
- If `origin` is missing or points elsewhere, correct it before committing/pushing.
- Commit messages must follow the active Jira issue key format: `git commit -m "DEVOPS-<issue-number> <short summary>"`.
- For epic-level scope when no child key is provided, use: `git commit -m "DEVOPS-429 DORA Metrics App"`.

## Engineering Standards

### Backend (Python)
- Prefer explicit, typed service boundaries; keep side effects in service/collector layers, not route handlers.
- Use SQLAlchemy 2.x patterns consistently; avoid mixing async ORM styles into sync codepaths.
- Ensure idempotent upsert behavior for collector writes.
- Handle external API errors with retries/backoff only for retryable cases.
- Keep scheduler tasks observable: structured logs, sync_log records, clear failure context.

### Frontend (Next.js)
- Keep UI components presentational where possible; place data orchestration in hooks/services.
- Use TanStack Query for server state (cache keys should be stable and explicit).
- Keep visualizations accessible (labels/tooltips/contrast) and robust with empty/error/loading states.
- Preserve embed compatibility (Confluence iframe constraints).

### API & Contracts
- Keep response schemas stable; any breaking change requires coordinated frontend update and docs/tests updates.
- Validate all external input with explicit schema models.
- Favor additive API changes over breaking shape changes.

### Security
- Never commit real secrets (`.env`, tokens, credentials).
- Do not log sensitive values.
- Treat admin auth/session handling as high-risk code; require tests for auth-protected route changes.

## Code Quality Best Practices

1) Keep changes small and intention-revealing
- Make the minimal safe change.
- Prefer clear naming over clever abstractions.
- Avoid broad refactors unless requested.

2) Preserve behavior with tests
- Add/adjust tests with every behavior change.
- For bug fixes, include a regression test when feasible.
- Follow the documented pyramid: many unit tests, targeted integrations, selective E2E.

3) Enforce correctness gates locally where possible
- Backend: lint (`ruff`), typing (`mypy`), unit/integration tests (`pytest`).
- Frontend: lint/typecheck/tests (`eslint`/TypeScript/Jest or project-standard commands).
- Do not ignore failing checks introduced by your change.

4) Reliability and failure handling
- Design collectors and sync steps to degrade gracefully.
- Prefer explicit error paths and actionable logs over silent fallbacks.
- Keep operations idempotent and restart-safe.

5) Performance and scalability hygiene
- Avoid N+1 query patterns and repeated external API calls in loops where batching/caching is possible.
- Keep snapshot generation and nightly sync efficient for configured lookback windows.

6) Documentation and traceability
- Update docs in `project_definition_2/` when behavior or assumptions change.
- Mention operational impact (migration, config, restart requirements) in PR notes/commit context.

## Testing Expectations

For substantive changes, verify the relevant scope:
- Unit tests for affected business logic (metric calculation, mapping, RBAC checks)
- Integration tests for DB/API/collector boundaries
- Frontend component tests for UI behavior changes
- E2E only when user-visible flows are changed materially

Coverage targets (from testing strategy):
- Backend unit coverage target >= 80%
- Frontend coverage target >= 70%

## Database and Migration Discipline

- Any schema change must include an Alembic migration.
- Keep migrations reversible when practical.
- Backfill/data-migration logic must be explicit and safe for existing data.
- Do not rewrite historical metric semantics without an explicit migration strategy.

## Agent Workflow

1) Read relevant docs first
- Before coding, inspect the matching spec docs in `project_definition_2/`.

2) Plan briefly, then implement
- Keep a short execution plan in your reasoning; implement end-to-end unless blocked.

3) Validate before finishing
- Run relevant tests/lint for touched areas.
- Confirm no secrets were added.
- Confirm docs/tests are updated for behavioral changes.

4) Communicate clearly
- Summarize what changed, why, and how it was verified.
- Call out any risks, trade-offs, and follow-up work.

## Non-Goals / Avoid

- Do not introduce unrelated architectural changes.
- Do not weaken RBAC or data-freshness guarantees.
- Do not commit generated artifacts or environment secrets.
- Do not modify metric definitions casually; coordinate via docs and tests.
