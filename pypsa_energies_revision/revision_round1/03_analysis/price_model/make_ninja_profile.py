"""Build inputs/namie_renewables_ninja_2024.parquet from Renewables.ninja downloads (not redistributed here).

First download the two series with your own token:
  python fetch_ninja.py pv namie 37.494 140.993 2024
  python fetch_ninja.py wind namie_h80 37.494 140.993 2024 height=80
Then run this script from this folder.
"""
from pathlib import Path

import pandas as pd

RAW = Path(__file__).parent / 'data/raw/ninja'
OUT = Path(__file__).resolve().parents[3] / '27_PyPSA_rebuild_20261016/inputs/namie_renewables_ninja_2024.parquet'


def series(name):
    d = pd.read_csv(RAW / name, usecols=['local_time', 'electricity'], parse_dates=['local_time'])
    return d.set_index('local_time')['electricity']


df = pd.DataFrame({'solar_pu': series('namie_pv_2024.csv'), 'wind_pu': series('namie_h80_wind_2024.csv')})
df.index.name = 'ts'
df.to_parquet(OUT)
print(OUT, df.mean().round(4).to_dict())
