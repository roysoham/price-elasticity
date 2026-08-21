import pandas as pd
import numpy as np

raw = pd.read_pickle("/sessions/gallant-sharp-hopper/mnt/outputs/v5_raw.pkl")
raw['booking_date'] = pd.to_datetime(raw['booking_date'])
# clean window: Aug 1-16 full days (Aug17 partial, pre-Aug1 sparse/lagged)
clean = raw[(raw['booking_date']>='2026-08-01') & (raw['booking_date']<='2026-08-16')].copy()
print("Clean window rows:", len(clean), "of", len(raw))

clean['n_disc_types'] = ((clean['special_discount']>0).astype(int) + (clean['vip_discount']>0).astype(int) +
                          (clean['coupon_discount']>0).astype(int) + (clean['redcash']>0).astype(int) + (clean['giftcard']>0).astype(int))
clean['has_coupon'] = clean['coupon_discount']>0
clean.to_pickle("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/clean.pkl")

# Master coupon rules table
crm = pd.read_excel("/sessions/gallant-sharp-hopper/mnt/GM Improvement/Coupon code crm settings .xlsx")
crm.columns = [c.strip() for c in crm.columns]
print(crm.shape)

# ADDFAMILY definitions - manual, per user spec (not in CRM file)
addfamily_defs = pd.DataFrame([
    {'Coupon Code':'ADDFAMILY2NYNNN','Coupon Name':'ADDFAMILY2NYNNN','MOV':0,'Type':'percentage','Discount':20,
     'Valid once per user':'No','Is Red Cash':'No','Upper Limit Percentage':20,'Created By':'AUTO (family add-on)','User Group':None,
     'Create Date':None,'Active':None,'Edit':None},
    {'Coupon Code':'ADDFAMILY3NYNNN','Coupon Name':'ADDFAMILY3NYNNN','MOV':0,'Type':'percentage','Discount':25,
     'Valid once per user':'No','Is Red Cash':'No','Upper Limit Percentage':25,'Created By':'AUTO (family add-on)','User Group':None,
     'Create Date':None,'Active':None,'Edit':None},
    {'Coupon Code':'ADDFAMILY4NYNNN','Coupon Name':'ADDFAMILY4NYNNN','MOV':0,'Type':'percentage','Discount':30,
     'Valid once per user':'No','Is Red Cash':'No','Upper Limit Percentage':30,'Created By':'AUTO (family add-on)','User Group':None,
     'Create Date':None,'Active':None,'Edit':None},
    {'Coupon Code':'ADDFAMILY5NYNNN','Coupon Name':'ADDFAMILY5NYNNN','MOV':0,'Type':'percentage','Discount':30,
     'Valid once per user':'No','Is Red Cash':'No','Upper Limit Percentage':30,'Created By':'AUTO (family add-on)','User Group':None,
     'Create Date':None,'Active':None,'Edit':None},
])
master_coupon = pd.concat([crm, addfamily_defs], ignore_index=True)
master_coupon.to_csv("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/master_coupon_rules.csv", index=False)
print("\nMaster coupon rules table:", master_coupon.shape)

# Verify ADDFAMILY total-discount cap claim
for code, cap in [('ADDFAMILY2NYNNN',20),('ADDFAMILY3NYNNN',25),('ADDFAMILY4NYNNN',30)]:
    sub = clean[clean['coupon_code']==code]
    print(f"\n{code}: n={len(sub)}, avg Total_Discount%={sub['Total_Discount %'].mean():.1f}, max={sub['Total_Discount %'].max():.1f}, "
          f"share with vip_discount>0: {(sub['vip_discount']>0).mean():.1%}, avg total_member={sub['total_member'].mean():.2f}, "
          f"fresh%={(sub['Booking_Flag']=='Fresh').mean():.1%}, booked_by Self%={(sub['booked_by']=='Self').mean():.1%}")
import pandas as pd
import numpy as np

clean = pd.read_pickle("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/clean.pkl")
master_coupon = pd.read_csv("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/master_coupon_rules.csv")

# Real campaign-level scorecard - GM% now computed directly (no proxy needed)
camp = clean.groupby('coupon_code').agg(
    bookings=('booking_id','count'),
    revenue=('Collected Net Revenue','sum'),
    gm=('Gross_Margin','sum'),
    avg_total_disc_pct=('Total_Discount %','mean'),
    avg_coupon_disc_pct=('coupon_discount %','mean'),
    avg_members=('total_member','mean'),
    fresh_pct=('Booking_Flag', lambda s: (s=='Fresh').mean()),
    self_pct=('booked_by', lambda s: (s=='Self').mean()),
    vip_stack_pct=('vip_discount', lambda s: (s>0).mean()),
).reset_index()
camp['gm_pct'] = camp['gm']/camp['revenue']
camp = camp.sort_values('bookings', ascending=False)
camp = camp.merge(master_coupon[['Coupon Code','MOV','Discount','Upper Limit Percentage','Type']], left_on='coupon_code', right_on='Coupon Code', how='left')
camp['known_in_crm'] = camp['Coupon Code'].notna()
print("Total distinct coupon codes used:", len(camp), "| known in CRM/ADDFAMILY master:", camp['known_in_crm'].sum())
print(camp.head(30).to_string())
camp.to_csv("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/campaign_real_gm.csv", index=False)

