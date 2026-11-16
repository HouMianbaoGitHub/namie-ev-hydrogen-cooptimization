"""Present-value ledger with net metering of trade (results/value_ledger)."""

import numpy as np
import pandas as pd
import value_ledger_gross as L

L.OUT = L.ROOT / 'results' / 'value_ledger'
_gross = L.operation


def operation(d, args):
    annual = _gross(d, args)
    assert args.import_adder_jpy_per_kwh == 0 and args.export_deduction_jpy_per_kwh == 0, (
        'netting needs equal prices'
    )
    gen = pd.read_parquet(d / 'generator_dispatch.parquet')
    snaps = gen.index
    p = L.prices(snaps, L.ROOT / 'inputs' / L.Path(args.price_series).name) * args.price_scale
    net = gen['export'] - gen['import']
    yr = pd.Series(snaps.year, index=snaps)
    annual['export_revenue'] = (np.maximum(net, 0) * p / 1000000000.0).groupby(yr).sum().values
    annual['purchases'] = (-np.maximum(-net, 0) * p / 1000000000.0).groupby(yr).sum().values
    return annual


L.operation = operation
if __name__ == '__main__':
    L.main()
