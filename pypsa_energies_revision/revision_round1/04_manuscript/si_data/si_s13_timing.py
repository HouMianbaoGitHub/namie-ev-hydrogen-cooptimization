"""SI S13: explanation of the hydrogen build timing (F6, truncation 2050 and 2060). Descriptive only.

Reads (read-only):
  27_PyPSA_rebuild_20261016/results/f6_20261030/F6__<case>/installed_units.csv, F6t2060__<case>/installed_units.csv
  27_PyPSA_rebuild_20261016/results/f6_20261030/F6__S2/summary.json   (command = default_D2_args.txt + batch flags)
  27_PyPSA_rebuild_20261016/results/f6_20261030/F6__S1/grid_conditions_by_year.csv (price, regional curtailment, wind value factor)
  27_PyPSA_rebuild_20261016/results/f6_20261030/postprocess/energy_balance_by_year.csv (S1 curtailment, hours at export limit)
  27_PyPSA_rebuild_20261016/inputs/tohoku_price_plan_ref2024.parquet (hourly price, percentiles)
  27_PyPSA_rebuild_20261016/src/model.py  (imported only for h2_unit_annual_cost and tech_life; nothing is solved)
Writes:
  si_data/si_s13_cumulative.csv   in-service electrolyzer (kg/h), fuel cell (MW), tank (t) by year 2040-2050, S2/AH/BH/CH,
                                  both truncations, and share of the 2050 value
  si_data/si_s13_unit_cost.csv    for build years 2030-2050: capital cost, life, level annual cost per unit (capital recovery
                                  incl. in-life stack replacement + FO&M) and the one-year-earlier threshold under
                                  truncation at 2050 and 2060 for a reference hydrogen set
  si_data/si_s13_conditions.csv   price and surplus indicators by year (S1)
Reference hydrogen set (per 1,000 kg/h of electrolysis, i.e. 100 blocks): fuel cell and tank in the S2 2050 proportions.
Threshold for building in year v rather than v+1 (both kept to the truncation year E, level annuities A_v, discount
factor d_t = 1.03^-(t-2024)):  m_v = [A_v * sum_{t=v}^{E} d_t - A_{v+1} * sum_{t=v+1}^{E} d_t] / d_v
          = A_v + (A_v - A_{v+1}) * sum_{t=v+1}^{E} d_t / d_v,
i.e. the annual cost plus a lock-in premium for the higher annuity of the earlier vintage.
Usage: python si_s13_timing.py
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] / '27_PyPSA_rebuild_20261016'
RES = ROOT / 'results' / 'f6_20261030'
sys.path.insert(0, str(ROOT / 'src'))
import model as M  # noqa: E402

UNIT = {'electrolyzer': 10., 'fuelcell': 10., 'tank': 1.}   # kg/h, MW, t per unit

# 1. cumulative in-service hydrogen capacity
rows = []
for batch in ('F6', 'F6t2060'):
    for c in ('S2', 'AH', 'BH', 'CH'):
        u = pd.read_csv(RES / f'{batch}__{c}' / 'installed_units.csv', index_col=0)
        for y in range(2040, 2051):
            r = {'batch': batch, 'case': c, 'year': y}
            for k in UNIT:
                r[k] = u.at[y, k] * UNIT[k]
                r[k + '_share_of_2050'] = u.at[y, k] / u.at[2050, k] if u.at[2050, k] > 0 else np.nan
            rows.append(r)
cum = pd.DataFrame(rows)
cum.to_csv(HERE / 'si_s13_cumulative.csv', index=False)

# 2. unit costs and one-year-earlier threshold
s = json.loads((RES / 'F6__S2' / 'summary.json').read_text())
args = SimpleNamespace(**s['command'])
u50 = pd.read_csv(RES / 'F6__S2' / 'installed_units.csv', index_col=0).loc[2050]
per_set = {'electrolyzer': 100., 'fuelcell': 100. * u50.fuelcell / u50.electrolyzer, 'tank': 100. * u50.tank / u50.electrolyzer}
d = lambda t: 1.03 ** -(t - 2024)
A = {}
rows = []
for y in range(2030, 2061):
    r = {'year': y}
    tot = 0.
    for k in UNIT:
        a = M.h2_unit_annual_cost(k, y, args)
        L = M.tech_life(k, args, y)
        cap = M._interp(M.parse_path(getattr(args, 'capex_' + k)), y)
        r[k + '_capex_input'] = cap          # electrolyzer: thousand JPY per 10 kg/h block; fuel cell: thousand JPY/kW; tank: thousand JPY/t
        r[k + '_life'] = L
        r[k + '_annual_cost_MJPY_per_unit'] = a / 1e6
        tot += a * per_set[k]
    r['set_annual_cost_MJPY'] = tot / 1e6
    A[y] = tot
    rows.append(r)
uc = pd.DataFrame(rows).set_index('year')
for E in (2050, 2060):
    th = {}
    for v in range(2030, E):
        later = sum(d(t) for t in range(v + 1, E + 1))
        th[v] = (A[v] * sum(d(t) for t in range(v, E + 1)) - A[v + 1] * later) / d(v) / 1e6
    uc[f'threshold_trunc{E}_MJPY'] = pd.Series(th)
    uc[f'premium_trunc{E}_MJPY'] = uc[f'threshold_trunc{E}_MJPY'] - uc['set_annual_cost_MJPY']
uc = uc.loc[2030:2050]
uc.attrs['set'] = per_set
uc.to_csv(HERE / 'si_s13_unit_cost.csv')

# 3. conditions by year (S1)
gc = pd.read_csv(RES / 'F6__S1' / 'grid_conditions_by_year.csv', index_col=0)
eb = pd.read_csv(RES / 'postprocess' / 'energy_balance_by_year.csv')
eb = eb[eb.case == 'S1'].set_index('year')
iu = pd.read_csv(RES / 'F6__S1' / 'installed_units.csv', index_col=0)
p = pd.read_parquet(ROOT / 'inputs' / 'tohoku_price_plan_ref2024.parquet')['price']
pq = p.groupby(level=0).quantile([.1, .9]).unstack()
cond = pd.DataFrame({
    'price_mean_JPYkWh': gc.mean_price / 1000,
    'price_p10_JPYkWh': pq[.1], 'price_p90_JPYkWh': pq[.9],
    'price_floor_hour_share': (p <= p.min() + 1e-6).groupby(level=0).mean(),
    'regional_curtail_share': gc.curtail_share, 'wind_value_factor_S1': gc.wind_value_factor,
    'S1_new_wind_MW': iu.wind * 40., 'S1_vre_curtail_rate': eb.vre_curtail_rate,
    'S1_net_export_at_limit_hours': eb.net_export_at_limit_hours})
cond.index.name = 'year'
cond.to_csv(HERE / 'si_s13_conditions.csv')

pd.set_option('display.width', 250); pd.set_option('display.max_columns', 40)
print(cum[cum.year.isin([2041, 2043, 2045, 2047, 2050])].round(3).to_string())
print('set per 1000 kg/h:', per_set)
print(uc.round(3).to_string())
print(cond.round(3).to_string())
