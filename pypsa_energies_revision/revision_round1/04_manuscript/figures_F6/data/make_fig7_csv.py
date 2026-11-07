"""Build data/fig7_sensitivity.csv (format: make_figures_f6.fig7) from results/sensF6_20261030/sensF6_summary.csv.
I_C is the interaction against the no-fleet reference, (CH-C0)-(S2-S1); ratio = ΔH(C)/ΔH(S) (share of the hydrogen value
retained with V2G); EV flexibility C-A only where A0 is the base A0.
Usage: python make_fig7_csv.py"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
S = HERE.parents[3] / '27_PyPSA_rebuild_20261016' / 'results' / 'sensF6_20261030' / 'sensF6_summary.csv'
EV, H2, CO, SY, EH = ('EV fleet', 'Hydrogen technology and operation', 'Hydrogen capital cost',
                      'System, prices and demand', 'End of horizon (different basis)')
GROUPS = [  # theme, group, label (order = plot order, top to bottom)
    (EV, 'coh3_t05', 'EV cohorts 3, θ = 0.5'), (EV, 'coh3_t075', 'EV cohorts 3, θ = 0.75'),
    (EV, 'coh4_t05', 'EV cohorts 4, θ = 0.5'),
    (EV, 'v2g6', 'V2G wear 6 JPY/kWh'), (EV, 'v2g10', 'V2G wear 10 JPY/kWh'), (EV, 'evcap080', 'EV usable capacity 0.8'),
    (EV, 'part025', 'EV participation 25%'), (EV, 'part075', 'EV participation 75%'),
    (EV, 'part100', 'EV participation 100%'), (EV, 'chg6', 'Charger 6 kW'),
    (H2, 'minload030', 'Electrolyzer min. load 30%'), (H2, 'startcost', 'Start-up cost 8,000 JPY/MW'),
    (H2, 'startenergy', 'Cold-start energy 0.15 MWh/MW'), (H2, 'stack10', 'Stack life 10 yr'),
    (H2, 'stack40', 'Stack life 40 yr'), (H2, 'pem', 'PEM electrolysis'),
    (H2, 'leak01', 'H$_2$ loss 0.1%/day'), (H2, 'leak10', 'H$_2$ loss 1%/day'),
    (H2, 'avail090', 'Availability 90%'), (H2, 'eff_hi', 'High H$_2$ efficiency'), (H2, 'eff_lo', 'Low H$_2$ efficiency'),
    (H2, 'tank043', 'Tank capped at 43 t'),
    (CO, 'capex070', 'H$_2$ capex ×0.7'), (CO, 'capex130', 'H$_2$ capex ×1.3'),
    (SY, 'price090', 'Price ×0.9'), (SY, 'price110', 'Price ×1.1'), (SY, 'wind075', 'Wind output ×0.75'),
    (SY, 'mkt100', 'Interface 100 MW'), (SY, 'mkt150', 'Interface 150 MW'),
    (SY, 'netcharge', 'Network charges on trade'), (SY, 'load090', 'Local demand ×0.9'),
    (SY, 'load110', 'Local demand ×1.1'), (SY, 'joint090', 'Wind/PV, EV availability, price ×0.9'),
    (EH, 'aperp', 'Perpetual annuity')]
s = pd.read_csv(S).set_index('group')
assert set(g for _, g, _ in GROUPS) == set(s.index) - {'BASE'}, set(s.index) ^ set(g for _, g, _ in GROUPS)
s['ratio'] = s['dH_C'] / s['dH_S']
b = s.loc['BASE']
rows = []
for th, g, lab in GROUPS:
    for m, col in (('dH_S', 'dH_S'), ('dH_C', 'dH_C'), ('I_C', 'I_S'), ('ratio', 'ratio'), ('EV_flex_CA', 'EV_flex_CA')):
        v = s.at[g, col]
        if m == 'EV_flex_CA' and 'C0' not in str(s.at[g, 'from_sensF5']):
            continue   # C0 not re-solved (hydrogen-only group): EV flexibility is the base value, not a result
        if pd.notna(v):
            rows.append(dict(theme=th, group=g, label=lab, metric=m, value=v, baseline=b[col]))
pd.DataFrame(rows).to_csv(HERE / 'fig7_sensitivity.csv', index=False)
print(len(rows), 'rows; ratio range', round(s.drop('BASE').ratio.min(), 3), '-', round(s.drop('BASE').ratio.max(), 3))
