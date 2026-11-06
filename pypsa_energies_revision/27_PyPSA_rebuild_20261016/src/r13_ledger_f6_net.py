"""R1.3 ledger of the F6 default with trade netted hour by hour (mock review N2-01, 2026-11-05).
In the base case purchases and sales carry the same price in every hour, so the LP can buy and sell in the same hour at
no cost and the gross import/export flows are not unique. This version books, in every hour, only the net position:
export revenue = max(export - import, 0) x export price, purchases = max(import - export, 0) x import price.
Everything else is r13_ledger_f6.py unchanged; NPV and the residual check are identical (netting changes nothing when
the two prices are equal, which is asserted). Output: results/r13_ledger_f6_net/ (r13_ledger_f6/ is left as it is).
Usage: python r13_ledger_f6_net.py"""
import numpy as np
import pandas as pd

import r13_ledger_f6 as L

L.OUT = L.ROOT / 'results' / 'r13_ledger_f6_net'
_gross = L.operation


def operation(d, args):
    annual = _gross(d, args)
    assert args.import_adder_jpy_per_kwh == 0 and args.export_deduction_jpy_per_kwh == 0, 'netting needs equal prices'
    gen = pd.read_parquet(d / 'generator_dispatch.parquet')
    snaps = gen.index
    p = L.prices(snaps, L.ROOT / 'inputs' / L.Path(args.price_series).name) * args.price_scale
    net = gen['export'] - gen['import']
    yr = pd.Series(snaps.year, index=snaps)
    annual['export_revenue'] = (np.maximum(net, 0) * p / 1e9).groupby(yr).sum().values
    annual['purchases'] = (-np.maximum(-net, 0) * p / 1e9).groupby(yr).sum().values
    return annual


L.operation = operation

if __name__ == '__main__':
    L.main()
