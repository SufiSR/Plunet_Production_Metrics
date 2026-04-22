| DEVOPS-506 | implementation | 2026-04-22 10:43 | 2026-04-22 11:28 | 45m | MTTR Alpha UX/data improvements: visible trend points, release-based version drill-down, and 30d/quarterly/yearly-aligned detail windows; rebuilt and browser-verified |
| DEVOPS-504 | jira-update | 2026-04-16 15:59 | 2026-04-16 16:01 | 2m | Bug Subtask under DEVOPS-488: description, Solution (ADF), Confluence component, assignee; Jira worklog 2m; GitLab commit/push DEVOPS-504 |
| DEVOPS-488 | jira-update | 2026-04-16 15:49 | 2026-04-16 15:50 | 1m | Commit and push workspace changes to GitLab |
| DEVOPS-503 | jira-update | 2026-04-16 15:41 | 2026-04-16 15:47 | 6m | Created DEVOPS-503 under DEVOPS-488 (Confluence, assignee); booked 5 worklogs (50m) from worklog-time-log |
| DEVOPS-429 | validation | 2026-04-16 15:36 | 2026-04-16 15:43 | 7m | Docker compose build --pull + up -d; db/backend/frontend healthy |
| DEVOPS-429 | implementation | 2026-04-16 15:30 | 2026-04-16 15:38 | 8m | CFR semantics: count only post-production bugs (exclude pre-production memo); shared predicate; tests + UI copy |
| DEVOPS-429 | implementation | 2026-04-16 15:18 | 2026-04-16 15:34 | 16m | CFR drill-down: backend failed-release + issues endpoints/schemas/service/tests; frontend panel + API/hooks/query-keys; TrendOverviewSection wiring |
| DEVOPS-429 | investigation | 2026-04-16 18:00 | 2026-04-16 18:12 | 12m | Assessed feasibility + implementation approach for CFR drill-down (failed customer releases → linked Jira issues) |
| DEVOPS-429 | investigation | 2026-04-16 17:30 | 2026-04-16 17:37 | 7m | Explained which data is used for Change Failure Rate (CFR) |
| DEVOPS-429 | implementation | 2026-04-16 09:50 | 2026-04-16 10:07 | 17m | Implemented deployment swimlane timeline: backend release timeline endpoint + schema/tests, frontend API/hook wiring, new dashboard/embed swimlane component with customer-release emphasis and detail panel |
| DEVOPS-429 | investigation | 2026-04-16 12:15 | 2026-04-16 12:18 | 3m | Explained lead-time trend gaps vs customer releases; sorted metrics history chronologically in api-client for trend/sparkline charts |
| DEVOPS-429 | implementation | 2026-04-16 14:05 | 2026-04-16 14:11 | 6m | Generated sample dual-series lead-time mockup image and copied to docs/ |
| DEVOPS-429 | implementation | 2026-04-16 15:20 | 2026-04-16 15:26 | 6m | Generated release→MR drill-down UI mockup and saved under docs/ |
| DEVOPS-429 | implementation | 2026-04-16 16:00 | 2026-04-16 16:45 | 45m | Release drill-down: paginated customer releases + MR API, frontend panel with repo filter and MR pagination, aligned RepositoriesResponse types |
| DEVOPS-429 | implementation | 2026-04-16 14:50 | 2026-04-16 14:54 | 4m | Lead-time diagnostics follow-up: release drill-down compare/Jira summary UI, restore latest-vs-previous window in metrics_public_service, fix MR list test dates, full pytest + docker compose build |
| DEVOPS-429 | validation | 2026-04-16 14:56 | 2026-04-16 14:58 | 2m | Docker Compose up --build -d; db/backend/frontend healthy on 5433/8000/3000 |
| DEVOPS-502 | jira-update | 2026-04-16 15:06 | 2026-04-16 15:07 | 1m | Created Improvement Subtask under DEVOPS-488: description + Solution (ADF), Confluence component, assignee; booked 6m engineering worklog from DEVOPS-429 worklog-time-log entries |
# Worklog Time Log

