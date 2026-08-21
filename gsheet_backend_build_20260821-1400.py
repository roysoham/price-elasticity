"""
Backend build for DASHBOARD_VISUALIZATION_SPEC.md §A — new pre-aggregated tabs,
P0-priority slice only (Segment_Summary, Channel_Summary, Discount_Stacking_Summary,
Geo_Summary, DoD_Summary, Financial_Waterfall_Summary, Package_GM_Summary).

Source: a local export of the Booking_Summary raw tab (64,904 rows, Jun2-Aug21 2026),
same schema as documented in CLAUDE.md. Not re-fetched from the Sheet here — this repo's
CLAUDE.md flags the raw tab as too large (~52MB+) for a gviz round-trip; pull a fresh
export the same way if re-running this later.

Clean window: 2026-08-01 to 2026-08-19 (per the Settings tab's newer clean_window entry,
which supersedes the original 2026-08-01/08-16 window used by Booking_Weekly_Summary/
Coupon_Summary — those two tabs are NOT touched by this script). Aug 20 (873 bookings)
and Aug 21 (1 booking) are confirmed partial days, excluded from every weekly/day-bucketed
tab except DoD_Summary, which needs the full range to let CADENCE-01 draw partial days as
visually distinct rather than silently equal-confidence.

NOTE — Settings tab currently has two conflicting `clean_window` rows (08-19 and 08-16
end dates, duplicate key). Used the newer/08-19 one here; flagged back to the project
owner rather than silently resolved — worth cleaning up the Settings tab itself.
"""
import pandas as pd
import numpy as np
import os

SRC = "/root/.claude/uploads/aabc5007-5332-538d-9613-577e4a814ad1/e37ccc11-Booking_Summary.xlsx"
OUT_DIR = "/tmp/claude-0/-home-user-price-elasticity/aabc5007-5332-538d-9613-577e4a814ad1/scratchpad/gsheet_build"
os.makedirs(OUT_DIR, exist_ok=True)

CLEAN_START = "2026-08-01"
CLEAN_END = "2026-08-19"

df = pd.read_excel(SRC)

# cpt has 2 stray '#############' Excel-overflow strings out of 64,904 rows (real data
# quirk, not a bug). Coerce to NaN, then reconstruct from GM = Collected Net Revenue - cpt
# (both of those 2 rows have a valid Gross_Margin) so Financial_Waterfall_Summary still
# reconciles exactly instead of silently undercounting cpt_sum for them.
df["cpt"] = pd.to_numeric(df["cpt"], errors="coerce")
cpt_missing = df["cpt"].isna() & df["Gross_Margin"].notna()
df.loc[cpt_missing, "cpt"] = df.loc[cpt_missing, "Collected Net Revenue"] - df.loc[cpt_missing, "Gross_Margin"]

df["week_start"] = (df["booking_date"] - pd.to_timedelta(df["booking_date"].dt.weekday, unit="D")).dt.strftime("%Y-%m-%d")

clean = df[(df["booking_date"] >= CLEAN_START) & (df["booking_date"] <= CLEAN_END)].copy()
print(f"clean window rows: {len(clean)} of {len(df)} total")

TOP_CITY6 = clean["city"].value_counts().head(6).index.tolist()
clean["city_bucket6"] = np.where(clean["city"].isin(TOP_CITY6), clean["city"], "OTHER")

# ---------- Segment_Summary: week x customer_category x Booking_Flag x city_bucket(top-6) ----------
seg = clean.groupby(["week_start", "customer_category", "Booking_Flag", "city_bucket6"], dropna=False).agg(
    bookings=("booking_id", "count"),
    gm_sum=("Gross_Margin", "sum"),
    revenue_sum=("Collected Net Revenue", "sum"),
    offer_price_sum=("offer_price", "sum"),
).reset_index().rename(columns={"Booking_Flag": "booking_flag", "city_bucket6": "city_bucket"})
seg["gm_pct"] = (seg["gm_sum"] / seg["revenue_sum"].replace(0, np.nan) * 100).round(1)
seg["asp"] = (seg["offer_price_sum"] / seg["bookings"]).round(0)
seg = seg.drop(columns=["offer_price_sum"]).round({"gm_sum": 0, "revenue_sum": 0})
seg.to_csv(f"{OUT_DIR}/Segment_Summary.csv", index=False)
print("Segment_Summary rows:", len(seg))

