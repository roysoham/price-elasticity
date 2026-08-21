# V5 — GM Improvement Model: Methodology & Data Reference

**Purpose of this document.** Single reference for how `GM_V5_Model_Aug2026.xlsx` was built: what every number means, where it came from, what changed from V4 and why, what's still missing, and how to extend it. Written so a future chat — with no memory of the sessions that built this — can pick it up cold. If you're an AI assistant reading this: read this whole document before touching the model or answering questions about it. **V4_Methodology.md is superseded by this document** — keep it for historical record only, don't treat its numbers as current.

Last updated: 2026-08-18. Model version: V5.

---

## 1. What changed from V4, and why this is a rebuild, not an add-on

Two new inputs changed what's measurable:

1. **The raw booking export now carries `coupon_code` directly on every row.** V4 had to name-match a separate 13-day coupon file against booking data with no shared key — a real limitation, documented as such. That workaround is now retired. Every booking's exact coupon is known, joined directly to its real `cpt`, `Gross_Margin`, `package_code`, `customer_category`, `Booking_Flag`, `booked_by` — no proxy needed anywhere in the coupon analysis.
2. **You supplied the real coupon CRM settings** (`Coupon code crm settings .xlsx`: MOV, discount%, upper-limit%, type) **and the ADDFAMILY family-add-on logic** (not in the CRM export — a separate, auto-generated coupon family you defined manually). MOV moves from "qualitative hypothesis" (V4's stated gap) to a real, checkable number.

Base dataset also changed: `online_discount_summary__raw_Aug17MTD.xlsx`, unfiltered, booking_date range Jun 2 – Aug 17 2026. **Clean/reliable window used throughout this doc: Aug 1–16 (51,701 bookings)** — see §7 for why the edges of the window are excluded.

### The correction you need to know before trusting any V4 number

V4's coupon depth-vs-margin curve (built on a smaller, 8-day window, coupon identity inferred by name-matching rather than joined) found real GM% collapsing to **~1% at 30%+ discount depth**, and called FREEDOM50 (42% depth) a near-giveaway needing an urgent kill. **On this larger, directly-linked dataset, that finding does not hold.** FREEDOM50's real GM%, measured directly via `coupon_code`, is **47.9%** — the lowest among major campaigns, worth optimizing, but nowhere near a giveaway. The corrected depth-vs-margin curve (§4.2) shows a real but gradual decline, not a cliff: 82% (no discount) → 77% → 71% → 61% → ~61% (30-40%) → 43% (40%+). The V4 number was a small-sample artifact of the workaround method combined with an unusually low-margin 8-day window, not a real structural collapse. **Own this plainly if asked: the earlier "kill FREEDOM50 urgently" call was wrong.** This is exactly why the coupon_code linkage matters — it's not a nice-to-have, it changed a real conclusion.

Similarly, V4's Segment Diagnostic (also built on the smaller window) showed Repeat VIP-Gold GM% at 59.8%; on this larger sample it's **69.0%**. The smaller window was a lower-margin period generally, not representative. Directional findings from V4 (VIP Gold gets shallower coupons than Regular, Phlebo has an ancillary-attach gap, certain packages carry price×coupon stacking risk) still hold — only the specific GM% figures were off, and they're now corrected everywhere in V5.

### Structural simplification

V4 had 13 tabs; V5 has 9. Coupon-related tabs collapsed from 4 (`Coupon - Action List`, `Depth vs Margin`, `Channel Diagnostic`, `WoW Scorecard`) into 2 (`Customer & Coupon Analysis`, `Coupon Rules & Definitions`) — this was the user's explicit ask: simplify, and if something doesn't connect to the core price → segment → coupon-rules flow, remove it rather than let it accumulate.

## 2. Standing conventions (unchanged from V4 — still apply)

- **Margin metric: `GM = Collected Net Revenue − cpt`.** Still the standard; `cpt` is the only real cost field. `diagnostic_cost`, `express_slot`, `vip_paid_amount`, `report_hardcopy_cost` remain customer-paid fees, not costs.
- Discount types: `special_discount`, `vip_discount`, `coupon_discount`, `redcash`, `giftcard` — a booking can carry several at once (`n_disc_types`). Always check this before reading `coupon_discount = 0` as "no discount."
- Channels: Self / Sales / Phlebo. Categories: `regular` / `vip` / `vip gold`. `Booking_Flag`: Fresh / Repeat.

## 3. Data sources

| File | Window used | What it provides | Status |
|---|---|---|---|
| `online_discount_summary__raw_Aug17MTD.xlsx` | Booking-level, clean window Aug 1–16 (51,701 rows) | THE base file for V5. Real `cpt`/`Gross_Margin`/`GM%`, all discount flags, segment fields, `package_code`, and now **`coupon_code`** directly on every row. | **Primary, replaces the Jul26-Aug2 file** |
| `Coupon code crm settings .xlsx` | Point-in-time (as of pull date) | Master coupon rules: MOV, discount%, type (percentage/amount), upper-limit%, valid-once-per-user, is-redcash flag, created-by, create-date. 41 coupons. | **New — resolves the "MOV is qualitative" gap from V4** |
| ADDFAMILY family-add-on logic | User-supplied, not in any export | 4 coupon codes (`ADDFAMILY2/3/4/5NYNNN`) with member-count-based discount tiers, manually documented since they don't appear in the CRM settings export (see §5). | **New, user-supplied, verified against data** |
| `coupon_usage_online_*.xlsx` (both the Aug 1-13 and Aug 16 MTD versions) | — | **Deprecated as of V5.** The raw discount summary file's new `coupon_code` column does everything this file did, with a real package/cost/segment join the standalone file never had. Do not use for new analysis; superseded. |
| Everything else from V4 §3 (price MoM file, Android funnel, May Coupon Modeller, competitor pricing file) | Unchanged | Still valid, still referenced where relevant (§6). No new pulls this round. | Unchanged |

## 4. The model, five stages (simplified flow, per the redesign agreed last round)

**Price data → changes → learnings from bookings data → segmented action plan (price × category × VIP tier) → coupon rules.** Each stage exists only because it feeds the next one.

### 4.1 Price data & changes

Unchanged from V4 §4.1 — no new price/MoM pull this round, so the 39-package action list, GM-breakeven recommendation logic, and confidence tiers all carry forward as-is (`Price - Action List` tab). **Still-open gap, unresolved this round**: elasticity events are not yet tagged for whether coupon depth moved concurrently with the price change (the "does elasticity include coupon/VIP stacking" question from last round). This needs the price MoM file re-pulled with `coupon_code` history to fix properly — flagged for next round, not solved here (see §7).

### 4.2 Learnings from bookings data — corrected numbers

**Discount stacking** (Aug 1–16, n=51,701): 0 discount types → 81.7% GM. 1 type → 69.5%. 2 types → 66.3%. 3 types → 67.3%. Flatter than V4's finding (which showed steeper decay) — more data, less noise. Still confirms: any discount at all drops you ~12-15pp from baseline, but stacking beyond one type doesn't compound as sharply as the smaller sample suggested.

**Depth-vs-margin curve** (isolated coupon-only bookings — coupon is the *only* discount on the booking): 0% → 81.7%, 1-10% → 76.8%, 10-20% → 71.0%, 20-30% → 61.2%, 30-40% → 60.6%, 40%+ → 43.2%. This is the corrected curve — see §1 for why it supersedes V4's version. Practical read: margin holds up fine to ~20%, degrades steadily but not catastrophically beyond that, and only the deepest tier (40%+, which is mostly FREEDOM50) shows a real hit.

**Segment diagnostic** (Fresh/Repeat × Category, Aug 1–16):

| Segment | Revenue share | GM% | Coupon penetration | Avg members/booking |
|---|---|---|---|---|
| Repeat, VIP-Gold | 35.7% (largest) | 69.0% | 49.4% | 1.21 |
| Fresh, Regular | 27.4% | 67.8% | 71.5% | 1.19 |
| Repeat, VIP | 17.2% | 69.5% | 64.1% | 1.17 |
| Repeat, Regular | 9.9% | 68.9% | 67.8% | 1.16 |
| Fresh, VIP | 9.1% | 68.2% | 63.0% | 1.16 |
| Fresh, VIP-Gold | 0.8% (smallest) | 67.0% | 76.0% | 1.44 |

All segments now sit in a tighter 67-70% GM% band (vs. the 57.7-66.6% spread V4 reported) — the earlier spread was noise from the smaller window, not a real structural difference between segments. The *directional* finding stands: Regular still gets deeper discounts than VIP/VIP-Gold, Fresh-Regular is still the largest acquisition-heavy cohort.

### 4.3 Segmented action plan (price × category × VIP)

Not yet built as a fully segmented per-package recommendation engine — that requires enough booking volume per package × segment cell, which most of the 39 price-action packages don't clear individually. What V5 *does* provide: the `Price-Coupon Stacking Risk` tab now names the actual top coupon driving each flagged package's discount exposure (via the real `coupon_code` join), which is a big step toward segment-aware pricing even without a full segment-level elasticity model. **4 packages remain HIGH risk** (down from 6 in V4, on more reliable data): PL124I (top coupon: SAVEBIGGER20), PL334 (SAVEBIGGER20), PL203 (SAVEBIGGER20), PL91 (SAVEBIGGER20). Notably, all four HIGH-risk packages share the same top coupon — SAVEBIGGER20 is doing most of the stacking damage on this specific set, which makes it a more targeted, cheaper fix than reviewing coupon policy broadly.

### 4.4 Coupon rules

This is the new, real part of the model, replacing V4's observational-only coupon section.

**Master coupon table** (`Coupon Rules & Definitions` tab): 41 CRM-defined coupons (MOV, discount%, upper-limit%) + 4 ADDFAMILY definitions documented manually. 22 of the ~30 coupon codes with meaningful volume in Aug 1–16 are matched to a known rule; the rest (SAVEBIGGER20/22/25 notably — your highest-volume campaigns — plus GAMBHIR20X, FITINDIA-family) are **not in the CRM export at all**, meaning either the export only captures a subset of "official" active coupons, or these were created/managed outside that system. Worth reconciling with whoever owns coupon configuration — the biggest campaigns by volume shouldn't be invisible to the settings-of-record file.

**ADDFAMILY logic, verified against real data** (per your definition):
- `ADDFAMILY2NYNNN`: adds 1 member to an existing booking of 1 (→2 total), 20% max combined discount (coupon+VIP capped together, not additive). Verified: avg Total_Discount% = 20.2%, avg members/booking = 1.99, 72.7% also VIP-stacked, 87.2% Self-channel.
- `ADDFAMILY3NYNNN`: →3 total members, 25% max combined. Verified: 25.1% avg discount, 2.99 avg members, 63.9% VIP-stacked, 53.7% Self.
- `ADDFAMILY4NYNNN`/`5NYNNN`+: →4+ members, 30% max combined. Verified: 30.1% avg discount, 4.13 avg members, 58.1% VIP-stacked, 42.4% Self.

All three match your stated design almost exactly — the cap is real and enforced, not just a nominal max. **Interpretation, per your point**: this is a fresh/repeat growth driver via basket expansion, not leakage. The discount is proportionate to incremental members added, and it visibly works — average member count scales cleanly with the tier (2, 3, 4+). The channel-mix shift (87% Self at the 2-member tier down to 42% Self at 4-member) suggests larger family additions increasingly need assisted checkout — worth a UX look at whether the Self/app flow breaks down for 3+ member bookings, since that's a friction point, not a discount problem.

**MOV compliance check**: for coupons with a stated MOV, what share of bookings are priced below it? SAVEBIG20 (MOV ₹1,499): 20.1% of its bookings are below. SAVEBIG15 (MOV ₹799): 15.0% below. SAVEBIGGER25 (MOV ₹4,299): 8.5% below. **Caveat**: `offer_price` here is the per-booking package price, not necessarily full cart value, so this isn't a confirmed MOV breach — a booking could clear MOV on a multi-item cart while looking "below MOV" on a single package's own price. Flagged as an investigation item for whoever owns cart-level logic, not a confirmed leak.

**Upper-limit compliance**: checked whether actual coupon discount% ever exceeds the coupon's own stated upper-limit%. **No breaches found** — discount caps are being enforced correctly at the system level across all checked coupons.

### 4.5 VIP Gold ASP Strategy

Carried forward from V4 with a refresh note added at the top of the tab (see §1's correction — the segment GM% figures cited there are from the smaller window and now read low versus the Aug 1-16 numbers in §4.2). Directional actions (ancillary attach push, family add-on forcing, hold on VIP-Gold-heavy price cuts) are unaffected by the correction and still stand.

## 5. Cross-lever finding, refreshed

Discount stacking (§4.2) and the price × coupon conflict check (§4.3) both still hold on the larger dataset — confirms these aren't artifacts of the smaller V4 sample, unlike the depth-curve and segment-GM% numbers that were.

## 6. Competitor pricing cross-check (carried from last round, unchanged this round)

`Redcliffe labs Pricing top tests - Top Competition - August 2026.xlsx`, `Comparison Sheet` tab: 33 team-recommended price increases (range +3.9% to +50%), all anchored to staying below Tata/Dr Lal. Cross-checked against the price elasticity model: **HBA1C and Thyroid Profile Total — both methods independently agree: raise.** LFT and KFT showed *positive* (untrustworthy) elasticity in the internal model but a clean competitor-headroom case to raise — use the competitor file as the tiebreaker there. **Gap in the team's own file**: several of the 33 recommendations (Ferritin, Magnesium, Homocysteine, Amylase) raise price while Healthians is already pricing meaingfully below Redcliffe on that specific test — the file benchmarks against Tata/Dr Lal without weighting Healthians specifically undercutting on those SKUs. Flag back to the team before executing those specific rows.

## 7. Known gaps — read before trusting a number blindly

1. **Price elasticity still isn't stacking-aware.** Confirmed real problem last round, not fixed this round (needed a fresh price MoM pull with coupon history, which wasn't part of this round's inputs). Next-round priority.
2. **Booking-date edges of the raw export are unreliable.** `Gross_Margin` is sparse/artifactual before ~Jul 26 in this pull (collection-date lag — a booking's margin populates only once it's actually collected, and the earliest booking_dates in any pull haven't all collected yet) and Aug 17 is a partial day (898 bookings vs. ~3,000-3,900 on full days). **V5 uses Aug 1–16 only** for this reason — always check the daily bookings count for a new pull before trusting its edges.
3. **CRM coupon settings export doesn't cover your highest-volume campaigns.** SAVEBIGGER20/22/25 (your 3 biggest coupons by volume) aren't in the 41-row settings file. Worth asking whoever owns that file why — either it's an incomplete export or those are managed through a different system.
4. **MOV compliance check is a proxy, not a confirmed breach**, per §4.4's caveat — needs cart-level (not package-level) price data to be definitive.
5. **Segment-level price elasticity (stage 4.3) is not a real per-cell model** — volume doesn't support it for most packages. What exists is a coupon-identity-aware risk flag, not a true segmented price recommendation. If this is the next priority, it needs either much bigger volume per package or a pooling strategy across similar packages.
6. **MOV, discount rules for the ~3,900+ long-tail/personal/adhoc coupon codes remain undocumented** — only the 41 CRM-listed + 4 ADDFAMILY codes have known rules. These are low-volume individually but numerous; worth a policy decision (e.g., cap all unlisted codes at a default ceiling) rather than leaving them fully unmanaged.
7. Everything in V4 §7 not superseded above still applies (observational not causal throughout, coupon targeting isn't random, etc.).

## 8. How to refresh this model

Same weekly/monthly cadence as V4 §8, with one addition: **whenever a new raw export lands, check for `coupon_code` presence and the clean-window edges (per §7.2) before running anything** — the methodology now depends on both being right.

## 9. File map (V5 additions in bold)

```
GM Improvement/
├── GM_V5_Model_Aug2026.xlsx           <- THE working file (this doc describes it)
├── V5_Methodology.md                   <- this document
├── GM_V4_Model_Aug2026.xlsx            <- superseded, kept for history
├── V4_Methodology.md                   <- superseded, kept for history
├── **online_discount_summary__raw_Aug17MTD.xlsx**  <- NEW base data source, has coupon_code
├── **Coupon code crm settings .xlsx**  <- NEW, master coupon rules (MOV, discount%, upper-limit%)
├── scripts/                            <- every script, timestamped, incl. v5_* builds
├── (all V4-listed files remain, unchanged)
```
