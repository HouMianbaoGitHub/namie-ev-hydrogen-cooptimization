"""EV battery standing loss in the base cases."""

import numpy as np
import pandas as pd
import postprocess as fp


def loss(case):
    r = fp.load(case)
    idx = r['h'].index
    cmd = r['cmd']
    e = pd.Series(0.0, index=idx)
    if r['has_ev']:
        for k in fp.FLEETS:
            e = e + r['ev'][k]['e']
    share = 1.0 if cmd.get('ev_control') == 'fixed' else 1 - cmd['ev_participation']
    for k in fp.FLEETS:
        e = e + fp.FIX[k + '_stored_MWh'].reindex(idx) * share
    mwh = fp.EV_LOSS * e
    w = 1.03 ** (-(idx.year.to_numpy() - 2024))
    pv = float((mwh * r['h']['price'] * 1000 * w).sum()) / 1000000000.0
    return (float(mwh.sum()) / 1000, float(mwh[idx.year == 2050].sum()) / 1000, pv)


rows = {c: loss(c) for c in ('A0', 'B0', 'C0')}
df = pd.DataFrame(rows, index=['loss_GWh_2025_2050', 'loss_GWh_2050', 'loss_PV_bn_JPY']).T
npv = pd.read_csv(fp.RES / 'summary.csv').query("batch == 'base'").set_index('case').npv
df.loc['B0-A0 avoided', :] = df.loc['A0'] - df.loc['B0']
df.loc['C0-A0 avoided', :] = df.loc['A0'] - df.loc['C0']
print(df.round(3).to_string())
print(
    'share of B0-A0 value:',
    round(df.at['B0-A0 avoided', 'loss_PV_bn_JPY'] / (npv.B0 - npv.A0), 3),
    ' of C0-A0:',
    round(df.at['C0-A0 avoided', 'loss_PV_bn_JPY'] / (npv.C0 - npv.A0), 3),
)
df.to_csv(fp.OUT / 'ev_standing_loss.csv')
