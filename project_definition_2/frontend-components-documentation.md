# Frontend Components – Documentation

## Technology Mapping (Vue → Next.js)

| Vue concept | Next.js / React equivalent |
| --- | --- |
| Vue SFC `.vue` | React `.tsx` component |
| Pinia store | TanStack Query (server state) + Zustand (UI state) |
| Vue Router | Next.js App Router |
| Chart.js | Recharts |
| Vitest + Vue Test Utils | Jest + React Testing Library |
| CSS variables | Tailwind CSS + CSS custom properties |

---

## Framework Decisions

- **Next.js App Router** with `"use client"` directives where interactivity is needed.
- **Server Components** used for layout, static shell, and metadata only. All metric data is fetched client-side so the dashboard works inside a Confluence iframe without SSR hydration issues.
- **TanStack Query v5** manages all API data fetching, caching, and background refetching.
- **Zustand** for lightweight UI state (selected period type, theme mode, active modal).
- **Recharts** for all charts (React-native, responsive, composable).
- **Tailwind CSS** for styling.

---

## Access control (RBAC)

| Audience | Login | Routes |
| --- | --- | --- |
| **Viewer** | **No** | `/`, `/embed`, all **read-only** API usage via `lib/api-client.ts` (no `Authorization` header). |
| **Admin** | **Yes** | `/admin/login` → after success → **`/admin/config`**. Only admins may call **`POST/PATCH /api/admin/config`** and **`POST /api/auth/logout`**. |

### Behaviour

- **Middleware** (`middleware.ts`): protect `/admin/*` **except** `/admin/login`. Unauthenticated users hitting `/admin/config` are redirected to `/admin/login`.
- **Session**: Prefer **HTTP-only cookie** set by backend on login (`SameSite=Lax` or `Strict`; `Secure` in production) so tokens are not exposed to JS. Alternative: **Bearer JWT** in memory + `Authorization` header for admin API calls only.
- **Main dashboard** does **not** require login; Confluence iframe users remain anonymous viewers.
- **No link** to Admin in the default header (optional: show “Admin” link only if `GET /api/auth/me` returns role=admin — avoids advertising the path; operators bookmark `/admin/login`).

### Admin configuration page (`/admin/config`)

- **Sections:** GitLab (URL, token, project paths, branches, markers), Jira (URL, user, token, excluded projects, indicator CF IDs), Scheduler (cron), Webhook, Retention.
- **Token fields:** Display **masked** values; “Change token” reveals a replace-only input (never show full secret after save).
- **Validation:** Client-side required fields + server error toast on `422`.
- **Save:** `PATCH /api/admin/config` with partial updates; success toast + optional “Restart required” banner if backend cannot hot-reload.

---

## Visualization & dashboard scope

Aligned with **`dora-metrics-app-documentation.md`** (Visualization section). Frontend ownership:

| Priority | UI element | Data |
| --- | --- | --- |
| P1 | Metric cards ×4 + DORA level badges | `GET /metrics/current` |
| P1 | Period selector + trend chart | `GET /metrics/history` |
| P1 | Metric detail modal + in-modal history chart | same + static copy in `metric-explanations.ts` |
| P1 | Sync status + `generated_at` | `GET /sync/status`, metrics |
| P1.5 | **Lead time split** (first_commit→merge vs merge→tag) | Extended API or client-derived from MR export endpoint (TBD) |
| P1.5 | **By-branch** / **feature vs patch** views | Query params or separate endpoints |
| P1.5 | **Rework rate** chart | Tag/version aggregation API |
| P1.5 | **Data health** panel (tables) | New `GET /data-health` or embed in dashboard |
| P2 | Repository table | `GET /repositories` + per-repo metrics |

**Gap:** Until Phase 1.5, the app delivers **core DORA storytelling** (cards + trends); **deep operational visuals** are explicitly backlog, not an oversight.

---

## Data freshness (daily sync)

- **`SyncStatus`** (`components/header/SyncStatus.tsx`) loads **`GET /sync/status`** on dashboard mount and shows **last successful sync** time and status (**SUCCESS** / **PARTIAL_FAILURE** / **FAILED**).
- **`HeaderBar`** may show a subtle warning if `last_sync` is older than **26 hours** (missed schedule) or if status is failure — exact thresholds configurable.
- **Metric cards** display **`generated_at`** from **`GET /metrics/current`** (or per-card tooltip) so users know the snapshot timestamp aligns with the nightly pipeline described in `dora-metrics-app-documentation.md`.
- TanStack Query: `staleTime` can be set to **~24 hours** for metric queries (data only changes after sync); **`refetchOnWindowFocus`** may remain **true** so a user returning the next day sees fresh data without a hard reload.

