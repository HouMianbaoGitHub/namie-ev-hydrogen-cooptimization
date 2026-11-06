"""Values for the [SENS:...] placeholders of the F6 manuscript (revision_round1/02_plan/sens_values_F6.json).
Every value comes from results/sensF6_20261030/sensF6_summary.csv (built by summarize_sensf6.py) or from
results/sensF6_20261030/pypsa_timescale_metrics.json; assemble_F5.py substitutes them, English or Chinese by block.
Keys: [SENS:group:metric] and bare [SENS:group] (a compact "ΔH(S) = x, I = y" or "C−A = x, I = y" note).
Usage: python make_sens_values_f6.py"""
import json
from pathlib import Path

import pandas as pd

R = Path(__file__).resolve().parents[1] / 'results'
D = R / 'sensF6_20261030'
OUT = Path(__file__).resolve().parents[2] / 'revision_round1' / '02_plan' / 'sens_values_F6.json'
s = pd.read_csv(D / 'sensF6_summary.csv').set_index('group')
ts = json.loads((D / 'pypsa_timescale_metrics.json').read_text())
b = s.loc['BASE']
g = s.drop('BASE')
EV = [k for k in g.index if g.at[k, 'solved_F6'] == 'CH']          # EV groups re-solve CH only
f2 = lambda x: f'{x:.2f}'.replace('-0.00', '0.00').replace('-', '−')
f1 = lambda x: f'{x:.1f}'.replace('-', '−')
V = {}


def put(key, en, zh=None):
    V[key] = {'en': en, 'zh': en if zh is None else zh}


for k, r in g.iterrows():
    for m in ('dH_S', 'dH_C', 'C0'):
        put(f'{k}:{m}', f2(r[m]))
    put(f'{k}:I_C_S', f2(r['I_S']))
    put(f'{k}:C0_change', f2(r['C0'] - b['C0']))   # V2G-portfolio NPV change vs base (A0 not re-solved in chg6/evcap080)
    put(f'{k}:ratio_S', f2(r['ratio']))
    if pd.notna(r['EV_flex_CA']):
        put(f'{k}:CA', f2(r['EV_flex_CA']))
        put(f'{k}:CA_change', f2(b['EV_flex_CA'] - r['EV_flex_CA']))   # "falls by"
    put(f'{k}:tank_CH', f1(r['tank_CH_t']))
    put(f'{k}:el_CH', f'{r["el_CH_kgph"]:,.0f} kg/h', f'{r["el_CH_kgph"]:,.0f} kg/h')
    put(f'{k}:first_h2', f'{int(r["first_h2_S2"])}' + (f' (CH {int(r["first_h2_CH"])})' if r['first_h2_CH'] != r['first_h2_S2'] else ''))
    if k in EV:
        put(k, f'C−A = {f2(r["EV_flex_CA"]) if pd.notna(r["EV_flex_CA"]) else "n/a"}, I^S^_C = {f2(r["I_S"])}')
    else:
        put(k, f'ΔH(S) = {f2(r["dH_S"])}, I^S^_C = {f2(r["I_S"])}')
for k, run in (('leak10', 'leak10__CH'), ('leak01', 'leak01__CH'), ('tank043', 'tank043__CH')):
    put(f'{k}:fifo_CH', f1(ts[run]['fifo_mean_days']))
c = g.loc['capex130']
put('capex130:built', f'CH builds only {c.el_CH_kgph:,.0f} kg/h of electrolysis, from {int(c.first_h2_CH)}',
    f'CH 仅建 {c.el_CH_kgph:,.0f} kg/h 电解槽，{int(c.first_h2_CH)} 年起')
t = g.loc['tank043']
put('tank043:note', f'billion JPY (crowding-out ratio {f2(t.ratio)}; mean residence time of hydrogen in CH {f1(ts["tank043__CH"]["fifo_mean_days"])} days)',
    f'十亿日元（挤出比例 {f2(t.ratio)}；CH 中氢的平均储存时间 {f1(ts["tank043__CH"]["fifo_mean_days"])} 天）')
put('coh4_t10', 'infeasible; Section S7', '不可行；第 S7 节')

