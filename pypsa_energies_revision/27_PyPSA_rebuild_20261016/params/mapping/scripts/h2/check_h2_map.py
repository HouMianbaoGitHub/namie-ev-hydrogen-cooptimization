"""Registry (params/h2.yaml) -> model.py effective values, D2 run (default_D2_args.txt).

How: the argparse parser of model.py main() is rebuilt from the source with ast (add_argument calls replayed),
PRESET_PLEXOS is applied with set_defaults, then the D2 arguments are parsed -- the same order as model.py.
Functions/constants needed (scale_annuity, parse_kv, _interp, TECH, UNIT_KW, H2_PHYS, PRESET_PLEXOS) are executed
from the model.py text; `import model` is never used and the model is not built.
Effective values are computed with the code formulas (line numbers in params/mapping/h2_map.yaml) and compared with
the registry value. Usage: python check_h2_map.py  (writes h2_map_results.json next to this script).
"""
import argparse
import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]                      # 27_PyPSA_rebuild_20261016
SRC = (ROOT / 'src' / 'model.py').read_text(encoding='utf-8')
TREE = ast.parse(SRC)
REG = {r['id']: r for r in yaml.safe_load((ROOT / 'params' / 'h2.yaml').read_text(encoding='utf-8'))}

# ---------------------------------------------------------------- code objects from model.py text
ns = {'np': np, 'pd': pd, 'ROOT': ROOT, 'Path': Path}
CONSTS = ('TECH', 'UNIT_KW', 'H2_PHYS', 'PRESET_PLEXOS', 'EL_LIFE_PATH', 'H2_STACK')
FUNCS = ('scale_annuity', 'parse_kv', '_interp')
for node in TREE.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in CONSTS for t in node.targets):
        exec(compile(ast.Module([node], []), 'model.py', 'exec'), ns)
    if isinstance(node, ast.FunctionDef) and node.name in FUNCS:
        exec(compile(ast.Module([node], []), 'model.py', 'exec'), ns)
fn_src = {n.name: ast.get_source_segment(SRC, n) for n in TREE.body if isinstance(n, ast.FunctionDef)}

# ---------------------------------------------------------------- rebuild the argparse parser of main()
main = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
parser = argparse.ArgumentParser()
env = {'argparse': argparse, 'Path': Path, 'float': float, 'int': int, 'str': str}
for call in ast.walk(main):
    if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) and call.func.attr == 'add_argument' \
            and isinstance(call.func.value, ast.Name) and call.func.value.id == 'parser':
        a = [ast.literal_eval(x) for x in call.args]
        kw = {k.arg: eval(compile(ast.Expression(k.value), 'model.py', 'eval'), env) for k in call.keywords}
        parser.add_argument(*a, **kw)
d2_txt = (ROOT / 'src' / 'default_D2_args.txt').read_text(encoding='utf-8').replace('{INP}', str(ROOT / 'inputs') + '/')
d2 = d2_txt.split() + ['--scenario', 'S2', '--output', str(HERE / '_unused')]
pre, _ = parser.parse_known_args(d2)
assert pre.preset == 'plexos'
parser.set_defaults(**ns['PRESET_PLEXOS'])
A = parser.parse_args(d2)
hu = 1e-3 if A.unit_scaling else 1.

cfg = json.loads((ROOT / 'inputs' / 'S2_parameters.json').read_text(encoding='utf-8'))
P = lambda o, k: cfg[o][k]['value']
ann = json.loads((ROOT / 'inputs' / 'S2_annuity.json').read_text(encoding='utf-8'))
OBJ = {'electrolyzer': 'Power to H2 Facility', 'fuelcell': 'FH2R Fuel Cell Power Station Hydrogen', 'tank': 'H2 Storage Tank'}
YEARS = range(2025, 2051)
r = .03

out = {}
def rec(i, effective, expected, ok, how, extra=None):
    out[i] = dict(effective=effective, expected=expected, ok=bool(ok), check=how, **(extra or {}))

def close(a, b, tol=1e-6):
    return abs(a - b) <= tol * max(1., abs(b))

