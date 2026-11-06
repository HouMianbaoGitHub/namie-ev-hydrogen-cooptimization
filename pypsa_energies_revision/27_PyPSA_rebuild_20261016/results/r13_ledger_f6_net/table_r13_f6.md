# R1.3 present-value ledger, F6 default (billion JPY, PV 2024, 3%)

Horizon 2025-2050, every asset paid as a finite-life annuity (capital recovery + fixed O&M) from its build year to 2050; no perpetuity (2050 weighted as one year). Capital charged = full-life capital cost minus the salvage value at end-2050 (PV of the capital-recovery annuities falling after 2050). Indented lines are components of the line below them; NPV = export revenue + purchases + operating + electrolyzer start-up wear + capital charged + fixed O&M. Revenues positive, costs negative.

## Table 1. Ledger by case

| Item | S0 | S1 | S2 | A0 | AH | B0 | BH | C0 | CH |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Electricity export revenue | 22.43 | 79.26 | 83.29 | 76.79 | 80.55 | 77.84 | 81.51 | 80.67 | 83.78 |
| Electricity purchases | -2.22 | -0.81 | -0.63 | -1.56 | -1.12 | -1.16 | -0.87 | -1.33 | -1.16 |
| Operating costs (electrolyzer VOM, V2G throughput, biomass) | -0.00 | -0.00 | -0.08 | -0.00 | -0.08 | -0.00 | -0.07 | -0.82 | -0.86 |
| Electrolyzer start-up wear (solver term) | -0.00 | -0.00 | -0.10 | -0.00 | -0.09 | -0.00 | -0.09 | -0.00 | -0.08 |
| &nbsp;&nbsp;Wind: full-life capital cost | 0.00 | -48.92 | -47.39 | -51.34 | -50.09 | -50.73 | -49.59 | -51.56 | -49.97 |
| &nbsp;&nbsp;Wind: less salvage value at end-2050 (credit) | -0.00 | 11.92 | 10.55 | 12.88 | 11.78 | 12.46 | 11.44 | 12.73 | 11.35 |
| Wind: capital charged to 2050 | 0.00 | -37.00 | -36.84 | -38.46 | -38.31 | -38.27 | -38.15 | -38.83 | -38.61 |
| Wind: fixed O&M to 2050 | 0.00 | -2.76 | -2.73 | -2.89 | -2.86 | -2.86 | -2.84 | -2.91 | -2.88 |
| &nbsp;&nbsp;Hydrogen: full-life capital cost | 0.00 | -0.00 | -9.98 | -0.00 | -9.72 | -0.00 | -9.23 | -0.00 | -8.56 |
| &nbsp;&nbsp;Hydrogen: less salvage value at end-2050 (credit) | -0.00 | 0.00 | 7.16 | 0.00 | 6.93 | 0.00 | 6.61 | 0.00 | 6.26 |
| Hydrogen: capital charged to 2050 | 0.00 | -0.00 | -2.81 | -0.00 | -2.79 | -0.00 | -2.62 | -0.00 | -2.30 |
| Hydrogen: fixed O&M to 2050 | 0.00 | -0.00 | -0.87 | -0.00 | -0.86 | -0.00 | -0.81 | -0.00 | -0.70 |
| **NPV** | **20.21** | **38.69** | **39.23** | **33.89** | **34.43** | **35.56** | **36.05** | **36.78** | **37.19** |

Residual (ledger NPV - solver NPV), billion JPY: S0 2.5e-13, S1 -2.6e-12, S2 2.8e-11, A0 -3.3e-12, AH -1.3e-11, B0 -7.1e-14, BH 1.1e-11, C0 -2.3e-12, CH -2.8e-11

## Table 2. Increments

