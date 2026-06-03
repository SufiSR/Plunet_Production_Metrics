# Pipeline and Metrics Deep Dive

This document describes the implemented data pipelines and metric/report semantics for the current engineering analytics platform.

The platform has three main ingestion paths:

- DORA nightly pipeline: GitLab + Jira production-bug data, derivations, and DORA snapshots.
- Jira Analytics sync: Jira warehouse, workflow, allocation, feature, and report inputs.
- HRWorks sync: roster and capacity data used by team reports.

## 1) DORA Pipeline Orchestration

Main function: `run_nightly_sync`.

Runtime phases:

- `gitlab`
- `jira`
- `derivations`
- `snapshots`
- `complete`

The orchestrator writes a `sync_log` row with `source=nightly` and stores phase state in `details_json.pipeline_runtime`. Each phase transitions through `pending`, `running`, and a terminal state such as `success`, `failed`, or `skipped`.

Status outcomes:

- `success`: GitLab and Jira collectors succeeded and derivations completed.
- `partial_failure`: one collector failed/skipped, or derivations failed.
- `failed`: both collectors failed/skipped, or orchestration crashed.

Snapshot gating:

- DORA snapshots are skipped when derivation errors exist so stale or partially-derived relationships are not published as fresh metrics.

## 2) DORA GitLab Collector

Main function: `collect_gitlab_tags_and_releases`.

### Repository Mapping

Source: GitLab project API.

Mapped into `repository`:

- GitLab project id -> `repository.id` and `repository.gitlab_id`.
- Project name -> `repository.name`.
- `path_with_namespace` -> `repository.path`.
- Default branch -> `repository.default_branch`.
- Repository is marked active.

### Release Mapping

Source: project repository tags.

For each valid tag:

- Tag name -> `release.tag_name`.
- Commit SHA -> `release.commit_sha`.
- Commit date -> `release.committed_at`.
- Parsed semantic version fields -> `version_major`, `version_minor`, `version_patch`, `pre_release`.
- `customer_release` is true unless the tag matches configured non-customer release markers such as `rc` or `beta`.

Reconciliation:

- Tags no longer present in GitLab are removed from `release`.
- Related `bug_release` links are removed before deleting releases.
- A safety guard avoids destructive reconciliation when a fetched tag set appears incomplete.

### Merge Request Mapping

Source: merged merge requests for configured target branches.

Mapped into `merge_request`:

- GitLab MR id, title, description, author, source/target branch.
- Timestamps such as `created_at` and `merged_at`.
- Commit references such as head, merge, and squash commit SHA.
- `effective_commit_sha`: first available merge commit, squash commit, or head SHA.
- Jira key extracted from title, branch, or description.
- `jira_key_source` to explain where the key came from.

If the Jira key changes on upsert, `jira_ready_for_qa_at` is reset to avoid stale lead-time linkage.

### First Commit Enrichment

For each relevant MR:

- Fetch MR commits.
- Parse commit dates.
- Store the earliest valid date as `merge_request.first_commit_at`.

### MR to First Customer Release

For each MR with an `effective_commit_sha`:

- Fetch GitLab tag refs attached to the SHA.
- Keep refs corresponding to customer releases in the database.
- Keep only releases whose commit date is at or after the MR merge date.
- Select the earliest eligible release.

Derived fields:

- `first_customer_tag`
- `first_customer_tag_date`
- `release_wait_time_hours`
- `lead_time_hours`

Lead-time match statuses include:

- `matched`
- `first_commit_missing`
- `no_effective_commit_sha`
- `no_tag_ref_found`
- `no_customer_tag_ref_found`
- `no_customer_tag_after_merge`

## 3) DORA Jira Collector

Main function: `collect_jira_production_bugs`.

### Issue Selection

JQL filters include:

- Issue type in Bug/Bug Subtask.
- Created after the global sync floor.
- Updated within configured lookback.
- Optional project exclusions from configuration.

### Production Bug Mapping

For each issue, the collector upserts `production_bug`:

- `jira_key`
- Summary, issue type, status, priority.
- Versions, fixVersions, components, parent metadata, and configured custom fields.
- Created, updated, and closed timestamps.
- Health and quality flags.
- Ready-for-QA timestamp from changelog transitions.
- Total worklog seconds.

MTTR base calculation:

- `mttr_minutes = floor((closed_at - created_at) / 60)` when dates are valid.

### Worklog Mapping

