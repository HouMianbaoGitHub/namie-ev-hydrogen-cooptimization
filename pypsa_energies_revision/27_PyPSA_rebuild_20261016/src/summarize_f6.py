"""Nine-scenario summary of the F6 default batch (truncated annuity at 2050) and its 2060 variant.
Electrolyzer block = 10 kg/h output; MW shown at the 2050 full-load SEC (54 kWh/kg). Fuel-cell block = 10 MW; tank in t.
Usage: python summarize_f6.py -> results/f6_20261030/F6_summary.csv"""
import json
from pathlib import Path

import pandas as pd

D = Path(__file__).resolve().parents[1] / 'results' / 'f6_20261030'
CASES = ['S0', 'S1', 'S2', 'A0', 'AH', 'B0', 'BH', 'C0', 'CH']
rows = []
for b in ('F6', 'F6t2060'):
    for c in CASES:
        d = D / f'{b}__{c}'
        s = json.loads((d / 'summary.json').read_text())
        r = {'batch': b, 'case': c, 'term': s['termination_condition'], 'check': s['check_passed'], 'npv': s['npv_billion_JPY'],
             'solve_min': s['solve_seconds'] / 60}
        if (d / 'installed_units.csv').exists():
            u = pd.read_csv(d / 'installed_units.csv', index_col=0).reindex(columns=['wind', 'electrolyzer', 'fuelcell', 'tank'], fill_value=0.)
            r.update(wind_MW_2050=u.at[2050, 'wind'] * 40, el_kgph_2050=u.at[2050, 'electrolyzer'] * 10,
                     el_MW_2050=u.at[2050, 'electrolyzer'] * 10 * 54 / 1000, fc_MW_2050=u.at[2050, 'fuelcell'] * 10,
                     tank_t_2050=u.at[2050, 'tank'])
            h = u.index[(u['electrolyzer'] > 1e-6) | (u['fuelcell'] > 1e-6)]
            r['first_h2'] = int(h[0]) if len(h) else None
        rows.append(r)
df = pd.DataFrame(rows)
df.to_csv(D / 'F6_summary.csv', index=False)
pd.set_option('display.width', 250)
print(df.round(3).to_string(index=False))
for b in ('F6', 'F6t2060'):
    n = df[df.batch == b].set_index('case').npv
    print(f'\n[{b}] H2 value: noEV {n.S2 - n.S1:.3f}  A {n.AH - n.A0:.3f}  B {n.BH - n.B0:.3f}  C {n.CH - n.C0:.3f}')
    print(f'  EV flex w/o H2: B-A {n.B0 - n.A0:.3f}  C-A {n.C0 - n.A0:.3f};  with H2: B-A {n.BH - n.AH:.3f}  C-A {n.CH - n.AH:.3f}')
    print(f'  interaction (CH-C0)-(AH-A0) {(n.CH - n.C0) - (n.AH - n.A0):.3f};  (BH-B0)-(AH-A0) {(n.BH - n.B0) - (n.AH - n.A0):.3f}')
