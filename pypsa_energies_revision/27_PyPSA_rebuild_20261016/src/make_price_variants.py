"""Price-shape variants of the F6 price series for the 2026-11-01 review sensitivity (registry sensitivity_review_F6_20261101).
spread070: in every model year, price = annual mean + 0.7 x (price - annual mean); annual mean unchanged, curtail_rate unchanged.
Input : inputs/tohoku_price_plan_ref2024.parquet   (year, ts) -> price [JPY/kWh], curtail_rate
Output: inputs/tohoku_price_plan_ref2024_spread070.parquet
Usage: python make_price_variants.py"""
from pathlib import Path

import pandas as pd

INP = Path(__file__).resolve().parents[1] / 'inputs'
ps = pd.read_parquet(INP / 'tohoku_price_plan_ref2024.parquet')
k = 0.7
m = ps.groupby(level='year')['price'].transform('mean')
out = ps.copy()
out['price'] = m + k * (ps['price'] - m)
assert (out['price'] > 0).all()
dst = INP / 'tohoku_price_plan_ref2024_spread070.parquet'
assert not dst.exists(), dst
out.to_parquet(dst)
s = pd.DataFrame({'mean_old': ps.groupby(level='year').price.mean(), 'mean_new': out.groupby(level='year').price.mean(),
                  'std_old': ps.groupby(level='year').price.std(), 'std_new': out.groupby(level='year').price.std(),
                  'min_new': out.groupby(level='year').price.min()})
print(s.loc[[2025, 2030, 2040, 2050]].round(3))
print('wrote', dst.name)
