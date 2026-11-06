"""Print the Markdown table bodies used in SI_S11-S14 from the si_data CSVs (run the si_s1x_*.py scripts first).
Usage: python si_tables_md.py > si_tables_md.txt
"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RES = HERE.parents[2] / '27_PyPSA_rebuild_20261016' / 'results'
f1 = lambda x: f'{x:.1f}'
f2 = lambda x: f'{x:.2f}'
neg = lambda s: s.replace('-', '−') if s.startswith('-') else s


def row(cells):
    return '| ' + ' | '.join(cells) + ' |'


print('### S11.1 / S11.2 window and year')
w = pd.read_csv(HERE / 'si_s11_window_year.csv')
lab = {('S2', 'H2'): 'H~2~ S2', ('AH', 'H2'): 'H~2~ AH', ('BH', 'H2'): 'H~2~ BH', ('CH', 'H2'): 'H~2~ CH',
       ('A0', 'EV total fleet (fixed profile)'): 'EV A (input profile)', ('B0', 'EV managed'): 'EV B0',
       ('BH', 'EV managed'): 'EV BH', ('C0', 'EV managed'): 'EV C0', ('CH', 'EV managed'): 'EV CH'}
order = list(lab)
w = w.set_index(['case', 'storage']).loc[order]
for y in (2050, 2049):
    print(f'-- {y}')
    for k, r in w.iterrows():
        a = ' / '.join(f1(r[f'{c}_{y}']) for c in ('var_lt1d_7_28', 'var_1to7d', 'var_7to28d', 'var_gt28d'))
        b = ' / '.join(f1(r[f'{c}_{y}']) for c in ('var_lt1d_5_20', 'var_1to5d', 'var_5to20d', 'var_gt20d'))
        print(row([lab[k], a, b, f2(r[f'fifo_mean_days_{y}'])]))
print('-- max |2050-2049|')
for k, r in w.iterrows():
    print(lab[k], f1(r.max_abs_diff_2050_2049_pp))

print('### S11.3 sensitivity')
s = pd.read_csv(HERE / 'si_s11_sens_by_group.csv')
groups = list(dict.fromkeys(s.group))
for g in groups:
    x = s[s.group == g]
    cells = [g]
    for c in ('S2', 'CH'):
        h = x[(x.case == c) & (x.storage == 'H2')]
        cells += ([f1(h.var_1to7d.iloc[0]), f1(h.var_gt28d.iloc[0]), f2(h.fifo_mean_days.iloc[0])] if len(h) else ['–'] * 3)
    e = x[x.storage == 'EV managed']
    cells += ([f1(e.var_lt1d_7_28.iloc[0]), f2(e.fifo_mean_days.iloc[0])] if len(e) else ['–'] * 2)
    print(row(cells))

print('### S12.2 by technology')
t = pd.read_csv(HERE / 'si_s12_by_tech.csv')
for b in ('F6', 'F6t2060'):
    print('--', b)
    for c in ('S1', 'S2', 'AH', 'BH', 'CH', 'A0', 'B0', 'C0'):
        for k in ('electrolyzer', 'fuelcell', 'tank', 'wind'):
            x = t[(t.batch == b) & (t.case == c) & (t.tech == k)]
            if not len(x):
                continue
            r = x.iloc[0]
            print(row([c, k, f'{r["size"]:,.0f}', f2(r.capital_full_life), f2(r.capital_charged), f2(r.fom_charged),
                       f2(r.salvage), f'{100 * r.salvage_share:.0f}']))

print('### S12.3 hydrogen vintages')
v = pd.read_csv(HERE / 'si_s12_h2_vintage.csv')
for b in ('F6', 'F6t2060'):
    print('--', b)
    for y in range(2041, 2051):
        cells = [str(y)]
        for c in ('S2', 'CH'):
            x = v[(v.batch == b) & (v.case == c) & (v.year == y)]
            cells += ([f'{x.el_kgph_built.iloc[0]:,.0f}', f2(x.capital_full_life.iloc[0]), f2(x.salvage.iloc[0]),
                       f'{100 * x.salvage_share.iloc[0]:.0f}'] if len(x) else ['–'] * 4)
        print(row(cells))

print('### S12.4 wind vintages')
wv = pd.read_csv(HERE / 'si_s12_wind_vintage.csv')
for b in ('F6', 'F6t2060'):
    print('--', b)
    for p in ('2025', '2026-2030', '2031-2040', '2041-2050', '2051-2060'):
        cells = [p.replace('-', '–')]
        for c in ('S1', 'S2', 'C0', 'CH'):
            x = wv[(wv.batch == b) & (wv.case == c) & (wv.period == p)]
            cells += ([f'{x["size"].iloc[0]:.0f}', f2(x.salvage.iloc[0])] if len(x) else ['–'] * 2)
        if any(cc != '–' for cc in cells[1:]):
            print(row(cells))

print('### S13.1 cumulative')
cu = pd.read_csv(HERE / 'si_s13_cumulative.csv')
for b in ('F6', 'F6t2060'):
    print('--', b)
    for y in range(2040, 2051):
        cells = [str(y)]
        for c in ('S2', 'AH', 'BH', 'CH'):
            x = cu[(cu.batch == b) & (cu.case == c) & (cu.year == y)].iloc[0]
            cells.append(f'{x.electrolyzer:,.0f} ({100 * x.electrolyzer_share_of_2050:.0f}%)')
        print(row(cells))
print('-- fuel cell / tank share 2045')
for b in ('F6', 'F6t2060'):
    x = cu[(cu.batch == b) & (cu.year == 2045)]
    print(b, x[['case', 'electrolyzer_share_of_2050', 'fuelcell_share_of_2050', 'tank_share_of_2050']].round(4).to_string())

print('### S13.2 unit cost')
uc = pd.read_csv(HERE / 'si_s13_unit_cost.csv', index_col=0)
for y in (2030, 2035, 2038, 2039, 2040, 2041, 2042, 2043, 2044, 2045, 2046, 2047, 2048, 2049, 2050):
    r = uc.loc[y]
    print(row([str(y), f'{r.electrolyzer_capex_input / 549.2:.1f}', f'{r.fuelcell_capex_input:.0f}',
               f'{r.tank_capex_input / 1000:.0f}', f'{int(r.electrolyzer_life)}', f'{r.set_annual_cost_MJPY:.0f}',
               '–' if pd.isna(r.premium_trunc2050_MJPY) else f'{r.premium_trunc2050_MJPY:.0f}',
               f'{r.premium_trunc2060_MJPY:.0f}']))

print('### S13.3 conditions')
co = pd.read_csv(HERE / 'si_s13_conditions.csv', index_col=0)
for y in (2025, 2030, 2035, 2040, 2041, 2043, 2045, 2047, 2050):
    r = co.loc[y]
    print(row([str(y), f2(r.price_mean_JPYkWh), f'{100 * r.price_floor_hour_share:.1f}', f2(r.wind_value_factor_S1),
               f'{r.S1_new_wind_MW:.0f}', f'{100 * r.S1_vre_curtail_rate:.1f}', f'{r.S1_net_export_at_limit_hours:,.0f}']))

print('### S14')
fl = pd.read_csv(HERE / 'si_s14_flows.csv', dtype={'period': str})
cases = ['S0', 'S1', 'S2', 'A0', 'AH', 'B0', 'BH', 'C0', 'CH']
for per in ('2050', '2025-2050'):
    x = fl[fl.period == per].set_index('case').loc[cases]
    print('--', per)
    items = [('wind_GWh', 'Wind generation'), ('solar_GWh', 'PV generation'), ('hydro_GWh', 'Hydropower'),
             ('fc_out_GWh', 'Fuel-cell output'), ('ev_dis_grid_GWh', 'V2G discharge to grid'),
             ('net_import_GWh', 'Net purchases (import)'), ('load_fixed_GWh', 'Non-EV load'),
             ('ev_uncontrolled_GWh', 'Uncontrolled EV charging'), ('ev_ch_GWh', 'Managed EV charging'),
             ('el_link_GWh', 'Electrolyzer, linear branch'), ('el_aux_GWh', 'Electrolyzer, auxiliary branch'),
             ('h2_aux_GWh', 'Hot standby and start-up'), ('net_export_GWh', 'Net sales (export)'),
             ('vre_curtail_GWh', 'Curtailment')]
    for k, n in items:
        print(row([n] + [f'{v:,.1f}' for v in x[k]]))
    for k, n, f in (('vre_curtail_rate', 'VRE curtailment rate (%)', lambda v: f'{100 * v:.1f}'),
                    ('wind_curtail_rate', 'wind (%)', lambda v: f'{100 * v:.1f}'),
                    ('solar_curtail_rate', 'PV (%)', lambda v: f'{100 * v:.1f}'),
                    ('curtail_incl_aux_dump_ub_rate', 'incl. aux (%)', lambda v: f'{100 * v:.1f}'),
                    ('net_export_flh_h', 'net export FLH', lambda v: f'{v:,.0f}'),
                    ('net_import_flh_h', 'net import FLH', lambda v: f'{v:,.0f}'),
                    ('net_export_at_limit_hours_per_yr', 'hours at limit /yr', lambda v: f'{v:,.0f}'),
                    ('hours_net_export', 'hours net export /yr', lambda v: f'{v:,.0f}'),
                    ('hours_net_import', 'hours net import /yr', lambda v: f'{v:,.0f}'),
                    ('el_import_share', 'el import share (%)', lambda v: '–' if pd.isna(v) else f'{100 * v:.0f}'),
                    ('ev_ch_from_import_share', 'ev import share (%)', lambda v: '–' if pd.isna(v) else f'{100 * v:.0f}')):
        print(row([n] + [f(v) for v in x[k]]))