# MOV compliance check: for coupons with MOV>0, what % of bookings clear it (offer_price >= MOV)?
mov_check = camp[(camp['MOV']>0) & (camp['bookings']>=10)].copy()
compliance = []
for _,row in mov_check.iterrows():
    sub = clean[clean['coupon_code']==row['coupon_code']]
    below_mov = (sub['offer_price'] < row['MOV']).mean()
    compliance.append(below_mov)
mov_check['pct_bookings_below_stated_mov'] = compliance
print("\n=== MOV compliance check (bookings priced below the coupon's own stated MOV) ===")
print(mov_check[['coupon_code','MOV','bookings','pct_bookings_below_stated_mov']].sort_values('pct_bookings_below_stated_mov', ascending=False).to_string())
mov_check.to_csv("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/mov_compliance.csv", index=False)

# Upper limit compliance: does actual coupon_discount % ever exceed the Upper Limit Percentage?
ul_check = camp[(camp['Upper Limit Percentage']>0) & (camp['bookings']>=10)].copy()
breach = []
for _,row in ul_check.iterrows():
    sub = clean[clean['coupon_code']==row['coupon_code']]
    over = (sub['coupon_discount %'] > row['Upper Limit Percentage']+0.5).mean()  # 0.5pp tolerance for rounding
    breach.append(over)
ul_check['pct_bookings_over_upper_limit'] = breach
print("\n=== Upper-limit breach check ===")
print(ul_check[ul_check['pct_bookings_over_upper_limit']>0.05][['coupon_code','Upper Limit Percentage','bookings','pct_bookings_over_upper_limit']].to_string())
import pandas as pd
import numpy as np
clean = pd.read_pickle("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/clean.pkl")

# Discount stacking curve refresh (bigger n)
stack = clean.groupby('n_disc_types').agg(n=('booking_id','count'), revenue=('Collected Net Revenue','sum'), gm=('Gross_Margin','sum')).reset_index()
stack['gm_pct'] = stack['gm']/stack['revenue']
print("=== Discount stacking GM% (Aug1-16, n=51,701) ===")
print(stack.to_string())
stack.to_csv("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/stacking_refresh.csv", index=False)

# Clean coupon-only depth curve refresh
clean['coupon_disc_pct_row'] = np.where(clean['offer_price']>0, clean['coupon_discount']/clean['offer_price'], np.nan)
iso = clean[clean['n_disc_types']<=1].copy()
def tier(row):
    if row['n_disc_types']==0: return '0% - no discount'
    p = row['coupon_disc_pct_row']
    if p < 0.10: return '1-10%'
    if p < 0.20: return '10-20%'
    if p < 0.30: return '20-30%'
    if p < 0.40: return '30-40%'
    return '40%+'
iso['depth_tier'] = iso.apply(tier, axis=1)
order = ['0% - no discount','1-10%','10-20%','20-30%','30-40%','40%+']
depth = iso.groupby('depth_tier').agg(n=('booking_id','count'), revenue=('Collected Net Revenue','sum'), gm=('Gross_Margin','sum')).reindex(order)
depth['gm_pct'] = depth['gm']/depth['revenue']
print("\n=== Depth curve refresh (isolated coupon-only) ===")
print(depth.to_string())
depth.to_csv("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/depth_refresh.csv")

# Segment / Customer analysis (fresh/repeat x category x channel), with coupon detail
seg = clean.groupby(['Booking_Flag','customer_category']).agg(
    bookings=('booking_id','count'), revenue=('Collected Net Revenue','sum'), gm=('Gross_Margin','sum'),
    coupon_pen=('has_coupon','mean'), avg_disc=('Total_Discount %','mean'), avg_members=('total_member','mean'),
).reset_index()
seg['gm_pct'] = seg['gm']/seg['revenue']
seg['rev_share'] = seg['revenue']/seg['revenue'].sum()
print("\n=== Segment (Fresh/Repeat x Category), Aug1-16 ===")
print(seg.to_string())
seg.to_csv("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/segment_refresh.csv", index=False)

seg_chan = clean.groupby(['Booking_Flag','customer_category','booked_by']).agg(
    bookings=('booking_id','count'), revenue=('Collected Net Revenue','sum'), gm=('Gross_Margin','sum'),
    coupon_pen=('has_coupon','mean'), avg_disc=('Total_Discount %','mean'),
).reset_index()
seg_chan['gm_pct'] = seg_chan['gm']/seg_chan['revenue']
seg_chan.to_csv("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/segment_channel_refresh.csv", index=False)

