"""Storage timescale metrics: variance decomposition, autocorrelation, residence time, matching."""

from __future__ import annotations
import numpy as np
from collections import deque
import pandas as pd


def decomposition(values: np.ndarray, days_per_week: int, weeks_per_block: int) -> dict:
    days_per_block = days_per_week * weeks_per_block
    complete_days = len(values) // (24 * days_per_block) * days_per_block
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
        raise ValueError('Variance decomposition did not close')
    return {
        'days_included': int(complete_days),
        'days_per_week': days_per_week,
        'weeks_per_block': weeks_per_block,
        'block_days': days_per_block,
        'variance_pp_squared': variance,
        'shares': [float(c / variance) for c in components],
    }


def acf_standard(x: np.ndarray, lag: int) -> float:
    centered = x - x.mean()
    return float(np.dot(centered[:-lag], centered[lag:]) / np.dot(centered, centered))


def residence(frame: pd.DataFrame, mode: str) -> dict:
    q: deque = deque()
    first_open = (
        float(frame['opening'].iloc[0])
        if not np.isnan(frame['opening'].iloc[0])
        else float(frame['stock'].iloc[0])
    )
    q.append([None, first_open])
    ages, weights, untracked = ([], [], 0.0)
    prev = first_open
    for t, (inflow, outflow, stock) in enumerate(frame[['in', 'out', 'stock']].to_numpy()):
        if inflow > 0:
            q.append([t, float(inflow)])
        loss = max(prev + inflow - outflow - stock, 0.0)
        for amount, record in ((outflow, True), (loss, False)):
            need = float(amount)
            while need > 1e-09 and q:
                layer = q[0] if mode == 'FIFO' else q[-1]
                take = min(layer[1], need)
                if record:
                    if layer[0] is None:
                        untracked += take
                    else:
                        ages.append(t - layer[0])
                        weights.append(take)
                layer[1] -= take
                need -= take
                if layer[1] <= 1e-09:
                    q.popleft() if mode == 'FIFO' else q.pop()
        prev = stock
    a, w = (np.asarray(ages, float), np.asarray(weights, float))
    order = np.argsort(a)
    a, w = (a[order], w[order])
    cw = np.cumsum(w) / w.sum()
    total_out = float(frame['out'].sum())
    return {
        'median_h': float(a[np.searchsorted(cw, 0.5)]),
        'p90_h': float(a[np.searchsorted(cw, 0.9)]),
        'mean_h': float(np.average(a, weights=w)),
        'max_h': float(a.max()),
        'share_le_24h': float(w[a <= 24].sum() / total_out),
        'share_gt_168h': float(w[a > 168].sum() / total_out),
        'untracked_share': untracked / total_out,
    }


def matched_by(frame: pd.DataFrame, rule: str) -> float:
    g = frame[['in', 'out']].resample(rule).sum()
    return float(np.minimum(g['in'], g['out']).sum())
