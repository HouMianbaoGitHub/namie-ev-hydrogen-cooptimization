"""Effective values of the grid / market / renewables / load / economics registry (params/grid_econ.yaml) under D2.

D2 = argparse defaults <- PRESET_PLEXOS <- src/default_D2_args.txt (exactly the order of model.py main()).
Functions and constants are taken from src/model.py with ast (no `import model`, no solve); the hourly mappings of
model.py build() (renewable profile L222-227, price series L228-236, scaling L237-239, export p_max_pu L321) are
re-implemented line by line with the same formulas. Output: printed report + effective_values.json next to this file.
Usage: python compute_grid_econ.py
"""
import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]                       # 27_PyPSA_rebuild_20261016
INP = ROOT / 'inputs'
PM = ROOT.parent / 'revision_round1' / '03_analysis' / 'price_model'
SRC = (ROOT / 'src' / 'model.py').read_text(encoding='utf-8')
TREE = ast.parse(SRC)
OUT = {}


def rec(key, val):
    OUT[key] = val
    print(f'{key}: {val}')


# ---------------------------------------------------------------- model.py pieces (ast) ----------------------------
NS = {'np': np, 'pd': pd, 'ROOT': ROOT, 'json': json}
WANT_F = {'_interp', 'parse_path', 'extend_years', 'load_annuity', 'scale_annuity', 'parse_kv', 'grid_pv_per_mw',
          'W2050', 'annuity_factor', 'param'}
WANT_C = {'TECH', 'UNIT_KW', 'PERP', 'HEND', 'YEND', 'PRESET_PLEXOS', 'H2_PHYS'}
for node in TREE.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in WANT_C for t in node.targets):
        exec(compile(ast.Module([node], []), 'model.py', 'exec'), NS)
    if isinstance(node, ast.FunctionDef) and node.name in WANT_F:
        exec(compile(ast.Module([node], []), 'model.py', 'exec'), NS)


def lineno(pattern):
    """First model.py line containing pattern (for the mapping file)."""
    for i, line in enumerate(SRC.splitlines(), 1):
        if pattern in line:
            return i
    return None


# argparse defaults: every parser.add_argument('--x', ..., default=...) call in main()
defaults = {}
for node in ast.walk(TREE):
    if isinstance(node, ast.Call) and getattr(node.func, 'attr', '') == 'add_argument' and node.args:
        name = node.args[0].value.lstrip('-').replace('-', '_')
        kw = {k.arg: k.value for k in node.keywords}
        if 'default' in kw:
            defaults[name] = ast.literal_eval(kw['default'])
        elif isinstance(kw.get('action'), ast.Constant) and kw['action'].value == 'store_true':
            defaults[name] = False
        else:
            defaults[name] = None
eff = dict(defaults)
eff.update(NS['PRESET_PLEXOS'])
toks = (ROOT / 'src' / 'default_D2_args.txt').read_text().replace('{INP}', str(INP) + '/').split()
d2 = {}
i = 0
while i < len(toks):
    t = toks[i]
    if '=' in t:
        k, v = t.split('=', 1); d2[k] = v; i += 1
    elif i + 1 < len(toks) and not toks[i + 1].startswith('--'):
        d2[t] = toks[i + 1]; i += 2
    else:
        d2[t] = True; i += 1
for k, v in d2.items():
    name = k.lstrip('-').replace('-', '_')
    if k == '--preset':
        continue
    if v is True:
        eff[name] = True
        continue
    base = defaults.get(name)
    try:
        eff[name] = float(v) if isinstance(base, float) or base is None and v.replace('.', '', 1).isdigit() else (int(v) if isinstance(base, int) and not isinstance(base, bool) else v)
    except ValueError:
        eff[name] = v
keys = ['market_limit_mw', 'grid_max_mw', 'grid_capex_jpy_per_kw', 'grid_fom', 'grid_life', 'grid_wacc', 'grid_start_year',
        'import_adder_jpy_per_kwh', 'export_deduction_jpy_per_kwh', 'renewable_scale', 'wind_scale', 'price_scale',
        'series_curtail_scale', 'investment_method', 'no_perpetuity', 'perpetuity', 'extend_to', 'wacc', 're_fom_jpy_per_kw',
        'days_per_year', 'tsam_segments', 'price_wind_beta', 'price_wind_beta_path', 'export_curtail_share',
        'export_curtail_share_path', 'end_year', 'only_year', 'import_limit_mw', 'self_sufficiency', 'island_days']
rec('effective_args_D2', {k: eff.get(k) for k in keys})
PERP = eff['perpetuity'] or not eff['no_perpetuity']
rec('PERP', PERP)