Issue worklogs are synchronized into `issue_worklog`:

- Existing rows are updated by Jira worklog id.
- New worklogs are inserted.
- Removed worklogs are deleted.

### Ready-for-QA Hydration for Non-Bug Keys

Function: `hydrate_merge_request_jira_ready_for_qa`.

Purpose:

- For MR Jira keys not represented by `production_bug.ready_for_qa_at`.
- Fetch changelog and write `merge_request.jira_ready_for_qa_at`.

## 4) DORA Derivations

Derivations run only when both DORA collectors have sufficient source data.

### Bug to Release Linking

Function: `_map_bugs_to_releases`.

Logic:

- Normalize release tags so `v1.2.3` and `1.2.3` are treated as equivalent.
- Match production-bug affected versions to release tags.
- Recreate links per bug.

### MTTR Alpha Fix Release Resolution

Function: `_resolve_mttr_alpha_fix_releases`.

Eligibility:

- `production_bug.healthy = true`.
- Priority is in configured `jira.mttr_alpha_priorities`.

Resolution order:

1. MR linkage through `merge_request.jira_key` and earliest `first_customer_tag_date`.
2. Fallback to bug fixVersions matching release tags.

Derived fields:

- `first_fix_release_tag`
- `first_fix_release_date`
- `mttr_alpha_resolution_path`
- `mttr_alpha_minutes`

### Lead Post-Production

Function: `_compute_lead_post_production`.

For merge requests in lookback:

- Choose `ready_at` from `production_bug.ready_for_qa_at` or `merge_request.jira_ready_for_qa_at`.
- If missing, or if merge happened before Ready for QA, result is null.
- Otherwise store `lead_post_production_hours`.

## 5) DORA Snapshot Generation

Function: `refresh_snapshots`.

Windows are built for:

- `WEEK`
- `MONTH`
- `QUARTER`

Window bounds use UTC `[start, end)` semantics.

For each repository and window:

- Calculate metric values through `calculate_period_metrics`.
- Delete the existing snapshot for `(repository_id, period_type, period_start)`.
- Insert a fresh `metric_snapshot` row.

Fields include:

- Deployment frequency.
- Median lead time.
- Median dev/review time.
- Median release-wait time.
- Change failure rate.
- MTTR and MTTR Alpha medians.
- Lead post-production median.
- Lead-time sample count and match counts.

## 6) DORA Metric Formulas

### Deployment Frequency

Population:

- Customer releases for repository in the period.

Formula:

- `deployment_freq_per_week = release_count / number_of_weeks_in_period`, rounded to 4 decimals.

### Lead Time

Population:

- Repository MRs with `lead_time_hours`.
- `first_customer_tag_date` inside the period.
- Optional exclusion of release-only MRs based on configured title/source branch markers.

Formula:

- Median of `lead_time_hours * 60`, rounded to nearest minute.

### Release Wait

Same cohort as lead time, using `release_wait_time_hours`.

Formula:

- Median of hours * 60, rounded to nearest minute.

### Dev/Review Time

Same cohort as lead time, requiring both lead time and release wait.

Per row:

- `delta = lead_time_hours - release_wait_time_hours`.
- Keep non-negative deltas.

Formula:

- Median of `delta * 60`, rounded to nearest minute.

### Change Failure Rate

Denominator:

- Eligible customer releases in the period for repository.

Numerator:

- Distinct denominator releases linked through `bug_release` to CFR-eligible production bugs.

Formula:

- `failed_release_count / total_release_count`, rounded to 4 decimals.
- Returns zero when denominator is zero.

### MTTR

Population:

- Healthy production bugs.
- Valid Jira created timestamp.
- `closed_at` inside the period.
- `mttr_minutes` present.

Formula:

- Median of `mttr_minutes`.

### MTTR Alpha

Population:

- Healthy production bugs.
- Valid Jira created timestamp.
- `first_fix_release_date` inside the period.
- `mttr_alpha_minutes` present.

Formula:

- Median of `mttr_alpha_minutes`.

### Lead Post-Production

Population:

- Repository MRs with `first_customer_tag_date` in the period.
- `lead_post_production_hours` present.

Formula:

- Median of `lead_post_production_hours * 60`.

## 7) Jira Analytics Sync

Main function: `run_jira_analytics_sync`.

Purpose:

- Maintain a reporting warehouse from Jira issue, worklog, field, sprint, relation, user, and workflow data.
- Refresh derived feature, workflow, allocation, and data-quality inputs used by analytics reports.