| Item | S2-S1 | CH-C0 | AH-A0 | C0-A0 | B0-A0 | C0-B0 | (CH-C0)-(AH-A0) | CH-BH |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Electricity export revenue | 4.04 | 3.11 | 3.76 | 3.88 | 1.06 | 2.83 | -0.65 | 2.27 |
| Electricity purchases | 0.18 | 0.17 | 0.44 | 0.22 | 0.40 | -0.18 | -0.27 | -0.29 |
| Operating costs (electrolyzer VOM, V2G throughput, biomass) | -0.08 | -0.04 | -0.08 | -0.82 | -0.00 | -0.82 | 0.03 | -0.79 |
| Electrolyzer start-up wear (solver term) | -0.10 | -0.08 | -0.09 | 0.00 | 0.00 | 0.00 | 0.02 | 0.01 |
| &nbsp;&nbsp;Wind: full-life capital cost | 1.53 | 1.59 | 1.25 | -0.22 | 0.61 | -0.83 | 0.34 | -0.38 |
| &nbsp;&nbsp;Wind: less salvage value at end-2050 (credit) | -1.37 | -1.37 | -1.10 | -0.15 | -0.42 | 0.27 | -0.27 | -0.08 |
| Wind: capital charged to 2050 | 0.16 | 0.22 | 0.14 | -0.37 | 0.19 | -0.56 | 0.07 | -0.46 |
| Wind: fixed O&M to 2050 | 0.03 | 0.03 | 0.02 | -0.02 | 0.02 | -0.05 | 0.01 | -0.03 |
| &nbsp;&nbsp;Hydrogen: full-life capital cost | -9.98 | -8.56 | -9.72 | 0.00 | 0.00 | 0.00 | 1.16 | 0.67 |
| &nbsp;&nbsp;Hydrogen: less salvage value at end-2050 (credit) | 7.16 | 6.26 | 6.93 | 0.00 | 0.00 | 0.00 | -0.67 | -0.35 |
| Hydrogen: capital charged to 2050 | -2.81 | -2.30 | -2.79 | 0.00 | 0.00 | 0.00 | 0.49 | 0.32 |
| Hydrogen: fixed O&M to 2050 | -0.87 | -0.70 | -0.86 | 0.00 | 0.00 | 0.00 | 0.16 | 0.10 |
| **NPV** | **0.54** | **0.40** | **0.54** | **2.90** | **1.67** | **1.23** | **-0.14** | **1.13** |

## Table 3. Flows by period (payment year; salvage enters the capital charged)

### 2025-2039

| Item | S0 | S1 | S2 | A0 | AH | B0 | BH | C0 | CH |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Electricity export revenue | 18.27 | 55.39 | 55.39 | 54.06 | 54.06 | 54.64 | 54.64 | 55.70 | 55.70 |
| Electricity purchases | -1.12 | -0.46 | -0.46 | -0.75 | -0.75 | -0.59 | -0.59 | -0.62 | -0.62 |
| Operating costs (electrolyzer VOM, V2G throughput, biomass) | -0.00 | -0.00 | -0.00 | -0.00 | -0.00 | -0.00 | -0.00 | -0.31 | -0.31 |
| Electrolyzer start-up wear (solver term) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Wind: capital charged to 2050 | 0.00 | -21.41 | -21.41 | -22.00 | -22.00 | -22.03 | -22.03 | -22.29 | -22.29 |
| Wind: fixed O&M to 2050 | 0.00 | -1.49 | -1.49 | -1.53 | -1.53 | -1.53 | -1.53 | -1.55 | -1.55 |
| Hydrogen: capital charged to 2050 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| Hydrogen: fixed O&M to 2050 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| **NPV** | **17.15** | **32.04** | **32.04** | **29.78** | **29.78** | **30.48** | **30.48** | **30.92** | **30.92** |

### 2040-2050

