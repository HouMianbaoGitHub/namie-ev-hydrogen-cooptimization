"""Hourly Tohoku price series 2025-2050 from 2024 prices, wind-price coupling and curtailment (method only; raw data not included)."""

from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
REF = 2024
PV_REF_GW, WIND_REF_GW = (9.05, 2.24)
NUC_GW, NUC_CF = (0.825, 0.72)
PRICE_FLOOR = 0.01
DATC = {2024: 0, 2027: 0, 2028: 1920, 2030: 2720, 2032: 3670, 2050: 3670}
T_SPLIT = 5500
OTHER = ['tohoku_hydro', 'tohoku_geothermal', 'tohoku_biomass', 'tohoku_pumped', 'tohoku_battery']
d = pd.read_parquet(HERE / 'data/processed/hourly_tohoku_tokyo.parquet')
d['export'] = -d['tohoku_interconnector']
d['thermal_need'] = (
    d.tohoku_demand + d.export - d.tohoku_solar - d.tohoku_wind - d[OTHER].sum(axis=1) - d.tohoku_nuclear
)
fit = d[(d.fy >= 2023) & d.tohoku_demand.notna()].copy()
fit['bin'] = (fit.thermal_need / 250).round()
curve = fit.groupby('bin').price_tohoku.median()
counts = fit.groupby('bin').size()
curve = curve[counts >= 20]
T_MIN = float(fit.tohoku_thermal.quantile(0.001))


def supply(tn):
    b = np.asarray(tn) / 250
    return np.interp(b, curve.index.values, curve.values)


fit['base'] = supply(fit.thermal_need)
mh = (fit.price_tohoku - fit.base).groupby([fit.index.month, fit.index.hour]).median()


def price_of(tn, idx):
    p = supply(tn) + np.array([mh.get((m, h), 0.0) for m, h in zip(idx.month, idx.hour)])
    p = np.where(tn < T_MIN, PRICE_FLOOR, p)
    return np.clip(p, PRICE_FLOOR, None)


tr = fit[fit.fy <= 2024]
te = d[d.fy == 2025].dropna(subset=['tohoku_demand']).copy()
c24 = tr.groupby((tr.thermal_need / 250).round()).price_tohoku.median()
mh24 = (
    (tr.price_tohoku - np.interp(tr.thermal_need / 250, c24.index, c24.values))
    .groupby([tr.index.month, tr.index.hour])
    .median()
)
te['pred'] = np.interp(te.thermal_need / 250, c24.index, c24.values) + [
    mh24.get((m, h), 0) for m, h in zip(te.index.month, te.index.hour)
]
vf = lambda p, g: float((p * g).sum() / g.sum() / p.mean())
print(f'T_MIN (must-run thermal) = {T_MIN:.0f} MW')
print(
    'Validation FY2025 (fit FY2023-24): mean actual %.2f pred %.2f | MAE %.2f | corr %.2f | VF solar %.3f vs %.3f | VF wind %.3f vs %.3f'
    % (
        te.price_tohoku.mean(),
        te.pred.mean(),
        (te.pred - te.price_tohoku).abs().mean(),
        np.corrcoef(te.pred, te.price_tohoku)[0, 1],
        vf(te.pred, te.tohoku_solar),
        vf(te.price_tohoku, te.tohoku_solar),
        vf(te.pred, te.tohoku_wind),
        vf(te.price_tohoku, te.tohoku_wind),
    )
)
r = d.loc[str(REF)].copy()
pv_shape = (r.tohoku_solar + r.tohoku_solar_curtail) / (PV_REF_GW * 1000)
on_shape = (r.tohoku_wind + r.tohoku_wind_curtail) / (WIND_REF_GW * 1000)
SITES = {
    'off_oga_katagami': 315,
    'off_happo_noshiro': 375 + 139,
    'off_noshiro_mitane_oga': 415,
    'off_yurihonjo': 730,
    'off_aomori_south': 615 + 300,
    'off_murakami_tainai': 684,
    'off_yuza': 450 + 500,
}
off_shape = 0.0
for site, w in SITES.items():
    s = pd.read_csv(HERE / f'data/raw/ninja/{site}_wind_2024.csv')
    s.index = pd.to_datetime(s['local_time'])
    off_shape = off_shape + s['electricity'].reindex(r.index).interpolate().bfill().ffill() * w / sum(
        SITES.values()
    )
off_shape = off_shape.clip(upper=1.0)
dem_shape = r.tohoku_demand / r.tohoku_demand.sum()
other = r[OTHER].sum(axis=1)
export = r.export
print(
    f'2024 shapes: PV CF {pv_shape.mean():.3f}, onshore CF {on_shape.mean():.3f}, offshore CF {off_shape.mean():.3f} (ninja, capacity-weighted)'
)
cap = pd.read_csv(HERE.parent / 'tohoku_penetration_beta.csv')
cap = cap[cap.scenario == 'plan'].set_index('year')
out, summ = ({}, [])
for y, c in cap.iterrows():
    pv = pv_shape * c.pv_GW * 1000
    on = on_shape * c.onshore_GW * 1000
    off = off_shape * c.offshore_GW * 1000
    dem = dem_shape * c.demand_TWh * 1000000.0
    nuc = NUC_GW * NUC_CF * 1000 if y >= 2025 else 0.0
    tn = dem + export - pv - on - off - nuc - other
    datc = float(np.interp(y, sorted(DATC), [DATC[k] for k in sorted(DATC)]))
    extra_export = np.minimum(datc, np.clip(T_SPLIT - tn, 0, None))
    tn = tn + extra_export
    p = price_of(tn.values, r.index)
    curt = np.clip(T_MIN - tn.values, 0, None)
    vre = (pv + on + off).values
    out[y] = pd.DataFrame(
        {
            'price': p,
            'curtail_MW': curt,
            'curtail_rate': np.where(vre > 0, np.minimum(curt / np.maximum(vre, 1e-06), 1), 0),
        },
        index=r.index,
    )
    summ.append(
        dict(
            year=y,
            mean_price=p.mean(),
            wind_VF=vf(p, (on + off).values),
            solar_VF=vf(p, pv.values),
            hours_floor=int((p <= PRICE_FLOOR + 1e-09).sum()),
            p10=np.quantile(p, 0.1),
            p90=np.quantile(p, 0.9),
            curtail_TWh=curt.sum() / 1000000.0,
            curtail_pct_of_VRE=100 * curt.sum() / vre.sum(),
            extra_export_TWh=extra_export.sum() / 1000000.0,
        )
    )
s = pd.DataFrame(summ).set_index('year')
s.round(3).to_csv(HERE / 'future_prices_summary.csv')
pd.concat(out, names=['year', 'ts']).to_parquet(HERE / 'future_prices.parquet')
pd.set_option('display.width', 200)
print(s.loc[[2025, 2028, 2030, 2032, 2035, 2040, 2045, 2050]].round(3).to_string())
