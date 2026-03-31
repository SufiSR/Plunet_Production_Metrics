# Database Schema - Documentation

- Source URL: https://plunet.atlassian.net/wiki/spaces/EN/pages/770015256/Database+Schema+-+Documentation
- Confluence Page ID: `770015256`

## ER Diagram

```
┌─────────────────┐       ┌─────────────────────┐
│   repository    │       │       release       │
├─────────────────┤       ├─────────────────────┤
│ id (PK)         │       │ id (PK)             │
│ gitlab_id       │◄──────┤ repository_id (FK)  │
│ name            │       │ tag_name            │
│ path            │       │ version_major       │
│ default_branch  │       │ version_minor       │
│ active          │       │ version_patch       │
│ created_at      │       │ pre_release         │
│ updated_at      │       │ commit_sha          │
└─────────────────┘       │ created_at          │
                          └─────────────────────┘
                                    │
                                    ▼
┌─────────────────┐       ┌─────────────────────┐
│  merge_request  │       │   release_commit    │
├─────────────────┤       ├─────────────────────┤
│ id (PK)         │       │ release_id (FK, PK) │
│ repository_id   │       │ commit_sha (FK, PK) │
│ gitlab_mr_id    │       └─────────────────────┘
│ title           │                 ▲
│ source_branch   │                 │
│ merged_at       │       ┌─────────────────────┐
│ commit_sha      │───────┤       commit        │
│ created_at      │       ├─────────────────────┤
└─────────────────┘       │ sha (PK)            │
                          │ repository_id (FK)  │
                          │ author              │
                          │ committed_at        │
                          │ created_at          │
                          └─────────────────────┘

┌─────────────────────┐       ┌─────────────────────┐
│   production_bug    │       │     bug_release     │
├─────────────────────┤       ├─────────────────────┤
│ id (PK)             │◄──────┤ bug_id (FK, PK)     │
│ jira_key            │       │ release_id (FK, PK) │
│ summary             │       └─────────────────────┘
│ created_at          │
│ closed_at           │
│ mttr_minutes        │
└─────────────────────┘

┌─────────────────────┐
│   metric_snapshot   │
├─────────────────────┤
│ id (PK)             │
│ repository_id (FK)  │
│ period_start        │
│ period_end          │
│ period_type         │
│ deployment_freq     │
│ lead_time_minutes   │
│ change_failure_rate │
│ mttr_minutes        │
│ created_at          │
└─────────────────────┘
```

## Table Descriptions

### repository
All GitLab projects being monitored.

### release
Every tag on a protected branch (minor + patch releases).

### commit
Commits on the main branch.

### release_commit
Maps which commits are included in which release (n:m).

### merge_request
Merged merge requests for lead time calculation.

### production_bug
Jira bugs with populated "External Ticket Links" field.

### bug_release
Maps bugs to affected releases (n:m).

### metric_snapshot
Pre-calculated metrics per time period for fast dashboard queries.

### sync_log
Monitoring of daily synchronization jobs.

## Data Retention Policy

| Data | Retention | Rationale |
| --- | --- | --- |
| Raw data (commits, MRs)  | 2 years  | Enables trend analysis and traceability  |
| Releases, bugs  | Unlimited  | Low volume, high value for history  |
| Metric snapshots  | Unlimited  | Very compact, basis for long-term dashboards  |

## RC Release Handling

| Metric | RC Releases |
| --- | --- |
| Deployment Frequency  | Excluded  |
| Lead Time for Changes  | Excluded (first "real" tag counts)  |
| Change Failure Rate  | Excluded  |
| MTTR  | Not affected (based on bugs, not releases)  |