# ---------------------------------------------------------------- 1. economics ------------------------------------
NS['PERP'] = PERP; NS['STATIC'] = None; NS['YEND'] = eff['extend_to']; NS['HEND'] = eff['extend_to']
W = NS['W2050']()
ops = {y: 1.03 ** -(y - 2024) for y in range(2025, 2050)}
rec('W2050', round(W, 4))
rec('W2050_closed_form_check', round(1.03 ** -25 / .03, 4))
rec('W2050_equals_sum_2050_to_inf', round(sum(1.03 ** -(t - 2024) for t in range(2050, 3000)), 4))
rec('share_2050_in_operating_weight', round(W / (sum(ops.values()) + W), 4))
rec('discount_2025_ops', round(1.03 ** -1, 4))

ann_raw = NS['load_annuity'](INP, 'S2')
from argparse import Namespace
a = Namespace(**{k: eff.get(k) for k in ('capex_electrolyzer', 'capex_fuelcell', 'capex_tank', 'h2_fom', 'h2_stack_repl')})
pv = NS['scale_annuity'](ann_raw, a)
raw = {(r['object'], r['year']): r['pv_per_unit'] for r in ann_raw}
TECH = NS['TECH']; UK = NS['UNIT_KW']
bc_files = {'wind': ('Build_Cost_WindOnshore_Yearly.csv', 1.), 'solar': ('Build_Cost_UtilityPV_Yearly.csv', 1.),
            'roof': ('Build_Cost_Rooftop_Yearly.csv', 1.)}
re_cost = {}
for k, (fn, _) in bc_files.items():
    bc = pd.read_csv(INP / 'historical_s4' / 'DataFiles' / fn, thousands=',', encoding='utf-8-sig')
    bc.columns = [c.strip() for c in bc.columns]
    bc = bc.set_index('year').iloc[:, 0].astype(str).str.replace(',', '').str.strip().astype(float) / 1000  # kJPY/kW
    obj = TECH[k][0]
    rows = {}
    for y in range(2025, 2051):
        per_kw = pv[(obj, y)] / UK[k] / 1000                     # kJPY/kW, PV in 2025 money
        undisc = per_kw / 1.03 ** -(y - 2025)                    # back to build year (capex discount convention)
        rows[y] = dict(pv_kJPY_per_kW=round(per_kw, 3), per_kW_build_year=round(undisc, 3), buildcost_csv=round(bc[y], 3),
                       fom_part=round(undisc - bc[y], 3), unchanged_by_scale_annuity=abs(pv[(obj, y)] - raw[(obj, y)]) < 1e-6)
    re_cost[k] = rows
    ys = [2025, 2030, 2035, 2040, 2050]
    rec(f'{k}_per_kW_by_year', {y: rows[y] for y in ys})
    ratios = [bc[y + 1] / bc[y] for y in range(2030, 2040)]
    rec(f'{k}_buildcost_geometric_2030_2040', dict(min_ratio=round(min(ratios), 6), max_ratio=round(max(ratios), 6)))
    rec(f'{k}_fom_part_range', (round(min(r['fom_part'] for r in rows.values()), 3), round(max(r['fom_part'] for r in rows.values()), 3)))
rec('fom_1000_over_r_kJPY', round(1000 / .03 / 1000, 3))
rec('fom_1000_over_r_x_8766_over_8760', round(1000 / .03 / 1000 * 8766 / 8760, 3))
rec('h2_rows_changed_by_scale_annuity', sum(abs(pv[k] - raw[k]) > 1e-6 for k in raw))

# --extend-to 2060: later vintages and W2050
NS['YEND'] = 2060
ann60 = NS['load_annuity'](INP, 'S2')
w60 = NS['W2050']()
k60 = {(r['object'], r['year']): r['pv_per_unit'] for r in ann60}
rec('ext2060_rows', len(ann60))
rec('ext2060_wind_2055_over_2050', round(k60[(TECH['wind'][0], 2055)] / k60[(TECH['wind'][0], 2050)], 6))
rec('ext2060_W', round(w60, 4))
NS['YEND'] = eff['extend_to']

