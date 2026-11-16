"""Salvage value of assets whose annuities extend beyond 2050."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
import model as M

D = ROOT / 'results' / 'base'
CASES = ['S1', 'S2', 'A0', 'AH', 'B0', 'BH', 'C0', 'CH']
d24 = lambda t: 1.03 ** (-(t - 2024))


def parts(k, y, args, pv):
    w = args.wacc
    crf = lambda L: w / (1 - (1 + w) ** (-L))
    L = M.tech_life(k, args, y)
    if k in ('electrolyzer', 'fuelcell', 'tank'):
        fom = M.parse_kv(args.h2_fom) if args.h2_fom else {}
        stk = M.parse_kv(args.h2_stack_repl) if args.h2_stack_repl else {}
        unit = {'electrolyzer': 1.0, 'fuelcell': M.UNIT_KW['fuelcell'], 'tank': 1.0}[k]
        capex = M._interp(M.parse_path(getattr(args, 'capex_' + k)), y) * 1000 * unit
        repl = (
            sum((stk[k][0] * (1 + w) ** (-t) for t in np.arange(stk[k][1], L, stk[k][1])))
            if k in stk
            else 0.0
        )
        a = (capex * crf(L) * (1 + repl), capex * fom.get(k, (0.0,))[0])
        assert abs(sum(a) - M.h2_unit_annual_cost(k, y, args)) < 1e-06 * sum(a)
        return a + (L,)
    capex = pv[M.TECH[k][0], y] / 1.03 ** (-(y - 2025)) - 1000 * M.UNIT_KW[k] / 0.03
    return (capex * crf(L), args.re_fom_jpy_per_kw * M.UNIT_KW[k], L)


def salvage(batch, case):
    d = D / f'{batch}__{case}'
    s = json.loads((d / 'summary.json').read_text())
    args = SimpleNamespace(**s['command'])
    M.STATIC, M.PERP = (None, False)
    M.YEND = args.extend_to
    M.HEND = args.end_year or M.YEND
    pv = {
        (r['object'], int(r['year'])): r['pv_per_unit']
        for r in M.load_annuity(ROOT / 'inputs', args.scenario)
    }
    build = pd.read_csv(d / 'annual_build.csv', index_col=0)
    rows = []
    for y in build.index:
        for k in build.columns:
            b = float(build.at[y, k])
            if b < 1e-09:
                continue
            acap, afom, L = parts(k, int(y), args, pv)
            life = range(int(y), int(y) + L)
            inh = [t for t in life if t <= M.HEND]
            rows.append(
                {
                    'tech': k,
                    'year': int(y),
                    'units': b,
                    'life': L,
                    'capital_full_life': b * acap * sum(map(d24, life)) / 1000000000.0,
                    'capital_charged': b * acap * sum(map(d24, inh)) / 1000000000.0,
                    'fom_charged': b * afom * sum(map(d24, inh)) / 1000000000.0,
                }
            )
    r = pd.DataFrame(rows)
    r['salvage'] = r.capital_full_life - r.capital_charged
    resid = (
        r.capital_charged.sum()
        + r.fom_charged.sum()
        - s['objective_ledger']['investment_and_fixed_million_JPY'] / 1000.0
    )
    return (r, resid)


def main():
    by_build, by_tech = ([], {})
    for b in ('base', 'base2060'):
        for c in CASES:
            r, resid = salvage(b, c)
            print(
                f'{b:8s} {c}: salvage {r.salvage.sum():7.3f}  check residual {resid:.1e} bn JPY', flush=True
            )
            assert abs(resid) < 1e-06
            by_build.append(r.assign(batch=b, case=c))
            g = r.assign(
                group=r.tech.map(lambda k: 'hydrogen' if k in ('electrolyzer', 'fuelcell', 'tank') else k)
            ).groupby('group')
            for grp, x in g:
                by_tech[b, c, grp] = x[
                    ['capital_full_life', 'capital_charged', 'fom_charged', 'salvage']
                ].sum()
    pd.concat(by_build).to_csv(D / 'salvage_by_build.csv', index=False)
    t = pd.DataFrame(by_tech).T
    t.index.names = ['batch', 'case', 'group']
    t['salvage_share'] = t.salvage / t.capital_full_life
    t.to_csv(D / 'salvage_by_tech.csv')
    pd.set_option('display.width', 220)
    print(t.round(3).to_string())


if __name__ == '__main__':
    main()
