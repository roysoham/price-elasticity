# price-elasticity — repo brief for coding agents

Read this whole file before touching anything. This repo powers a live GM (gross margin) improvement dashboard for Redcliffe Labs, an Indian diagnostics company. It's the code layer of a larger analysis chain that started as chat-based Excel work and is now moving to code + a live Google Sheets backend + a Netlify-hosted static dashboard.

**Expanding the dashboard's visualizations?** Read `DASHBOARD_VISUALIZATION_SPEC.md` in this same repo root first — it's the build spec (new backend tabs required, full visualization index, per-chart data/compute/caveat specs) for taking the dashboard from its current small set of charts to full coverage of the raw data. This is the standing convention for all future dashboard/HTML build work on this repo, not a one-off doc.

## What this repo is

- `index.html` (originally `gm_action_plan_dashboard.html`) — the live dashboard. Single self-contained HTML file (Chart.js vendored inline in a `<script>` tag — not loaded from a CDN, see caveat below — vanilla JS, no build step, no framework, no npm). Reads data client-side directly from a Google Sheet via the `gviz` JSON endpoint — no backend, no API key, no server. Deploy as-is to Netlify (or any static host).
  - **Chart.js is vendored, not CDN-loaded.** It originally loaded from `cdnjs.cloudflare.com`, which some corporate networks/ad-blockers block outright — that produced a `Chart is not defined` error even though the Sheet data loaded fine (KPI cards populated, charts didn't). Fixed by inlining Chart.js v4.4.4's UMD build directly into the `<head>` `<script>` tag, so the dashboard has zero external JS dependencies. If you ever need to bump the Chart.js version, re-vendor it the same way (pull `dist/chart.umd.js` from the npm tarball and paste it in) rather than reverting to a CDN `<script src>`.
- `gsheet_backend_build_20260821-0000.py` / `_20260821-1400.py` / `_20260824-1100.py` / `_20260909-1300.py` — the Python/pandas scripts that aggregated the raw booking-level export(s) into the summary tables living in the Google Sheet. **The 20260909 one is current** — it rebuilds all 10 tabs from `data_manifest.json`'s file list in a single run, replacing the single-rolling-file assumption the three earlier scripts made. Write a new timestamped copy (don't edit an old one in place) whenever the raw data needs refreshing or a new pre-aggregated tab is needed — see `DASHBOARD_VISUALIZATION_SPEC.md` §A for the pattern.
- `build_manifest.py` — scans the repo root for `online_discount_summary__raw_*.xlsx` files and writes `data_manifest.json`. Re-run this and commit the updated manifest **every time a raw file is added or removed**, before running the main build script (which reads the manifest, not the filesystem directly).
- `data_manifest.json` — the file↔collection-month mapping. One entry per raw file: filename, row count, `collection_date`/`booking_date` min/max, which calendar month(s) it covers. This is what a build run consults to know which files to union for a given date range.
- `online_discount_summary__raw_<Month><Year>.xlsx` (repo root, currently `_July_2026.xlsx`, `_Aug2026.xlsx`, `_1-9Sep2026.xlsx`) — the raw booking-level exports, one per calendar month. See "Raw data source" below — this is not the same file-management model as before 2026-09-09, read it before adding a new one.

## Raw data source — one file per collection month, all kept permanently

**Each raw file is scoped by `collection_date` (the month payment settled), not `booking_date` (the appointment/test date).** Confirmed empirically 2026-09-09: `online_discount_summary__raw_July_2026.xlsx` is *every booking whose payment collected in July* — 100% bounded to `2026-07-01`..`2026-07-31` on `collection_date`, zero nulls. `booking_date` spills backward by weeks (a booking made in May can still collect payment in July) because payment settlement lags the actual service.

**Consequence: files are disjoint by construction — zero `booking_id` overlap between any two.** Confirmed across all three current files (219,560 rows unioned, 219,560 unique `booking_id`). **Never dedup when combining them, just union** — and if a future file ever *does* overlap another (an amendment/correction on the source side), that's a signal something changed upstream, not something to silently paper over; investigate before shipping.

**File management model, as of 2026-09-09**: one file per calendar month, kept in the repo **permanently** — do not delete a file just because a newer one exists (they cover different months, not the same one). This replaced the old "one rolling file, delete-and-replace on each refresh" model (used through `online_discount_summary__raw_1to23AugMTD.xlsx`, retired 2026-09-09 — confirmed a 75,195/75,199 `booking_id` subset of the new `_Aug2026.xlsx`, so nothing was lost). Only delete a file if it's a genuine mistake/duplicate of the *same* month, not a superseded partial pull of a *different* month — a `..._1-9Sep2026.xlsx` MTD file, for instance, stays even after a later `..._Sep2026.xlsx` full-month file arrives; both are legitimate, `data_manifest.json`'s `collection_months` field is what a build run uses to tell them apart.