# ---------- Channel_Summary: week x booked_by x city_bucket(top-6) ----------
chan = clean.groupby(["week_start", "booked_by", "city_bucket6"], dropna=False).agg(
    bookings=("booking_id", "count"),
    gm_sum=("Gross_Margin", "sum"),
    revenue_sum=("Collected Net Revenue", "sum"),
    avg_discount_pct=("Total_Discount %", "mean"),
).reset_index().rename(columns={"city_bucket6": "city_bucket"})
chan["gm_pct"] = (chan["gm_sum"] / chan["revenue_sum"].replace(0, np.nan) * 100).round(1)
chan = chan.round({"gm_sum": 0, "revenue_sum": 0, "avg_discount_pct": 1})
chan.to_csv(f"{OUT_DIR}/Channel_Summary.csv", index=False)
print("Channel_Summary rows:", len(chan))

# ---------- Discount_Stacking_Summary: week x n_disc_types ----------
disc_cols = ["special_discount", "vip_discount", "coupon_discount", "redcash", "giftcard"]
clean["n_disc_types"] = (clean[disc_cols].fillna(0) != 0).sum(axis=1)
clean["n_disc_types_bucket"] = np.where(clean["n_disc_types"] >= 3, "3+", clean["n_disc_types"].astype(str))
stack = clean.groupby(["week_start", "n_disc_types_bucket"], dropna=False).agg(
    bookings=("booking_id", "count"),
    gm_sum=("Gross_Margin", "sum"),
    revenue_sum=("Collected Net Revenue", "sum"),
).reset_index().rename(columns={"n_disc_types_bucket": "n_disc_types"})
stack["gm_pct"] = (stack["gm_sum"] / stack["revenue_sum"].replace(0, np.nan) * 100).round(1)
stack = stack.round({"gm_sum": 0, "revenue_sum": 0})
stack.to_csv(f"{OUT_DIR}/Discount_Stacking_Summary.csv", index=False)
print("Discount_Stacking_Summary rows:", len(stack))
print("  redcash note: 0 nonzero rows in this pull -- n_disc_types logic still counts it, ready if that changes")

# ---------- Geo_Summary: week x city(top-20) x zone(top-30, OTHER bucket -- 211 raw zones, spec silent on zone bucketing) ----------
TOP_CITY20 = clean["city"].value_counts().head(20).index.tolist()
TOP_ZONE30 = clean["Zone"].value_counts().head(30).index.tolist()
clean["city_bucket20"] = np.where(clean["city"].isin(TOP_CITY20), clean["city"], "OTHER")
clean["zone_bucket30"] = np.where(clean["Zone"].isin(TOP_ZONE30), clean["Zone"], "OTHER")
geo = clean.groupby(["week_start", "city_bucket20", "zone_bucket30"], dropna=False).agg(
    bookings=("booking_id", "count"),
    gm_sum=("Gross_Margin", "sum"),
    revenue_sum=("Collected Net Revenue", "sum"),
    offer_price_sum=("offer_price", "sum"),
).reset_index().rename(columns={"city_bucket20": "city", "zone_bucket30": "zone"})
geo["gm_pct"] = (geo["gm_sum"] / geo["revenue_sum"].replace(0, np.nan) * 100).round(1)
geo["asp"] = (geo["offer_price_sum"] / geo["bookings"]).round(0)
geo = geo.drop(columns=["offer_price_sum"]).round({"gm_sum": 0, "revenue_sum": 0})
geo.to_csv(f"{OUT_DIR}/Geo_Summary.csv", index=False)
print("Geo_Summary rows:", len(geo))

# ---------- DoD_Summary: DAILY x package_bucket(top-15) x city_bucket(top-6) ----------
# Full date range (not clean-window-restricted) so CADENCE-01 can flag partial/sparse days
# instead of silently dropping them. is_partial = outside the Settings clean_window.
dod_src = df.copy()
TOP_PKG15 = dod_src[(dod_src["booking_date"] >= CLEAN_START) & (dod_src["booking_date"] <= CLEAN_END)]["package_code"].value_counts().head(15).index.tolist()
dod_src["package_bucket"] = np.where(dod_src["package_code"].isin(TOP_PKG15), dod_src["package_code"], "OTHER")
dod_src["city_bucket"] = np.where(dod_src["city"].isin(TOP_CITY6), dod_src["city"], "OTHER")
dod_src["booking_date_str"] = dod_src["booking_date"].dt.strftime("%Y-%m-%d")
dod = dod_src.groupby(["booking_date_str", "package_bucket", "city_bucket"], dropna=False).agg(
    bookings=("booking_id", "count"),
    gm_sum=("Gross_Margin", "sum"),
    revenue_sum=("Collected Net Revenue", "sum"),
).reset_index().rename(columns={"booking_date_str": "booking_date"})
dod["gm_pct"] = (dod["gm_sum"] / dod["revenue_sum"].replace(0, np.nan) * 100).round(1)
dod["is_partial"] = ~((dod["booking_date"] >= CLEAN_START) & (dod["booking_date"] <= CLEAN_END))
dod = dod.round({"gm_sum": 0, "revenue_sum": 0})
dod.to_csv(f"{OUT_DIR}/DoD_Summary.csv", index=False)
print("DoD_Summary rows:", len(dod))

