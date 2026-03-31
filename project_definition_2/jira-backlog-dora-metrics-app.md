# Jira-Backlog: DORA Metrics App

Dieses Dokument dient als **Vorlage für Jira**: Epic, Stories und Subtasks können 1:1 als Vorgänge angelegt werden.  
**Epic-Name:** `DORA Metrics App`  
**Technische Referenz:** `project_definition_2/*.md`, insbesondere `dora-metrics-app-documentation.md`, `database-schema-documentation.md`, `api-specification-documentation.md`.

---

## Epic

| Feld | Inhalt |
| --- | --- |
| **Summary** | DORA Metrics App |
| **Beschreibung** | Interne Web-App zur Messung von Delivery-Metriken (GitLab + Jira): Deployment Frequency, Lead Time, Release Wait, CFR, MTTR Alpha, **Lead Post-Production** (Ready for QA → Merge), **Jira-Zeiterfassung** (Worklogs vs. Kalenderzeit), später Rework Rate. Dashboard (Next.js) mit Confluence-Embed; täglicher Sync; Admin-Konfiguration. |
| **Komponenten** (optional) | Backend · Frontend · DevOps · Daten |

---

## Story 1: Projektgrundlage & Repository

| Feld | Inhalt |
| --- | --- |
| **Summary** | Monorepo-Struktur und Tooling-Grundlagen |
| **Typ** | Story |

### Subtasks

1. Monorepo mit `backend/` (Python) und `frontend/` (Next.js) anlegen; Root-`README` verlinken auf `project_definition_2`.
2. Python: **`requirements.txt`** (PyPI / `pip install -r requirements.txt`); kein Poetry — Abhängigkeiten explizit und CI-freundlich. Optional `venv`. `ruff` + `mypy` (Konfiguration laut `testing-strategy-documentation.md`).
3. Frontend: `package.json`, ESLint, Prettier, TypeScript strict.
4. `.env.example` mit Platzhaltern (`GITLAB_*`, `JIRA_*`, `DATABASE_URL`, `DORA_ADMIN_*`, `CONFIG_ENCRYPTION_KEY`).
5. `configuration.yml`-Schema dokumentieren (oder Pydantic-Modell) für nicht-geheime Defaults.
6. **MVP-Entscheidung:** GitLab wird zunächst als Repo + Versionierung genutzt; Lint/Tests laufen lokal vor dem Push. CI-Skeleton auf MR ist optional und auf Phase 2 verschiebbar (Details Story 18).

---

## Story 2: Datenbankschema & Alembic

| Feld | Inhalt |
| --- | --- |
| **Summary** | PostgreSQL-Schema und Migrationen |
| **Typ** | Story |

### Subtasks

1. SQLAlchemy-Modelle: `repository`, `release`, `merge_request`, `production_bug`, **`issue_worklog`** (Jira gebuchte Zeiten), `bug_release`, `metric_snapshot`, `sync_log`, `app_configuration` (siehe `database-schema-documentation.md`).
2. Alembic initialisieren; erste Migration (alle Tabellen + Indizes).
3. Indizes für zeitbasierte Abfragen (`merged_at`, `committed_at`, `period_start`, …).
4. Seed optional: leere `app_configuration`-Zeile oder Migration-Hook für Defaults.
5. Testcontainers-Setup für Integrationstests (Story 17).

---

## Story 3: GitLab-Collector (Tags & Releases)

| Feld | Inhalt |
| --- | --- |
| **Summary** | GitLab: Tags und Customer-Release-Erkennung |
| **Typ** | Story |

### Subtasks

1. REST v4: Tags pro Projekt listen (Pagination); `customer_release` aus Namensmustern (`non_customer_release_markers`).
2. Version parsen (major/minor/patch, pre-release).
3. Upsert in `release` mit `commit_sha`, `committed_at`.
4. Konfiguration: `gitlab_project_paths` aus effektivem Config-Merge (Story 10).
5. Retry/Backoff (Tenacity) und Sync-Fehler in `sync_log` (Story 8).
6. Unit-Tests: RC/Beta-Ausschluss, Version-Parsing.

---

## Story 4: GitLab-Collector (Merge Requests)

| Feld | Inhalt |
| --- | --- |
| **Summary** | GitLab: MRs je Ziel-Branch |
| **Typ** | Story |

### Subtasks

