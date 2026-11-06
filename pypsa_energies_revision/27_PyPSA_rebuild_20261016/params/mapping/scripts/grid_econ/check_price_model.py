"""Check the price-model entries of params/grid_econ.yaml against revision_round1/03_analysis/price_model/build_future_prices.py.

Constants are read with ast (the script itself is NOT run, so no output file is overwritten); derived values
(T_MIN, 2024 shape CFs, fixed net export) are recomputed from data/processed/hourly_tohoku_tokyo.parquet with the
same formulas (build_future_prices.py L32-42, L72-74). Output: printed report + price_model_values.json.
Usage: python check_price_model.py
"""
import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PM = HERE.parents[4] / 'revision_round1' / '03_analysis' / 'price_model'
src = (PM / 'build_future_prices.py').read_text(encoding='utf-8')
out = {}
consts = {}
for node in ast.parse(src).body:
    if isinstance(node, ast.Assign):
        for t in node.targets:
            names = [t] if isinstance(t, ast.Name) else (t.elts if isinstance(t, ast.Tuple) else [])
            try:
                val = ast.literal_eval(node.value)
            except Exception:
                val = None
            if val is None and isinstance(node.value, ast.Dict):   # e.g. SITES: {'x': 375 + 139}
                try:
                    val = eval(compile(ast.Expression(node.value), 'bfp', 'eval'), {'__builtins__': {}})
                except Exception:
                    continue
            if val is None:
                continue
            if isinstance(t, ast.Tuple):
                for n_, v in zip(names, val):
                    consts[n_.id] = (v, node.lineno)
            else:
                consts[t.id] = (val, node.lineno)
for k in ('REF', 'PV_REF_GW', 'WIND_REF_GW', 'NUC_GW', 'NUC_CF', 'PRICE_FLOOR', 'DATC', 'T_SPLIT', 'SITES'):
    out[k] = {'value': consts[k][0], 'line': consts[k][1]}
out['SITES_total_MW'] = sum(consts['SITES'][0].values())

d = pd.read_parquet(PM / 'data/processed/hourly_tohoku_tokyo.parquet')
d['export'] = -d['tohoku_interconnector']
fit = d[(d.fy >= 2023) & d.tohoku_demand.notna()]
out['T_MIN_MW'] = round(float(fit.tohoku_thermal.quantile(0.001)), 1)
r = d.loc[str(consts['REF'][0])]
out['pv_shape_cf_2024'] = round(float(((r.tohoku_solar + r.tohoku_solar_curtail) / (consts['PV_REF_GW'][0] * 1000)).mean()), 4)
out['onshore_shape_cf_2024'] = round(float(((r.tohoku_wind + r.tohoku_wind_curtail) / (consts['WIND_REF_GW'][0] * 1000)).mean()), 4)
out['net_export_2024_TWh'] = round(float(r.export.sum()) / 1e6, 2)
out['nuclear_MW'] = consts['NUC_GW'][0] * consts['NUC_CF'][0] * 1000
cap = pd.read_csv(PM.parent / 'tohoku_penetration_beta.csv')
cap = cap[cap.scenario == 'plan'].set_index('year')
out['plan_portfolio'] = {c: {int(y): float(cap.at[y, c]) for y in (2025, 2030, 2035, 2050)} for c in ('pv_GW', 'onshore_GW', 'offshore_GW', 'demand_TWh')}
val = pd.read_csv(PM / 'validation_metrics.csv', index_col=0)
out['validation'] = {'corr': val['corr'].to_dict(), 'MAE': val['MAE'].to_dict()}
summ = pd.read_csv(PM / 'future_prices_summary.csv', index_col=0)
out['extra_export_TWh_2050'] = float(summ.at[2050, 'extra_export_TWh'])
for k, v in out.items():
    print(f'{k}: {v}')
(HERE / 'price_model_values.json').write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
