#!/usr/bin/env python3
"""Synthetic diagnostics-booking generator for the Margin & Pricing Command Center demo.

Deterministic (fixed seed). Simulates booking-level rows in memory, then aggregates every
published table from that single frame, so all tables reconcile exactly. Planted patterns and
ground truth are written to truth.json so the dashboard's estimates can be tested against them.

Usage: python3 synthetic_data_20261028-1307.py [output_dir]   (default: site/data)
Needs: numpy, pandas.
"""
import json
import pathlib
import sys

import numpy as np
import pandas as pd

SEED = 20261028
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("site/data")
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(SEED)

W0 = pd.Timestamp("2026-06-08")  # a Monday
N_WEEKS = 21                     # weeks 0..19 complete; week 20 is partial (2 of 7 days)
PARTIAL_WEEK = 20
PARTIAL_FACTOR = 2 / 7
BASE_WEEKLY = 40000

MARKETS = list("ABCDEF")
M_SHARE = np.array([.26, .20, .17, .14, .12, .11])
M_PRICE = np.array([1.00, 1.00, .97, .95, .92, .90])  # market-tier pricing
TIERS = ["Standard", "Member", "Premium member"]
T_SHARE = [.45, .30, .25]
T_MEMBER_DISC = np.array([0, .10, .15])
T_MEMBER_P = np.array([0, .94, .94])
T_REPEAT = np.array([.45, .70, .85])
T_COUPON_P = np.array([.68, .62, .62])
T_WALLET_P = np.array([.06, .22, .28])
T_GIFT_P = np.array([.03, .08, .10])
CHANNELS = ["Self", "Sales", "Field collector"]
C_SHARE = [.55, .30, .15]

# code, category, USD list price, volume weight, cost-ratio offset
SKUS = [
    ("SKU-01", "Thyroid panel", 14, .20, -.02), ("SKU-02", "Metabolic panel", 24, .12, .01),
    ("SKU-03", "Vitamin panel", 29, .10, .00), ("SKU-04", "Full-body screen", 79, .09, .03),
    ("SKU-05", "Diabetes panel", 22, .08, .00), ("SKU-06", "Lipid profile", 12, .07, -.01),
    ("SKU-07", "Fever panel", 16, .06, .00), ("SKU-08", "Women's health panel", 54, .05, .02),
    ("SKU-09", "Cardiac risk panel", 64, .04, .03), ("SKU-10", "Hormone panel", 38, .035, .02),
    ("SKU-11", "Liver panel", 15, .03, -.01), ("SKU-12", "Kidney panel", 17, .03, -.01),
    ("SKU-13", "Allergy panel", 69, .02, .03), ("SKU-14", "Senior screen", 99, .02, .03),
    ("SKU-15", "Executive screen", 139, .015, .04), ("SKU-LT", "Long tail", 34, .09, .00),
]
SKU_CODES = [s[0] for s in SKUS]
SKU_PRICE = np.array([s[2] for s in SKUS], float)
SKU_W = np.array([s[3] for s in SKUS], float)
SKU_W = SKU_W / SKU_W.sum()
SKU_OFF = np.array([s[4] for s in SKUS], float)
HIGH_COST = {"SKU-04", "SKU-09", "SKU-14", "SKU-15"}
LT = SKU_CODES.index("SKU-LT")

COUPONS = ["SAVER10", "SAVER15", "SAVER20", "SAVER22", "SAVER25", "PARTNER20", "FAMILY2",
           "FAMILY3", "FAMILY4", "LOYALTY15", "WELCOME15", "FESTIVE25", "BUNDLE40"]
C_DEPTH = np.array([.10, .15, .20, .22, .25, .20, .12, .17, .22, .15, .15, .25, .40])
C_BASEW = np.array([.03, .20, .24, .12, .05, .09, .08, .03, .015, .05, .07, 0, 0])
FESTIVE_WEEKS = range(11, 15)
BUNDLE_START = 7
STACK_ADD = {0: 0.0, 1: .045, 2: .03, 3: .02}  # discounts skew to higher-cost tests
BASE_CR = .18
CAMPAIGN_WEEKS = range(0, 4)                  # campaign discount switched off after week 3
PROMO_B = (12, 13)                            # market-B coupon push (confounds events in B)

