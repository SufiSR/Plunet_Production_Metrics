# DORA Metrics Server

Monorepo baseline for the DORA Metrics application.

## Structure

- `backend/` - Python backend (FastAPI, scheduler, collectors)
- `frontend/` - Next.js frontend dashboard
- `project_definition_2/` - active architecture, API, schema, and testing reference

## Specification Reference

Implementation and product semantics are documented in `project_definition_2/`, especially:

- `project_definition_2/README.md`
- `project_definition_2/dora-metrics-app-documentation.md`
- `project_definition_2/backend-components-documentation.md`
- `project_definition_2/api-specification-documentation.md`
- `project_definition_2/database-schema-documentation.md`
- `project_definition_2/frontend-components-documentation.md`
- `project_definition_2/testing-strategy-documentation.md`
- `project_definition_2/new_kpis.md`

## MVP Delivery Note

For MVP, local lint/test checks are required before push/merge. Mandatory CI pipeline gates are deferred to Phase 2 (`DEVOPS-445`).
Containerization (`Dockerfile` / `docker-compose.yml`) is tracked separately in `DEVOPS-443`.
