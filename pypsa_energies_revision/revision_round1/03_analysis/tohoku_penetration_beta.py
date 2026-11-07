"""Tohoku-area wind/solar penetration by year -> target wind value factor -> beta (option 5, draft).

Inputs (reports/东北海上风电项目与连系线计划.md, reports/东北风光装机规划与需求.md):
- FY2025 actual: PV 9.82 GW, wind 2.41 GW (onshore ~2.27, port offshore ~0.14); demand 79.6 TWh; shares PV 13.5%, wind 7.6%.
- Supply plan (OCCTO 2026): PV 12.95 / 16.16 GW, wind (total) 5.74 / 7.28 GW in FY2030 / FY2035; demand 79.1 / 78.0 TWh.
- Master plan (OCCTO 2023) 2050: onshore 18.2, offshore 8.8, PV 33.8 GW; demand ~116 TWh.
- Offshore list (planned / delay-adjusted): see OFF_* below.
Capacity factors (assumption, from Tohoku actuals FY2022-25 and Akita port offshore): onshore 0.25, offshore 0.35, PV 0.13.
Value-factor relation (Hirth 2013, to be checked against the paper): wind VF falls from ~1.0 to 0.5-0.8 as wind share rises 0->30%;
linearised around the 2024 anchor (share 7.6%, VF 0.973): VF = 0.973 - k (s - 0.076), k = 0.67 (mitigated, upper edge) or 1.5 (central).
beta(VF): this model's transform (7-day wind anomaly, monthly mean kept) scanned on the 2050 profile; VF cannot fall below ~0.67.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path(__file__).parent
Y = np.arange(2025, 2051)
ip = lambda pts, y: float(np.interp(y, sorted(pts), [pts[k] for k in sorted(pts)]))
OFF_PLAN = {2025: .139, 2027: .139, 2028: .454, 2029: 1.513, 2030: 2.608, 2033: 3.753, 2035: 4.553, 2040: 4.553, 2050: 8.8}
OFF_AWARDED = {2025: .139, 2027: .139, 2028: .454, 2029: 1.513, 2030: 2.608, 2050: 2.608}  # selected projects only (in the supply plan)
OFF_DELAY = {2025: .139, 2029: .454, 2030: 1.168, 2031: 2.608, 2035: 3.753, 2037: 4.553, 2050: 4.553}
SCEN = {
    # high: supply plan to 2035, master plan 2050 (onshore = supply-plan wind total minus planned offshore, floored at 2025 level)
    'plan': dict(wind_tot={2025: 2.41, 2030: 5.74, 2035: 7.28, 2050: 27.0}, off=OFF_PLAN, pv={2025: 9.82, 2030: 12.95, 2035: 16.16, 2050: 33.8},
                 dem={2025: 79.6, 2030: 79.1, 2035: 78.0, 2050: 116.0}),
    # trend: FY2015-25 growth continued (wind +0.17 GW/yr onshore, PV +0.74 GW/yr), delayed offshore list, flat demand
    'trend': dict(on={2025: 2.27, 2050: 2.27 + 0.17 * 25}, off=OFF_DELAY, pv={2025: 9.82, 2050: 9.82 + 0.74 * 25}, dem={2025: 79.6, 2050: 78.0}),
}
CF = {'on': .25, 'off': .35, 'pv': .13}
BETA_VF = [(0, .973), (.5, .894), (1, .830), (1.4, .790), (2, .744), (3, .698), (4, .676), (6, .667)]  # scan on 2050 profile

rows = []
for s, c in SCEN.items():
    for y in Y:
        off = ip(c['off'], y)
        # supply-plan wind total includes only awarded offshore -> onshore = total - awarded offshore
        on = max(ip(c['wind_tot'], y) - ip(OFF_AWARDED, y), 2.27) if 'wind_tot' in c else ip(c['on'], y)
        if 'wind_tot' in c and y == 2050:
            on = 18.2
        if 'wind_tot' in c and 2035 < y < 2050:
            on = ip({2035: 7.28 - ip(OFF_AWARDED, 2035), 2050: 18.2}, y)
        dem = ip(c['dem'], y) * 1000  # GWh
        sw = (on * CF['on'] + off * CF['off']) * 8760 / dem
        spv = ip(c['pv'], y) * CF['pv'] * 8760 / dem
        r = dict(scenario=s, year=y, onshore_GW=on, offshore_GW=off, pv_GW=ip(c['pv'], y), demand_TWh=dem / 1000, wind_share=sw, pv_share=spv)
        for k in (0.67, 1.5):
            vf = 0.973 - k * (sw - 0.076)
            r[f'VF_k{k}'] = vf
            bv = [b for b, v in BETA_VF]; vv = [v for b, v in BETA_VF]
            r[f'beta_k{k}'] = float(np.interp(-vf, [-v for v in vv], bv)) if vf >= min(vv) else np.nan  # nan = beyond this transform
        rows.append(r)
d = pd.DataFrame(rows)
d.round(3).to_csv(OUT / 'tohoku_penetration_beta.csv', index=False)
show = d[d.year.isin([2025, 2028, 2030, 2032, 2035, 2040, 2045, 2050])]
pd.set_option('display.width', 220)
print(show.round(3).to_string(index=False))

INK, MUTED, GRID = '#1f1f1d', '#6b6a66', '#e4e3df'
C1, C2 = '#2a78d6', '#eb6834'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': MUTED})
fig, ax = plt.subplots(1, 3, figsize=(13, 3.9))
for a in ax:
    a.grid(color=GRID, lw=0.8); a.set_axisbelow(True); a.set_xlim(2025, 2050)
    for sp in ('top', 'right'):
        a.spines[sp].set_visible(False)
for s, ls in (('plan', '-'), ('trend', '--')):
    x = d[d.scenario == s].set_index('year')
    ax[0].plot(x.index, 100 * x.wind_share, color=C1, ls=ls, lw=2, label=f'Wind, {s}')
    ax[0].plot(x.index, 100 * x.pv_share, color=C2, ls=ls, lw=2, label=f'Solar, {s}')
    ax[1].plot(x.index, x['VF_k0.67'], color=C1, ls=ls, lw=2, label=f'{s}, k = 0.67')
    ax[1].plot(x.index, x['VF_k1.5'], color=INK, ls=ls, lw=1.5, label=f'{s}, k = 1.5')
    ax[2].plot(x.index, x['beta_k0.67'], color=C1, ls=ls, lw=2, label=f'{s}, k = 0.67')
    ax[2].plot(x.index, x['beta_k1.5'], color=INK, ls=ls, lw=1.5, label=f'{s}, k = 1.5')
ax[1].axhline(0.667, color=C2, lw=1, ls=':'); ax[1].text(2026, 0.675, 'floor of current price transform', color=C2, fontsize=8)
ax[2].plot([2025, 2035, 2050], [0, 0.9, 1.4], color=MUTED, lw=1, ls=':', label='current default path')
ax[0].set_ylabel('% of Tohoku demand'); ax[0].set_title('(a) Wind and solar share (before curtailment)', loc='left', fontsize=10)
ax[1].set_ylabel('Wind value factor'); ax[1].set_title('(b) Target wind value factor', loc='left', fontsize=10)
ax[2].set_ylabel('β'); ax[2].set_title('(c) Implied β (gap = beyond transform)', loc='left', fontsize=10)
for a in ax:
    a.legend(frameon=False, fontsize=7); a.set_xlabel('Year')
fig.tight_layout(); fig.savefig(OUT / 'tohoku_penetration_beta.png', dpi=200)