# price events: id, sku, treated markets, pct change, change week (None = not executed), true elasticity, status, control
EVENTS = [
    ("E01", "SKU-01", ["B"], .10, 9, -.6, "Uploaded", "A"),
    ("E02", "SKU-02", ["C"], .10, 10, -1.2, "Uploaded", "A"),
    ("E03", "SKU-03", ["B"], .12, 10, -.9, "Uploaded", "A"),
    ("E04", "SKU-05", ["C", "E"], .10, 11, -1.5, "Uploaded", "D"),
    ("E05", "SKU-06", ["D"], .12, 11, -.4, "Uploaded", "A"),
    ("E06", "SKU-04", ["E"], -.10, 12, -1.0, "Uploaded", "A"),
    ("E07", "SKU-07", ["F"], .12, 13, -1.8, "Uploaded", "D"),
    ("E08", "SKU-08", ["C"], .10, 14, -.7, "Uploaded", "A"),
    ("E09", "SKU-09", ["B"], .05, None, -.8, "Recommended", "A"),
    ("E10", "SKU-10", ["D"], .06, None, -1.0, "Recommended", "A"),
    ("E11", "SKU-11", ["E"], .04, None, -.5, "Not uploaded", "A"),
]
CONFOUNDED = {"E01", "E03"}  # treated market B + coupon push inside the post window


def week_start(w):
    return W0 + pd.Timedelta(days=7 * w)


def price_mult(w, m, s):
    mult, elast = 1.0, 1.0
    for eid, sku, mk, pct, cw, e, status, ctrl in EVENTS:
        if cw is not None and sku == s and m in mk and w >= cw:
            mult *= (1 + pct)
            elast *= (1 + pct) ** e
    return mult, elast


