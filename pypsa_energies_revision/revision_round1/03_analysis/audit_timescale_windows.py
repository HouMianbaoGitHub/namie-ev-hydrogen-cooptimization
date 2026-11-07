"""Independently recalculate 2050 SoC timescale metrics from hourly exports."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "4_基础场景的结果分析/3_Hourly_Results"
HERE = Path(__file__).resolve().parent
FLEET = {
    2049: {"EV JR Namie Commercial Area": 5759, "EV Residential Cars": 7269},
    2050: {"EV JR Namie Commercial Area": 5865, "EV Residential Cars": 7365},
}


def load_soc(scenario: str, kind: str, year: int) -> tuple[np.ndarray, str]:
    if kind == "H2":
        path = BASE / scenario / "Storage/Hourly" / f"Storage_Hourly_{scenario}.csv"
        df = pd.read_csv(path)
        df = df.loc[df.Object.eq("H2 Storage Tank")]
        df["time"] = pd.to_datetime(df.Timestamp, format="mixed")
        df = df.loc[df.time.dt.year.eq(year)].sort_values("time")
        capacity_kg = {"S2": 50000, "S4": 45000}[scenario]
        values = df.ClosingInventory.to_numpy(dtype=float) / capacity_kg * 100
        times = df.time
    else:
        path = BASE / scenario / "Vehicle/Hourly" / f"Vehicle_Hourly_{scenario}.csv"
        df = pd.read_csv(path)
        df["time"] = pd.to_datetime(df.Timestamp, format="mixed")
        df = df.loc[df.time.dt.year.eq(year)]
        df["weight"] = df.Object.map(FLEET[year])
        if df.weight.isna().any():
            raise ValueError(f"Unknown fleet object in {path}")
        df["weighted"] = df.SoC * df.weight
        grouped = df.groupby("time", sort=True).agg(weighted=("weighted", "sum"), weight=("weight", "sum"))
        values = (grouped.weighted / grouped.weight).to_numpy(dtype=float)
        times = pd.Series(grouped.index)
    expected = pd.date_range(f"{year}-01-01", f"{year}-12-31 23:00:00", freq="h")
    if len(values) != 8760 or not pd.DatetimeIndex(times).equals(expected):
        raise ValueError(f"{year} chronology mismatch: {scenario} {kind}")
    return values, str(path)


def decomposition(values: np.ndarray, days_per_week: int, weeks_per_block: int) -> dict:
    days_per_block = days_per_week * weeks_per_block
    complete_days = (len(values) // (24 * days_per_block)) * days_per_block
    x = values[: complete_days * 24].reshape(complete_days, 24)
    day_mean = x.mean(axis=1)
    week_mean = day_mean.reshape(-1, days_per_week).mean(axis=1)
    block_mean = week_mean.reshape(-1, weeks_per_block).mean(axis=1)
    mu = x.mean()
    intraday = x - day_mean[:, None]
    within_week = day_mean - np.repeat(week_mean, days_per_week)
    within_block = week_mean - np.repeat(block_mean, weeks_per_block)
    components = [
        np.mean(intraday**2),
        np.mean(within_week**2),
        np.mean(within_block**2),
        np.mean((block_mean - mu) ** 2),
    ]
    variance = float(np.var(x))
    if not np.isclose(sum(components), variance, rtol=1e-10, atol=1e-10):
        raise ValueError("Variance decomposition did not close")
    return {
        "days_included": int(complete_days),
        "days_per_week": days_per_week,
        "weeks_per_block": weeks_per_block,
        "block_days": days_per_block,
        "variance_pp_squared": variance,
        "shares": [float(c / variance) for c in components],
    }


def acf_pearson(x: np.ndarray, lag: int) -> float:
    return float(np.corrcoef(x[:-lag], x[lag:])[0, 1])


def acf_standard(x: np.ndarray, lag: int) -> float:
    centered = x - x.mean()
    return float(np.dot(centered[:-lag], centered[lag:]) / np.dot(centered, centered))


def main() -> None:
    out = {}
    old = pd.read_csv(ROOT / "26_Energies_submission/8_H2_role_analysis_20260916/soc_timescale_metrics.csv")
    for year in (2049, 2050):
      for scenario, kind in (("S2", "H2"), ("S4", "H2"), ("S3", "EV"), ("S4", "EV")):
        x, path = load_soc(scenario, kind, year)
        key = f"{scenario} {kind} {year}"
        base = decomposition(x, 7, 4)
        alternate = decomposition(x, 5, 4)
        earlier = old.loc[old.series.eq(f"{scenario} {kind}") & old.year.eq(year)]
        if len(earlier) != 1:
            raise ValueError(f"Missing original metric row: {key}")
        reported = earlier.iloc[0]
        original_shares = [float(reported[k]) for k in ("var_intraday", "var_1-7 d", "var_7-28 d", "var_>28 d")]
        out[key] = {
            "source": path,
            "hours": len(x),
            "soc_min_pct": float(np.min(x)),
            "soc_max_pct": float(np.max(x)),
            "acf_pearson_12h": acf_pearson(x, 12),
            "acf_pearson_24h": acf_pearson(x, 24),
            "acf_standard_12h": acf_standard(x, 12),
            "acf_standard_24h": acf_standard(x, 24),
            "reported_acf_12h": float(reported["acf_12h"]),
            "reported_acf_24h": float(reported["acf_24h"]),
            "standard_acf_max_reported_difference": max(abs(acf_standard(x, 12)-float(reported["acf_12h"])), abs(acf_standard(x, 24)-float(reported["acf_24h"]))),
            "base_7day_28day": base,
            "reported_base_shares": original_shares,
            "max_reported_share_difference": float(max(abs(a - b) for a, b in zip(base["shares"], original_shares))),
            "alternate_5day_20day": alternate,
        }
    output = HERE / "timescale_window_audit.json"
    output.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    for key, row in out.items():
        print(key, "base", [round(z, 3) for z in row["base_7day_28day"]["shares"]],
              "alternate", [round(z, 3) for z in row["alternate_5day_20day"]["shares"]],
              "max_original_difference", round(row["max_reported_share_difference"], 8))


if __name__ == "__main__":
    main()
