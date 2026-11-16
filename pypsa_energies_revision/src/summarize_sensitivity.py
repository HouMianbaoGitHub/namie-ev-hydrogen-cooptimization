"""Summary table of the one-at-a-time sensitivity cases."""

import json
from pathlib import Path
import pandas as pd

R = Path(__file__).resolve().parents[1] / 'results'
D = R / 'sensitivity'
D5 = R / 'sensitivity_no_h2'
base = pd.read_csv(R / 'base' / 'summary.csv').query("batch == 'base'").set_index('case')
NOH2 = ('S1', 'A0', 'C0')


def run(d):
    s = json.loads((d / 'summary.json').read_text())
    r = {'term': s['termination_condition'], 'npv': s.get('npv_billion_JPY'), 'uc': s.get('h2_uc') or {}}
    if (d / 'installed_units.csv').exists():
        u = pd.read_csv(d / 'installed_units.csv', index_col=0).reindex(
            columns=['wind', 'electrolyzer', 'fuelcell', 'tank'], fill_value=0.0
        )
        r.update(
            el_kgph=u.at[2050, 'electrolyzer'] * 10,
            fc_MW=u.at[2050, 'fuelcell'] * 10,
            tank_t=u.at[2050, 'tank'],
            wind_MW=u.at[2050, 'wind'] * 40,
        )
        h = u.index[(u.electrolyzer > 1e-06) | (u.fuelcell > 1e-06)]
        r['first_h2'] = int(h[0]) if len(h) else None
    return r


runs6 = {p.name: run(p) for p in D.iterdir() if (p / 'summary.json').exists()}
runs5 = {p.name: run(p) for p in D5.iterdir() if (p / 'summary.json').exists()}
groups = sorted({k.split('__')[0] for k in runs6})
A0_CHANGES = {'evcap080', 'chg6'}
A0_RUNS = {p.name: run(p) for p in (R / 'sensitivity_a0').iterdir() if (p / 'summary.json').exists()}


def ev_flex(g, n, x):
    a = A0_RUNS.get(f'{g}__A0')
    if a is not None:
        assert a['term'] == 'optimal', g
        return n['C0'] - a['npv']
    return n['C0'] - n['A0'] if x['S1'] == 'base' and g not in A0_CHANGES else float('nan')


COLS = {
    'el_kgph': 'el_kgph_2050',
    'fc_MW': 'fc_MW_2050',
    'tank_t': 'tank_t_2050',
    'wind_MW': 'wind_MW_2050',
    'first_h2': 'first_h2',
}
rows = []
for g in ['BASE'] + groups:
    n, x, src = ({}, {}, {})
    for c in ('S1', 'S2', 'A0', 'C0', 'CH'):
        r, tag = (runs6.get(f'{g}__{c}'), 'solved')
        if r is None and c in NOH2:
            r, tag = (runs5.get(f'{g}__{c}'), 'no_h2_batch')
        ok = r is not None and r['term'] == 'optimal'
        n[c] = r['npv'] if ok else base.at[c, 'npv']
        x[c] = tag if ok else 'INFEASIBLE' if r is not None else 'base'
        src[c] = r if ok else None
    get = lambda c, k: src[c].get(k) if src[c] is not None else base.at[c, COLS[k]]
    dS, dC = (n['S2'] - n['S1'], n['CH'] - n['C0'])
    uc = src['CH']['uc'] if src['CH'] is not None else {}
    rows.append(
        {
            'group': g,
            'solved': ','.join((c for c in x if x[c] == 'solved')),
            'from_no_h2_batch': ','.join((c for c in x if x[c] == 'no_h2_batch')),
            'infeasible': ','.join((c for c in x if x[c] == 'INFEASIBLE')),
            'S1': n['S1'],
            'S2': n['S2'],
            'C0': n['C0'],
            'CH': n['CH'],
            'dH_S': dS,
            'dH_C': dC,
            'I_S': dC - dS,
            'ratio': dC / dS if abs(dS) > 1e-06 else float('nan'),
            'EV_flex_CA': ev_flex(g, n, x),
            'el_S2_kgph': get('S2', 'el_kgph'),
            'el_CH_kgph': get('CH', 'el_kgph'),
            'fc_CH_MW': get('CH', 'fc_MW'),
            'tank_CH_t': get('CH', 'tank_t'),
            'first_h2_S2': get('S2', 'first_h2'),
            'first_h2_CH': get('CH', 'first_h2'),
            'el_started_MW_CH': uc.get('electrolyzer_started_MW_total'),
            'el_standby_mean_MW_CH': uc.get('electrolyzer_mean_standby_MW'),
        }
    )
df = pd.DataFrame(rows).set_index('group')
num = [c for c in df.columns if c not in ('solved', 'from_no_h2_batch', 'infeasible')]
df.loc[df.infeasible != '', num] = float('nan')
df.to_csv(D / 'summary.csv')
pd.set_option('display.width', 250)
print(
    df.drop(columns=['S1', 'S2', 'C0', 'CH', 'el_started_MW_CH', 'el_standby_mean_MW_CH'])
    .round(3)
    .to_string()
)
