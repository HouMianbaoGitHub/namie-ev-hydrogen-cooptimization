"""F6 Latin-hypercube batch (registry lhs_F6_20261031): one row per sample, distributions and PRCC.
Per sample: H2 value dH_S = S2−S1, dH_A = AH−A0, dH_C = CH−C0; EV flexibility C−A without (C0−A0) and with hydrogen (CH−AH);
interactions I_S = dH_C − dH_S, I_A = dH_C − dH_A; crowding-out ratios dH_C/dH_S and dH_C/dH_A (only where hydrogen is built
in the reference case, dH > 0.01 bn JPY). PRCC (Marino et al. 2008): Spearman correlation of the rank residuals after removing
the linear effect of the other parameters' ranks.
Usage: python analyze_lhs_f6.py -> results/lhsF6_20261031/lhs_results.csv, lhs_prcc.csv, lhs_stats.json"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

D = Path(__file__).resolve().parents[1] / 'results' / 'lhsF6_20261031'
S = pd.read_csv(D / 'lhs_samples.csv', index_col=0)
SCEN = ('S1', 'S2', 'A0', 'AH', 'C0', 'CH')
BUILT = 0.01   # bn JPY: hydrogen value below this counts as "not built"


def run(d):
    if not (d / 'summary.json').exists():
        return None
    s = json.loads((d / 'summary.json').read_text())
    r = {'term': s['termination_condition'], 'npv': s.get('npv_billion_JPY')}
    if (d / 'installed_units.csv').exists():
        u = pd.read_csv(d / 'installed_units.csv', index_col=0).reindex(columns=['electrolyzer', 'fuelcell', 'tank'], fill_value=0.)
        r.update(el_kgph=u.at[2050, 'electrolyzer'] * 10, fc_MW=u.at[2050, 'fuelcell'] * 10, tank_t=u.at[2050, 'tank'])
    return r


rows = []
for sid in S.index:
    r = {c: run(D / f'{sid}__{c}') for c in SCEN}
    row = {'sample': sid, 'n_optimal': sum(x is not None and x['term'] == 'optimal' for x in r.values())}
    if row['n_optimal'] == len(SCEN):
        n = {c: r[c]['npv'] for c in SCEN}
        dS, dA, dC = n['S2'] - n['S1'], n['AH'] - n['A0'], n['CH'] - n['C0']
        row.update(n, dH_S=dS, dH_A=dA, dH_C=dC, I_S=dC - dS, I_A=dC - dA, EV_CA=n['C0'] - n['A0'], EV_CA_H=n['CH'] - n['AH'],
                   ratio_S=dC / dS if dS > BUILT else np.nan, ratio_A=dC / dA if dA > BUILT else np.nan,
                   built_S2=dS > BUILT, built_CH=dC > BUILT,
                   el_S2_kgph=r['S2'].get('el_kgph'), el_AH_kgph=r['AH'].get('el_kgph'), el_CH_kgph=r['CH'].get('el_kgph'),
                   fc_CH_MW=r['CH'].get('fc_MW'), tank_CH_t=r['CH'].get('tank_t'))
        row['el_change_AH_CH'] = row['el_CH_kgph'] / row['el_AH_kgph'] - 1 if row['el_AH_kgph'] > 1 else np.nan
    rows.append(row)
res = S.join(pd.DataFrame(rows).set_index('sample'))
res.to_csv(D / 'lhs_results.csv')
ok = res[res.n_optimal == len(SCEN)]


def prcc(df, x_cols, y):
    rk = df[x_cols + [y]].rank()
    out = {}
    for c in x_cols:
        Z = np.column_stack([np.ones(len(rk))] + [rk[o] for o in x_cols if o != c])
        res_x = rk[c] - Z @ np.linalg.lstsq(Z, rk[c], rcond=None)[0]
        res_y = rk[y] - Z @ np.linalg.lstsq(Z, rk[y], rcond=None)[0]
        out[c] = float(np.corrcoef(res_x, res_y)[0, 1])
    return out


X = list(S.columns)
built = ok[ok.built_S2 | ok.built_CH]
P = pd.DataFrame({y: prcc(ok if y in ('dH_S', 'dH_C', 'EV_CA', 'I_S', 'I_A') else built, X, y)
                  for y in ('dH_S', 'dH_C', 'EV_CA', 'I_S', 'I_A', 'ratio_A')})
P.to_csv(D / 'lhs_prcc.csv')
q = lambda s: {'min': s.min(), 'p25': s.quantile(.25), 'median': s.median(), 'p75': s.quantile(.75), 'max': s.max()}
stats = {'n_samples': len(S), 'n_complete': len(ok), 'n_built_S2': int(ok.built_S2.sum()), 'n_built_CH': int(ok.built_CH.sum()),
         'n_not_built_any': int((~ok.built_S2 & ~ok.built_CH).sum()),
         'n_IS_neg': int((ok.I_S < -1e-6).sum()), 'n_IA_neg': int((ok.I_A < -1e-6).sum()),
         'n_IS_pos': int((ok.I_S > 1e-6).sum()), 'n_IA_pos': int((ok.I_A > 1e-6).sum()),
         'n_EV_gt_H': int((ok.EV_CA > ok.dH_S).sum()),
         **{k: q(built[k].dropna()) for k in ('dH_S', 'dH_C', 'I_S', 'I_A', 'ratio_S', 'ratio_A', 'el_change_AH_CH')},
         'EV_CA': q(ok.EV_CA)}
(D / 'lhs_stats.json').write_text(json.dumps(stats, indent=1, default=float))
pd.set_option('display.width', 250)
print(res[['n_optimal', 'dH_S', 'dH_A', 'dH_C', 'I_S', 'I_A', 'ratio_A', 'EV_CA', 'el_change_AH_CH']].round(3).to_string())
print(P.round(2).to_string())
print(json.dumps({k: v for k, v in stats.items() if not isinstance(v, dict)}))
