"""2050 timescale metrics of every hydrogen run of the F6 sensitivity batch (R2.3 / R2.6b; SI-S11).
Uses the definitions of f6_postprocess.py (load, h2_frame, ev_frame, ts_metrics) on results/sensF6_20261030/<group>__<case>.
H2 for S2 and CH where a tank is built; 'EV managed' (V2G fleet) for CH.
Usage: python sens_timescale_f6.py -> results/sensF6_20261030/sens_timescale_2050.csv"""
import inspect
import traceback

import pandas as pd

import f6_postprocess as fp

SENSD = fp.ROOT / 'results' / 'sensF6_20261030'
src = inspect.getsource(fp.load).replace("d = RES / f'F6__{case}'", "d = SENSD / case").replace(
    "SCEN[case]", "SCEN[case.split('__')[1]]")
assert 'SENSD / case' in src and "case.split('__')[1]" in src
ns = vars(fp).copy(); ns['SENSD'] = SENSD
exec(src, ns)
load = ns['load']
rows = []
for d in sorted(SENSD.iterdir()):
    if '__' not in d.name or d.name.split('__')[1] not in ('S2', 'CH'):
        continue
    try:
        r = load(d.name)
        g, c = d.name.split('__')
        series = []
        if r['has_h2'] and r['capy'].at[2050, 'tank_t'] > 0:
            series.append(('H2', fp.h2_frame(r, 2050)))
        if r['has_ev'] and c == 'CH':
            series.append(('EV managed', fp.ev_frame(r, 2050, 'managed')))
        for name, (f, cap) in series:
            if f is None or f['out'].sum() <= 0:
                continue
            rows.append({'group': g, 'case': c, 'storage': name, **fp.ts_metrics(f, cap)})
        print(d.name, 'ok', flush=True)
    except Exception:
        print(d.name, 'FAILED'); traceback.print_exc()
df = pd.DataFrame(rows)
df.to_csv(SENSD / 'sens_timescale_2050.csv', index=False)
pd.set_option('display.width', 250)
print(df[['group', 'case', 'storage', 'fifo_mean_days', 'var_lt1d_7_28', 'var_1to7d', 'var_7to28d', 'var_gt28d']].round(2).to_string(index=False))
