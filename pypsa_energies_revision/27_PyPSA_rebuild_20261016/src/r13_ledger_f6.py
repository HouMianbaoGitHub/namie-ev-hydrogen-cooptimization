"""R1.3 auditable present-value ledger of the F6 default (--all-annuity --no-perpetuity, horizon 2025-2050).
Every objective term is rebuilt from saved outputs and checked against the solver NPV (npv_billion_JPY):
- electrolyzer start-up cost (F6): taken from the solver's own term h2_startup_million_JPY (start-ups are not saved
  hourly), shown as its own line and booked in 2040-2050 (no hydrogen is built before 2041 in any F6 case);
- operation: hourly export/import x price, electrolyzer VOM (4 JPY/kg x kg, kWh/kg path), V2G throughput cost, biomass sale
  revenue and year-end biomass stock holding, all discounted with 1.03^-(y-2024) (2050 = one year, no perpetuity);
- investment: per build, capital-recovery annuity and FO&M (r13_salvage.parts, mirroring model.investment_pv); the charged
  capital (annuities 2025-2050) is shown as full-life capital PV minus the salvage value at end-2050 (PV of the post-2050
  capital annuities). Per build, charged capital + charged FO&M is checked against units x model.investment_pv.
Outputs (billion JPY, PV 2024, 3%) in results/r13_ledger_f6/: r13f6_table.csv, r13f6_detail.csv, r13f6_increments.csv,
r13f6_by_period.csv, r13f6_annual_<case>.csv, r13f6_check.csv, r13f6_breakeven.csv, table_r13_f6.md.
Usage: python r13_ledger_f6.py"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import model as M  # noqa: E402
from r13_salvage import parts  # noqa: E402

D = ROOT / 'results' / 'f6_20261030'
OUT = ROOT / 'results' / 'r13_ledger_f6'
CASES = ['S0', 'S1', 'S2', 'A0', 'AH', 'B0', 'BH', 'C0', 'CH']
H2 = ('electrolyzer', 'fuelcell', 'tank')
SPLIT = 2040  # periods 2025-2039 / 2040-2050: no hydrogen is built before 2041 in any F6 case
d24 = lambda t: 1.03 ** -(t - 2024)


def prices(snapshots, path):
    ps = pd.read_parquet(path)
    pm = {(y, t.month, t.day, t.hour): p for (y, t), p in zip(ps.index, ps['price'].values)}
    ylast = max(y for y, *_ in pm)
    return pd.Series([pm[(min(t.year, ylast), t.month, t.day, t.hour)] * 1000 for t in snapshots], index=snapshots)  # JPY/MWh


def operation(d, args):
    """Annual undiscounted operating cash flows (billion JPY, + = revenue)."""
    gen = pd.read_parquet(d / 'generator_dispatch.parquet')
    link = pd.read_parquet(d / 'link_input.parquet')
    sto = pd.read_parquet(d / 'store_inventory.parquet')
    snaps = gen.index
    yr = pd.Series(snaps.year, index=snaps)
    p = prices(snaps, ROOT / 'inputs' / Path(args.price_series).name) * args.price_scale
    p_imp = p + args.import_adder_jpy_per_kwh * 1000
    p_exp = p - args.export_deduction_jpy_per_kwh * 1000
    fp = pd.read_csv(ROOT / 'inputs' / 'historical_s4/DataFiles/Hydrogen_Biomass_Market_Benchmark_Price_yearly.csv').set_index('year')['BiomassMarket']
    bu = 1e-3 if args.unit_scaling else 1.
    zero = pd.Series(0., index=snaps)
    if 'electrolyzer' in link:
        ael = yr.map(lambda y: M._interp(M.parse_path(args.el_sec_path), y) / 1000 / M.EL_FL_RATIO) if args.el_sec_path else args.h2_electrolysis_mwh_per_kg
        el_vom = -link['electrolyzer'] * 4 / ael
    else:
        el_vom = zero
    dis = [c for c in link if c.endswith('_discharge')]
    hourly = pd.DataFrame({
        'export_revenue': gen['export'] * p_exp,
        'purchases': -gen['import'] * p_imp,
        'electrolyzer_vom': el_vom,
        'v2g_throughput_cost': -link[dis].sum(axis=1) * args.v2g_cost_jpy_per_kwh * 1000 if dis else zero,
        'biomass_sales': gen['biomass_sale'] * yr.map(fp) / bu if 'biomass_sale' in gen else zero,
    }) / 1e9
    annual = hourly.groupby(yr).sum()
    annual.index.name = 'year'
    annual['biomass_stock_holding'] = [-sto.loc[sto.index.year == y, 'biomass_stock'].iloc[-1] * 10 / bu / 1e9 for y in annual.index]
    return annual


def investment(d, args, s):
    """Per build: capital full life / charged / salvage, FO&M charged; annual charged flows (undiscounted) by payment year."""
    f = d / 'annual_build.csv'
    if not f.exists():
        return pd.DataFrame(columns=['tech', 'year', 'units', 'life', 'capital_full_life', 'capital_charged', 'fom_charged', 'salvage']), pd.DataFrame(), 0.
    build = pd.read_csv(f, index_col=0)
    ann = M.load_annuity(ROOT / 'inputs', args.scenario)
    pv = {(r['object'], int(r['year'])): r['pv_per_unit'] for r in ann}
    coeff = M.investment_pv(args, ann)
    rows, flows, solver_inv = [], {}, 0.
    for y in build.index:
        for k in build.columns:
            b = float(build.at[y, k])
            solver_inv += b * coeff[(M.TECH[k][0], int(y))] / 1e9
            if abs(b) < 1e-12:
                continue
            acap, afom, L = parts(k, int(y), args, pv)
            life = range(int(y), int(y) + L)
            inh = [t for t in life if t <= M.HEND]
            r = {'tech': k, 'year': int(y), 'units': b, 'life': L,
                 'capital_full_life': b * acap * sum(map(d24, life)) / 1e9,
                 'capital_charged': b * acap * sum(map(d24, inh)) / 1e9,
                 'fom_charged': b * afom * sum(map(d24, inh)) / 1e9}
            assert abs(r['capital_charged'] + r['fom_charged'] - b * coeff[(M.TECH[k][0], int(y))] / 1e9) < 1e-9 * max(1., r['capital_charged']), (k, y)
            rows.append(r)
            for t in inh:  # undiscounted annual payments
                flows[(t, f'{k}_capital')] = flows.get((t, f'{k}_capital'), 0.) - b * acap / 1e9
                flows[(t, f'{k}_fom')] = flows.get((t, f'{k}_fom'), 0.) - b * afom / 1e9
    r = pd.DataFrame(rows)
    r['salvage'] = r.capital_full_life - r.capital_charged
    resid_inv = solver_inv - s['objective_ledger']['investment_and_fixed_million_JPY'] / 1e3
    return r, pd.Series(flows).unstack(fill_value=0.), resid_inv


def ledger(case):
    d = D / f'F6__{case}'
    s = json.loads((d / 'summary.json').read_text())
    args = SimpleNamespace(**s['command'])
    assert args.all_annuity and args.no_perpetuity and not args.perpetuity and args.extend_to == 2050
    M.STATIC, M.PERP, M.YEND = None, False, args.extend_to
    M.HEND = args.end_year or M.YEND
    op = operation(d, args)
    byb, flows, resid_inv = investment(d, args, s)
    assert byb.empty or set(byb.tech) <= {'wind', *H2}, set(byb.tech)  # only wind and hydrogen are built in F6
    # annual ledger (undiscounted and discounted)
    annual = op.join(flows, how='left').fillna(0.)
    w = pd.Series(annual.index.map(d24), index=annual.index)
    pv_annual = annual.mul(w, axis=0)
    det = pv_annual.sum()
    # check the operating part against the solver's own ledger terms
    ol = s['objective_ledger']
    op_solver = -(ol['Generator_operation_million_JPY'] + ol['Link_operation_million_JPY'] + ol['fuel_holding_million_JPY'] + ol.get('h2_startup_million_JPY', 0.)) / 1e3
    startup = -ol.get('h2_startup_million_JPY', 0.) / 1e3
    if startup:
        assert not byb.empty and byb.loc[byb.tech.isin(H2), 'year'].min() >= SPLIT, case
    resid_op = pv_annual[op.columns].to_numpy().sum() + startup - op_solver
    g = lambda techs, col: -byb.loc[byb.tech.isin(techs), col].sum() if not byb.empty else 0.
    row = {
        'export_revenue': det['export_revenue'],
        'purchases': det['purchases'],
        'operating_net': det[['electrolyzer_vom', 'v2g_throughput_cost', 'biomass_sales', 'biomass_stock_holding']].sum(),
        'h2_startup': startup,
        'wind_capital_full_life': g(['wind'], 'capital_full_life'),
        'wind_salvage_2050': -g(['wind'], 'salvage'),
        'wind_capital_charged': g(['wind'], 'capital_charged'),
        'wind_fom': g(['wind'], 'fom_charged'),
        'h2_capital_full_life': g(H2, 'capital_full_life'),
        'h2_salvage_2050': -g(H2, 'salvage'),
        'h2_capital_charged': g(H2, 'capital_charged'),
        'h2_fom': g(H2, 'fom_charged'),
    }
    detail = dict(row)
    for c in ('electrolyzer_vom', 'v2g_throughput_cost', 'biomass_sales', 'biomass_stock_holding'):
        detail[c] = det[c]
    for k in H2:
        for col, lab in (('capital_full_life', 'capital_full_life'), ('salvage', 'salvage_2050'), ('capital_charged', 'capital_charged'), ('fom_charged', 'fom')):
            v = g([k], col)
            detail[f'{k}_{lab}'] = -v if col == 'salvage' else v
    flows_sum = [k for k in row if not k.endswith(('full_life', 'salvage_2050'))]
    npv = sum(row[k] for k in flows_sum)
    row['NPV'] = npv
    detail['NPV'] = npv
    chk = {'ledger_npv': npv, 'solver_npv': s['npv_billion_JPY'], 'residual': npv - s['npv_billion_JPY'],
           'residual_operation': resid_op, 'residual_investment': resid_inv,
           'salvage_identity': (row['wind_capital_full_life'] + row['wind_salvage_2050'] - row['wind_capital_charged'])
           + (row['h2_capital_full_life'] + row['h2_salvage_2050'] - row['h2_capital_charged'])}
    # periods: discounted flows by payment year; salvage booked at end-2050
    per = {}
    for lab, sel in ((f'2025-{SPLIT - 1}', pv_annual.index < SPLIT), (f'{SPLIT}-2050', pv_annual.index >= SPLIT)):
        x = pv_annual[sel].sum()
        cap = lambda ks: sum(x.get(f'{k}_capital', 0.) for k in ks)
        fom = lambda ks: sum(x.get(f'{k}_fom', 0.) for k in ks)
        per[lab] = {'export_revenue': x['export_revenue'], 'purchases': x['purchases'],
                    'operating_net': x[['electrolyzer_vom', 'v2g_throughput_cost', 'biomass_sales', 'biomass_stock_holding']].sum(),
                    'h2_startup': startup if lab.startswith(str(SPLIT)) else 0.,
                    'wind_capital_charged': cap(['wind']), 'wind_fom': fom(['wind']),
                    'h2_capital_charged': cap(H2), 'h2_fom': fom(H2)}
        per[lab]['NPV'] = sum(per[lab].values())
    pv_annual = pv_annual.assign(discount_factor=w)
    return row, detail, chk, per, pv_annual, byb


LABELS = [
    ('export_revenue', 'Electricity export revenue', 0),
    ('purchases', 'Electricity purchases', 0),
    ('operating_net', 'Operating costs (electrolyzer VOM, V2G throughput, biomass)', 0),
    ('h2_startup', 'Electrolyzer start-up wear (solver term)', 0),
    ('wind_capital_full_life', 'Wind: full-life capital cost', 1),
    ('wind_salvage_2050', 'Wind: less salvage value at end-2050 (credit)', 1),
    ('wind_capital_charged', 'Wind: capital charged to 2050', 0),
    ('wind_fom', 'Wind: fixed O&M to 2050', 0),
    ('h2_capital_full_life', 'Hydrogen: full-life capital cost', 1),
    ('h2_salvage_2050', 'Hydrogen: less salvage value at end-2050 (credit)', 1),
    ('h2_capital_charged', 'Hydrogen: capital charged to 2050', 0),
    ('h2_fom', 'Hydrogen: fixed O&M to 2050', 0),
    ('NPV', '**NPV**', 0),
]
INCR = [('S2-S1', 'S2', 'S1'), ('CH-C0', 'CH', 'C0'), ('AH-A0', 'AH', 'A0'), ('C0-A0', 'C0', 'A0'),
        ('B0-A0', 'B0', 'A0'), ('C0-B0', 'C0', 'B0')]


def md_table(df, cols, fmt='{:.2f}'):
    lines = ['| Item | ' + ' | '.join(cols) + ' |', '|---|' + '---:|' * len(cols)]
    for key, lab, sub in LABELS:
        if key not in df.index:
            continue
        name = ('&nbsp;&nbsp;' + lab) if sub else lab
        vals = [fmt.format(df.at[key, c]) for c in cols]
        if key == 'NPV':
            vals = [f'**{v}**' for v in vals]
        lines.append(f'| {name} | ' + ' | '.join(vals) + ' |')
    return '\n'.join(lines)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, details, checks, pers, builds = {}, {}, {}, {}, []
    for c in CASES:
        row, detail, chk, per, pva, byb = ledger(c)
        rows[c], details[c], checks[c] = row, detail, chk
        for lab, v in per.items():
            pers[(c, lab)] = v
        pva.to_csv(OUT / f'r13f6_annual_{c}.csv')
        if not byb.empty:
            builds.append(byb.assign(case=c))
        print(f"{c}: ledger {chk['ledger_npv']:.6f}  solver {chk['solver_npv']:.6f}  residual {chk['residual']:.2e}"
              f"  (operation {chk['residual_operation']:.1e}, investment {chk['residual_investment']:.1e})", flush=True)
        assert abs(chk['residual']) < 1e-6, c
    tab = pd.DataFrame(rows)
    tab.to_csv(OUT / 'r13f6_table.csv')
    pd.DataFrame(details).to_csv(OUT / 'r13f6_detail.csv')
    pd.DataFrame(checks).T.to_csv(OUT / 'r13f6_check.csv')
    pd.concat(builds).to_csv(OUT / 'r13f6_by_build.csv', index=False)
    inc = pd.DataFrame({n: tab[a] - tab[b] for n, a, b in INCR})
    inc['(CH-C0)-(AH-A0)'] = inc['CH-C0'] - inc['AH-A0']
    inc['CH-BH'] = tab['CH'] - tab['BH']
    inc.to_csv(OUT / 'r13f6_increments.csv')
    per = pd.DataFrame(pers)
    per.to_csv(OUT / 'r13f6_by_period.csv')
    pinc = {}
    for lab in per.columns.get_level_values(1).unique():
        for n, a, b in INCR[:3] + INCR[3:4]:
            pinc[(n, lab)] = per[(a, lab)] - per[(b, lab)]
    pinc = pd.DataFrame(pinc)
    pinc.to_csv(OUT / 'r13f6_by_period_increments.csv')

    # break-even of bidirectional chargers, JPY per managed vehicle per year
    prof = pd.read_parquet(ROOT / 'inputs' / 'profiles.parquet')
    part = json.loads((D / 'F6__C0' / 'summary.json').read_text())['command']['ev_participation']
    nman = ((prof.commercial_vehicles + prof.residential_vehicles).groupby(prof.index.year).mean() * part).loc[2025:2050]
    dw = pd.Series({y: d24(y) for y in nman.index})
    af = dw.sum()  # 2025-2050 annuity factor at 3%, = (1 - 1.03^-26)/0.03
    veh_years = (dw * nman).sum()  # discounted managed vehicle-years
    be = []
    for n, a, b in [('C0-B0', 'C0', 'B0'), ('CH-BH', 'CH', 'BH'), ('B0-A0', 'B0', 'A0'), ('BH-AH', 'BH', 'AH')]:
        dpv = tab.at['NPV', a] - tab.at['NPV', b]
        be.append({'increment': n, 'pv_billion_JPY': dpv, 'annuity_billion_JPY_per_yr': dpv / af,
                   'JPY_per_managed_vehicle_yr_levelized': dpv * 1e9 / veh_years,
                   'JPY_per_managed_vehicle_yr_2050_fleet': dpv * 1e9 / af / nman[2050],
                   'annuity_factor': af, 'discounted_managed_vehicle_years': veh_years,
                   'weighted_mean_managed_vehicles': veh_years / af, 'managed_vehicles_2050': nman[2050]})
    be = pd.DataFrame(be)
    be.to_csv(OUT / 'r13f6_breakeven.csv', index=False)
    nman.rename('managed_vehicles').to_csv(OUT / 'r13f6_managed_vehicles.csv')

    # markdown
    chk = pd.DataFrame(checks).T
    md = ['# R1.3 present-value ledger, F6 default (billion JPY, PV 2024, 3%)', '',
          'Horizon 2025-2050, every asset paid as a finite-life annuity (capital recovery + fixed O&M) from its build year to 2050; '
          'no perpetuity (2050 weighted as one year). Capital charged = full-life capital cost minus the salvage value at end-2050 '
          '(PV of the capital-recovery annuities falling after 2050). Indented lines are components of the line below them; '
          'NPV = export revenue + purchases + operating + electrolyzer start-up wear + capital charged + fixed O&M. Revenues positive, costs negative.', '',
          '## Table 1. Ledger by case', '', md_table(tab, CASES), '',
          'Residual (ledger NPV - solver NPV), billion JPY: ' + ', '.join(f'{c} {chk.at[c, "residual"]:.1e}' for c in CASES), '',
          '## Table 2. Increments', '', md_table(inc, list(inc.columns)), '']
    md += ['## Table 3. Flows by period (payment year; salvage enters the capital charged)', '']
    for lab in per.columns.get_level_values(1).unique():
        sub = per.xs(lab, axis=1, level=1)
        md += [f'### {lab}', '', md_table(sub, CASES), '']
    md += ['### Hydrogen and V2G increments by period', '']
    for lab in pinc.columns.get_level_values(1).unique():
        md += [f'**{lab}**', '', md_table(pinc.xs(lab, axis=1, level=1), list(pinc.xs(lab, axis=1, level=1).columns)), '']
    md += ['## Table 4. Bidirectional-charger break-even', '',
           '| Increment | PV (bn JPY) | Annuity 2025-2050 (M JPY/yr) | JPY per managed vehicle-yr (levelized) | JPY per vehicle-yr (2050 fleet) |',
           '|---|---:|---:|---:|---:|']
    for r in be.itertuples():
        md.append(f'| {r.increment} | {r.pv_billion_JPY:.2f} | {r.annuity_billion_JPY_per_yr * 1e3:.1f} | '
                  f'{r.JPY_per_managed_vehicle_yr_levelized:,.0f} | {r.JPY_per_managed_vehicle_yr_2050_fleet:,.0f} |')
    md += ['', f'Managed vehicles = {part} x (commercial + residential fleet) per year, inputs/profiles.parquet '
           f'(columns commercial_vehicles, residential_vehicles; model.py multiplies them by --ev-participation). '
           f'Managed fleet 2025 {nman[2025]:,.0f}, 2050 {nman[2050]:,.0f}; discount-weighted mean {veh_years / af:,.0f}. '
           f'Levelized = PV / sum_t 1.03^-(t-2024) N_t (t = 2025-2050) = annuity over 2025-2050 (factor {af:.3f}) / weighted mean fleet; '
           'same method as the F3 value (28,600 JPY with F3 perpetuity weights).', '']
    (OUT / 'table_r13_f6.md').write_text('\n'.join(md), encoding='utf-8')
    pd.set_option('display.width', 250)
    print(tab.round(3).to_string())
    print(inc.round(3).to_string())
    print(per.round(3).to_string())
    print(be.round(4).to_string())


if __name__ == '__main__':
    main()
