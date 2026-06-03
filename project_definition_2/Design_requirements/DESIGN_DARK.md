# Design System: Editorial Engineering (Dark Mode)

## 1. Overview

This document defines the **dark mode counterpart** to `DESIGN_LIGHT.md`. It uses the same "Editorial Engineering / The Technical Curator" creative north star, the same typography system (Space Grotesk + Inter), the same "No-Line Rule", and the same component patterns. Only the color tokens change.

The dark palette is derived from the same **Indigo / Cool Gray Material Design seed** as the light palette, following Material Design's dark-scheme generation rules:

- Surface layers are deep neutrals — darkness increases as elevation *decreases* (lower surface = darker).
- The primary Indigo inverts: the dark-mode `primary` token is the light-mode `primary-fixed-dim` (#c0c1ff) — a soft lavender that reads at high contrast on dark backgrounds without burning the eye.
- All `on-*` tokens are correspondingly inverted from their light-mode pairs.

---

## 2. Color Tokens — Dark Mode

These values replace the light-mode values when the `<html>` element carries the `.dark` class.

### Surface Hierarchy (Tonal Stacking — Dark)

The "Layering Principle" still applies: higher elevation = lighter tonal surface. But in dark mode, "lighter" means slightly less dark.

| Token | Dark Value | Light Equivalent | Notes |
|---|---|---|---|
| `background` | `#1e2226` | `#f8f9fa` | Page canvas (soft charcoal) |
| `surface` | `#1e2226` | `#f8f9fa` | Same as background |
| `surface-dim` | `#181b1f` | `#d9dadb` | Dimmed/muted surface |
| `surface-bright` | `#2a3036` | `#f8f9fa` | Emphasized bright surface |
| `surface-container-lowest` | `#2a3036` | `#ffffff` | Cards on dark bg (lighter than canvas) |
| `surface-container-low` | `#343b42` | `#f3f4f5` | Slight step up |
| `surface-container` | `#3e464e` | `#edeeef` | Standard container |
| `surface-container-high` | `#49525a` | `#e7e8e9` | Elevated container |
| `surface-container-highest` | `#565f68` | `#e1e3e4` | Highest elevation |
| `surface-variant` | `#6b6978` | `#e1e3e4` | Variant surface |
| `inverse-surface` | `#e2e3e4` | `#2e3132` | Snackbar/tooltip bg |
| `inverse-on-surface` | `#2e3132` | `#f0f1f2` | Text on inverse surface |

### Text / Icon Tokens

| Token | Dark Value | Light Equivalent |
|---|---|---|
| `on-background` | `#f3f4f5` | `#191c1d` |
| `on-surface` | `#f3f4f5` | `#191c1d` |
| `on-surface-variant` | `#e0deef` | `#464554` |
| `outline` | `#b8b5c8` | `#767586` |
| `outline-variant` | `#848194` | `#c7c4d7` |

### Primary (Indigo — Dark)

| Token | Dark Value | Light Equivalent |
|---|---|---|
| `primary` | `#c0c1ff` | `#4648d4` |
| `on-primary` | `#0c0e8c` | `#ffffff` |
| `primary-container` | `#2527b5` | `#6063ee` |
| `on-primary-container` | `#e1e0ff` | `#fffbff` |
| `primary-fixed` | `#e1e0ff` | `#e1e0ff` |
| `primary-fixed-dim` | `#c0c1ff` | `#c0c1ff` |
| `on-primary-fixed` | `#07006c` | `#07006c` |
| `on-primary-fixed-variant` | `#2f2ebe` | `#2f2ebe` |
| `inverse-primary` | `#4648d4` | `#c0c1ff` |
| `surface-tint` | `#c0c1ff` | `#494bd6` |

### Secondary (Cool Violet — Dark)

| Token | Dark Value | Light Equivalent |
|---|---|---|
| `secondary` | `#c0c1ff` | `#575992` |
| `on-secondary` | `#282a62` | `#ffffff` |
| `secondary-container` | `#404178` | `#bdbefe` |
| `on-secondary-container` | `#e1e0ff` | `#494b83` |
| `secondary-fixed` | `#e1e0ff` | `#e1e0ff` |
| `secondary-fixed-dim` | `#c0c1ff` | `#c0c1ff` |
| `on-secondary-fixed` | `#13144a` | `#13144a` |
| `on-secondary-fixed-variant` | `#404178` | `#404178` |

### Tertiary (Amber/Orange — Dark)

| Token | Dark Value | Light Equivalent |
|---|---|---|
| `tertiary` | `#ffb783` | `#904900` |
| `on-tertiary` | `#4d2600` | `#ffffff` |
| `tertiary-container` | `#6d3900` | `#b55d00` |
| `on-tertiary-container` | `#ffdcc5` | `#fffbff` |
| `tertiary-fixed` | `#ffdcc5` | `#ffdcc5` |
| `tertiary-fixed-dim` | `#ffb783` | `#ffb783` |
| `on-tertiary-fixed` | `#301400` | `#301400` |
| `on-tertiary-fixed-variant` | `#703700` | `#703700` |

### Error (Red — Dark)

| Token | Dark Value | Light Equivalent |
|---|---|---|
| `error` | `#ffb4ab` | `#ba1a1a` |
| `on-error` | `#690005` | `#ffffff` |
| `error-container` | `#93000a` | `#ffdad6` |
| `on-error-container` | `#ffdad6` | `#93000a` |

---

## 3. Dark Mode Rules

### Surface Layering (Inverted)

In light mode, cards are bright white on a light gray canvas. In dark mode, the palette uses a **soft charcoal** base (`#1e2226`) with clearly lighter container steps so heroes, sections, and tables remain easy to scan.

> **Correct card stack (dark):**
> - Page background: `background` (`#1e2226`)
> - Card bg: `surface-container-lowest` (`#2a3036`) — one step lighter than the canvas
> - Hero panels (analytics): `surface-container` (`#3e464e`) via `.analytics-hero-panel` in dark mode
> - Section panels: `surface-container-low` (`#343b42`) via `.analytics-section-panel`
> - Hover state: `surface-container-high` (`#49525a`)

### The "No-Line Rule" in Dark Mode

The same rule applies. Do not add 1px borders. The tonal difference between `surface-container-lowest` and `background` is sufficient for definition.

The "Ghost Border Fallback" for accessibility: use `outline-variant` at **15% opacity** (`#464554` at 0.15 opacity). Note that in dark mode `outline-variant` is a medium-dark gray, so 15% opacity gives an extremely subtle line — test WCAG contrast ratio when applying.

### Ambient Shadows in Dark Mode

Dark surfaces absorb shadow, making standard box shadows invisible. Replace the light-mode shadow:

```
Light: shadow-[40px_40px_40px_0px_rgba(25,28,29,0.04)]
Dark:  shadow-[0px_4px_24px_0px_rgba(0,0,0,0.4)]
```

The dark card "float" shadow uses full black at 40% opacity and 24px blur (vs light's 4% opacity and 40px blur).

### DORA Performance Badges in Dark Mode

Same token names, different resolved colors:

| Badge | Dark bg token | Dark text token | Resolved bg | Resolved text |
|---|---|---|---|---|
| **ELITE** | `primary` | `on-primary` | `#c0c1ff` (lavender) | `#0c0e8c` (dark indigo) |
| **HIGH** | `secondary-container` | `on-secondary-container` | `#404178` (dark violet) | `#e1e0ff` (light lavender) |
| **MEDIUM** | `tertiary-fixed` | `on-tertiary-fixed-variant` | `#ffdcc5` (peach) | `#703700` (dark amber) |
| **LOW** | `error-container` | `on-error-container` | `#93000a` (dark red) | `#ffdad6` (light red) |

Note that ELITE and HIGH badges will look distinctly different in dark mode compared to light mode — this is expected and follows Material Design's dark-scheme conventions.

### Glassmorphism in Dark Mode

For floating menus / navigation overlays:

```css
background: rgba(13, 15, 16, 0.85); /* surface-container-lowest at 85% */
backdrop-filter: blur(24px);
```

(Light mode used `surface_container_lowest` at 80% + 24px backdrop-blur; dark mode increases opacity slightly to maintain legibility.)

### Chart Colors in Dark Mode

Recharts does not read CSS variables directly. Use `frontend/lib/chart-colors.ts` (`getChartColors`, `useReportChartTheme`, `useChartSeriesColors`) so charts pick up theme tokens.

| Token | Light | Dark |
|---|---|---|
| `chart-grid` | `#d5d7d9` | `#8b95a3` (65% opacity on plot) |
| `chart-axis` | `#464554` | `#e8e6f5` |
| `chart-plot` | `#ffffff` | `#343b42` |
| `chart-tooltip-bg` | `#2e3132` | `#49525a` |
| `chart-tooltip-text` | `#f0f1f2` | `#f3f4f5` |
| Series palette | `CHART_SERIES_LIGHT` | `CHART_SERIES_DARK` (brighter saturated hues) |

Chart containers use `.analytics-chart-plot` for a slightly elevated plot background in dark mode.

---

## 4. Do's and Don'ts (Dark Mode Addendum)

### Do
- **Do** use `surface-container-lowest` (`#2a3036`) as the card background, not pure black (`#000000`). Pure black creates excessive contrast.
- **Do** use `primary` (`#c0c1ff`) lavender as the accent — it draws the eye without glare.
- **Do** increase chart grid line opacity in dark mode to maintain visibility (e.g. opacity 20% on `#464554` instead of using `surface-container`).

### Don't
- **Don't** use pure white (`#ffffff`) for text in dark mode. Use `on-surface` (`#e2e3e4`).
- **Don't** use light-mode surface values for dark components. Even one wrong `#ffffff` card background will break the entire dark hierarchy visually.
- **Don't** use the same shadow values as light mode. Dark shadows need higher opacity and shorter blur.
