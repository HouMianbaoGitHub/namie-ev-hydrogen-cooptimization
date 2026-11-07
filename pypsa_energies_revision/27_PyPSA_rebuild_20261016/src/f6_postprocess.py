"""Post-processing of the F6 default batch (truncated annuities at 2050) for the energies-4608521 revision.

Reads the nine F6 result directories (results/f6_20261030/F6__<case>/) plus the model inputs that the solved model
used but did not write out (inputs/profiles.parquet: EV fleet size and plug-in availability; inputs/fixed_fleet_charging_newbase.parquet:
uncontrolled-charging SoC; inputs/namie_renewables_ninja_2024.parquet: wind/PV capacity factors; inputs/tohoku_price_plan_ref2024.parquet:
price and export curtailment rate; inputs/S*_parameters.json: fixed plant capacities). Parameters are taken from each run's
build_stats.json 'command' (efficiencies, paths, availability), not hard-coded, except the model constants copied below from
src/model.py (EL_FL_RATIO, the 0.0005/h EV standing loss, 10 kW per connected vehicle, 0.35 x 70 kWh floor).

Tasks (outputs in results/f6_20261030/postprocess/):
 1 timescale_metrics.csv/json   hydrogen and EV storage timescale metrics, 2050 (definitions as lp_timescale_metrics.py)
 2 window_sensitivity.csv       variance decomposition 7/28 d vs 5/20 d (all cases, 2049 and 2050)
 3 energy_balance_by_year.csv, energy_balance_summary.csv   (2050 and 2025-2050 cumulative)
 4 mechanism_2050.csv, mechanism_hour_of_day_2050.csv
 5 ev_feasibility.csv           shared charger limit, SoC bounds, simultaneous charge/discharge
 6 capacity_summary.csv
Usage: python f6_postprocess.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / 'results' / 'f6_20261030'
OUT = RES / 'postprocess'
INP = ROOT / 'inputs'
METRICS = ROOT.parent / 'revision_round1' / '03_analysis' / 'lp_main_results'
sys.path.insert(0, str(METRICS)); sys.path.insert(0, str(METRICS.parent))
from lp_timescale_metrics import residence, matched_by  # noqa: E402
from audit_timescale_windows import decomposition, acf_standard  # noqa: E402

CASES = ['S0', 'S1', 'S2', 'A0', 'AH', 'B0', 'BH', 'C0', 'CH']
SCEN = {'S0': 'S0', 'S1': 'S1', 'S2': 'S2', 'A0': 'S3', 'B0': 'S3', 'C0': 'S3', 'AH': 'S4', 'BH': 'S4', 'CH': 'S4'}
FLEETS = ('commercial', 'residential')
# constants of src/model.py
EL_FL_RATIO = 54.92 / 49.12
EV_LOSS = 0.0005           # Store standing_loss per hour
EV_FLOOR = 0.35 * 0.07     # MWh per vehicle (model_fixes: absolute 35 % of 70 kWh)
EV_NOM = 0.07              # nominal MWh per vehicle (old manuscript capacity basis)
TOL = 1e-3                 # MW, "nonzero" threshold
MW_PER_KGH = 0.054         # MW per kg/h at the 2050 full-load SEC 54 kWh/kg (F5_summary convention)


def interp(path: str, years) -> np.ndarray:
    pts = {int(k): float(v) for k, v in (p.split(':') for p in path.split(','))}
    ks = sorted(pts)
    return np.interp(np.asarray(years, float), ks, [pts[k] for k in ks])


def param(cfg, obj, key, default=0.):
    return cfg.get(obj, {}).get(key, {}).get('value', default)


# ---------------------------------------------------------------- shared inputs
PROF = pd.read_parquet(INP / 'profiles.parquet')
FIX = pd.read_parquet(INP / 'fixed_fleet_charging_newbase.parquet')


def re_profile(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Wind/PV p.u. exactly as model.build maps the reference year (month-day-hour, interpolate, bfill, ffill)."""
    rp = pd.read_parquet(INP / 'namie_renewables_ninja_2024.parquet')
    out = pd.DataFrame(index=index)
    keys = list(zip(index.month, index.day, index.hour))
    for col in ('solar_pu', 'wind_pu'):
        m = dict(zip(zip(rp.index.month, rp.index.day, rp.index.hour), rp[col].values))
        out[col] = pd.Series([m.get(k, np.nan) for k in keys], index=index).interpolate().bfill().ffill().clip(upper=1)
    return out