# ---------- Financial_Waterfall_Summary: week only ----------
# Restrict to rows with a computed Gross_Margin. 2,601 clean-window rows have revenue
# collected but Gross_Margin/cpt still null (collection-date lag, CLAUDE.md caveat) --
# summing revenue over those while gm_sum/cpt_sum silently skip the NaNs broke the
# waterfall identity (revenue - cpt != gm_sum) by ~4.6L in one week. Every column in
# this tab must come from the same row subset for FIN-01's reconciliation check to hold.
fin_src = clean.dropna(subset=["Gross_Margin"])
fin = fin_src.groupby("week_start").agg(
    offer_price_sum=("offer_price", "sum"),
    special_discount_sum=("special_discount", "sum"),
    vip_discount_sum=("vip_discount", "sum"),
    coupon_discount_sum=("coupon_discount", "sum"),
    redcash_sum=("redcash", "sum"),
    giftcard_sum=("giftcard", "sum"),
    collected_net_revenue_sum=("Collected Net Revenue", "sum"),
    cpt_sum=("cpt", "sum"),
    gm_sum=("Gross_Margin", "sum"),
).reset_index()
fin = fin.round(0)
fin.to_csv(f"{OUT_DIR}/Financial_Waterfall_Summary.csv", index=False)
print("Financial_Waterfall_Summary rows:", len(fin))

# Reconciliation check per spec's FIN-01 caveat: ending value must match gm_sum from other tabs.
recon = (fin["collected_net_revenue_sum"] - fin["cpt_sum"] - fin["gm_sum"]).abs()
print("FIN-01 reconciliation (collected_net_revenue - cpt - gm_sum, should be ~0):")
print(recon.describe())
assert (recon < 1.0).all(), "FIN-01 waterfall does not reconcile to GM = Collected Net Revenue - cpt"

# ---------- Package_GM_Summary (not in spec §A table explicitly, but PKG-01/P0 needs a full- ----------
# universe package ranking wider than Booking_Weekly_Summary's top-15; adding this rather than
# silently leaving PKG-01 unbuildable. All packages with >=10 bookings in the clean window kept
# individually (not bucketed to OTHER) so the ranking table stays genuinely full-universe; below
# that floor folded into OTHER to avoid single-booking noise, consistent with this repo's existing
# "min-booking floor" convention (CHAN-04/Phlebo dashboard).
pkg_counts = clean["package_code"].value_counts()
KEEP_PKG = pkg_counts[pkg_counts >= 10].index.tolist()
clean["package_bucket_full"] = np.where(clean["package_code"].isin(KEEP_PKG), clean["package_code"], "OTHER")
pkgsum = clean.groupby("package_bucket_full", dropna=False).agg(
    bookings=("booking_id", "count"),
    gm_sum=("Gross_Margin", "sum"),
    revenue_sum=("Collected Net Revenue", "sum"),
    offer_price_sum=("offer_price", "sum"),
).reset_index().rename(columns={"package_bucket_full": "package_code"})
pkgsum["gm_pct"] = (pkgsum["gm_sum"] / pkgsum["revenue_sum"].replace(0, np.nan) * 100).round(1)
pkgsum["asp"] = (pkgsum["offer_price_sum"] / pkgsum["bookings"]).round(0)
pkgsum["is_combo"] = pkgsum["package_code"].str.contains(",", na=False)
pkgsum = pkgsum.drop(columns=["offer_price_sum"]).round({"gm_sum": 0, "revenue_sum": 0})
pkgsum.to_csv(f"{OUT_DIR}/Package_GM_Summary.csv", index=False)
print("Package_GM_Summary rows:", len(pkgsum), "| combo rows:", pkgsum["is_combo"].sum())

print("\nAll P0 tabs built OK ->", OUT_DIR)