1. MRs `state=merged` für `target_branches` (`master`, `9.x`, `10.x`, `11.x`); Lookback-Filter.
2. Felder: `merged_at`, `merge_commit_sha`, `squash_commit_sha`, `effective_commit_sha`, Metadaten.
3. Jira-Key-Extraktion aus Titel → Branch → Beschreibung (Regex); `jira_key_source` speichern.
4. Deduplizierung bei mehreren Branches.
5. Unit-Tests: Key-Extraktion, `effective_commit_sha`-Logik.

---

## Story 5: GitLab — first_commit_at & Lead-Time-Mapping

| Feld | Inhalt |
| --- | --- |
| **Summary** | MR: frühester Commit + erstes Customer-Release-Tag |
| **Typ** | Story |

### Subtasks

1. `GET /merge_requests/:iid/commits` paginiert; frühestes `committed_date` → `first_commit_at`.
2. `GET /repository/commits/:sha/refs?type=tag` für `effective_commit_sha`; frühestes Tag mit `customer_release=true` und `committed_date >= merged_at`.
3. Berechnung: `lead_time_hours` (first_commit → Tag), `release_wait_time_hours` (merge → Tag); `lead_time_match_status`.
4. Rate-Limiting / Cooldown zwischen Calls (POC-Erfahrung: viele MRs).
5. Integrationstests mit Mock-API (respx) oder aufgezeichneten Fixtures.

---

## Story 6: Jira-Collector (Production Bugs, Worklogs, Ready for QA)

| Feld | Inhalt |
| --- | --- |
| **Summary** | Jira: Bugs inkl. Health, Priority, **gebuchte Zeiten**, **Ready-for-QA-Zeitpunkt** |
| **Typ** | Story |

### Subtasks

1. JQL: Issue-Typen Bug / Bug Subtask, Lookback, `excluded_projects`.
2. Felder: `summary`, `status`, **`priority`**, `created`, `updated`, `resolutiondate`, `versions`, `fixVersions`, `components`, `parent`, Custom Fields Indikatoren (`cf[10114]`, `cf[10123]`).
3. Health-Evaluation gemäß `jira-production-bug-filter-decision.md` (inkl. Parent-Zweitpass wo nötig).
4. Upsert `production_bug`; optional `mttr_minutes` (Lifecycle) berechnen.
5. Pagination (`enhanced_jql` / Cursor).
6. **Worklogs:** `GET /rest/api/3/issue/{issueIdOrKey}/worklog` (paginieren falls >20 Einträge). Tabelle **`issue_worklog`**: `jira_worklog_id`, `bug_id` FK, `author`, `started`, **`time_spent_seconds`**, optional Kommentar-Hash/Länge (kein Klartext nötig). Pro Nightly-Sync: Worklogs je Issue **ersetzen** oder upserten (idempotent).
7. **`total_worklog_seconds`** auf `production_bug` als aggregierte Summe (Cache für Reports / Vergleich zur Kalenderzeit).
8. **Changelog / Ready for QA:** `GET /rest/api/3/issue/{key}/changelog` paginieren; **ersten** Übergang **zu** einem Status identifizieren, der in `configuration.yml` unter `ready_for_qa_status_names` liegt (z. B. `Ready for QA`, `Ready for test` — projektspezifisch). Ergebnis → **`ready_for_qa_at`** (UTC) auf `production_bug`. Fehlt der Status → NULL.
9. Unit-Tests: Health-Regeln; Worklog-Parsing; Changelog-Mock mit fiktivem Übergang.

---

## Story 7: Querschnitt — bug_release, MTTR Alpha & Lead Post-Production

| Feld | Inhalt |
| --- | --- |
| **Summary** | Releases mit Bugs verknüpfen; MTTR Alpha; **Lead Post-Production (Ready for QA → Merge)** |
| **Typ** | Story |

### Subtasks