# grid reinforcement cost per MW (only when --grid-max-mw > 0)
for label, g in (('D2_args', dict(grid_wacc=eff['grid_wacc'], grid_life=eff['grid_life'], grid_capex_jpy_per_kw=eff['grid_capex_jpy_per_kw'], grid_fom=eff['grid_fom'])),
                 ('registry', dict(grid_wacc=.03, grid_life=28., grid_capex_jpy_per_kw=105000., grid_fom=.019))):
    v = NS['grid_pv_per_mw'](2031, Namespace(**g))
    w, L = g['grid_wacc'], g['grid_life']
    crf = w / (1 - (1 + w) ** -L)
    rec(f'grid_pv_per_MW_2031_{label}', dict(million_JPY=round(v, 3), crf=round(crf, 5), annual_million_JPY_per_MW=round(g['grid_capex_jpy_per_kw'] * 1000 * (crf + g['grid_fom']) / 1e6, 4)))

# ---------------------------------------------------------------- 2. inputs / interface ---------------------------
cfg = {s: json.loads((INP / f'{s}_parameters.json').read_text(encoding='utf-8')) for s in ['S0', 'S1', 'S2', 'S3', 'S4']}
par = NS['param']
for s, c in cfg.items():
    market = eff['market_limit_mw'] if eff['market_limit_mw'] is not None else par(c, 'TohokuPowerMarket', 'Max Purchases', 150)
    gmax = eff['grid_max_mw'] if eff['grid_max_mw'] > 0 else 0.
    fixed_solar = sum(par(c, o, 'Units') * par(c, o, 'Max Capacity') for o in c if 'UtilityPV' in o or o == 'Namie RooftopPV')
    fixed_wind = par(c, 'Fukushima Revitalization OnshoreWind', 'Max Capacity') * par(c, 'Fukushima Revitalization OnshoreWind', 'Units')
    lim = {}
    for k in ('wind', 'solar', 'roof'):
        o, cap = TECH[k]
        lim[k] = dict(total_MW=par(c, o, 'Max Units Built') * par(c, o, cap), per_year_MW=par(c, o, 'Max Units Built in Year', par(c, o, 'Max Units Built')) * par(c, o, cap))
    rec(f'{s}_interface_and_fleet', dict(import_p_nom=market + gmax, export_p_nom=market + gmax, plexos_file_market=par(c, 'TohokuPowerMarket', 'Max Purchases', None),
                                        fixed_solar_MW=fixed_solar, fixed_wind_MW=fixed_wind, new_limits=lim,
                                        hydro_MW=par(c, 'Ukedo Gawa Hydro', 'Max Capacity', 1),
                                        newUtilityPV_units=par(c, 'NewUtilityPV UtilityPV', 'Units', None),
                                        lifetimes={k: (par(c, TECH[k][0], 'Technical Life', None), par(c, TECH[k][0], 'Economic Life', None)) for k in ('wind', 'solar', 'roof')}))

# ---------------------------------------------------------------- 3. hourly frame as in build() ---------------------
prof = pd.read_parquet(INP / 'profiles.parquet')
df = prof.copy()
rp = pd.read_parquet(eff['renewable_profile'])
key = lambda ix: list(zip(ix.month, ix.day, ix.hour))
for col in ('solar_pu', 'wind_pu'):                                   # model.py L224-227
    m = dict(zip(key(rp.index), rp[col].values)); df[col] = [m.get(k, np.nan) for k in key(df.index)]
    df[col] = df[col].interpolate().bfill().ffill()
ps = pd.read_parquet(eff['price_series'])                            # model.py L231-236
pm = {(y, t.month, t.day, t.hour): (p, c) for (y, t), p, c in zip(ps.index, ps['price'].values, ps['curtail_rate'].values)}
ylast = max(y for y, *_ in pm)
vals = [pm.get((min(t.year, ylast), t.month, t.day, t.hour)) for t in df.index]
rec('price_missing_snapshots', sum(v is None for v in vals))
df['price_JPY_MWh'] = [v[0] * 1000 for v in vals]; df['curt_rate'] = [v[1] for v in vals]
df['solar_pu'] = (df['solar_pu'] * eff['renewable_scale']).clip(upper=1)   # L237
df['wind_pu'] = (df['wind_pu'] * eff['renewable_scale'] * eff['wind_scale']).clip(upper=1)   # L238
df['price_JPY_MWh'] = df['price_JPY_MWh'] * eff['price_scale']     # L239
yr = df.index.year
rec('snapshots', len(df))
rec('hours_per_year_sample', {y: int((yr == y).sum()) for y in (2025, 2028, 2050)})
rec('nan_after_mapping', int(df[['solar_pu', 'wind_pu']].isna().sum().sum()))

