"""Price series with the intra-year spread scaled by 0.7 (review case spread070)."""

from pathlib import Path
import pandas as pd

INP = Path(__file__).resolve().parents[1] / 'inputs'
ps = pd.read_parquet(INP / 'electricity_price.parquet')
k = 0.7
m = ps.groupby(level='year')['price'].transform('mean')
out = ps.copy()
out['price'] = m + k * (ps['price'] - m)
assert (out['price'] > 0).all()
dst = INP / 'electricity_price_spread070.parquet'
assert not dst.exists(), dst
out.to_parquet(dst)
s = pd.DataFrame(
    {
        'mean_old': ps.groupby(level='year').price.mean(),
        'mean_new': out.groupby(level='year').price.mean(),
        'std_old': ps.groupby(level='year').price.std(),
        'std_new': out.groupby(level='year').price.std(),
        'min_new': out.groupby(level='year').price.min(),
    }
)
print(s.loc[[2025, 2030, 2040, 2050]].round(3))
print('wrote', dst.name)
