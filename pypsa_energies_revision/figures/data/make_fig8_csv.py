"""Figure 8 data from results/lhs."""

from pathlib import Path
import pandas as pd

HERE = Path(__file__).resolve().parent
D = HERE.parents[1] / 'results' / 'lhs'
r = pd.read_csv(D / 'lhs_results.csv', index_col=0)
out = (
    r[['dH_S', 'dH_A', 'dH_C', 'I_A', 'EV_CA', 'ratio_A', 'ev_participation', 'h2_capex_scale']]
    .rename(columns={'I_A': 'I_C', 'EV_CA': 'EV_flex_CA', 'ratio_A': 'ratio'})
    .rename_axis('sample')
    .reset_index()
)
out.to_csv(HERE / 'fig8_lhs_samples.csv', index=False)
LAB = {
    'price_scale': 'Price level',
    'wind_scale': 'Wind output',
    'market_limit_mw': 'Interface capacity',
    'load_scale': 'Non-EV demand',
    'h2_capex_scale': 'H$_2$ capital cost',
    'el_sec_scale': 'Electrolyzer consumption',
    'fc_kg_scale': 'Fuel-cell consumption',
    'ev_participation': 'EV participation',
    'v2g_cost': 'V2G wear cost',
}
P = pd.read_csv(D / 'lhs_prcc.csv', index_col=0)
rows = [
    dict(parameter=LAB[p], metric=m, prcc=P.at[p, c])
    for p in P.index
    for m, c in (('I_C', 'I_A'), ('ratio', 'ratio_A'), ('EV_flex_CA', 'EV_CA'))
]
pd.DataFrame(rows).to_csv(HERE / 'fig8_prcc.csv', index=False)
print(len(out), 'samples;', len(rows), 'prcc rows')
