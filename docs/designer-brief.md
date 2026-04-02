# DORA Metrics App — Google Stitch Design Brief

## How to use this document

Google Stitch works best with short, focused prompts — one screen at a time. This document gives you:

1. **One initial prompt** to set the project vibe and global rules
2. **One prompt per screen** to copy-paste into Stitch, in order

Start with the Initial Prompt, let Stitch generate, then work through each screen prompt one by one. Only move to the next screen once you're happy with the current one.

---

## Context (read before prompting)

**What is this?**
An internal engineering metrics dashboard for a software company. It shows four delivery health KPIs pulled from GitLab and Jira. Think of it as an operational health display — not a consumer product.

**Critical iframe constraint**
Every public-facing screen (the dashboard and all its drilldown pages) will be embedded inside a Confluence page as an `<iframe>`. This affects everything:
- No full-height browser layouts — content must fit and scroll gracefully inside a constrained iframe
- Navigation must happen within the iframe, never triggering full browser navigation
- No double scrollbars — the iframe itself and the inner page must not both show scrollbars at the same time
- Breadcrumbs are the primary navigation mechanism so users always know where they are and how to get back — without needing menus

**Navigation philosophy**
- Public screens (dashboard + drilldowns): **no menus** — all navigation happens through clickable cards, breadcrumbs, and inline links
- Admin screens only: a **sidebar or tab navigation** is acceptable since admins have a browser, not an iframe
- Every drilldown page must be reachable directly from the dashboard by clicking on a card or chart element
- Breadcrumbs appear on every drilldown page (not needed on the dashboard root itself)

**Users**
- **Viewers** — any Confluence user, no login required, sees the dashboard and drilldowns
- **Admins** — operators who configure the system, access `/admin` directly by URL, login required

**Theme**
The app must support both light mode and dark mode. A toggle visible on every screen switches between them. It should default to the user's OS preference and persist their choice.

---

## Prompt 1 — Project Vibe (paste this first)

> A clean, data-focused internal engineering dashboard called "DORA Metrics." It lives inside a Confluence iframe so it must be compact and self-contained. The mood is professional and calm — like a well-designed ops tool, not a flashy consumer product. It should support both light and dark mode with a toggle on every screen. Navigation is minimal: no menus on public screens, breadcrumbs instead. Four KPI metric cards are the centrepiece. Charts are clean and readable. The aesthetic should feel trustworthy and precise — something an engineering team would be proud to show leadership.

---

## Prompt 2 — Main Dashboard (`/`)

> Design the main dashboard screen. It contains:
>
> **Header strip (compact, not tall):** App name "DORA Metrics" on the left. On the right: a sync status indicator showing the last data pipeline run (it has five states: success with timestamp, partial failure, failed, loading, and stale/overdue), a period selector control letting the user choose Week / Month / Quarter, and a light/dark mode toggle.
>
> **Four metric cards in a row:** Each card shows a metric name, a large current value with its unit, a trend indicator (change vs previous period — direction matters: for lead time, lower is better; for deployment frequency, higher is better), and a performance level badge with one of four states: ELITE, HIGH, MEDIUM, or LOW. The four metrics are: Deployment Frequency, Lead Time for Changes, Change Failure Rate, and MTTR Alpha. Clicking a card navigates to the drilldown page for that metric.
>
> **Trend chart below the cards:** A time series line chart showing all four metrics over time. Each metric line can be toggled on or off independently. Hover tooltip shows values. Must fit within the iframe width with no horizontal scrolling.
>
> **Footer strip:** "Data as of [timestamp]" freshness label.
>
> No navigation menu. Cards are the only navigation elements.

---

## Prompt 3 — Metric Drilldown Page (one template for all four metrics)

> Design a metric drilldown page. This page opens when a user clicks a metric card on the dashboard. It still lives inside the Confluence iframe.
>
> **Breadcrumb at the top:** "DORA Metrics > Deployment Frequency" — clicking the first crumb returns to the dashboard.
>
> **Hero section:** Metric name, current value with unit, and the ELITE/HIGH/MEDIUM/LOW performance level badge. A brief plain-language description of what the metric means.
>
> **Two-column or stacked layout below:**
> - Left/top: A larger history chart for this single metric over the selected period
> - Right/bottom: A reference table showing all four performance levels (ELITE, HIGH, MEDIUM, LOW) with their threshold values — the current level is visually highlighted
>
> **Below that:** A "How it's calculated" section with a short explanation and a "Data sources" note (e.g. GitLab tags, Jira bugs).
>
> **Same header strip as the dashboard** (period selector, sync status, theme toggle) — the period selector here controls the drilldown chart.
>
> No menu. Back navigation is only through the breadcrumb.

