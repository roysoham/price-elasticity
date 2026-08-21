import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
import datetime

FONT = "Arial"
TITLE_FILL = PatternFill("solid", fgColor="1F4E78")
SECTION_FILL = PatternFill("solid", fgColor="2E5C8A")
HEADER_FILL = PatternFill("solid", fgColor="D9E1F2")
BODY_FONT = Font(name=FONT, size=10)
BOLD = Font(name=FONT, size=10, bold=True)
GREEN = PatternFill("solid", fgColor="C6E0B4")
YELLOW = PatternFill("solid", fgColor="FFF2CC")
RED = PatternFill("solid", fgColor="F8CBAD")
thin = Side(style='thin', color="B7B7B7")
BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)

wb = Workbook()
ws = wb.active
ws.title = "ASP Action Plan"
ws.sheet_view.showGridLines = False
widths = [30, 14, 16, 14, 30, 16, 14, 16]
for j,w in enumerate(widths, start=1):
    ws.column_dimensions[get_column_letter(j)].width = w

r = 1
c = ws.cell(row=r, column=1, value="ASP Action Plan -- Redcliffe Labs")
c.font = Font(name=FONT, size=16, bold=True, color="1F4E78")
r += 1
c = ws.cell(row=r, column=1, value=f"Generated {datetime.date.today().isoformat()} | Source: online_discount_summary_raw_Aug17MTD.xlsx (Aug 1-16 clean window, 51,701 bookings) + competitor pricing file + coupon CRM settings. No new price/MoM data this cycle.")
c.font = Font(name=FONT, size=9, italic=True)
c.alignment = Alignment(wrap_text=True)
ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=8)
r += 2

def section_header(r, text):
    c = ws.cell(row=r, column=1, value=text)
    c.font = Font(name=FONT, size=12, bold=True, color="FFFFFF")
    c.fill = SECTION_FILL
    for j in range(1, 9):
        ws.cell(row=r, column=j).fill = SECTION_FILL
    ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
    return r + 1

def table_header(r, headers):
    for j, h in enumerate(headers, start=1):
        cell = ws.cell(row=r, column=j, value=h)
        cell.font = BOLD
        cell.fill = HEADER_FILL
        cell.border = BORDER
        cell.alignment = Alignment(wrap_text=True, vertical='center')
    return r + 1

def data_row(r, values, fills=None, formats=None):
    for j, v in enumerate(values, start=1):
        cell = ws.cell(row=r, column=j, value=v)
        cell.font = BODY_FONT
        cell.border = BORDER
        cell.alignment = Alignment(wrap_text=True, vertical='top')
        if formats and j in formats:
            cell.number_format = formats[j]
        if fills and j in fills:
            cell.fill = fills[j]
    return r + 1

# ============ SECTION 1 ============
r = section_header(r, "1. PRICE RECOMMENDATIONS -- sensitivity + competitor confirmed (5 tests, not 39 -- highest-confidence only)")
r = table_header(r, ["Test", "Current Price (Rs)", "Recommended Price (Rs)", "Action", "Why (Confidence)", "Impact -- Weekly GM (Rs)", "Impact -- ASP", "Owner"])
price_rows = [
 ["HBA1C Test", 357, 390, "+9.2%", "Elasticity Tier A (measured) + competitor headroom both confirm raise", 20959, "+9.2%", ""],
 ["Thyroid Profile Total", 423, 470, "+11.1%", "Elasticity Tier B + competitor headroom both confirm raise", 35655, "+11.1%", ""],
 ["Liver Function Test (LFT)", 386, 425, "+10.2%", "Elasticity ambiguous internally -- competitor headroom resolves it (Redcliffe well below Tata/Dr Lal); conservative estimate assumes flat volume", 26330, "+10.2%*", ""],
 ["Kidney Function Test (KFT)", 403, 449, "+11.4%", "Same as LFT -- competitor-confirmed, conservative flat-volume estimate", 27976, "+11.4%*", ""],
 ["TSH, Ultrasensitive", 263, 299, "+13.7%", "Elasticity inelastic-leaning (Tier A) + competitor headroom confirm raise", 9554, "+13.7%*", ""],
]
for row in price_rows:
    r = data_row(r, row, fills={4: GREEN}, formats={2:'#,##0', 3:'#,##0', 6:'#,##0'})
