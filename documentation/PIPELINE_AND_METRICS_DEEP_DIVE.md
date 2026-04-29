# Pipeline and Metrics Deep Dive

This document explains the exact backend pipeline behavior as implemented today, including:

- source-to-database mappings,
- derivation steps,
- snapshot generation,
- and metric calculation formulas/filters.

## 1) Pipeline orchestration (`run_nightly_sync`)

Pipeline phases in runtime state:

- `gitlab`
- `jira`
- `derivations`
- `snapshots`
- `complete`

The orchestrator writes a `sync_log` row for `source=nightly` with `details_json.pipeline_runtime`, then transitions each phase through `pending` -> `running` -> `success|failed|skipped`.

Status outcomes:

- `success`: both collectors succeeded and derivations had no errors.
- `partial_failure`: one collector failed/skipped, or derivations failed.
- `failed`: both collectors failed/skipped, or fatal crash in orchestration.

Snapshot gating rule:

- If derivation errors exist, snapshots are skipped intentionally (to avoid publishing partially-derived metrics).

## 2) GitLab collector: exact mapping

Main function: `collect_gitlab_tags_and_releases`.

### 2.1 Repository mapping

Source: `GET /projects/{path}`.

Mapped into `repository`:

- `project.id` -> `repository.id` and `repository.gitlab_id`
- `project.name` -> `repository.name`
- `project.path_with_namespace` -> `repository.path`
- `project.default_branch` -> `repository.default_branch`
- forced `repository.active = true`

### 2.2 Release mapping

Source: `GET /projects/{path}/repository/tags`.

For each valid tag:

- `tag.name` -> `release.tag_name`
- `tag.commit.id` -> `release.commit_sha`
- `tag.commit.committed_date` -> `release.committed_at`
- parsed semantic components -> `version_major`, `version_minor`, `version_patch`, `pre_release`
- `customer_release` is derived:
  - true when tag does not match configured non-customer markers (default markers include `rc` and `beta`)
  - false otherwise

Reconciliation:

- Tags no longer present in GitLab are deleted from `release`.
- Related `bug_release` links are deleted first for removed releases.
- Safety guard avoids destructive reconciliation when fetched tag count appears incomplete.

### 2.3 Merge request mapping

Source: merged MRs per configured target branches.

Mapped into `merge_request`:

- identifiers and metadata (`gitlab_mr_id`, title, description, author, branches)
- timestamps (`created_at`, `merged_at`)
- commit references (`head_sha`, `merge_commit_sha`, `squash_commit_sha`)
- `effective_commit_sha` = first non-empty of merge commit, squash commit, head SHA
- Jira key extraction from title/branch/description:
  - prefers `[ABC-123]` form,
  - fallback to first regex ticket key
- `jira_key_source` tracks where key was found

When Jira key changes on upsert:

- `jira_ready_for_qa_at` is reset to null to avoid stale linkage.

### 2.4 First commit enrichment (`merge_request.first_commit_at`)

For each relevant MR:

- fetch MR commits,
- parse all commit `committed_date`,
- keep earliest valid date as `first_commit_at`.

### 2.5 MR -> first customer release mapping

For each MR with `effective_commit_sha`:

- fetch tag refs attached to that SHA,
- keep refs that correspond to customer releases in DB,
- keep only releases with `release.committed_at >= mr.merged_at`,
- select earliest eligible release.

Derived fields:

- `first_customer_tag`
- `first_customer_tag_date`
- `release_wait_time_hours = (first_customer_tag_date - merged_at)` in hours (rounded to 2 decimals)
- `lead_time_hours = (first_commit_at - first_customer_tag_date)` in hours (rounded to 2 decimals) when first commit exists

Lead-time match statuses:

- `matched`
- `first_commit_missing`
- `no_effective_commit_sha`
- `no_tag_ref_found`
- `no_customer_tag_ref_found`
- `no_customer_tag_after_merge`

## 3) Jira collector: exact mapping

Main function: `collect_jira_production_bugs`.

### 3.1 Issue selection query

JQL constraints include:

- issue type in Bug/Bug Subtask,
- created after global sync floor,
- updated within configured lookback,
- optional project exclusions from config.

### 3.2 Production bug mapping

For each issue, upsert into `production_bug`:

- identity: `jira_key`
- descriptive fields: summary, issue type, status, priority
- classification fields: versions/fixVersions/components, parent issue metadata, custom fields
- timestamps: created, updated, closed
- quality flags:
  - `jira_created_at_valid`
  - `healthy`
  - `healthmemo`
- `ready_for_qa_at` from changelog status transitions
- `total_worklog_seconds` from issue worklogs

MTTR base calculation:

- `mttr_minutes = floor((closed_at - created_at)/60)` when created is valid and closed >= created.
- otherwise null.

### 3.3 Worklog mapping

All issue worklogs are synchronized into `issue_worklog`:

- upsert existing rows by Jira worklog id,
- insert new worklogs,
- delete removed worklogs.

### 3.4 Ready-for-QA hydration for non-bug Jira keys

Function: `hydrate_merge_request_jira_ready_for_qa`.

Purpose:

- For MR Jira keys that are not covered by `production_bug.ready_for_qa_at`,
- fetch changelog and write `merge_request.jira_ready_for_qa_at`.

## 4) Derivation phase details

Derivations run only when both collectors succeed.