---

## Application Layout

```
app/
├── layout.tsx          # Root layout: providers (QueryClient, ThemeProvider)
├── page.tsx            # Main dashboard page (Server Component shell)
├── embed/
│   └── page.tsx        # Embed-mode page (?embed=true equivalent, minimal UI)
└── admin/
    ├── login/page.tsx  # Admin login form → POST /api/auth/login
    └── config/page.tsx # Protected: integration settings form
```

---

## Component Hierarchy

```
app/page.tsx
└── <Dashboard />              (client component, fetches data)
    ├── <HeaderBar />
    │   ├── <SyncStatus />
    │   ├── <PeriodSelector />
    │   └── <ThemeToggle />
    ├── <MetricCards />
    │   └── <MetricCard /> ×4
    │       └── <MetricDetailModal /> (rendered in portal)
    │           ├── <MetricExplanation />
    │           └── <MetricHistoryChart />
    ├── <TrendChart />
    │   └── <MetricToggle />
    ├── <RepositoryTable /> (Phase 2)
    │   └── <RepositoryRow /> ×n
    └── <FooterBar />

app/admin/config/page.tsx
└── <AdminConfigPage />         (client)
    ├── <GitLabSettingsSection />
    ├── <JiraSettingsSection />
    ├── <SchedulerSection />
    └── <SaveActions />
```

---

## File Structure

```
frontend/
├── app/
│   ├── layout.tsx
│   ├── page.tsx
│   ├── embed/page.tsx
│   └── admin/
│       ├── login/page.tsx
│       └── config/page.tsx
├── components/
│   ├── header/
│   │   ├── HeaderBar.tsx
│   │   ├── SyncStatus.tsx
│   │   ├── PeriodSelector.tsx
│   │   └── ThemeToggle.tsx
│   ├── metrics/
│   │   ├── MetricCards.tsx
│   │   ├── MetricCard.tsx
│   │   └── MetricDetailModal.tsx
│   ├── charts/
│   │   ├── TrendChart.tsx
│   │   ├── MetricToggle.tsx
│   │   └── MetricHistoryChart.tsx
│   ├── repository/
│   │   ├── RepositoryTable.tsx        (Phase 2)
│   │   └── RepositoryRow.tsx          (Phase 2)
│   ├── admin/
│   │   ├── AdminConfigForm.tsx
│   │   ├── GitLabSettingsSection.tsx
│   │   ├── JiraSettingsSection.tsx
│   │   └── SecretInput.tsx       # masked PAT/token fields
│   └── common/
│       ├── FooterBar.tsx
│       └── LoadingSpinner.tsx
├── lib/
│   ├── api-client.ts              # fetch wrapper; credentials: 'include' for admin routes
│   ├── admin-api.ts               # GET/PATCH /api/admin/config; login/logout
│   ├── metric-explanations.ts     # static metric copy (description, formula, sources)
│   └── dora-levels.ts             # DORA threshold constants + classifier
├── stores/
│   └── ui-store.ts                # Zustand: periodType, theme, activeMetric
├── hooks/
│   ├── use-current-metrics.ts     # TanStack Query hook → GET /metrics/current
│   ├── use-metrics-history.ts     # TanStack Query hook → GET /metrics/history
│   ├── use-repositories.ts        # TanStack Query hook → GET /repositories
│   ├── use-sync-status.ts         # TanStack Query hook → GET /sync/status
│   ├── use-auth.ts                # current user / admin role (GET /api/auth/me)
│   └── use-admin-config.ts        # GET/PATCH admin config
├── middleware.ts                  # protect /admin/* (except /admin/login)
├── tests/
├── tailwind.config.ts
├── next.config.ts
├── Dockerfile
└── package.json
```

---

## Key Components

### `MetricCard.tsx`

Displays a single DORA metric. Clicking opens the detail modal.

```
┌─────────────────────────────┐
│  Deployment Frequency    ⓘ │
│                             │
│         4.2                 │
│    deploys / week           │
│                             │
│   ▲ 12.5%    ● HIGH         │
└─────────────────────────────┘
```

