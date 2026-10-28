"""
Full refresh of all 9 backend tabs against the fresher raw export
(online_discount_summary__raw_1to23AugMTD.xlsx, 75,199 rows, Jun 2-Aug 23 2026).

Rebuilds BOTH the original two tabs (Booking_Weekly_Summary, Coupon_Summary,
Package_Info) AND the 7 P0 tabs added for DASHBOARD_VISUALIZATION_SPEC.md --
same schemas as before in every case, just fresher numbers, so no dashboard
JS changes are required by this refresh alone.

Clean window widened from 2026-08-01/08-19 to 2026-08-01/08-22: the extra
pull shows Aug 20-22 are now fully collection-complete (zero null
Gross_Margin rows), only Aug 23 remains a partial tail day (1,103 rows vs
~3,100/day normal -- pull taken mid-day). This is the collection-date-lag
pattern CLAUDE.md already documents: a day just needs a few days to "settle"
before its Gross_Margin/cpt values are reliably populated.
"""
import pandas as pd
import numpy as np
import os

SRC = "/home/user/price-elasticity/online_discount_summary__raw_1to23AugMTD.xlsx"
OUT_DIR = "/tmp/claude-0/-home-user-price-elasticity/aabc5007-5332-538d-9613-577e4a814ad1/scratchpad/gsheet_build_20260824"
os.makedirs(OUT_DIR, exist_ok=True)

CLEAN_START = "2026-08-01"
CLEAN_END = "2026-08-22"
WINDOW_TAG = "aug1_22"  # for Package_Info's bookings_<window> column name

df = pd.read_excel(SRC)

# cpt: reconstruct any Excel-overflow-corrupted values from the GM identity (see prior refresh's note)
df["cpt"] = pd.to_numeric(df["cpt"], errors="coerce")
cpt_missing = df["cpt"].isna() & df["Gross_Margin"].notna()
df.loc[cpt_missing, "cpt"] = df.loc[cpt_missing, "Collected Net Revenue"] - df.loc[cpt_missing, "Gross_Margin"]
print(f"cpt reconstructed from GM identity for {cpt_missing.sum()} rows")

df["week_start"] = (df["booking_date"] - pd.to_timedelta(df["booking_date"].dt.weekday, unit="D")).dt.strftime("%Y-%m-%d")

clean = df[(df["booking_date"] >= CLEAN_START) & (df["booking_date"] <= CLEAN_END)].copy()
print(f"clean window rows: {len(clean)} of {len(df)} total")
assert clean["Gross_Margin"].isna().sum() == 0, "clean window still has null-GM rows -- window too wide, back off CLEAN_END"

TOP_PKG15 = clean["package_code"].value_counts().head(15).index.tolist()
TOP_CITY6 = clean["city"].value_counts().head(6).index.tolist()
TOP_COUPON30 = clean["coupon_code"].value_counts().head(30).index.tolist()
TOP_CITY20 = clean["city"].value_counts().head(20).index.tolist()
TOP_ZONE30 = clean["Zone"].value_counts().head(30).index.tolist()
TOP_PKG80 = clean["package_code"].value_counts().head(80)

clean["package_bucket15"] = np.where(clean["package_code"].isin(TOP_PKG15), clean["package_code"], "OTHER")
clean["city_bucket6"] = np.where(clean["city"].isin(TOP_CITY6), clean["city"], "OTHER")
clean["coupon_bucket30"] = clean["coupon_code"].where(clean["coupon_code"].isin(TOP_COUPON30), "OTHER")
clean["coupon_bucket30"] = clean["coupon_bucket30"].fillna("NONE")

# ============ 1. Booking_Weekly_Summary: week x package(top15) x city(top6) ============
bs = clean.groupby(["week_start", "package_bucket15", "city_bucket6"], dropna=False).agg(
    bookings=("booking_id", "count"), gm_sum=("Gross_Margin", "sum"), revenue_sum=("Collected Net Revenue", "sum"),
).reset_index().rename(columns={"package_bucket15": "package_bucket", "city_bucket6": "city_bucket"})
bs["gm_pct"] = (bs["gm_sum"] / bs["revenue_sum"].replace(0, np.nan) * 100).round(1)
bs = bs.round({"gm_sum": 0, "revenue_sum": 0})
bs.to_csv(f"{OUT_DIR}/Booking_Weekly_Summary.csv", index=False)
print("Booking_Weekly_Summary rows:", len(bs))