### 4.1 Bug -> release linking (`bug_release`)

Function: `_map_bugs_to_releases`.

Mapping logic:

- normalize release tags (`v1.2.3` and `1.2.3` treated as equivalents),
- for each bug `affects_versions`, match release tags by normalized keys,
- recreate links per bug (old links removed first).

### 4.2 MTTR Alpha fix release resolution

Function: `_resolve_mttr_alpha_fix_releases`.

Eligibility:

- bug must be `healthy=true`
- bug priority must be in configured `jira.mttr_alpha_priorities`.

Resolution order:

1. Try MR linkage by `merge_request.jira_key` with earliest `first_customer_tag_date`.
2. Fallback to bug `fix_versions` matching release tags.

Derived fields on `production_bug`:

- `first_fix_release_tag`
- `first_fix_release_date`
- `mttr_alpha_resolution_path` (`mr_jira_key` or `fix_version`)
- `mttr_alpha_minutes = floor((first_fix_release_date - created_at)/60)` when valid; else null.

### 4.3 Lead post-production derivation

Function: `_compute_lead_post_production`.

For merge requests in lookback:

- choose `ready_at` from bug `ready_for_qa_at`, fallback to MR `jira_ready_for_qa_at`.
- if missing or `merged_at < ready_at`, result is null.
- else `lead_post_production_hours = (merged_at - ready_at)` in hours, rounded to 2 decimals.

## 5) Snapshot generation details

Function: `refresh_snapshots`.

### 5.1 Window construction

For active repositories, build windows over configured lookback for:

- `WEEK`
- `MONTH`
- `QUARTER`

Window bounds are UTC `[start, end)` semantics (`end` exclusive in SQL filtering).

### 5.2 Precomputed global MTTR values per window

For each `(period_start, period_end)` window:

- compute `mttr_minutes` and `mttr_alpha_minutes` once (global, not repository-specific),
- reuse for each repository snapshot row in that same window.

### 5.3 Snapshot row write behavior

For each repository + window:

- compute metric values via `calculate_period_metrics`,
- delete existing row for `(repository_id, period_type, period_start)`,
- insert fresh `metric_snapshot` row.

Fields written include:

- deployment frequency
- lead-time median
- dev/review median
- release-wait median
- change failure rate
- MTTR and MTTR Alpha medians
- lead post-production median
- lead-time diagnostics (`lead_time_sample_count`, `lead_time_match_counts`)

## 6) Metric formulas and filters

All calculations use UTC datetime bounds from period windows.

### 6.1 Deployment Frequency

Population:

- customer releases for repository in `[start_dt, end_dt)`.

Formula:

- `deployment_freq_per_week = release_count / number_of_weeks_in_period`
- rounded to 4 decimals.

### 6.2 Lead Time (median minutes)

Population:

- `merge_request.lead_time_hours is not null`,
- MR belongs to repository,
- `first_customer_tag_date` inside period,
- optional exclusion of release-only MRs based on title/source markers from config.

Formula:

- median of `lead_time_hours * 60`, rounded to nearest minute (half-up).

### 6.3 Release Wait (median minutes)

Same cohort filter as Lead Time, value source:

- `merge_request.release_wait_time_hours`.

Formula:

- median of hours*60, rounded to minute.

### 6.4 Dev/Review (median minutes)

Same cohort, rows requiring both:

- `lead_time_hours` and `release_wait_time_hours`.

Per row:

- `delta = lead_time_hours - release_wait_time_hours`.
- keep only `delta >= 0`.

Formula:

- median of `delta * 60`, rounded to minute.

### 6.5 Change Failure Rate (CFR)

Denominator:

- count of eligible customer releases in period for repository.

Numerator:

- distinct releases in denominator that are linked via `bug_release`
- to `production_bug` rows satisfying `cfr_eligible_production_bug_predicate()`.

Formula:

- `failed_release_count / total_release_count`, rounded to 4 decimals.
- returns `0` when denominator is zero.

### 6.6 MTTR (median minutes)

Population:

- `production_bug.healthy = true`
- `jira_created_at_valid = true`
- `closed_at` inside period
- `mttr_minutes` present

Formula:

- median of `mttr_minutes`, rounded to minute.

### 6.7 MTTR Alpha (median minutes)

Population:

- `production_bug.healthy = true`
- `jira_created_at_valid = true`
- `created_at` present
- `first_fix_release_date` inside period
- `mttr_alpha_minutes` present

Formula:

- median of `mttr_alpha_minutes`, rounded to minute.

### 6.8 Lead Post-Production (median minutes)

Population:

- repository MR rows with `first_customer_tag_date` in period
- `lead_post_production_hours` present

Formula:

- median of `lead_post_production_hours * 60`, rounded to minute.

### 6.9 Lead-time diagnostics

For the lead-time cohort:

- `lead_time_sample_count`: count where `lead_time_hours` is non-null.
- `lead_time_match_counts`: grouped counts by `lead_time_match_status`.

## 7) Freshness and sync status data exposed to frontend

The frontend status components depend on `sync_log`-derived status and snapshot metadata:

- latest nightly run status (`success`, `partial_failure`, `failed`, `running`, `crashed` mapping),
- per-phase runtime state from `details_json.pipeline_runtime`,
- `snapshots_generated` and latest snapshot timestamp.

This enables:

- stale/failure banners,
- sync status pill states,
- admin pipeline progress visualization.