Props: `metricKey`, `data: MetricValue`, `onClick`

### `MetricDetailModal.tsx`

Appears when a MetricCard is clicked. Contains:
- Current value + badge
- Text explanation (from `metric-explanations.ts`)
- Calculation formula
- Data sources
- Performance level table (with current level highlighted)
- Single-metric history chart (`MetricHistoryChart`)

Implemented via React Portal to render above the iframe viewport.

### `TrendChart.tsx`

Recharts `LineChart` with all 4 metrics. Each line is independently toggleable. Responsive container adapts to iframe width.

### `ThemeToggle.tsx`

| Feature | Implementation |
| --- | --- |
| Toggle | Zustand `uiStore.setTheme()` |
| CSS | Tailwind `dark:` variant + `class="dark"` on `<html>` |
| Persistence | `localStorage` via Zustand persist middleware |
| Default | `window.matchMedia('(prefers-color-scheme: dark)')` on first load |

### `SyncStatus.tsx`

Polls `GET /sync/status` via TanStack Query (refetch interval: 60 s).

| Status | Display |
| --- | --- |
| `SUCCESS` | ✓ Green + timestamp |
| `PARTIAL_FAILURE` | ⚠ Yellow + error note |
| `FAILED` | ✗ Red + error note |

### `PeriodSelector.tsx`

Controlled dropdown backed by Zustand `uiStore.periodType`. On change triggers re-fetch of history data.

---

## State Management

### TanStack Query (server state)

```typescript
// hooks/use-current-metrics.ts
export function useCurrentMetrics() {
  return useQuery({
    queryKey: ["metrics", "current"],
    queryFn: () => apiClient.get("/metrics/current"),
    staleTime: 5 * 60 * 1000,  // 5 minutes
  });
}

// hooks/use-metrics-history.ts
export function useMetricsHistory(params: HistoryParams) {
  return useQuery({
    queryKey: ["metrics", "history", params],
    queryFn: () => apiClient.get("/metrics/history", { params }),
    staleTime: 5 * 60 * 1000,
  });
}
```

### Zustand (UI state)

```typescript
// stores/ui-store.ts
interface UIStore {
  periodType: PeriodType;
  isDarkMode: boolean;
  activeMetric: MetricKey | null;
  setPeriodType: (t: PeriodType) => void;
  setTheme: (dark: boolean) => void;
  openMetricModal: (key: MetricKey) => void;
  closeMetricModal: () => void;
}
```

---

## Performance Level Colors

| Level | Tailwind Class | Hex |
| --- | --- | --- |
| ELITE | `text-purple-500` | `#9B59B6` |
| HIGH | `text-green-500` | `#27AE60` |
| MEDIUM | `text-yellow-500` | `#F1C40F` |
| LOW | `text-red-500` | `#E74C3C` |

---

## Responsive Design

| Breakpoint | Layout |
| --- | --- |
| `lg` (≥1024px) | 4 metric cards in a row, full table |
| `md` (768–1024px) | 2×2 card grid, scrollable table |
| `sm` (<768px) | 1 card per row, simplified table |

---

## Confluence Embed Mode

The `/embed` route renders only metric cards + trend chart with no header or footer. Use this URL as the iframe `src`.

```html
<iframe
  src="http://your-host/embed"
  width="100%"
  height="600"
  frameborder="0"
/>
```

If height auto-resize is needed, implement `postMessage` from the Next.js page to the Confluence macro.

---

## API Client

```typescript
// lib/api-client.ts
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api";

export const apiClient = {
  async get<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${BASE_URL}${path}`, options);
    if (!res.ok) {
      const error = await res.json();
      throw new Error(error.message ?? `HTTP ${res.status}`);
    }
    return res.json();
  },
};
```

The `NEXT_PUBLIC_API_URL` environment variable must be set at build time (or via Docker Compose).

---

## Metric Explanations (Static Copy)

All text for `MetricDetailModal` is defined in `lib/metric-explanations.ts`:

```typescript
export const METRIC_EXPLANATIONS: Record<MetricKey, MetricExplanation> = {
  deployment_frequency: {
    title: "Deployment Frequency",
    description: "How often your team deploys code to production...",
    calculation: "Count of tags on protected branches per time period. RC releases excluded.",
    data_sources: ["GitLab: Tags on protected branches"],
    unit: "deploys / week",
  },
  // lead_time, change_failure_rate, mttr ...
};
```
