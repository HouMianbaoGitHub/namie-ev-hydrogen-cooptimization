"""Decompose the leave-one-year-out error of the price model into a monthly-level part and a within-month part.
Reuses fit_predict from revision_round1/03_analysis/price_model/validate_price_model.py (copied, read-only)."""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
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


rows = []
for fy in (2023, 2024, 2025):
    te = d[d.fy == fy].copy(); te['pred'] = np.clip(fit_predict(d[d.fy != fy], te), 0.01, None)
    a, p = te.price_tohoku, te.pred
    ym = te.index.to_period('M')
    ma, mp = a.groupby(ym).transform('mean'), p.groupby(ym).transform('mean')
    p_adj = p - mp + ma                                   # model with each month's mean set to the actual month mean
    da, dp = a - ma, p - mp                               # within-month deviations
    e = p - a
    lvl = (mp - ma)                                       # monthly level error, per hour
    mon = pd.DataFrame({'a': a, 'p': p}).groupby(ym).mean()
    rows.append(dict(FY=fy,
                     MAE=e.abs().mean(), corr=np.corrcoef(p, a)[0, 1],
                     monthly_mean_corr=np.corrcoef(mon.p, mon.a)[0, 1],
                     monthly_level_MAE=(mon.p - mon.a).abs().mean(),
                     share_MSE_monthly_level=(lvl ** 2).mean() / (e ** 2).mean(),
                     MAE_month_level_removed=(p_adj - a).abs().mean(),
                     corr_within_month=np.corrcoef(dp, da)[0, 1],
                     corr_month_level_removed=np.corrcoef(p_adj, a)[0, 1],
                     corr_diurnal_profile=np.corrcoef(p.groupby(te.index.hour).mean(), a.groupby(te.index.hour).mean())[0, 1],
                     mean_price=a.mean()))
r = pd.DataFrame(rows).set_index('FY').round(3)
pd.set_option('display.width', 250)
print(r.T.to_string())
