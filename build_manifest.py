"""
Scans the repo root for online_discount_summary__raw_*.xlsx files and writes
data_manifest.json -- the "date-wise mapping file": one row per raw export,
recording which collection_date month it covers.

Each file is scoped by collection_date (the month payment settled), not
booking_date (the appointment/test date) -- confirmed empirically 2026-09-09:
every row in a given file has collection_date falling entirely within one
calendar month, booking_date can spill backward by weeks/months (a booking
made in May can still collect payment in July). Files are therefore disjoint
by construction (zero booking_id overlap between any two files) -- no dedup
needed when combining them, just a union.

Re-run this whenever a raw file is added/removed, and commit the updated
data_manifest.json in the same change.
"""
import pandas as pd
import glob
import json
import os

REPO_ROOT = "/home/user/price-elasticity"
OUT_PATH = f"{REPO_ROOT}/data_manifest.json"

files = sorted(glob.glob(f"{REPO_ROOT}/online_discount_summary__raw_*.xlsx"))
manifest = {"files": []}

for f in files:
    fname = os.path.basename(f)
    df = pd.read_excel(f, usecols=["booking_id", "booking_date", "collection_date"])
    cd = pd.to_datetime(df["collection_date"])
    bd = pd.to_datetime(df["booking_date"])
    collection_months = cd.dt.to_period("M").unique()
    entry = {
        "filename": fname,
        "rows": len(df),
        "collection_date_min": str(cd.min().date()),
        "collection_date_max": str(cd.max().date()),
        "collection_months": [str(m) for m in sorted(collection_months)],
        "booking_date_min": str(bd.min().date()),
        "booking_date_max": str(bd.max().date()),
        "booking_id_min": int(df["booking_id"].min()),
        "booking_id_max": int(df["booking_id"].max()),
    }
    if len(collection_months) > 1:
        entry["note"] = "spans multiple collection months -- treat as month-to-date/partial, not a clean single-month file"
    manifest["files"].append(entry)
    print(f"{fname}: {len(df)} rows, collection_date {entry['collection_date_min']}..{entry['collection_date_max']}, booking_date {entry['booking_date_min']}..{entry['booking_date_max']}")

with open(OUT_PATH, "w") as fh:
    json.dump(manifest, fh, indent=2)
print(f"\nWrote {OUT_PATH}")
