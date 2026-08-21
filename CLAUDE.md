# price-elasticity — repo brief for coding agents

Read this whole file before touching anything. This repo powers a live GM (gross margin) improvement dashboard for Redcliffe Labs, an Indian diagnostics company. It's the code layer of a larger analysis chain that started as chat-based Excel work and is now moving to code + a live Google Sheets backend + a Netlify-hosted static dashboard.

## What this repo is

- `index.html` (originally `gm_action_plan_dashboard.html`) — the live dashboard. Single self-contained HTML file (Chart.js vendored inline in a `<script>` tag — not loaded from a CDN, see caveat below — vanilla JS, no build step, no framework, no npm). Reads data client-side directly from a Google Sheet via the `gviz` JSON endpoint — no backend, no API key, no server. Deploy as-is to Netlify (or any static host).
  - **Chart.js is vendored, not CDN-loaded.** It originally loaded from `cdnjs.cloudflare.com`, which some corporate networks/ad-blockers block outright — that produced a `Chart is not defined` error even though the Sheet data loaded fine (KPI cards populated, charts didn't). Fixed by inlining Chart.js v4.4.4's UMD build directly into the `<head>` `<script>` tag, so the dashboard has zero external JS dependencies. If you ever need to bump the Chart.js version, re-vendor it the same way (pull `dist/chart.umd.js` from the npm tarball and paste it in) rather than reverting to a CDN `<script src>`.
- `gsheet_backend_build_20260821-0000.py` — the Python/pandas script that aggregated the raw booking-level export into the summary tables currently living in the Google Sheet. Re-run (or rewrite) this whenever the raw data needs refreshing at a different grain.

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
| `Settings` | key/value config | `key`, `value`, `notes` — column-name mappings + business thresholds (MOV default, coupon depth ceiling, stacking-risk flag %, impact-tracking window). Edit this tab to retune the model without touching code. |
| `Price_Change_Log` | one row per price move | `Test Code`, `Test Name`, `City`, `Old Offer Price`, `New Offer Price`, `Difference`, `Price Upload` (Yes/No/Recommended), `Change Date` (mostly blank — fill in when a move goes live), `Source` |
| `Coupon_Settings_Log` | point-in-time snapshot, 41 rows | `Coupon Code`, `MOV`, `Type`, `Discount`, `Upper Limit Percentage`, `Create Date` (note: gviz currently fails to parse this date format — shows blank in the dashboard, cosmetic only) |
| `Package_Info` | top-80 packages by volume | `package_code`, `bookings_aug1_16`, `note` — flags rows where `package_code` is actually a comma-separated multi-package combo (e.g. `BC023,BC033`), a real quirk in the source data, not a bug |
| `Booking_Weekly_Summary` | weekly × top-15 package × top-6 city, Aug 1–16 window | `week_start`, `package_bucket`, `city_bucket`, `bookings`, `gm_sum`, `revenue_sum`, `gm_pct`. **This is what the dashboard actually reads** — the JS aliases it internally to `Booking_Summary`, see `TABS`/`ALIAS` at the top of the `<script>` block. |
| `Coupon_Summary` | weekly × top-30 coupon, same window | `week_start`, `coupon_bucket`, `bookings`, `gm_sum`, `revenue_sum`, `repeat_bookings`, `avg_discount_pct`, `gm_pct`, `repeat_share` |
| `Booking_Summary` | **raw booking-level, 55,571 rows, Jun 2–Aug 17** | Full schema below. **Do not wire this into the client-side dashboard** — fetching it via the gviz JSON endpoint returns a ~52MB response, which will hang or crash a browser tab. It exists as a reference/source tab only. If you need row-level analysis, either (a) pull a date/city/package-filtered slice server-side (Python + the Sheets API, not gviz-in-browser), or (b) re-run `gsheet_backend_build_20260821-0000.py` against it and push a new pre-aggregated tab, same pattern as `Booking_Weekly_Summary`. Rename this tab to something less confusable with `Booking_Weekly_Summary` if you get the chance (e.g. `Raw_Bookings`) — kept as-is for now to avoid another 52MB round-trip just to rename it. |

**Known scope limit, worth fixing if you're picking this up**: `Booking_Weekly_Summary` is intentionally narrow (top-15 packages × top-6 cities, no customer_category/Fresh-Repeat split) because pushing a wider aggregate through the Sheets API one cell-range at a time was too slow/expensive in the original build session. Now that the raw tab exists, the better move is a **server-side** re-aggregation step (pandas, reading the Sheet via the Sheets API or a local export) that pushes a wider `Booking_Weekly_Summary` — segment splits, more packages/cities — not a client-side rewrite of the dashboard to read the 52MB raw tab directly.

### Raw source schema (`Booking_Summary` tab, 42 columns, reference only — see caveat above)

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
