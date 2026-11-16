"""Tohoku-area wind and solar penetration by year and the implied wind-price coupling."""

from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path(__file__).parent
Y = np.arange(2025, 2051)
ip = lambda pts, y: float(np.interp(y, sorted(pts), [pts[k] for k in sorted(pts)]))
OFF_PLAN = {
    2025: 0.139,
    2027: 0.139,
    2028: 0.454,
    2029: 1.513,
    2030: 2.608,
    2033: 3.753,
    2035: 4.553,
    2040: 4.553,
    2050: 8.8,
}
OFF_AWARDED = {2025: 0.139, 2027: 0.139, 2028: 0.454, 2029: 1.513, 2030: 2.608, 2050: 2.608}
OFF_DELAY = {2025: 0.139, 2029: 0.454, 2030: 1.168, 2031: 2.608, 2035: 3.753, 2037: 4.553, 2050: 4.553}
SCEN = {
    'plan': dict(
        wind_tot={2025: 2.41, 2030: 5.74, 2035: 7.28, 2050: 27.0},
        off=OFF_PLAN,
        pv={2025: 9.82, 2030: 12.95, 2035: 16.16, 2050: 33.8},
        dem={2025: 79.6, 2030: 79.1, 2035: 78.0, 2050: 116.0},
    ),
    'trend': dict(
        on={2025: 2.27, 2050: 2.27 + 0.17 * 25},
        off=OFF_DELAY,
        pv={2025: 9.82, 2050: 9.82 + 0.74 * 25},
        dem={2025: 79.6, 2050: 78.0},
    ),
}
CF = {'on': 0.25, 'off': 0.35, 'pv': 0.13}
BETA_VF = [(0, 0.973), (0.5, 0.894), (1, 0.83), (1.4, 0.79), (2, 0.744), (3, 0.698), (4, 0.676), (6, 0.667)]
rows = []
for s, c in SCEN.items():
    for y in Y:
        off = ip(c['off'], y)
        on = max(ip(c['wind_tot'], y) - ip(OFF_AWARDED, y), 2.27) if 'wind_tot' in c else ip(c['on'], y)
        if 'wind_tot' in c and y == 2050:
            on = 18.2
        if 'wind_tot' in c and 2035 < y < 2050:
            on = ip({2035: 7.28 - ip(OFF_AWARDED, 2035), 2050: 18.2}, y)
        dem = ip(c['dem'], y) * 1000
        sw = (on * CF['on'] + off * CF['off']) * 8760 / dem
        spv = ip(c['pv'], y) * CF['pv'] * 8760 / dem
        r = dict(
            scenario=s,
            year=y,
            onshore_GW=on,
            offshore_GW=off,
            pv_GW=ip(c['pv'], y),
            demand_TWh=dem / 1000,
            wind_share=sw,
            pv_share=spv,
        )
        for k in (0.67, 1.5):
            vf = 0.973 - k * (sw - 0.076)
            r[f'VF_k{k}'] = vf
            bv = [b for b, v in BETA_VF]
            vv = [v for b, v in BETA_VF]
            r[f'beta_k{k}'] = float(np.interp(-vf, [-v for v in vv], bv)) if vf >= min(vv) else np.nan
        rows.append(r)
d = pd.DataFrame(rows)
d.round(3).to_csv(OUT / 'tohoku_penetration_beta.csv', index=False)
show = d[d.year.isin([2025, 2028, 2030, 2032, 2035, 2040, 2045, 2050])]
pd.set_option('display.width', 220)
print(show.round(3).to_string(index=False))
INK, MUTED, GRID = ('#1f1f1d', '#6b6a66', '#e4e3df')
C1, C2 = ('#2a78d6', '#eb6834')
plt.rcParams.update(
    {
        'font.size': 9,
        'axes.edgecolor': MUTED,
        'axes.labelcolor': INK,
        'xtick.color': MUTED,
        'ytick.color': MUTED,
    }
)
fig, ax = plt.subplots(1, 3, figsize=(13, 3.9))
for a in ax:
    a.grid(color=GRID, lw=0.8)
    a.set_axisbelow(True)
    a.set_xlim(2025, 2050)
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
ax[1].axhline(0.667, color=C2, lw=1, ls=':')
ax[1].text(2026, 0.675, 'floor of current price transform', color=C2, fontsize=8)
ax[2].plot([2025, 2035, 2050], [0, 0.9, 1.4], color=MUTED, lw=1, ls=':', label='current default path')
ax[0].set_ylabel('% of Tohoku demand')
ax[0].set_title('(a) Wind and solar share (before curtailment)', loc='left', fontsize=10)
ax[1].set_ylabel('Wind value factor')
ax[1].set_title('(b) Target wind value factor', loc='left', fontsize=10)
ax[2].set_ylabel('β')
ax[2].set_title('(c) Implied β (gap = beyond transform)', loc='left', fontsize=10)
for a in ax:
    a.legend(frameon=False, fontsize=7)
    a.set_xlabel('Year')
fig.tight_layout()
fig.savefig(OUT / 'tohoku_penetration_beta.png', dpi=200)