def price_series(index: pd.DatetimeIndex) -> pd.DataFrame:
    ps = pd.read_parquet(INP / 'tohoku_price_plan_ref2024.parquet')
    pm = {(y, t.month, t.day, t.hour): (p, c) for (y, t), p, c in zip(ps.index, ps['price'].values, ps['curtail_rate'].values)}
    ylast = max(k[0] for k in pm)
    v = [pm[(min(t.year, ylast), t.month, t.day, t.hour)] for t in index]
    return pd.DataFrame({'price_JPY_kWh': [a for a, _ in v], 'curt_rate': [b for _, b in v]}, index=index)


# ---------------------------------------------------------------- per-case loading
def load(case: str) -> dict:
    d = RES / f'F6__{case}'
    cmd = json.loads((d / 'build_stats.json').read_text())['command']
    cfg = json.loads((INP / f'{SCEN[case]}_parameters.json').read_text(encoding='utf-8'))
    g = pd.read_parquet(d / 'generator_dispatch.parquet')
    l = pd.read_parquet(d / 'link_input.parquet')
    s = pd.read_parquet(d / 'store_inventory.parquet')
    x = pd.read_parquet(d / 'electricity_exchange.parquet')
    idx = g.index
    yrs = idx.year.to_numpy()
    inst = pd.read_csv(d / 'installed_units.csv', index_col=0) if (d / 'installed_units.csv').exists() else None
    hu = 1e-3 if cmd.get('unit_scaling') else 1.
    # capacities (MW / kg/h / t) by year
    fixed_wind = param(cfg, 'Fukushima Revitalization OnshoreWind', 'Max Capacity') * param(cfg, 'Fukushima Revitalization OnshoreWind', 'Units')
    fixed_solar = sum(param(cfg, o, 'Units') * param(cfg, o, 'Max Capacity') for o in cfg if 'UtilityPV' in o or o == 'Namie RooftopPV')
    yidx = pd.Index(sorted(set(yrs)), name='year')
    capy = pd.DataFrame(index=yidx)
    get = (lambda k: inst[k].reindex(yidx).fillna(0.) if (inst is not None and k in inst.columns) else pd.Series(0., index=yidx))
    capy['wind_new_MW'] = get('wind') * param(cfg, 'NewOnshoreWInd OnshoreWind', 'Max Capacity')
    capy['wind_total_MW'] = fixed_wind + capy['wind_new_MW']
    capy['solar_total_MW'] = fixed_solar + get('solar') * param(cfg, 'NewUtilityPV UtilityPV', 'Max Capacity') + get('roof') * param(cfg, 'NewRooftopPV RooftopPV', 'Max Capacity')
    capy['el_kgph'] = get('electrolyzer') * param(cfg, 'Power to H2 Facility', 'Max Operating Level', 10.)
    capy['fc_MW'] = get('fuelcell') * param(cfg, 'FH2R Fuel Cell Power Station Hydrogen', 'Max Capacity', 10.)
    capy['tank_t'] = get('tank') * param(cfg, 'H2 Storage Tank', 'Max Inventory', 1000.) / 1000.
    re = re_profile(idx)
    h = pd.DataFrame(index=idx)
    h['wind_avail'] = capy['wind_total_MW'].reindex(yrs).to_numpy() * re['wind_pu'].to_numpy()
    h['solar_avail'] = capy['solar_total_MW'].reindex(yrs).to_numpy() * re['solar_pu'].to_numpy()
    h['wind'] = g['wind']; h['solar'] = g['solar']; h['hydro'] = g['hydro']
    h['biomass'] = l['biomass'] * (0.1 / (1e-3 if cmd.get('unit_scaling') else 1.))
    h['import'] = g['import']; h['export'] = g['export']
    # import and export carry the same price (no adder/deduction in F5), so simultaneous gross import + export is a
    # zero-cost wash in the LP; hourly attribution below uses net flows
    h['net_import'] = (h['import'] - h['export']).clip(lower=0); h['net_export'] = (h['export'] - h['import']).clip(lower=0)
    h['load_total'] = x['load']                       # fixed load + uncontrolled EV charging
    h['load_fixed'] = PROF['load_MW'].reindex(idx).to_numpy()
    h['ev_uncontrolled'] = h['load_total'] - h['load_fixed']
    ps = price_series(idx)
    h['price'] = ps['price_JPY_kWh']
    h['export_limit'] = cmd['market_limit_mw'] * (1 - ps['curt_rate'] * cmd.get('series_curtail_scale', 1.)).clip(0, 1)
    has_h2 = 'electrolyzer' in l.columns
    if has_h2:
        ael = interp(cmd['el_sec_path'], yrs) / 1000 / EL_FL_RATIO          # MWh/kg linear coefficient
        el_age = (cmd['el_stack_life'] - 1) / 2 if cmd.get('degradation_average') else None
        fc_age = (cmd['fc_stack_life'] - 1) / 2 if cmd.get('degradation_average') else None
        fk = interp(cmd['fc_kg_path'], yrs) * hu * (1 + cmd['fc_degradation'] * fc_age)  # t per MWh_e
        h['el_link'] = l['electrolyzer']
        h['el_aux'] = l['el_eff_aux']
        h['h2_aux'] = l['h2_aux_power'] if 'h2_aux_power' in l.columns else 0.   # F6: hot standby + start-up energy
        h['h2_prod_t'] = l['electrolyzer'] * hu / (ael * (1 + cmd['el_degradation'] * el_age))
        h['fc_h2_t'] = l['fuelcell']
        h['fc_out'] = l['fuelcell'] / fk
        # electrolyzer link capacity (MW_e) as in model: kg/h x ael x availability
        el_cap = capy['el_kgph'].reindex(yrs).to_numpy() * ael * cmd['el_availability']
        h['el_cap_MW'] = el_cap
        # minimum auxiliary energy the curve/no-load constraints require for the observed p (over feasible commitment u in
        # [p, min(C, p/b1)]); aux above this is free dumping of surplus (= curtailment), see summary el_eff_aux_slack_GWh
        p = h['el_link'].to_numpy()
        pieces = [tuple(float(v) for v in q.split(':')) for q in cmd['el_curve'].split(',')]
        nl = cmd['el_noload']
        best = np.full_like(p, np.inf)
        for frac in np.linspace(0, 1, 201):
            u = p + frac * np.maximum(np.minimum(el_cap, p / min(b for b, _ in pieces)) - p, 0)
            req = nl * u + np.maximum.reduce([np.zeros_like(p)] + [sj * (p - bj * u) for bj, sj in pieces])
            best = np.minimum(best, req)
        best[p <= 1e-9] = 0.
        h['el_aux_req_min'] = np.minimum(best, h['el_aux'])
        h['el_aux_dump_ub'] = h['el_aux'] - h['el_aux_req_min']
        h['el_elec'] = h['el_link'] + h['el_aux_req_min']
    else:
        for c in ('el_link', 'el_aux', 'h2_aux', 'h2_prod_t', 'fc_h2_t', 'fc_out', 'el_cap_MW', 'el_aux_req_min', 'el_aux_dump_ub', 'el_elec'):
            h[c] = 0.
    has_ev = 'ev_commercial_charge' in l.columns
    es, ebc, ebd = cmd['ev_station_eff'], cmd['ev_batt_charge_eff'], cmd['ev_batt_discharge_eff']
    ev = {}
    if has_ev:
        p_ev = cmd['ev_participation']
        for k in FLEETS:
            n_ctrl = PROF[k + '_vehicles'].reindex(idx) * p_ev
            av = (PROF[k + '_availability'].reindex(idx) * cmd.get('ev_availability_scale', 1)).clip(upper=1)
            ev[k] = pd.DataFrame({'ch_ac': l[f'ev_{k}_charge'], 'dis_batt': l[f'ev_{k}_discharge'], 'e': s[f'ev_{k}'],
                                  'N': n_ctrl, 'a': av, 'drive_ctrl': PROF[k + '_drive_MWh'].reindex(idx) * p_ev}, index=idx)
        h['ev_ch'] = sum(ev[k]['ch_ac'] for k in FLEETS)
        h['ev_dis_grid'] = sum(ev[k]['dis_batt'] for k in FLEETS) * ebd * es
        h['ev_ch_avail'] = sum(ev[k]['N'] * ev[k]['a'] * cmd['ev_charger_kw'] / 1000 / es for k in FLEETS)
    else:
        h['ev_ch'] = 0.; h['ev_dis_grid'] = 0.; h['ev_ch_avail'] = 0.
    # closure check of the reconstructed electricity balance
    sup = h.wind + h.solar + h.hydro + h.biomass + h['import'] + h.fc_out + h.ev_dis_grid
    dem = h.export + h.load_total + h.el_link + h.el_aux + h.h2_aux + h.ev_ch
    resid = float((sup - dem).abs().max())
    return dict(case=case, cmd=cmd, h=h, ev=ev, capy=capy, store=s, link=l, resid=resid, has_h2=has_h2, has_ev=has_ev,
                summary=json.loads((d / 'summary.json').read_text()))


