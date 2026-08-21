# Dashboard Visualization Spec — price-elasticity / GM Action Plan

**Read `CLAUDE.md` first.** This doc assumes you already know: the Google Sheet ID and tab schema, the `&headers=1` gviz gotcha, the GM formula (`GM = Collected Net Revenue − cpt`), why the raw `Booking_Summary` tab (52MB) must never be fetched client-side, and where `V5_Methodology.md` lives. This file is the build spec for expanding `gm_action_plan_dashboard.html` from its current 2-chart Overview into full coverage of the raw data. Don't re-derive methodology here — reference it.

**How to use this doc.** Section A lists new backend tabs that must exist before certain visualizations can be built (the raw tab is too large for the browser, so new pre-aggregated tabs are the only path — same pattern as `Booking_Weekly_Summary`/`Coupon_Summary`). Section B is the master index. Section C is the per-visualization spec, grouped by theme, each with an ID you can reference in commits/PRs. Build in priority order (P0 → P2) unless told otherwise — each is independently shippable.

---

## A. New backend tabs required (build these first)

All produced by extending `gsheet_backend_build_*.py` (new timestamped copy per this repo's script-naming convention) against the raw `Booking_Summary` tab (or a fresh local export of the same data — see `CLAUDE.md` §Raw source schema). Push via the Sheets API, same pattern as existing tabs. Keep every tab's row count in the low thousands at most — that's what keeps gviz fetches fast; bucket long-tail dimensions into `OTHER` exactly like `Booking_Weekly_Summary` does for package/city.

| New tab | Grain | Columns | Powers |
|---|---|---|---|
| `Segment_Summary` | week × `customer_category` × `Booking_Flag` × city_bucket(top-6) | `week_start, customer_category, booking_flag, city_bucket, bookings, gm_sum, revenue_sum, gm_pct, asp` | SEG-01 to SEG-04 |
| `Channel_Summary` | week × `booked_by` × city_bucket(top-6) | `week_start, booked_by, city_bucket, bookings, gm_sum, revenue_sum, gm_pct, avg_discount_pct` | CHAN-01 to CHAN-03 |
| `Discount_Stacking_Summary` | week × `n_disc_types` (0/1/2/3+, computed as count of nonzero among special/vip/coupon/redcash/giftcard) | `week_start, n_disc_types, bookings, gm_sum, revenue_sum, gm_pct` | COUP-01 (extends existing depth chart) |
| `Slot_Summary` | `collection_slot` bucket × `pickup_status` | `collection_slot, pickup_status, bookings` | OPS-01, OPS-02 |
| `Geo_Summary` | week × `city` (wider than top-6 — top-20) × `Zone` | `week_start, city, zone, bookings, gm_sum, revenue_sum, gm_pct, asp` | GEO-01, GEO-02 |
| `DoD_Summary` | **daily** (not weekly) × package_bucket(top-15) × city_bucket(top-6) | `booking_date, package_bucket, city_bucket, bookings, gm_sum, revenue_sum, gm_pct` | CADENCE-01 |
| `Financial_Waterfall_Summary` | week only, no other dimension | `week_start, offer_price_sum, special_discount_sum, vip_discount_sum, coupon_discount_sum, redcash_sum, giftcard_sum, collected_net_revenue_sum, cpt_sum, gm_sum` | FIN-01 |
| `Agent_Summary` | week × `agent_id` (top-20 by volume, Sales-booked only) | `week_start, agent_id, bookings, gm_sum, revenue_sum, gm_pct` | CHAN-04 |
| `MOV_Compliance_Summary` | week × `coupon_bucket` | `week_start, coupon_bucket, bookings, bookings_below_mov, pct_below_mov` — join against `Coupon_Settings_Log.MOV` | COUP-04 |
| `ADDFAMILY_Verification` | week × `coupon_bucket` (ADDFAMILY2/3/4 only) | `week_start, coupon_bucket, bookings, avg_total_member, avg_discount_pct, pct_vip_stacked, pct_self_channel` | COUP-03 |

`Package_Info` and `Coupon_Settings_Log` already exist and don't need new tabs — PKG-01 to PKG-03 and RULES-01 read from them directly. `Competitor_Price_Gap` (PRICE-03) reads from `Redcliffe labs Pricing top tests - Top Competition - August 2026.xlsx` — push as a new tab if not already in the Sheet; it's mostly static, refresh only when the team updates that file.

**Every new tab needs a corresponding block added to the `Settings` tab** (field-name mappings, same pattern as existing `field_gm`/`field_revenue`/etc.) — don't hardcode column names into chart code.

---

## B. Visualization index

| ID | Title | Source tab(s) | Chart type | Priority |
|---|---|---|---|---|
| PRICE-01 | Price change event impact tracker | `Price_Change_Log` × `DoD_Summary` | Timeline + before/after delta cards | P0 |
| PRICE-02 | Elasticity scatter | `Price_Change_Log` (needs `predicted_elasticity` column added) | Scatter, colored by confidence tier | P1 |
| PRICE-03 | Competitor price-gap chart | `Competitor_Price_Gap` (new) | Grouped bar per test | P1 |
| PRICE-04 | GM-breakeven band | `Price_Change_Log` + `Package_Info` (cpt) | Range/band chart | P2 |
| COUP-01 | Discount-stacking heatmap | `Discount_Stacking_Summary` (new) | Heatmap (n_disc_types × week) | P0 |
| COUP-02 | GM% vs. discount depth | `Coupon_Summary` (**exists**) | Bubble | — (already live) |
| COUP-03 | ADDFAMILY tier verification | `ADDFAMILY_Verification` (new) | Grouped bar (member count vs. discount%) | P1 |
| COUP-04 | MOV compliance | `MOV_Compliance_Summary` (new) | Bar, one per coupon | P1 |
| COUP-05 | Coupon lifecycle/adoption curve | `Coupon_Summary` + `Coupon_Settings_Log.Create Date` | Line, days-since-launch on x-axis | P2 |
| SEG-01 | Fresh vs. Repeat: GM%/AOV/volume trend | `Segment_Summary` (new) | 3-line trend, small multiples | P0 |
| SEG-02 | Customer category comparison (regular/vip/vip gold) | `Segment_Summary` (new) | Grouped bar | P0 |
| SEG-03 | VIP Gold fresh-share trend | `Segment_Summary` (new), filter `customer_category=vip gold` | Line + stacked area (fresh vs repeat share) | P0 — **this is the metric from the "2.9x AOV gap" discussion, now independently verifiable** |
| SEG-04 | City × segment cross-tab | `Segment_Summary` (new) | Heatmap or matrix table | P1 |
| CHAN-01 | Channel split trend (Self/Sales/Phlebo) | `Channel_Summary` (new) | Stacked area, volume + GM% | P0 |
| CHAN-02 | Channel × discount depth | `Channel_Summary` (new) | Grouped bar | P1 |
| CHAN-03 | Channel GM%/AOV comparison | `Channel_Summary` (new) | Bar | P1 |
| CHAN-04 | Agent leaderboard | `Agent_Summary` (new) | Sortable table | P2 |
| PKG-01 | Full-universe package GM% ranking | `Package_Info` + `Booking_Weekly_Summary` | Sortable/filterable table (already partially exists as Package Explorer — extend) | P0 |
| PKG-02 | Multi-package combo GM impact | `Package_Info` (combo flag) + `Booking_Weekly_Summary` | Comparison bar: combo vs. single-package GM% | P1 |
| PKG-03 | `is_premium` split | needs `is_premium` added to `Booking_Weekly_Summary` or a new cut | Bar | P2 |
| GEO-01 | City/Zone GM% ranking | `Geo_Summary` (new) | Sortable table + bar, not literal map | P0 |
| GEO-02 | AOV-by-city outlier view | `Geo_Summary` (new) | Bar with outlier threshold line | P1 |
| OPS-01 | Time-of-day booking heatmap | `Slot_Summary` (new) | Heatmap | P2 |
| OPS-02 | Pickup status funnel | `Slot_Summary` (new) | Funnel/stacked bar | P2 |
| FIN-01 | Revenue-to-GM waterfall | `Financial_Waterfall_Summary` (new) | Waterfall chart | P0 |
| CADENCE-01 | True day-on-day trend | `DoD_Summary` (new) | Line, daily grain | P0 |
| CADENCE-02 | WoW scorecard | `Booking_Weekly_Summary` + `Coupon_Summary` | Scorecard table with WoW deltas (extends existing Overview KPI cards) | P1 |
| RISK-01 | Price × coupon stacking risk | `Price_Change_Log` × `Coupon_Summary` | Table (**exists in prior xlsx model — port to dashboard**) | P0 |
| RISK-02 | Coupon health scorecard | `Coupon_Summary` + `Discount_Stacking_Summary` | Composite score card, live-computed (not a one-off writeup) | P1 |

---

## C. Detailed specs

Format per entry: **Data** (tab, columns, filters) → **Compute** (client-side aggregation/joins the JS must do) → **Chart** (type, library — Chart.js unless noted) → **Caveats** (pull from `V5_Methodology.md`/`CLAUDE.md`, don't restate the whole doc, just what's relevant to *this* chart).

### PRICE-01 — Price change event impact tracker
**Data**: `Price_Change_Log` rows with non-blank `Change Date`, joined to `DoD_Summary` filtered to same `Test Code`≈`package_bucket` and `City`≈`city_bucket`.
**Compute**: for each event, sum bookings/GM/revenue in the `impact_tracking_window_days` (from `Settings`) before vs. after `Change Date`. Compute actual GM% delta and actual ASP delta.
**Chart**: timeline of events (dots on a date axis) + a detail card per event showing predicted vs. actual impact side by side.
**Caveats**: `Test Code` in `Price_Change_Log` doesn't always match `package_code` exactly (multi-test names, combo codes) — exact-match only for v1, flag unmatched rows rather than guessing a fuzzy match. Price elasticity is NOT stacking-aware (§V5_Methodology.md) — a coincident coupon change in the same window will contaminate the "actual" read; check `Coupon_Settings_Log`/`ADDFAMILY_Verification` for concurrent changes and annotate if found, don't silently present a clean number.

### PRICE-02 — Elasticity scatter
**Data**: `Price_Change_Log`, needs a `predicted_elasticity` and `confidence_tier` column added (pull from the existing elasticity model output, not recomputed here).
**Chart**: scatter, x = price change %, y = volume change % (from PRICE-01's before/after), point color = confidence tier (A/B/C per existing convention).
**Caveats**: only plot events with both a `Change Date` and a resolved before/after window — don't plot "Recommended" (not-yet-executed) rows.

### PRICE-03 — Competitor price-gap chart
**Data**: new `Competitor_Price_Gap` tab (push from the competitor xlsx, columns: Test, City, Redcliffe price, Tata delta, Healthians delta, Dr Lal delta).
**Chart**: grouped horizontal bar per test, one bar per competitor showing ± gap.
**Caveats**: per V5_Methodology.md §6, several team recommendations raise price while Healthians is already pricing below Redcliffe on that specific test — surface this as a warning badge on affected rows, don't just show the raw gap.

### PRICE-04 — GM-breakeven band
**Data**: `Package_Info` (cpt), `Price_Change_Log` (current/recommended price).
**Chart**: range/floor-ceiling bar — current price vs. calculated breakeven price (`-Price/(Price-Cost)` formula from methodology) vs. recommended price.
**Caveats**: this is illustrative of the pricing logic, not a live recompute of the elasticity model — labeled as such.

### COUP-01 — Discount-stacking heatmap
**Data**: `Discount_Stacking_Summary` (new).
**Chart**: heatmap, x = week, y = n_disc_types (0/1/2/3+), color = GM%.
**Caveats**: matches the existing "discount stacking degrades GM%" finding — this makes it visual/time-series instead of a single static number.

### COUP-02 — GM% vs. discount depth
Already live (`Coupon Performance` tab, bubble chart). No change needed — just cross-reference it from the new COUP-01/03/04 views so they read as one coherent section, not scattered tabs.

### COUP-03 — ADDFAMILY tier verification
**Data**: `ADDFAMILY_Verification` (new).
**Chart**: grouped bar — x = tier (2/3/4 member), two series: avg_total_member (should track 2/3/4 almost exactly) and avg_discount_pct (should track 20/25/30% caps).
**Caveats**: per V5_Methodology.md §4.4, this has verified as working-as-designed — this chart should make that verification durable/visual, not just a one-time text claim.

### COUP-04 — MOV compliance
**Data**: `MOV_Compliance_Summary` (new), joined to `Coupon_Settings_Log.MOV`.
**Chart**: bar per coupon, height = % of bookings below stated MOV.
**Caveats**: this is a proxy on `offer_price` (single package), not real cart value — label the chart title/subtitle with this caveat every time it renders, per the existing methodology note. Don't let it read as a confirmed breach.

### COUP-05 — Coupon lifecycle/adoption curve
**Data**: `Coupon_Summary` + `Coupon_Settings_Log.Create Date` (note: this field currently fails to parse via gviz on some rows — see CLAUDE.md — handle nulls gracefully).
**Chart**: line, x = weeks since Create Date, y = bookings, one line per coupon (or small multiples for top 5).

### SEG-01 — Fresh vs. Repeat trend
**Data**: `Segment_Summary` (new), grouped by `Booking_Flag`.
**Chart**: 3 small-multiple line charts (GM%, AOV, volume) each with 2 lines (Fresh/Repeat).

### SEG-02 — Customer category comparison
**Data**: `Segment_Summary` (new), grouped by `customer_category`.
**Chart**: grouped bar, 3 categories × (GM%, AOV, volume as small multiples or a toggle).

### SEG-03 — VIP Gold fresh-share trend
**Data**: `Segment_Summary` filtered to `customer_category = vip gold`.
**Compute**: fresh_share = fresh bookings / total bookings, per week.
**Chart**: line (fresh share %) + stacked area (fresh vs. repeat volume) underneath.
**Caveats**: this is the exact metric that was previously sourced from an external, unverified deepdive and only partially cross-checked. Once this chart exists, it becomes the source of truth — update `V5_Methodology.md` to point here instead of the external analysis once built and verified.

### SEG-04 — City × segment cross-tab
**Data**: `Segment_Summary` (new).
**Chart**: matrix/heatmap table, rows = top cities, columns = segment (Fresh-Regular, Repeat-Regular, Fresh-VIP, ... Fresh-VIP Gold, Repeat-VIP Gold), cell = GM% or AOV (toggle).

### CHAN-01 — Channel split trend
**Data**: `Channel_Summary` (new).
**Chart**: stacked area (volume by `booked_by` over weeks) + separate line overlay for blended GM%.

### CHAN-02 — Channel × discount depth
**Data**: `Channel_Summary` (new).
**Chart**: grouped bar, x = channel, y = avg_discount_pct.
**Caveats**: earlier analysis flagged a possible Phlebo ancillary-attach gap — if this chart shows Phlebo materially more/less discounted, note it but don't re-open the "ancillary fee attach" framing the user explicitly rejected — frame any Phlebo finding in fresh/repeat/AOV/city terms per the standing mandate.

### CHAN-03 — Channel GM%/AOV comparison
**Data**: `Channel_Summary` (new).
**Chart**: bar, dual-axis (GM% and AOV).

### CHAN-04 — Agent leaderboard
**Data**: `Agent_Summary` (new).
**Chart**: sortable table, min-booking threshold filter (avoid single-booking noise skewing the list — use a similar floor to the Phlebo dashboard's "min 15 bookings" convention).

### PKG-01 — Full-universe package GM% ranking
**Data**: `Package_Info` + `Booking_Weekly_Summary`.
**Chart**: extend the existing Package Explorer table — it's currently capped at top-15 packages from `Booking_Weekly_Summary`; this should either widen that tab's package coverage or add a separate "all packages, by GM%" ranked table sourced from `Package_Info`'s booking counts joined to a wider aggregate.
**Caveats**: `package_code` combo strings (flagged in `Package_Info.note`) should be visually distinguished (badge/icon), not silently ranked alongside single-package rows.

### PKG-02 — Multi-package combo GM impact
**Data**: `Package_Info` (combo flag) + `Booking_Weekly_Summary`.
**Chart**: two-bar comparison — avg GM% for combo bookings vs. single-package bookings.

### PKG-03 — `is_premium` split
**Data**: needs `is_premium` folded into an aggregate (not currently in any pushed tab).
**Chart**: simple bar, GM%/AOV by premium flag.

### GEO-01 — City/Zone GM% ranking
**Data**: `Geo_Summary` (new, top-20 cities not top-6).
**Chart**: sortable bar/table, not a literal geographic map (no mapping library in the stack — keep it simple per the "no build tooling" convention).

### GEO-02 — AOV-by-city outlier view
**Data**: `Geo_Summary` (new).
**Chart**: bar with a horizontal reference line at the median/mean, outliers highlighted.
**Caveats**: this is exactly the Gurugram-AOV-outlier finding from the ASP Action Plan — treat this chart as the ongoing monitor for that open investigation, not a new finding each time.

### OPS-01 — Time-of-day booking heatmap
**Data**: `Slot_Summary` (new).
**Chart**: heatmap, x = collection_slot buckets, y = day-of-week (if added) or just a single-row heatmap if `Slot_Summary` doesn't carry date.

### OPS-02 — Pickup status funnel
**Data**: `Slot_Summary` (new).
**Chart**: funnel or stacked bar (confirmed/pending/failed/etc. as % of total).

### FIN-01 — Revenue-to-GM waterfall
**Data**: `Financial_Waterfall_Summary` (new).
**Chart**: waterfall (Chart.js doesn't have a native waterfall type — build with a stacked bar using invisible "base" segments, standard technique, or add the `chartjs-chart-financial`/floating-bar approach; don't add a whole new charting library for this one chart).
**Caveats**: this must reconcile exactly to `GM = Collected Net Revenue − cpt` — if the waterfall's ending value doesn't match `gm_sum` from other tabs for the same week, that's a bug, not a rounding footnote. Sanity-check before shipping.

### CADENCE-01 — True day-on-day trend
**Data**: `DoD_Summary` (new, daily grain).
**Chart**: line, daily GM%/bookings/revenue, with the known-partial-day dates (per `Settings.clean_window`) visually distinguished (dashed line segment or shaded region) rather than silently plotted as equal-confidence data.

### CADENCE-02 — WoW scorecard
**Data**: `Booking_Weekly_Summary` + `Coupon_Summary` (already have the data; this is a presentation extension of the existing Overview KPI cards).
**Chart**: table, one row per week, columns = bookings/GM/revenue/GM% with WoW % change, conditionally formatted (green/red) — extends the existing KPI-card delta logic into a fuller table.

### RISK-01 — Price × coupon stacking risk
**Data**: `Price_Change_Log` (rows with Price Upload = Yes/Recommended) × `Coupon_Summary` (top coupon per package, if package-level coupon attribution is added — currently `Coupon_Summary` is coupon-level only, not package-level; may need a `Package_Coupon_Summary` cross tab, or port the static 4-row finding from `ASP_Action_Plan.xlsx` §4 as a start and note it needs a live join to become dynamic).
**Chart**: table, matches the existing `Coupon Ceilings & Controls` section format from `ASP_Action_Plan.xlsx`.

### RISK-02 — Coupon health scorecard
**Data**: `Coupon_Summary` + `Discount_Stacking_Summary`.
**Compute**: composite score across revenue/volume/AOV/repeat-quality/concentration/discount-efficiency dimensions — same rubric as the ad hoc scorecard built earlier in this engagement, but computed live from real numbers each time the sheet refreshes, not re-typed by hand.
**Chart**: score cards/gauges, one per dimension, plus an overall composite.
**Caveats**: keep the scoring rubric itself in `Settings` (thresholds for what counts as "healthy" per dimension) so it's tunable without a code change, consistent with this repo's existing pattern.

---

## D. Standing rules for whoever builds this (repeats CLAUDE.md, intentionally — read it there for full context)

1. Every new tab goes through the `Settings`-tab column-mapping pattern — no hardcoded column names in chart JS.
2. Never wire the raw `Booking_Summary` tab into client-side fetches. All new visualizations read pre-aggregated tabs only.
3. `&headers=1` on every gviz fetch, no exceptions.
4. GM = Collected Net Revenue − cpt. Never substitute a different cost basis.
5. Flag partial/unreliable dates visually wherever a chart could otherwise imply confidence it doesn't have (see CADENCE-01, and the Aug 17-20 collection-lag pattern already seen once in this data).
6. One file, no build step, Chart.js from CDN — matches this repo's and the two sibling Redcliffe dashboards' conventions.
7. When a visualization here duplicates or supersedes a finding currently written as prose in `V5_Methodology.md` (e.g. SEG-03 vs. the VIP Gold AOV gap writeup), update that doc to point at the live chart once built and verified — don't let the two drift into contradicting each other.