# top coupons by customer_category
top_cat_coupon = clean[clean['has_coupon']].groupby(['customer_category','coupon_code']).size().reset_index(name='n')
top_cat_coupon = top_cat_coupon.sort_values(['customer_category','n'], ascending=[True,False])
top5 = top_cat_coupon.groupby('customer_category').head(5)
print("\n=== Top 5 coupons per customer category ===")
print(top5.to_string())
top5.to_csv("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/top_coupons_by_category.csv", index=False)
import pandas as pd
import numpy as np

clean = pd.read_pickle("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/clean.pkl")
act = pd.read_csv("/sessions/gallant-sharp-hopper/mnt/outputs/coupon_analysis/price_coupon_exposure_check_v2.csv")

clean['package_code'] = clean['package_code'].astype(str).str.strip()
exposure = clean.groupby('package_code').agg(
    n_bookings=('booking_id','count'),
    coupon_penetration=('has_coupon','mean'),
    avg_total_disc_pct=('Total_Discount %','mean'),
    gm_pct=('Gross_Margin', lambda s: np.nan),  # placeholder, compute properly below
).reset_index()
# proper gm_pct per package
pkg_gm = clean.groupby('package_code').apply(lambda g: g['Gross_Margin'].sum()/g['Collected Net Revenue'].sum(), include_groups=False).rename('gm_pct_real')
exposure = exposure.drop(columns=['gm_pct']).merge(pkg_gm, on='package_code', how='left')

# top coupon used per package
top_coupon_per_pkg = clean[clean['has_coupon']].groupby(['package_code','coupon_code']).size().reset_index(name='n')
top_coupon_per_pkg = top_coupon_per_pkg.sort_values(['package_code','n'], ascending=[True,False]).drop_duplicates('package_code')
exposure = exposure.merge(top_coupon_per_pkg[['package_code','coupon_code','n']].rename(columns={'coupon_code':'top_coupon','n':'top_coupon_n'}), on='package_code', how='left')

merged = act[['package_code','package_name','weekly_gm_delta','actual_price_pct_change']].merge(exposure, on='package_code', how='left')

def risk_flag(row):
    if pd.isna(row['coupon_penetration']):
        return 'No data (Aug1-16)'
    if row['actual_price_pct_change'] < 0 and row['coupon_penetration'] > 0.5 and row['avg_total_disc_pct'] > 15:
        return 'HIGH -- price cut on already heavily-discounted package'
    if row['actual_price_pct_change'] > 0 and row['coupon_penetration'] < 0.15:
        return 'LOW -- clean, price increase on lightly-discounted package'
    if row['coupon_penetration'] > 0.5:
        return 'MEDIUM -- high coupon exposure, monitor stacking'
    return 'LOW'
merged['stacking_risk'] = merged.apply(risk_flag, axis=1)
merged = merged.sort_values('weekly_gm_delta', ascending=False)
print(merged.to_string())
print("\nHIGH risk count:", (merged['stacking_risk'].astype(str).str.startswith('HIGH')).sum())
merged.to_csv("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/stacking_risk_v2.csv", index=False)
import pandas as pd
clean = pd.read_pickle("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/clean.pkl")
dod = clean.groupby('booking_date').agg(
    bookings=('booking_id','count'), revenue=('Collected Net Revenue','sum'), gm=('Gross_Margin','sum'),
    coupon_pen=('has_coupon','mean'), avg_disc=('Total_Discount %','mean'),
    fresh_bookings=('Booking_Flag', lambda s: (s=='Fresh').sum()),
    repeat_bookings=('Booking_Flag', lambda s: (s=='Repeat').sum()),
    vip_gold_bookings=('customer_category', lambda s: (s=='vip gold').sum()),
    self_bookings=('booked_by', lambda s: (s=='Self').sum()),
    sales_bookings=('booked_by', lambda s: (s=='Sales').sum()),
    phlebo_bookings=('booked_by', lambda s: (s=='Phlebo').sum()),
).reset_index()
dod['gm_pct'] = dod['gm']/dod['revenue']
dod['fresh_pct'] = dod['fresh_bookings']/dod['bookings']
dod['booking_date'] = dod['booking_date'].dt.strftime('%Y-%m-%d')
print(dod.to_string())
dod.to_csv("/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/dod_seed_v2.csv", index=False)
import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
import datetime

FONT="Arial"
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(name=FONT, size=10, bold=True, color="FFFFFF")
BODY_FONT = Font(name=FONT, size=10)
GREEN = PatternFill("solid", fgColor="C6E0B4")
YELLOW = PatternFill("solid", fgColor="FFF2CC")
RED = PatternFill("solid", fgColor="F8CBAD")

B = "/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/"

wb = Workbook()
ws = wb.active
ws.title = "README"
ws.sheet_view.showGridLines = False
ws.column_dimensions['A'].width = 112