frames = []
for w in range(N_WEEKS):
    growth = 1 + .004 * w
    season = 1.08 if w in FESTIVE_WEEKS else 1.0
    part = PARTIAL_FACTOR if w == PARTIAL_WEEK else 1.0
    cells = []
    for mi, m in enumerate(MARKETS):
        for si, s in enumerate(SKU_CODES):
            pm, vm = price_mult(w, m, s)
            promo = 1.15 if (m == "B" and w in PROMO_B) else 1.0
            lam = BASE_WEEKLY * growth * season * part * M_SHARE[mi] * SKU_W[si] * vm * promo
            cells.append((mi, si, pm, rng.poisson(lam)))
    mi_a = np.concatenate([np.full(c[3], c[0]) for c in cells])
    si_a = np.concatenate([np.full(c[3], c[1]) for c in cells])
    pm_a = np.concatenate([np.full(c[3], c[2]) for c in cells])
    n = len(mi_a)
    offer = SKU_PRICE[si_a] * M_PRICE[mi_a] * pm_a
    lt = si_a == LT
    offer[lt] *= rng.lognormal(0, .35, lt.sum())
    offer = np.round(offer, 2)

    tier = rng.choice(3, n, p=T_SHARE)
    chan = rng.choice(3, n, p=C_SHARE)
    repeat = rng.random(n) < T_REPEAT[tier]

    # coupon assignment
    pc = T_COUPON_P[tier].copy()
    if w in PROMO_B:
        pc[mi_a == 1] = .75
    has_c = rng.random(n) < pc
    W = np.tile(C_BASEW, (n, 1))
    W[repeat, COUPONS.index("WELCOME15")] = 0
    if w in FESTIVE_WEEKS:
        W[:, COUPONS.index("FESTIVE25")] = .14
    if w >= BUNDLE_START:
        elig = (tier > 0) & np.isin(si_a, [SKU_CODES.index(c) for c in HIGH_COST])
        W[elig, COUPONS.index("BUNDLE40")] = .20
    W = W / W.sum(1, keepdims=True)
    cum = W.cumsum(1)
    ci = (rng.random((n, 1)) > cum).sum(1).clip(0, len(COUPONS) - 1)
    ci = np.where(has_c, ci, -1)
    depth = np.where(ci >= 0, C_DEPTH[np.maximum(ci, 0)], 0.0)

    d_coupon = depth * offer
    d_member = T_MEMBER_DISC[tier] * offer * (rng.random(n) < T_MEMBER_P[tier])
    d_campaign = (.05 * offer * (rng.random(n) < .07)) if w in CAMPAIGN_WEEKS else np.zeros(n)
    d_wallet = rng.uniform(.02, .07, n) * offer * (rng.random(n) < T_WALLET_P[tier])
    d_gift = rng.uniform(.05, .20, n) * offer * (rng.random(n) < T_GIFT_P[tier])
    tot = d_coupon + d_member + d_campaign + d_wallet + d_gift
    scale = np.minimum(1, .95 * offer / np.maximum(tot, 1e-9))
    d_coupon, d_member, d_campaign, d_wallet, d_gift = [x * scale for x in (d_coupon, d_member, d_campaign, d_wallet, d_gift)]
    ntypes = sum((x > 0).astype(int) for x in (d_coupon, d_member, d_campaign, d_wallet, d_gift))
    cr = BASE_CR + SKU_OFF[si_a] + np.vectorize(lambda k: STACK_ADD[min(int(k), 3)])(ntypes)
    is_bundle = ci == COUPONS.index("BUNDLE40")
    cr = np.where(is_bundle, rng.uniform(.38, .52, n), cr)
    net = offer - d_coupon - d_member - d_campaign - d_wallet - d_gift
    cost = offer * cr
    frames.append(pd.DataFrame({
        "week": w, "market": np.array(MARKETS)[mi_a], "sku": np.array(SKU_CODES)[si_a],
        "tier": np.array(TIERS)[tier], "channel": np.array(CHANNELS)[chan],
        "flag": np.where(repeat, "Repeat", "Fresh"),
        "coupon": np.where(ci >= 0, np.array(COUPONS)[np.maximum(ci, 0)], "None"),
        "ntypes": np.minimum(ntypes, 3), "offer": offer, "campaign": d_campaign, "member": d_member,
        "coupon_d": d_coupon, "wallet": d_wallet, "gift": d_gift, "net": net, "cost": cost,
    }))

df = pd.concat(frames, ignore_index=True)
df["gm"] = df["net"] - df["cost"]
df["neg"] = (df["gm"] < 0).astype(int)
df["week_start"] = df["week"].map(lambda w: week_start(w).strftime("%Y-%m-%d"))
df["is_partial"] = (df["week"] == PARTIAL_WEEK)
df["n3"] = (df["ntypes"] >= 3).astype(int)
df["n_disc_types"] = df["ntypes"].map(lambda k: "3+" if k >= 3 else str(k))
SUMS = ["offer", "campaign", "member", "coupon_d", "wallet", "gift", "net", "cost", "gm"]


def agg(keys, extra=None):
    g = df.groupby(keys, as_index=False).agg(bookings=("offer", "size"), **{c: (c, "sum") for c in SUMS},
                                           **(extra or {}))
    g[SUMS] = g[SUMS].round(2)
    g["gm_pct"] = (100 * g["gm"] / g["net"]).round(2)
    return g


agg(["week_start", "is_partial", "market", "sku"]).to_csv(OUT / "weekly_market_sku.csv", index=False)
agg(["week_start", "is_partial", "n_disc_types", "tier"]).to_csv(OUT / "weekly_stack.csv", index=False)
agg(["week_start", "is_partial", "coupon"], dict(repeat_bookings=("flag", lambda s: (s == "Repeat").sum()),
                                                  bookings_3plus=("n3", "sum"), bookings_negative_gm=("neg", "sum"))
    ).to_csv(OUT / "weekly_coupon.csv", index=False)
agg(["week_start", "is_partial", "market", "tier", "flag", "channel"]).to_csv(OUT / "weekly_segment.csv", index=False)
wf = agg(["week_start", "is_partial"])
wf.to_csv(OUT / "weekly_waterfall.csv", index=False)

