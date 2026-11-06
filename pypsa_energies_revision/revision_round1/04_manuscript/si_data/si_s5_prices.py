"""SI S5: annual statistics of the Tohoku price series and regional curtailment rate as seen by the F6 model.

Reads (read-only):
  27_PyPSA_rebuild_20261016/inputs/tohoku_price_plan_ref2024.parquet   (year, ts) -> price [JPY/kWh], curtail_rate
       (identical to revision_round1/03_analysis/price_model/future_prices.parquet, built by build_future_prices.py)
  27_PyPSA_rebuild_20261016/inputs/profiles.parquet                   model snapshots 2025-2050 (index only)
  revision_round1/03_analysis/price_model/future_prices_summary.csv     generator's own summary (reference-year hours, 8,784 per year)
  revision_round1/03_analysis/tohoku_penetration_beta.csv               plan portfolio (scenario = plan)
Mapping as in model.py (--price-series): key (min(year, 2050), month, day, hour); non-leap model years skip 29 February of the
2024 reference year, so model-year statistics use 8,760 h (8,784 h in leap years).
Writes:
  si_data/si_s5_price_by_year.csv   per model year: plan portfolio, mean price, time-weighted p10/p50/p90, floor hours, hours < 5 JPY/kWh,
                                    hours with curtail_rate > 0, hours with curtail_rate > 0 off the floor, max curtail_rate, hourly-mean
                                    curtail_rate, VRE-weighted curtailment share (generator summary), extra export (generator summary)
Usage: python si_s5_prices.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RR = HERE.parents[1]
ROOT = RR.parent / '27_PyPSA_rebuild_20261016'
FLOOR = 0.01

ps = pd.read_parquet(ROOT / 'inputs' / 'tohoku_price_plan_ref2024.parquet')
gen = pd.read_parquet(RR / '03_analysis' / 'price_model' / 'future_prices.parquet')
same = float((gen[['price', 'curtail_rate']] - ps).abs().max().max())
snap = pd.read_parquet(ROOT / 'inputs' / 'profiles.parquet').index
pm = {(y, t.month, t.day, t.hour): (p, c) for (y, t), p, c in zip(ps.index, ps['price'].values, ps['curtail_rate'].values)}
vals = np.array([pm[(min(t.year, 2050), t.month, t.day, t.hour)] for t in snap])
m = pd.DataFrame({'price': vals[:, 0], 'curt': vals[:, 1]}, index=snap)

rows = []
for y, d in m.groupby(m.index.year):
    p, c = d.price, d.curt
    fl = p <= FLOOR + 1e-9
    rows.append(dict(year=y, hours=len(d), mean_price=p.mean(), p10=p.quantile(.1), p50=p.median(), p90=p.quantile(.9), max_price=p.max(),
                     floor_hours=int(fl.sum()), hours_below5=int((p < 5).sum()), curt_hours=int((c > 0).sum()),
                     curt_hours_off_floor=int(((c > 0) & ~fl).sum()), floor_hours_without_curt=int((fl & (c <= 0)).sum()),
                     max_curt_rate=c.max(), mean_curt_rate_hourly=c.mean()))
t = pd.DataFrame(rows).set_index('year')
summ = pd.read_csv(RR / '03_analysis' / 'price_model' / 'future_prices_summary.csv').set_index('year')
t = t.join(summ[['mean_price', 'hours_floor', 'curtail_pct_of_VRE', 'extra_export_TWh', 'wind_VF', 'solar_VF']].add_prefix('ref8784_'))
cap = pd.read_csv(RR / '03_analysis' / 'tohoku_penetration_beta.csv').query("scenario == 'plan'").set_index('year')
t = cap[['pv_GW', 'onshore_GW', 'offshore_GW', 'demand_TWh']].join(t, how='right')
t.round(4).to_csv(HERE / 'si_s5_price_by_year.csv')

# supply-curve facts, recomputed exactly as in build_future_prices.py L31-42 (read-only)
d = pd.read_parquet(RR / '03_analysis' / 'price_model' / 'data' / 'processed' / 'hourly_tohoku_tokyo.parquet')
OTHER = ['tohoku_hydro', 'tohoku_geothermal', 'tohoku_biomass', 'tohoku_pumped', 'tohoku_battery']
d['export'] = -d['tohoku_interconnector']
d['tn'] = d.tohoku_demand + d.export - d.tohoku_solar - d.tohoku_wind - d[OTHER].sum(axis=1) - d.tohoku_nuclear
f = d[(d.fy >= 2023) & d.tohoku_demand.notna()]
b = (f.tn / 250).round(); cv = f.groupby(b).price_tohoku.median(); cv = cv[f.groupby(b).size() >= 20]
r24 = d.loc['2024']
facts = {'fit_hours_FY2023_2025': len(f), 'curve_bins': len(cv), 'curve_tn_min_MW': cv.index.min() * 250, 'curve_tn_max_MW': cv.index.max() * 250,
         'curve_price_min': cv.min(), 'curve_price_max': cv.max(), 'T_MIN_MW': f.tohoku_thermal.quantile(0.001),
         'net_export_2024_TWh': r24.export.sum() / 1e6, 'other_fixed_2024_TWh': r24[OTHER].sum(axis=1).sum() / 1e6,
         'demand_2024_TWh': r24.tohoku_demand.sum() / 1e6}
pd.Series(facts).round(4).to_csv(HERE / 'si_s5_price_model_facts.csv', header=['value'])

pd.set_option('display.width', 250)
print(pd.Series(facts).round(3).to_string())
print(f'model-input parquet == generator parquet: max abs diff {same}')
print(t.loc[[2025, 2028, 2030, 2035, 2040, 2045, 2050]].round(3).T.to_string())
print('all years: curt>0 hours off floor =', int(t.curt_hours_off_floor.sum()), '; global min price =', m.price.min(),
      '; floor hours without curtailment =', int(t.floor_hours_without_curt.sum()), '; max curt rate =', round(m.curt.max(), 4),
      '; min export p_max_pu =', round(1 - m.curt.max(), 4))