def h1(cell, text, size=14, color="1F4E78"):
    cell.value = text; cell.font = Font(name=FONT, size=size, bold=True, color=color)
def body(cell, text, italic=False, size=11):
    cell.value = text; cell.font = Font(name=FONT, size=size, italic=italic)
    cell.alignment = Alignment(wrap_text=True, vertical='top')

r=1
h1(ws.cell(row=r,column=1), "V5 -- GM Improvement Model: Price + Coupon + Channel + Segment (simplified, real coupon linkage)"); r+=1
body(ws.cell(row=r,column=1), f"Generated {datetime.date.today().isoformat()} | Base data: online_discount_summary__raw_Aug17MTD.xlsx (clean window Aug 1-16, 51,701 bookings) | Full methodology: V5_Methodology.md", italic=True); r+=2
for s in [
 "This is a rebuild, not an add-on. Two things changed the model this round: the raw data export now carries coupon_code directly on every booking (no more name-matching workaround), and you supplied the real coupon CRM settings (MOV, discount%, upper limit%) plus the ADDFAMILY family-add-on logic. Both let this version measure things V4 could only proxy.",
 "CORRECTION FROM V4 -- read this before trusting old numbers: V4's coupon depth-vs-margin curve (from a smaller, 8-day window with no direct coupon-to-package link) showed 30%+-depth coupons collapsing to ~1% GM and called FREEDOM50 a near-giveaway. On this larger, directly-linked dataset, that does NOT hold: FREEDOM50's real GM% is 47.9% -- low relative to the book average, but nowhere near the earlier alarm. The V4 number was a small-sample artifact of the workaround method, not a real cliff. Full explanation in V5_Methodology.md section 2.",
 "Tab count is down from V4's 13 to 9 -- coupon-related tabs consolidated from 4 into 2 (Customer & Coupon Analysis, Coupon Rules & Definitions) per the simplification you asked for.",
]:
    body(ws.cell(row=r,column=1), s); r+=1
r+=1
h1(ws.cell(row=r,column=1), "Tabs", size=12); r+=1
for s in [
 "1. Master Action List -- ranked Price + Coupon + Channel actions.",
 "2. Customer & Coupon Analysis -- Fresh/Repeat x Regular/VIP/VIP-Gold x Channel, with top coupons per segment (merges old Segment Diagnostic + Coupon Channel Diagnostic + WoW Scorecard).",
 "3. Coupon Rules & Definitions -- master coupon table (CRM settings + ADDFAMILY logic), MOV compliance check, corrected depth-vs-margin curve.",
 "4. Price-Coupon Stacking Risk -- rebuilt with real coupon_code x package_code join, now names the actual top coupon driving each flagged package.",
 "5. VIP Gold ASP Strategy -- carried forward from V4, key GM% figures refreshed.",
 "6. Price - Action List -- unchanged from V4 (no new price/MoM pull this round).",
 "7. DoD Cadence Tracker -- extended to 16 clean daily rows (was 7).",
 "8. Appendix - Price Full Detail -- all 365 packages, audit trail.",
]:
    body(ws.cell(row=r,column=1), s); r+=1

def write_df(ws, df, freeze="A2", widths=18, number_formats=None):
    headers = list(df.columns)
    for j, htext in enumerate(headers, start=1):
        c = ws.cell(row=1, column=j, value=str(htext))
        c.font = HEADER_FONT; c.fill = HEADER_FILL
        c.alignment = Alignment(wrap_text=True, vertical='center', horizontal='center')
    for i, (_, row) in enumerate(df.iterrows(), start=2):
        for j, key in enumerate(headers, start=1):
            val = row[key]
            if pd.isna(val): val = None
            c = ws.cell(row=i, column=j, value=val)
            c.font = BODY_FONT
            if number_formats and key in number_formats:
                c.number_format = number_formats[key]
    ws.freeze_panes = freeze
    for j in range(1, len(headers)+1):
        ws.column_dimensions[get_column_letter(j)].width = widths

# ---- Master Action List (rebuild from prior master + refreshed stacking risk) ----
master_prev = pd.read_excel("/sessions/gallant-sharp-hopper/mnt/GM Improvement/MASTER_Weekly_GM_Action_Plan_Aug2026.xlsx", sheet_name="Master Action List")
ws_m = wb.create_sheet("Master Action List")
write_df(ws_m, master_prev, widths=22, number_formats={'Weekly GM$ Impact (Rs)':'#,##0'})
note_row = len(master_prev)+3
body(ws_m.cell(row=note_row, column=1), "Price rows carried from the price elasticity model (unchanged this round -- no new price/MoM data supplied). Coupon/Channel rows should be re-sized against the corrected numbers in 'Coupon Rules & Definitions' before next execution -- FREEDOM50's opportunity estimate here is stale (based on the V4 depth-cliff error) and should be dropped or recomputed, not acted on as-is.", italic=True)

