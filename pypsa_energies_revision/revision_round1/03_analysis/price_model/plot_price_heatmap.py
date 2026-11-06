"""Hourly heatmaps (day of year x hour) of the portfolio-based Tohoku price for selected model years, plus 2024 actual."""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
f = pd.read_parquet(HERE / 'future_prices.parquet')
act = pd.read_parquet(HERE / 'data/processed/hourly_tohoku_tokyo.parquet').loc['2024', 'price_tohoku']
panels = [('2024 actual (JEPX Tohoku)', act)] + [(f'{y} model', f.loc[y].price) for y in (2025, 2035, 2050)]
INK, MUTED = '#1f1f1d', '#6b6a66'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': MUTED})
fig, ax = plt.subplots(len(panels), 1, figsize=(11, 10), sharex=True)
for a, (title, s) in zip(ax, panels):
    m = s.groupby([s.index.dayofyear, s.index.hour]).mean().unstack()
    im = a.imshow(m.T.values, aspect='auto', origin='lower', cmap='viridis', vmin=0, vmax=20, extent=[1, m.shape[0] + 1, 0, 24])
    a.set_ylabel('Hour'); a.set_yticks([0, 6, 12, 18, 24])
    a.set_title(f'{title}: mean {s.mean():.1f} JPY/kWh, hours < 1 JPY: {100 * (s < 1).mean():.0f}%', loc='left', fontsize=10)
months = pd.date_range('2024-01-01', periods=12, freq='MS')
ax[-1].set_xticks(months.dayofyear); ax[-1].set_xticklabels(months.strftime('%b'))
cb = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.01); cb.set_label('JPY/kWh (capped at 20)')
fig.savefig(HERE / 'price_heatmap.png', dpi=180, bbox_inches='tight')
