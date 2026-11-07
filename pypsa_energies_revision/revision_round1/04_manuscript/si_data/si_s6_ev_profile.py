"""SI S6: hourly check of the uncontrolled charging profile A (regime A and the non-participating half in B/C) against the
F6 EV parameters, and collection of the B/C feasibility statistics.

Reads (read-only):
  27_PyPSA_rebuild_20261016/inputs/fixed_fleet_charging_newbase.parquet   profile used by F6 (default_D2_args.txt --fixed-charge-profile)
       built by revision_round1/03_analysis/fixed_fleet_charging/build_fixed_profile.py --preset newbase
  27_PyPSA_rebuild_20261016/inputs/profiles.parquet                       vehicles, drive energy (MWh/h), connection share
  27_PyPSA_rebuild_20261016/results/f6_20261030/postprocess/ev_feasibility.csv   B0/BH/C0/CH hourly checks (src/f6_postprocess.py task 5)
  27_PyPSA_rebuild_20261016/results/f6_20261030/postprocess/ev_standing_loss.csv
F6 EV parameters (default_D2_args.txt; model.py PRESET_NEWBASE): 70 kWh nominal, capacity scale 0.9 (63 kWh usable), charger 10 kW,
charger efficiency 0.93, battery charge efficiency 0.98, standing loss 0.0005/h, floor 0.35 x 70 kWh, ceiling 0.96 x 63 kWh,
departure 0.8 x 63 kWh at the end of the 06:00 snapshot (07:00), new vehicles enter at 96%.
Writes:
  si_data/si_s6_profileA_checks.csv     per fleet: maximum violations of power limit, floor, ceiling, departure requirement, energy-balance
                                        residual, SoC range, hours at the power limit, energy totals, peak load
  si_data/si_s6_profileA_by_year.csv    per year: grid charging GWh (whole fleet), peak MW, traction GWh
Usage: python si_s6_ev_profile.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] / '27_PyPSA_rebuild_20261016'
NOM, SCALE, KW, ES, EBC, LAM = 0.07, 0.9, 0.01, 0.93, 0.98, 0.0005
USE = NOM * SCALE

fx = pd.read_parquet(ROOT / 'inputs' / 'fixed_fleet_charging_newbase.parquet')
pr = pd.read_parquet(ROOT / 'inputs' / 'profiles.parquet')
assert fx.index.equals(pr.index)
rows, yrs = [], {}
for g in ('commercial', 'residential'):
    N = pr[f'{g}_vehicles'].to_numpy(float); a = pr[f'{g}_availability'].to_numpy(float); drv = pr[f'{g}_drive_MWh'].to_numpy(float)
    P = fx[f'{g}_grid_charge_MW'].to_numpy(float); e = fx[f'{g}_stored_MWh'].to_numpy(float)
    lim = N * a * KW / ES                                   # AC-side limit, Equation (S11a)
    arrivals = np.diff(N, prepend=N[0]) * USE * 0.96
    prev = np.r_[e[0] - ES * EBC * P[0] + drv[0], e[:-1]]   # first hour: e_initial without standing loss (build_fixed_profile.py)
    ret = np.r_[1.0, np.full(len(e) - 1, 1 - LAM)]
    resid = e - (ret * prev - drv + arrivals + ES * EBC * P)
    resid[0] = e[0] - (0.96 * USE * N[0] - drv[0] + ES * EBC * P[0])
    floor = 0.35 * NOM * N; ceil = 0.96 * USE * N
    dep = pr.index.hour == 6
    soc = e / (N * USE) * 100
    rows.append({'fleet': g,
                 'max_power_excess_MW': float((P - lim).max()), 'hours_at_power_limit': int((P >= lim - 1e-9).sum() - (lim <= 1e-12).sum()),
                 'hours_below_target_after_charging': int((e < ceil - 1e-7).sum()),
                 'max_floor_violation_MWh': float((floor - e).max()), 'max_ceiling_violation_MWh': float((e - ceil).max()),
                 'max_departure_violation_MWh': float((0.8 * USE * N - e)[dep].max()),
                 'max_abs_balance_residual_MWh': float(np.abs(resid).max()),
                 'soc_min_pct_of_63kWh': float(soc.min()), 'soc_max_pct_of_63kWh': float(soc.max()),
                 'soc_min_at_0700_pct_of_63kWh': float(soc[dep].min()),
                 'grid_charge_GWh_2025_2050': P.sum() / 1000, 'traction_GWh_2025_2050': drv.sum() / 1000,
                 'charge_to_traction': P.sum() / drv.sum(), 'standing_loss_GWh_2025_2050': float((LAM * prev[1:]).sum() / 1000),
                 'peak_MW': float(P.max()), 'peak_time': str(pr.index[P.argmax()])})
    yrs[g] = pd.Series(P, index=pr.index).groupby(pr.index.year).sum() / 1000
tot = fx['commercial_grid_charge_MW'] + fx['residential_grid_charge_MW']
by = pd.DataFrame({'commercial_GWh': yrs['commercial'], 'residential_GWh': yrs['residential'],
                   'total_GWh': tot.groupby(tot.index.year).sum() / 1000, 'peak_MW': tot.groupby(tot.index.year).max(),
                   'traction_GWh': (pr.commercial_drive_MWh + pr.residential_drive_MWh).groupby(pr.index.year).sum() / 1000,
                   'vehicles': (pr.commercial_vehicles + pr.residential_vehicles).groupby(pr.index.year).first()})
by.index.name = 'year'
chk = pd.DataFrame(rows).set_index('fleet')
chk.to_csv(HERE / 'si_s6_profileA_checks.csv')
by.round(4).to_csv(HERE / 'si_s6_profileA_by_year.csv')

pd.set_option('display.width', 250)
print(chk.T.to_string())
print(by.loc[[2025, 2030, 2040, 2050]].round(3).to_string())
print('peak of total profile 2025-2050:', round(tot.max(), 2), 'MW at', tot.idxmax())
f = pd.read_csv(ROOT / 'results' / 'f6_20261030' / 'postprocess' / 'ev_feasibility.csv')
print(f[f.period == '2025-2050'].to_string())

# how often the 07:00 requirement binds in the optimized regimes (managed half, store_inventory.parquet of each F6 run)
dep = pr.index.hour == 6
rows = []
for c in ('B0', 'BH', 'C0', 'CH'):
    inv = pd.read_parquet(ROOT / 'results' / 'f6_20261030' / f'F6__{c}' / 'store_inventory.parquet')
    for g in ('commercial', 'residential'):
        n = 0.5 * pr[f'{g}_vehicles']
        req = 0.8 * USE * n
        e = inv[f'ev_{g}'].reindex(pr.index)
        bind = (e - req)[dep] <= 1e-6 * n[dep]
        rows.append({'case': c, 'fleet': g, 'days': int(dep.sum()), 'days_departure_binding': int(bind.sum()),
                     'share_binding': float(bind.mean()), 'min_soc_0700_pct': float((e / (USE * n))[dep].min() * 100),
                     'min_soc_pct': float((e / (USE * n)).min() * 100), 'max_soc_pct': float((e / (USE * n)).max() * 100)})
db = pd.DataFrame(rows)
db.to_csv(HERE / 'si_s6_departure_binding.csv', index=False)
print(db.round(4).to_string())
