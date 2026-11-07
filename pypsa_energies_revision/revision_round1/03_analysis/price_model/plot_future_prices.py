"""Overview of the portfolio-based future Tohoku prices (future_prices.parquet / future_prices_summary.csv)."""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
s = pd.read_csv(HERE / 'future_prices_summary.csv', index_col=0)
f = pd.read_parquet(HERE / 'future_prices.parquet')
INK, MUTED, GRID = '#1f1f1d', '#6b6a66', '#e4e3df'
C1, C2, C3 = '#2a78d6', '#eb6834', '#1baf7a'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': MUTED})
fig, ax = plt.subplots(2, 2, figsize=(11, 7.4))
for a in ax.flat:
    a.grid(color=GRID, lw=0.8); a.set_axisbelow(True)
    for sp in ('top', 'right'):
        a.spines[sp].set_visible(False)

a = ax[0, 0]
a.fill_between(s.index, s.p10, s.p90, color=C1, alpha=0.12, lw=0, label='10–90th percentile')
a.plot(s.index, s.mean_price, color=INK, lw=2, label='Mean price')
a.plot(s.index, s.mean_price * s.wind_VF, color=C1, lw=2, label='Price earned by wind')
a.plot(s.index, s.mean_price * s.solar_VF, color=C2, lw=2, label='Price earned by solar')
a.set_xlim(2025, 2050); a.set_ylim(0, None); a.set_ylabel('JPY/kWh')
a.set_title('(a) Tohoku price by year (plan portfolio)', loc='left', fontsize=10); a.legend(frameon=False, fontsize=8, loc='lower left')

a = ax[0, 1]
a.plot(s.index, s.curtail_pct_of_VRE, color=C3, lw=2, label='Curtailment, % of wind+solar')
a.plot(s.index, 100 * s.hours_floor / 8784, color=MUTED, lw=1.5, ls='--', label='Hours at price floor, % of year')
a.set_xlim(2025, 2050); a.set_ylim(0, None); a.set_ylabel('%')
a.set_title('(b) Curtailment and floor-price hours', loc='left', fontsize=10); a.legend(frameon=False, fontsize=8)

a = ax[1, 0]
for y, c in ((2025, MUTED), (2035, C1), (2050, C2)):
    x = f.loc[y]; dh = x.groupby(x.index.hour).price.mean()
    a.plot(dh.index, dh.values, color=c, lw=2, label=str(y))
a.set_xlim(0, 23); a.set_ylim(0, None); a.set_xlabel('Hour of day'); a.set_ylabel('JPY/kWh')
a.set_title('(c) Mean diurnal profile', loc='left', fontsize=10); a.legend(frameon=False, fontsize=8)

a = ax[1, 1]
for y, c in ((2025, MUTED), (2035, C1), (2050, C2)):
    x = f.loc[y].loc['2024-05-01':'2024-05-07']
    a.plot(np.arange(len(x)), x.price.values, color=c, lw=1.4, label=str(y))
a.set_xlabel('Hour (1–7 May, 2024 weather)'); a.set_ylabel('JPY/kWh'); a.set_ylim(0, None)
a.set_title('(d) Hourly price, one spring week', loc='left', fontsize=10); a.legend(frameon=False, fontsize=8)
fig.tight_layout(); fig.savefig(HERE / 'future_prices.png', dpi=200); fig.savefig(HERE / 'future_prices.pdf')