1. `map_bugs_to_releases`: `affects_versions` ↔ `release.tag_name` / Version (Data-Health bei Mismatch).
2. CFR-Vorbereitung: welche Releases ≥1 healthy Bug verknüpft haben.
3. `resolve_mttr_alpha_fix_releases`: Scope `healthy=true` + Priority Critical/Blocker (konfigurierbar).
4. Pfad A: MR mit `jira_key` = Bug-Key → `first_customer_tag_date` aus MR-Mapping.
5. Pfad B: `fix_versions` → Tag-Name-Match (mit/ohne `v`); frühestes Datum.
6. Felder setzen: `first_fix_release_*`, `mttr_alpha_minutes`, `mttr_alpha_resolution_path`.
7. **Lead Post-Production:** Für jeden `merge_request` mit `jira_key`: passenden `production_bug` laden. Wenn **`ready_for_qa_at`** gesetzt: **`lead_post_production_hours`** = `merged_at - ready_for_qa_at` (Kalenderzeit bis Merge). NULL wenn kein Ready-for-QA oder kein Key-Match.
8. **Vergleich gebucht vs. gedauert (optional auf MR-Ebene):** Verhältnis **`total_worklog_seconds`** (vom Bug) zu **`merged_at - created_at`** oder zu **`merged_at - ready_for_qa_at`** als Kennzahl „effektive Arbeit vs. Wartezeit“ — Speicherung als zusätzliche Spalte oder nur in API/Export (dokumentieren).
9. Tests: beide MTTR-Pfade; Lead Post-Production mit/ohne `ready_for_qa_at`.

---

## Story 8: Nightly Sync & Scheduler

| Feld | Inhalt |
| --- | --- |
| **Summary** | APScheduler: täglicher Lauf `run_nightly_sync` |
| **Typ** | Story |

### Subtasks

1. FastAPI `lifespan`: Scheduler starten/stoppen.
2. Reihenfolge implementieren: GitLab (Tags → MRs → first_commit → Lead-Mapping) → Jira (Bugs + **Worklogs** + **Changelog/ready_for_qa_at**) → Links → MTTR Alpha → **Lead Post-Production** → Snapshots → `sync_log` → Webhook (siehe `backend-components-documentation.md`).
3. Partial-Failure-Policy: ein Collector fällt aus → anderer läuft; Snapshots nur wenn mindestens ein Collector OK; MTTR Alpha nur wenn GitLab+Jira erfolgreich (oder dokumentierte Ausnahme).
4. Konfiguration: `sync_cron_hour` / `sync_cron_minute`.
5. Logging: strukturiert, keine Secrets.
6. Optional: manueller Trigger `POST /admin/sync` (nur Admin, Story 11) — Backlog-Flag.

---

## Story 9: Metrik-Service & Snapshots

| Feld | Inhalt |
| --- | --- |
| **Summary** | KPI-Berechnung und `metric_snapshot` |
| **Typ** | Story |

### Subtasks

1. Deployment Frequency pro Periode (Woche/Monat/Quartal).
2. Lead Time / Release Wait: Median oder vereinbarte Statistik aus MR-Zeilen; optional per Branch aggregiert.
3. CFR: Anteil fehlgeschlagener Releases.
4. MTTR Alpha: Aggregation aus `mttr_alpha_minutes` (eligible Bugs).
5. **Lead Post-Production:** Median/P75 aus `lead_post_production_hours` (nur MRs mit gesetztem `ready_for_qa_at`); optional in `metric_snapshot` als eigene Spalte.
6. **Jira-Arbeitszeit vs. Kalender:** Reporting-Aggregate (z. B. Summe `total_worklog_seconds` pro Periode vs. Summe Kalenderintervalle) — für Dashboard-Tabelle oder Export; Definition mit PO abstimmen.
7. `metric_snapshot` schreiben/überschreiben für laufende und abgeschlossene Perioden; `generated_at`.
8. DORA-Level-Klassifikation (Schwellen aus `api-specification-documentation.md`).
9. Unit-Tests für Randfälle (leere Perioden, Division durch null).

---

## Story 10: Runtime-Konfiguration (Backend)

| Feld | Inhalt |
| --- | --- |
| **Summary** | Effektive Config: YAML + DB + Secrets |
| **Typ** | Story |

### Subtasks

1. Merge-Reihenfolge: Defaults → `configuration.yml` → `app_configuration` (DB) → Env-Overrides wo definiert.
2. Konfig-Keys: u. a. **`ready_for_qa_status_names`** (Liste von exakten Jira-Statusnamen für den Changelog-Parser).
3. Fernet (oder gleichwertig) für `gitlab_token_enc` / `jira_token_enc`; `CONFIG_ENCRYPTION_KEY`.
4. `config_service`: laden für Collector-Lauf; nach `PATCH` Reload oder Neustart-Dokumentation.
5. Keine Klartext-Tokens in Logs oder API-Responses (nur Hints).
6. Optional: `config_audit_log` (wer, wann, welche Keys — ohne Secret-Werte).

