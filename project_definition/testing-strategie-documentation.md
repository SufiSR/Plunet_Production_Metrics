# Testing-Strategie - Documentation

- Source URL: https://plunet.atlassian.net/wiki/spaces/EN/pages/771489795/Testing-Strategie+-+Documentation
- Confluence Page ID: `771489795`

## Test Pyramid

- Unit tests (many)
- Integration tests (medium)
- E2E tests (few)

## Backend Tests (Java/Spring Boot)

### Unit Tests
Coverage includes metric calculations, release parsing, production bug classification, snapshot generation, and retry logic.

### Integration Tests
Coverage includes collectors, repository layer, REST API, and webhook notifier with WireMock and Testcontainers.

### Test Data
Fixtures include repositories, releases (with RC), merge requests, and production bugs.

## Frontend Tests (Vue)

### Unit Tests (Vitest)
Component rendering, trend/color logic, selector behavior, theme persistence, store actions, and metric explanation completeness.

### Component Tests
Composition and interaction checks for cards, charts, modal, and header.

### E2E Tests (Playwright)
Scenarios include dashboard load, period changes, theme toggle, metric detail modal, and embed mode behavior.

## E2E Environment

Runs against Docker Compose test stack in local and CI contexts.

Typical flow:
1. Start test environment
2. Wait for health checks
3. Seed test data
4. Run Playwright
5. Tear down environment

## Developer Commands

```shell
npm run e2e:setup
npm run e2e
npm run e2e:teardown
npm run e2e:full
```

## Tooling

Backend: Spring Boot test, Testcontainers, WireMock.  
Frontend: Vitest, Vue Test Utils, Playwright.

## Coverage Goals

- Backend unit tests: `>= 80%`
- Backend integration: all endpoints
- Frontend unit tests: `>= 70%`
- Frontend E2E: all main scenarios

## CI Integration

Pipeline stages: Build -> Unit -> Integration -> E2E -> Coverage/Quality gate.

