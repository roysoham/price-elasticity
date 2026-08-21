import pandas as pd
import numpy as np

SRC = "online_discount_summary__raw_Aug17MTD.xlsx"
OUT_DIR = "/sessions/gallant-sharp-hopper/mnt/outputs/gsheet_build"
import os
os.makedirs(OUT_DIR, exist_ok=True)

df = pd.read_excel(SRC)
clean = df[(df['booking_date'] >= '2026-08-01') & (df['booking_date'] <= '2026-08-16')].copy()

# week start (Mon)
clean['week_start'] = (clean['booking_date'] - pd.to_timedelta(clean['booking_date'].dt.weekday, unit='D')).dt.strftime('%Y-%m-%d')

TOP_PKG = clean['package_code'].value_counts().head(80).index.tolist()
TOP_CITY = clean['city'].value_counts().head(15).index.tolist()
TOP_COUPON = clean['coupon_code'].value_counts().head(30).index.tolist()

clean['package_bucket'] = np.where(clean['package_code'].isin(TOP_PKG), clean['package_code'], 'OTHER')
clean['city_bucket'] = np.where(clean['city'].isin(TOP_CITY), clean['city'], 'OTHER')
clean['coupon_bucket'] = clean['coupon_code'].where(clean['coupon_code'].isin(TOP_COUPON), 'OTHER')
clean['coupon_bucket'] = clean['coupon_bucket'].fillna('NONE')

# 1. Booking_Summary: weekly x package x city x category x fresh/repeat
bs = clean.groupby(['week_start','package_bucket','city_bucket','customer_category','Booking_Flag'], dropna=False).agg(
    bookings=('booking_id','count'),
    gm_sum=('Gross_Margin','sum'),
    revenue_sum=('Collected Net Revenue','sum'),
    cpt_sum=('cpt','sum'),
    offer_price_sum=('offer_price','sum'),
    total_discount_pct_avg=('Total_Discount %','mean'),
).reset_index()
bs['gm_pct'] = (bs['gm_sum'] / bs['revenue_sum'].replace(0,np.nan) * 100).round(1)
bs['asp'] = (bs['offer_price_sum'] / bs['bookings']).round(0)
bs = bs.round({'gm_sum':0,'revenue_sum':0,'cpt_sum':0,'total_discount_pct_avg':1})
bs.to_csv(f"{OUT_DIR}/Booking_Summary.csv", index=False)
print("Booking_Summary rows:", len(bs))

# 2. Coupon_Summary: weekly x coupon
cs = clean.groupby(['week_start','coupon_bucket'], dropna=False).agg(
    bookings=('booking_id','count'),
    gm_sum=('Gross_Margin','sum'),
    revenue_sum=('Collected Net Revenue','sum'),
    repeat_bookings=('Booking_Flag', lambda s: (s=='Repeat').sum()),
    avg_discount_pct=('coupon_discount %','mean'),
).reset_index()
cs['gm_pct'] = (cs['gm_sum'] / cs['revenue_sum'].replace(0,np.nan) * 100).round(1)
cs['repeat_share'] = (cs['repeat_bookings'] / cs['bookings'] * 100).round(1)
cs = cs.round({'gm_sum':0,'revenue_sum':0,'avg_discount_pct':1})
cs.to_csv(f"{OUT_DIR}/Coupon_Summary.csv", index=False)
print("Coupon_Summary rows:", len(cs))

print(bs.head(3).to_string())
print(cs.head(3).to_string())