Scheduling:

- Controlled by `jira_analytics.sync_cron_hour` and `jira_analytics.sync_cron_minute`.
- Scheduled runs use `jira_analytics.scheduled_lookback_days`.
- Manual admin triggers can override lookback.

Major data groups:

- Projects and issues.
- Issue details and field values.
- Worklogs.
- Sprints and issue-sprint membership.
- Issue relations.
- Status transitions.
- Users.
- Workflows and workflow status classifications.

Derived/normalization responsibilities:

- Project scoping for analytics.
- Feature root and feature membership resolution.
- Feature family membership and suggestions.
- Topic classification for worklogs and issues.
- Workflow normalization and status condensation.
- Waiting, active/passive, and thrash calculations.
- Monthly allocated effort and monthly topic effort bases.
- Data-quality checks and drilldowns.

Allocation behavior:

- Jira worklog effort is mapped to users, roles, teams, topics, features, feature families, customers, and investment categories.
- User/team/role assignment tables provide the source of truth for organizational attribution.
- Allocation can be rebuilt from admin endpoints when rules or source data change.

## 8) HRWorks Sync

Main function: `run_hrworks_sync`.

Purpose:

- Import HRWorks person roster.
- Import monthly available hours for historical and forecast windows.
- Provide capacity denominators for team utilization and forecast reports.

Scheduling:

- Weekly by default, controlled by `hrworks.sync_cron_day_of_week`, `hrworks.sync_cron_hour`, and `hrworks.sync_cron_minute`.

Configuration:

- `hrworks.backfill_start_date` for initial history.
- `hrworks.incremental_months_back` and `hrworks.incremental_forecast_months` for scheduled refreshes.
- `hrworks.roster_refresh_hours` for roster refresh cadence.
- `hrworks.denied_person_ids` to exclude technical or invalid accounts.

Outputs:

- `hrworks_person_roster`.
- `jira_user_monthly_hrworks_hours`.

## 9) Jira Analytics Report Families

### Portfolio Investment

Uses monthly allocation and topic classification to explain where capacity went:

- Investment categories.
- Feature investment ranking.
- Feature investment audit with issue/worklog drilldowns and Excel export.
- Investment by theme.

### Features

Uses feature roots, memberships, families, worklogs, and delivery metadata:

- Feature worklog hours matrix.
- Feature-family hours matrix.
- Issues without feature.
- Feature delivery risk.

### Flow

Uses feature lifecycle fields, issue dates, status categories, and derived timelines:

- Lifecycle funnel.
- Promised vs actual.
- Idea aging.
- Size vs speed.
- Roadmap reliability.

### Bottlenecks

Uses status transitions and workflow classifications:

- Status waiting time.
- Active vs passive time.
- Active/passive trend.
- Workflow thrashing.

### Teams

Uses assignments, roles, HRWorks capacity, Jira worklogs, and completion signals:

- Work allocation heatmap.
- Planned vs unplanned.
- Availability vs booked.
- Capacity forecast.
- Real interruption ratio.
- Throughput stability.
- Bus factor.
- Engineering health index.
- Team comparison.

### Customers

Uses issue/customer attribution and effort allocation:

- Customer effort.

### Data Quality

Checks whether analytics outputs are trustworthy:

- Missing or weak mappings.
- Unclassified effort.
- User-level drilldowns.
- Ignore/unignore support for accepted exceptions.

## 10) Freshness and Frontend Status

The frontend uses sync data to show:

- Latest DORA sync status and phase runtime.
- HRWorks latest sync.
- Jira Analytics latest sync.
- Ingestion progress and error states.
- Dashboard stale/failure banners.
- Admin operations status cards.

DORA public freshness comes from `/api/sync/status`. Jira Analytics and HRWorks latest sync state is exposed through admin endpoints.

## 11) Rebuild and Recovery Operations

Available operational actions:

- Trigger DORA sync.
- Trigger Jira Analytics sync.
- Trigger HRWorks sync.
- Rebuild Jira Analytics allocation.
- Inspect raw table data.
- Inspect data-health and data-quality warnings.

Typical recovery path:

1. Check admin overview and latest sync logs.
2. Review ingestion-specific progress/errors.
3. Fix configuration, credentials, or source mapping.
4. Re-run the affected sync.
5. Rebuild allocation if assignment/rule/source changes affect derived analytics.
6. Validate data quality before relying on reports.
