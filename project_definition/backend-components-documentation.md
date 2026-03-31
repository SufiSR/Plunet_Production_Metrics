# Backend Components - Documentation

- Source URL: https://plunet.atlassian.net/wiki/spaces/EN/pages/768573469/Backend+Components+-+Documentation
- Confluence Page ID: `768573469`

## Component Overview

Spring Boot backend with collectors, services, REST API, infrastructure utilities, and Spring Data repository layer connected to PostgreSQL.

## Collectors

### GitLabCollector
- `syncRepositories()`
- `syncTags()`
- `syncMergeRequests()`
- `syncCommits()`
- `mapCommitsToReleases()`

### JiraCollector
- `syncProductionBugs()`
- `mapBugsToReleases()`
- `calculateMTTR()`

## Services

### MetricService
- `calculateDeploymentFrequency()`
- `calculateLeadTime()`
- `calculateChangeFailureRate()`
- `calculateMTTR()`

### SnapshotService
- `generateSnapshots()`
- `generateRepositorySnapshots()`
- `generateAggregatedSnapshots()`

### ReleaseService
- `parseVersion()`
- `isPreRelease()`
- `getCommitsForRelease()`

### BugService
- `isProductionBug()`
- `getAffectedReleases()`

## Scheduler

Nightly schedule at `02:00` runs GitLab and Jira collectors independently, then generates snapshots if at least one collector succeeds, logs the run, and emits webhook notifications.

## Error Handling

- Collectors execute independently.
- One collector failure does not stop others.
- Snapshot generation can still proceed with partial success.
- Results are persisted and notified.

## Webhook Notifications

### Event Types
- `SYNC_SUCCESS`
- `SYNC_PARTIAL_FAILURE`
- `SYNC_COMPLETE_FAILURE`

Payloads include per-collector outcomes, processed-record counts, and error details.

## Retry Strategy

- Exponential backoff retries (default max retries: 3).
- Retryable: `429`, `5xx`, timeouts.
- Non-retryable: `401`, `404`, `400`.

## REST API

- `GET /api/metrics/current`
- `GET /api/metrics/history`
- `GET /api/metrics/repository/{id}`
- `GET /api/repositories`
- `GET /api/health`
- `GET /api/sync/status`

## Configuration

`application.yml` includes GitLab/Jira credentials, sync cron, initial load date, retry behavior, webhook options, and data retention settings.

## Initial Data Load

Historical import starts from `2025-01-01` automatically on first scheduled run.

