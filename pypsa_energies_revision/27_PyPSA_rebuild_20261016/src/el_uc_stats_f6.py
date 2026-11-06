"""Electrolyzer commitment statistics of the F6 default (SI-S8): equivalent full cold starts and hot-standby hours.
From summary.json h2_uc (model.py: started MW and standby MW summed/averaged over all hourly snapshots 2025-2050, link-input
basis) and the 2050 electrolyzer link capacity (kg/h x linear kWh/kg x availability, as model.py electrolyzer_year_capacity).
Equivalent full starts = started MW / 2050 capacity; per operating year divides by the years from the first hydrogen build
to the last model year. The 2050 capacity is the largest in the path, so the per-year figures are lower bounds on per-MW cycling.
Usage: python el_uc_stats_f6.py -> results/f6_20261030/postprocess/el_uc_stats.csv"""
import json
from pathlib import Path

import pandas as pd

import model as M

D = Path(__file__).resolve().parents[1] / 'results' / 'f6_20261030'
rows = []
for b in ('F6', 'F6t2060'):
    for c in ('S2', 'AH', 'BH', 'CH'):
        d = D / f'{b}__{c}'
        s = json.loads((d / 'summary.json').read_text())
        cmd, uc = s['command'], s['h2_uc']
        u = pd.read_csv(d / 'installed_units.csv', index_col=0)
        ael = M._interp(M.parse_path(cmd['el_sec_path']), 2050) / 1000 / M.EL_FL_RATIO
        cap = u.at[2050, 'electrolyzer'] * 10 * ael * cmd['el_availability']
        first = int(u.index[u['electrolyzer'] > 1e-6][0])
        hours = len(pd.read_parquet(d / 'link_input.parquet', columns=['electrolyzer']))
        yrs = int(u.index.max()) - first + 1
        starts = uc['electrolyzer_started_MW_total'] / cap
        standby_h = uc['electrolyzer_mean_standby_MW'] * hours / cap
        rows.append({'batch': b, 'case': c, 'el_link_MW_2050': cap, 'first_build': first, 'operating_years': yrs,
                     'started_MW_total': uc['electrolyzer_started_MW_total'], 'equiv_full_starts_total': starts,
                     'equiv_full_starts_per_yr': starts / yrs, 'standby_equiv_full_h_total': standby_h,
                     'standby_equiv_full_h_per_yr': standby_h / yrs,
                     'mean_committed_MW_2025_2050': uc['electrolyzer_mean_committed_MW'],
                     'startup_cost_bn_JPY': s['objective_ledger'].get('h2_startup_million_JPY', 0.) / 1e3,
                     'aux_energy_GWh_total': uc['aux_energy_GWh_total']})
df = pd.DataFrame(rows)
df.to_csv(D / 'postprocess' / 'el_uc_stats.csv', index=False)
pd.set_option('display.width', 250)
print(df.round(2).to_string(index=False))