cf = df.groupby(yr)[['solar_pu', 'wind_pu']].mean()
rec('pv_cf_by_year', {y: round(cf.at[y, 'solar_pu'] * 100, 3) for y in (2025, 2028, 2050)})
rec('wind_cf_by_year', {y: round(cf.at[y, 'wind_pu'] * 100, 3) for y in (2025, 2028, 2050)})
rec('pv_flh_2025', round(df.loc[yr == 2025, 'solar_pu'].sum(), 1))
rec('wind_flh_2025', round(df.loc[yr == 2025, 'wind_pu'].sum(), 1))
rec('ninja_file_cf_8784h', dict(pv=round(rp.solar_pu.mean() * 100, 3), wind=round(rp.wind_pu.mean() * 100, 3)))
w075 = (df.loc[yr == 2025, 'wind_pu'] * .75).clip(upper=1)
rec('wind_scale_075_cf_2025', round(w075.mean() * 100, 3))
rec('wind_pu_max', float(df['wind_pu'].max()))
rec('pv_diurnal_peak_hour', int(df.loc[yr == 2025, 'solar_pu'].groupby(df.loc[yr == 2025].index.hour).mean().idxmax()))
# raw ninja CSVs vs parquet
raw_dir = PM / 'data' / 'raw' / 'ninja'
for nm, col in (('namie_pv_2024.csv', 'solar_pu'), ('namie_h80_wind_2024.csv', 'wind_pu'), ('namie_wind_2024.csv', 'wind_pu')):
    r = pd.read_csv(raw_dir / nm); r.index = pd.to_datetime(r['local_time'])
    j = rp[[col]].join(r['electricity'], how='inner')
    rec(f'parquet_{col}_vs_{nm}', dict(n=len(j), max_abs_diff=float((j[col] - j['electricity']).abs().max()), cf_raw=round(r['electricity'].mean() * 100, 3)))

# prices
mp = df.groupby(yr)['price_JPY_MWh'].mean() / 1000
rec('mean_price_by_year', {y: round(mp[y], 3) for y in (2025, 2030, 2035, 2040, 2045, 2050)})
rec('price_min_file', float(ps['price'].min()))
rec('price_min_model', float(df['price_JPY_MWh'].min() / 1000))
fl = (df['price_JPY_MWh'] <= 10 + 1e-6).groupby(yr).sum()
rec('floor_hours_model', {y: int(fl[y]) for y in (2025, 2030, 2040, 2050)})
fp = pd.read_parquet(PM / 'future_prices.parquet')
same = fp[['price', 'curtail_rate']].reset_index(drop=True).equals(ps[['price', 'curtail_rate']].reset_index(drop=True)) and list(fp.index) == list(ps.index)
rec('price_file_identical_to_price_model_output', bool(same))
# curtailment and export cap
cr = df['curt_rate']
rec('curt_rate_mean_hourly_by_year_pct', {y: round(cr[yr == y].mean() * 100, 3) for y in (2025, 2030, 2035, 2040, 2050)})
pos = cr > 0
rec('curt_hours_not_at_floor', int((pos & (df['price_JPY_MWh'] > 10 + 1e-6)).sum()))
exp_pmax = (1 - cr * eff['series_curtail_scale']).clip(0, 1)
rec('export_pmax_min', float(exp_pmax.min()))
rec('export_lost_MWh_cap_by_year', {y: round(float(((1 - exp_pmax[yr == y]) * 118).sum()), 1) for y in (2025, 2040, 2050)})
summ = pd.read_csv(PM / 'future_prices_summary.csv', index_col=0)
rec('summary_curtail_pct_of_VRE', {y: float(summ.at[y, 'curtail_pct_of_VRE']) for y in (2025, 2030, 2035, 2040, 2050)})
rec('summary_mean_price', {y: float(summ.at[y, 'mean_price']) for y in (2025, 2030, 2035, 2040, 2045, 2050)})
rec('summary_hours_floor', {y: int(summ.at[y, 'hours_floor']) for y in (2025, 2030, 2040, 2050)})
rec('summary_extra_export_TWh_2050', float(summ.at[2050, 'extra_export_TWh']))