# ---------------------------------------------------------------- task 1/2: timescale metrics
def h2_frame(r: dict, year: int) -> tuple[pd.DataFrame, float]:
    hu = 1e-3 if r['cmd'].get('unit_scaling') else 1.
    e = r['store']['hydrogen'] / hu
    out = r['link']['fuelcell'] / hu
    lam = 1 - (1 - float(r['cmd'].get('h2_standing_loss_per_day', 0) or 0)) ** (1 / 24)
    prev = e.shift(1).fillna(0.)
    f = pd.DataFrame({'in': (e - (1 - lam) * prev + out).clip(lower=0), 'out': out, 'stock': e, 'opening': prev})
    f = f.loc[f.index.year == year]
    cap_kg = float(r['capy'].at[year, 'tank_t']) * 1000
    f['soc'] = f['stock'] / cap_kg * 100
    return f, cap_kg


def ev_frame(r: dict, year: int, part: str) -> tuple[pd.DataFrame, float]:
    """part = 'managed' (optimised store, B/C), 'uncontrolled' (fixed profile share), 'total'.
    in = battery-side charging, out = battery-side discharge + traction, stock = energy above the 35 % x 70 kWh floor,
    SoC (%) = stored / (N x usable 63 kWh); capacity for throughput = N x nominal 70 kWh (old manuscript basis)."""
    cmd = r['cmd']; idx = r['h'].index
    eff_c = cmd['ev_station_eff'] * cmd['ev_batt_charge_eff']
    parts = []
    if part in ('managed', 'total') and r['has_ev']:
        for k in FLEETS:
            v = r['ev'][k]
            prev = v['e'].shift(1)
            inn = v['ch_ac'] * eff_c
            trac = ((1 - EV_LOSS) * prev + inn - v['dis_batt'] - v['e'])  # store balance -> traction (incl. fleet arrivals)
            parts.append(pd.DataFrame({'in': inn, 'out': (v['dis_batt'] + trac).clip(lower=0), 'e': v['e'], 'N': v['N']}))
    if part in ('uncontrolled', 'total'):
        share = 1.0 if cmd.get('ev_control') == 'fixed' else (1 - cmd['ev_participation'])
        if share > 0:
            for k in FLEETS:
                e = FIX[k + '_stored_MWh'].reindex(idx) * share
                inn = FIX[k + '_grid_charge_MW'].reindex(idx) * share * eff_c
                prev = e.shift(1)
                trac = (1 - EV_LOSS) * prev + inn - e
                parts.append(pd.DataFrame({'in': inn, 'out': trac.clip(lower=0), 'e': e,
                                           'N': PROF[k + '_vehicles'].reindex(idx) * share}))
    if not parts:
        return None, None
    tot = sum(p[['in', 'out', 'e', 'N']] for p in parts)
    tot = tot.loc[tot.index.year == year]
    f = pd.DataFrame({'in': tot['in'], 'out': tot['out'], 'stock': tot['e'] - tot['N'] * EV_FLOOR,
                      'soc': tot['e'] / (tot['N'] * EV_NOM * cmd['ev_capacity_scale']) * 100})
    f['opening'] = f['stock'].shift(1)
    cap = float(tot['N'].mean()) * EV_NOM
    return f, cap


