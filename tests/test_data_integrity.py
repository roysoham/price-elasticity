"""
Acceptance tests #1 (reconciliation), #3 (no real-world names), #9 (meta-derived
strings) from PORTFOLIO_BUILD_SPEC.md section 9. Pure Python/pandas, no browser
needed -- see tests/test_browser.spec.js for the behavioural checks (#2, #4-8, #10).

Run: python3 tests/test_data_integrity.py
"""
import hashlib
import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_DATA = os.path.join(REPO_ROOT, "site", "data")

failures = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


# ---------- #1 reconciliation ----------
def load_csv(name):
    import csv
    path = os.path.join(SITE_DATA, f"{name}.csv")
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def fnum(row, key):
    v = row.get(key, "")
    return float(v) if v not in ("", None) else 0.0


waterfall = load_csv("weekly_waterfall")
complete_wf = [r for r in waterfall if r["is_partial"] == "False"]

PER_ROW_TOL = 0.0101  # spec's "0.01" tolerance, inclusive of float rounding right at the boundary

bad_weeks = []
for r in complete_wf:
    net, cost, gm = fnum(r, "net"), fnum(r, "cost"), fnum(r, "gm")
    if abs((net - cost) - gm) > PER_ROW_TOL:
        bad_weeks.append(r["week_start"])
check("weekly_waterfall: net - cost = gm, every complete week", not bad_weeks, f"bad weeks: {bad_weeks}")

total_wf_gm = sum(fnum(r, "gm") for r in complete_wf)
# Cross-table totals are each an independent sum over a different grouping of the same
# ~hundreds-of-thousands-of-bookings universe (different row order/grouping), so they
# accumulate different float rounding error -- tolerance scales with magnitude rather
# than reusing the per-row cent tolerance above.
AGG_TOL = max(1.0, abs(total_wf_gm) * 1e-6)

stack = load_csv("weekly_stack")
total_stack_gm = sum(fnum(r, "gm") for r in stack if r["is_partial"] == "False")
check("weekly_stack total GM matches weekly_waterfall total GM",
      abs(total_stack_gm - total_wf_gm) < AGG_TOL, f"{total_stack_gm} vs {total_wf_gm}")

coupon = load_csv("weekly_coupon")
total_coupon_gm = sum(fnum(r, "gm") for r in coupon if r["is_partial"] == "False")
check("weekly_coupon total GM matches weekly_waterfall total GM",
      abs(total_coupon_gm - total_wf_gm) < AGG_TOL, f"{total_coupon_gm} vs {total_wf_gm}")

segment = load_csv("weekly_segment")
total_segment_gm = sum(fnum(r, "gm") for r in segment if r["is_partial"] == "False")
check("weekly_segment total GM matches weekly_waterfall total GM",
      abs(total_segment_gm - total_wf_gm) < AGG_TOL, f"{total_segment_gm} vs {total_wf_gm}")

sku = load_csv("weekly_market_sku")
total_sku_gm = sum(fnum(r, "gm") for r in sku if r["is_partial"] == "False")
check("weekly_market_sku total GM matches weekly_waterfall total GM",
      abs(total_sku_gm - total_wf_gm) < AGG_TOL, f"{total_sku_gm} vs {total_wf_gm}")