Use this file as the durable source for Jira worklog entries.
Record only actual active work time.

## Entry format

| Issue | Activity | Start (local) | End (local) | Duration | Notes |
| --- | --- | --- | --- | --- | --- |
| DEVOPS-000 | planning | 2026-03-31 14:00 | 2026-03-31 14:05 | 5m | Initial plan draft |
| DEVOPS-433 | planning | 2026-03-31 14:32 | 2026-03-31 14:33 | 1m | Scope check and implementation plan approval |
| DEVOPS-433 | implementation | 2026-03-31 14:34 | 2026-03-31 14:35 | 1m | Added MR collection, Jira key extraction, dedupe, and unit tests |
| DEVOPS-433 | jira-update | 2026-03-31 14:36 | 2026-03-31 14:37 | 1m | Added Jira plan/estimate/worklog, prepared solution and status transition |
| DEVOPS-433 | jira-update | 2026-03-31 14:38 | 2026-03-31 14:38 | 1m | Updated solution field and executed Done transition with required log-work entry |
| DEVOPS-435 | implementation | 2026-03-31 14:52 | 2026-03-31 14:58 | 6m | Implemented MR first-commit and customer-tag mapping logic with unit tests |
| DEVOPS-435 | validation | 2026-03-31 14:59 | 2026-03-31 15:00 | 1m | Added Jira progress comment and reran backend unit tests (12 passed) |
| DEVOPS-435 | jira-update | 2026-03-31 15:01 | 2026-03-31 15:03 | 2m | Committed/pushed changes and prepared Jira solution/worklog/done transition |
| DEVOPS-435 | jira-update | 2026-03-31 15:03 | 2026-03-31 15:04 | 1m | Jira done transition required explicit log-work during transition |
| DEVOPS-434 | planning | 2026-03-31 15:07 | 2026-03-31 15:08 | 1m | Reviewed issue details and prepared approved implementation plan with estimate |
| DEVOPS-434 | implementation | 2026-03-31 15:09 | 2026-03-31 15:12 | 3m | Implemented Jira production bug collector with health/worklog/changelog handling and DB upserts |
| DEVOPS-434 | validation | 2026-03-31 15:12 | 2026-03-31 15:12 | 1m | Ran backend unit tests including new Jira collector tests (18 passed) |
| DEVOPS-434 | jira-update | 2026-03-31 15:22 | 2026-03-31 15:22 | 1m | Performed commit/push and prepared Jira solution, worklog, and Done transition updates |
| DEVOPS-434 | jira-update | 2026-03-31 15:23 | 2026-03-31 15:23 | 1m | Jira Done transition required explicit log-work entry; prepared transition-compliant update |
| DEVOPS-436 | planning | 2026-03-31 15:44 | 2026-03-31 15:45 | 1m | Reviewed issue details, adjusted estimate to 2h, and recorded approved implementation plan in Jira |
| DEVOPS-436 | implementation | 2026-03-31 15:45 | 2026-03-31 15:48 | 3m | Added FastAPI lifespan startup/shutdown, APScheduler cron job wiring, nightly sync pipeline ordering, and partial-failure policy hooks |
| DEVOPS-436 | validation | 2026-03-31 15:48 | 2026-03-31 15:48 | 1m | Ran backend unit tests for scheduler/sync pipeline and existing collector test suites (21 passed) |
| DEVOPS-436 | jira-update | 2026-03-31 16:03 | 2026-03-31 16:04 | 1m | Committed and pushed DEVOPS-436 implementation to origin/main |
| DEVOPS-436 | jira-update | 2026-03-31 16:04 | 2026-03-31 16:05 | 1m | Updated Jira solution field and added implementation considerations comment |
| DEVOPS-436 | jira-update | 2026-03-31 16:05 | 2026-03-31 16:05 | 1m | Close transition requested explicit log-work; prepared transition-compliant closure update |
| DEVOPS-437 | planning | 2026-03-31 16:15 | 2026-03-31 16:16 | 1m | Reviewed implementation state/spec alignment, prepared extensive issue rewrite, and logged approved plan + estimate in Jira |
| DEVOPS-437 | implementation | 2026-03-31 16:16 | 2026-03-31 16:19 | 3m | Implemented Story 7 derivation updates (config-driven priorities, normalized bug-release/MTTR matching, path labels) and added tests |
| DEVOPS-437 | jira-update | 2026-03-31 16:24 | 2026-03-31 16:24 | 1m | Transitioned status from Refinement -> Ready for development -> Development (In Progress) and reconciled worklog tracking |
| DEVOPS-437 | implementation | 2026-03-31 16:25 | 2026-03-31 16:27 | 2m | Added hardening for version normalization edge cases, deterministic MR selection for MTTR path A, stale lead-post-production clearing, and extra regression tests |
| DEVOPS-437 | validation | 2026-03-31 16:27 | 2026-03-31 16:28 | 1m | Re-ran Story 7 and scheduler tests after hardening (9 passed) and checked lints |
| DEVOPS-437 | jira-update | 2026-03-31 16:34 | 2026-03-31 16:35 | 1m | Added Jira progress comment with acceptance-criteria gap check and deferred-scope notes |
| DEVOPS-437 | jira-update | 2026-03-31 16:36 | 2026-03-31 16:37 | 1m | Finalized code delivery: staged files, committed DEVOPS-437 changes, and pushed to origin/main |
| DEVOPS-437 | jira-update | 2026-03-31 16:38 | 2026-03-31 16:38 | 1m | Updated Jira solution field and prepared completion transition (close step requires explicit log-work) |
| DEVOPS-437 | jira-update | 2026-03-31 16:38 | 2026-03-31 16:38 | 1m | Executed close transition with transition-level log-work payload due workflow validator requirement |
| DEVOPS-438 | planning | 2026-03-31 16:47 | 2026-03-31 16:47 | 1m | Started issue, reviewed Jira scope, and prepared implementation plan for approval |
| DEVOPS-438 | jira-update | 2026-03-31 16:50 | 2026-03-31 16:50 | 1m | Added approved plan comment and set Original Estimate/Remaining Estimate to 3h |
| DEVOPS-438 | implementation | 2026-03-31 16:50 | 2026-03-31 16:53 | 3m | Added runtime config service with YAML+DB+env merge precedence, encrypted secret handling, and sync pipeline wiring |
| DEVOPS-438 | validation | 2026-03-31 16:53 | 2026-03-31 16:54 | 1m | Ran backend unit tests including new config service coverage (30 passed) and targeted lint check |
| DEVOPS-438 | jira-update | 2026-03-31 17:03 | 2026-03-31 17:03 | 1m | Created and pushed DEVOPS-438 commit, prepared Jira solution/worklog/done transition updates |
| DEVOPS-438 | jira-update | 2026-03-31 17:04 | 2026-03-31 17:04 | 1m | Jira close transition required explicit transition-level log-work payload |
| DEVOPS-439 | implementation | 2026-04-01 09:42 | 2026-04-01 09:45 | 3m | Implemented metric calculation and snapshot services, integrated nightly snapshot generation, and validated with targeted backend unit tests |
| DEVOPS-439 | jira-update | 2026-04-01 09:52 | 2026-04-01 09:53 | 1m | Posted DEVOPS-439 implementation progress comment on Jira |
| DEVOPS-439 | jira-update | 2026-04-01 10:05 | 2026-04-01 10:05 | 1m | Post-implementation closure updates: set Solution field, added final worklog, and transitioned issue to Done |
| DEVOPS-451 | planning | 2026-04-01 10:16 | 2026-04-01 10:18 | 2m | Reviewed scope, prepared implementation plan, got approval, and recorded plan + estimate in Jira |
| DEVOPS-451 | implementation | 2026-04-01 14:28 | 2026-04-01 14:34 | 6m | merge_request inserted_at→updated_at, initial schema + rename migration for existing DBs, database-schema doc, unit test |
| DEVOPS-451 | validation | 2026-04-01 14:34 | 2026-04-01 14:35 | 1m | pytest story7/story9 (11 passed) |
| DEVOPS-451 | jira-update | 2026-04-01 14:36 | 2026-04-01 14:38 | 2m | Committed/pushed DEVOPS-451; prepared Jira solution, worklog, and Done transition |
| DEVOPS-451 | jira-update | 2026-04-01 14:39 | 2026-04-01 14:40 | 1m | Jira Close transition required transition-level worklog entry |
| DEVOPS-452 | implementation | 2026-04-01 10:36 | 2026-04-01 10:38 | 2m | Reviewed linked Jira items and performed production ETL risk analysis; documented findings in DEVOPS-452-findings.md |
| DEVOPS-452 | jira-update | 2026-04-01 10:38 | 2026-04-01 10:48 | 10m | Created Bug Subtasks DEVOPS-453..DEVOPS-457 from highest-risk findings and linked them under DEVOPS-452 |
| DEVOPS-452 | jira-update | 2026-04-01 10:48 | 2026-04-01 10:52 | 4m | Created second batch of Bug Subtasks DEVOPS-458..DEVOPS-462 for remaining Medium findings |
| DEVOPS-452 | jira-update | 2026-04-01 10:52 | 2026-04-01 10:57 | 5m | Manual coordination and review work performed by assignee; requested to include in Jira worklog |
| DEVOPS-452 | jira-update | 2026-04-01 11:01 | 2026-04-01 11:02 | 1m | Updated solution summary, added Jira worklog (21m total requested), transitioned Resolve Issue -> Done |
| DEVOPS-453 | planning | 2026-04-01 11:16 | 2026-04-01 11:17 | 1m | Reviewed bug subtask scope, refined implementation plan, set estimate, and prepared workflow progression |
| DEVOPS-453 | implementation | 2026-04-01 11:17 | 2026-04-01 11:18 | 1m | Cleared stale MR mapping fields on remap iteration and added regression test for stale-to-unmatched rerun |
| DEVOPS-453 | validation | 2026-04-01 11:18 | 2026-04-01 11:18 | 1m | Ran targeted backend unit tests for gitlab collector and story7 derivations (19 passed) |
| DEVOPS-453 | jira-update | 2026-04-01 11:19 | 2026-04-01 11:20 | 1m | Updated solution field, logged work (4m + transition-required 1m), and transitioned Development -> Done |
| DEVOPS-454 | planning | 2026-04-01 11:20 | 2026-04-01 11:20 | 1m | Reviewed subtask scope, set 30m estimate, documented implementation plan, and moved issue through refinement flow |
| DEVOPS-454 | implementation | 2026-04-01 11:20 | 2026-04-01 11:21 | 1m | Changed nightly sync to skip snapshot generation on partial collector success and added explicit skip log |
| DEVOPS-454 | validation | 2026-04-01 11:21 | 2026-04-01 11:21 | 1m | Updated and ran scheduler/sync pipeline tests with partial-failure snapshot assertion (9 passed) |
| DEVOPS-454 | jira-update | 2026-04-01 11:22 | 2026-04-01 11:22 | 1m | Updated solution field, logged work (4m + transition-required 1m), and transitioned Development -> Done |
| DEVOPS-455 | planning | 2026-04-01 11:22 | 2026-04-01 11:23 | 1m | Reviewed timezone-boundary scope, set estimate, documented plan, and moved issue through refinement workflow |
| DEVOPS-455 | implementation | 2026-04-01 11:23 | 2026-04-01 11:24 | 1m | Switched collector lookback anchors to UTC date in GitLab and Jira services; added UTC-midnight tests |
| DEVOPS-455 | validation | 2026-04-01 11:24 | 2026-04-01 11:24 | 1m | Ran collector + derivation unit tests after UTC lookback update (27 passed) |
| DEVOPS-455 | jira-update | 2026-04-01 11:24 | 2026-04-01 11:24 | 1m | Updated solution field, logged work (4m + transition-required 1m), and transitioned Development -> Done |
| DEVOPS-456 | planning | 2026-04-01 11:28 | 2026-04-01 11:29 | 1m | Reviewed subtask scope, set 30m estimate, documented plan, and moved issue through refinement flow |
| DEVOPS-456 | implementation | 2026-04-01 11:29 | 2026-04-01 11:31 | 2m | Updated nightly sync to load runtime config with DB session and added regression test for DB-backed config loading |
| DEVOPS-456 | validation | 2026-04-01 11:31 | 2026-04-01 11:32 | 1m | Ran scheduler/sync and config unit tests after DB-backed runtime config change (7 passed) |
| DEVOPS-456 | jira-update | 2026-04-01 11:32 | 2026-04-01 11:33 | 1m | Updating Jira solution/worklog/resolution and transitioning Development -> Done with transition-required log-work |
| DEVOPS-457 | planning | 2026-04-01 11:33 | 2026-04-01 11:33 | 1m | Reviewed updated-aware sync scope, set 30m estimate, documented plan, and moved issue through refinement flow |
| DEVOPS-457 | implementation | 2026-04-01 11:33 | 2026-04-01 11:34 | 1m | Switched Jira bug JQL from created-based to updated-based incremental filter and added regression test for JQL generation |
| DEVOPS-457 | validation | 2026-04-01 11:34 | 2026-04-01 11:34 | 1m | Ran Jira bug collector unit tests after incremental-sync update (8 passed) |
| DEVOPS-457 | jira-update | 2026-04-01 11:34 | 2026-04-01 11:35 | 1m | Updating Jira solution/worklog/resolution and transitioning Development -> Done with transition-required log-work |
| DEVOPS-458 | planning | 2026-04-01 11:37 | 2026-04-01 11:37 | 1m | Reviewed snapshot ID-collision scope, set 30m estimate, documented plan, and moved issue through refinement flow |
| DEVOPS-458 | implementation | 2026-04-01 11:37 | 2026-04-01 11:38 | 1m | Removed manual snapshot max(id)+1 assignment and switched to DB-managed IDs; added SQLite-compatible PK autoincrement variant |
| DEVOPS-458 | validation | 2026-04-01 11:38 | 2026-04-01 11:38 | 1m | Ran snapshot + scheduler unit tests after ID generation changes (9 passed) |
| DEVOPS-458 | jira-update | 2026-04-01 11:38 | 2026-04-01 11:39 | 1m | Updating Jira solution/worklog/resolution and transitioning Development -> Done with transition-required log-work |
| DEVOPS-459 | planning | 2026-04-01 11:43 | 2026-04-01 11:43 | 1m | Reviewed deletion-reconciliation scope, set 45m estimate, documented plan, and moved issue through refinement flow |
| DEVOPS-459 | implementation | 2026-04-01 11:43 | 2026-04-01 11:44 | 1m | Added release reconciliation in GitLab collector to remove upstream-missing tags and added regression test for stale-tag cleanup |
| DEVOPS-459 | validation | 2026-04-01 11:44 | 2026-04-01 11:44 | 1m | Ran GitLab collector and scheduler unit tests after reconciliation update (19 passed) |
| DEVOPS-459 | jira-update | 2026-04-01 11:44 | 2026-04-01 11:45 | 1m | Updating Jira solution/worklog/resolution and transitioning Development -> Done with transition-required log-work |
| DEVOPS-460 | planning | 2026-04-01 11:51 | 2026-04-01 11:51 | 1m | Reviewed MR pagination performance scope, set 30m estimate, documented plan, and moved issue through refinement flow |
| DEVOPS-460 | implementation | 2026-04-01 11:51 | 2026-04-01 11:52 | 1m | Added server-side updated_after bound to merged MR API call and added regression test for bounded params plus merged_at safety filter |
| DEVOPS-460 | validation | 2026-04-01 11:52 | 2026-04-01 11:52 | 1m | Ran GitLab collector tests after pagination optimization update (16 passed) |
| DEVOPS-460 | jira-update | 2026-04-01 11:52 | 2026-04-01 11:53 | 1m | Updating Jira solution/worklog/resolution and transitioning Development -> Done with transition-required log-work |
| DEVOPS-461 | planning | 2026-04-01 12:17 | 2026-04-01 12:17 | 1m | Reviewed coherent bug_release rebuild scope, set 30m estimate, documented plan, and moved issue through refinement flow |
| DEVOPS-461 | implementation | 2026-04-01 12:17 | 2026-04-01 12:18 | 1m | Gated bug_release mapping to run only when both collectors succeed and added partial-failure test assertion for skipped links |
| DEVOPS-461 | validation | 2026-04-01 12:18 | 2026-04-01 12:18 | 1m | Ran scheduler/sync pipeline tests after coherent rebuild gating update (4 passed) |
| DEVOPS-461 | jira-update | 2026-04-01 12:18 | 2026-04-01 12:19 | 1m | Updating Jira solution/worklog/resolution and transitioning Development -> Done with transition-required log-work |
| DEVOPS-462 | implementation | 2026-04-01 17:15 | 2026-04-01 17:22 | 7m | jira_created_at_valid + nullable created_at migration, upsert without synthetic now, MTTR Alpha guards, unit tests |
| DEVOPS-464 | implementation | 2026-04-01 17:22 | 2026-04-01 17:28 | 6m | first_commit_at revalidation for MRs in UTC lookback (updated_at/merged_at); regression test |
| DEVOPS-465 | implementation | 2026-04-01 17:28 | 2026-04-01 17:34 | 6m | Jira search expand=changelog with truncated-embedded fallback; changelog helper unit tests |
| DEVOPS-462 | jira-update | 2026-04-01 17:34 | 2026-04-01 17:42 | 8m | Jira workflow for 462/464/465 (components on 464/465), solution + timetracking, worklogs, Close issue with transition worklog |
| DEVOPS-458 | implementation | 2026-04-01 20:10 | 2026-04-01 20:18 | 8m | Removed manual metric_snapshot id assignment; DB autoincrement; Integer PK variant on SQLite; regression test for assigned ids |
| DEVOPS-463 | implementation | 2026-04-01 20:18 | 2026-04-01 20:22 | 4m | Mock load_runtime_config in nightly sync unit tests; align partial-failure test with skipped links/snapshots |
| DEVOPS-463 | jira-update | 2026-04-01 20:22 | 2026-04-01 20:28 | 6m | Close parent DEVOPS-463: solution, worklog, transitions |
| DEVOPS-463 | jira-update | 2026-04-01 20:28 | 2026-04-01 20:29 | 1m | Jira Close issue transition: required worklog on transition payload |
| DEVOPS-466 | implementation | 2026-04-01 14:20 | 2026-04-01 14:33 | 13m | Story7 lead-post tests (lookback_days, processed count), scoped ruff on _parse_dt, backend unit pytest (50 passed), commit/push DEVOPS-466 |
| DEVOPS-466 | jira-update | 2026-04-01 14:33 | 2026-04-01 14:52 | 19m | Jira DEVOPS-467-485: Original Estimate + Solution (ADF), Done transitions; parent DEVOPS-466 solution and closure prep |