# ---------------------------------------------------------------- A. capex (per kW, build year)
blk_kw = REG['h2_el_block_kw_basis']['value']
unit = {'electrolyzer': blk_kw, 'fuelcell': 10000., 'tank': 1.}          # kW per block (tank: t per block)
argcap = {k: ns['parse_kv'](getattr(A, 'capex_' + k)) for k in OBJ}
for k, rid in [('electrolyzer', 'h2_el_capex'), ('fuelcell', 'h2_fc_capex'), ('tank', 'h2_tank_capex')]:
    pts = {y: v[0] for y, v in {int(a): b for a, b in argcap[k].items()}.items()}
    regv = REG[rid]['value']
    # D2 string -> kJPY per kW (electrolyzer: per block / 549.2; fuel cell: given per kW; tank: kJPY/t -> kJPY/kg)
    conv = {'electrolyzer': 1 / blk_kw, 'fuelcell': 1., 'tank': 1e-3}[k]
    worst = max(abs(ns['_interp'](pts, y) * conv / ns['_interp'](regv, y) - 1) for y in YEARS)
    rec(rid, {y: round(pts[y] * conv, 4) for y in pts}, regv, worst < 1e-6,
        'D2 --capex-* parsed by parse_kv, _interp 2025-2050, divided by block size; max rel. diff %.2e' % worst)

# full unit cost in the objective (PV / discount) incl. FOM + stack replacement
eff_all = ns['scale_annuity'](ann, A)
def only(**kw):
    ns2 = argparse.Namespace(**{**vars(A), **kw})
    return ns['scale_annuity'](ann, ns2)
eff_fom = only(h2_stack_repl=None)
eff_stk = only(h2_fom=None)
fomv = {k: ns['parse_kv'](A.h2_fom).get(k, (0.,))[0] for k in OBJ}
stkv = ns['parse_kv'](A.h2_stack_repl)
fom_back, stk_back, tot_bad = {}, {}, 0
for k in OBJ:
    fb, sb = [], []
    for y in YEARS:
        d = 1.03 ** -(y - 2025)
        nv = ns['_interp']({int(a): b[0] for a, b in argcap[k].items()}, y) * 1000 * (ns['UNIT_KW']['fuelcell'] if k == 'fuelcell' else 1.)
        fb.append((eff_fom[(OBJ[k], y)] / d / nv - 1) * r)                 # implied FOM share per year
        if k in stkv:
            sb.append(eff_stk[(OBJ[k], y)] / d / nv - 1)                    # implied PV share of perpetual replacements
        regc = ns['_interp'](REG[{'electrolyzer': 'h2_el_capex', 'fuelcell': 'h2_fc_capex', 'tank': 'h2_tank_capex'}[k]]['value'], y) * 1000 * {'electrolyzer': blk_kw, 'fuelcell': 10000., 'tank': 1000.}[k]  # registry kJPY/kW (tank kJPY/kg) -> JPY per block
        f = REG[{'electrolyzer': 'h2_el_fom', 'fuelcell': 'h2_fc_fom', 'tank': 'h2_tank_fom'}[k]]['value']
        s = REG.get({'electrolyzer': 'h2_el_stack_replacement_cost', 'fuelcell': 'h2_fc_stack_replacement_cost'}.get(k, ''), {}).get('value')
        exp = regc * (1 + f / r + (s['share'] / (1.03 ** s['interval_years'] - 1) if s else 0))
        if not close(eff_all[(OBJ[k], y)] / d, exp): tot_bad += 1
    fom_back[k] = (min(fb), max(fb))
    if sb: stk_back[k] = (min(sb), max(sb))
for k, rid in [('electrolyzer', 'h2_el_fom'), ('fuelcell', 'h2_fc_fom'), ('tank', 'h2_tank_fom')]:
    lo, hi = fom_back[k]
    rec(rid, round(lo, 8), REG[rid]['value'], close(lo, REG[rid]['value']) and close(hi, REG[rid]['value']),
        'scale_annuity with --h2-stack-repl removed: (PV/d/capex - 1) x 0.03, all years 2025-2050')
for k, rid in [('electrolyzer', 'h2_el_stack_replacement_cost'), ('fuelcell', 'h2_fc_stack_replacement_cost')]:
    v = REG[rid]['value']; want = v['share'] / (1.03 ** v['interval_years'] - 1)
    lo, hi = stk_back[k]
    rec(rid, {'share': stkv[k][0], 'interval_years': stkv[k][1], 'pv_share_of_capex': round(lo, 6)},
        {**v, 'pv_share_of_capex': round(want, 6)}, close(lo, want) and close(hi, want),
        'scale_annuity with --h2-fom removed: PV/d/capex - 1 = share/(1.03^L - 1)')
out['_total_unit_cost'] = dict(mismatching_year_tech=tot_bad)