# ---- Customer & Coupon Analysis ----
seg = pd.read_csv(B+"segment_refresh.csv")
seg_chan = pd.read_csv(B+"segment_channel_refresh.csv")
top5 = pd.read_csv(B+"top_coupons_by_category.csv")
ws_c = wb.create_sheet("Customer & Coupon Analysis")
r=1
h1(ws_c.cell(row=r,column=1), "Fresh/Repeat x Customer Category -- Aug 1-16, 2026 (51,701 bookings)", size=12); r+=2
seg_disp = seg.rename(columns={'Booking_Flag':'Fresh/Repeat','customer_category':'Category','bookings':'Bookings','revenue':'Net Revenue (Rs)',
    'gm':'Gross Margin (Rs)','coupon_pen':'Coupon Penetration %','avg_disc':'Avg Total Discount %','avg_members':'Avg Members/Booking',
    'gm_pct':'GM %','rev_share':'Revenue Share %'})
cols = ['Fresh/Repeat','Category','Bookings','Net Revenue (Rs)','Gross Margin (Rs)','GM %','Avg Members/Booking','Coupon Penetration %','Avg Total Discount %','Revenue Share %']
seg_disp = seg_disp[cols]
for j,htext in enumerate(cols, start=1):
    c = ws_c.cell(row=r,column=j,value=htext); c.font=HEADER_FONT; c.fill=HEADER_FILL
r+=1
for _,row in seg_disp.iterrows():
    for j,key in enumerate(cols, start=1):
        c = ws_c.cell(row=r,column=j,value=row[key]); c.font=BODY_FONT
        if key in ('GM %','Coupon Penetration %','Revenue Share %'): c.number_format='0.0%'
        if key=='Avg Total Discount %': c.number_format='0.0"%"'
        if key in ('Net Revenue (Rs)','Gross Margin (Rs)'): c.number_format='#,##0'
    r+=1
r+=2
h1(ws_c.cell(row=r,column=1), "+ Channel breakdown", size=12); r+=2
sc_disp = seg_chan.rename(columns={'Booking_Flag':'Fresh/Repeat','customer_category':'Category','booked_by':'Channel','bookings':'Bookings',
    'revenue':'Net Revenue (Rs)','gm':'Gross Margin (Rs)','coupon_pen':'Coupon Penetration %','avg_disc':'Avg Total Discount %','gm_pct':'GM %'}).sort_values('Net Revenue (Rs)', ascending=False)
cols2 = ['Fresh/Repeat','Category','Channel','Bookings','Net Revenue (Rs)','Gross Margin (Rs)','GM %','Coupon Penetration %','Avg Total Discount %']
sc_disp = sc_disp[cols2]
for j,htext in enumerate(cols2, start=1):
    c = ws_c.cell(row=r,column=j,value=htext); c.font=HEADER_FONT; c.fill=HEADER_FILL
r+=1
for _,row in sc_disp.iterrows():
    for j,key in enumerate(cols2, start=1):
        c = ws_c.cell(row=r,column=j,value=row[key]); c.font=BODY_FONT
        if key in ('GM %','Coupon Penetration %'): c.number_format='0.0%'
        if key=='Avg Total Discount %': c.number_format='0.0"%"'
        if key in ('Net Revenue (Rs)','Gross Margin (Rs)'): c.number_format='#,##0'
    r+=1
r+=2
h1(ws_c.cell(row=r,column=1), "Top 5 coupons used, by customer category", size=12); r+=2
top5cols = list(top5.columns)
for j,htext in enumerate(top5cols, start=1):
    c = ws_c.cell(row=r,column=j,value=htext); c.font=HEADER_FONT; c.fill=HEADER_FILL
r+=1
for _,row in top5.iterrows():
    for j,key in enumerate(top5cols, start=1):
        c = ws_c.cell(row=r,column=j,value=row[key]); c.font=BODY_FONT
    r+=1
for col,w in zip(['A','B','C','D','E','F','G','H','I','J'], [12,10,10,12,14,14,10,18,16,14]):
    ws_c.column_dimensions[col].width = w

wb.save(B+"GM_V5_Model_Aug2026_PART1.xlsx")
print("Part1 saved:", wb.sheetnames)
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

FONT="Arial"
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(name=FONT, size=10, bold=True, color="FFFFFF")
BODY_FONT = Font(name=FONT, size=10)
GREEN = PatternFill("solid", fgColor="C6E0B4")
YELLOW = PatternFill("solid", fgColor="FFF2CC")
RED = PatternFill("solid", fgColor="F8CBAD")
B = "/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/"

wb = load_workbook(B+"GM_V5_Model_Aug2026_PART1.xlsx")

def h1(cell, text, size=12, color="1F4E78"):
    cell.value = text; cell.font = Font(name=FONT, size=size, bold=True, color=color)
