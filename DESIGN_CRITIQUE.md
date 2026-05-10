# Design Critique: IIoT Smart Factory Monitor Dashboard

**Date:** 2026-05-10
**Reviewer:** Design critique agent (design:design-critique skill)
**Stack:** Vanilla HTML/CSS/JS, Chart.js 4.4.1, JetBrains Mono + Inter, dark theme
**Target audience:** German automotive internship reviewers (BMW, Bosch, Continental)

---

## Executive Summary

The dashboard reads as a credible, purpose-built industrial monitoring tool. The dark theme, monospace numerics, and structured card layout immediately communicate "engineering software." The biggest risk to portfolio impact is the Z-score chart — with 9 overlapping coloured lines it is the most complex visual on the page and currently the hardest to read, which is a problem because it is the anomaly-detection centrepiece. Several `--text-faint` text instances fail WCAG AA contrast. Both issues have straightforward fixes.

---

## Critical Issues

### 1. WCAG AA contrast failures on `--text-faint`

`--text-faint: #5f6675` achieves approximately 3.1–3.2:1 contrast ratio on all backgrounds it is used on. WCAG AA requires 4.5:1 for normal text.

**Affected elements:** arm sub-labels ("NODE · ARM_01"), metric unit labels (°C, g, A), section label counts, footer, chart Y-axis labels, uptime counter, empty-row italic text.

**Fix:** Raise `--text-faint` from `#5f6675` to `#7a8190` (approximately 4.6:1 on `--surface`). One CSS variable change fixes all instances.

### 2. Z-score chart is illegible under normal conditions

Nine datasets (3 arms × 3 sensors) plus anomaly dots overlap in a ±5σ band. Near zero the lines fully tangle. A technical reviewer opening this panel will read it as visual noise before reading it as signal.

**Fix:** Reduce to 3 lines — one per arm, showing the max absolute Z-score across all 3 sensors at each tick. The anomaly red dots remain as the high-frequency detail. Alternatively, add a sensor toggle to isolate individual channels.

### 3. "LOCALHOST:8000" in the footer undermines a portfolio deployment

Any recruiter or interviewer viewing the live demo will see a localhost URL in the footer, signalling the project is not properly deployed.

**Fix:** Replace with the actual deployed API URL, or suppress the host entirely (`API · FASTAPI BACKEND`) in portfolio builds.

---

## Medium Issues

### 4. Pulse animation glow colour is hardcoded green

`@keyframes pulse` always emits a green box-shadow regardless of the current connection state. A red "DISCONNECTED" pill still pulses with a green glow — a semantic mismatch.

**Fix:** Apply separate animation keyframes per pill class (`.status-pill` for green, `.status-pill.disconnected` for red, `.status-pill.degraded` for amber) or use a CSS custom property for the shadow colour.

### 5. "CONNECTED · SIM FEED" amber pill frames demo mode as degraded

The amber/yellow pill communicates a warning state. For portfolio contexts the backend is intentionally absent, so the warning colour misleads reviewers.

**Fix:** When no live API is available, show a neutral slate pill labelled "DEMO MODE" instead of the amber degraded indicator.

### 6. Y-axis range mismatch: data occupies only 20–45% of chart area

Temperature data (50–60°C) uses a fixed range of 35–110°C, leaving 55% of chart area empty. Vibration data hugs the bottom 20% of its 0–5g range.

**Fix:** Either tighten the fixed ranges to ±3 standard deviations of the baseline values, or add a subtle reference-band fill showing the nominal operating range so the empty space communicates something meaningful.

### 7. Chart height is too short for detecting signal drift

At 180px, the actual plot area after axis chrome is approximately 120px. Subtle thermal drift is visually indistinguishable from noise at this height.

**Fix:** Increase `.chart-body` height from `180px` to `220px`. This is a one-line CSS change.

### 8. Anomaly log table triggers reflow on every render

The `table` element lacks `table-layout: fixed`, so the browser recalculates column widths on every 2-second DOM update. For 200 rows this causes measurable jank.

**Fix:** Add `table-layout: fixed` to the `table` selector and pin explicit widths to `<col>` elements or the existing `<th style="width:...">` values.

### 9. No scroll indicator on the anomaly log

The `max-height: 280px` scroll container shows 6–7 rows. There is no fade gradient or shadow indicating that more content exists below the visible area.

**Fix:** Add a CSS `::after` pseudo-element with a gradient fade at the bottom of `.log-scroll` when overflow is active, or a simple `box-shadow: inset 0 -16px 16px -8px var(--bg-2)`.