# ---------------------------------------------------------------- C. lives (PLEXOS method: no life anywhere)
uses_life = 'tech_life' in fn_src['scale_annuity']
for rid in ('h2_el_system_life', 'h2_fc_system_life', 'h2_tank_life'):
    v = REG[rid]['value']
    life = (lambda y: round(ns['_interp'](v, y))) if isinstance(v, dict) else (lambda y, v=v: v)
    expired = [y for y in YEARS if y + life(y) <= 2050]
    rec(rid, 'not used (investment_method=%s; scale_annuity uses tech_life: %s)' % (A.investment_method, uses_life), v,
        A.investment_method == 'plexos' and not uses_life, 'args.investment_method; ast: tech_life absent from scale_annuity',
        {'vintages_past_registry_life_by_2050': expired})

# ---------------------------------------------------------------- degradation
age_el = (A.el_stack_life - 1) / 2 if A.degradation_average else None
age_fc = (A.fc_stack_life - 1) / 2 if A.degradation_average else None
dl_el = 1 + A.el_degradation * age_el
dl_fc = 1 + A.fc_degradation * age_fc
rec('h2_el_stack_life', A.el_stack_life, REG['h2_el_stack_life']['value'], A.el_stack_life == REG['h2_el_stack_life']['value'],
    'args.el_stack_life (L347 age = (L-1)/2) and --h2-stack-repl interval', {'age_years': age_el})
rec('h2_fc_stack_life', A.fc_stack_life, REG['h2_fc_stack_life']['value'], A.fc_stack_life == REG['h2_fc_stack_life']['value'],
    'args.fc_stack_life (L350)', {'age_years': age_fc})
rec('h2_el_degradation', A.el_degradation, REG['h2_el_degradation']['value'], close(A.el_degradation, REG['h2_el_degradation']['value']),
    'L346-348: eff = hu/(a_el(1+r*age))', {'delta_el': round(dl_el, 5)})
rec('h2_fc_degradation', A.fc_degradation, REG['h2_fc_degradation']['value'], close(A.fc_degradation, REG['h2_fc_degradation']['value']),
    'L349-351', {'delta_fc': round(dl_fc, 5), 'aged_kg_per_MWh': round(A.fc_kg_per_mwh * dl_fc, 3)})
rec('h2_degradation_method', 'lifetime_average' if A.degradation_average else 'sawtooth', REG['h2_degradation_method']['value'],
    A.degradation_average, 'args.degradation_average', {'age_el': age_el, 'age_fc': age_fc, 'registry_unit_text': REG['h2_degradation_method']['unit']})

# ---------------------------------------------------------------- D. electricity per kg
a = A.h2_electrolysis_mwh_per_kg * 1000          # kWh/kg
pieces = [tuple(float(v) for v in p.split(':')) for p in A.el_curve.split(',')]
f0 = A.el_noload
def extra(x):                                     # MW extra per MW productive committed (L519-525, ref = u - su)
    return f0 + max([0.] + [s * (x - b) for b, s in pieces])
def sec(x, dl=1.):                                # kWh per kg actually produced at load fraction x
    return a * dl * (1 + extra(x) / x)
F = 1 + extra(1.)
rec('h2_el_linear_coeff', round(a, 6), REG['h2_el_linear_coeff']['value'], close(a, REG['h2_el_linear_coeff']['value']),
    'args.h2_electrolysis_mwh_per_kg x 1000; L339 efficiency = hu/a_el')
rec('h2_el_compression_energy', 'not separable (contained in a_el = %.2f)' % a, REG['h2_el_compression_energy']['value'],
    close(a, 47.12 + REG['h2_el_compression_energy']['value']), '49.12 = 47.12 + 2.0 (registry chain); scaled by delta_el',
    {'compression_after_ageing_kWh_per_kg': round(REG['h2_el_compression_energy']['value'] * dl_el, 3)})
rec('h2_el_sec_reference_53', 'not in D2 (PRESET_PLEXOS 0.053 overridden by --h2-electrolysis-mwh-per-kg)', 53.0, True, 'args')
sb = REG['h2_el_sec_basis']
rec('h2_el_sec_basis', {'linear_coeff': a, 'full_load_system': round(sec(1.), 3)}, sb['value'],
    close(a, sb['value']['linear_coeff']) and abs(sec(1.) - sb['value']['full_load_system']) < .01,
    'SEC(x) = a*delta*(1 + extra(x)/x)', {'unaged': {'x035': round(sec(.35), 2), 'x050': round(sec(.5), 2), 'x070': round(sec(.7), 2), 'x100': round(sec(1.), 2)},
                                          'aged_delta_%.4f' % dl_el: {'x035': round(sec(.35, dl_el), 2), 'x100': round(sec(1., dl_el), 2)},
                                          'registry_sensitivity_aged': sb['sensitivity']['as_coded_aged_lifetime_avg']})