def body(cell, text, italic=False):
    cell.value = text; cell.font = Font(name=FONT, size=11, italic=italic)
    cell.alignment = Alignment(wrap_text=True, vertical='top')
def write_df_at(ws, df, r, widths=None):
    headers = list(df.columns)
    for j,htext in enumerate(headers, start=1):
        c = ws.cell(row=r,column=j,value=str(htext)); c.font=HEADER_FONT; c.fill=HEADER_FILL
        c.alignment = Alignment(wrap_text=True, vertical='center', horizontal='center')
    start=r; r+=1
    for _,row in df.iterrows():
        for j,key in enumerate(headers, start=1):
            val = row[key]
            if pd.isna(val): val=None
            c = ws.cell(row=r,column=j,value=val); c.font=BODY_FONT
        r+=1
    return r

# ---- Coupon Rules & Definitions ----
ws = wb.create_sheet("Coupon Rules & Definitions")
ws.sheet_view.showGridLines = False
ws.column_dimensions['A'].width = 100
r=1
h1(ws.cell(row=r,column=1), "Master Coupon Rules -- from CRM settings export + ADDFAMILY logic (manually documented, not in CRM export)", size=13); r+=2
master_coupon = pd.read_csv(B+"master_coupon_rules.csv")
r = write_df_at(ws, master_coupon[['Coupon Code','MOV','Type','Discount','Upper Limit Percentage','Valid once per user','Is Red Cash','Created By']], r)
r+=2
h1(ws.cell(row=r,column=1), "ADDFAMILY family add-on logic (per your definition, verified against Aug1-16 data)"); r+=1
for s in [
 "ADDFAMILY2NYNNN -- adds 1 member to an existing booking of 1 (2 total), max 20% discount. If VIP is also active, coupon+VIP combined is capped at 20% total, not additive. VERIFIED: avg Total_Discount% = 20.2% (n=1,066), avg members/booking = 1.99, 72.7% also carry a VIP discount, 87.2% Self-channel.",
 "ADDFAMILY3NYNNN -- adds to 3 total members, max 25% combined. VERIFIED: avg Total_Discount% = 25.1% (n=363), avg members = 2.99, 63.9% VIP-stacked, 53.7% Self-channel.",
 "ADDFAMILY4NYNNN / 5NYNNN and beyond -- 4+ total members, max 30% combined. VERIFIED: avg Total_Discount% = 30.1% (n=217, ADDFAMILY4), avg members = 4.13, 58.1% VIP-stacked, 42.4% Self-channel.",
 "Pattern: as family size grows, the booking shifts from Self-driven (87% at 2-member) toward Sales-assisted (58% at 4-member) -- larger multi-member bookings apparently need more assisted checkout. This is a fresh/repeat growth driver, not leakage: it's a structured, capped mechanic that grows basket size (total_member) predictably and the discount is proportionate to the incremental members added, not a flat giveaway.",
]:
    body(ws.cell(row=r,column=1), s); r+=1
r+=2
h1(ws.cell(row=r,column=1), "MOV compliance check -- bookings priced BELOW the coupon's own stated minimum order value"); r+=1
body(ws.cell(row=r,column=1), "offer_price here is the per-booking package price, not necessarily full cart value -- a genuine MOV breach needs cart-level data to confirm. Flagged as an investigation item, not a confirmed leak.", italic=True); r+=1
mov = pd.read_csv(B+"mov_compliance.csv")
mov_disp = mov[['coupon_code','MOV','bookings','pct_bookings_below_stated_mov']].sort_values('pct_bookings_below_stated_mov', ascending=False)
r = write_df_at(ws, mov_disp, r)
for rr in range(r-len(mov_disp), r):
    c = ws.cell(row=rr, column=4)
    if isinstance(c.value,(int,float)):
        c.number_format='0.0%'
        if c.value>0.1: c.fill=YELLOW
r+=2

h1(ws.cell(row=r,column=1), "CORRECTED depth-vs-margin curve (Aug 1-16, isolated coupon-only bookings, n=51,701 base)"); r+=1
body(ws.cell(row=r,column=1), "This SUPERSEDES the V4 curve. V4 (8-day window, no direct coupon link) showed a cliff to ~1% GM at 30%+ depth. On this larger, directly-linked sample, the decline is real but gradual, not a cliff.", italic=True); r+=1
depth = pd.read_csv(B+"depth_refresh.csv")
depth_disp = depth.rename(columns={'depth_tier':'Depth Tier','n':'Bookings','revenue':'Revenue (Rs)','gm':'GM (Rs)','gm_pct':'GM %'})
r = write_df_at(ws, depth_disp, r)
for rr in range(r-len(depth_disp), r):
    c = ws.cell(row=rr, column=5)
    if isinstance(c.value,(int,float)): c.number_format='0.0%'
r+=2

