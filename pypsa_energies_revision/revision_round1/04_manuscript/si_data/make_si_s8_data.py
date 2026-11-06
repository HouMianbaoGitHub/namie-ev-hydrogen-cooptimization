"""Data for Supplementary Section S8 (hydrogen operating restrictions, R1.5c). Reads solved runs only; writes CSVs and the
markdown tables that are pasted between the TABLES markers of sections_F5/SI_S8_h2_operation.md (--write patches the file).

1. si_s8_el_uc.csv - electrolyzer commitment statistics in CH (and S2) for the F6 base, the F5 base (no start-up cost, no hot
   standby, 40-year stack) and the electrolyzer-operation sensitivity groups of sensF6. Method identical to
   27_PyPSA_rebuild_20261016/src/el_uc_stats_f6.py: started MW (link-input basis, summary.json h2_uc) divided by the 2050
   link capacity (kg/h x SEC_2050/1000/EL_FL_RATIO x availability) = equivalent full cold starts; per operating year divides by
   2050 - first electrolyzer build + 1; hot standby likewise as equivalent full-capacity hours. The 2050 capacity is the largest
   on the path, so per-MW cycling is a lower bound.
2. si_s8_fc_starts.csv - fuel-cell plant starts in 2050 for F6 S2, AH, BH, CH from the hourly fuel-cell hydrogen input
   (link_input.parquet column 'fuelcell'): 'on' = input above 1% of the 2050 maximum hour; starts = off->on transitions;
   ramp-up equivalent = sum of positive hourly changes / maximum (the start count a linear relaxation would see).
   Same definition as reports/燃料电池UC与换堆参数核实.md section 0.2 (which used F5).
Usage: python make_si_s8_data.py [--write]"""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RB = ROOT / '27_PyPSA_rebuild_20261016'
RES = RB / 'results'
sys.path.insert(0, str(RB / 'src'))
import model as M  # noqa: E402  (EL_FL_RATIO, _interp, parse_path)

SEC_FILE = HERE.parent / 'sections_F5' / 'SI_S8_h2_operation.md'
CASES = [('F6 base', 'f6_20261030/F6__{c}'), ('F5 base', 'f5_20261030/F5__{c}')] + [
    (g, f'sensF6_20261030/{g}__{{c}}') for g in ('minload030', 'startcost', 'startenergy', 'stack10', 'stack40', 'pem', 'avail090')]


def el_stats(d):
    s = json.loads((d / 'summary.json').read_text())
    cmd, uc = s['command'], s['h2_uc']
    u = pd.read_csv(d / 'installed_units.csv', index_col=0)
    ael = M._interp(M.parse_path(cmd['el_sec_path']), 2050) / 1000 / M.EL_FL_RATIO
    cap = u.at[2050, 'electrolyzer'] * 10 * ael * cmd['el_availability']
    first = int(u.index[u['electrolyzer'] > 1e-6][0])
    hours = len(pd.read_parquet(d / 'link_input.parquet', columns=['electrolyzer']))
    yrs = int(u.index.max()) - first + 1
    starts = uc['electrolyzer_started_MW_total'] / cap
    sb_h = uc.get('electrolyzer_mean_standby_MW', 0.) * hours / cap
    return {'el_kgph_2050': u.at[2050, 'electrolyzer'] * 10, 'el_MW_2050_at54': u.at[2050, 'electrolyzer'] * 10 * 0.054,
            'el_link_MW_2050': cap, 'first_build': first, 'operating_years': yrs,
            'started_MW_total': uc['electrolyzer_started_MW_total'], 'equiv_full_starts_per_yr': starts / yrs,
            'starts_per_15yr_stack': starts / yrs * 15, 'standby_equiv_full_h_per_yr': sb_h / yrs,
            'el_startup_cost_code': cmd['el_startup_cost'], 'el_standby_power_code': cmd['el_standby_power'],
            'startup_cost_bn_JPY': s['objective_ledger'].get('h2_startup_million_JPY', 0.) / 1e3}


rows = []
for lab, pat in CASES:
    for c in ('S2', 'CH'):
        d = RES / pat.format(c=c)
        rows.append({'case_set': lab, 'scenario': c, **el_stats(d)})
el = pd.DataFrame(rows)
el.to_csv(HERE / 'si_s8_el_uc.csv', index=False)

fr = []
for c in ('S2', 'AH', 'BH', 'CH'):
    p = pd.read_parquet(RES / 'f6_20261030' / f'F6__{c}' / 'link_input.parquet', columns=['fuelcell'])['fuelcell']
    p = p[p.index.year == 2050]
    mx = p.max()
    on = p > 0.01 * mx
    fr.append({'scenario': c, 'year': 2050, 'operating_hours': int(on.sum()), 'starts': int((on & ~on.shift(1, fill_value=False)).sum()),
               'ramp_up_equiv_starts': float(p.diff().clip(lower=0).sum() / mx), 'full_load_hours_rel_max': float(p.sum() / mx),
               'share_hours_below_20pct': float(((p > 0.01 * mx) & (p < 0.2 * mx)).sum() / on.sum())})
fc = pd.DataFrame(fr)
fc.to_csv(HERE / 'si_s8_fc_starts.csv', index=False)

# ---- markdown table S8.2 (electrolyzer-operation groups, CH) ----
sens = pd.read_csv(RES / 'sensF6_20261030' / 'sensF6_summary.csv', index_col='group')
f5 = pd.read_csv(RES / 'f5_20261030' / 'F5_summary.csv').query("batch == 'F5'").set_index('case')['npv']
NAME = {'F6 base': ('F6 base', 'F6基准'), 'F5 base': ('F5 (no wear cost, no standby, 40-yr stack)', 'F5（无磨损成本、无热备用、40年换堆）'),
        'minload030': ('minload030', 'minload030'), 'startcost': ('startcost', 'startcost'), 'startenergy': ('startenergy', 'startenergy'),
        'stack10': ('stack10', 'stack10'), 'stack40': ('stack40', 'stack40'), 'pem': ('pem', 'pem'), 'avail090': ('avail090', 'avail090')}
