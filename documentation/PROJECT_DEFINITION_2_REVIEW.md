# Review of `project_definition_2`

`project_definition_2/` is historical context for the original DORA metrics application. It should not be treated as the source of truth for the current engineering analytics platform.

The current implementation reference is:

- `README.md`
- `documentation/APPLICATION_DOCUMENTATION.md`
- `documentation/PIPELINE_AND_METRICS_DEEP_DIVE.md`

## Status Legend

- `Useful`: still valuable for product or domain intent.
- `Partially Outdated`: contains relevant ideas, but implementation details or scope have drifted.
- `Outdated`: historical only; do not use for implementation or endpoint/schema decisions.

## File-by-File Review

- `README.md` -> `Outdated`
  The index is still useful for locating old planning files, but it describes the former DORA-only project rather than the current platform.

- `dora-metrics-app-documentation.md` -> `Partially Outdated`
  DORA product intent and KPI framing remain useful. Architecture, routes, admin behavior, and scope are now superseded by the current docs.

- `backend-components-documentation.md` -> `Partially Outdated`
  Some backend concepts still map to the DORA pipeline, but the current backend now includes Jira Analytics, HRWorks, allocation, workflow, feature-family, and expanded admin modules.

- `api-specification-documentation.md` -> `Partially Outdated`
  API principles remain relevant, but the endpoint surface has expanded substantially under `/api/jira-analytics` and `/api/admin`.

- `database-schema-documentation.md` -> `Partially Outdated`
  The original DORA schema concepts remain recognizable, but the live schema has many additional Jira Analytics and HRWorks entities.

- `frontend-components-documentation.md` -> `Partially Outdated`
  UI principles and dashboard concepts are useful, but current routes now center on `/analytics` and the new `/admin` console.

- `testing-strategy-documentation.md` -> `Partially Outdated`
  The test pyramid and quality goals still apply, but coverage expectations should now include Jira Analytics, HRWorks, allocation, workflows, and admin operations.

- `new_kpis.md` -> `Useful`
  Still valuable for metric intent and leadership questions. Treat concrete implementation details as historical unless reflected in current services/tests.

- `jira-production-bug-filter-decision.md` -> `Useful`
  Still important for DORA CFR and production-bug classification rationale.

- `open-questions.md` -> `Outdated`
  Historical planning artifact. Re-validate any open question before acting on it.

- `jira-backlog-dora-metrics-app.md` -> `Outdated`
  Backlog snapshot for the old project. Do not use as the current delivery backlog.

- `Design_requirements/DESIGN_LIGHT.md` -> `Partially Outdated`
  Useful as design language inspiration, but not a strict description of current UI.

- `Design_requirements/DESIGN_DARK.md` -> `Partially Outdated`
  Useful as design language inspiration, but not a strict description of current UI.

- `Design_requirements/dora_editorial_light/DESIGN.md` -> `Partially Outdated`
  Useful style reference for the DORA/editorial look. Current analytics pages have evolved beyond this prototype.

- `Design_requirements/main_dashboard_light/code.html` -> `Outdated`
  Static prototype only.

- `Design_requirements/drilldown_light/code.html` -> `Outdated`
  Static prototype only.

- `Design_requirements/admin_config_light/code.html` -> `Outdated`
  Static prototype for the old admin config experience.

## Practical Guidance

Use `project_definition_2/` for:

- Understanding why the original DORA app was built.
- Recovering KPI/domain rationale.
- Reviewing old design language ideas.
- Comparing current implementation against earlier product intent.

Do not use it for:

- Current API endpoint lists.
- Current database schema.
- Current frontend route/component structure.
- Current scheduler behavior.
- Current repository publishing decisions.

When a conflict exists, current code and the files in `documentation/` win.