| DEVOPS-466 | implementation | 2026-04-01 21:30 | 2026-04-01 21:45 | 15m | Fixing after secondary review: 13 pipeline integrity/reliability fixes (F1-F13), test updates, lint, commit/push |
| DEVOPS-440 | implementation | 2026-04-01 23:05 | 2026-04-01 23:40 | 35m | Signed session cookie (Starlette SessionMiddleware), auth + admin config routes, CORS, ErrorResponse handlers, /api/health, scheduler reschedule on PATCH, unit tests (SQLite); integration tests skip without Docker |
| DEVOPS-440 | implementation | 2026-04-02 00:05 | 2026-04-02 00:45 | 40m | Public API: metrics current/history/repository, repositories list, sync/status, full /api/health; sync_log.details_json + pipeline payload; metrics_public_service aggregation; export_openapi script; migration 20260402_0006; public route unit tests |
| DEVOPS-440 | jira-update | 2026-04-02 00:15 | 2026-04-02 00:22 | 7m | Jira Solution (ADF), worklogs 35m + 40m per worklog-time-log, workflow to Done (Close issue + transition worklog), implementation comment, git commit/push |
| DEVOPS-441 | planning | 2026-04-02 12:10 | 2026-04-02 12:31 | 21m | Reviewed DEVOPS-441, design requirements (DESIGN_LIGHT.md, HTML prototypes), identified dark mode token gap, drafted full 12-subtask implementation plan, got user approval on all 5 design decisions |
| DEVOPS-441 | implementation | 2026-04-02 12:31 | 2026-04-02 12:49 | 18m | Full DEVOPS-441 implementation: DESIGN_DARK.md, Tailwind v4 CSS vars, next-themes, Zustand, API client, HeaderBar, MetricGrid, TrendChart, MetricModal, StaleBanner, embed route, CSP config, LeadPostProductionTable, 20 tests, typecheck+lint clean |
| DEVOPS-466 | jira-update | 2026-04-02 20:00 | 2026-04-02 20:20 | 20m | Jira comment + worklog: short delivery recap for tests/docs push (commit 8f311f9); aligns with repo worklog-time-log |
| DEVOPS-443 | planning | 2026-04-02 21:15 | 2026-04-02 21:20 | 5m | Reviewed issue, fetched Jira, read spec and repo structure, drafted plan, posted to Jira, set estimate 1.5h, transitioned to In Progress |
| DEVOPS-443 | implementation | 2026-04-02 21:20 | 2026-04-02 21:40 | 20m | backend/Dockerfile, frontend/Dockerfile, docker-compose.yml, .env.docker.example, docs/deployment.md, next.config.ts standalone output, .gitignore update |
| DEVOPS-443 | jira-update | 2026-04-02 21:41 | 2026-04-02 21:43 | 2m | Committed/pushed c5effc4, updated Solution field (ADF), logged 5m+20m worklogs, transitioned to Done |
| DEVOPS-442 | planning | 2026-04-02 13:10 | 2026-04-02 14:20 | 70m | Reviewed DEVOPS-442, design requirements (DESIGN_LIGHT.md, DESIGN_DARK.md, admin_config prototype), existing frontend/backend code, drafted full 11-task plan, posted to Jira, set estimate 3h30m, transitioned to Development |
| DEVOPS-442 | implementation | 2026-04-02 14:20 | 2026-04-02 14:45 | 25m | middleware, admin-api-client, types/admin, AdminSidebar, SecretInput, UnsavedToast, TagListInput, GitLab/Jira/Scheduler/Webhook sections, login/config pages, 13 new tests (33 total), tsc+eslint clean, commit e88425b pushed |
| DEVOPS-429 | implementation | 2026-04-02 15:18 | 2026-04-02 15:19 | 1m | Docker backend: mount configuration.yml, DORA_CONFIG_PATH; .env.example + deployment + backend README |
| DEVOPS-429 | validation | 2026-04-02 15:20 | 2026-04-02 15:41 | 21m | Docker compose up: frontend SSR fixes, next.config.mjs standalone, itsdangerous, compose healthchecks, configuration.yml Jira CF string ids; stack healthy |