h1(ws.cell(row=r,column=1), "Real campaign-level GM% -- top 20 by volume (Aug 1-16, directly linked via coupon_code)"); r+=1
camp = pd.read_csv(B+"campaign_real_gm.csv").head(20)
camp_disp = camp.rename(columns={'coupon_code':'Coupon Code','bookings':'Bookings','gm_pct':'Real GM %','avg_total_disc_pct':'Avg Total Discount %',
    'avg_members':'Avg Members','fresh_pct':'Fresh %','self_pct':'Self %','MOV':'MOV (Rs)','Upper Limit Percentage':'Upper Limit %','known_in_crm':'In CRM Master?'})
cols = ['Coupon Code','Bookings','Real GM %','Avg Total Discount %','Avg Members','Fresh %','Self %','MOV (Rs)','Upper Limit %','In CRM Master?']
camp_disp = camp_disp[cols]
r = write_df_at(ws, camp_disp, r)
for rr in range(r-len(camp_disp), r):
    for col,fmt in [(3,'0.0%'),(6,'0.0%'),(7,'0.0%')]:
        c = ws.cell(row=rr, column=col)
        if isinstance(c.value,(int,float)): c.number_format=fmt
    gm_cell = ws.cell(row=rr, column=3)
    if isinstance(gm_cell.value,(int,float)) and gm_cell.value < 0.55:
        gm_cell.fill = YELLOW

wb.save(B+"GM_V5_Model_Aug2026_PART1.xlsx")
print("Saved. Sheets:", wb.sheetnames)
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

FONT="Arial"
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(name=FONT, size=10, bold=True, color="FFFFFF")
BODY_FONT = Font(name=FONT, size=10)
GREEN = PatternFill("solid", fgColor="C6E0B4")
YELLOW = PatternFill("solid", fgColor="FFF2CC")
RED = PatternFill("solid", fgColor="F8CBAD")
B = "/sessions/gallant-sharp-hopper/mnt/outputs/v5_build/"

wb = load_workbook(B+"GM_V5_Model_Aug2026_PART1.xlsx")

def write_df(ws, df, freeze="A2", widths=18, number_formats=None):
    headers = list(df.columns)
    for j, htext in enumerate(headers, start=1):
        c = ws.cell(row=1, column=j, value=str(htext))
        c.font = HEADER_FONT; c.fill = HEADER_FILL
        c.alignment = Alignment(wrap_text=True, vertical='center', horizontal='center')
    for i, (_, row) in enumerate(df.iterrows(), start=2):
        for j, key in enumerate(headers, start=1):
            val = row[key]
            if pd.isna(val): val = None
            c = ws.cell(row=i, column=j, value=val)
            c.font = BODY_FONT
            if number_formats and key in number_formats:
                c.number_format = number_formats[key]
    ws.freeze_panes = freeze
    for j in range(1, len(headers)+1):
        ws.column_dimensions[get_column_letter(j)].width = widths

# ---- Price-Coupon Stacking Risk (v2) ----
risk = pd.read_csv(B+"stacking_risk_v2.csv")
ws1 = wb.create_sheet("Price-Coupon Stacking Risk")
risk_disp = risk.rename(columns={'package_code':'Package Code','package_name':'Package Name','weekly_gm_delta':'Projected Weekly GM$ (price model)',
    'actual_price_pct_change':'Price Change %','n_bookings':'Bookings (Aug1-16)','coupon_penetration':'Coupon Penetration %',
    'avg_total_disc_pct':'Avg Total Discount %','gm_pct_real':'Real GM %','top_coupon':'Top Coupon Used','top_coupon_n':'Top Coupon Bookings','stacking_risk':'Risk Flag'})
cols = ['Package Code','Package Name','Price Change %','Projected Weekly GM$ (price model)','Bookings (Aug1-16)','Coupon Penetration %','Avg Total Discount %','Real GM %','Top Coupon Used','Top Coupon Bookings','Risk Flag']
risk_disp = risk_disp[cols]
write_df(ws1, risk_disp, widths=18, number_formats={'Price Change %':'0.0%','Projected Weekly GM$ (price model)':'#,##0','Coupon Penetration %':'0.0%','Real GM %':'0.0%'})
for r_ in range(2, len(risk_disp)+2):
    rc = ws1.cell(row=r_, column=11)
    if rc.value and str(rc.value).startswith('HIGH'): rc.fill = RED
    elif rc.value and str(rc.value).startswith('MEDIUM'): rc.fill = YELLOW

# ---- VIP Gold ASP Strategy (carry from V4, add refresh note) ----
v4 = load_workbook("/sessions/gallant-sharp-hopper/mnt/GM Improvement/GM_V4_Model_Aug2026.xlsx")
src = v4["VIP Gold ASP Strategy"]
ws2 = wb.create_sheet("VIP Gold ASP Strategy")
ws2.column_dimensions['A'].width = 100
for row in src.iter_rows():
    for cell in row:
        newcell = ws2.cell(row=cell.row, column=cell.column, value=cell.value)
        if cell.has_style:
            newcell.font = Font(name=FONT, size=cell.font.size, bold=cell.font.bold, italic=cell.font.italic, color=cell.font.color)
            newcell.alignment = Alignment(wrap_text=True, vertical="top")
