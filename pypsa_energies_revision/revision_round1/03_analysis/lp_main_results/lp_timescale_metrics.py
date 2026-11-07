"""2050 timescale metrics for the LP main results (Table timescale_metrics).

Variance decomposition and autocorrelation reuse ../audit_timescale_windows.py;
net calendar matching and mean-stock residence follow ../audit_calendar_stock.py.
FIFO/LIFO residence is re-implemented here because the submission script was not
archived: inflows join a queue stamped with their hour, real outflows (H2
withdrawal; EV discharge + driving) leave from the oldest (FIFO) or newest (LIFO)
layer. The opening 2050 stock has unknown age and is reported as "untracked".
EV stock is usable energy above the 35% floor; the implied self-discharge loss
(inflow - outflow - stock change) leaves the queue in the same order but is not
counted as a residence observation.
"""
from __future__ import annotations

from collections import deque
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from audit_timescale_windows import acf_standard, decomposition  # noqa: E402

BASE = HERE / "3_Hourly_Results"
FLEET = {"EV JR Namie Commercial Area": 5865, "EV Residential Cars": 7365}
TANK_KG = {"S2": 47542.2, "S4": 50000.0}
FUEL_CELL_MW = {"S2": 14.604, "S4": 14.092}
KG_PER_MWH = 60.6
EV_CAP_KWH = sum(FLEET.values()) * 70


def load(scenario: str, kind: str) -> pd.DataFrame:
    if kind == "H2":
        f = pd.read_csv(BASE / scenario / "Storage/Hourly" / f"Storage_Hourly_{scenario}.csv")
        f = f.loc[f.Object.eq("H2 Storage Tank")].copy()
        f["time"] = pd.to_datetime(f.Timestamp, format="mixed")
        f = f.loc[f.time.dt.year.eq(2050)].sort_values("time").set_index("time")
        out = pd.DataFrame({"in": f.Injection, "out": f.Withdrawal, "stock": f.ClosingInventory,
                            "opening": f.OpeningInventory, "soc": f.ClosingInventory / TANK_KG[scenario] * 100})
    else:
        f = pd.read_csv(BASE / scenario / "Vehicle/Hourly" / f"Vehicle_Hourly_{scenario}.csv")
        f["time"] = pd.to_datetime(f.Timestamp, format="mixed")
        f = f.loc[f.time.dt.year.eq(2050)].copy()
        f["w"] = f.Object.map(FLEET)
        f["in"] = f.Charging * 0.95
        f["out"] = f.Discharging / 0.90 + f.EnergyConsumption
        f["stock"] = (f.SoC / 100 - 0.35) * f.w * 70
        f["wsoc"] = f.SoC * f.w
        g = f.groupby("time", sort=True).agg(**{"in": ("in", "sum"), "out": ("out", "sum"), "stock": ("stock", "sum"),
                                               "wsoc": ("wsoc", "sum"), "w": ("w", "sum")})
        out = pd.DataFrame({"in": g["in"], "out": g["out"], "stock": g["stock"], "soc": g.wsoc / g.w})
        out["opening"] = out.stock.shift(1)
    expected = pd.date_range("2050-01-01", "2050-12-31 23:00", freq="h")
    if not out.index.equals(expected):
        raise ValueError(f"Chronology mismatch: {scenario} {kind}")
    return out


