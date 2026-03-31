# Testing Strategy – Documentation

## Test Pyramid

```
                    ┌───────────┐
                    │    E2E    │   Playwright
                    │   Tests   │
                    └─────┬─────┘
                          │ few
                    ┌─────┴─────┐
                    │Integration│   pytest + respx + testcontainers-python
                    │   Tests   │
                    └─────┬─────┘
                          │ medium
                    ┌─────┴─────┐
                    │   Unit    │   pytest + Jest/Vitest + React Testing Library
                    │   Tests   │
                    └───────────┘
                          │ many
```

---

## Backend Tests (Python)

### Tooling

| Tool | Purpose |
| --- | --- |
| `pytest` | Test runner |
| `pytest-asyncio` | Async test support |
| `httpx.AsyncClient` + `respx` | Mock external HTTP calls (GitLab, Jira) |
| `testcontainers-python` | Spin up real PostgreSQL for integration tests |
| `factory-boy` | Test fixture factories for ORM models |
| `coverage.py` | Code coverage reporting |
| `ruff` | Linting (replaces flake8 + isort) |
| `mypy` | Static type checking |

### Unit Tests

Location: `backend/tests/unit/`

| Module | What Is Tested |
| --- | --- |
| `metric_service` | All 4 DORA metric calculations, edge cases |
| `release_service` | Version parsing, RC detection, commit resolution |
| `bug_service` | Production bug identification, affected release mapping |
| `snapshot_service` | Snapshot generation logic, period boundary handling |
| `nightly_sync` | **Order of operations**: GitLab → first_commit → lead map → Jira → bug_release → **resolve_mttr_alpha** → snapshots; partial failure policies |
| `auth` / `admin_config` | Login success/failure; **401** on unauthenticated `PATCH /admin/config`; secrets never echoed in responses |
| `retry_handler` | Tenacity backoff decisions, retryable vs non-retryable errors |

**Example test cases – `metric_service`:**

| Test | Description |
| --- | --- |
| `test_deployment_frequency_excludes_rc` | RC releases not counted |
| `test_deployment_frequency_empty_period` | Returns `0.0` when no releases |
| `test_lead_time_multiple_commits` | Averages across multiple MRs |
| `test_change_failure_rate_no_releases` | Returns `0.0`, no division by zero |
| `test_mttr_no_bugs` | Returns `None` when no closed bugs |

**Example test cases – `release_service`:**

| Test | Description |
| --- | --- |
| `test_parse_version_major_minor_patch` | Parses `"2.3.1"` to `(2, 3, 1, None)` |
| `test_parse_version_with_rc` | Parses `"2.3.0-RC1"` to `(2, 3, 0, "RC1")` |
| `test_parse_version_invalid_format` | Raises `ValueError` for malformed tag |
| `test_is_pre_release_rc` | Returns `True` for RC version |
| `test_is_pre_release_stable` | Returns `False` for stable version |

### Integration Tests

Location: `backend/tests/integration/`

Uses `testcontainers-python` to start a real PostgreSQL 16 container. Alembic migrations are applied before each test session.

| Component | What Is Tested | Mocking |
| --- | --- | --- |
| `GitLabCollector` | API pagination, tag/MR/commit mapping | `respx` (mock GitLab HTTP) |
| `JiraCollector` | Bug fetching, Affects Versions mapping | `respx` (mock Jira HTTP) |
| ORM / repository layer | JPA queries, FK constraints, upsert behaviour | Real PostgreSQL |
| FastAPI endpoints | Request/response contracts, pagination, 404 | `httpx.AsyncClient` via `pytest` |
| WebhookNotifier | HTTP POST is sent with correct payload | `respx` |

**Example test cases – `GitLabCollector`:**

| Test | Description |
| --- | --- |
| `test_sync_tags_maps_correctly` | Tags correctly map to `Release` entities |
| `test_sync_tags_handles_rate_limit` | Retries on HTTP 429 |
| `test_sync_tags_handles_pagination` | All pages of results are fetched |

**Example test cases – FastAPI endpoints:**

| Test | Description |
| --- | --- |
| `test_get_current_metrics_returns_all_four` | Response contains all 4 metrics |
| `test_get_current_metrics_includes_level` | `overall_performance_level` is present |
| `test_get_history_pagination` | Pagination fields are correct |
| `test_get_history_invalid_period_type` | Returns 422 Unprocessable Entity |
| `test_get_repository_metrics_not_found` | Returns 404 for unknown ID |

### Test Fixtures

```python
# tests/factories.py using factory-boy
class RepositoryFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Repository
        sqlalchemy_session_persistence = "commit"

    gitlab_id = factory.Sequence(lambda n: n + 100)
    name = factory.Faker("slug")
    path = factory.LazyAttribute(lambda o: f"group/{o.name}")
    default_branch = "main"
    active = True
```

