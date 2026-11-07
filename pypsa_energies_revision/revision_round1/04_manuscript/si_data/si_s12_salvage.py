"""SI S12: implied salvage value by technology and by vintage, truncation at 2050 (F6) and at 2060 (F6t2060).

Reads (read-only):
  27_PyPSA_rebuild_20261016/results/f6_20261030/r13_salvage_by_build.csv   (src/r13_salvage_f6.py)
  27_PyPSA_rebuild_20261016/results/f6_20261030/r13_salvage_by_tech.csv
Writes:
  si_data/si_s12_by_tech.csv     batch x case x technology (electrolyzer, fuel cell, tank, wind): full-life capital,
                                 capital charged, FO&M charged, salvage, salvage share, units
  si_data/si_s12_h2_vintage.csv  hydrogen (electrolyzer + fuel cell + tank) by build year, S2 and CH, both truncations
  si_data/si_s12_wind_vintage.csv wind by build period, S1, S2, C0, CH, both truncations
All money in billion JPY, PV 2024, 3%. Salvage = full-life capital - capital charged (PV of capital-recovery annuities
after the truncation year). Electrolyzer unit = 10 kg/h, fuel cell unit = 10 MW, tank unit = 1 t, wind unit = 40 MW.
Usage: python si_s12_salvage.py
"""
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RES = HERE.parents[2] / '27_PyPSA_rebuild_20261016' / 'results' / 'f6_20261030'
M = ['capital_full_life', 'capital_charged', 'fom_charged', 'salvage']
SIZE = {'electrolyzer': ('kg/h', 10.), 'fuelcell': ('MW', 10.), 'tank': ('t', 1.), 'wind': ('MW', 40.)}

b = pd.read_csv(RES / 'r13_salvage_by_build.csv')
b['size'] = b.units * b.tech.map(lambda k: SIZE[k][1])

t = b.groupby(['batch', 'case', 'tech'])[M + ['size']].sum().reset_index()
t['salvage_share'] = t.salvage / t.capital_full_life
t['charged_share'] = t.capital_charged / t.capital_full_life
t.to_csv(HERE / 'si_s12_by_tech.csv', index=False)

# consistency with r13_salvage_by_tech.csv (hydrogen = sum of the three hydrogen technologies)
ref = pd.read_csv(RES / 'r13_salvage_by_tech.csv')
g = t.assign(group=t.tech.where(t.tech == 'wind', 'hydrogen')).groupby(['batch', 'case', 'group'])[M].sum().reset_index()
chk = g.merge(ref, on=['batch', 'case', 'group'], suffixes=('', '_ref'))
assert len(chk) == len(ref)
for m in M:
    assert (chk[m] - chk[m + '_ref']).abs().max() < 1e-9, m

h = b[b.tech != 'wind'].copy()
hv = h.groupby(['batch', 'case', 'year'])[M].sum().reset_index()
el = h[h.tech == 'electrolyzer'].set_index(['batch', 'case', 'year'])['size'].rename('el_kgph_built')
hv = hv.join(el, on=['batch', 'case', 'year'])
hv['el_kgph_built'] = hv.el_kgph_built.fillna(0.)
hv['salvage_share'] = hv.salvage / hv.capital_full_life
hv[hv.case.isin(['S2', 'CH'])].to_csv(HERE / 'si_s12_h2_vintage.csv', index=False)

w = b[b.tech == 'wind'].copy()
w['period'] = pd.cut(w.year, [2024, 2025, 2030, 2040, 2050, 2060], labels=['2025', '2026-2030', '2031-2040', '2041-2050', '2051-2060'])
wv = w.groupby(['batch', 'case', 'period'], observed=True)[M + ['size']].sum().reset_index()
wv['salvage_share'] = wv.salvage / wv.capital_full_life
wv[wv.case.isin(['S1', 'S2', 'C0', 'CH'])].to_csv(HERE / 'si_s12_wind_vintage.csv', index=False)

pd.set_option('display.width', 250)
print(t.round(3).to_string())
print(hv[hv.case.isin(['S2', 'CH'])].round(3).to_string())
print(wv[wv.case.isin(['S1', 'S2', 'C0', 'CH'])].round(3).to_string())
