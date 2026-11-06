"""2050 timescale metrics of every hydrogen run of the F6 Latin-hypercube batch (registry lhs_F6_20261031; R2.6b; SI-S11).
Same definitions as sens_timescale_f6.py (f6_postprocess load, h2_frame, ev_frame, ts_metrics) on results/lhsF6_20261031/<sample>__<case>.
H2 for S2, AH and CH where a tank is built; 'EV managed' (V2G fleet) for CH.
Usage: python lhs_timescale_f6.py -> results/lhsF6_20261031/lhs_timescale_2050.csv"""
import inspect
import traceback

import pandas as pd

import f6_postprocess as fp

LHSD = fp.ROOT / 'results' / 'lhsF6_20261031'
src = inspect.getsource(fp.load).replace("d = RES / f'F6__{case}'", "d = LHSD / case").replace(
    "SCEN[case]", "SCEN[case.split('__')[1]]")
assert 'LHSD / case' in src and "case.split('__')[1]" in src
ns = vars(fp).copy(); ns['LHSD'] = LHSD
exec(src, ns)
load = ns['load']
rows = []
for d in sorted(LHSD.iterdir()):
    if '__' not in d.name or d.name.split('__')[1] not in ('S2', 'AH', 'CH'):
        continue
    try:
        r = load(d.name)
        s, c = d.name.split('__')
        series = []
        if r['has_h2'] and r['capy'].at[2050, 'tank_t'] > 0:
            series.append(('H2', fp.h2_frame(r, 2050)))
        if r['has_ev'] and c == 'CH':
            series.append(('EV managed', fp.ev_frame(r, 2050, 'managed')))
        for name, (f, cap) in series:
            if f is None or f['out'].sum() <= 0:
                continue
            rows.append({'sample': s, 'case': c, 'storage': name, 'tank_t': r['capy'].at[2050, 'tank_t'], **fp.ts_metrics(f, cap)})
        print(d.name, 'ok', flush=True)
    except Exception:
        print(d.name, 'FAILED'); traceback.print_exc()
df = pd.DataFrame(rows)
df.to_csv(LHSD / 'lhs_timescale_2050.csv', index=False)
pd.set_option('display.width', 250)
print(df.groupby(['case', 'storage'])[['fifo_mean_days', 'var_lt1d_7_28', 'var_1to7d', 'var_gt28d', 'fifo_share_gt_168h', 'across_quarter_net_share']]
      .describe().T.round(3).to_string())