def ts_metrics(f: pd.DataFrame, cap: float) -> dict:
    soc = f['soc'].to_numpy(float)
    total = float(f['out'].sum())
    fifo, lifo = residence(f, 'FIFO'), residence(f, 'LIFO')
    daily = f['soc'].resample('D').agg(['min', 'max'])
    monthly = f['soc'].resample('MS').mean()
    v7, v5 = decomposition(soc, 7, 4)['shares'], decomposition(soc, 5, 4)['shares']
    return {
        'capacity_basis': cap, 'annual_out': total, 'throughput_over_capacity': total / cap,
        'var_lt1d_7_28': 100 * v7[0], 'var_1to7d': 100 * v7[1], 'var_7to28d': 100 * v7[2], 'var_gt28d': 100 * v7[3],
        'var_lt1d_5_20': 100 * v5[0], 'var_1to5d': 100 * v5[1], 'var_5to20d': 100 * v5[2], 'var_gt20d': 100 * v5[3],
        'acf_12h': acf_standard(soc, 12), 'acf_24h': acf_standard(soc, 24),
        'soc_min_pct': float(soc.min()), 'soc_max_pct': float(soc.max()),
        'mean_daily_soc_range_pp': float((daily['max'] - daily['min']).mean()),
        'annual_range_monthly_mean_pp': float(monthly.max() - monthly.min()),
        'little_mean_days': float(f['stock'].mean() * len(f) / total / 24),
        'fifo_mean_days': fifo['mean_h'] / 24, 'fifo_median_days': fifo['median_h'] / 24, 'fifo_p90_days': fifo['p90_h'] / 24,
        'lifo_median_h': lifo['median_h'], 'lifo_share_le_24h': lifo['share_le_24h'],
        'fifo_share_gt_168h': fifo['share_gt_168h'], 'fifo_untracked_share': fifo['untracked_share'],
        'same_month_net_share': matched_by(f, 'MS') / total,
        'across_quarter_net_share': (total - matched_by(f, 'QS')) / total,
    }