neg = lambda x: f'{x:.2f}'.replace('-', '−')


def vals(lab):
    if lab == 'F6 base':
        r = sens.loc['BASE']
        return r.dH_S, r.dH_C, r.I_S, r.ratio
    if lab == 'F5 base':
        dS, dC = f5['S2'] - f5['S1'], f5['CH'] - f5['C0']
        return dS, dC, dC - dS, dC / dS
    r = sens.loc[lab]
    return r.dH_S, r.dH_C, r.I_S, r.ratio


def table(lang):
    if lang == 'en':
        hd = ('| Case | ΔH(S) | ΔH(C) | I^S^~C~ | ΔH(C)/ΔH(S) | Electrolyzer CH 2050, kg/h (MW) | First build CH | Equivalent full cold starts per year, CH | Hot standby, full-capacity h per year, CH | Start-up cost, PV to 2050 (billion JPY), CH |')
    else:
        hd = ('| 算例 | ΔH(S) | ΔH(C) | I^S^~C~ | ΔH(C)/ΔH(S) | CH 2050年电解槽，kg/h（MW） | CH首建年 | CH每年等效满容量冷启动次数 | CH每年热备用满容量小时 | CH启动成本现值至2050年（十亿日元） |')
    out = [hd, '|:--|' + '--:|' * 9]
    for lab, _ in CASES:
        r = el[(el.case_set == lab) & (el.scenario == 'CH')].iloc[0]
        dS, dC, I, q = vals(lab)
        nm = NAME[lab][0 if lang == 'en' else 1]
        out.append(f'| {nm} | {neg(dS)} | {neg(dC)} | {neg(I)} | {q:.2f} | {r.el_kgph_2050:,.0f} ({r.el_MW_2050_at54:.0f}) | {r.first_build} | '
                   f'{r.equiv_full_starts_per_yr:.0f} | {r.standby_equiv_full_h_per_yr:.0f} | {r.startup_cost_bn_JPY:.3f} |')
    return '\n'.join(out)


def fc_table(lang):
    hd = ('| Scenario (2050) | Plant starts | Ramp-up equivalent starts | Operating hours | Full-load hours (relative to maximum hour) | Operating hours below 20% load (%) |'
          if lang == 'en' else '| 情景（2050年） | 全厂启动次数 | 爬升等效启动次数 | 运行小时 | 满负荷小时（相对最大小时） | 负荷低于20%的运行小时（%） |')
    out = [hd, '|:--|' + '--:|' * 5]
    for _, r in fc.iterrows():
        out.append(f'| {r.scenario} | {r.starts} | {r.ramp_up_equiv_starts:.0f} | {r.operating_hours:,} | {r.full_load_hours_rel_max:,.0f} | {100 * r.share_hours_below_20pct:.1f} |')
    return '\n'.join(out)


base_uc = pd.read_csv(RES / 'f6_20261030' / 'postprocess' / 'el_uc_stats.csv')   # written by src/el_uc_stats_f6.py


def base_table(lang):
    hd = ('| Horizon | Scenario | First build | Electrolyzer 2050 (MW, link input) | Equivalent full cold starts per year | Per 15-year stack | Hot standby, full-capacity h per year | Start-up cost, PV (billion JPY) |'
          if lang == 'en' else '| 规划期 | 情景 | 首建年 | 2050年电解槽（MW，链路输入） | 每年等效满容量冷启动次数 | 每个15年电堆 | 每年热备用满容量小时 | 启动成本现值（十亿日元） |')
    hz = {'F6': ('to 2050 (base)', '至2050年（基准）'), 'F6t2060': ('to 2060', '至2060年')}
    out = [hd, '|:--|:--|' + '--:|' * 6]
    for _, r in base_uc.iterrows():
        out.append(f'| {hz[r.batch][0 if lang == "en" else 1]} | {r.case} | {r.first_build} | {r.el_link_MW_2050:.0f} | {r.equiv_full_starts_per_yr:.0f} | '
                   f'{15 * r.equiv_full_starts_per_yr:,.0f} | {r.standby_equiv_full_h_per_yr:.0f} | {r.startup_cost_bn_JPY:.3f} |')
    return '\n'.join(out)


block = {'BASE_EN': base_table('en'), 'BASE_ZH': base_table('zh'), 'EL_EN': table('en'), 'EL_ZH': table('zh'),
         'FC_EN': fc_table('en'), 'FC_ZH': fc_table('zh')}
pd.set_option('display.width', 250)
print(el.round(3).to_string(index=False))
print(fc.round(3).to_string(index=False))
for k, v in block.items():
    print(f'\n[{k}]\n{v}')
if '--write' in sys.argv:
    t = SEC_FILE.read_text(encoding='utf-8')
    for k, v in block.items():
        a, b = f'<!-- BEGIN {k} -->', f'<!-- END {k} -->'
        i, j = t.index(a) + len(a), t.index(b)
        cap = [ln for ln in t[i:j].splitlines() if ln.startswith('Table:')]   # caption kept; it must sit directly above the table
        t = t[:i] + '\n\n' + ''.join(c + '\n\n' for c in cap) + v + '\n\n' + t[j:]
    SEC_FILE.write_text(t, encoding='utf-8')
    print('patched', SEC_FILE)