# ============ 2. Coupon_Summary: week x coupon(top30) ============
cs = clean.groupby(["week_start", "coupon_bucket30"], dropna=False).agg(
    bookings=("booking_id", "count"), gm_sum=("Gross_Margin", "sum"), revenue_sum=("Collected Net Revenue", "sum"),
    repeat_bookings=("Booking_Flag", lambda s: (s == "Repeat").sum()),
    avg_discount_pct=("coupon_discount %", "mean"),
).reset_index().rename(columns={"coupon_bucket30": "coupon_bucket"})
cs["gm_pct"] = (cs["gm_sum"] / cs["revenue_sum"].replace(0, np.nan) * 100).round(1)
cs["repeat_share"] = (cs["repeat_bookings"] / cs["bookings"] * 100).round(1)
cs = cs.round({"gm_sum": 0, "revenue_sum": 0, "avg_discount_pct": 1})
cs.to_csv(f"{OUT_DIR}/Coupon_Summary.csv", index=False)
print("Coupon_Summary rows:", len(cs))

# ============ 3. Package_Info: top-80 packages by volume, combo flag via note ============
pkg_info = TOP_PKG80.reset_index()
pkg_info.columns = ["package_code", f"bookings_{WINDOW_TAG}"]
pkg_info["note"] = np.where(pkg_info["package_code"].str.contains(",", na=False), "combo booking", "")
pkg_info.to_csv(f"{OUT_DIR}/Package_Info.csv", index=False)
print(f"Package_Info rows: {len(pkg_info)} (column renamed to bookings_{WINDOW_TAG})")

# ============ 4. Segment_Summary ============
seg = clean.groupby(["week_start", "customer_category", "Booking_Flag", "city_bucket6"], dropna=False).agg(
    bookings=("booking_id", "count"), gm_sum=("Gross_Margin", "sum"), revenue_sum=("Collected Net Revenue", "sum"),
    offer_price_sum=("offer_price", "sum"),
).reset_index().rename(columns={"Booking_Flag": "booking_flag", "city_bucket6": "city_bucket"})
seg["gm_pct"] = (seg["gm_sum"] / seg["revenue_sum"].replace(0, np.nan) * 100).round(1)
seg["asp"] = (seg["offer_price_sum"] / seg["bookings"]).round(0)
seg = seg.drop(columns=["offer_price_sum"]).round({"gm_sum": 0, "revenue_sum": 0})
seg.to_csv(f"{OUT_DIR}/Segment_Summary.csv", index=False)
print("Segment_Summary rows:", len(seg))

# ============ 5. Channel_Summary ============
chan = clean.groupby(["week_start", "booked_by", "city_bucket6"], dropna=False).agg(
    bookings=("booking_id", "count"), gm_sum=("Gross_Margin", "sum"), revenue_sum=("Collected Net Revenue", "sum"),
    avg_discount_pct=("Total_Discount %", "mean"),
).reset_index().rename(columns={"city_bucket6": "city_bucket"})
chan["gm_pct"] = (chan["gm_sum"] / chan["revenue_sum"].replace(0, np.nan) * 100).round(1)
chan = chan.round({"gm_sum": 0, "revenue_sum": 0, "avg_discount_pct": 1})
chan.to_csv(f"{OUT_DIR}/Channel_Summary.csv", index=False)
print("Channel_Summary rows:", len(chan))

# ============ 6. Discount_Stacking_Summary ============
disc_cols = ["special_discount", "vip_discount", "coupon_discount", "redcash", "giftcard"]
clean["n_disc_types"] = (clean[disc_cols].fillna(0) != 0).sum(axis=1)
clean["n_disc_types_bucket"] = np.where(clean["n_disc_types"] >= 3, "3+", clean["n_disc_types"].astype(str))
stack = clean.groupby(["week_start", "n_disc_types_bucket"], dropna=False).agg(
    bookings=("booking_id", "count"), gm_sum=("Gross_Margin", "sum"), revenue_sum=("Collected Net Revenue", "sum"),
).reset_index().rename(columns={"n_disc_types_bucket": "n_disc_types"})
stack["gm_pct"] = (stack["gm_sum"] / stack["revenue_sum"].replace(0, np.nan) * 100).round(1)
stack = stack.round({"gm_sum": 0, "revenue_sum": 0})
stack.to_csv(f"{OUT_DIR}/Discount_Stacking_Summary.csv", index=False)
print("Discount_Stacking_Summary rows:", len(stack))

