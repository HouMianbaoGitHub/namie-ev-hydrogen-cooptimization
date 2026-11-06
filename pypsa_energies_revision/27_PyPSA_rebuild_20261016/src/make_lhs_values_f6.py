"""Values for the [LHS:...] placeholders of the F6 manuscript and response (revision_round1/02_plan/lhs_values_F6.json).
Every value comes from results/lhsF6_20261031/ (analyze_lhs_f6.py -> lhs_results.csv, lhs_prcc.csv; lhs_timescale_f6.py ->
lhs_timescale_2050.csv; make_lhs_f6.py -> lhs_samples.csv). Interaction and crowding-out ratio use the A reference of
Equation (11): I_C = ΔH(C) − ΔH(A), ratio = ΔH(C)/ΔH(A); "built" means ΔH(A) > 0.01 bn JPY.
assemble_F5.py and fill_response_f6.py substitute them, English or Chinese by block.
Usage: python make_lhs_values_f6.py"""
import json
from pathlib import Path

import pandas as pd

D = Path(__file__).resolve().parents[1] / 'results' / 'lhsF6_20261031'
OUT = Path(__file__).resolve().parents[2] / 'revision_round1' / '02_plan' / 'lhs_values_F6.json'
r = pd.read_csv(D / 'lhs_results.csv', index_col=0)
P = pd.read_csv(D / 'lhs_prcc.csv', index_col=0)
t = pd.read_csv(D / 'lhs_timescale_2050.csv')
assert (r.n_optimal == 6).all() and len(r) == 40
BUILT = 0.01
b = r[r.dH_A > BUILT]
nb = r[r.dH_A <= BUILT]
f2 = lambda x: f'{x:.2f}'.replace('-', '−')
pc = lambda x: f'{100 * x:.0f}%'.replace('-', '−')
sp = lambda x: f'{x:+.2f}'.replace('-', '−')
V = {}


def put(key, en, zh=None):
    V[key] = {'en': en, 'zh': en if zh is None else zh}


def rng(s, f=f2, zh=False):
    return f'{f(s.min())}–{f(s.max())}' if s.min() >= 0 else f'{f(s.min())} {"至" if zh else "to"} {f(s.max())}'


put('n', f'{len(r)}')
put('parameters',
    'the price level (×0.9–1.1), wind output (×0.8–1.1), interface capacity (100–150 MW), non-EV demand (×0.9–1.1), '
    'hydrogen capital cost (×0.7–1.3), the specific consumption of the electrolyzer (×0.89–1.09) and of the fuel cell (×0.95–1.13), '
    'EV participation (25–100%) and the V2G wear cost (0–10 JPY/kWh)',
    '电价水平（×0.9–1.1）、风电出力（×0.8–1.1）、接口容量（100–150 MW）、非EV需求（×0.9–1.1）、氢能造价（×0.7–1.3）、'
    '电解槽单位耗电（×0.89–1.09）和燃料电池单位耗氢（×0.95–1.13）、EV参与率（25–100%）以及V2G损耗成本（0–10 JPY/kWh）')
