"""SI S7: cohort test (R1.4a) - results relative to the F6 base and a feasibility screen under the F6 EV parameters.

Reads (read-only):
  27_PyPSA_rebuild_20261016/results/sensF6_20261030/sensF6_summary.csv  (src/summarize_sensf6.py: C0 from sensF5 - F6 changes only
       hydrogen parameters, so no-hydrogen cases equal F5 -, CH from sensF6; EV_flex_CA = C0 - A0 with the base A0;
       I_S = (CH - C0) - (S2 - S1); ratio = (CH - C0)/(S2 - S1))
  27_PyPSA_rebuild_20261016/results/f6_20261030/F6_summary.csv          base A0 and AH (profile A is unchanged by the cohort split)
  27_PyPSA_rebuild_20261016/results/sensF5_20261030/coh4_t10__{C0,CH}/summary.json   termination condition of theta = 1
  27_PyPSA_rebuild_20261016/inputs/profiles.parquet                     fleet, connection share, drive energy
Cohort construction as in model.py (--ev-cohorts K --ev-cohort-theta theta, participation 0.5, F6 EV parameters).
Screen: for each cohort, charge at the maximum connected power in every hour (capped at the 96% ceiling, which V2G can always
restore) and subtract traction; this gives the highest energy any dispatch can reach, so an hour in which it is below the
35% floor or the 07:00 departure requirement proves the case infeasible (necessary condition; grid limits ignored).
Writes:
  si_data/si_s7_cohort_results.csv   per group: C0, CH, C0-A0, CH-AH, I_S, ratio, hydrogen capacities, changes vs base
  si_data/si_s7_cohort_screen.csv    per K, theta, fleet, cohort: hours below the lower bound, first failure, minimum slack
Usage: python si_s7_cohorts.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] / '27_PyPSA_rebuild_20261016'
R = ROOT / 'results'

s = pd.read_csv(R / 'sensF6_20261030' / 'sensF6_summary.csv', index_col=0)
b = pd.read_csv(R / 'f6_20261030' / 'F6_summary.csv').query("batch == 'F6'").set_index('case')
A0, AH = b.at['A0', 'npv'], b.at['AH', 'npv']
t = s.loc[['BASE', 'coh3_t05', 'coh3_t075', 'coh4_t05'], ['C0', 'CH', 'dH_S', 'dH_C', 'I_S', 'ratio', 'EV_flex_CA', 'el_CH_kgph', 'fc_CH_MW', 'tank_CH_t', 'first_h2_CH']].copy()
t['EV_flex_CH_AH'] = t.CH - AH
for c in ('C0', 'CH', 'EV_flex_CA', 'EV_flex_CH_AH', 'I_S', 'dH_C'):
    t[f'd_{c}'] = t[c] - t.at['BASE', c]
t['rel_EV_flex_CA_pct'] = 100 * t.d_EV_flex_CA / t.at['BASE', 'EV_flex_CA']
t['rel_EV_flex_CH_AH_pct'] = 100 * t.d_EV_flex_CH_AH / t.at['BASE', 'EV_flex_CH_AH']
term = {c: json.loads((R / 'sensF5_20261030' / f'coh4_t10__{c}' / 'summary.json').read_text()).get('termination_condition') for c in ('C0', 'CH')}
t.loc['coh4_t10'] = np.nan
t.to_csv(HERE / 'si_s7_cohort_results.csv')

# ---- screen under F6 parameters -------------------------------------------------------------------------------------------
NOM, USE, KW, ES, EBC, LAM, P = 0.07, 0.063, 0.01, 0.93, 0.98, 0.0005, 0.5
df = pd.read_parquet(ROOT / 'inputs' / 'profiles.parquet')
dep = (df.index.hour == 6)
rows = []
for K, theta in ((1, 0.0), (3, 0.5), (3, 0.75), (3, 1.0), (4, 0.5), (4, 1.0)):   # K = 1: aggregate fleet (reference)
    for key in ('commercial', 'residential'):
        count = df[key + '_vehicles'] * P; avail = df[key + '_availability']; away = count * (1 - avail); w = 1 / K
        for k in range(K):
            stack = (away - k * w * count).clip(lower=0).clip(upper=w * count)
            away_k = (1 - theta) * w * away + theta * stack
            count_k = count * w; avail_k = (1 - away_k / count_k).clip(0, 1)
            share = (away_k / away).where(away > 0, w)
            drive = (df[key + '_drive_MWh'] * P * share).to_numpy()
            n = count_k.to_numpy(); arr = np.diff(n, prepend=n[0]) * USE * 0.96
            chg = n * avail_k.to_numpy() * KW / ES * ES * EBC          # battery-side MWh per hour at full connected power
            hi = 0.96 * USE * n; lo = np.where(dep, np.maximum(0.35 * NOM, 0.8 * USE), 0.35 * NOM) * n
            e = 0.96 * USE * n[0]; fails = []; worst = np.inf
            for i in range(len(n)):
                e = min((1 - LAM) * e + arr[i] + chg[i] - drive[i], hi[i])
                sl = e - lo[i]
                worst = min(worst, sl / (NOM * n[i]))
                if sl < -1e-9:
                    fails.append(i); e = lo[i]
            ix = df.index[fails]
            md = ix.month * 100 + ix.day
            hol = ((md >= 429) & (md <= 506)) | ((md >= 811) & (md <= 817)) | (md >= 1228) | (md <= 104)   # Golden Week, Obon, New Year
            con0 = (avail_k.to_numpy() <= 1e-9).astype(int)                                           # cohort fully away
            edges = np.flatnonzero(np.diff(np.r_[0, con0, 0]))                                      # start, end, start, end, ...
            runs = (edges[1::2] - edges[0::2]) if con0.any() else np.array([0])
            rows.append({'failure_days': len({x.date() for x in ix}), 'failure_days_in_holiday_periods': len({x.date() for x, h in zip(ix, hol) if h}),
                         'longest_fully_away_h': int(runs.max()),'K': K, 'theta': theta, 'fleet': key, 'cohort': k + 1, 'hours_below_lower_bound': len(fails),
                         'of_which_at_0700': int(dep[fails].sum()) if fails else 0,
                         'first_failure': str(ix[0]) if len(ix) else '', 'failure_dates': ' '.join(sorted({str(x.date()) for x in ix}))[:400],
                         'failure_years': ' '.join(sorted({str(x.year) for x in ix})),
                         'min_slack_share_of_nominal': worst,
                         'max_drive_kWh_per_vehicle_h': float((drive / n).max() * 1000), 'max_away_share': float((away_k / count_k).max())})
sc = pd.DataFrame(rows)
sc.to_csv(HERE / 'si_s7_cohort_screen.csv', index=False)

pd.set_option('display.width', 250); pd.set_option('display.max_colwidth', 120)
print('theta=1 (K=4) termination:', term, '; base A0, AH =', round(A0, 4), round(AH, 4))
print(t.drop(columns=['first_h2_CH']).round(3).T.to_string())
print(sc.drop(columns=['failure_dates']).round(3).to_string())
print(sc.loc[sc.hours_below_lower_bound > 0, ['K', 'theta', 'fleet', 'cohort', 'failure_dates']].to_string())