# ---------------------------------------------------------------- 4. load, hydro -----------------------------------
load = df.groupby(yr)['load_MW'].sum() / 1000
rec('load_GWh_by_year', {y: round(load[y], 3) for y in (2025, 2030, 2035, 2040, 2045, 2050)})
rec('load_peak_MW', dict(y2025=round(df.loc[yr == 2025, 'load_MW'].max(), 2), y2050=round(df.loc[yr == 2050, 'load_MW'].max(), 2)))
lc = pd.read_csv(INP / 'historical_s4' / 'DataFiles' / 'load_2024_2050.csv', index_col=0, parse_dates=True)
lt = lc.sum(axis=1)
rec('load_csv_2024_GWh', round(lt[lt.index.year == 2024].sum() / 1000, 3))
rec('load_csv_2050_GWh', round(lt[lt.index.year == 2050].sum() / 1000, 3))
rec('load_csv_nonzero_nodes', [c for c in lc.columns if lc[c].abs().sum() > 0])
b25 = df.loc[yr == 2025, 'load_MW']; b25.index = [(t.month, t.day, t.hour) for t in b25.index]
b50 = df.loc[yr == 2050, 'load_MW']; b50.index = [(t.month, t.day, t.hour) for t in b50.index]
ratio = (b50 / b25.reindex(b50.index))
rec('load_2050_over_2025_ratio', dict(min=round(ratio.min(), 4), max=round(ratio.max(), 4)))
hy = pd.read_parquet(INP / 'hydro_monthly.parquet').hydro_GWh
h25 = hy[hy.index.year == 2025]
hours = pd.Series([pd.Period(f'2025-{m:02d}').days_in_month * 24 for m in range(1, 13)], index=h25.index)
rec('hydro_monthly_2025_GWh', [round(v, 4) for v in h25.values])
rec('hydro_annual_GWh', round(h25.sum(), 4))
rec('hydro_achievable_GWh_1MW', round(np.minimum(h25.values * 1000, hours.values).sum() / 1000, 4))
rec('hydro_years_identical', bool(all(np.allclose(hy[hy.index.year == y].values, h25.values) for y in range(2025, 2051))))

# ---------------------------------------------------------------- 5. biomass ---------------------------------------
fp_b = pd.read_csv(INP / 'historical_s4' / 'DataFiles' / 'Hydrogen_Biomass_Market_Benchmark_Price_yearly.csv').set_index('year')['BiomassMarket']
bu = 1e-3 if eff['unit_scaling'] else 1.
rec('biomass', dict(link_p_nom_input_GJ_per_h=20 * bu / bu, efficiency_MWh_per_GJ=round(.1 / bu * bu, 4), output_MW=20 * .1,
                    heat_rate_GJ_per_MWh=10, stock_initial_GJ=10000, max_energy_GWh=10000 * .1 / 1000, e_nom_GJ=100000,
                    holding_JPY_per_GJ_yr=10, sale_price_2025=round(fp_b[2025], 2), sale_price_2050=round(fp_b[2050], 2),
                    sale_price_2051_exists=bool(2051 in fp_b.index)))

# ---------------------------------------------------------------- 6. line numbers ------------------------------------
pats = {'W2050': 'def W2050', 'annuity_factor': 'def annuity_factor', 'load_annuity': 'def load_annuity', 'scale_annuity': 'def scale_annuity',
        'grid_pv_per_mw': 'def grid_pv_per_mw', 'renewable_profile': 'if args.renewable_profile', 'price_series': 'if args.price_series',
        'wind_scale': "args.wind_scale).clip", 'discount': 'discount=pd.Series(1.03', 'W2050_ops': 'discount.loc[snapshots.year==YEND]',
        'fixed_solar': 'fixed_solar=sum', 'fixed_wind': 'fixed_wind=param', 'import_gen': "n.add('Generator','import'",
        'export_gen': "n.add('Generator','export'", 'market': 'market=args.market_limit_mw', 'gmax': 'gmax=args.grid_max_mw',
        'hydro_gen': "n.add('Generator','hydro'", 'hydro_month': "hydro_month_", 'biomass_store': "n.add('Store','biomass_stock'",
        'biomass_link': "n.add('Link','biomass'", 'build_upper': 'upper=xr.DataArray([param(cfg,TECH[k][0],\'Max Units Built in Year\'',
        'total_build': "name='total_build_'", 'costs': 'costs=xr.DataArray([[ann[', 'grid_block': 'if gmax>0:',
        'grid_obj': 'model.add_objective(model.objective.expression+(gbuild*gpv)', 'holding': 'coeff=10/1e6/bu',
        'preset_plexos': 'PRESET_PLEXOS=dict(', 'perp_set': 'PERP=args.perpetuity or not args.no_perpetuity',
        'fix_guard': 'if args.fix_builds is not None and PERP', 'extend_years': 'def extend_years', 'investment_pv': 'def investment_pv',
        'wind_cap': "name='wind_year_capacity'", 'solar_cap': "name='solar_year_capacity'", 'beta': 'if (beta_t!=0).any():',
        'share': 'if (share_t>0).any():', 'fuel_price': 'fuel_price=pd.read_csv'}
rec('model_py_lines', {k: lineno(p) for k, p in pats.items()})

(HERE / 'effective_values.json').write_text(json.dumps(OUT, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