def residence(frame: pd.DataFrame, mode: str) -> dict:
    q: deque = deque()
    first_open = float(frame["opening"].iloc[0]) if not np.isnan(frame["opening"].iloc[0]) else float(frame["stock"].iloc[0])
    q.append([None, first_open])
    ages, weights, untracked = [], [], 0.0
    prev = first_open
    for t, (inflow, outflow, stock) in enumerate(frame[["in", "out", "stock"]].to_numpy()):
        if inflow > 0:
            q.append([t, float(inflow)])
        loss = max(prev + inflow - outflow - stock, 0.0)
        for amount, record in ((outflow, True), (loss, False)):
            need = float(amount)
            while need > 1e-9 and q:
                layer = q[0] if mode == "FIFO" else q[-1]
                take = min(layer[1], need)
                if record:
                    if layer[0] is None:
                        untracked += take
                    else:
                        ages.append(t - layer[0]); weights.append(take)
                layer[1] -= take; need -= take
                if layer[1] <= 1e-9:
                    (q.popleft() if mode == "FIFO" else q.pop())
        prev = stock
    a, w = np.asarray(ages, float), np.asarray(weights, float)
    order = np.argsort(a); a, w = a[order], w[order]
    cw = np.cumsum(w) / w.sum()
    total_out = float(frame["out"].sum())
    return {"median_h": float(a[np.searchsorted(cw, 0.5)]), "p90_h": float(a[np.searchsorted(cw, 0.9)]),
            "mean_h": float(np.average(a, weights=w)), "max_h": float(a.max()),
            "share_le_24h": float(w[a <= 24].sum() / total_out), "share_gt_168h": float(w[a > 168].sum() / total_out),
            "untracked_share": untracked / total_out}


def matched_by(frame: pd.DataFrame, rule: str) -> float:
    g = frame[["in", "out"]].resample(rule).sum()
    return float(np.minimum(g["in"], g["out"]).sum())


def main() -> None:
    result = {}
    for scenario, kind in (("S2", "H2"), ("S4", "H2"), ("S3", "EV"), ("S4", "EV")):
        f = load(scenario, kind)
        soc = f["soc"].to_numpy(float)
        total = float(f["out"].sum())
        cap = TANK_KG[scenario] if kind == "H2" else EV_CAP_KWH * 0.61  # usable window 35-96%
        daily = f["soc"].resample("D").agg(["min", "max"])
        monthly = f["soc"].resample("MS").mean()
        row = {
            "installed_capacity_MWh_e": TANK_KG[scenario] / KG_PER_MWH if kind == "H2" else EV_CAP_KWH / 1000,
            "throughput_over_capacity": total / (TANK_KG[scenario] if kind == "H2" else EV_CAP_KWH),
            "variance_shares_7_28": decomposition(soc, 7, 4)["shares"],
            "variance_shares_5_20": decomposition(soc, 5, 4)["shares"],
            "acf_12h": acf_standard(soc, 12), "acf_24h": acf_standard(soc, 24),
            "mean_daily_soc_range_pp": float((daily["max"] - daily["min"]).mean()),
            "annual_range_monthly_mean_pp": float(monthly.max() - monthly.min()),
            "little_mean_h": float(f["stock"].mean() * len(f) / total),
            "fifo": residence(f, "FIFO"), "lifo": residence(f, "LIFO"),
            "same_month_net_share": matched_by(f, "MS") / total,
            "across_quarter_net_share": (total - matched_by(f, "QS")) / total,
        }
        if kind == "H2":
            b = f.loc[(f.index.month.isin([1, 4, 7, 10])) & (f.index.day == 1) & (f.index.hour == 0), "opening"]
            row["quarter_boundary_stock_share"] = float(b.sum() / total)
            row["quarter_boundary_stock_t"] = float(b.sum() / 1000)
            row["full_tank_duration_h"] = TANK_KG[scenario] / KG_PER_MWH / FUEL_CELL_MW[scenario]
        result[f"{scenario} {kind}"] = row
    (HERE / "lp_timescale_metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    keys = ["throughput_over_capacity", "acf_12h", "acf_24h", "mean_daily_soc_range_pp", "annual_range_monthly_mean_pp",
            "little_mean_h", "same_month_net_share", "across_quarter_net_share"]
    for k, r in result.items():
        print(k, {x: round(r[x], 3) for x in keys}, "var7/28", [round(v * 100, 1) for v in r["variance_shares_7_28"]],
              "FIFO med/mean", round(r["fifo"]["median_h"]), round(r["fifo"]["mean_h"]), "LIFO med", round(r["lifo"]["median_h"]),
              "LIFO<=24h", round(r["lifo"]["share_le_24h"] * 100, 1), "untracked", round(r["fifo"]["untracked_share"] * 100, 2),
              "qstock", round(r.get("quarter_boundary_stock_share", 0) * 100, 2))


if __name__ == "__main__":
    main()