c = ws.cell(row=r, column=1, value="* Flat-volume conservative estimate (elasticity read unreliable for these 3 -- actual GM upside likely higher if demand holds as expected for staple diagnostic tests)")
c.font = Font(name=FONT, size=9, italic=True)
ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
r += 1
c = ws.cell(row=r, column=1, value="TOTAL projected weekly GM impact, these 5 tests:")
c.font = BOLD
tot_cell = ws.cell(row=r, column=6, value=20959+35655+26330+27976+9554)
tot_cell.font = BOLD
tot_cell.number_format = '#,##0'
r += 2
c = ws.cell(row=r, column=1, value="HELD BACK (do not action this cycle): Ferritin, Magnesium, Homocysteine, Amylase -- team's competitor file recommends raising these, but Healthians already prices meaningfully BELOW Redcliffe on these specific tests (e.g. Ferritin: Healthians Rs 235 vs Redcliffe's proposed Rs 525). Raising here risks losing price-sensitive share to the one competitor already undercutting us. Needs a Healthians-specific check before any move.")
c.font = Font(name=FONT, size=9, italic=True, color="C00000")
c.alignment = Alignment(wrap_text=True)
ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
r += 2

# ============ SECTION 2 ============
r = section_header(r, "2. CUSTOMER LEARNINGS & NUDGE ACTIONS -- fresh/repeat, AOV, city")
r = table_header(r, ["Insight", "Nudge Action", "Priority City(s)", "Execution Ease", "Impact"])
learn_rows = [
 ["VIP Gold Fresh AOV (Rs 4,653) is 2.9x Repeat AOV (Rs 1,614) -- and fresh share is shrinking (30.8%->25.7% over 11 weeks). Blended VIP Gold ASP mechanically drags down as mix shifts toward the low-value repeat cohort.",
  "In-app/CRM nudge on repeat VIP-Gold bookings to add a family member (ADDFAMILY-style, already proven to lift basket size to 2-4x members with a capped, controlled discount -- see Section 4)",
  "Ghaziabad (6.8x gap), Mumbai (3.9x), Bangalore (2.8x)", "EASY -- existing mechanic, just needs targeted nudge/CRM trigger, no new pricing or system build",
  "Directional: closing even 20% of the fresh-repeat AOV gap in these 3 cities moves blended VIP Gold ASP measurably -- size properly once nudge is live and first-week data comes back"],
 ["Gurugram's overall Fresh AOV (Rs 2,719) runs 40-70% above every other top-10 city (Rs 1,587-1,928 range) -- an outlier worth understanding before assuming it's noise.",
  "Investigate what's different in Gurugram (package mix, catchment income, channel mix) -- replicate if it's a repeatable pattern, not a one-off.",
  "Gurugram (source), test in 1-2 similar-profile cities after diagnosis", "MEDIUM -- needs a diagnosis step before any action",
  "Unknown until diagnosed -- flagged as next investigation, not sized yet"],
]
for row in learn_rows:
    r = data_row(r, row, fills={4: GREEN})
r += 1

# ============ SECTION 3 ============
r = section_header(r, "3. THIS CYCLE'S EXECUTION LIST -- the few pkg/test to action now")
r = table_header(r, ["#", "Test", "Action", "Owner", "Target Date"])
for i, row in enumerate(price_rows, start=1):
    r = data_row(r, [i, row[0], f"Move price {row[3]}", "", ""])
r += 1

# ============ SECTION 4 ============
r = section_header(r, "4. COUPON CEILINGS & CONTROLS")
r = table_header(r, ["Control", "Finding", "Action", "Impact"])
coupon_rows = [
 ["Depth ceiling", "Real GM% holds up through ~20% coupon depth (82%->77%->71%), degrades steadily beyond it, only collapses meaningfully at 40%+ (43% GM, mostly FREEDOM50).",
  "Set 20% as the standard depth ceiling for new/renewed campaigns. FREEDOM50 (42% depth, 47.9% GM) is below-average but not urgent -- optimize when convenient, not this cycle.", "Directional margin protection, not a one-time number"],
 ["Price x coupon stacking risk", "4 packages flagged for a price increase are ALSO heavily discounted via coupon -- PL124I, PL334, PL203, PL91. All 4 are driven by the SAME coupon: SAVEBIGGER20.",
  "Review/cap SAVEBIGGER20 eligibility on these 4 specific SKUs before executing their price moves -- single targeted fix, not a policy overhaul.", "Protects the Section 1 price-increase GM from being eroded by concurrent coupon stacking"],
 ["ADDFAMILY caps", "Verified working exactly as designed: 2-member=20.2% avg discount, 3-member=25.1%, 4-member=30.1% -- matches your stated 20/25/30% caps almost exactly.",
  "No action needed -- monitor only.", "N/A -- confirmed healthy"],
 ["MOV compliance", "SAVEBIG20: 20% of bookings priced below its own Rs 1,499 MOV. SAVEBIG15: 15% below its Rs 799 MOV.",
  "Flag to whoever owns cart/coupon logic for a cart-level check (package price alone isn't proof of a real breach) -- investigation item, not yet an action.", "Unconfirmed -- resolve before sizing"],
]
for row in coupon_rows:
    r = data_row(r, row)

wb.save("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/ASP_Action_Plan.xlsx")
print("Saved.")
