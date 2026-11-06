"""EV registry (params/ev.yaml) -> model.py mapping check under the D2 settings.

Recomputes, from the input files and the D2 command line, the values that enter the EV constraints and the
objective, and compares them with the registry values. Line numbers are located in model.py by pattern, so
the report stays valid if lines shift.

Rules (as params/check_h2_costs.py): model.py is read as text / ast only (no `import model`), the full model
is not built or solved, no input file is modified. The fixed charging profile is rebuilt into a temporary
directory with build_fixed_profile.py --preset newbase and compared with inputs/fixed_fleet_charging_newbase.parquet.

Usage:  python check_ev_map.py            -> prints a report and writes ev_effective_values.json next to this file
        python check_ev_map.py --no-rebuild  (skip the fixed-profile rebuild, ~1 min)
"""
import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]                      # 27_PyPSA_rebuild_20261016
PROJECT = ROOT.parent
INP = ROOT / 'inputs'
FIXED_SCRIPT = PROJECT / 'revision_round1' / '03_analysis' / 'fixed_fleet_charging' / 'build_fixed_profile.py'
MODEL = ROOT / 'src' / 'model.py'
SRC = MODEL.read_text(encoding='utf-8')
TREE = ast.parse(SRC)
LINES = SRC.splitlines()
TOL = 1e-9
results, checks = {}, []


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def grep(pattern, text_lines=LINES):
    """[(line number, stripped line)] of lines matching the regex."""
    rx = re.compile(pattern)
    return [(i + 1, l.strip()[:200]) for i, l in enumerate(text_lines) if rx.search(l)]


def line_of(pattern, text_lines=LINES):
    hits = grep(pattern, text_lines)
    return ','.join(f'L{i}' for i, _ in hits) if hits else 'NOT FOUND'


def check(name, ok, detail):
    checks.append(dict(check=name, ok=bool(ok), detail=detail))


# ---------------------------------------------------------------- D2 arguments, reconstructed with model.py's own parser
def d2_args(design_tokens):
    main = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    stmts = []
    for st in main.body:
        if isinstance(st, ast.Assign) and ast.get_source_segment(SRC, st).startswith('pre,_'):
            break
        stmts.append(st)
    ns = {'argparse': argparse, 'Path': Path, 'ROOT': ROOT}
    for node in TREE.body:      # PRESET_PLEXOS / PRESET_NEWBASE dict literals
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id.startswith('PRESET_') for t in node.targets):
            exec(compile(ast.Module([node], []), 'model.py', 'exec'), ns)
    exec(compile(ast.Module(stmts, []), 'model.py', 'exec'), ns)
    parser = ns['parser']
    d2 = (ROOT / 'src' / 'default_D2_args.txt').read_text().replace('{INP}', str(INP) + '/').split()
    argv = design_tokens + d2 + ['--output', str(Path(tempfile.gettempdir()) / 'ev_map_dummy')]
    pre, _ = parser.parse_known_args(argv)
    parser.set_defaults(**(ns['PRESET_PLEXOS'] if pre.preset == 'plexos' else ns['PRESET_NEWBASE']))
    return parser.parse_args(argv), d2


