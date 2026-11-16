"""Storage timescale metrics of the Latin-hypercube cases, 2050."""

import inspect
import traceback
import pandas as pd
import postprocess as fp

LHSD = fp.ROOT / 'results' / 'lhs'
src = (
    inspect.getsource(fp.load)
    .replace("d = RES / f'base__{case}'", 'd = LHSD / case')
    .replace('SCEN[case]', "SCEN[case.split('__')[1]]")
)
assert 'LHSD / case' in src and "case.split('__')[1]" in src
ns = vars(fp).copy()
ns['LHSD'] = LHSD
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
            rows.append(
                {
                    'sample': s,
                    'case': c,
                    'storage': name,
                    'tank_t': r['capy'].at[2050, 'tank_t'],
                    **fp.ts_metrics(f, cap),
                }
            )
        print(d.name, 'ok', flush=True)
    except Exception:
        print(d.name, 'FAILED')
        traceback.print_exc()
df = pd.DataFrame(rows)
df.to_csv(LHSD / 'lhs_timescale_2050.csv', index=False)
pd.set_option('display.width', 250)
print(
    df.groupby(['case', 'storage'])[
        [
            'fifo_mean_days',
            'var_lt1d_7_28',
            'var_1to7d',
            'var_gt28d',
            'fifo_share_gt_168h',
            'across_quarter_net_share',
        ]
    ]
    .describe()
    .T.round(3)
    .to_string()
)