rec('h2_el_full_load_input_factor', round(F, 5), REG['h2_el_full_load_input_factor']['value'], abs(F - REG['h2_el_full_load_input_factor']['value']) < 5e-5,
    '1 + noload + max_j s_j(1-b_j)')
rec('h2_el_noload', A.el_noload, REG['h2_el_noload']['value'], close(A.el_noload, REG['h2_el_noload']['value']) and A.h2_uc,
    'L519-521 extra >= noload*u (u in link MW)', {'share_of_full_load_input': round(A.el_noload / F, 5)})
(b1, s1), (b2, s2) = pieces
cv = REG['h2_el_partload_curve']['value']
ok_curve = (A.el_curve == cv['cli'] and abs(s1 * a - cv['extra_slope_kwh_per_kg'][0]) < .01 and abs((s2 - s1) * a - cv['extra_slope_kwh_per_kg'][1]) < .01
            and abs(s1 * (cv['breakpoints'][1] - b1) - s2 * (cv['breakpoints'][1] - b2)) < 1e-4 and b1 == cv['breakpoints'][0])
rec('h2_el_partload_curve', {'cli': A.el_curve, 'slopes_kWh_per_kg': [round(s1 * a, 3), round((s2 - s1) * a, 3)],
                             'kink_x': round((s2 * b2 - s1 * b1) / (s2 - s1), 4)}, cv, ok_curve,
    'L522-525; kink where s1(x-b1) = s2(x-b2); ref = u - su (model_fixes & h2_uc & startup_hours>0)',
    {'ref_is_committed_minus_startup': bool(A.model_fixes and A.h2_uc and A.h2_startup_hours > 0)})
vom_per_kg = 4 * dl_el                            # marginal_cost (4/a_el) per MWh input; kg produced per MWh = 1/(a_el*delta)
rec('h2_el_water_vom', round(vom_per_kg, 4), REG['h2_el_water_vom']['value'], close(vom_per_kg, REG['h2_el_water_vom']['value']),
    'L339 marginal_cost = (4/a_el)/1e6 per MWh link input; kg per MWh input = 1/(a_el*delta) (L348)',
    {'JPY_per_MWh_input': round(4 / A.h2_electrolysis_mwh_per_kg, 2), 'hardcoded_in_code': 'marginal_cost=(4/a_el)' in SRC,
     'S2_parameters_VOM': P('Power to H2 Facility', 'VO&M Charge')})

# ---------------------------------------------------------------- F. operations
simple = [('h2_uc_enabled', A.h2_uc), ('h2_el_min_load', A.el_min_load), ('h2_el_startup_hours', A.h2_startup_hours),
          ('h2_el_standby_power', A.el_standby_power), ('h2_el_startup_energy', A.el_startup_energy), ('h2_el_startup_cost', A.el_startup_cost),
          ('h2_el_ramp', A.el_ramp), ('h2_fc_min_load', A.fc_min_load), ('h2_fc_startup_hours', A.fc_startup_hours), ('h2_fc_ramp', A.fc_ramp),
          ('h2_el_availability', A.el_availability), ('h2_fc_availability', A.fc_availability), ('h2_fc_kg_per_mwh', A.fc_kg_per_mwh),
          ('h2_tank_standing_loss', A.h2_standing_loss_per_day)]
for rid, v in simple:
    rv = REG[rid]['value']
    rec(rid, v, rv, (v == rv) if isinstance(rv, bool) else close(float(v), float(rv)), 'resolved args (argparse default <- PRESET_PLEXOS <- D2)')
fcs = {'standby': A.fc_standby_power, 'startup_energy': A.fc_startup_energy, 'startup_cost': A.fc_startup_cost}
rec('h2_fc_standby_startup', fcs, REG['h2_fc_standby_startup']['value'], fcs == REG['h2_fc_standby_startup']['value'], 'argparse defaults')
out['h2_el_ramp']['binding_possible'] = A.el_ramp < 1
out['h2_fc_ramp']['binding_possible'] = A.fc_ramp < 1
out['h2_fc_availability'].update(max_electric_MW_per_MW=round(A.fc_availability / dl_fc, 4))
out['h2_el_availability'].update(link_MW_per_block=round(10 * A.h2_electrolysis_mwh_per_kg * A.el_availability, 5),
                                 kg_per_h_per_block_aged=round(10 * A.el_availability / dl_el, 4))
