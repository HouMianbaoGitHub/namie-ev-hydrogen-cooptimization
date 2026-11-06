"""Future hourly Tohoku-area price from the generation portfolio (reference weather/market year 2024).

Per hour t of reference year 2024 and model year y:
  thermal_need = demand_y(t) + net_export_2024(t) - PV_y(t) - onshore_y(t) - offshore_y(t) - nuclear_y(t) - other_2024(t)
  price = supply curve(thermal_need) + month-hour adjustment   (fitted on FY2023-FY2025 actuals, JEPX Tohoku)
  if thermal_need < T_MIN: price = 0.01 JPY/kWh and curtailment = T_MIN - thermal_need (VRE that cannot be absorbed)
Net export, hydro, geothermal, biomass, pumped storage and batteries are fixed at their 2024 hourly values (no feedback loop).
Shapes: demand, PV, onshore wind from Tohoku NW 2024 actuals (curtailment added back), scaled to plan capacities/demand.
Offshore wind: Renewables.ninja 2024, capacity-weighted over Tohoku sea areas (see SITES).
Plan scenario capacities: ../tohoku_penetration_beta.csv (scenario 'plan').
Outputs: future_prices.parquet (year x hour), future_prices_summary.csv, validation printout.
"""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
REF = 2024
PV_REF_GW, WIND_REF_GW = 9.05, 2.24          # calendar-2024 mean capacity (mean of FY2023/FY2024 year-end, reports/东北风光装机规划与需求.md)
NUC_GW, NUC_CF = 0.825, 0.72                 # Onagawa 2 (FY2025 actual 5.21 TWh); Higashidori not assumed
PRICE_FLOOR = 0.01
# Interconnector reinforcement (Tohoku-Tokyo): extra effective export capacity relative to 2024 (5.73 GW), MW.
# OCCTO: 10.28 GW nominal from 2027-11 but 6.8-8.5 GW effective; 7.8-9.1 GW in the 2030s; 9.2-9.6 GW around 2032
# (reports/东北海上风电项目与连系线计划.md); mid-points. Master-plan HVDC (Japan Sea route) not included (timing unverified).
DATC = {2024: 0, 2027: 0, 2028: 1920, 2030: 2720, 2032: 3670, 2050: 3670}
T_SPLIT = 5500   # thermal need below which Tohoku splits from Tokyo in >=50% of hours (FY2024-25): interconnector full
# Rule (no feedback loop): below T_SPLIT the 2024 interconnector was full; extra capacity lets Tohoku export up to
# DATC more, lifting thermal need back towards T_SPLIT (never above it).
OTHER = ['tohoku_hydro', 'tohoku_geothermal', 'tohoku_biomass', 'tohoku_pumped', 'tohoku_battery']

d = pd.read_parquet(HERE / 'data/processed/hourly_tohoku_tokyo.parquet')
d['export'] = -d['tohoku_interconnector']
d['thermal_need'] = d.tohoku_demand + d.export - d.tohoku_solar - d.tohoku_wind - d[OTHER].sum(axis=1) - d.tohoku_nuclear

# --- supply curve fitted on FY2023-FY2025 (2022 excluded: fuel crisis) -------------------------------------------------
fit = d[(d.fy >= 2023) & d.tohoku_demand.notna()].copy()
fit['bin'] = (fit.thermal_need / 250).round()
curve = fit.groupby('bin').price_tohoku.median()
counts = fit.groupby('bin').size()
curve = curve[counts >= 20]
T_MIN = float(fit.tohoku_thermal.quantile(0.001))          # lowest thermal output observed (must-run level)


def supply(tn):
    b = np.asarray(tn) / 250
    return np.interp(b, curve.index.values, curve.values)   # flat beyond the observed range


fit['base'] = supply(fit.thermal_need)
mh = (fit.price_tohoku - fit.base).groupby([fit.index.month, fit.index.hour]).median()


def price_of(tn, idx):
    p = supply(tn) + np.array([mh.get((m, h), 0.0) for m, h in zip(idx.month, idx.hour)])
    p = np.where(tn < T_MIN, PRICE_FLOOR, p)
    return np.clip(p, PRICE_FLOOR, None)


