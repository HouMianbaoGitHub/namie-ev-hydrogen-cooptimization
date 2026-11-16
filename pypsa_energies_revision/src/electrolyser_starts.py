"""Electrolyser commitment and start-up statistics of the base cases."""

import json
from pathlib import Path
import pandas as pd
import model as M

D = Path(__file__).resolve().parents[1] / 'results' / 'base'
rows = []
for b in ('base', 'base2060'):
    for c in ('S2', 'AH', 'BH', 'CH'):
        d = D / f'{b}__{c}'
        s = json.loads((d / 'summary.json').read_text())
        cmd, uc = (s['command'], s['h2_uc'])
        u = pd.read_csv(d / 'installed_units.csv', index_col=0)
        ael = M._interp(M.parse_path(cmd['el_sec_path']), 2050) / 1000 / M.EL_FL_RATIO
        cap = u.at[2050, 'electrolyzer'] * 10 * ael * cmd['el_availability']
        first = int(u.index[u['electrolyzer'] > 1e-06][0])
        hours = len(pd.read_parquet(d / 'link_input.parquet', columns=['electrolyzer']))
        yrs = int(u.index.max()) - first + 1
        starts = uc['electrolyzer_started_MW_total'] / cap
        standby_h = uc['electrolyzer_mean_standby_MW'] * hours / cap
        rows.append(
            {
                'batch': b,
                'case': c,
                'el_link_MW_2050': cap,
                'first_build': first,
                'operating_years': yrs,
                'started_MW_total': uc['electrolyzer_started_MW_total'],
                'equiv_full_starts_total': starts,
                'equiv_full_starts_per_yr': starts / yrs,
                'standby_equiv_full_h_total': standby_h,
                'standby_equiv_full_h_per_yr': standby_h / yrs,
                'mean_committed_MW_2025_2050': uc['electrolyzer_mean_committed_MW'],
                'startup_cost_bn_JPY': s['objective_ledger'].get('h2_startup_million_JPY', 0.0) / 1000.0,
                'aux_energy_GWh_total': uc['aux_energy_GWh_total'],
            }
        )
df = pd.DataFrame(rows)
df.to_csv(D / 'postprocess' / 'el_uc_stats.csv', index=False)
pd.set_option('display.width', 250)
print(df.round(2).to_string(index=False))