---

## Prompt 4 — Confluence Embed View (`/embed`)

> Design the embed-only variant of the dashboard. This is the most constrained layout — it will be dropped into a Confluence iframe with a fixed height of roughly 500–600px.
>
> **No header strip, no footer.** Just the four metric cards and the trend chart below them, with a minimal "Data as of [timestamp]" line at the very bottom.
>
> The cards must still be clickable (opening the metric drilldown within the same iframe context).
>
> Everything must fit without vertical overflow unless absolutely necessary. Content should be slightly more compact than the full dashboard. No double scrollbars.

---

## Prompt 5 — Admin Login (`/admin/login`)

> Design a simple admin login screen. This is not linked from the public dashboard — operators navigate here directly by URL. It is not inside a Confluence iframe.
>
> Centred card layout with: app name, a "Admin Login" heading, a username field, a password field, and a login button.
>
> Four states to show: idle (empty form), submitting (loading state on the button), error (wrong credentials — inline error message, not a browser alert), and success (this just navigates away).
>
> Respects the light/dark mode toggle.

---

## Prompt 6 — Admin Configuration (`/admin/config`)

> Design an admin configuration page. This is a protected screen only accessible after login. It is a normal browser page, not inside a Confluence iframe. Admins use this to configure integrations instead of editing config files.
>
> **This is the one screen that uses a navigation menu** — a left sidebar or top tab navigation with four sections: GitLab, Jira, Scheduler, Retention.
>
> **Header:** App name, current page title "Configuration", and a Logout action.
>
> **GitLab section fields:** Base URL, Access Token (shown masked with a "Change token" action — full secret never shown after save), monitored project paths, target branches, pre-release markers to exclude.
>
> **Jira section fields:** Jira base URL, API email, API token (same masking pattern), excluded projects, "Ready for QA" status names.
>
> **Scheduler section fields:** Daily sync time (hour and minute), optional webhook URL for failure alerts.
>
> **Retention section fields:** Data lookback window in days.
>
> **Footer of the form:** Cancel and Save actions. A "Restart required" notice banner for when some changes need a backend restart to take effect.
>
> States to show: loading config, editing a field, saving, save success (toast), save error (toast), and a masked token field with its reveal-to-replace flow.

---

## States & Components Stitch needs to cover

After the main screens are done, ask Stitch to design these states one at a time:

- **Metric card: loading skeleton** — "Show the metric card in a loading skeleton state, with placeholder shapes for the value and label"
- **Metric card: error state** — "Show the metric card when data failed to load, with an inline retry affordance"
- **Sync status: stale warning** — "Show the sync status indicator in a stale/overdue state — last successful sync was more than 26 hours ago"
- **Trend chart: no data** — "Show the trend chart when there is no historical data yet"
- **Token field: change flow** — "Show the masked API token field expanding into a replace-only input when the user clicks Change token"
- **Toast notifications** — "Design success, warning, and error toast notifications for the admin config screen"

---

## Hard constraints (non-negotiable, remind Stitch of these if it drifts)

- **Iframe-first:** All public screens must work inside a constrained iframe. No full-viewport overlays that break the Confluence embed. No designs that assume a full browser window.
- **Breadcrumbs on every drilldown page.** Not optional.
- **No menus on public screens.** Card clicks and breadcrumbs only.
- **Light and dark mode on every screen.** Toggle must be visible.
- **Four performance levels — ELITE / HIGH / MEDIUM / LOW — must be visually distinct from each other** and remain legible in both light and dark mode.
- **Masked token fields.** The full secret value must never be visible after first save.
- **Data freshness always visible.** Users must never be uncertain whether numbers are from today or older.

---

## Glossary (for Stitch context if needed)

| Term | Meaning |
|---|---|
| Deployment Frequency | How often production software releases ship per time period |
| Lead Time for Changes | Time from first code commit to that code being in a production release |
| Change Failure Rate | Share of releases that contained a production bug |
| MTTR Alpha | Time from a critical bug being filed to it being fixed in a release |
| DORA level | ELITE / HIGH / MEDIUM / LOW — performance classification for a metric |
| Sync status | Result of the last nightly data collection pipeline run |
| Data as of / generated_at | Timestamp showing when the metric numbers were last computed |
| Period selector | Week / Month / Quarter — controls which time window the charts and cards show |