| Item | S0 | S1 | S2 | A0 | AH | B0 | BH | C0 | CH |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Electricity export revenue | 4.16 | 23.86 | 27.90 | 22.72 | 26.49 | 23.21 | 26.87 | 24.97 | 28.08 |
| Electricity purchases | -1.10 | -0.35 | -0.18 | -0.81 | -0.37 | -0.56 | -0.28 | -0.71 | -0.54 |
| Operating costs (electrolyzer VOM, V2G throughput, biomass) | 0.00 | 0.00 | -0.08 | 0.00 | -0.08 | 0.00 | -0.07 | -0.50 | -0.55 |
| Electrolyzer start-up wear (solver term) | -0.00 | -0.00 | -0.10 | -0.00 | -0.09 | -0.00 | -0.09 | -0.00 | -0.08 |
| Wind: capital charged to 2050 | 0.00 | -15.60 | -15.44 | -16.45 | -16.31 | -16.24 | -16.12 | -16.54 | -16.32 |
| Wind: fixed O&M to 2050 | 0.00 | -1.27 | -1.25 | -1.35 | -1.33 | -1.33 | -1.31 | -1.35 | -1.32 |
| Hydrogen: capital charged to 2050 | 0.00 | 0.00 | -2.81 | 0.00 | -2.79 | 0.00 | -2.62 | 0.00 | -2.30 |
| Hydrogen: fixed O&M to 2050 | 0.00 | 0.00 | -0.87 | 0.00 | -0.86 | 0.00 | -0.81 | 0.00 | -0.70 |
| **NPV** | **3.06** | **6.64** | **7.18** | **4.11** | **4.65** | **5.07** | **5.57** | **5.87** | **6.27** |

### Hydrogen and V2G increments by period

**2025-2039**

| Item | S2-S1 | CH-C0 | AH-A0 | C0-A0 |
|---|---:|---:|---:|---:|
| Electricity export revenue | 0.00 | 0.00 | 0.00 | 1.64 |
| Electricity purchases | -0.00 | 0.00 | -0.00 | 0.13 |
| Operating costs (electrolyzer VOM, V2G throughput, biomass) | 0.00 | 0.00 | 0.00 | -0.31 |
| Electrolyzer start-up wear (solver term) | 0.00 | 0.00 | 0.00 | 0.00 |
| Wind: capital charged to 2050 | 0.00 | 0.00 | 0.00 | -0.29 |
| Wind: fixed O&M to 2050 | 0.00 | -0.00 | 0.00 | -0.02 |
| Hydrogen: capital charged to 2050 | 0.00 | 0.00 | 0.00 | 0.00 |
| Hydrogen: fixed O&M to 2050 | 0.00 | 0.00 | 0.00 | 0.00 |
| **NPV** | **0.00** | **0.00** | **0.00** | **1.14** |

**2040-2050**

| Item | S2-S1 | CH-C0 | AH-A0 | C0-A0 |
|---|---:|---:|---:|---:|
| Electricity export revenue | 4.04 | 3.11 | 3.76 | 2.25 |
| Electricity purchases | 0.18 | 0.17 | 0.44 | 0.09 |
| Operating costs (electrolyzer VOM, V2G throughput, biomass) | -0.08 | -0.04 | -0.08 | -0.50 |
| Electrolyzer start-up wear (solver term) | -0.10 | -0.08 | -0.09 | 0.00 |
| Wind: capital charged to 2050 | 0.16 | 0.22 | 0.14 | -0.08 |
| Wind: fixed O&M to 2050 | 0.03 | 0.03 | 0.02 | -0.00 |
| Hydrogen: capital charged to 2050 | -2.81 | -2.30 | -2.79 | 0.00 |
| Hydrogen: fixed O&M to 2050 | -0.87 | -0.70 | -0.86 | 0.00 |
| **NPV** | **0.54** | **0.40** | **0.54** | **1.76** |

## Table 4. Bidirectional-charger break-even

| Increment | PV (bn JPY) | Annuity 2025-2050 (M JPY/yr) | JPY per managed vehicle-yr (levelized) | JPY per vehicle-yr (2050 fleet) |
|---|---:|---:|---:|---:|
| C0-B0 | 1.23 | 68.7 | 21,986 | 10,384 |
| CH-BH | 1.13 | 63.4 | 20,298 | 9,587 |
| B0-A0 | 1.67 | 93.4 | 29,887 | 14,116 |
| BH-AH | 1.63 | 90.9 | 29,097 | 13,743 |

Managed vehicles = 0.5 x (commercial + residential fleet) per year, inputs/profiles.parquet (columns commercial_vehicles, residential_vehicles; model.py multiplies them by --ev-participation). Managed fleet 2025 183, 2050 6,615; discount-weighted mean 3,124. Levelized = PV / sum_t 1.03^-(t-2024) N_t (t = 2025-2050) = annuity over 2025-2050 (factor 17.877) / weighted mean fleet; same method as the F3 value (28,600 JPY with F3 perpetuity weights).