out['h2_fc_kg_per_mwh'].update(lhv_eff=round(1000 / (A.fc_kg_per_mwh * 33.33), 4), aged=round(A.fc_kg_per_mwh * dl_fc, 3),
                               aged_lhv_eff=round(1000 / (A.fc_kg_per_mwh * dl_fc * 33.33), 4))
rec('h2_fc_partload', 'constant' if 'fc_curve' not in SRC else 'curve', 'constant', 'fc_curve' not in SRC, 'no fuel-cell curve argument/constraint in model.py')

# ---------------------------------------------------------------- I. tank
rec('h2_tank_initial_inventory', 0, REG['h2_tank_initial_inventory']['value'],
    "n.add('Store','hydrogen'" in SRC and 'e_initial=0,e_cyclic=bool(STATIC),standing_loss=h2_loss' in SRC and P('H2 Storage Tank', 'Opening Inventory') == 0, 'L338 + S2_parameters Opening Inventory')
rec('h2_tank_terminal_condition', 'steady final year' if A.model_fixes else 'e(end)=0', REG['h2_tank_terminal_condition']['value'],
    A.model_fixes and 'hydrogen_steady_final_year' in SRC, 'L551-556: steady = model_fixes and 2049 in snapshots')

# ---------------------------------------------------------------- J. blocks
el_blk = P('Power to H2 Facility', 'Max Operating Level')
fc_blk = P('FH2R Fuel Cell Power Station Hydrogen', 'Max Capacity')
tk_blk = P('H2 Storage Tank', 'Max Inventory') * hu
rec('h2_el_block_size', el_blk, REG['h2_el_block_size']['value'], el_blk == REG['h2_el_block_size']['value'], "cap() L466 = installed*param/bsc (bsc=1)")
rec('h2_fc_block_size', fc_blk, REG['h2_fc_block_size']['value'], fc_blk == REG['h2_fc_block_size']['value'], 'cap() with bsc=10 -> MW')
rec('h2_tank_block_size', tk_blk, REG['h2_tank_block_size']['value'], close(tk_blk, REG['h2_tank_block_size']['value']), 'L530 cap(tank)*hu')
kw_link = el_blk * a; kw_full = kw_link * F
capex_kw_basis = {int(y): v[0] / {2025: 120, 2030: 52, 2040: 40, 2050: 30}[int(y)] for y, v in argcap['electrolyzer'].items()}
rec('h2_el_block_kw_basis', {'capex_divisor_from_D2': capex_kw_basis, 'full_load_input_kW': round(kw_full, 2), 'link_kW': kw_link, 'UNIT_KW': ns['UNIT_KW']['electrolyzer']},
    blk_kw, all(abs(v - blk_kw) < 1e-6 for v in capex_kw_basis.values()) and abs(kw_full - blk_kw) < .05,
    'D2 capex per block / registry kJPY/kW; 10 x a_el x F')

# ---------------------------------------------------------------- K. caps
phys = {'electrolyzer': ns['H2_PHYS']['electrolyzer_MW'] / (10 * A.h2_electrolysis_mwh_per_kg), 'fuelcell': ns['H2_PHYS']['fuelcell_MW'] / 10., 'tank': ns['H2_PHYS']['tank_t']}
pv = REG['h2_physical_caps']['value']
rec('h2_physical_caps', {'H2_PHYS': ns['H2_PHYS'], 'unit_caps': {k: round(v, 2) for k, v in phys.items()},
                         'electrolyzer_full_load_MW': round(phys['electrolyzer'] * kw_full / 1000, 1)},
    pv, ns['H2_PHYS'] == {'electrolyzer_MW': pv['electrolyzer_MW_link'], 'fuelcell_MW': pv['fuelcell_MW'], 'tank_t': pv['tank_t']}, 'L121, L434-437, L462-463')
rec('h2_build_caps', 'none (physical caps only)' if A.h2_unlimited else 'original limits', None, A.h2_unlimited, 'args.h2_unlimited -> h2s=h2a=inf (L336, L432-436)')

missing = sorted(set(REG) - set(out))
print(json.dumps({k: (v['ok'], v['effective'], v['expected']) for k, v in out.items() if not k.startswith('_')}, ensure_ascii=False, indent=1, default=str))
print('registry ids:', len(REG), 'checked:', len([k for k in out if not k.startswith('_')]), 'missing:', missing)
print('total unit cost mismatches (tech-year):', tot_bad)
(HERE / 'h2_map_results.json').write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