---

## Story 11: API — öffentliche Endpoints & Auth/Admin

| Feld | Inhalt |
| --- | --- |
| **Summary** | FastAPI: Metrics, Sync, Health, Auth, Admin-Config |
| **Typ** | Story |

### Subtasks

1. Öffentlich: `GET /metrics/current`, `/metrics/history`, `/metrics/repository/{id}`, `/repositories`, `/sync/status`, `/health` (OpenAPI wie Spezifikation).
2. Auth: `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` (Session oder JWT — Entscheidung `open-questions.md` I8).
3. Admin: `GET /admin/config` (maskiert), `PATCH /admin/config` (401 ohne Session).
4. Pydantic-Schemas; einheitliches `ErrorResponse`; 401/403/404/500.
5. CORS: Credentials für Admin-Origin; Produktion: explizite Origins.
6. OpenAPI exportieren für Reviews (optional CI).

---

## Story 12: Frontend — Dashboard (Viewer)

| Feld | Inhalt |
| --- | --- |
| **Summary** | Next.js: Hauptdashboard ohne Login |
| **Typ** | Story |

### Subtasks

1. Layout, TanStack Query, API-Client (`fetch` zu Backend-URL).
2. Metric Cards (4 Kernmetriken), Trend, DORA-Level-Anzeige.
3. Periodenwahl; Trend-Chart (`/metrics/history`).
4. Metric-Detail-Modal mit Erklärungstext und History-Sparkline/Chart.
5. `SyncStatus` + Anzeige `generated_at` / Datenalter.
6. Embed-Route `/embed` (minimales Chrome) für Confluence.
7. Theming (hell/dunkel) optional.
8. `next.config`: `frame-ancestors` / CSP für Confluence (siehe `open-questions.md` J3).
9. **Minimal-UI Erstimplementierung:** Tabelle oder Export-Spalten für **Lead Post-Production** und **gebuchte vs. Kalenderzeit** (sobald API Daten liefert); volle Charts optional Phase 1.5.

---

## Story 13: Frontend — Admin (Login & Konfiguration)

| Feld | Inhalt |
| --- | --- |
| **Summary** | Geschützte Admin-UI `/admin/login`, `/admin/config` |
| **Typ** | Story |

### Subtasks

1. Next.js `middleware`: `/admin/*` außer Login schützen.
2. Login-Formular; Session-Cookie oder JWT-Speicherung (Konsistenz mit Story 11).
3. Formularsektionen: GitLab (URL, Token, Projekte, Branches, Marker), Jira (URL, User, Token, Projekte, CF-IDs), Scheduler, Webhook.
4. `SecretInput`: maskierte Anzeige; „Token ersetzen“ nur bei Eingabe.
5. `PATCH` mit partiellen Updates; Erfolg/Fehler-Feedback.
6. Kein Admin-Link im Standard-Header für Viewer (optional nur bei Admin-Session).

---

## Story 14: Docker & Deployment

| Feld | Inhalt |
| --- | --- |
| **Summary** | Docker Compose: DB, Backend, Frontend |
| **Typ** | Story |

### Subtasks

1. `Dockerfile` Backend (Alembic migrate on start + uvicorn).
2. `Dockerfile` Frontend (build-time `NEXT_PUBLIC_API_URL`).
3. `docker-compose.yml`: Services, Netzwerk, Volumes für Postgres, Healthchecks.
4. Dokumentation: Caddy auf Host (kein nginx im Compose laut Spezifikation).
5. Secrets nur via `.env` / Orchestrator, nicht im Image.

---

## Story 15: Webhook & Betrieb

| Feld | Inhalt |
| --- | --- |
| **Summary** | Benachrichtigung bei Sync-Fehlern; Backup-Hinweis |
| **Typ** | Story |

### Subtasks

1. Webhook POST bei Abschluss von `run_nightly_sync` (Payload laut Spezifikation).
2. Konfiguration: URL ein/aus, bei Erfolg optional.
3. Dokumentation `pg_dump`-Retention aus `configuration.yml` (Job optional APScheduler).
4. Runbook: Was tun bei `SYNC_COMPLETE_FAILURE`?

---

## Story 16: Datenqualität & Data-Health-UI (Minimum)

| Feld | Inhalt |
| --- | --- |
| **Summary** | Transparenz bei Lücken (Jira/GitLab) |
| **Typ** | Story |

### Subtasks