# ============ 7. Geo_Summary: week x city(top20) x zone(top30) ============
clean["city_bucket20"] = np.where(clean["city"].isin(TOP_CITY20), clean["city"], "OTHER")
clean["zone_bucket30"] = np.where(clean["Zone"].isin(TOP_ZONE30), clean["Zone"], "OTHER")
geo = clean.groupby(["week_start", "city_bucket20", "zone_bucket30"], dropna=False).agg(
    bookings=("booking_id", "count"), gm_sum=("Gross_Margin", "sum"), revenue_sum=("Collected Net Revenue", "sum"),
    offer_price_sum=("offer_price", "sum"),
).reset_index().rename(columns={"city_bucket20": "city", "zone_bucket30": "zone"})
geo["gm_pct"] = (geo["gm_sum"] / geo["revenue_sum"].replace(0, np.nan) * 100).round(1)
geo["asp"] = (geo["offer_price_sum"] / geo["bookings"]).round(0)
geo = geo.drop(columns=["offer_price_sum"]).round({"gm_sum": 0, "revenue_sum": 0})
geo.to_csv(f"{OUT_DIR}/Geo_Summary.csv", index=False)
print("Geo_Summary rows:", len(geo))

# ============ 8. DoD_Summary: DAILY x package(top15) x city(top6), FULL range, is_partial flag ============
dod_src = df.copy()
dod_src["package_bucket"] = np.where(dod_src["package_code"].isin(TOP_PKG15), dod_src["package_code"], "OTHER")
dod_src["city_bucket"] = np.where(dod_src["city"].isin(TOP_CITY6), dod_src["city"], "OTHER")
dod_src["booking_date_str"] = dod_src["booking_date"].dt.strftime("%Y-%m-%d")
dod = dod_src.groupby(["booking_date_str", "package_bucket", "city_bucket"], dropna=False).agg(
    bookings=("booking_id", "count"), gm_sum=("Gross_Margin", "sum"), revenue_sum=("Collected Net Revenue", "sum"),
).reset_index().rename(columns={"booking_date_str": "booking_date"})
dod["gm_pct"] = (dod["gm_sum"] / dod["revenue_sum"].replace(0, np.nan) * 100).round(1)
dod["is_partial"] = ~((dod["booking_date"] >= CLEAN_START) & (dod["booking_date"] <= CLEAN_END))
dod = dod.round({"gm_sum": 0, "revenue_sum": 0})
dod.to_csv(f"{OUT_DIR}/DoD_Summary.csv", index=False)
print("DoD_Summary rows:", len(dod))

# ============ 9. Financial_Waterfall_Summary: week only, collection-complete rows only ============
fin_src = clean.dropna(subset=["Gross_Margin"])
fin = fin_src.groupby("week_start").agg(
    offer_price_sum=("offer_price", "sum"), special_discount_sum=("special_discount", "sum"),
    vip_discount_sum=("vip_discount", "sum"), coupon_discount_sum=("coupon_discount", "sum"),
    redcash_sum=("redcash", "sum"), giftcard_sum=("giftcard", "sum"),
    collected_net_revenue_sum=("Collected Net Revenue", "sum"), cpt_sum=("cpt", "sum"), gm_sum=("Gross_Margin", "sum"),
).reset_index().round(0)
fin.to_csv(f"{OUT_DIR}/Financial_Waterfall_Summary.csv", index=False)
recon = (fin["collected_net_revenue_sum"] - fin["cpt_sum"] - fin["gm_sum"]).abs()
print("Financial_Waterfall_Summary rows:", len(fin), "| max reconciliation error:", recon.max())
assert (recon < 1.0).all(), "FIN-01 waterfall does not reconcile"

# ============ 10. Package_GM_Summary: full package universe, >=10 bookings kept individually ============
pkg_counts = clean["package_code"].value_counts()
KEEP_PKG = pkg_counts[pkg_counts >= 10].index.tolist()
clean["package_bucket_full"] = np.where(clean["package_code"].isin(KEEP_PKG), clean["package_code"], "OTHER")
pkgsum = clean.groupby("package_bucket_full", dropna=False).agg(
    bookings=("booking_id", "count"), gm_sum=("Gross_Margin", "sum"), revenue_sum=("Collected Net Revenue", "sum"),
    offer_price_sum=("offer_price", "sum"),
).reset_index().rename(columns={"package_bucket_full": "package_code"})
pkgsum["gm_pct"] = (pkgsum["gm_sum"] / pkgsum["revenue_sum"].replace(0, np.nan) * 100).round(1)
pkgsum["asp"] = (pkgsum["offer_price_sum"] / pkgsum["bookings"]).round(0)
pkgsum["is_combo"] = pkgsum["package_code"].str.contains(",", na=False)
pkgsum = pkgsum.drop(columns=["offer_price_sum"]).round({"gm_sum": 0, "revenue_sum": 0})
pkgsum.to_csv(f"{OUT_DIR}/Package_GM_Summary.csv", index=False)
print("Package_GM_Summary rows:", len(pkgsum), "| combo rows:", pkgsum["is_combo"].sum())

print("\nAll 9 tabs rebuilt OK ->", OUT_DIR)
print("New clean window:", CLEAN_START, "to", CLEAN_END)
print("Base file:", SRC, "|", len(df), "rows, Jun2-Aug23")
