# Namie Town EV–Hydrogen Co-Optimization — PLEXOS Model and Input Data

PLEXOS model files and input data for a municipality-scale capacity-expansion and hourly-dispatch
study of Namie Town, Fukushima, Japan (2025–2050), examining how electric-vehicle (V2G) flexibility
and hydrogen storage interact in a high-renewable, export-oriented regional energy system.

**Authors:** Tuo Zhang, Takuro Kobashi
Graduate School of Environmental Studies, Tohoku University, Sendai 980-8572, Japan
Corresponding author: zhang.tuo.b7@tohoku.ac.jp

---

## Contents

```
.
├── S0_BAU.xml                 Business as usual
├── S1_RenewableOnly.xml       Renewable expansion only
├── S2_RE_Hydrogen.xml         Renewable expansion + hydrogen
├── S3_RE_EV.xml               Renewable expansion + EV flexibility
├── S4_RE_Hydrogen_EV.xml      Renewable expansion + hydrogen + EV flexibility
└── DataFiles/                 Input time series and cost trajectories
```

Model files are PLEXOS 11.0 databases, solved with Gurobi 12.0.0 at a 0.1 % relative optimality gap.

---

## Requirements

- **PLEXOS 11.0** or later (Energy Exemplar). A commercial licence is required.
- **Gurobi 12.0.0** or a compatible MILP solver.

Open an `.xml` file in PLEXOS and the relative paths under `DataFiles/` resolve automatically,
provided the `.xml` and `DataFiles/` stay siblings in the same directory.

---

## Input data referenced by the models

The 18 files below are the ones the five model databases read directly. The remaining files in
`DataFiles/` are supporting inputs and intermediate series retained for transparency.

### Technology cost trajectories (annual, 2024–2050)

| File | Technology | Unit |
|---|---|---|
| `DataFiles/1_Fuel_cell_BuildCost.csv` | Fuel cell | JPY/kW |
| `DataFiles/P2H  facility build cost.csv` | Electrolyser (power-to-hydrogen facility) | JPY per unit |
| `DataFiles/h2 Storage build cost.csv` | Hydrogen storage tank | JPY per unit |
| `DataFiles/Build_Cost_Rooftop_Yearly.csv` | Rooftop solar PV | JPY/kW |
| `DataFiles/Build_Cost_UtilityPV_Yearly.csv` | Utility-scale solar PV | JPY/kW |
| `DataFiles/Build_Cost_WindOnshore_Yearly.csv` | Onshore wind | JPY/kW |
| `DataFiles/Build_Cost_Offshore_Yearly.csv` | Offshore wind | JPY/kW |

These correspond to Appendix A of the manuscript. The fuel-cell, electrolyser and hydrogen-storage
trajectories all decline monotonically over the horizon.

### Demand, resource and market time series

| File | Content |
|---|---|
| `DataFiles/load_2024_2050.csv` | Hourly electricity demand by node, 2024–2050 |
| `DataFiles/ElectricityPrice_Forecast_2024_2050.csv` | Hourly Tohoku wholesale price projection |
| `DataFiles/RF_SolarPV/RF_Solar_Namie.csv` | Solar capacity factors |
| `DataFiles/RF_Wind/RF_Wind_Namie.csv` | Onshore wind capacity factors |
| `DataFiles/RF_OffshoreWind/RF_OffshoreWind_Namie.csv` | Offshore wind capacity factors |
| `DataFiles/Hydro_MaxEnergyMonth.csv` | Monthly hydropower energy limits |

### EV fleet and mobility

| File | Content |
|---|---|
| `DataFiles/EV_data/ev_data_2018_2050.csv` | Hourly EV driving demand and availability |
| `DataFiles/EV_data/ev_charging_share_2018_2050.csv` | Hourly charger-availability share |
| `DataFiles/EV_data/EVforecast - Integrated.csv` | Annual EV fleet trajectory |
| `DataFiles/ChargingStationsForecast - integrated.csv` | Charging-station deployment trajectory |

### Hydrogen market

| File | Content |
|---|---|
| `DataFiles/Hydrogen_Biomass_Market_Benchmark_Price_yearly.csv` | Benchmark hydrogen price |

---

## Notes and known quirks

- **`P2H  facility build cost.csv` contains two consecutive spaces** in its filename. This is
  intentional and must not be corrected: the path is hard-coded inside the PLEXOS databases, and
  renaming the file will break the models. Scripts reading this directory should quote paths.
- Several filenames contain spaces, `&`, or a trailing ` - variant` suffix, for the same reason.
- `DataFiles/` retains a small number of supporting and historical series beyond the 18 files listed
  above. Exact-duplicate copies and unused intermediate outputs have been removed; what remains is
  either read by the models or kept because it documents how an input was derived.

---

## Data not included here

Hourly and annual result time series (about 1.9 GB across the five scenarios) exceed what is
practical to host in a Git repository. They are available from the corresponding author on
reasonable request, or via the Zenodo record linked in the publication.

The transport model and related mobility data are separately available at
<https://zenodo.org/records/16777118>.

---

## Citation

If you use these files, please cite the associated publication. Citation details will be added here
once the paper is published.

---

## Licence

Released under the **Creative Commons Attribution 4.0 International (CC BY 4.0)** licence.
See [`LICENSE`](LICENSE).

Note that the PLEXOS software itself is commercial and is not distributed here; only the model
databases and input data are covered by this licence.

---

## Acknowledgements

This work was supported by JSPS KAKENHI Grant Number 25K15551 and the Fukushima Institute for
Research, Education and Innovation (F-REI).