### Running Backend Tests

```shell
# All tests
pytest backend/tests/

# Unit only (fast, no containers)
pytest backend/tests/unit/

# Integration only
pytest backend/tests/integration/

# With coverage
pytest --cov=app --cov-report=html backend/tests/
```

---

## Frontend Tests (Next.js / React)

### Tooling

| Tool | Purpose |
| --- | --- |
| `Jest` + `ts-jest` | Test runner |
| `@testing-library/react` | Component rendering + user interactions |
| `@testing-library/user-event` | Realistic user event simulation |
| `msw` (Mock Service Worker) | Mock API calls in tests |
| `jest-environment-jsdom` | Browser-like environment |
| `Playwright` | E2E tests |

### Unit Tests

Location: `frontend/tests/unit/`

| Component / Module | What Is Tested |
| --- | --- |
| `MetricCard` | Value display, trend arrow color, performance badge |
| `PeriodSelector` | Dropdown options render, onChange fires |
| `ThemeToggle` | Theme switch, localStorage write |
| `ui-store` (Zustand) | State mutations for period, theme, modal |
| `metric-explanations.ts` | All 4 metrics have complete copy |
| `dora-levels.ts` | Classification thresholds for all metrics |

**Example test cases – `MetricCard`:**

| Test | Description |
| --- | --- |
| `renders value and unit` | Shows `4.2 deploys / week` |
| `shows up trend in green` | Upward trend indicator is green |
| `shows down trend in red` | Downward trend indicator is red |
| `shows correct level badge color` | `HIGH` renders green badge |
| `emits click to open modal` | Clicking card triggers `onClick` |

### Component Tests

Location: `frontend/tests/components/`

| Component | What Is Tested |
| --- | --- |
| `MetricCards` | Renders 4 cards from mock data |
| `TrendChart` | Chart renders, metric toggle hides/shows lines |
| `MetricDetailModal` | Opens on click, closes on X, displays content |
| `HeaderBar` | Child components render, period select propagates |

### Running Frontend Tests

```shell
# Unit + component tests
npm run test

# Watch mode
npm run test:watch

# Coverage
npm run test:coverage
```

---

## E2E Tests (Playwright)

Location: `frontend/tests/e2e/`

| Scenario | Description |
| --- | --- |
| Dashboard loads | Page opens, all 4 metric cards visible |
| Period change | Switch to Monthly, chart data re-fetches |
| Theme toggle | Dark mode activates, background color changes |
| Metric detail modal | Click a card, modal opens with explanation |
| Modal close | Press Escape or click X, modal closes |
| Repository filter (Phase 2) | Select repo, cards update to repo-specific values |
| Embed mode | `/embed` route shows no header or footer |

### E2E Environment

E2E tests run against a local Docker Compose test environment with mocked GitLab/Jira APIs.

```
┌──────────────────────────────────────────────────────────────┐
│  Local / CI Environment                                       │
│                                                               │
│  docker-compose.test.yml:                                     │
│  ├── db (PostgreSQL 16)     ← fresh volume per run           │
│  ├── backend (FastAPI)      ← pre-seeded test data           │
│  ├── frontend (Next.js)     ← points to backend              │
│  └── mock-api (WireMock or mockoon) ← fake GitLab + Jira     │
│                                                               │
│  Playwright runs against: http://localhost:3000               │
└──────────────────────────────────────────────────────────────┘
```

### E2E Commands

```shell
# Start test environment
npm run e2e:setup

# Run Playwright
npm run e2e

# Run with UI (debug mode)
npm run e2e:ui

# Teardown
npm run e2e:teardown

# All in one
npm run e2e:full
```

---

## Code Coverage Goals

| Area | Target |
| --- | --- |
| Backend unit tests | ≥ 80% line coverage |
| Backend integration | All 6 API endpoints |
| Frontend unit tests | ≥ 70% component coverage |
| Frontend E2E | All main user scenarios |

---

## CI Pipeline Integration

```
┌──────────────────────────────────────────────────────────────┐
│  GitLab CI Pipeline                                          │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│  │  Lint   │→ │  Unit    │→ │  Integ.  │→ │  E2E         │ │
│  │ ruff    │  │  pytest  │  │  pytest  │  │  Playwright  │ │
│  │ mypy    │  │  jest    │  │  + containers│             │ │
│  │ eslint  │  │          │  │          │  │              │ │
│  └─────────┘  └──────────┘  └──────────┘  └──────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │        Coverage Report + Quality Gate                │     │
│  └─────────────────────────────────────────────────────┘     │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```
