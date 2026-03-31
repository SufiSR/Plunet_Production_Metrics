# Frontend Components - Documentation

- Source URL: https://plunet.atlassian.net/wiki/spaces/EN/pages/770703362/Frontend+Components+-+Documentation
- Confluence Page ID: `770703362`

## Overview

Vue dashboard composed of:
- Header (sync status, period selector, theme toggle)
- DORA metric cards
- Historical trend chart
- Repository table (phase 2)
- Footer

## Component Hierarchy

`App.vue`
- `HeaderBar.vue`
- `MetricCards.vue`
- `TrendChart.vue`
- `MetricDetailModal.vue`
- `RepositoryTable.vue` (Phase 2)
- `FooterBar.vue`

## Key Components

### `MetricCard.vue`
Shows metric value, unit, trend, and performance badge; clicking opens details.

### `MetricDetailModal.vue`
Contains current value, metric explanation, calculation logic, data sources, level mapping, and single-metric history chart.

### `TrendChart.vue`
Displays historical trends for all metrics with toggles and tooltips.

### `ThemeToggle.vue`
Supports light/dark mode, localStorage persistence, and system default.

### `RepositoryTable.vue`
Provides per-repository metrics with sorting, filtering, and drill-down (phase 2).

## Metric Explanations

Includes documented definition, formula, data sources, and units for:
- Deployment Frequency
- Lead Time for Changes
- Change Failure Rate
- MTTR

## Visual Design

- Performance level colors defined for `ELITE`, `HIGH`, `MEDIUM`, `LOW`
- Light and dark palette definitions included
- Responsive behavior for desktop/tablet/mobile breakpoints

## State Management

Pinia stores:
- `metricsStore.js`
- `repositoryStore.js`
- `syncStore.js`
- `themeStore.js`

## File Structure

Organized by feature folders under `components`, `stores`, `services`, and `constants`.

## Confluence Embed Mode

Supports iframe usage via `?embed=true` with reduced UI and integration-oriented layout.

