"""SI S14: 2050 (and 2025-2050) electricity flows of the nine F6 scenarios.

Reads (read-only):
  27_PyPSA_rebuild_20261016/results/f6_20261030/postprocess/energy_balance_summary.csv
  27_PyPSA_rebuild_20261016/results/f6_20261030/postprocess/mechanism_2050.csv
  27_PyPSA_rebuild_20261016/results/f6_20261030/F6__<case>/electricity_exchange.parquet (hourly import/export, MW)
Writes:
  si_data/si_s14_flows.csv  per case and period: supply and use (GWh), net export/import, curtailment rates,
                            interface indicators.
Net flows only: import and export carry the same price in the base case, so simultaneous gross import and export is a
zero-cost wash in the LP and gross volumes are not meaningful (f6_postprocess.py). Interface equivalent full-load hours =
net export (or net import) energy / 118 MW. Hours with net export / net import > 1 kW (TOL of f6_postprocess.py).
Usage: python si_s14_flows.py
"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RES = HERE.parents[2] / '27_PyPSA_rebuild_20261016' / 'results' / 'f6_20261030'
CASES = ['S0', 'S1', 'S2', 'A0', 'AH', 'B0', 'BH', 'C0', 'CH']
LIM, TOL = 118., 1e-3

eb = pd.read_csv(RES / 'postprocess' / 'energy_balance_summary.csv', dtype={'period': str})
rows = []
for c in CASES:
    x = pd.read_parquet(RES / f'F6__{c}' / 'electricity_exchange.parquet')
    net = x['export'] - x['import']
    for per, sel in (('2050', x.index.year == 2050), ('2025-2050', slice(None))):
        n = net[sel]
        e = eb[(eb.case == c) & (eb.period == per)].iloc[0]
        r = {'case': c, 'period': per}
        for k in ('wind_avail_GWh', 'wind_GWh', 'solar_avail_GWh', 'solar_GWh', 'hydro_GWh', 'biomass_GWh',
                  'net_import_GWh', 'net_export_GWh', 'load_fixed_GWh', 'ev_uncontrolled_GWh', 'ev_ch_GWh',
                  'ev_dis_grid_GWh', 'el_link_GWh', 'el_aux_GWh', 'h2_aux_GWh', 'el_elec_GWh', 'el_aux_dump_ub_GWh',
                  'fc_out_GWh', 'vre_curtail_GWh', 'vre_curtail_rate', 'wind_curtail_rate', 'solar_curtail_rate',
                  'curtail_incl_aux_dump_ub_rate', 'el_import_share', 'ev_ch_from_import_share',
                  'net_export_at_limit_hours'):
            r[k] = e[k]
        nyears = len(set(n.index.year))
        r['net_export_flh_h'] = e.net_export_GWh * 1000 / LIM / nyears
        r['net_import_flh_h'] = e.net_import_GWh * 1000 / LIM / nyears
        r['hours_net_export'] = int((n > TOL).sum()) / nyears
        r['hours_net_import'] = int((n < -TOL).sum()) / nyears
        r['net_export_at_limit_hours_per_yr'] = e.net_export_at_limit_hours / nyears
        # check the net-flow totals against the postprocess summary
        assert abs(n.clip(lower=0).sum() / 1000 - e.net_export_GWh) < 1e-3 * max(1., e.net_export_GWh)
        assert abs((-n).clip(lower=0).sum() / 1000 - e.net_import_GWh) < 1e-3 * max(1., e.net_import_GWh)
        # electricity balance with net exchange: supply - use (GWh)
        sup = e.wind_GWh + e.solar_GWh + e.hydro_GWh + e.biomass_GWh + e.net_import_GWh + e.fc_out_GWh + e.ev_dis_grid_GWh
        use = (e.net_export_GWh + e.load_fixed_GWh + e.ev_uncontrolled_GWh + e.ev_ch_GWh + e.el_link_GWh + e.el_aux_GWh
               + e.h2_aux_GWh)
        r['balance_residual_GWh'] = sup - use
        rows.append(r)
out = pd.DataFrame(rows)
mech = pd.read_csv(RES / 'postprocess' / 'mechanism_2050.csv').set_index('case')
out = out.join(mech[['hours_vre_curtailed', 'hours_import']].add_prefix('mech2050_'), on='case')
out.to_csv(HERE / 'si_s14_flows.csv', index=False)
pd.set_option('display.width', 250); pd.set_option('display.max_columns', 60)
print(out.set_index(['case', 'period']).T.round(3).to_string())
