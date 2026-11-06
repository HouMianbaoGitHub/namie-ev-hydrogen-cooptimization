"""Leave-one-year-out validation of the Tohoku price model (FY2023, FY2024, FY2025).

Model: price = supply curve(thermal need) + month-hour adjustment, thermal need = demand + net export - PV - wind -
nuclear - hydro - geothermal - biomass - pumped - battery (all actuals). For each held-out FY the curve is fitted on the
other two FYs. Outputs: validation_metrics.csv, validation.png/pdf.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
OTHER = ['tohoku_hydro', 'tohoku_geothermal', 'tohoku_biomass', 'tohoku_pumped', 'tohoku_battery', 'tohoku_nuclear']
d = pd.read_parquet(HERE / 'data/processed/hourly_tohoku_tokyo.parquet')
d = d[d.fy.between(2023, 2025)].dropna(subset=['tohoku_demand']).copy()
d['tn'] = d.tohoku_demand - d.tohoku_interconnector - d.tohoku_solar - d.tohoku_wind - d[OTHER].sum(axis=1)


def fit_predict(tr, te):
    c = tr.groupby((tr.tn / 250).round()).price_tohoku.median()
    n = tr.groupby((tr.tn / 250).round()).size(); c = c[n >= 20]
    base = lambda x: np.interp(x.tn / 250, c.index.values, c.values)
    mh = (tr.price_tohoku - base(tr)).groupby([tr.index.month, tr.index.hour]).median()
    return base(te) + np.array([mh.get((m, h), 0.0) for m, h in zip(te.index.month, te.index.hour)])


vf = lambda p, g: float((p * g).sum() / g.sum() / p.mean())
preds, rows = [], []
for fy in (2023, 2024, 2025):
    te = d[d.fy == fy].copy(); te['pred'] = np.clip(fit_predict(d[d.fy != fy], te), 0.01, None)
    a, p = te.price_tohoku, te.pred
    rows.append(dict(FY=fy, mean_actual=a.mean(), mean_pred=p.mean(), MAE=(p - a).abs().mean(), RMSE=np.sqrt(((p - a) ** 2).mean()),
                     corr=np.corrcoef(p, a)[0, 1], daily_mean_corr=np.corrcoef(p.resample('D').mean(), a.resample('D').mean())[0, 1],
                     VF_solar_actual=vf(a, te.tohoku_solar), VF_solar_pred=vf(p, te.tohoku_solar),
                     VF_wind_actual=vf(a, te.tohoku_wind), VF_wind_pred=vf(p, te.tohoku_wind),
                     hours_below5_actual=100 * (a < 5).mean(), hours_below5_pred=100 * (p < 5).mean()))
    preds.append(te)
m = pd.DataFrame(rows).set_index('FY'); m.round(3).to_csv(HERE / 'validation_metrics.csv')
pd.set_option('display.width', 250); print(m.round(3).to_string())
P = pd.concat(preds)

INK, MUTED, GRID = '#1f1f1d', '#6b6a66', '#e4e3df'
CA, CP = '#1f1f1d', '#2a78d6'
plt.rcParams.update({'font.size': 9, 'axes.edgecolor': MUTED, 'axes.labelcolor': INK, 'xtick.color': MUTED, 'ytick.color': MUTED})
fig, ax = plt.subplots(2, 2, figsize=(11, 7.4))
for a in ax.flat:
    a.grid(color=GRID, lw=0.8); a.set_axisbelow(True)
    for s in ('top', 'right'):
        a.spines[s].set_visible(False)
mm = P[['price_tohoku', 'pred']].resample('MS').mean()
a = ax[0, 0]; a.plot(mm.index, mm.price_tohoku, color=CA, lw=2, label='Actual JEPX Tohoku'); a.plot(mm.index, mm.pred, color=CP, lw=2, label='Model (held-out year)')
a.set_ylabel('JPY/kWh'); a.set_title('(a) Monthly mean price, FY2023–FY2025', loc='left', fontsize=10); a.legend(frameon=False, fontsize=8); a.set_ylim(0, None)
dh = P.groupby(P.index.hour)[['price_tohoku', 'pred']].mean()
a = ax[0, 1]; a.plot(dh.index, dh.price_tohoku, color=CA, lw=2, label='Actual'); a.plot(dh.index, dh.pred, color=CP, lw=2, label='Model')
a.set_xlabel('Hour of day'); a.set_ylabel('JPY/kWh'); a.set_title('(b) Mean diurnal profile', loc='left', fontsize=10); a.set_xlim(0, 23); a.set_ylim(0, None); a.legend(frameon=False, fontsize=8)
a = ax[1, 0]; q = np.linspace(0, 100, 201)
a.plot(q, np.percentile(P.price_tohoku, 100 - q), color=CA, lw=2, label='Actual'); a.plot(q, np.percentile(P.pred, 100 - q), color=CP, lw=2, label='Model')
a.set_xlabel('% of hours'); a.set_ylabel('JPY/kWh'); a.set_title('(c) Price duration curve', loc='left', fontsize=10); a.set_ylim(0, 40); a.set_xlim(0, 100); a.legend(frameon=False, fontsize=8)
wk = P.loc['2024-05-01':'2024-05-14']
a = ax[1, 1]; a.plot(wk.index, wk.price_tohoku, color=CA, lw=1.5, label='Actual'); a.plot(wk.index, wk.pred, color=CP, lw=1.5, label='Model')
a.set_ylabel('JPY/kWh'); a.set_title('(d) Hourly price, 1–14 May 2024 (held-out FY2024)', loc='left', fontsize=10); a.legend(frameon=False, fontsize=8)
a.tick_params(axis='x', labelrotation=30); a.set_ylim(0, None)
fig.tight_layout(); fig.savefig(HERE / 'validation.png', dpi=200); fig.savefig(HERE / 'validation.pdf')
