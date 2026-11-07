"""2050 hydrogen timescale metrics for PyPSA runs (R2.3 / R1.5 robustness cases).

Reuses the FIFO/LIFO residence and the variance decomposition of the manuscript
metrics (revision_round1/03_analysis/lp_main_results/lp_timescale_metrics.py), so the
numbers are comparable with Table 9. Hydrogen inflow is recovered from the store
balance, in_t = e_t - (1 - loss) e_{t-1} + out_t, which also covers time-varying
electrolysis efficiency; out_t is fuel-cell hydrogen use (kg/h).

Usage: python pypsa_timescale.py RUN_DIR [RUN_DIR ...]   (each with store_inventory.parquet,
link_input.parquet, annual_build.csv, build_stats.json)
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

METRICS = Path(__file__).resolve().parents[2] / 'revision_round1' / '03_analysis' / 'lp_main_results'
sys.path.insert(0, str(METRICS)); sys.path.insert(0, str(METRICS.parent))
from lp_timescale_metrics import residence, matched_by  # noqa: E402
from audit_timescale_windows import decomposition, acf_standard  # noqa: E402


def h2_frame(run: Path) -> tuple[pd.DataFrame, float]:
    e = pd.read_parquet(run / 'store_inventory.parquet')['hydrogen']
    out = pd.read_parquet(run / 'link_input.parquet')['fuelcell']
    cmd = json.loads((run / 'build_stats.json').read_text()).get('command', {})
    if cmd.get('unit_scaling'):  # hydrogen stored in tonnes and fuel-cell input in t/h
        e, out = e * 1000, out * 1000
    loss_day = float(cmd.get('h2_standing_loss_per_day', 0) or 0)
    lam = 1 - (1 - loss_day) ** (1 / 24)
    prev = e.shift(1).fillna(0.0)
    inflow = (e - (1 - lam) * prev + out).clip(lower=0)
    f = pd.DataFrame({'in': inflow, 'out': out, 'stock': e, 'opening': prev})
    f = f.loc[f.index.year == 2050]
    if (run / 'installed_units.csv').exists():  # vintage runs: capacity in service in 2050
        tank_kg = float(pd.read_csv(run / 'installed_units.csv', index_col=0).loc[2050, 'tank']) * 1000
    else:
        tank_kg = float(pd.read_csv(run / 'annual_build.csv')['tank'].sum()) * 1000
    f['soc'] = f['stock'] / tank_kg * 100
    return f, tank_kg


def metrics(run: Path) -> dict:
    f, tank_kg = h2_frame(run)
    total = float(f['out'].sum())
    soc = f['soc'].to_numpy(float)
    fifo, lifo = residence(f, 'FIFO'), residence(f, 'LIFO')
    shares = decomposition(soc, 7, 4)['shares']
    return {
        'tank_t': tank_kg / 1000,
        'throughput_over_capacity': total / tank_kg,
        'variance_shares_lt1d_1to7d_7to28d_gt28d': [round(100 * s, 1) for s in shares],
        'acf_24h': acf_standard(soc, 24),
        'little_mean_days': float(f['stock'].mean() * len(f) / total / 24),
        'fifo_mean_days': fifo['mean_h'] / 24, 'fifo_median_days': fifo['median_h'] / 24,
        'lifo_share_le_24h': lifo['share_le_24h'], 'fifo_share_gt_168h': fifo['share_gt_168h'],
        'across_quarter_net_share': (total - matched_by(f, 'QS')) / total,
    }


if __name__ == '__main__':
    result = {Path(r).name: metrics(Path(r)) for r in sys.argv[1:]}
    for k, v in result.items():
        print(k, {x: (round(y, 3) if isinstance(y, float) else y) for x, y in v.items()})
    out = Path(sys.argv[1]).parent / 'pypsa_timescale_metrics.json'
    old = json.loads(out.read_text()) if out.exists() else {}
    old.update(result); out.write_text(json.dumps(old, indent=2))