rows = []
for eid, sku, mk, pct, cw, e, status, ctrl in EVENTS:
    for m in mk:
        old = round(float(SKU_PRICE[SKU_CODES.index(sku)] * M_PRICE[MARKETS.index(m)]), 2)
        new = round(old * (1 + pct), 2)
        rows.append(dict(event_id=eid, sku=sku, market=m, old_price=old, new_price=new,
                         price_change=round(new - old, 2), pct_change=round(100 * pct, 1),
                         status=status, change_date=week_start(cw).strftime("%Y-%m-%d") if cw is not None else "",
                         control_market=ctrl))
pd.DataFrame(rows).to_csv(OUT / "price_changes.csv", index=False)

promo = [dict(week_start=week_start(w).strftime("%Y-%m-%d"), market="B", event="Coupon push (SAVER20 weighting)", scope="market")
         for w in PROMO_B]
promo += [dict(week_start=week_start(w).strftime("%Y-%m-%d"), market="ALL", event="FESTIVE25 live", scope="global")
          for w in FESTIVE_WEEKS]
promo += [dict(week_start=week_start(BUNDLE_START).strftime("%Y-%m-%d"), market="ALL", event="BUNDLE40 launched", scope="global"),
          dict(week_start=week_start(4).strftime("%Y-%m-%d"), market="ALL", event="Campaign discount switched off", scope="global")]
pd.DataFrame(promo).to_csv(OUT / "promo_events.csv", index=False)

full = df[~df["is_partial"]]
stack = full.groupby("n_disc_types").agg(bookings=("offer", "size"), net=("net", "sum"), gm=("gm", "sum"))
stack["share_pct"] = (100 * stack["bookings"] / stack["bookings"].sum()).round(1)
stack["gm_pct"] = (100 * stack["gm"] / stack["net"]).round(1)
b40 = full[full["coupon"] == "BUNDLE40"]
truth = dict(
    seed=SEED, note="Ground truth for the synthetic demo. The dashboard must recover these, not read them.",
    elasticity={e[0]: dict(sku=e[1], markets=e[3 - 1], pct=e[3], change_week=e[4], true_elasticity=e[5],
                           confounded=e[0] in CONFOUNDED, status=e[6]) for e in EVENTS},
    stack_distribution_complete_weeks=stack[["share_pct", "gm_pct"]].to_dict("index"),
    planted_overstack_tail=dict(coupon="BUNDLE40", launch_week=BUNDLE_START,
                                bookings=int(len(b40)), negative_gm_bookings=int(b40["neg"].sum()),
                                negative_gm_share_pct=round(100 * float(b40["neg"].mean()), 1),
                                gm_lost_on_negative_usd=round(float(b40.loc[b40["gm"] < 0, "gm"].sum()), 2)),
    confounder="Market B coupon push in weeks 12-13 contaminates E01 and E03 post windows",
    policy_change="Campaign discount switched off after week 3",
)
(OUT / "truth.json").write_text(json.dumps(truth, indent=2, default=str))
meta = dict(generated="2026-10-28", seed=SEED, first_week=week_start(0).strftime("%Y-%m-%d"),
            last_complete_week=week_start(PARTIAL_WEEK - 1).strftime("%Y-%m-%d"),
            partial_week=week_start(PARTIAL_WEEK).strftime("%Y-%m-%d"), n_weeks=N_WEEKS, currency="USD",
            fx=dict(AED=3.6725, as_of="2026-10-28", note="indicative; editable in Assumptions"),
            min_n_for_percentages=100, stacking_so_what_basis="0->1->2 discount step, n shown per cell")
(OUT / "meta.json").write_text(json.dumps(meta, indent=2))

print("bookings:", len(df))
print(stack)
print(truth["planted_overstack_tail"])
tot = full.groupby("week_start")[["offer", "net", "cost", "gm"]].sum()
print((tot["net"] - tot["cost"] - tot["gm"]).abs().max(), "reconciliation max diff")
