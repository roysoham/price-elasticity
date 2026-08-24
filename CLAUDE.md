# price-elasticity — repo brief for coding agents

Read this whole file before touching anything. This repo powers a live GM (gross margin) improvement dashboard for Redcliffe Labs, an Indian diagnostics company. It's the code layer of a larger analysis chain that started as chat-based Excel work and is now moving to code + a live Google Sheets backend + a Netlify-hosted static dashboard.

**Expanding the dashboard's visualizations?** Read `DASHBOARD_VISUALIZATION_SPEC.md` in this same repo root first — it's the build spec (new backend tabs required, full visualization index, per-chart data/compute/caveat specs) for taking the dashboard from its current small set of charts to full coverage of the raw data. This is the standing convention for all future dashboard/HTML build work on this repo, not a one-off doc.

## What this repo is

- `index.html` (originally `gm_action_plan_dashboard.html`) — the live dashboard. Single self-contained HTML file (Chart.js vendored inline in a `<script>` tag — not loaded from a CDN, see caveat below — vanilla JS, no build step, no framework, no npm). Reads data client-side directly from a Google Sheet via the `gviz` JSON endpoint — no backend, no API key, no server. Deploy as-is to Netlify (or any static host).
  - **Chart.js is vendored, not CDN-loaded.** It originally loaded from `cdnjs.cloudflare.com`, which some corporate networks/ad-blockers block outright — that produced a `Chart is not defined` error even though the Sheet data loaded fine (KPI cards populated, charts didn't). Fixed by inlining Chart.js v4.4.4's UMD build directly into the `<head>` `<script>` tag, so the dashboard has zero external JS dependencies. If you ever need to bump the Chart.js version, re-vendor it the same way (pull `dist/chart.umd.js` from the npm tarball and paste it in) rather than reverting to a CDN `<script src>`.
- `gsheet_backend_build_20260821-0000.py` / `gsheet_backend_build_20260821-1400.py` / `gsheet_backend_build_20260824-1100.py` — the Python/pandas scripts that aggregated the raw booking-level export into the summary tables living in the Google Sheet. The 20260824 one is the current one — it rebuilds all 10 tabs (the original 3 plus the 7 P0 tabs) in a single run, superseding the two earlier scripts' narrower scope. Re-run (or write a new timestamped copy) whenever the raw data needs refreshing or a new pre-aggregated tab is needed — see `DASHBOARD_VISUALIZATION_SPEC.md` §A for the pattern.
- `online_discount_summary__raw_<date-range>MTD.xlsx` (repo root, currently `online_discount_summary__raw_1to23AugMTD.xlsx`) — **the canonical raw booking-level export, 75,199 rows, Jun 2–Aug 23 2026, 42 columns (schema below).** Lives in the repo, not in the Google Sheet — see "Raw data source" below for why and for the refresh convention.

## Raw data source — repo file, not a Sheet tab

The raw booking-level export lives in the repo root as `online_discount_summary__raw_<date-range>.xlsx` (e.g. `online_discount_summary__raw_1to23AugMTD.xlsx`), **not** in the Google Sheet. This changed 2026-08-24: earlier pulls were pasted into a `Booking_Summary` Sheet tab, but at ~75k rows the paste itself became unreliable (Sheets UI stalling mid-paste) well before hitting any gviz size limit. The repo file is the more reliable canonical source now — a `gsheet_backend_build_*.py` run reads it directly with pandas, no Sheets round-trip needed for the raw data itself (only the pre-aggregated *output* tabs get pushed to the Sheet, via the Sheets API, same as always).

**Refreshing the raw data**: drop the new export into the repo root using the same `online_discount_summary__raw_<date-range>.xlsx` naming pattern (matches what `gsheet_backend_build_*.py` scripts already expect as `SRC`), delete the now-superseded older file in the same change (`git rm`) so the repo doesn't accumulate multiple stale multi-MB raw dumps, and update this section's row count/date range. Point the next `gsheet_backend_build_*.py` run's `SRC` at the new filename.

**The `Booking_Summary` Sheet tab itself has been cleared** (data removed, tab structure kept) now that the repo file is the source of truth — don't paste raw data into it going forward, and don't expect it to have rows if you open the Sheet.

## Data source — Google Sheet (the actual backend)

Spreadsheet ID: `1lJfg79zQ1hQUKh_IHqkzzkTuUW9kdJGHfvg8bLcdTCk` (title in the UI: "Backend data for Price Elasticity").

Fetch pattern used throughout the dashboard JS:
```js
`https://docs.google.com/spreadsheets/d/${SHEET_ID}/gviz/tq?tqx=out:json&sheet=${sheetName}&headers=1`
```
**The `&headers=1` is not optional.** Without it, Google's gviz endpoint sometimes fails to auto-detect the header row (especially on sheets where column A is all-string, like `Settings`) and silently merges the first several data rows into the column labels, corrupting the parse. This bit us once already — don't drop it.

Requires the sheet's general access to be "Anyone with the link → Viewer". This is the same pattern used by the two other live Redcliffe dashboards on Netlify (`enchanting-strudel-cff41c.netlify.app` — Dead Slot Attribution, `phlebo-productivity.netlify.app` — Phlebo Productivity) — match their conventions where sensible (badge colors, sortable-table pattern, "Refresh Data" button, footer data-basis note) rather than inventing a new house style.

### Current tabs and schema

| Tab | Grain | Key columns |
|---|---|---|
| `Settings` | key/value config | `key`, `value`, `notes` — column-name mappings + business thresholds (MOV default, coupon depth ceiling, stacking-risk flag %, impact-tracking window). Edit this tab to retune the model without touching code. The duplicate `clean_window` key (08-01/08-16 vs 08-01/08-19) flagged here previously was fixed 2026-08-24 — there's now a single `clean_window` row. |
| `Price_Change_Log` | one row per price move | `Test Code`, `Test Name`, `City`, `Old Offer Price`, `New Offer Price`, `Difference`, `Price Upload` (Yes/No/Recommended), `Change Date` (mostly blank — fill in when a move goes live), `Source` |
| `Coupon_Settings_Log` | point-in-time snapshot, 41 rows | `Coupon Code`, `MOV`, `Type`, `Discount`, `Upper Limit Percentage`, `Create Date` (note: gviz currently fails to parse this date format — shows blank in the dashboard, cosmetic only) |
| `Package_Info` | top-80 packages by volume | `package_code`, `bookings_aug1_22`, `note` — flags rows where `package_code` is actually a comma-separated multi-package combo (e.g. `BC023,BC033`), a real quirk in the source data, not a bug. **Fetched by the dashboard but not currently read by any chart** — PKG-01 ended up sourced from `Package_GM_Summary` instead, which carries `is_combo` directly. Harmless (small tab, fast fetch), but worth knowing if you're tracing why a column here doesn't show up anywhere in the JS. |
| `Booking_Weekly_Summary` | weekly × top-15 package × top-6 city, Aug 1–22 window | `week_start`, `package_bucket`, `city_bucket`, `bookings`, `gm_sum`, `revenue_sum`, `gm_pct`. **This is what the dashboard actually reads** — the JS aliases it internally to `Booking_Summary`, see `TABS`/`ALIAS` at the top of the `<script>` block. |
| `Coupon_Summary` | weekly × top-30 coupon, same window | `week_start`, `coupon_bucket`, `bookings`, `gm_sum`, `revenue_sum`, `repeat_bookings`, `avg_discount_pct`, `gm_pct`, `repeat_share` |
| `Segment_Summary` | week × `customer_category` × `Booking_Flag` × city_bucket(top-6), clean window 08-01/08-22 | `week_start`, `customer_category`, `booking_flag`, `city_bucket`, `bookings`, `gm_sum`, `revenue_sum`, `gm_pct`, `asp`. Powers SEG-01 to SEG-04 (`DASHBOARD_VISUALIZATION_SPEC.md`). |
| `Channel_Summary` | week × `booked_by` × city_bucket(top-6), same window | `week_start`, `booked_by`, `city_bucket`, `bookings`, `gm_sum`, `revenue_sum`, `gm_pct`, `avg_discount_pct`. Powers CHAN-01 to CHAN-03. |
| `Discount_Stacking_Summary` | week × `n_disc_types` (0/1/2/3+, count of nonzero among special/vip/coupon/redcash/giftcard discounts), same window | `week_start`, `n_disc_types`, `bookings`, `gm_sum`, `revenue_sum`, `gm_pct`. Powers COUP-01. **Two** weeks now show negative GM% at 3+ stacked discounts on the 2026-08-24 refresh — week of Aug 10 (−5.0%, 40 bookings) and week of Aug 17 (−6.7%, 31 bookings). Both tiny samples, but two independent weeks landing negative is a stronger signal than the single-week read from the previous refresh — worth escalating past "watch" if a third week lands the same way. |
| `Geo_Summary` | week × city (top-20, wider than the top-6 used elsewhere) × Zone (top-30), same window | `week_start`, `city`, `zone`, `bookings`, `gm_sum`, `revenue_sum`, `gm_pct`, `asp`. Powers GEO-01/02. Zone bucketing (top-30 + OTHER) was our own call — the spec didn't pin a number, 211 raw zones was too many to leave unbucketed. |
| `DoD_Summary` | **daily** (not weekly) × package_bucket(top-15) × city_bucket(top-6), full Jun 2–Aug 23 range | `booking_date`, `package_bucket`, `city_bucket`, `bookings`, `gm_sum`, `revenue_sum`, `gm_pct`, `is_partial` (true outside the 08-01/08-22 clean window — render those days visually distinct, don't plot as equal-confidence). Powers CADENCE-01 and the Overview "Monthly Insights" box (client-side rollup of this same tab to calendar-month grain, no separate tab). |
| `Financial_Waterfall_Summary` | week only, clean window rows with a computed `Gross_Margin` only (excludes collection-lag rows — see caveat below) | `week_start`, `offer_price_sum`, `special_discount_sum`, `vip_discount_sum`, `coupon_discount_sum`, `redcash_sum`, `giftcard_sum`, `collected_net_revenue_sum`, `cpt_sum`, `gm_sum`. Powers FIN-01. Reconciles exactly to `gm_sum = collected_net_revenue_sum − cpt_sum` — verified before push, re-verify after any refresh. |
| `Package_GM_Summary` | full package universe (≥10 bookings kept individually, else `OTHER`), clean window, no week/city split | `package_code`, `bookings`, `gm_sum`, `revenue_sum`, `gm_pct`, `asp`, `is_combo` (gviz reads this as the string `'True'`/`'False'`, not a native bool — compare accordingly). Powers PKG-01; not explicitly named in `DASHBOARD_VISUALIZATION_SPEC.md` §A but needed to make that P0 item buildable (full-universe ranking wider than `Booking_Weekly_Summary`'s top-15). |
| `Booking_Summary` | **empty — cleared 2026-08-24** | No longer holds data. The raw export now lives as a repo file (`online_discount_summary__raw_<date-range>.xlsx`) instead — see "Raw data source" above. This tab was never wired into the client-side dashboard and never will be (gviz would hang/crash a browser tab on a 75k-row response); it existed only as a raw-data staging area, and the paste itself became unreliable at that row count, so that role moved to the repo file. Left in the Sheet as an empty placeholder rather than deleted outright. |

**Known scope limit, worth fixing if you're picking this up**: `Booking_Weekly_Summary` is intentionally narrow (top-15 packages × top-6 cities, no customer_category/Fresh-Repeat split) because pushing a wider aggregate through the Sheets API one cell-range at a time was too slow/expensive in the original build session. The better move is a **server-side** re-aggregation step (pandas, reading the `online_discount_summary__raw_*.xlsx` repo file directly) that pushes a wider `Booking_Weekly_Summary` — segment splits, more packages/cities — not a client-side rewrite of the dashboard to read a huge raw file/tab directly.

### Raw source schema (`online_discount_summary__raw_*.xlsx` repo file, 42 columns)

```
collection_slot, booking_date, booking_slot, lead_id, booking_id, total_member,
fresh_members, repeat_members, Booking_Flag, customer_category, Gross_Margin, cpt,
GM %, offer_price, booked_by, Collected Net Revenue, special_discount, vip_discount,
coupon_discount, diagnostic_cost, express_slot, vip_paid_amount, report_hardcopy_cost,
redcash, giftcard, referral, collection_date, final_paid_amount, diff, agent_id,
pickup_status, special_discount %, vip_discount %, coupon_discount %,
redcash_discount %, Total_Discount, city, Total_Discount %, is_premium,
package_code, Zone, coupon_code
```

## Non-negotiable conventions (get these wrong and every downstream number is wrong)

- **`GM = Collected Net Revenue − cpt`.** `cpt` is the only real cost field. `diagnostic_cost`, `express_slot`, `vip_paid_amount`, `report_hardcopy_cost` are customer-paid fees, not company costs — never subtract them from margin.
- **Booking_Flag**: Fresh / Repeat. **customer_category**: regular / vip / vip gold. **booked_by** (channel): Self / Sales / Phlebo.
- **Discount stacking**: a booking can carry `special_discount`, `vip_discount`, `coupon_discount`, `redcash`, `giftcard` simultaneously. Never read `coupon_discount = 0` as "no discount" without checking the others.
- **Date reliability**: the raw export's earliest booking dates are unreliable (`Gross_Margin` is sparse before a booking has actually collected — collection-date lag), and the most recent day in any pull is usually a partial day. Always sanity-check daily row counts before trusting the edges of a new pull.
- **VIP Gold discount stacks at two layers on the live site** (confirmed via manual browser walkthrough, Aug 2026): package-page level shows 15% off that item's offer price; cart-level applies a second "VIP Gold Discount (15%)" against the cart subtotal. Confirm with eng whether this is by design before building messaging around it.
- **`package_code` is sometimes a multi-package combo string**, not a single SKU (see `Package_Info` note column). Any package-level analysis needs to decide explicitly whether to split, exclude, or bucket these — don't silently treat them as single packages.

## Full methodology and known gaps

The complete analytical methodology (elasticity model, GM-breakeven pricing logic, coupon depth-vs-margin findings, VIP Gold segment analysis, competitor pricing cross-check, and a running list of known gaps/caveats) lives outside this repo, in `V5_Methodology.md` in the Redcliffe Labs "GM Improvement" working folder. If you don't have access to that file, ask for it before making any pricing or coupon recommendation — this repo is the display layer; the methodology doc is the source of truth for what the numbers mean and how confident to be in them. Key things it documents that aren't obvious from the data alone:
- Price recommendations use a GM-breakeven elasticity threshold (`-Price/(Price-Cost)` with a 20% safety buffer), not a flat "cut if elasticity < -1" rule — the flat rule was tried first and produced GM-negative recommendations.
- The coupon depth-vs-margin curve was wrong in an earlier round (small-sample proxy method said FREEDOM50 was a ~1% GM near-giveaway; the real, directly-joined number is 47.9%) — always prefer the direct `coupon_code` join over any name-matching workaround.
- Real GM% (not revenue or AOV) declines monotonically with coupon discount depth — don't let an AOV-based "deeper coupons are basket-builders" argument override the GM read.
- Price elasticity is still NOT stacking-aware (doesn't control for concurrent coupon/VIP discount changes during a price-change event) — flagged as a next-round priority, unresolved as of this writing.

## Working style for this project

- Ship working, self-contained code. No build tooling unless there's a real reason for it — the two sibling Redcliffe dashboards on Netlify are both single-file static HTML, and that's proven to work for this audience (non-engineering, Netlify drag-deploy).
- Every number on the dashboard should be traceable to a specific Sheet tab and column — no hardcoded/mocked figures in the shipped file.
- When you change what a tab means or add a new one, update the "Current tabs and schema" table above in the same change — this file is meant to stay accurate, not become stale documentation.
- Before recommending a price or coupon action, sanity-check it against the GM-first convention above — the project owner has explicitly rejected revenue/AOV-only framing multiple times.
