"""Necessary-condition screen for the EV cohort split (R1.4).

For each fleet cohort, charge at the maximum connected power whenever possible
(the most favourable policy for feasibility, ignoring grid limits) and subtract
traction energy. If SoC still falls below the 35% floor, no dispatch can be
feasible. Uses the same cohort construction as model.py (--ev-cohorts/--ev-cohort-theta).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
df = pd.read_parquet(ROOT / 'inputs' / 'profiles.parquet')
K = int(sys.argv[1]) if len(sys.argv) > 1 else 3
thetas = [float(x) for x in (sys.argv[2].split(',') if len(sys.argv) > 2 else ['0.5', '0.75', '1'])]
out = {}
for theta in thetas:
    for key in ('commercial', 'residential'):
        count = df[key + '_vehicles']; avail = df[key + '_availability']; away = count * (1 - avail)
        w = 1 / K
        for k in range(K):
            stack = (away - k * w * count).clip(lower=0).clip(upper=w * count)
            away_k = (1 - theta) * w * away + theta * stack
            count_k = count * w; avail_k = (1 - away_k / count_k).clip(0, 1)
            share = (away_k / away).where(away > 0, w)
            drive = (df[key + '_drive_MWh'] * share).to_numpy()
            cap = (count_k * 0.07).to_numpy(); lo = 0.35 * cap; hi = 0.96 * cap
            charge = (count_k * 0.01 * 0.95 * avail_k).to_numpy()   # battery-side MWh per hour
            arrivals = (count_k.diff().fillna(0) * 0.07 * 0.96).to_numpy()
            e = 0.96 * cap[0]; worst = np.inf; first_fail = None; fails = 0
            for t in range(len(df)):
                e = min(e * (1 - 0.0005) + arrivals[t] + charge[t], hi[t]) - drive[t]
                slack = e - lo[t]
                if slack < -1e-6:
                    fails += 1
                    if first_fail is None:
                        first_fail = str(df.index[t])
                    e = lo[t]                      # reset to keep scanning
                worst = min(worst, slack / cap[t])
            out[f'theta{theta}_{key}_c{k+1}'] = {'hours_below_floor': fails, 'first_failure': first_fail,
                                                 'worst_slack_share_of_capacity': worst,
                                                 'max_hourly_drive_per_vehicle_kWh': float((drive / count_k.to_numpy()).max() * 1000)}
print(json.dumps(out, indent=1))
(Path(__file__).with_name('cohort_feasibility_screen.json')).write_text(json.dumps(out, indent=2))