# ---------- #3 no real-world names ----------
# SHA-256(lowercase token) for every banned real-world string. No plain text here --
# derive the list from the internal dashboard (index.html / CLAUDE.md) if you need to
# extend it: company name, sheet ID, real coupon/package codes, real city names,
# internal file-name stems, the three live Netlify slugs.
BANNED_HASHES = {
    "42269f06fc9ea7dc6048658300d20695d29f8285c5cf8b767868f83718fb5f81",
    "922c9548ebcd48fbcf081c528f72ae3f4effca214d11d55b6735514962110a27",
    "2858ee3aa42001c3d0e39479c2d867d01d2304708001850212f9794e31fe4b0b",
    "f7d0a2333b6008cf048389fd8352426e071adf6d05fb7be0b9bcebf395c8ee6f",
    "55e5e0d6afd6837f3d6bc024a04d249d7ecb86bedf66672966d3abd352475637",
    "bc7f05c0a5efa40a130998fd86216e7d72aa2567fe157c65308c86d5060efda0",
    "3fff78320e73059741c972524a6a33d17af5f3047e1cd71b9e5e6c3e21f27a6f",
    "ce8837ababcf221ff871eca42f802f26749eb448b267b980f901889608aeb149",
    "59fae6b4e333de7c085f7048ffd64c56bcd9956544912f02db07899b015f2f4c",
    "e79b3d6c2c9cf856818d4b35fc2a4678d2181832913c651f938acd644ec513f2",
    "4205033bd1dfc5ee918250711dd9237b834dfb5cde5f0b676b6d42f9e673c7cc",
    "e65a700f1e1ef204bc6a4a8cc73a92aa03b2a6d8e23b8fb7e6bd9d6a402aba7a",
    "53cd5cdd4366e2f03e6404d9f469b54db0d03f571f30e9efae3f280442ebac42",
    "4de3010d2244cb8aaba747a061a069afd277bfb2b671ce53f5e717d8302a6b18",
    "6d8b4e16cbf43d1b387f0899f0c1164895c5a8f952a21ec9ab8365230ace82d3",
    "75bdaf171e2cfc712d41d655b84b2139c7741792632e0b534508845c3d0d036c",
    "d209bcc17778fd19fd2bc0c99a3868bf011da5162d3a75037a605768ebc276e2",
    "40ace5b4f58193240d4006e6468fa37fdf64111407672475b0a804b4a76d0339",
    "c5508df96097559eba53e0301aaf688926e0c3c6c5568883defcc6823b6c9e3f",
    "6b465516e7221fc65d4c48330a398de95ce1b11089f185d2e4874499ae96f1c8",
    "997fd09b1525ef0c91232cbba0b70b83b5ec4599be8e92c8e240e924192c3179",
    "f9584209348e402f0a472b6809c036a7162d1a59e2ce31d7b0dab4d66c34f636",
    "1114c6826958d2a68e23243c9ce4be4ec82ecc330aa915fe34eed793a69a4042",
    "6689106ca7922c30b2fd2c175c85bc7fc2d52cc4941bdd7bb622c6cdc6284a85",
    "1fff55ae51b6ec5231c5e1f4349d48b8e98c28db8f3eb05d1821cac20cdd82f8",
    "b4c0372af033c406857a420644e46c806280a0bab8246bd0c62c7807f66f794f",
    "a59f6598a62478c05e206d83593f510080816c99f4d0a3c90c59b2567d3f758a",
    "ce12e19a28f61d264967bcf66c5f2c917395aaf5214aa4310d90bbe42551841f",
    "5b2fa990487c5c7d39ead6264f43a89b9b0aa05dbc10d2cc1f2e4c5a5912b832",
    "f0bddb3cc08da99e0b275e53901530e75b9da407d00873c9d89b2f0e8aeebe78",
}
# (hashes cover: the company name and its one-word form, the live Sheet ID, the three
# Netlify slugs, two real coupon codes, four real package codes, four internal
# file-name stems, and a dozen major Indian city names -- see tests/README.md)

SCAN_DIRS = [
    os.path.join(REPO_ROOT, "site"),
    os.path.join(REPO_ROOT, "tests"),
]
# CLAUDE.md documents the pre-existing *internal* dashboard and legitimately names the
# real company/coupons/cities throughout -- only the section this change adds, about the
# new public site, needs to be clean. That section is fenced with these HTML-comment
# markers (see CLAUDE.md) so the scan can target just it.
CLAUDE_MD_PATH = os.path.join(REPO_ROOT, "CLAUDE.md")
CLAUDE_MD_FENCE_START = "<!-- PUBLIC_SITE_SECTION_START -->"
CLAUDE_MD_FENCE_END = "<!-- PUBLIC_SITE_SECTION_END -->"

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-]{2,60}")


