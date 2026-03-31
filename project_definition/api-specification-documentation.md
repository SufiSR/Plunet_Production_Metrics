# API Specification - Documentation

- Source URL: https://plunet.atlassian.net/wiki/spaces/EN/pages/768901161/API+Specification+-+Documentation
- Confluence Page ID: `768901161`

## Base URL

`http://{host}:{port}/api`

## Endpoints

- `GET /metrics/current` - Current aggregated metrics with DORA levels
- `GET /metrics/history` - Historical series (paginated)
- `GET /metrics/repository/{id}` - Repository-specific current metrics
- `GET /repositories` - Monitored repositories
- `GET /sync/status` - Last sync status
- `GET /health` - Health check

## Query Parameters

### `/metrics/history`
- `periodType`: `WEEK | MONTH | QUARTER`
- `from`, `to`: ISO dates
- `repositoryId`: optional
- `page`, `size`: pagination

### `/repositories`
- `active`: optional boolean filter

## Error Format

Unified error response with:
- `error`
- `message`
- `timestamp`

## Data Types

### Trend
- `UP`
- `DOWN`
- `STABLE`

### Sync Status
- `SUCCESS`
- `PARTIAL_FAILURE`
- `FAILED`

### Performance Level
- `ELITE`
- `HIGH`
- `MEDIUM`
- `LOW`

## DORA Performance Classification

Level thresholds are based on DORA report ranges for:
- Deployment Frequency
- Lead Time
- Change Failure Rate
- MTTR

Overall level is the lowest level among the four metrics.