batch = ast.parse((ROOT / 'src' / 'make_reg1_batch.py').read_text(encoding='utf-8'))
DESIGN = next(ast.literal_eval(n.value) for n in batch.body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') == 'DESIGN')
EV_DESIGNS = {k: v for k, v in DESIGN.items() if k[0] in 'ABC'}
ARGS = {k: d2_args(v)[0] for k, v in EV_DESIGNS.items()}
_, D2_TOKENS = d2_args(DESIGN['C0'])
a = ARGS['C0']
EV_KEYS = ['model_fixes', 'tsam_segments', 'ev_capacity_scale', 'ev_station_eff', 'ev_batt_charge_eff', 'ev_batt_discharge_eff',
           'ev_charger_kw', 'v2g_cost_jpy_per_kwh', 'ev_departure_soc', 'ev_departure_hour', 'ev_departure_groups', 'ev_participation',
           'ev_availability_scale', 'ev_max_soc', 'ev_cohorts', 'ev_cohort_theta', 'ev_v2g_efc_cap', 'fixed_charge_profile', 'preset',
           'days_per_year', 'only_year', 'end_year', 'extend_to']
results['d2_args'] = {k: (str(getattr(a, k)) if isinstance(getattr(a, k), Path) else getattr(a, k)) for k in EV_KEYS}
results['designs'] = {k: dict(scenario=ARGS[k].scenario, ev_control=ARGS[k].ev_control) for k in ARGS}
check('A/B/C ev_control', all(ARGS[k].ev_control == {'A': 'fixed', 'B': 'charge_only', 'C': 'bidirectional'}[k[0]] for k in ARGS), results['designs'])
check('hourly snapshots (tsam_segments=0, days_per_year=0, full horizon)', a.tsam_segments == 0 and a.days_per_year == 0 and a.only_year is None and a.end_year is None and a.extend_to == 2050, '')

# ---------------------------------------------------------------- registry
REG = {r['id']: r for r in yaml.safe_load((ROOT / 'params' / 'ev.yaml').read_text(encoding='utf-8'))}

# ---------------------------------------------------------------- inputs
prof = pd.read_parquet(INP / 'profiles.parquet')
cfg = {s: json.loads((INP / f'{s}_parameters.json').read_text(encoding='utf-8')) for s in ('S3', 'S4')}
EVD = INP / 'historical_s4' / 'DataFiles' / 'ev_data'
fleet = pd.read_csv(EVD / 'EVforecast - Integrated.csv', encoding='utf-8-sig').set_index('year')


def load_time(path):   # same as prepare_inputs.load_time
    df = pd.read_csv(path)
    key = next(c for c in df if c.upper() == 'DATETIME')
    ix = pd.to_datetime(df.pop(key), format='mixed')
    df.index = ix
    return df.sort_index()


drive_csv = load_time(EVD / 'ev_data_2018_2050.csv').reindex(prof.index)
avail_csv = load_time(EVD / 'ev_charging_share_2018_2050.csv').reindex(prof.index)
GROUPS = {'commercial': 'EV JR Namie Commercial Area', 'residential': 'EV Residential Cars'}
years = prof.index.year

# ---- 1. fleet counts
for g, col in GROUPS.items():
    by_year = prof[g + '_vehicles'].groupby(years).agg(['min', 'max'])
    const = bool((by_year['min'] == by_year['max']).all())
    eq_csv = bool((by_year['max'] == fleet.loc[by_year.index, col]).all())
    reg = REG[f'ev_fleet_count_{g}']['value']
    eq_reg = all(int(by_year.loc[y, 'max']) == v for y, v in reg.items())
    results[f'ev_fleet_count_{g}'] = dict(by_year={int(y): float(v) for y, v in by_year['max'].items() if y in reg}, constant_within_year=const,
                                          equals_csv=eq_csv, equals_registry=eq_reg, managed_2050=float(by_year.loc[2050, 'max'] * a.ev_participation))
    check(f'fleet {g}: profiles.parquet == csv == registry', const and eq_csv and eq_reg, results[f'ev_fleet_count_{g}']['by_year'])
res_eq = bool((fleet['EV Residential Cars'] == fleet['EV JR Namie Commercial Area'] + fleet['EV Namie East Residential']).all())
results['residential_equals_commercial_plus_east'] = res_eq

# ---- 2. capacity and SoC window (code constants located by pattern)
ecap = .07 * a.ev_capacity_scale
floor = .35 * (.07 if a.model_fixes else ecap)
maxsoc = {s: {g: cfg[s][o]['Max SoC']['value'] / 100 for g, o in GROUPS.items()} for s in cfg}
results['ev_battery_nominal_capacity'] = dict(code=line_of(r'ecap=\.07\*args\.ev_capacity_scale'), nominal_MWh=.07)
results['ev_soh_capacity_scale'] = dict(arg=a.ev_capacity_scale, ecap_MWh=ecap)
results['ev_soc_min'] = dict(code=line_of(r'floor_dep=pd\.Series\(\.35'), model_fixes=a.model_fixes, floor_MWh_per_vehicle=floor,
                             share_of_usable=floor / ecap)
results['ev_soc_max'] = dict(code=line_of(r"maxsoc=param\(cfg,obj,'Max SoC'\)"), cfg_max_soc=maxsoc, ev_max_soc_arg=a.ev_max_soc,
                             emax_MWh_per_vehicle=ecap * maxsoc['S3']['commercial'], share_of_nominal=ecap * maxsoc['S3']['commercial'] / .07)
init = {s: {g: cfg[s][o]['Initial SoC']['value'] / 100 for g, o in GROUPS.items()} for s in cfg}
results['ev_initial_soc'] = dict(code_e_initial=line_of(r'e_initial=float\(count(_k)?\.iloc\[0\]\)\*ecap\*\.96'),
                                 code_arrivals=line_of(r'energy_arrivals=count(_k)?\.diff\(\)\.fillna\(0\)\*ecap\*\.96'), hardcoded=.96, cfg_initial_soc=init)
check('nominal capacity 0.07 MWh = registry 70 kWh', abs(.07 * 1000 - REG['ev_battery_nominal_capacity']['value']) < TOL, '')
check('SOH arg = registry', abs(a.ev_capacity_scale - REG['ev_soh_capacity_scale']['value']) < TOL, a.ev_capacity_scale)
check('SoC floor = 0.35 x 70 kWh (absolute)', a.model_fixes and abs(floor - REG['ev_soc_min']['value'] * .07) < TOL, floor)
check('SoC max: cfg Max SoC = 0.96 for all EV objects, --ev-max-soc unset', a.ev_max_soc is None and all(abs(v - REG['ev_soc_max']['value']) < TOL for s in maxsoc.values() for v in s.values()), maxsoc)
check('initial SoC 0.96 hardcoded = cfg Initial SoC = registry', all(abs(v - REG['ev_initial_soc']['value']) < TOL for s in init.values() for v in s.values()), init)

# ---- 3. standing loss
sl_hits = grep(r'standing_loss=\.0005')
results['ev_self_discharge'] = dict(code=','.join(f'L{i}' for i, _ in sl_hits), per_hour=5e-4, store_weighting=1.0 if a.tsam_segments == 0 else 'seg',
                                    per_day=1 - (1 - 5e-4) ** 24, per_30d=1 - (1 - 5e-4) ** 720,
                                    pypsa_formula='e_t = (1-standing_loss)^w_stores * e_(t-1) + p_t * w_stores (pypsa 1.2.4 define_store_constraints)')
check('EV standing loss 5e-4 per hourly snapshot = registry', len(sl_hits) == 2 and abs(5e-4 - REG['ev_self_discharge']['value']) < TOL and a.tsam_segments == 0, results['ev_self_discharge']['code'])

# ---- 4. efficiencies
es, ebc, ebd = a.ev_station_eff, a.ev_batt_charge_eff, a.ev_batt_discharge_eff
results['ev_station_efficiency'] = dict(arg=es, code=line_of(r'efficiency=es\*ebc|efficiency=ebd\*es'))
results['ev_battery_charge_efficiency'] = dict(arg=ebc, charge_link_eff=es * ebc)
results['ev_battery_discharge_efficiency'] = dict(arg=ebd, discharge_link_eff=ebd * es)
results['ev_round_trip_efficiency'] = dict(value=es * ebc * ebd * es)
for rid, v in [('ev_station_efficiency', es), ('ev_battery_charge_efficiency', ebc), ('ev_battery_discharge_efficiency', ebd)]:
    check(f'{rid} arg = registry', abs(v - REG[rid]['value']) < TOL, v)
check('round trip = registry 0.831 (3 d.p.)', abs(round(es * ebc * ebd * es, 3) - REG['ev_round_trip_efficiency']['value']) < 1e-9, es * ebc * ebd * es)

# ---- 5. charger power (DC metering under model_fixes)
kw = a.ev_charger_kw / 1000
results['ev_charger_power'] = dict(arg=a.ev_charger_kw, code_kw=line_of(r'kw_ev=args\.ev_charger_kw/1000'),
                                   code_shared=line_of(r"_charge'\)\*es\+links\.sel\(name=bus\+'_discharge'\)\*ebd<="),
                                   dc_kW=kw * 1000, ac_max_charge_kW=kw / es * 1000, battery_side_max_discharge_kW=kw / ebd * 1000,
                                   grid_side_max_discharge_kW=kw * es * 1000, model_fixes=a.model_fixes)
check('charger 10 kW DC (model_fixes shared-power constraint)', a.model_fixes and abs(a.ev_charger_kw - REG['ev_charger_power']['value']) < TOL, '')

# ---- 6. departure
h_dep = (a.ev_departure_hour - 1) % 24 if a.model_fixes else a.ev_departure_hour
dmask = prof.index.hour == h_dep
dep_floor = max(floor, a.ev_departure_soc * ecap)
hours_per_year = pd.Series(dmask, index=prof.index).groupby(years).sum()
days_per_year = pd.Series(1, index=prof.index).groupby(years).sum() / 24
results['ev_departure_hour'] = dict(arg=a.ev_departure_hour, code=line_of(r'h_dep=\(args\.ev_departure_hour-1\)%24'), constrained_snapshot_hour=h_dep,
                                    meaning='Store-e at snapshot 06:00 = energy at end of 06:00-07:00 = 07:00',
                                    constrained_hours_equal_days=bool((hours_per_year == days_per_year).all()))
results['ev_departure_soc'] = dict(arg=a.ev_departure_soc, floor_MWh_per_vehicle=dep_floor, share_of_nominal=dep_floor / .07,
                                   window_left_MWh=ecap * maxsoc['S3']['commercial'] - dep_floor, code=line_of(r'floor_dep\[dmask\]=np\.maximum'),
                                   dead_code_dep_floor=line_of(r'dep_floor'))
results['ev_departure_groups'] = dict(arg=a.ev_departure_groups, code=line_of(r'floor_dep if key in dep_groups'))
check('departure: hour 7 -> snapshot 06:00 every day', a.ev_departure_hour == REG['ev_departure_hour']['value'] and h_dep == 6 and results['ev_departure_hour']['constrained_hours_equal_days'], h_dep)
check('departure SoC 0.8 x usable = 50.4 kWh', abs(a.ev_departure_soc - REG['ev_departure_soc']['value']) < TOL and abs(dep_floor - .0504) < 1e-12, dep_floor)
check('departure groups = registry', a.ev_departure_groups.split(',') == REG['ev_departure_groups']['value'], a.ev_departure_groups)

# ---- 7. participation
p = a.ev_participation
part = {}
for g in GROUPS:
    N = prof[g + '_vehicles'] * p
    part[g] = dict(managed_vehicles_2050=float(N.loc['2050'].max()), e_nom_MWh=float(N.max() * ecap), charge_p_nom_MW_AC=float(N.max() * kw / es),
                   discharge_p_nom_MW_batt=float(N.max() * kw / ebd), managed_drive_GWh_total=float((prof[g + '_drive_MWh'] * p).sum() / 1000))
results['ev_participation'] = dict(arg=p, code_scale=line_of(r"df\[key\+'_vehicles'\]=df\[key\+'_vehicles'\]\*p_ev"),
                                   code_nonpart=line_of(r"p_set=\(1-p_ev\)\*fixed_grid_mw"), applies_to_designs='B, C only (A: whole fleet on fixed profile)', groups=part)
check('participation 0.5 = registry', abs(p - REG['ev_participation']['value']) < TOL, p)

# ---- 8. V2G cost and cycle cap
results['ev_v2g_cost'] = dict(arg=a.v2g_cost_jpy_per_kwh, marginal_cost_MJPY_per_MWh=a.v2g_cost_jpy_per_kwh / 1000,
                              code=line_of(r'marginal_cost=args\.v2g_cost_jpy_per_kwh/1000'), measured_on='discharge Link p0 (bus0 = EV battery bus) -> battery side',
                              active_in='C only (B: discharge == 0; A: no EV links)')
check('V2G cost 3 JPY/kWh -> 0.003 MJPY/MWh', abs(a.v2g_cost_jpy_per_kwh - REG['ev_v2g_cost']['value']) < TOL and abs(a.v2g_cost_jpy_per_kwh / 1000 - .003) < 1e-15, '')
results['ev_v2g_efc_cap'] = dict(arg=a.ev_v2g_efc_cap, code=line_of(r'if args\.ev_v2g_efc_cap is not None'))
check('no V2G EFC cap in D2', a.ev_v2g_efc_cap is None, '')

# ---- 9. availability and traction
av = {}
for g, col in GROUPS.items():
    exp = avail_csv[col + '~CS_JR Namie Commercial Area'] / 100
    av[g] = dict(source_column=col + '~CS_JR Namie Commercial Area', max_abs_diff=float((prof[g + '_availability'] - exp).abs().max()),
                 mean=float(prof[g + '_availability'].mean()), mean_at_06=float(prof.loc[prof.index.hour == 6, g + '_availability'].mean()),
                 max=float(prof[g + '_availability'].max()))
results['ev_availability_profile'] = av
check('availability = csv/100 (own fleet column, ~CS_JR Namie Commercial Area)', all(v['max_abs_diff'] < 1e-12 and v['max'] <= 1 for v in av.values()), {g: v['max_abs_diff'] for g, v in av.items()})
results['ev_availability_scale'] = dict(arg=a.ev_availability_scale, code=line_of(r"df\[column\]=\(df\[column\]\*args\.ev_availability_scale\)"))
check('availability scale 1.0', a.ev_availability_scale == REG['ev_availability_scale']['value'], '')
tr = {}
for g, col in GROUPS.items():
    exp = prof[g + '_vehicles'] * .0002 * drive_csv[col]
    km = drive_csv[col]
    annual_km = km.groupby(years).sum()
    tr[g] = dict(max_abs_diff_MWh=float((prof[g + '_drive_MWh'] - exp).abs().max()), mean_km_per_vehicle_hour=float(km.mean()),
                 annual_km_per_vehicle_mean=float(annual_km.mean()), annual_km_per_vehicle_min=float(annual_km.min()), annual_km_per_vehicle_max=float(annual_km.max()),
                 annual_kWh_per_vehicle_mean=float(annual_km.mean() * .2), night_0_6_kWh_per_vehicle_hour=float(km[prof.index.hour < 7].mean() * .2))
results['ev_traction_profile'] = tr
results['ev_energy_per_km'] = dict(code=line_of(r"\*\.0002\*drive", (ROOT / 'src' / 'prepare_inputs.py').read_text(encoding='utf-8').splitlines()) + ' (prepare_inputs.py)',
                                   MWh_per_km=.0002, cfg_Efficiency_Wh_per_km={s: cfg[s][GROUPS['commercial']]['Efficiency']['value'] for s in cfg})
check('drive_MWh = vehicles x 0.0002 x csv km', all(v['max_abs_diff_MWh'] < 1e-9 for v in tr.values()), '')
check('0.0002 MWh/km = registry 0.2 kWh/km', abs(.0002 * 1000 - REG['ev_energy_per_km']['value']) < TOL, '')
results['ev_annual_mileage'] = {g: dict(km=tr[g]['annual_km_per_vehicle_mean'], kWh=tr[g]['annual_kWh_per_vehicle_mean']) for g in GROUPS}

# ---- 10. cohorts
results['ev_cohort_test'] = dict(arg_cohorts=a.ev_cohorts, arg_theta=a.ev_cohort_theta, code_branch=line_of(r'args\.ev_cohorts>1'))
check('D2 uses 1 cohort (aggregate branch)', a.ev_cohorts == REG['ev_cohort_test']['value']['base_cohorts'], a.ev_cohorts)

# ---- 11. terminal condition
steady = a.model_fixes and (2049 in set(years))
ratio = {g: float(prof[g + '_vehicles'].iloc[-1] / prof.loc['2049', g + '_vehicles'].iloc[-1]) for g in GROUPS}
results['ev_terminal_condition'] = dict(steady=steady, ratio=ratio, code=line_of(r"_steady_final_year'\)$|_steady_final_year'\)"),
                                        terminal_recycle_active=not steady)
check('steady final year active (model_fixes, 2049 present)', steady, ratio)

# ---- 12. cost boundary: objective additions
obj_lines = grep(r'add_objective|marginal_cost=|capital_cost')
results['ev_battery_capex_in_system_cost'] = dict(objective_terms=obj_lines,
                                                  ev_terms=[x for x in obj_lines if 'ev' in x[1].lower() and 'v2g' not in x[1].lower() and 'price' not in x[1].lower()])
check('no EV battery / charger capex term in objective', not results['ev_battery_capex_in_system_cost']['ev_terms'] and not grep(r'capital_cost'), '')

# ---- 13. fixed (uncontrolled) charging profile
fs_lines = FIXED_SCRIPT.read_text(encoding='utf-8').splitlines()
fs_tree = ast.parse('\n'.join(fs_lines))
fs_ns = {}
for node in fs_tree.body:
    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ('BATTERY_MWH_PER_EV', 'CHARGER_MW_PER_EV', 'INITIAL_AND_MAX_SOC', 'MIN_SOC', 'HOURLY_STANDING_LOSS', 'PRESETS'):
        exec(compile(ast.Module([node], []), 'build_fixed_profile.py', 'exec'), fs_ns)
P = fs_ns['PRESETS']['newbase']
fx_params = dict(usable_MWh=P['battery_mwh'] * P['soh'], station_eff=P['station_eff'], battery_charge_eff=P['battery_charge_eff'],
                 standing_loss=fs_ns['HOURLY_STANDING_LOSS'], charger_MW=fs_ns['CHARGER_MW_PER_EV'], target_soc=fs_ns['INITIAL_AND_MAX_SOC'],
                 absolute_floor=P['absolute_floor'], departure_soc_check_only=P['departure_soc'])
d2_params = dict(usable_MWh=ecap, station_eff=es, battery_charge_eff=ebc, standing_loss=5e-4, charger_MW=kw, target_soc=maxsoc['S3']['commercial'],
                 absolute_floor=a.model_fixes, departure_soc_check_only=a.ev_departure_soc)
diff = {k: (fx_params[k], d2_params[k]) for k in fx_params if not (fx_params[k] == d2_params[k] or (isinstance(fx_params[k], float) and isinstance(d2_params[k], float) and abs(fx_params[k] - d2_params[k]) < 1e-12))}
fixed_path = INP / 'fixed_fleet_charging_newbase.parquet'
fx = pd.read_parquet(fixed_path)
fx_info = dict(script=str(FIXED_SCRIPT), script_params=fx_params, d2_params=d2_params, differing=diff, sha256_input=sha(fixed_path),
               d2_arg=str(a.fixed_charge_profile), d2_arg_resolves_to_this_file=Path(a.fixed_charge_profile).resolve() == fixed_path.resolve())
for g in GROUPS:
    soc = fx[g + '_stored_MWh'] / (prof[g + '_vehicles'] * ecap)
    fx_info[g] = dict(min_soc=float(soc.min()), min_soc_at_06=float(soc[prof.index.hour == 6].min()), charge_GWh=float(fx[g + '_grid_charge_MW'].sum() / 1000),
                      drive_GWh=float(prof[g + '_drive_MWh'].sum() / 1000), floor_shortfall_max=float(fx[g + '_floor_shortfall_MWh'].max()))
    fx_info[g]['charge_over_drive'] = fx_info[g]['charge_GWh'] / fx_info[g]['drive_GWh']
fx_info['peak_total_MW'] = float((fx['commercial_grid_charge_MW'] + fx['residential_grid_charge_MW']).max())
fx_info['index_matches_profiles'] = bool(fx.index.equals(prof.index))
if '--no-rebuild' not in sys.argv:
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([sys.executable, str(FIXED_SCRIPT), '--input', str(INP / 'profiles.parquet'), '--output-dir', td, '--preset', 'newbase'],
                           capture_output=True, text=True, cwd=td)
        if r.returncode:
            fx_info['rebuild_error'] = r.stderr[-2000:]
        else:
            new = Path(td) / 'fixed_fleet_charging.parquet'
            fx_info['sha256_rebuilt'] = sha(new)
            rb = pd.read_parquet(new)
            fx_info['rebuilt_max_abs_diff_MW'] = float((rb[fx.columns] - fx).abs().max().max())
            rep = json.loads((Path(td) / 'check.json').read_text())
            fx_info['rebuilt_check'] = dict(feasible_floor=rep['feasible_under_aggregate_floor'], feasible_departure_check_only=rep['feasible_departure_soc'])
results['ev_uncontrolled_charging_profile'] = fx_info
check('fixed profile generator parameters = D2 (except departure_soc, check-only)', set(diff) <= {'departure_soc_check_only'}, diff)
check('fixed profile SoC at 06:00 >= departure SoC 0.8', all(fx_info[g]['min_soc_at_06'] >= a.ev_departure_soc - 1e-9 for g in GROUPS), {g: fx_info[g]['min_soc_at_06'] for g in GROUPS})
if 'rebuild_error' in fx_info:
    check('fixed profile reproducible (rebuild ran)', False, fx_info['rebuild_error'][-300:])
if 'sha256_rebuilt' in fx_info:
    check('fixed profile reproducible (SHA-256 or values)', fx_info['sha256_rebuilt'] == fx_info['sha256_input'] or fx_info['rebuilt_max_abs_diff_MW'] < 1e-9,
          (fx_info['sha256_rebuilt'][:12], fx_info['sha256_input'][:12], fx_info['rebuilt_max_abs_diff_MW']))

# ---------------------------------------------------------------- output
out = dict(model_sha256=sha(MODEL), model_lines=len(LINES), profiles_sha256=sha(INP / 'profiles.parquet'), results=results, checks=checks)
(HERE / 'ev_effective_values.json').write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
for c in checks:
    print(('PASS ' if c['ok'] else 'FAIL ') + c['check'] + ('' if c['ok'] else f"   {c['detail']}"))
print(f"{sum(c['ok'] for c in checks)}/{len(checks)} checks passed; details in {HERE / 'ev_effective_values.json'}")
