"""SI S4: hourly non-EV load as used by the F6 model, by year and sector.

Reads (read-only):
  27_PyPSA_rebuild_20261016/inputs/profiles.parquet               load_MW (model.py: n.add('Load','fixed_load', p_set=df.load_MW), load_scale = 1 in F6)
  27_PyPSA_rebuild_20261016/inputs/historical_s4/DataFiles/load_2024_2050.csv   node-level load of the original model (prepare_inputs.py sums
                                                                    the three active nodes of S4_parameters.json into load_MW)
  27_PyPSA_rebuild_20261016/inputs/S4_parameters.json             active load nodes
Writes:
  si_data/si_s4_load_by_year.csv    annual energy (GWh), peak, minimum, mean (MW), load factor, by model year 2025-2050 (+ 2024 from the node file)
  si_data/si_s4_load_sectors.csv    energy by node (sector) for 2024, 2025, 2050 and shares
  si_data/si_s4_load_shape.csv      2050 mean load by hour of day and energy by month; shape-identity check across years
Usage: python si_s4_load.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] / '27_PyPSA_rebuild_20261016'
INP = ROOT / 'inputs'

p = pd.read_parquet(INP / 'profiles.parquet')
L = p['load_MW']
g = L.groupby(L.index.year)
yr = pd.DataFrame({'energy_GWh': g.sum() / 1000, 'peak_MW': g.max(), 'min_MW': g.min(), 'mean_MW': g.mean(), 'hours': g.size()})
yr['load_factor'] = yr.mean_MW / yr.peak_MW
yr.index.name = 'year'

node = pd.read_csv(INP / 'historical_s4' / 'DataFiles' / 'load_2024_2050.csv')
node.index = pd.to_datetime(node.pop('DATETIME'), format='mixed')
cfg = json.loads((INP / 'S4_parameters.json').read_text(encoding='utf-8'))
active = [k for k, v in cfg.items() if v.get('Load', {}).get('file')]
ann = node[active].groupby(node.index.year).sum() / 1000
yr.loc[2024, 'energy_GWh'] = ann.loc[2024].sum()          # base year of the plan (not a model year)
yr = yr.sort_index()
# consistency: node file summed over active nodes equals the model load in every model year
diff = (ann.loc[2025:2050].sum(axis=1) - yr.loc[2025:2050, 'energy_GWh']).abs().max()
yr.round(4).to_csv(HERE / 'si_s4_load_by_year.csv')

sec = ann.loc[[2024, 2025, 2050]].T
for y in (2024, 2025, 2050):
    sec[f'share_{y}'] = sec[y] / sec[y].sum()
sec.index.name = 'node'
sec.round(4).to_csv(HERE / 'si_s4_load_sectors.csv')

# shape: normalised hourly profile identical across years (except the leap day)?
def norm(y):
    s = L.loc[str(y)]
    s = s[~((s.index.month == 2) & (s.index.day == 29))]
    return (s / s.sum()).to_numpy()
corr = min(np.corrcoef(norm(2025), norm(y))[0, 1] for y in range(2026, 2051))
l50 = L.loc['2050']
hod = l50.groupby(l50.index.hour).mean().rename('mean_MW_2050_by_hour')
mon = (l50.groupby(l50.index.month).sum() / 1000).rename('GWh_2050_by_month')
shape = pd.concat([hod, mon], axis=1)
shape.index.name = 'hour_or_month'
shape.round(4).to_csv(HERE / 'si_s4_load_shape.csv')

print(yr.loc[[2024, 2025, 2030, 2035, 2040, 2045, 2050]].round(3).to_string())
print(sec.round(4).to_string())
print(f'max |node sum - model load| over 2025-2050 = {diff:.2e} GWh; min correlation of normalised 2025 shape with other years = {corr:.6f}')
print(f'2050: peak hour of mean diurnal load = {hod.idxmax()} h ({hod.max():.2f} MW), lowest = {hod.idxmin()} h ({hod.min():.2f} MW); '
      f'max month {mon.idxmax()} ({mon.max():.3f} GWh), min month {mon.idxmin()} ({mon.min():.3f} GWh)')
