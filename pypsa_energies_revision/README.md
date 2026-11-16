# Namie Town EV–hydrogen model

Code, inputs and results for *Electric-Vehicle Flexibility and Hydrogen Storage in Renewable Capacity Planning for an
Export-Oriented Municipality* (Tuo Zhang and Takuro Kobashi, Tohoku University). The model is a PyPSA/linopy linear
capacity-expansion and hourly-dispatch model of Namie Town, Fukushima, for 2025–2050.

## Contents

| Path | Content |
|---|---|
| `src/model.py` | The model |
| `src/base_args.txt`, `src/cases.csv` | Arguments of the base case and of every case in the paper (369 cases) |
| `src/run_case.py` | Runs one case of `cases.csv` |
| `src/build_uncontrolled_charging.py`, `src/make_price_variant.py` | Build the uncontrolled-charging profiles and the price variant in `inputs.zip` |
| other `src/*.py` | Post-processing that produced `results/` from the full model outputs |
| `inputs.zip` | Model inputs prepared by the authors |
| `results/` | Summary results: `base/` (nine base cases, hourly results of case CH), `sensitivity/`, `review_cases/`, `lhs/`, `value_ledger/` |
| `figures/` | Figures 1–8 as in the paper, and the script and data for Figures 2–8 |
| `supplementary_tables/` | Data of the tables in the Supplementary Materials |
| `price_model/` | Construction and back-test of the hourly price series (method only; the raw market data are not included) |
| `renewables_ninja/` | Download of the wind and solar capacity factors |

## Setup

```bash
cd pypsa_energies_revision
pip install -r requirements.txt
unzip inputs.zip                      # creates inputs/
```

Wind and solar capacity factors come from Renewables.ninja and are not redistributed. With your own API token in
`~/.renewables_ninja_token`:

```bash
cd renewables_ninja
python fetch_ninja.py pv namie 37.494 140.993 2024
python fetch_ninja.py wind namie_h80 37.494 140.993 2024 height=80
python make_ninja_profile.py          # writes inputs/namie_renewables_ninja_2024.parquet
```

## Running the model

```bash
# quick test: one representative day per year, open-source solver
python src/run_case.py base__CH --output results/test_CH --days-per-year 1 --solver highs

# full case with the solver settings of the paper (Gurobi licence required)
python src/run_case.py base__CH --output results/my_CH
```

Each case is the base arguments plus the changes in `cases.csv` (`--key value` sets an option, `!--key` removes it).
Sets: `base` (cases S0–CH), `base_to_2060` (horizon extended to 2060), `sensitivity` (one-at-a-time groups),
`review` (cost and price-shape cases), `lhs` (40 Latin-hypercube samples × 6 cases). The cases without hydrogen of the
sensitivity groups were solved in a separate batch whose arguments differed only in hydrogen options, which do not
enter those cases. A full case with hydrogen needs tens of GB of memory and up to a few hours.

## Figures

```bash
cd figures
python make_figures.py 2 3 4 5 6 7 8
```

`figures/Fig1`–`Fig8` are the images in the paper. Figure 1 is a drawing. When regenerated, Figure 2 has no map panel,
because the map is not included.

## Full outputs

The scripts in `src/` other than the model read the full hourly outputs (about 8 GB), which are available from the
corresponding author (zhang.tuo.b7@tohoku.ac.jp) on request.

## Licence

Code: MIT ([`LICENSE`](../LICENSE)). Inputs, results and figure and table data: CC BY 4.0 ([`LICENSE-DATA`](../LICENSE-DATA)).
