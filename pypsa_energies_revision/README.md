# Namie Town EV–hydrogen study: PyPSA model, inputs and figure data

Code, inputs and summary results for the revised manuscript energies-4608521 (*Energies*, MDPI).
All results in the manuscript come from a PyPSA/linopy linear capacity-expansion and hourly-dispatch model for
2025–2050. The PLEXOS files in the root of this repository belong to the earlier submitted version; they are kept for
reference and are not used here.

Full solver outputs (about 8 GB) are not included. They are available from the corresponding author on request.

## Contents

The folder keeps the project layout so that relative paths in the scripts work without changes.

| Path | Content |
|---|---|
| `27_PyPSA_rebuild_20261016/src/` | Model (`model.py`), base arguments (`default_D2_args.txt`), case definitions and post-processing |
| `27_PyPSA_rebuild_20261016/inputs.zip` | Model inputs except third-party data. Unzip in place to create `inputs/` |
| `27_PyPSA_rebuild_20261016/params/` | Parameter registry and mapping checks. Notes are mainly in Chinese |
| `27_PyPSA_rebuild_20261016/results/` | Summary tables, plus the four hourly files of case CH that Figure 6 needs |
| `revision_round1/04_manuscript/figures_F6/` | Figure scripts and data for Figures 7 and 8 |
| `revision_round1/04_manuscript/si_data/` | Scripts and tables for the Supplementary Materials |
| `revision_round1/02_plan/` | Numbers used in the text (`F6_facts.md`, `sens_values_F6.json`, `lhs_values_F6.json`) |
| `revision_round1/03_analysis/` | Price model, fixed-charging profile and helper modules |

## Scenarios

| Case | `--scenario` | `--ev-control` | Meaning |
|---|---|---|---|
| S0, S1, S2 | S0, S1, S2 | none | No expansion; renewables; renewables + hydrogen, no EV fleet |
| A0, AH | S3, S4 | `fixed` | Uncontrolled charging, without / with hydrogen |
| B0, BH | S3, S4 | `charge_only` | Smart charging, without / with hydrogen |
| C0, CH | S3, S4 | `bidirectional` | Smart charging + V2G, without / with hydrogen |

## Running

The runs used Python 3.14.3, PyPSA 1.2.4, linopy 0.8.0 and Gurobi 13.0.2 (`requirements.txt`). A Gurobi licence is
required for the settings below. `tsam` is imported by `model.py`; the figure and table scripts also use `matplotlib`,
`scipy` and `pyyaml`.

```bash
cd 27_PyPSA_rebuild_20261016
unzip inputs.zip
# then add inputs/namie_renewables_ninja_2024.parquet, see "Wind and solar" below

# one full case, here CH, with the settings of the base runs
python src/model.py --scenario S4 --ev-control bidirectional \
    --solver gurobi --threads 5 --time-limit 36000 \
    --gurobi-numeric-focus 1 --gurobi-bar-homogeneous 1 \
    --output results/my_CH $(sed 's#{INP}#inputs/#g' src/default_D2_args.txt)

# quick test: one representative day per year
python src/model.py --scenario S4 --ev-control bidirectional --days-per-year 1 \
    --solver gurobi --threads 4 --output results/smoke_CH \
    $(sed 's#{INP}#inputs/#g' src/default_D2_args.txt)
```

A full case with hydrogen needs tens of GB of memory and can take up to a few hours.
`summary.json` of each run holds a field `validation_status: reconstruction prototype`. It is a leftover label from the
early rebuild stage and carries no information about these results.

## Sensitivity runs

`src/make_timing_batch.py` holds the argument sets of the base and sensitivity cases, and `src/make_lhs_f6.py` holds the
Latin hypercube sample. Their sets used here are `f6`, `sensf6` and `revf6`. Both write PowerShell scripts for the authors'
workstations, so adapt the run directories before use. The generated scripts are not included.

## Reproducing the figures

After unzipping `inputs.zip` and adding the Renewables.ninja file:

```bash
cd revision_round1/04_manuscript/figures_F6
python make_figures_f6.py 2 3 4 5 6 7 8
```

Figures 2–8 regenerate from this folder. Figure 1 is a drawing, and its inset script needs a KML file that is not
included. The map panel of Figure 2 is not included and the panel is left out when the image is missing.

## What needs the full outputs

These scripts read hourly outputs of all cases, or archived tables of earlier model versions, and do not run from this
folder alone: `summarize_f6.py`, `make_sens_values_f6.py`, `make_f6_facts.py`, the `r13_*` ledgers, and the timescale
scripts for the sensitivity and sample runs. Their results are included as tables. `make_lhs_values_f6.py` runs as is.

## Input data notes

- **Hourly EV driving and charger connection:** `historical_s4/DataFiles/ev_data/ev_data_2018_2050.csv` and
  `ev_charging_share_2018_2050.csv` are synthetic series generated with a seeded random script. They were not derived
  from the origin–destination survey.
- **Wind and solar:** Renewables.ninja capacity factors for 2024 are not redistributed. Download them with your own
  token and build `inputs/namie_renewables_ninja_2024.parquet` with `make_ninja_profile.py`, in
  `revision_round1/03_analysis/price_model/`. The commands are at the top of that script. For the same reason
  `inputs/profiles.parquet` has no `solar_pu` and `wind_pu` columns and the `RF_*` folders are left out, so
  `prepare_inputs.py` does not run from this folder.
- **Generator scripts for the EV series** are not included.
- **Electricity prices:** hourly series from the model in `revision_round1/03_analysis/price_model/`. Raw market data are
  not redistributed; `data/README.md` lists the sources. 
- **Load-model training data** used by `si_s4_load_accuracy.py` are not included.

## Licence

Code: MIT (`LICENSE_CODE.txt`). Input data and tables prepared by the authors: CC BY 4.0, as in the repository `LICENSE`.
Third-party data remain under their providers' terms and are not included here.

## Citation

Please cite the *Energies* article once it is published.
