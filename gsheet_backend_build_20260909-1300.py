"""
Full rebuild of all 10 backend tabs from the new collection_date-scoped
monthly raw files (July/Aug/Sep2026), replacing the old single-rolling-file
approach entirely. See CLAUDE.md "Raw data source" section for the full
rationale; summary:

- Each online_discount_summary__raw_*.xlsx is scoped by collection_date
  (the month payment settled), not booking_date (the appointment/test
  date) -- confirmed empirically 2026-09-09. Files are therefore disjoint
  by construction (zero booking_id overlap between any two) -- this script
  just unions them, no dedup needed.
- Every row in every file already has a non-null Gross_Margin (collection,
  by definition, already happened for every row in a collection-scoped
  file) -- the old "scan for null GM near the tail" clean-window heuristic
  is now moot. Replaced with a settlement-lag-based rule: a booking_date
  is "clean" once we have a FULL collection-month file at least one month
  past it (empirically, 96-97% of a booking_month's eventual volume
  collects within that same month, another ~3% within the next month --
  see the analysis behind this script's authoring commit).
- We have no June (or earlier) collection-month file. May/June rows that
  do appear (stragglers that collected in July) are a small, structurally
  biased fragment -- NOT a real "business was ramping up" signal, just a
  data-coverage gap. Excluded entirely from clean-window tabs; excluded
  from DoD_Summary too (unlike a genuinely partial/settling month like the
  current one, showing this fragment even dashed would misrepresent real
  activity levels as near-zero).
"""
import pandas as pd
import numpy as np
import glob
import json
import os

REPO_ROOT = "/home/user/price-elasticity"
OUT_DIR = "/tmp/claude-0/-home-user-price-elasticity/aabc5007-5332-538d-9613-577e4a814ad1/scratchpad/gsheet_build_20260909"
os.makedirs(OUT_DIR, exist_ok=True)

with open(f"{REPO_ROOT}/data_manifest.json") as f:
    manifest = json.load(f)

frames = []
for entry in manifest["files"]:
    df = pd.read_excel(f"{REPO_ROOT}/{entry['filename']}")
    df["_src_file"] = entry["filename"]
    frames.append(df)
    print(f"loaded {entry['filename']}: {len(df)} rows")

df = pd.concat(frames, ignore_index=True)
assert df["booking_id"].is_unique, "booking_id collision across files -- files are no longer disjoint, dedup logic needed"
print(f"union: {len(df)} rows, {df['booking_id'].nunique()} unique booking_id (confirmed disjoint)")

# Collection happening (collection_date set) doesn't mean GM has finished computing -- there's a
# short secondary GM-computation lag on top of the booking->collection lag, concentrated in the
# first few days after each collection_date (e.g. 2,038 of the 2026-07-01 collection-date rows are
# still null-GM in this pull). Revenue is real for these rows but GM isn't, which would otherwise
# silently unbalance every gm_sum/revenue_sum pair downstream (the same class of bug fixed once
# before in Financial_Waterfall_Summary specifically) -- drop them everywhere, not settled yet.
gm_null = df["Gross_Margin"].isna().sum()
print(f"{gm_null} rows have collection_date set but Gross_Margin still null (GM computation lag) -- excluded from all tabs")
df = df.dropna(subset=["Gross_Margin"]).copy()

# cpt: defensive Excel-overflow-corruption fix (recurred once before, cheap to guard against)
df["cpt"] = pd.to_numeric(df["cpt"], errors="coerce")
cpt_missing = df["cpt"].isna() & df["Gross_Margin"].notna()
df.loc[cpt_missing, "cpt"] = df.loc[cpt_missing, "Collected Net Revenue"] - df.loc[cpt_missing, "Gross_Margin"]
if cpt_missing.sum():
    print(f"cpt reconstructed from GM identity for {cpt_missing.sum()} rows")

df["week_start"] = (df["booking_date"] - pd.to_timedelta(df["booking_date"].dt.weekday, unit="D")).dt.strftime("%Y-%m-%d")

# ---------- clean window: settlement-based, derived from the manifest, not hardcoded ----------
collection_months_covered = sorted({m for e in manifest["files"] for m in e["collection_months"]})
latest_collection_month = pd.Period(collection_months_covered[-1])
clean_end = (latest_collection_month - 1).end_time.normalize()  # last day of the month BEFORE the latest (still-settling) one

# earliest FULL (single-collection-month, non-MTD) file sets clean_start; anything with booking_date
# before that is a structural gap (no collection file covers it), not a "partial" period
full_month_files = [e for e in manifest["files"] if len(e["collection_months"]) == 1]
clean_start = min(pd.Period(e["collection_months"][0]).start_time for e in full_month_files)

CLEAN_START = clean_start.strftime("%Y-%m-%d")
CLEAN_END = clean_end.strftime("%Y-%m-%d")
print(f"derived clean window: {CLEAN_START} to {CLEAN_END} (latest collection month {latest_collection_month} excluded as still-settling)")