# summary
n_runs = int(sum(len(x.split(',')) for x in g.solved_F6 if isinstance(x, str) and x)
             + sum(len(x.split(',')) for x in g.from_sensF5 if isinstance(x, str) and x))
put('summary:n_groups', f'{len(g)}')
put('summary:n_cases', f'{n_runs}')
put('summary:n_IC_neg', f'{int((g.I_S < 0).sum())}')
put('summary:ratio_min', f2(g.ratio.min()))
put('summary:ratio_max', f2(g.ratio.max()))
gb = g[g.dH_S >= 0.05]   # groups in which hydrogen is clearly built (capex130: 0.02 bn JPY, barely built)
put('summary:ratio_min_built', f2(gb.ratio.min())); put('summary:ratio_max_built', f2(gb.ratio.max()))
put('summary:n_groups_built', f'{len(gb)}')
put('crowding_range', f'(crowding-out ratio {f2(g.ratio.min())}–{f2(g.ratio.max())})', f'（挤出比例 {f2(g.ratio.min())}–{f2(g.ratio.max())}）')
ops = g.loc[['startcost', 'startenergy', 'stack10', 'stack40', 'pem', 'avail090']]
part = g.loc[['part025', 'part075', 'part100']].ratio
cap = g.loc[['capex070', 'capex130']].ratio
put('summary:largest_effects',
    f'the EV participation rate (ratio ΔH(C)/ΔH(S) {f2(part.min())}–{f2(part.max())} for 100% to 25%), the hydrogen capital cost '
    f'({f2(cap.min())}–{f2(cap.max())}; at +30% hydrogen is barely built) and network charges on trade ({f2(g.at["netcharge", "ratio"])}); '
    f'the electrolyzer operating assumptions (start-up cost and energy, stack life, PEM, availability) keep the ratio within '
    f'{f2(ops.ratio.min())}–{f2(ops.ratio.max())}',
    f'EV 参与率（参与率 100% 至 25% 时比例 ΔH(C)/ΔH(S) 为 {f2(part.min())}–{f2(part.max())}）、氢能造价（{f2(cap.min())}–{f2(cap.max())}；造价 +30% 时氢能几乎不建）'
    f'和购售电网络费（{f2(g.at["netcharge", "ratio"])}）；电解槽运行假设（启停成本与能耗、电堆寿命、PEM、可用率）下比例保持在 '
    f'{f2(ops.ratio.min())}–{f2(ops.ratio.max())}')
# response letter (R1.5c, R2.3, R2.6b): timescale ranges over sensitivity runs (sens_timescale_f6.py)
tsc = pd.read_csv(D / 'sens_timescale_2050.csv')
h2, evm = tsc[tsc.storage == 'H2'], tsc[(tsc.storage == 'EV managed') & (tsc.case == 'CH')]
pct = lambda x: f'{x:.0f}%'
for k, col, fmt in (('h2_fifo', 'fifo_mean_days', f1), ('h2_var_1to7', 'var_1to7d', pct)):
    put(f'summary:{k}_min', fmt(h2[col].min())); put(f'summary:{k}_max', fmt(h2[col].max()))
put('summary:ev_intraday_min', pct(evm.var_lt1d_7_28.min())); put('summary:ev_intraday_max', pct(evm.var_lt1d_7_28.max()))
OPS = ['leak01', 'leak10', 'eff_hi', 'eff_lo', 'avail090']             # leakage, efficiency, availability
ho = h2[h2.group.isin(OPS)]
put('summary:h2ops_fifo_min', f1(ho.fifo_mean_days.min())); put('summary:h2ops_fifo_max', f1(ho.fifo_mean_days.max()))
put('summary:h2ops_var_gt28_max', pct(ho.var_gt28d.max()))
HOPS = ['minload030', 'startcost', 'startenergy', 'stack10', 'stack40', 'pem', 'avail090']   # electrolyzer operation (R1.5c)
hg = g.loc[HOPS]
put('summary:hydrogen_ops_n_IC_neg', 'all' if (hg.I_S < 0).all() else f'{int((hg.I_S < 0).sum())}', f'{int((hg.I_S < 0).sum())}')
put('summary:hydrogen_ops_el_CH_min', f'{hg.el_CH_kgph.min() * 0.054:.0f}'); put('summary:hydrogen_ops_el_CH_max', f'{hg.el_CH_kgph.max() * 0.054:.0f}')
j = g.loc['joint090']
put('joint090:C0_S1', f2(j.C0 - j.S1))
put('summary:division_statement', 'unchanged', '不变')