def hashed(word):
    return hashlib.sha256(word.lower().encode()).hexdigest()


def scan_file(path):
    hits = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except OSError:
        return hits
    for m in TOKEN_RE.finditer(text):
        tok = m.group(0)
        if hashed(tok) in BANNED_HASHES:
            hits.append(tok)
    return hits

all_hits = {}
files_scanned = 0
for d in SCAN_DIRS:
    if not os.path.isdir(d):
        continue
    for root, _, files in os.walk(d):
        for fn in files:
            if fn.endswith((".png", ".jpg", ".jpeg")):
                continue
            p = os.path.join(root, fn)
            files_scanned += 1
            hits = scan_file(p)
            if hits:
                all_hits[p] = hits

if os.path.isfile(CLAUDE_MD_PATH):
    with open(CLAUDE_MD_PATH, encoding="utf-8") as f:
        claude_md = f.read()
    start = claude_md.find(CLAUDE_MD_FENCE_START)
    end = claude_md.find(CLAUDE_MD_FENCE_END)
    if start == -1 or end == -1:
        all_hits[CLAUDE_MD_PATH] = ["MISSING public-site section fence markers"]
    else:
        files_scanned += 1
        fenced_text = claude_md[start:end]
        hits = []
        for m in TOKEN_RE.finditer(fenced_text):
            tok = m.group(0)
            if hashed(tok) in BANNED_HASHES:
                hits.append(tok)
        if hits:
            all_hits[CLAUDE_MD_PATH] = hits

script_dir = os.path.join(REPO_ROOT, "scripts")
if os.path.isdir(script_dir):
    for fn in os.listdir(script_dir):
        if fn.startswith("synthetic_") and fn.endswith(".py"):
            p = os.path.join(script_dir, fn)
            files_scanned += 1
            hits = scan_file(p)
            if hits:
                all_hits[p] = hits

check(f"no banned real-world tokens in site/, tests/, scripts/synthetic_*, CLAUDE.md ({files_scanned} files scanned)",
      not all_hits, f"hits: {all_hits}")

# docs.google.com must never be referenced from the new public site
gviz_hit = False
site_index = os.path.join(REPO_ROOT, "site", "index.html")
if os.path.isfile(site_index):
    with open(site_index, encoding="utf-8") as f:
        gviz_hit = "docs.google.com" in f.read()
check("site/index.html never references docs.google.com", not gviz_hit)


# ---------- #9 data-basis strings derive from meta.json, not hand-typed ----------
with open(os.path.join(SITE_DATA, "meta.json")) as f:
    meta = json.load(f)

with open(site_index, encoding="utf-8") as f:
    html = f.read()

# strip the <script> block's own meta.json field *references* (STATE.meta.xxx) before
# scanning for literal hand-typed dates; anything matching meta's own date values
# elsewhere in the file (outside the JSON comment reference) would indicate a hardcode.
suspicious = []
for key in ("first_week", "last_complete_week", "partial_week", "generated"):
    val = str(meta.get(key, ""))
    if not val:
        continue
    # every occurrence of this exact date string in the HTML must be inside the <script>
    # block (i.e. could only have gotten there by interpolation at render time) -- a
    # hand-typed literal would appear in the static HTML/markup portion instead.
    script_start = html.find("<script>\n/* ============")
    markup_before_script = html[:script_start] if script_start > 0 else ""
    if val in markup_before_script:
        suspicious.append((key, val))
check("no hand-typed meta.json date literal in static markup", not suspicious, f"{suspicious}")

print()
if failures:
    print(f"{len(failures)} check(s) FAILED: {failures}")
    sys.exit(1)
else:
    print("All data-integrity checks passed.")