# --- validation: FY2025 out of sample with a curve fitted on FY2023-24 only ---------------------------------------------
tr = fit[fit.fy <= 2024]; te = d[(d.fy == 2025)].dropna(subset=['tohoku_demand']).copy()
c24 = tr.groupby((tr.thermal_need / 250).round()).price_tohoku.median()
mh24 = (tr.price_tohoku - np.interp(tr.thermal_need / 250, c24.index, c24.values)).groupby([tr.index.month, tr.index.hour]).median()
te['pred'] = np.interp(te.thermal_need / 250, c24.index, c24.values) + [mh24.get((m, h), 0) for m, h in zip(te.index.month, te.index.hour)]
vf = lambda p, g: float((p * g).sum() / g.sum() / p.mean())
print(f'T_MIN (must-run thermal) = {T_MIN:.0f} MW')
print('Validation FY2025 (fit FY2023-24): mean actual %.2f pred %.2f | MAE %.2f | corr %.2f | VF solar %.3f vs %.3f | VF wind %.3f vs %.3f' % (
    te.price_tohoku.mean(), te.pred.mean(), (te.pred - te.price_tohoku).abs().mean(), np.corrcoef(te.pred, te.price_tohoku)[0, 1],
    vf(te.pred, te.tohoku_solar), vf(te.price_tohoku, te.tohoku_solar), vf(te.pred, te.tohoku_wind), vf(te.price_tohoku, te.tohoku_wind)))

# --- reference-year shapes ----------------------------------------------------------------------------------------------
r = d.loc[str(REF)].copy()
pv_shape = (r.tohoku_solar + r.tohoku_solar_curtail) / (PV_REF_GW * 1000)          # p.u. of capacity, curtailment added back
on_shape = (r.tohoku_wind + r.tohoku_wind_curtail) / (WIND_REF_GW * 1000)
# Offshore: Renewables.ninja 2024 (MERRA-2, Vestas V164 8 MW, 110 m), capacity-weighted over the Tohoku sea areas of the
# plan list (reports/东北海上风电项目与连系线计划.md): port projects 139 MW use the Happo-Noshiro shape; Aomori north
# (300) uses Aomori south; Sakata (500) uses Yuza; re-auction Noshiro 415 / Yurihonjo 730 MW (max. grid injection).
SITES = {'off_oga_katagami': 315, 'off_happo_noshiro': 375 + 139, 'off_noshiro_mitane_oga': 415, 'off_yurihonjo': 730,
         'off_aomori_south': 615 + 300, 'off_murakami_tainai': 684, 'off_yuza': 450 + 500}
off_shape = 0.0
for site, w in SITES.items():
    s = pd.read_csv(HERE / f'data/raw/ninja/{site}_wind_2024.csv')
    s.index = pd.to_datetime(s['local_time'])
    off_shape = off_shape + s['electricity'].reindex(r.index).interpolate().bfill().ffill() * w / sum(SITES.values())
off_shape = off_shape.clip(upper=1.0)
dem_shape = r.tohoku_demand / r.tohoku_demand.sum()                                 # fraction of annual energy
other = r[OTHER].sum(axis=1); export = r.export
print(f'2024 shapes: PV CF {pv_shape.mean():.3f}, onshore CF {on_shape.mean():.3f}, offshore CF {off_shape.mean():.3f} (ninja, capacity-weighted)')

cap = pd.read_csv(HERE.parent / 'tohoku_penetration_beta.csv')
cap = cap[cap.scenario == 'plan'].set_index('year')
out, summ = {}, []
for y, c in cap.iterrows():
    pv = pv_shape * c.pv_GW * 1000; on = on_shape * c.onshore_GW * 1000; off = off_shape * c.offshore_GW * 1000
    dem = dem_shape * c.demand_TWh * 1e6
    nuc = NUC_GW * NUC_CF * 1000 if y >= 2025 else 0.0
    tn = dem + export - pv - on - off - nuc - other
    datc = float(np.interp(y, sorted(DATC), [DATC[k] for k in sorted(DATC)]))
    extra_export = np.minimum(datc, np.clip(T_SPLIT - tn, 0, None))
    tn = tn + extra_export
    p = price_of(tn.values, r.index)
    curt = np.clip(T_MIN - tn.values, 0, None)
    vre = (pv + on + off).values
    out[y] = pd.DataFrame({'price': p, 'curtail_MW': curt, 'curtail_rate': np.where(vre > 0, np.minimum(curt / np.maximum(vre, 1e-6), 1), 0)}, index=r.index)
    summ.append(dict(year=y, mean_price=p.mean(), wind_VF=vf(p, (on + off).values), solar_VF=vf(p, pv.values),
                     hours_floor=int((p <= PRICE_FLOOR + 1e-9).sum()), p10=np.quantile(p, .1), p90=np.quantile(p, .9),
                     curtail_TWh=curt.sum() / 1e6, curtail_pct_of_VRE=100 * curt.sum() / vre.sum(),
                     extra_export_TWh=extra_export.sum() / 1e6))
s = pd.DataFrame(summ).set_index('year')
s.round(3).to_csv(HERE / 'future_prices_summary.csv')
pd.concat(out, names=['year', 'ts']).to_parquet(HERE / 'future_prices.parquet')
pd.set_option('display.width', 200)
print(s.loc[[2025, 2028, 2030, 2032, 2035, 2040, 2045, 2050]].round(3).to_string())