**Refreshing/adding raw data**: 1) drop the new file into the repo root as `online_discount_summary__raw_<Month><Year>.xlsx` (or `_<start>-<end><Month><Year>.xlsx` for a month-to-date pull); 2) run `python3 build_manifest.py` and commit the updated `data_manifest.json`; 3) write a new timestamped `gsheet_backend_build_*.py` (or just re-run the current one if its logic doesn't need to change) to rebuild and push all 10 tabs; 4) if the new file fully supersedes an old MTD pull of the *same* month, `git rm` the old one in the same change — but never remove a file covering a *different* month.

**The `Booking_Summary` Sheet tab has been cleared** (data removed, tab structure kept) — raw data lives in the repo as files, never gets pasted into a Sheet tab, regardless of size.

### GM-computation-lag rows — drop them, everywhere, always

Beyond the booking→collection lag, there's a **second, shorter lag**: `collection_date` can be set (payment genuinely collected) while `Gross_Margin` is still null for a few more days — concentrated heavily in the first ~5 days after each collection month starts (e.g. 2,038 of the 8,318 total null-GM rows found 2026-09-09 sit on `collection_date = 2026-07-01` alone, decaying fast after). Revenue (`Collected Net Revenue`) is real for these rows; GM isn't yet. Left in, this silently unbalances every `gm_sum`/`revenue_sum` pair computed downstream (understates GM% right after any month boundary) — **drop rows with null `Gross_Margin` from the working dataframe immediately after loading, before any aggregation, in every build script.** This incidentally also removes the entire pre-July "data gap" fragment (no `June2026` collection-file exists, see below) without needing separate handling — those stragglers are disproportionately slow-settling and mostly fall into this same null-GM bucket.

### Known data gap: no pre-July-2026 collection-month file

There is no `June2026` (or earlier) collection-month export. Bookings serviced in May/June are only visible to us if their payment happened to collect in July+ (a small, slow-settling, non-representative fragment) — after the GM-null drop above, this fragment disappears from the data entirely, which is correct (it was never a real signal, just noise). **`clean_start` for aggregation is therefore the earliest month we have a genuine full single-collection-month file for** (currently July 2026) — derive this from the manifest (`len(collection_months) == 1`), don't hardcode a date. If you're given a June (or earlier) file, this whole section's date becomes stale — update it.

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
| `Package_Info` | top-80 packages by volume | `package_code`, `bookings_jul01_aug31` (column name encodes the clean window, changes every refresh), `note` — flags rows where `package_code` is actually a comma-separated multi-package combo (e.g. `BC023,BC033`), a real quirk in the source data, not a bug. **Fetched by the dashboard but not currently read by any chart** — PKG-01 ended up sourced from `Package_GM_Summary` instead, which carries `is_combo` directly. Harmless (small tab, fast fetch), but worth knowing if you're tracing why a column here doesn't show up anywhere in the JS. |
| `Booking_Weekly_Summary` | weekly × top-15 package × top-6 city, clean window (currently Jul 1–Aug 31) | `week_start`, `package_bucket`, `city_bucket`, `bookings`, `gm_sum`, `revenue_sum`, `gm_pct`. **This is what the dashboard actually reads** — the JS aliases it internally to `Booking_Summary`, see `TABS`/`ALIAS` at the top of the `<script>` block. |
| `Coupon_Summary` | weekly × top-30 coupon, same window | `week_start`, `coupon_bucket`, `bookings`, `gm_sum`, `revenue_sum`, `repeat_bookings`, `avg_discount_pct`, `gm_pct`, `repeat_share` |
| `Segment_Summary` | week × `customer_category` × `Booking_Flag` × city_bucket(top-6), same window | `week_start`, `customer_category`, `booking_flag`, `city_bucket`, `bookings`, `gm_sum`, `revenue_sum`, `gm_pct`, `asp`. Powers SEG-01 to SEG-04 (`DASHBOARD_VISUALIZATION_SPEC.md`). |
| `Channel_Summary` | week × `booked_by` × city_bucket(top-6), same window | `week_start`, `booked_by`, `city_bucket`, `bookings`, `gm_sum`, `revenue_sum`, `gm_pct`, `avg_discount_pct`. Powers CHAN-01 to CHAN-03. |
| `Discount_Stacking_Summary` | week × `n_disc_types` (0/1/2/3+, count of nonzero among special/vip/coupon/redcash/giftcard discounts), same window | `week_start`, `n_disc_types`, `bookings`, `gm_sum`, `revenue_sum`, `gm_pct`. Powers COUP-01. **Four separate weeks** now show negative GM% at 3+ stacked discounts (2026-09-09 refresh, full Jul–Aug window): Aug 10 (−3%), Aug 17 (−8%), Aug 24 (**−71%**, the worst by far), Aug 31 (−1%, but that week is only 1 day of data, treat as noise). This is no longer a "watch" — four weeks including one catastrophic one is a real, escalatable pattern, not sampling noise from a couple of tiny weeks. |
| `Geo_Summary` | week × city (top-20, wider than the top-6 used elsewhere) × Zone (top-30), same window | `week_start`, `city`, `zone`, `bookings`, `gm_sum`, `revenue_sum`, `gm_pct`, `asp`. Powers GEO-01/02. Zone bucketing (top-30 + OTHER) was our own call — the spec didn't pin a number, 211 raw zones was too many to leave unbucketed. |
| `DoD_Summary` | **daily** (not weekly) × package_bucket(top-15) × city_bucket(top-6), full range from `clean_start` through the latest collection data we have (no pre-July gap rows — see "Known data gap" above) | `booking_date`, `package_bucket`, `city_bucket`, `bookings`, `gm_sum`, `revenue_sum`, `gm_pct`, `is_partial` (true only for the current, still-accumulating collection month — every day present already has a settled GM, `is_partial` means "month isn't finished yet", not "untrustworthy"). Powers CADENCE-01 and the Overview "Monthly Insights" box (client-side rollup of this same tab to calendar-month grain, no separate tab). |
| `Financial_Waterfall_Summary` | week only, clean window, GM-computation-lag rows already dropped upstream (see "GM-computation-lag rows" above) | `week_start`, `offer_price_sum`, `special_discount_sum`, `vip_discount_sum`, `coupon_discount_sum`, `redcash_sum`, `giftcard_sum`, `collected_net_revenue_sum`, `cpt_sum`, `gm_sum`. Powers FIN-01. Reconciles exactly to `gm_sum = collected_net_revenue_sum − cpt_sum` — verified before push, re-verify after any refresh. |
| `Package_GM_Summary` | full package universe (≥10 bookings kept individually, else `OTHER`), clean window, no week/city split | `package_code`, `bookings`, `gm_sum`, `revenue_sum`, `gm_pct`, `asp`, `is_combo` (gviz reads this as the string `'True'`/`'False'`, not a native bool — compare accordingly). Powers PKG-01; not explicitly named in `DASHBOARD_VISUALIZATION_SPEC.md` §A but needed to make that P0 item buildable (full-universe ranking wider than `Booking_Weekly_Summary`'s top-15). |
| `Booking_Summary` | **empty — cleared 2026-08-24, stays empty** | No longer holds data, and never will again — raw data is a repo file, not a Sheet tab, regardless of file count/size. This tab was never wired into the client-side dashboard (gviz would hang/crash a browser tab on a 75k+-row response). Left in the Sheet as an empty placeholder rather than deleted outright. |

**Known scope limit, worth fixing if you're picking this up**: `Booking_Weekly_Summary` is still top-15 packages × top-6 cities only. The customer_category/Fresh-Repeat split this note used to flag as missing now exists separately in `Segment_Summary` — if you need package/city breadth *and* segment splits together in one tab, that's still a gap; build it the same way (server-side pandas against the raw files, push a new tab), not a client-side rewrite to read a raw file directly.

## Frontend gotchas already hit once — don't reintroduce these

- **A chart's canvas gets constructed at 0×0 if its panel is `display:none`** (every non-Overview tab, on first load) — Chart.js doesn't reliably pick up a `ResizeObserver` firing on the `display:none → block` transition, so a chart built while hidden can render blank forever. Fixed with an explicit `chart.resize()` call on tab switch — but **scope it to the panel becoming visible, not every chart globally** (`panel.querySelectorAll('canvas')`, see the tab-click handler at the bottom of `index.html`'s `<script>`). Resizing a chart on the panel simultaneously going *hidden* corrupts its layout (resizes it to 0×0, and Chart.js doesn't reliably recover on a later resize back) — this silently broke GEO-01's bar chart after cycling through a few tabs even though its data and config were always correct. Caught by testing that clicks through every tab multiple times, not just once each — a single-visit test wouldn't have caught it.
- **"Latest `week_start`" is not the same as "latest complete week."** The clean window's edges (both ends — the earliest reliable month and the current still-accumulating one) produce 1–6 day boundary weeks in every weekly tab. Blindly picking `weeks[weeks.length-1]` for a KPI/trend/latest-week chart shows a nonsensical swing (a real example: a 1-day boundary week read as "▼95.4% vs prior week"). Every "latest week" or "trend across weeks" chart must filter through `isWeekComplete(weekStart, cleanEnd, cleanStart)` (defined once, reused everywhere — grep for it before adding a new one) rather than trusting sort order. This bit the Overview KPI cards, the coupon-concentration donut, SEG-01/02/03, and CHAN-01 in the same session before all being fixed the same way.

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
- **Date reliability**: there are two separate lags, not one. (1) Booking→collection lag: a booking's payment can settle weeks after the service date (`booking_date` vs `collection_date`), which is *why* raw files are scoped by `collection_date` in the first place (see "Raw data source" above). (2) GM-computation lag, shorter: `collection_date` can be set while `Gross_Margin` is still null for a few more days, concentrated right after each collection month starts — drop these rows everywhere, see "GM-computation-lag rows" above. Always sanity-check daily row counts (and null-GM counts) near the edges of a new pull before trusting them.
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