clean = df[(df["booking_date"] >= CLEAN_START) & (df["booking_date"] <= CLEAN_END)].copy()
print(f"clean window rows: {len(clean)} of {len(df)} total")
assert clean["Gross_Margin"].isna().sum() == 0, "clean window has null-GM rows -- unexpected given collection-scoped files"

TOP_CITY6 = clean["city"].value_counts().head(6).index.tolist()
TOP_PKG15 = clean["package_code"].value_counts().head(15).index.tolist()
TOP_COUPON30 = clean["coupon_code"].value_counts().head(30).index.tolist()
TOP_CITY20 = clean["city"].value_counts().head(20).index.tolist()
TOP_ZONE30 = clean["Zone"].value_counts().head(30).index.tolist()
TOP_PKG80 = clean["package_code"].value_counts().head(80)

clean["package_bucket15"] = np.where(clean["package_code"].isin(TOP_PKG15), clean["package_code"], "OTHER")
clean["city_bucket6"] = np.where(clean["city"].isin(TOP_CITY6), clean["city"], "OTHER")
clean["coupon_bucket30"] = clean["coupon_code"].where(clean["coupon_code"].isin(TOP_COUPON30), "OTHER")
clean["coupon_bucket30"] = clean["coupon_bucket30"].fillna("NONE")

# ============ 1. Booking_Weekly_Summary ============
bs = clean.groupby(["week_start", "package_bucket15", "city_bucket6"], dropna=False).agg(
    bookings=("booking_id", "count"), gm_sum=("Gross_Margin", "sum"), revenue_sum=("Collected Net Revenue", "sum"),
).reset_index().rename(columns={"package_bucket15": "package_bucket", "city_bucket6": "city_bucket"})
bs["gm_pct"] = (bs["gm_sum"] / bs["revenue_sum"].replace(0, np.nan) * 100).round(1)
bs = bs.round({"gm_sum": 0, "revenue_sum": 0})
bs.to_csv(f"{OUT_DIR}/Booking_Weekly_Summary.csv", index=False)
print("Booking_Weekly_Summary rows:", len(bs))

# ============ 2. Coupon_Summary ============
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

# ============ 3. Package_Info ============
window_tag = f"{clean_start.strftime('%b%d').lower()}_{clean_end.strftime('%b%d').lower()}"
pkg_info = TOP_PKG80.reset_index()
pkg_info.columns = ["package_code", f"bookings_{window_tag}"]
pkg_info["note"] = np.where(pkg_info["package_code"].str.contains(",", na=False), "combo booking", "")
pkg_info.to_csv(f"{OUT_DIR}/Package_Info.csv", index=False)
print(f"Package_Info rows: {len(pkg_info)} (bookings column: bookings_{window_tag})")

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

# ============ 7. Geo_Summary ============
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

# ============ 8. DoD_Summary: DAILY, full range EXCLUDING the pre-clean-start structural gap ============
# (unlike a genuinely partial/settling month, the pre-clean-start fragment is a coverage gap, not
# real-but-incomplete data -- showing it even dashed would misrepresent activity as near-zero)
dod_src = df[df["booking_date"] >= CLEAN_START].copy()
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
print("DoD_Summary rows:", len(dod), f"(excludes {len(df[df['booking_date'] < CLEAN_START])} pre-{CLEAN_START} gap rows entirely)")

# ============ 9. Financial_Waterfall_Summary ============
fin = clean.groupby("week_start").agg(
    offer_price_sum=("offer_price", "sum"), special_discount_sum=("special_discount", "sum"),
    vip_discount_sum=("vip_discount", "sum"), coupon_discount_sum=("coupon_discount", "sum"),
    redcash_sum=("redcash", "sum"), giftcard_sum=("giftcard", "sum"),
    collected_net_revenue_sum=("Collected Net Revenue", "sum"), cpt_sum=("cpt", "sum"), gm_sum=("Gross_Margin", "sum"),
).reset_index().round(0)
fin.to_csv(f"{OUT_DIR}/Financial_Waterfall_Summary.csv", index=False)
recon = (fin["collected_net_revenue_sum"] - fin["cpt_sum"] - fin["gm_sum"]).abs()
print("Financial_Waterfall_Summary rows:", len(fin), "| max reconciliation error:", recon.max())
assert (recon < 1.0).all(), "FIN-01 waterfall does not reconcile"

# ============ 10. Package_GM_Summary ============
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

print(f"\nAll 10 tabs rebuilt OK -> {OUT_DIR}")
print(f"Clean window: {CLEAN_START} to {CLEAN_END} | latest collection month (excluded, still settling): {latest_collection_month}")
print(f"Source files: {[e['filename'] for e in manifest['files']]}")