1. Backend: Endpoint oder erweiterte Payloads für Kennzahlen: % healthy Bugs, unmatched MRs, Versions-Mismatches (Aggregation aus DB).
2. Frontend: Panel oder Seite „Data Health“ mit Tabellen (Phase-1-minimal).
3. Verknüpfung zu Jira/GitLab-Keys (externe URLs) wo möglich.

---

## Story 17: Tests & Qualitätssicherung

| Feld | Inhalt |
| --- | --- |
| **Summary** | pytest, Frontend-Tests, Nightly-Pipeline-Test |
| **Typ** | Story |

### Subtasks

1. Unit-Tests: Metric-Service, Version-Parsing, Health-Regeln (Abdeckung laut Strategie).
2. Integration: GitLab/Jira gemockt (respx), echte Postgres (Testcontainers).
3. Test: `run_nightly_sync` Reihenfolge und Partial-Failure.
4. Frontend: RTL für kritische Komponenten; optional Playwright Smoke.
5. CI: Tests + Lint auf MR (Verknüpfung Story 1.6).

---

## Story 18: CI/CD-Pipeline (Repository, Phase 2)

| Feld | Inhalt |
| --- | --- |
| **Summary** | Optionale Pipeline für Lint, Test, Image-Build (nach MVP) |
| **Typ** | Story |

### Subtasks

1. Phase-2-Option: Pipeline-Stages `lint backend → lint frontend → test backend → test frontend → build images` (optional publish zu Registry).
2. Phase-2-Option: Schutzregeln (MR nur bei grün), falls Teamprozess das verlangt.
3. MVP gilt ohne Pflicht-Pipeline: Verifikation lokal (Lint/Tests) vor Push/Merge; GitLab primär für Repository und Versionierung.

---

## Story 19 (Phase 1.5): Erweiterte Visualisierungen

| Feld | Inhalt |
| --- | --- |
| **Summary** | Charts: Lead-Time-Split, Branch, CFR-Drilldown, Rework, MTTR-Verteilung |
| **Typ** | Story (optional eigenes Epic-Label „Phase 1.5“) |

### Subtasks

1. API-Erweiterungen oder Query-Parameter für Aggregationen pro Branch / feature vs patch.
2. UI: Lead-Zeit Aufteilung (dev vs release wait); Charts pro `target_branch`.
3. CFR: Tabelle Releases mit verknüpften Bugs.
4. Rework Rate: API + Chart (Patches pro Minor).
5. MTTR Alpha: Histogramm oder Perzentile-Strip.
6. UX-Review mit Stakeholdern.

---

## Story 20: Backlog / Später

| Feld | Inhalt |
| --- | --- |
| **Summary** | Nicht in v1 |
| **Typ** | Story (Epic-Label „Future“) |

### Subtasks

1. MTTR Beta (ServiceDesk End-to-End).
2. Filter pro Team/Produkt; SSO für Admin.
3. Manueller „Sync jetzt“-Button.

---

## Empfehlung für Jira-Felder

| Jira-Feld | Nutzung |
| --- | --- |
| **Epic Link** | Alle Stories oben → Epic „DORA Metrics App“. |
| **Story Points** | Pro Story schätzen; Subtasks meist 0.5–2 Tage Einzelaufwand. |
| **Labels** | `backend`, `frontend`, `devops`, `phase-1`, `phase-1.5`, `security` |
| **Fix Version** | Release-Ziele (z. B. `MVP`, `1.1`) nach Priorisierung setzen. |
| **Commit-Konvention** | Commits nach Jira-Key benennen, z. B. `git commit -m "DEVOPS-430 <summary>"`; Epic-Level möglich mit `git commit -m "DEVOPS-429 DORA Metrics App"`. Repository: `https://gitlab.plunet.com/operations/dora-metrics.git`. |

---

## Kurz-Checkliste (Reihenfolge der Umsetzung)

1. Story 1 → 2  
2. Story 3 → 4 → 5 (GitLab)  
3. Story 6 → 7 (Jira inkl. Worklogs/Ready-for-QA + Querschnitt inkl. Lead Post-Production)  
4. Story 9 + 8 (Metriken + Scheduler; 8 kann teilweise parallel zu 9)  
5. Story 10 + 11 (Config + API)  
6. Story 12 + 13 (Frontend)  
7. Story 14 + 15  
8. Story 16 + 17 + 18  

Story 19–20 nach Release oder parallel planen.