# Additional tests after the pre-submission review (registry sensitivity_review_F6_20261101; results/revF6_20261101,
# summary table revF6_summary.csv with the F6 base rows). Not part of the 34 one-at-a-time groups above.
RV = R / 'revF6_20261101'
rv = pd.read_csv(RV / 'revF6_summary.csv')
npv = {(r.group, r.case): r.npv_bn for r in rv.itertuples()}
elmw = {(r.group, r.case): r.el_2050_MW for r in rv.itertuples()}
gv = lambda d, grp, c: d.get((grp, c), d[('F6', c)])        # B1 groups re-solve S2 and CH only
mw = lambda x: f'{x:.0f}'
for grp in ('capex110', 'capex120', 'fom4', 'capexmid'):
    dS = gv(npv, grp, 'S2') - gv(npv, grp, 'S1'); dC = gv(npv, grp, 'CH') - gv(npv, grp, 'C0')
    put(f'{grp}:dH_S', f2(dS)); put(f'{grp}:dH_C', f2(dC)); put(f'{grp}:I_C_S', f2(dC - dS))
    put(f'{grp}:ratio_S', f2(dC / dS) if dS >= 0.01 else 'n/a', f2(dC / dS) if dS >= 0.01 else '无')
    put(f'{grp}:el_S2_MW', mw(gv(elmw, grp, 'S2'))); put(f'{grp}:el_CH_MW', mw(gv(elmw, grp, 'CH')))
for grp in ('spread070', 'curt2x'):
    v = {c: npv[(grp, c)] for c in ('S1', 'S2', 'A0', 'AH', 'C0', 'CH')}
    dS, dA, dC = v['S2'] - v['S1'], v['AH'] - v['A0'], v['CH'] - v['C0']
    for k, x in (('dH_S', dS), ('dH_A', dA), ('dH_C', dC), ('I_C', dC - dA), ('CA', v['C0'] - v['A0'])):
        put(f'{grp}:{k}', f2(x))
    put(f'{grp}:ratio_A', f2(dC / dA) if dA >= 0.01 else 'n/a', f2(dC / dA) if dA >= 0.01 else '无')
    for c in ('S2', 'AH', 'CH'):
        put(f'{grp}:el_{c}_MW', mw(elmw[(grp, c)]))
put('base:CA', f2(npv[('F6', 'C0')] - npv[('F6', 'A0')]))
# curt2x: exports in 2050 and the price in hours with regional curtailment (price series of the base)
ex = {k: pd.read_parquet(d / 'electricity_exchange.parquet') for k, d in
      (('base', R / 'f6_20261030' / 'F6__CH'), ('curt2x', RV / 'curt2x__CH'))}
ex = {k: (e['export'] - e['import']).clip(lower=0) for k, e in ex.items()}  # net sales: gross trade is not unique at equal prices
for k, e in ex.items():
    put(f'curt2x:export2050_{k}', f'{e[e.index.year == 2050].sum() / 1e6:.2f}')
ps = pd.read_parquet(R.parent / 'inputs' / 'tohoku_price_plan_ref2024.parquet').xs(2050, level=0)
cu = ps.curtail_rate > 0
put('curt2x:share_hours_2050', f'{100 * cu.mean():.0f}%')
put('curt2x:rate_in_hours_2050', f'{100 * ps.curtail_rate[cu].mean():.0f}%')
put('curt2x:price_curt_2050', f'{ps.price[cu].mean():.2f}'); put('curt2x:price_other_2050', f'{ps.price[~cu].mean():.1f}')
OUT.write_text(json.dumps(V, ensure_ascii=False, indent=1), encoding='utf-8')
print(OUT, len(V), 'keys;', 'groups', len(g), 'runs', n_runs)
for k in ('summary:n_cases', 'summary:ratio_min', 'summary:ratio_max', 'crowding_range', 'summary:largest_effects', 'tank043:note', 'capex130:built', 'aperp', 'mkt100'):
    print(k, '|', V[k]['en'])