### 10. "CRITICAL 13" — the number, not the label, should be red

The anomaly log header uses `var(--danger)` on the label text "CRITICAL" but plain white on the count "13". The count is the operational datum; it should carry the alert colour.

**Fix:** Swap the `class="danger"` from the `<span>` wrapping "CRITICAL" to the `<b>` element wrapping the count, and change the label to dim text.

### 11. "NORMAL" fault pill appears on anomalous rows

Several log rows with Z-scores of ±3.0–4.2σ display a "NORMAL" fault-mode pill. This creates a visual contradiction — a red-highlighted anomaly row labelled NORMAL.

**Fix:** Either filter these rows from the log (since a NORMAL-classified Z-spike means the simulator did not assign a fault name to that event), or display "UNCLASSIFIED" in a neutral style to signal the data inconsistency rather than hiding it.

---

## What Works Well

- **Card structure and colour-coded top borders** cleanly differentiate the three robot arms (blue/amber/green) in a way consistent throughout cards, charts, and the log table.
- **JetBrains Mono for all live numeric values** prevents layout shift on 2-second updates and signals precision — the right choice for industrial telemetry.
- **Section labels with blue accent dot** (`::before` 4px square) create clear visual chapters without consuming significant vertical space.
- **Left-border + subtle fill row highlighting in the anomaly log** (`inset 3px 0 0 var(--danger)` + `rgba(239,68,68,0.06)` background) is well-calibrated — prominent enough to scan for anomalies without causing eye fatigue across many rows.
- **SIM FEED fallback** means the dashboard self-demonstrates without needing a running backend, which is portfolio-intelligent.
- **Sticky header** with live clock and connection status provides persistent orientation — the viewer always knows the data freshness and connection state.
- **Responsive breakpoint at 1100px** gracefully collapses the 3-column arm grid to 1 column.
- **Millisecond-precision timestamps** in the anomaly log are correct for fault correlation in an industrial context.
- **Chart legends duplicated above each chart** (not inside the chart canvas) mean the series key is always visible without hover, which is correct for operational dashboards.

---

## Recommendations

Listed in descending impact-to-effort ratio.

### R1 — Fix `--text-faint` contrast (effort: trivial, impact: high)

```css
:root {
  --text-faint: #7a8190;  /* was #5f6675; now ~4.6:1 on --surface */
}
```

Fixes 6+ WCAG AA failures. Affects arm sub-labels, unit labels, footer, chart axis labels, and uptime counters.

### R2 — Simplify Z-score chart to 3 lines (effort: medium, impact: high)

Replace 9 per-sensor datasets with 3 per-arm datasets, each plotting `max(|z_temperature|, |z_vibration|, |z_current|)` at each tick. This preserves the threshold-breach signal while making the chart scannable in under 2 seconds. Retain the red anomaly dots for event precision.

### R3 — Replace localhost URL / brand mark (effort: low, impact: high for portfolio)

- Footer: show the deployed API endpoint or suppress the host in portfolio builds.
- Brand mark: replace the text "II" with a 20×20px SVG icon (robot arm silhouette or a simple factory-floor outline). The ambiguous "II" reads as unfinished.

### R4 — Reclassify SIM FEED pill as DEMO MODE (effort: trivial, impact: medium)

Change the label from "CONNECTED · SIM FEED" and amber colour to "DEMO MODE" in a neutral `--text-dim` colour (no warning connotation). Reserve amber for genuinely degraded states.

### R5 — Fix pulse animation semantic mismatch (effort: trivial, impact: low)

Add per-state keyframes or CSS custom property to make the glow colour match the pill state (green for live, red for disconnected, amber for degraded).

### R6 — Add `table-layout: fixed` and scroll shadow to anomaly log (effort: low, impact: medium)

Eliminates reflow jank on 2-second re-renders and communicates scrollable content:

```css
table {
  table-layout: fixed;
}
.log-scroll {
  position: relative;
}
.log-scroll::after {
  content: "";
  position: sticky;
  bottom: 0;
  display: block;
  height: 32px;
  background: linear-gradient(to bottom, transparent, var(--bg-2));
  pointer-events: none;
}
```

### R7 — Increase sensor chart height and tighten Y-axis ranges (effort: low, impact: medium)

```css
.chart-body { height: 220px; }  /* was 180px */
```

For Y-axis ranges: narrow the fixed bounds to baseline ± 4 standard deviations so the signal occupies at least 60% of the plot area.

---

*Critique produced by design:design-critique skill on 2026-05-10.*
*Screenshot captured via Claude Preview (sim-feed mode, ~20 seconds post-boot).*
