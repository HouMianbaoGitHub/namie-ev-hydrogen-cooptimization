"""Download Renewables.ninja hourly capacity factors (token read from ~/.renewables_ninja_token, never stored here).

Usage: python fetch_ninja.py <kind wind|pv> <name> <lat> <lon> <year> [key=value ...]
Saves data/raw/ninja/<name>_<kind>_<year>.csv with columns time_utc, local_time, electricity (capacity factor).
"""
import io
import sys
import time
from pathlib import Path

import pandas as pd
import requests

OUT = Path(__file__).parent / 'data/raw/ninja'
TOKEN = (Path.home() / '.renewables_ninja_token').read_text().strip()
DEFAULTS = {'wind': dict(capacity=1, height=100, turbine='Vestas V90 2000'),
            'pv': dict(capacity=1, system_loss=0.1, tracking=0, tilt=35, azim=180)}


def fetch(kind, name, lat, lon, year, **kw):
    out = OUT / f'{name}_{kind}_{year}.csv'
    if out.exists():
        return pd.read_csv(out, index_col=0, parse_dates=True)
    params = dict(lat=lat, lon=lon, date_from=f'{year}-01-01', date_to=f'{year}-12-31', dataset='merra2',
                  format='csv', header='false', local_time='true', **DEFAULTS[kind])
    params.update(kw)
    r = requests.get(f'https://www.renewables.ninja/api/data/{kind}', params=params,
                     headers={'Authorization': f'Token {TOKEN}'}, timeout=120)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    time.sleep(1.2)  # burst limit 1/s
    return pd.read_csv(out, index_col=0, parse_dates=True)


if __name__ == '__main__':
    kind, name, lat, lon, year = sys.argv[1:6]
    extra = dict(a.split('=', 1) for a in sys.argv[6:])
    d = fetch(kind, name, float(lat), float(lon), int(year), **extra)
    print(d.head(3)); print(len(d), 'rows, mean CF', round(d.iloc[:, -1].mean(), 4))