## Session protocol

Every session MUST follow this two-step pattern:

**Step 1 — write this as the VERY FIRST tool call when work starts:**
```
| DEVOPS-XXX | planning | 2026-01-01 14:30 | OPEN | — | Session started |
```

**Step 2 — update to this as the VERY LAST tool call before declaring session complete:**
```
| DEVOPS-XXX | planning | 2026-01-01 14:30 | 2026-01-01 14:52 | 22m | Description of what was done |
```

Duration = end minus start in minutes. Never estimate or guess.
If the OPEN entry is missing, ask the user for the actual start time before closing.
Never log to Jira until the entry is finalized (no OPEN or — remaining).

| DEVOPS-487 | implementation | 2026-04-02 15:48 | 2026-04-02 15:58 | 10m | Fixed admin cookie name in Next middleware; login success UI; Jira DEVOPS-487; commit; Done transition |
| DEVOPS-487 | bugfix | 2026-04-02 16:10 | 2026-04-02 17:01 | 51m | Root cause 2: cross-origin cookie; added Next.js proxy for /api/*; both api clients use relative /api default |
| DEVOPS-487 | bugfix | 2026-04-02 17:01 | 2026-04-02 17:33 | 32m | Root cause 3: BACKEND_INTERNAL_URL baked as Docker build arg so proxy routes to backend:8000 not localhost:8000 |
| adhoc | implementation | 2026-04-02 17:40 | 2026-04-02 17:50 | 10m | Remove environment field from admin UI; add manual sync trigger button |
| adhoc | implementation | 2026-04-02 18:05 | 2026-04-02 18:35 | 30m | Pipeline visibility: app logging, sync status in-progress, admin poll |
| adhoc | bugfix | 2026-04-02 17:51 | 2026-04-02 17:53 | 2m | Jira Cloud: use Basic auth (email+API token) via JIRA_USER_EMAIL / admin api_user_email; RuntimeConfig.jira_user_email |
| DEVOPS-489 | implementation | — | — | 40m | Jira worklog booked (same scope as adhoc 17:40–17:50 10m + 18:05–18:35 30m); subtask of DEVOPS-488; Done |
| DEVOPS-489 | commit | 2026-04-02 18:08 | 2026-04-02 18:08 | 0m | Git commit and push to origin/main |
| DEVOPS-490 | implementation | 2026-04-02 18:14 | 2026-04-02 18:17 | 3m | Collector progress logging; Jira worklog 3m; subtask of DEVOPS-488; Done |
| adhoc | bugfix | 2026-04-02 18:30 | 2026-04-02 18:31 | 1m | docker-compose: explicit DORA_LOG_LEVEL interpolation; .env.docker.example note |
| adhoc | bugfix | 2026-04-02 18:33 | 2026-04-02 18:35 | 2m | app logger StreamHandler stderr so docker logs show pipeline/collector INFO |
| adhoc | bugfix | 2026-04-02 18:40 | 2026-04-02 18:41 | 1m | Jira JQL per-page logs + sync phase=jira_start; gitlab collector start line |
| adhoc | implementation | 2026-04-02 18:42 | 2026-04-02 18:44 | 2m | JQL hard floor created >= 2023-01-01 for production bugs |
| adhoc | implementation | 2026-04-02 18:46 | 2026-04-02 18:47 | 1m | Sync floor 2024-01-01 Jira + GitLab MR/commits; sync_data_floor module |
| adhoc | investigation | 2026-04-02 18:16 | 2026-04-02 18:21 | 5m | DB table counts and latest timestamps (Docker backend + db) |
| DEVOPS-491 | implementation | — | — | 12m | Jira worklog (compose/logging/JQL/sync floor/investigation); Bug Subtask DEVOPS-488; Done |
| DEVOPS-491 | commit | 2026-04-02 18:50 | 2026-04-02 18:51 | 1m | Git commit and push to GitLab |
| adhoc | bugfix | 2026-04-02 18:53 | 2026-04-02 18:57 | 4m | GitLab monitored path: dev/plunet like POC; configuration.yml + env examples; YAML project_path coercion |
| DEVOPS-429 | implementation | 2026-04-02 19:15 | 2026-04-02 19:23 | 8m | Docker pipeline: fix empty DB project_paths override, stale nightly running rows, sync status + frontend types; GitLab dev/plunet default; Jira hydrate 404 skip |
| adhoc | implementation | 2026-04-14 12:07 | 2026-04-14 12:20 | 13m | Implement dual-display deployment frequency UX for sparse data |
| adhoc | investigation | 2026-04-14 12:20 | 2026-04-14 12:28 | 8m | Fix current metric endpoint picking up incomplete current-week windows |
| adhoc | implementation | 2026-04-14 12:28 | 2026-04-14 13:16 | 48m | Update backend metrics public service to aggregate the entire active period rather than just the latest bucket |