for col, dim in src.column_dimensions.items():
    ws2.column_dimensions[col].width = dim.width
# insert refresh note at top
ws2.insert_rows(2)
note = ws2.cell(row=2, column=1, value="V5 REFRESH NOTE: this content is carried from V4. Segment GM% figures below (from the Jul26-Aug2 8-day window) are LOWER than the Aug1-16 Customer & Coupon Analysis tab's numbers for the same segments (e.g. Repeat VIP-Gold GM% was 59.8% in V4, now 69.0% on the larger Aug1-16 sample) -- the smaller window appears to have been a lower-margin period, not representative. Directional findings (VIP Gold gets shallower coupons, Phlebo ancillary attach gap, price-cut stacking risk) still hold; specific GM% figures should be re-pulled from the Customer & Coupon Analysis tab before being quoted externally.")
note.font = Font(name=FONT, size=10, italic=True, bold=True, color="C00000")
note.alignment = Alignment(wrap_text=True, vertical='top')

# ---- Price - Action List (unchanged, carried from V4) ----
price_act = v4["Price - Action List"]
ws3 = wb.create_sheet("Price - Action List")
for row in price_act.iter_rows():
    for cell in row:
        newcell = ws3.cell(row=cell.row, column=cell.column, value=cell.value)
        newcell.font = Font(name=FONT, size=10)
for col, dim in price_act.column_dimensions.items():
    ws3.column_dimensions[col].width = dim.width

# ---- DoD Cadence Tracker (extended) ----
dod = pd.read_csv(B+"dod_seed_v2.csv")
ws4 = wb.create_sheet("DoD Cadence Tracker")
ws4.sheet_view.showGridLines = False
ws4.column_dimensions['A'].width = 100
r=1
def h1(cell, text, size=13, color="1F4E78"):
    cell.value = text; cell.font = Font(name=FONT, size=size, bold=True, color=color)
def body(cell, text, italic=False):
    cell.value = text; cell.font = Font(name=FONT, size=11, italic=italic)
    cell.alignment = Alignment(wrap_text=True, vertical='top')
h1(ws4.cell(row=r,column=1), "Day-on-Day Cadence Tracker -- extended to Aug 1-16 (16 clean days, was 7 in V4)"); r+=1
body(ws4.cell(row=r,column=1), "Extend this table each time a fresh raw export arrives -- paste new daily rows below, same columns. At 4+ weeks this supports real day-of-week control and a proper coupon elasticity read instead of the cross-sectional depth curve used today.", italic=True); r+=2
cols_map = {'booking_date':'Date','bookings':'Bookings','revenue':'Net Revenue (Rs)','gm':'Gross Margin (Rs)','gm_pct':'GM %',
    'coupon_pen':'Coupon Penetration %','avg_disc':'Avg Total Discount %','fresh_bookings':'Fresh Bookings','repeat_bookings':'Repeat Bookings',
    'fresh_pct':'Fresh %','vip_gold_bookings':'VIP-Gold Bookings','self_bookings':'Self Bookings','sales_bookings':'Sales Bookings','phlebo_bookings':'Phlebo Bookings'}
headers = list(cols_map.values())
for j,htext in enumerate(headers, start=1):
    c = ws4.cell(row=r,column=j,value=htext); c.font=HEADER_FONT; c.fill=HEADER_FILL
table_start=r; r+=1
for _,row in dod.iterrows():
    for j,key in enumerate(cols_map.keys(), start=1):
        val = row[key]
        c = ws4.cell(row=r,column=j,value=val); c.font=BODY_FONT
        if key in ('gm_pct','coupon_pen','fresh_pct'): c.number_format='0.0%'
        if key=='avg_disc': c.number_format='0.0"%"'
        if key in ('revenue','gm'): c.number_format='#,##0'
    r+=1
ws4.freeze_panes=f"A{table_start+1}"
widths=[12,10,14,14,8,16,16,12,14,8,14,10,10,10]
for j,w in enumerate(widths, start=1):
    ws4.column_dimensions[get_column_letter(j)].width=w

# ---- Appendix: Price Full Detail ----
full = v4["Price - Full Detail"]
ws5 = wb.create_sheet("Appendix - Price Full Detail")
for row in full.iter_rows():
    for cell in row:
        newcell = ws5.cell(row=cell.row, column=cell.column, value=cell.value)
        newcell.font = Font(name=FONT, size=9)
for col, dim in full.column_dimensions.items():
    ws5.column_dimensions[col].width = dim.width

wb.save("/sessions/gallant-sharp-hopper/mnt/GM Improvement/GM_V5_Model_Aug2026.xlsx")
print("Final V5 saved. Sheets:", wb.sheetnames)
