"""Check: hydrogen cost per unit that the model puts in the objective (PLEXOS method, D2 args) vs the registry.
Expected (from params/h2.yaml): PV/discount = capex x (1 + FOM/r + share/((1+r)^L - 1)), capex per unit from the
registry (electrolyzer kJPY/kW x 549.2 kW/block). Effective: model.py scale_annuity applied to inputs/S2_annuity.json
(function source executed from model.py text, no `import model`). Usage: python check_h2_costs.py"""
import ast
import json
from argparse import Namespace
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).parent
ROOT = HERE.parent
src = (ROOT / 'src' / 'model.py').read_text(encoding='utf-8')
tree = ast.parse(src)
need = {'scale_annuity', 'parse_kv', '_interp'}
ns = {'np': np, 'pd': pd, 'ROOT': ROOT}
for node in tree.body:   # module constants and the functions needed, without running the model
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ('TECH', 'UNIT_KW') for t in node.targets):
        exec(compile(ast.Module([node], []), 'model.py', 'exec'), ns)
    if isinstance(node, ast.FunctionDef) and node.name in need:
        exec(compile(ast.Module([node], []), 'model.py', 'exec'), ns)

reg = {r['id']: r for r in yaml.safe_load((HERE / 'h2.yaml').read_text(encoding='utf-8'))}
args_txt = (ROOT / 'src' / 'default_D2_args.txt').read_text().split()
get = lambda k: args_txt[args_txt.index(k) + 1]
args = Namespace(capex_electrolyzer=get('--capex-electrolyzer'), capex_fuelcell=get('--capex-fuelcell'), capex_tank=get('--capex-tank'),
                 h2_fom=get('--h2-fom'), h2_stack_repl=get('--h2-stack-repl'))
ann = json.loads((ROOT / 'inputs' / 'S2_annuity.json').read_text(encoding='utf-8'))
eff = ns['scale_annuity'](ann, args)

kw = reg['h2_el_block_kw_basis']['value']
capex = {'electrolyzer': ({2025: 120, 2030: 52, 2040: 40, 2050: 30}, kw), 'fuelcell': ({2025: 180, 2030: 150, 2040: 113, 2050: 113}, 10000.),
         'tank': ({2025: 112000, 2030: 96000, 2040: 63000, 2050: 54000}, 1.)}   # kJPY/kW (tank kJPY/t) x units -> per unit
fom = {'electrolyzer': reg['h2_el_fom']['value'], 'fuelcell': reg['h2_fc_fom']['value'], 'tank': reg['h2_tank_fom']['value']}
stk = {'electrolyzer': reg['h2_el_stack_replacement_cost']['value'], 'fuelcell': reg['h2_fc_stack_replacement_cost']['value']}
OBJ = {'electrolyzer': 'Power to H2 Facility', 'fuelcell': 'FH2R Fuel Cell Power Station Hydrogen', 'tank': 'H2 Storage Tank'}
bad = 0
for k, (pts, u) in capex.items():
    for y in range(2025, 2051):
        c = ns['_interp'](pts, y) * 1000 * u
        exp = c * (1 + fom[k] / .03 + (stk[k]['share'] / (1.03 ** stk[k]['interval_years'] - 1) if k in stk else 0))
        got = eff[(OBJ[k], y)] / 1.03 ** -(y - 2025)
        if abs(got / exp - 1) > 1e-6:
            bad += 1; print(f'MISMATCH {k} {y}: expected {exp:,.0f} got {got:,.0f}')
    print(f'{k}: 2030 per unit expected {capex[k][0][2030]} kJPY x {u} -> PV/disc = {eff[(OBJ[k], 2030)] / 1.03 ** -5 / 1e6:,.2f} MJPY')
print('all match' if not bad else f'{bad} mismatches')