put('n_built', f'{len(b)}')
put('n_not_built', f'{len(nb)}')
put('not_built_dH', f'ΔH(A) < {BUILT} billion JPY', f'ΔH(A) < {BUILT} 十亿日元')
put('n_IC_neg', f'{int((b.I_A < 0).sum())}')
put('IC_median', f2(b.I_A.median()))
put('IC_range', rng(b.I_A), rng(b.I_A, zh=True))
put('IC_share_median', pc((-b.I_A / b.dH_A).median()))
put('ratio_median', f2(b.ratio_A.median()))
put('ratio_range', rng(b.ratio_A))
big = b[b.dH_A > 0.2]
put('n_large', f'{len(big)}')
put('ratio_range_large', rng(big.ratio_A))
put('dH_A_median', f2(r.dH_A.median()))
put('dH_A_range', rng(r.dH_A.clip(lower=0)))
put('EV_CA_median', f2(r.EV_CA.median()))
put('EV_CA_range', rng(r.EV_CA))
put('n_EV_gt_H', f'{int((r.EV_CA > r.dH_A).sum())}')
put('el_change_median', pc(b.el_change_AH_CH.median()))
put('el_change_range', rng(b.el_change_AH_CH, pc), rng(b.el_change_AH_CH, pc, zh=True))
put('el_reduce_range', f'{pc(-b.el_change_AH_CH.max())}–{pc(-b.el_change_AH_CH.min())}')
put('el_reduce_median', pc(-b.el_change_AH_CH.median()))
put('IC_share_negative',
    f'interaction negative in all {len(b)} of the {len(r)} samples in which hydrogen is built, crowding-out ratio median {f2(b.ratio_A.median())}'
    if (b.I_A < 0).all() else f'interaction negative in {int((b.I_A < 0).sum())} of {len(b)} samples with hydrogen',
    f'{len(r)}组中建设氢能的{len(b)}组交互项全部为负，挤出比例中位数为{f2(b.ratio_A.median())}'
    if (b.I_A < 0).all() else f'建设氢能的{len(b)}组中有{int((b.I_A < 0).sum())}组交互项为负')
NAME = {'price_scale': ('price level', '电价水平'), 'wind_scale': ('wind output', '风电出力'),
        'market_limit_mw': ('interface capacity', '接口容量'), 'load_scale': ('non-EV demand', '非EV需求'),
        'h2_capex_scale': ('hydrogen capital cost', '氢能造价'), 'el_sec_scale': ('electrolyzer consumption', '电解槽单位耗电'),
        'fc_kg_scale': ('fuel-cell consumption', '燃料电池单位耗氢'), 'ev_participation': ('EV participation', 'EV参与率'),
        'v2g_cost': ('V2G wear cost', 'V2G损耗成本')}


def top(col, k):
    s = P[col].reindex(P[col].abs().sort_values(ascending=False).index)[:k]
    en = [f'{NAME[i][0]} ({sp(v)})' for i, v in s.items()]
    zh = [f'{NAME[i][1]}（{sp(v)}）' for i, v in s.items()]
    return ', '.join(en[:-1]) + ' and ' + en[-1], '、'.join(zh[:-1]) + '和' + zh[-1]


put('prcc_top', *top('I_A', 4))
put('prcc_ratio_top', *top('ratio_A', 3))
put('prcc_EV_top', *top('EV_CA', 2))
h = t[(t.storage == 'H2') & t['sample'].isin(b.index) & t.case.isin(['S2', 'CH'])]
e = t[t.storage == 'EV managed']
put('h2_fifo_range', f'{h.fifo_mean_days.min():.2f}–{h.fifo_mean_days.max():.2f} days', f'{h.fifo_mean_days.min():.2f}–{h.fifo_mean_days.max():.2f}天')
put('h2_fifo_median', f'{h.fifo_mean_days.median():.2f}')
put('h2_1to7_range', f'{h.var_1to7d.min():.1f}%–{h.var_1to7d.max():.1f}%')
put('h2_gt28_max', f'{h.var_gt28d.max():.1f}%')
put('h2_gt168h_max', f'{100 * h.fifo_share_gt_168h.max():.1f}%')
put('h2_quarter_max', f'{100 * h.across_quarter_net_share.max():.1f}%')
put('ev_intraday_range', f'{e.var_lt1d_7_28.min():.1f}%–{e.var_lt1d_7_28.max():.1f}%')
put('ev_fifo_range', f'{e.fifo_mean_days.min():.2f}–{e.fifo_mean_days.max():.2f} days', f'{e.fifo_mean_days.min():.2f}–{e.fifo_mean_days.max():.2f}天')
put('n_h2_series', f'{len(h)}')
OUT.write_text(json.dumps(V, ensure_ascii=False, indent=1), encoding='utf-8')
for k, v in V.items():
    print(k, '|', v['en'], '|', v['zh'] if v['zh'] != v['en'] else '')