def task_timescale(R: dict) -> pd.DataFrame:
    rows = []
    for c, r in R.items():
        for year in (2050, 2049):
            series = []
            if r['has_h2'] and r['capy'].at[year, 'tank_t'] > 0:
                series.append(('H2', h2_frame(r, year)))
            if r['has_ev']:
                series.append(('EV managed', ev_frame(r, year, 'managed')))
                series.append(('EV total fleet', ev_frame(r, year, 'total')))
            elif c[0] == 'A':
                series.append(('EV total fleet (fixed profile)', ev_frame(r, year, 'uncontrolled')))
            for name, (f, cap) in series:
                if f is None or f['out'].sum() <= 0:
                    continue
                if len(f) != 8760:
                    raise ValueError(f'{c} {name} {year}: {len(f)} hours')
                rows.append({'case': c, 'storage': name, 'year': year, **ts_metrics(f, cap)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- task 3: energy balance
FLOWS = ['wind_avail', 'wind', 'solar_avail', 'solar', 'hydro', 'biomass', 'import', 'export', 'net_import', 'net_export', 'load_fixed', 'ev_uncontrolled',
         'ev_ch', 'ev_dis_grid', 'el_link', 'el_aux', 'h2_aux', 'el_aux_req_min', 'el_aux_dump_ub', 'el_elec', 'fc_out']


def balance_rows(h: pd.DataFrame) -> dict:
    gwh = {k: float(h[k].sum()) / 1000 for k in FLOWS}
    avail = gwh['wind_avail'] + gwh['solar_avail']
    used = gwh['wind'] + gwh['solar']
    cur = avail - used
    el = h['el_elec']
    el_imp = np.minimum(el, h['net_import'])                     # import-first attribution per hour, net import
    ev_imp = np.minimum(h['ev_ch'], h['net_import'])
    at_lim = (h['net_export'] >= h['export_limit'] - TOL) & (h['export_limit'] > TOL)
    out = {**{k + '_GWh': v for k, v in gwh.items()},
           'h2_prod_t': float(h['h2_prod_t'].sum()), 'fc_h2_t': float(h['fc_h2_t'].sum()),
           'vre_curtail_GWh': cur, 'vre_curtail_rate': cur / avail if avail else np.nan,
           'wind_curtail_rate': 1 - gwh['wind'] / gwh['wind_avail'] if gwh['wind_avail'] else np.nan,
           'solar_curtail_rate': 1 - gwh['solar'] / gwh['solar_avail'] if gwh['solar_avail'] else np.nan,
           'curtail_incl_aux_dump_ub_rate': (cur + gwh['el_aux_dump_ub']) / avail if avail else np.nan,
           'el_from_import_GWh': float(el_imp.sum()) / 1000,
           'el_import_share': float(el_imp.sum() / el.sum()) if el.sum() > 0 else np.nan,
           'ev_ch_from_import_share': float(ev_imp.sum() / h['ev_ch'].sum()) if h['ev_ch'].sum() > 0 else np.nan,
           'net_export_at_limit_hours': int(at_lim.sum()),
           'gross_export_at_limit_hours': int(((h['export'] >= h['export_limit'] - TOL) & (h['export_limit'] > TOL)).sum()),
           'hours_import_and_export': int(((h['import'] > TOL) & (h['export'] > TOL)).sum()),
           'simult_import_export_GWh': float(np.minimum(h['import'], h['export']).sum()) / 1000}
    return out


def task_balance(R: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for c, r in R.items():
        h = r['h']
        for y, hy in h.groupby(h.index.year):
            rows.append({'case': c, 'year': y, **balance_rows(hy)})
    by_year = pd.DataFrame(rows)
    summ = []
    for c, r in R.items():
        h = r['h']
        summ.append({'case': c, 'period': '2050', **balance_rows(h.loc[h.index.year == 2050])})
        summ.append({'case': c, 'period': '2025-2050', **balance_rows(h)})
        summ[-1]['el_aux_slack_GWh_summary_json'] = r['summary'].get('h2_uc', {}).get('el_eff_aux_slack_GWh', np.nan)
        summ[-1]['balance_residual_max_MW'] = r['resid']
    return by_year, pd.DataFrame(summ)


# ---------------------------------------------------------------- task 4: mechanism
def task_mechanism(R: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, hod = [], []
    for c in ('S2', 'AH', 'BH', 'CH', 'C0', 'B0', 'A0', 'S1'):
        r = R[c]; h = r['h'].loc[r['h'].index.year == 2050]
        el = h['el_elec']; ev = h['ev_ch']; v2g = h['ev_dis_grid']; fc = h['fc_out']
        X = (h['net_export'] >= h['export_limit'] - TOL) & (h['export_limit'] > TOL)  # net export at interface limit
        K = (h['wind_avail'] + h['solar_avail'] - h['wind'] - h['solar']) > TOL       # VRE curtailed
        I = h['net_import'] > TOL
        S = X | K                                                                   # surplus hours
        hi = (ev >= 0.5 * h['ev_ch_avail']) & (h['ev_ch_avail'] > 0) & (ev > TOL)    # managed EV charging >= 50 % of plug-in limit
        sh = lambda s, m: float(s[m].sum() / s.sum()) if s.sum() > 0 else np.nan
        cap_kgph = float(r['capy'].at[2050, 'el_kgph'])
        el_on = h['el_link'] > TOL
        row = {'case': c,
               'hours_export_at_limit': int(X.sum()), 'hours_vre_curtailed': int(K.sum()), 'hours_surplus': int(S.sum()),
               'hours_import': int(I.sum()),
               'surplus_energy_GWh': float((h['net_export'][S].sum() + (h['wind_avail'] + h['solar_avail'] - h['wind'] - h['solar'])[S].sum())) / 1000,
               'el_kgph': cap_kgph, 'el_MW_54': cap_kgph * MW_PER_KGH,
               'el_elec_GWh': float(el.sum()) / 1000, 'h2_prod_t': float(h['h2_prod_t'].sum()),
               'el_FLH_h2': float(h['h2_prod_t'].sum() * 1000 / cap_kgph) if cap_kgph else np.nan,
               'el_FLH_link': float(h['el_link'].sum() / h['el_cap_MW'].max()) if cap_kgph else np.nan,
               'el_hours_on': int(el_on.sum()),
               'el_share_in_X': sh(el, X), 'el_share_in_K': sh(el, K), 'el_share_in_surplus': sh(el, S), 'el_share_in_import': sh(el, I),
               'ev_ch_GWh': float(ev.sum()) / 1000,
               'ev_share_in_X': sh(ev, X), 'ev_share_in_K': sh(ev, K), 'ev_share_in_surplus': sh(ev, S), 'ev_share_in_import': sh(ev, I),
               'el_share_in_ev_high_hours': sh(el, hi), 'hours_ev_high': int(hi.sum()),
               'hours_el_and_ev_ch': int((el_on & (ev > TOL)).sum()),
               'jaccard_el_ev_hours': float((el_on & (ev > TOL)).sum() / max((el_on | (ev > TOL)).sum(), 1)),
               'corr_el_ev_ch': float(np.corrcoef(el, ev)[0, 1]) if el.std() > 0 and ev.std() > 0 else np.nan,
               'price_el': float((el * h.price).sum() / el.sum()) if el.sum() > 0 else np.nan,
               'price_ev_ch': float((ev * h.price).sum() / ev.sum()) if ev.sum() > 0 else np.nan,
               'price_v2g': float((v2g * h.price).sum() / v2g.sum()) if v2g.sum() > 0 else np.nan,
               'price_fc': float((fc * h.price).sum() / fc.sum()) if fc.sum() > 0 else np.nan,
               'price_mean': float(h.price.mean()),
               'v2g_GWh': float(v2g.sum()) / 1000, 'fc_out_GWh': float(fc.sum()) / 1000,
               'fc_share_in_v2g_hours': sh(fc, v2g > TOL), 'v2g_share_in_fc_hours': sh(v2g, fc > TOL),
               'hours_fc_and_v2g': int(((fc > TOL) & (v2g > TOL)).sum()),
               'el_share_in_v2g_hours': sh(el, v2g > TOL), 'fc_share_in_ev_ch_hours': sh(fc, ev > TOL),
               'corr_fc_v2g': float(np.corrcoef(fc, v2g)[0, 1]) if fc.std() > 0 and v2g.std() > 0 else np.nan,
               'surplus_absorbed_el_GWh': float(el[S].sum()) / 1000, 'surplus_absorbed_ev_GWh': float(ev[S].sum()) / 1000}
        rows.append(row)
        g = pd.DataFrame({'el_elec': el, 'ev_ch': ev, 'v2g': v2g, 'fc_out': fc, 'net_export': h['net_export'], 'net_import': h['net_import'],
                          'curtail': h['wind_avail'] + h['solar_avail'] - h['wind'] - h['solar'], 'price': h.price}).groupby(h.index.hour).mean()
        g.insert(0, 'case', c); g.index.name = 'hour'
        hod.append(g.reset_index())
    return pd.DataFrame(rows), pd.concat(hod)


# ---------------------------------------------------------------- task 5: feasibility
def task_feasibility(R: dict) -> pd.DataFrame:
    rows = []
    for c in ('C0', 'CH', 'B0', 'BH'):
        r = R[c]; cmd = r['cmd']
        es, ebd = cmd['ev_station_eff'], cmd['ev_batt_discharge_eff']
        ecap = EV_NOM * cmd['ev_capacity_scale']
        dep_h = (cmd['ev_departure_hour'] - 1) % 24
        cfg = json.loads((INP / f'{SCEN[c]}_parameters.json').read_text(encoding='utf-8'))
        sim_all = None
        for k, obj in (('commercial', 'EV JR Namie Commercial Area'), ('residential', 'EV Residential Cars')):
            v = r['ev'][k]
            maxsoc = param(cfg, obj, 'Max SoC') / 100
            lim = v['N'] * v['a'] * cmd['ev_charger_kw'] / 1000
            lhs = es * v['ch_ac'] + ebd * v['dis_batt']
            floor = pd.Series(EV_FLOOR, index=v.index)
            dep = v.index.hour == dep_h
            floor[dep] = max(EV_FLOOR, cmd['ev_departure_soc'] * ecap)
            emin, emax = v['N'] * floor, v['N'] * ecap * maxsoc
            both = (v['ch_ac'] > TOL) & (v['dis_batt'] > TOL)
            simult = np.minimum(v['ch_ac'] * es * cmd['ev_batt_charge_eff'], v['dis_batt'])   # battery side
            soc63 = v['e'] / (v['N'] * ecap) * 100
            for period, m in (('2025-2050', slice(None)), ('2050', v.index.year == 2050)):
                vv = v.loc[m] if period == '2050' else v
                mm = (v.index.year == 2050) if period == '2050' else np.ones(len(v), bool)
                rows.append({'case': c, 'fleet': k, 'period': period,
                             'max_power_violation_MW': float((lhs - lim)[mm].max()),
                             'hours_power_limit_binding': int(((lhs - lim)[mm] > -1e-4).sum()),
                             'max_floor_violation_MWh': float((emin - v['e'])[mm].max()),
                             'max_cap_violation_MWh': float((v['e'] - emax)[mm].max()),
                             'max_departure_violation_MWh': float((emin - v['e'])[mm & dep].max()),
                             'soc_min_pct_of_63kWh': float(soc63[mm].min()), 'soc_max_pct_of_63kWh': float(soc63[mm].max()),
                             'soc_min_pct_of_70kWh': float((v['e'] / (v['N'] * EV_NOM) * 100)[mm].min()),
                             'soc_at_departure_min_pct_of_63kWh': float(soc63[mm & dep].min()),
                             'hours_ch_and_dis': int(both[mm].sum()),
                             'simult_energy_MWh_batt': float(simult[mm].sum()),
                             'discharge_MWh_batt': float(vv['dis_batt'].sum()),
                             'simult_share_of_discharge': float(simult[mm].sum() / vv['dis_batt'].sum()) if vv['dis_batt'].sum() > 0 else np.nan,
                             'max_simult_MW_batt': float(simult[mm].max())})
        # cross-fleet: one fleet charges while the other discharges (energy moved between fleets through the grid bus)
        a, b = r['ev']['commercial'], r['ev']['residential']
        x1 = np.minimum(a['ch_ac'], b['dis_batt'] * ebd * es) + np.minimum(b['ch_ac'], a['dis_batt'] * ebd * es)
        for period, mm in (('2025-2050', np.ones(len(a), bool)), ('2050', a.index.year == 2050)):
            dis = (a['dis_batt'] + b['dis_batt'])[mm].sum() * ebd * es
            rows.append({'case': c, 'fleet': 'cross-fleet', 'period': period,
                         'hours_ch_and_dis': int((x1[mm] > TOL).sum()), 'simult_energy_MWh_batt': float(x1[mm].sum()),
                         'discharge_MWh_batt': float(dis), 'simult_share_of_discharge': float(x1[mm].sum() / dis) if dis > 0 else np.nan})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- task 6: capacities
def task_capacity(R: dict, mech: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for c, r in R.items():
        cy = r['capy']
        for y in (2030, 2040, 2045, 2050):
            rows.append({'case': c, 'year': y, 'wind_new_MW': cy.at[y, 'wind_new_MW'], 'wind_total_MW': cy.at[y, 'wind_total_MW'],
                         'el_kgph': cy.at[y, 'el_kgph'], 'el_MW_at_54kWh_per_kg': cy.at[y, 'el_kgph'] * MW_PER_KGH,
                         'fc_MW': cy.at[y, 'fc_MW'], 'tank_t': cy.at[y, 'tank_t']})
    cap = pd.DataFrame(rows)
    flh = []
    for c, r in R.items():
        h = r['h'].loc[r['h'].index.year == 2050]
        k = float(r['capy'].at[2050, 'el_kgph']); fcmw = float(r['capy'].at[2050, 'fc_MW'])
        flh.append({'case': c, 'year': 2050,
                    'el_FLH_h2_output': float(h['h2_prod_t'].sum() * 1000 / k) if k else np.nan,
                    'el_FLH_elec_at_54': float(h['el_elec'].sum() / (k * MW_PER_KGH)) if k else np.nan,
                    'el_FLH_link_cap': float(h['el_link'].sum() / h['el_cap_MW'].max()) if k else np.nan,
                    'fc_FLH': float(h['fc_out'].sum() / fcmw) if fcmw else np.nan})
    return cap.merge(pd.DataFrame(flh), on=['case', 'year'], how='left')


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    R = {c: load(c) for c in CASES}
    for c, r in R.items():
        print(c, 'balance residual MW', f"{r['resid']:.2e}")
    ts = task_timescale(R)
    ts.to_csv(OUT / 'timescale_metrics.csv', index=False)
    win = ts[['case', 'storage', 'year', 'var_lt1d_7_28', 'var_1to7d', 'var_7to28d', 'var_gt28d',
              'var_lt1d_5_20', 'var_1to5d', 'var_5to20d', 'var_gt20d']]
    win.to_csv(OUT / 'window_sensitivity.csv', index=False)
    by_year, summ = task_balance(R)
    by_year.to_csv(OUT / 'energy_balance_by_year.csv', index=False)
    summ.to_csv(OUT / 'energy_balance_summary.csv', index=False)
    mech, hod = task_mechanism(R)
    mech.to_csv(OUT / 'mechanism_2050.csv', index=False)
    hod.to_csv(OUT / 'mechanism_hour_of_day_2050.csv', index=False)
    feas = task_feasibility(R)
    feas.to_csv(OUT / 'ev_feasibility.csv', index=False)
    cap = task_capacity(R, mech)
    cap.to_csv(OUT / 'capacity_summary.csv', index=False)
    # cross-check with the earlier hydrogen metrics (src/pypsa_timescale.py)
    ref = json.loads((RES / 'pypsa_timescale_metrics.json').read_text())
    chk = {}
    for c in ('S2', 'AH', 'BH', 'CH'):
        m = ts[(ts.case == c) & (ts.storage == 'H2') & (ts.year == 2050)].iloc[0]
        o = ref.get(f'F6__{c}')
        if o:
            chk[c] = {'var_shares_new': [round(m[k], 1) for k in ('var_lt1d_7_28', 'var_1to7d', 'var_7to28d', 'var_gt28d')],
                      'var_shares_ref': o['variance_shares_lt1d_1to7d_7to28d_gt28d'],
                      'fifo_mean_days_new': m['fifo_mean_days'], 'fifo_mean_days_ref': o['fifo_mean_days']}
    (OUT / 'check_vs_pypsa_timescale.json').write_text(json.dumps(chk, indent=2))
    pd.set_option('display.width', 250); pd.set_option('display.max_columns', 60)
    print(ts[ts.year == 2050].round(3).T.to_string())
    print(summ.round(3).T.to_string())
    print(mech.round(3).T.to_string())
    print(feas.round(4).to_string())
    print(cap.round(2).to_string())
    print(json.dumps(chk, indent=1))


if __name__ == '__main__':
    main()
