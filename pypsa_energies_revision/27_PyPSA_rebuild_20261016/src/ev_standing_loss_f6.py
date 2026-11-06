"""Share of the smart-charging value (B0 - A0) that reflects avoided EV standing loss (F6 default; Discussion 4.2 TODO).
Standing loss = EV_LOSS (0.05 %/h) x stored energy of the whole fleet (managed store + uncontrolled share of the fixed
profile), as in model.py. Valued at the hourly electricity price and discounted at 3 % to 2024 (approximation: the lost
energy is replaced in the same hour). Usage: python ev_standing_loss_f6.py"""
import numpy as np
import pandas as pd

import f6_postprocess as fp


def loss(case):
    r = fp.load(case)
    idx = r['h'].index
    cmd = r['cmd']
    e = pd.Series(0., index=idx)
    if r['has_ev']:
        for k in fp.FLEETS:
            e = e + r['ev'][k]['e']
    share = 1.0 if cmd.get('ev_control') == 'fixed' else (1 - cmd['ev_participation'])
    for k in fp.FLEETS:
        e = e + fp.FIX[k + '_stored_MWh'].reindex(idx) * share
    mwh = fp.EV_LOSS * e
    w = 1.03 ** -(idx.year.to_numpy() - 2024)
    pv = float((mwh * r['h']['price'] * 1000 * w).sum()) / 1e9    # price JPY/kWh -> JPY/MWh; billion JPY
    return float(mwh.sum()) / 1000, float(mwh[idx.year == 2050].sum()) / 1000, pv


rows = {c: loss(c) for c in ('A0', 'B0', 'C0')}
df = pd.DataFrame(rows, index=['loss_GWh_2025_2050', 'loss_GWh_2050', 'loss_PV_bn_JPY']).T
npv = pd.read_csv(fp.RES / 'F6_summary.csv').query("batch == 'F6'").set_index('case').npv
df.loc['B0-A0 avoided', :] = df.loc['A0'] - df.loc['B0']
df.loc['C0-A0 avoided', :] = df.loc['A0'] - df.loc['C0']
print(df.round(3).to_string())
print('share of B0-A0 value:', round(df.at['B0-A0 avoided', 'loss_PV_bn_JPY'] / (npv.B0 - npv.A0), 3),
      ' of C0-A0:', round(df.at['C0-A0 avoided', 'loss_PV_bn_JPY'] / (npv.C0 - npv.A0), 3))
df.to_csv(fp.OUT / 'ev_standing_loss.csv')
