"""Construct a transparent aggregate, non-coordinated EV charging proxy.

The output is a fleet-level policy counterfactual. It does not reconstruct
observed per-vehicle arrivals, departures, or charging sessions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


BATTERY_MWH_PER_EV = 0.07
CHARGER_MW_PER_EV = 0.01
INITIAL_AND_MAX_SOC = 0.96
MIN_SOC = 0.35
HOURLY_STANDING_LOSS = 0.0005
STATION_CHARGE_EFFICIENCY = 0.90
BATTERY_CHARGE_EFFICIENCY = 0.95
GRID_TO_BATTERY_EFFICIENCY = (
    STATION_CHARGE_EFFICIENCY * BATTERY_CHARGE_EFFICIENCY
)

# newbase mirrors PRESET_NEWBASE in 27_PyPSA_rebuild_20261016/src/model.py
PRESETS = {
    "plexos": dict(battery_mwh=0.07, soh=1.0, station_eff=0.90, battery_charge_eff=0.95, absolute_floor=False, departure_soc=None, departure_hour=7),
    "newbase": dict(battery_mwh=0.07, soh=0.9, station_eff=0.93, battery_charge_eff=0.98, absolute_floor=True, departure_soc=0.6, departure_hour=7),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_group(df: pd.DataFrame, group: str, P: dict) -> tuple[pd.DataFrame, dict]:
    count = df[f"{group}_vehicles"].to_numpy(dtype=float)
    drive = df[f"{group}_drive_MWh"].to_numpy(dtype=float)
    availability = df[f"{group}_availability"].to_numpy(dtype=float)
    if not (np.isfinite(count).all() and np.isfinite(drive).all() and np.isfinite(availability).all()):
        raise ValueError(f"{group}: non-finite input")
    if (count < 0).any() or (drive < 0).any() or (availability < 0).any() or (availability > 1).any():
        raise ValueError(f"{group}: input outside physical bounds")

    # Match the PyPSA reconstruction: AC charging is limited by the number
    # estimated available, and new EVs arrive at their configured initial SoC.
    eff = P["station_eff"] * P["battery_charge_eff"]
    usable = P["battery_mwh"] * P["soh"]
    max_grid_mw = count * P.get("charger_mw", CHARGER_MW_PER_EV) / P["station_eff"] * availability
    capacity_mwh = count * usable
    fleet_entry_mwh = np.diff(count, prepend=count[0]) * usable * INITIAL_AND_MAX_SOC
    grid_charge_mw = np.empty(len(df), dtype=float)
    stored_mwh = np.empty(len(df), dtype=float)
    uncapped_request_mw = np.empty(len(df), dtype=float)
    state = capacity_mwh[0] * INITIAL_AND_MAX_SOC
    tolerance = 1e-7

    for t in range(len(df)):
        # PyPSA's Store starts from e_initial at the first snapshot; standing
        # loss is applied only when carrying a solved state into the next hour.
        retention = 1.0 if t == 0 else 1 - HOURLY_STANDING_LOSS
        before_charge = retention * state - drive[t] + fleet_entry_mwh[t]
        target = capacity_mwh[t] * INITIAL_AND_MAX_SOC
        request = max(0.0, (target - before_charge) / eff)
        charge = min(request, max_grid_mw[t])
        state = before_charge + eff * charge
        if state > target + tolerance:
            raise AssertionError(f"{group}: exceeds maximum SoC at hour {t}")
        grid_charge_mw[t] = charge
        stored_mwh[t] = state
        uncapped_request_mw[t] = request

    floor = count * P["battery_mwh"] * MIN_SOC if P["absolute_floor"] else capacity_mwh * MIN_SOC
    hour = df.index.hour.to_numpy()
    dep = np.where(hour == (P["departure_hour"] - 1) % 24, capacity_mwh * P["departure_soc"], 0.0) if P["departure_soc"] else np.zeros(len(df))
    unmet_dep = np.maximum(0, dep - stored_mwh)
    unmet_floor = np.maximum(0, floor - stored_mwh)
    result = pd.DataFrame(
        {
            f"{group}_grid_charge_MW": grid_charge_mw,
            f"{group}_stored_MWh": stored_mwh,
            f"{group}_max_grid_charge_MW": max_grid_mw,
            f"{group}_uncapped_request_MW": uncapped_request_mw,
            f"{group}_floor_shortfall_MWh": unmet_floor,
        },
        index=df.index,
    )
    metrics = {
        "hours": len(df),
        "traction_MWh": float(drive.sum()),
        "grid_charge_MWh": float(grid_charge_mw.sum()),
        "max_floor_shortfall_MWh": float(unmet_floor.max()),
        "floor_violation_hours": int((unmet_floor > tolerance).sum()),
        "departure_violation_hours": int((unmet_dep > tolerance).sum()),
        "max_departure_shortfall_MWh": float(unmet_dep.max()),
        "hours_capped_below_target": int((uncapped_request_mw > max_grid_mw + tolerance).sum()),
        "final_stored_MWh": float(stored_mwh[-1]),
        "final_target_MWh": float(capacity_mwh[-1] * INITIAL_AND_MAX_SOC),
        "minimum_soc_fraction": float(np.min(stored_mwh / np.maximum(capacity_mwh, tolerance))),
    }
    return result, metrics


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--year", type=int, help="Diagnostic slice; full horizon by default")
    parser.add_argument("--preset", choices=["plexos", "newbase"], default="newbase")
    parser.add_argument("--availability-scale", type=float, default=1.0, help="Scale connection availability (same as model --ev-availability-scale)")
    parser.add_argument("--soh", type=float, help="Override usable share of nominal capacity (same as model --ev-capacity-scale)")
    parser.add_argument("--station-eff", type=float, help="Override charger efficiency (same as model --ev-station-eff)")
    parser.add_argument("--battery-charge-eff", type=float, help="Override battery charge efficiency (same as model --ev-batt-charge-eff)")
    parser.add_argument("--charger-kw", type=float, help="Override charger power per vehicle, kW (same as model --ev-charger-kw)")
    args = parser.parse_args()
    df = pd.read_parquet(args.input)
    for g in ("commercial", "residential"):
        df[f"{g}_availability"] = (df[f"{g}_availability"] * args.availability_scale).clip(upper=1)
    if args.year is not None:
        df = df.loc[str(args.year)]
    if not df.index.is_monotonic_increasing or df.index.has_duplicates:
        raise ValueError("Hourly profile index is not unique and increasing")
    if not (df.index.to_series().diff().dropna() == pd.Timedelta(hours=1)).all():
        raise ValueError("The input contains missing or non-hourly steps")
    P = dict(PRESETS[args.preset])
    if args.charger_kw is not None:
        P["charger_mw"] = args.charger_kw / 1000
    for k, v in (("soh", args.soh), ("station_eff", args.station_eff), ("battery_charge_eff", args.battery_charge_eff)):
        if v is not None:
            P[k] = v  # sensitivity runs must use a fixed profile built with the same EV parameters as the model run
    parts, groups = [], {}
    for group in ("commercial", "residential"):
        part, metrics = build_group(df, group, P)
        parts.append(part)
        groups[group] = metrics
    out = pd.concat(parts, axis=1)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    out.to_parquet(args.output_dir / "fixed_fleet_charging.parquet")
    out.to_csv(args.output_dir / "fixed_fleet_charging.csv", float_format="%.9f")
    report = {
        "status": "aggregate_internal_check_only",
        "policy": "At each hour, charge as early as aggregate availability allows to restore fleet SoC to 96%; no V2G or response to system conditions.",
        "scope": "Not observed per-vehicle arrival charging or proof of departure feasibility.",
        "input": str(args.input.resolve()),
        "input_sha256": sha256(args.input),
        "year_slice": args.year,
        "start": str(df.index[0]),
        "end": str(df.index[-1]),
        "preset": args.preset, "preset_parameters": P, "availability_scale": args.availability_scale,
        "parameters": {
            "battery_MWh_per_EV": BATTERY_MWH_PER_EV,
            "charger_MW_per_EV": CHARGER_MW_PER_EV,
            "max_soc": INITIAL_AND_MAX_SOC,
            "min_soc": MIN_SOC,
            "hourly_standing_loss": HOURLY_STANDING_LOSS,
            "grid_to_battery_efficiency": P["station_eff"] * P["battery_charge_eff"],
        },
        "groups": groups,
        "feasible_under_aggregate_floor": all(m["floor_violation_hours"] == 0 for m in groups.values()),
        "feasible_departure_soc": all(m["departure_violation_hours"] == 0 for m in groups.values()),
    }
    (args.output_dir / "check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
