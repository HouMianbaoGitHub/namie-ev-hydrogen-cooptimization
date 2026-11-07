"""SI S11: window and year sensitivity of the timescale metrics (F6) and their range across the F6 sensitivity runs.

Reads (read-only):
  27_PyPSA_rebuild_20261016/results/f6_20261030/postprocess/window_sensitivity.csv
  27_PyPSA_rebuild_20261016/results/f6_20261030/postprocess/timescale_metrics.csv
  27_PyPSA_rebuild_20261016/results/sensF6_20261030/sens_timescale_2050.csv   (src/sens_timescale_f6.py)
Writes:
  si_data/si_s11_window_year.csv   one row per case x storage: 7/28 and 5/20 shares for 2050 and 2049, shifts, max |2050-2049|
  si_data/si_s11_sens_by_group.csv H2 and V2G-fleet metrics of every sensitivity run (2050)
  si_data/si_s11_checks.txt        the numbers quoted in the main text / response and whether the data support them
Usage: python si_s11_timescales.py
"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] / '27_PyPSA_rebuild_20261016'
PP = ROOT / 'results' / 'f6_20261030' / 'postprocess'
SENS = ROOT / 'results' / 'sensF6_20261030' / 'sens_timescale_2050.csv'

B7 = ['var_lt1d_7_28', 'var_1to7d', 'var_7to28d', 'var_gt28d']
B5 = ['var_lt1d_5_20', 'var_1to5d', 'var_5to20d', 'var_gt20d']

w = pd.read_csv(PP / 'window_sensitivity.csv')
ts = pd.read_csv(PP / 'timescale_metrics.csv')
w = w.merge(ts[['case', 'storage', 'year', 'fifo_mean_days', 'acf_24h']], on=['case', 'storage', 'year'], how='left')
# keep the series of Table 6: H2 of S2/AH/BH/CH, A (input profile, once), EV managed of B0/BH/C0/CH
keep = (w.storage == 'H2') | ((w.storage == 'EV total fleet (fixed profile)') & (w.case == 'A0')) | (w.storage == 'EV managed')
w = w[keep].copy()
rows = []
for (c, s), g in w.groupby(['case', 'storage'], sort=False):
    a, b = g[g.year == 2050].iloc[0], g[g.year == 2049].iloc[0]
    r = {'case': c, 'storage': s}
    for y, x in ((2050, a), (2049, b)):
        for col in B7 + B5 + ['fifo_mean_days', 'acf_24h']:
            r[f'{col}_{y}'] = x[col]
    # shift from the 7/28 to the 5/20 split (2050): multi-day band 1-7 d -> 1-5 d and 7-28 d -> 5-20 d
    for y, x in ((2050, a), (2049, b)):
        r[f'shift_1to7_to_1to5_{y}'] = x.var_1to7d - x.var_1to5d
        r[f'shift_7to28_to_5to20_{y}'] = x.var_5to20d - x.var_7to28d
        r[f'intraday_change_{y}'] = x.var_lt1d_5_20 - x.var_lt1d_7_28
    r['max_abs_diff_2050_2049_pp'] = max(abs(a[c2] - b[c2]) for c2 in B7 + B5)
    r['max_abs_diff_2050_2049_pp_7_28'] = max(abs(a[c2] - b[c2]) for c2 in B7)
    rows.append(r)
wy = pd.DataFrame(rows)
wy.to_csv(HERE / 'si_s11_window_year.csv', index=False)

s = pd.read_csv(SENS)
cols = ['group', 'case', 'storage', 'capacity_basis'] + B7 + B5 + ['acf_24h', 'fifo_mean_days', 'fifo_median_days',
                                                                    'fifo_share_gt_168h', 'across_quarter_net_share',
                                                                    'throughput_over_capacity']
s[cols].to_csv(HERE / 'si_s11_sens_by_group.csv', index=False)

h = wy[wy.storage == 'H2']
ev = wy[wy.storage != 'H2']
sh = s[s.storage == 'H2']
se = s[s.storage == 'EV managed']
lines = [
    'H2 2050: shift 1-7d -> 1-5d (pp): %.2f-%.2f' % (h.shift_1to7_to_1to5_2050.min(), h.shift_1to7_to_1to5_2050.max()),
    'H2 2050: shift 7-28d -> 5-20d (pp): %.2f-%.2f' % (h.shift_7to28_to_5to20_2050.min(), h.shift_7to28_to_5to20_2050.max()),
    'H2 2049: shift 1-7d -> 1-5d (pp): %.2f-%.2f' % (h.shift_1to7_to_1to5_2049.min(), h.shift_1to7_to_1to5_2049.max()),
    'H2 2049: shift 7-28d -> 5-20d (pp): %.2f-%.2f' % (h.shift_7to28_to_5to20_2049.min(), h.shift_7to28_to_5to20_2049.max()),
    'H2 >20d share 2050: %.2f-%.2f ; 2049: %.2f-%.2f' % (h.var_gt20d_2050.min(), h.var_gt20d_2050.max(),
                                                          h.var_gt20d_2049.min(), h.var_gt20d_2049.max()),
    'H2 >28d share 2050: %.2f-%.2f ; 2049: %.2f-%.2f' % (h.var_gt28d_2050.min(), h.var_gt28d_2050.max(),
                                                          h.var_gt28d_2049.min(), h.var_gt28d_2049.max()),
    'EV (managed + A input) >20d share 2050: %.2f-%.2f ; 2049: %.2f-%.2f' % (
        ev.var_gt20d_2050.min(), ev.var_gt20d_2050.max(), ev.var_gt20d_2049.min(), ev.var_gt20d_2049.max()),
    'EV intraday change 7/28 -> 5/20 (pp, 2050): %.2f to %.2f' % (ev.intraday_change_2050.min(), ev.intraday_change_2050.max()),
    'max |2050-2049| any band, any series (pp): %.2f (%s %s)' % (
        wy.max_abs_diff_2050_2049_pp.max(), *wy.loc[wy.max_abs_diff_2050_2049_pp.idxmax(), ['case', 'storage']]),
    'H2 FIFO mean 2050: %.2f-%.2f ; 2049: %.2f-%.2f' % (h.fifo_mean_days_2050.min(), h.fifo_mean_days_2050.max(),
                                                         h.fifo_mean_days_2049.min(), h.fifo_mean_days_2049.max()),
    '--- sensitivity runs (2050) ---',
    'n runs with H2 metrics: %d ; n runs with V2G-fleet metrics: %d' % (len(sh), len(se)),
    'H2 FIFO mean: %.2f (%s %s) - %.2f (%s %s)' % (sh.fifo_mean_days.min(), *sh.loc[sh.fifo_mean_days.idxmin(), ['group', 'case']],
                                                  sh.fifo_mean_days.max(), *sh.loc[sh.fifo_mean_days.idxmax(), ['group', 'case']]),
    'H2 1-7d share: %.2f (%s %s) - %.2f (%s %s)' % (sh.var_1to7d.min(), *sh.loc[sh.var_1to7d.idxmin(), ['group', 'case']],
                                                   sh.var_1to7d.max(), *sh.loc[sh.var_1to7d.idxmax(), ['group', 'case']]),
    'H2 >28d share: %.2f - %.2f (%s %s)' % (sh.var_gt28d.min(), sh.var_gt28d.max(), *sh.loc[sh.var_gt28d.idxmax(), ['group', 'case']]),
    'H2 >20d share (5/20): %.2f - %.2f (%s %s)' % (sh.var_gt20d.min(), sh.var_gt20d.max(), *sh.loc[sh.var_gt20d.idxmax(), ['group', 'case']]),
    'H2 FIFO share >168h max: %.4f' % sh.fifo_share_gt_168h.max(),
    'H2 across-quarter net share max: %.4f' % sh.across_quarter_net_share.max(),
    'V2G fleet (CH) intraday share: %.2f (%s) - %.2f (%s)' % (se.var_lt1d_7_28.min(), se.loc[se.var_lt1d_7_28.idxmin(), 'group'],
                                                             se.var_lt1d_7_28.max(), se.loc[se.var_lt1d_7_28.idxmax(), 'group']),
    'V2G fleet FIFO mean: %.2f - %.2f' % (se.fifo_mean_days.min(), se.fifo_mean_days.max()),
]
(HERE / 'si_s11_checks.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('\n'.join(lines))
