"""Tables for Supplementary Section S9 (all one-at-a-time and combined sensitivity groups of the F6 base).
Reads only 27_PyPSA_rebuild_20261016/results/sensF6_20261030/sensF6_summary.csv (written by src/summarize_sensf6.py; rules in
its header: F6 changes hydrogen parameters only, so S1/A0/C0 come from the same group of sensF5 when solved there, otherwise
from the F6 base; S2/CH from sensF6 or, when not re-solved (EV groups re-solve CH only), from the F6 base) and the termination
status of the sensF5 group coh4_t10 (not re-run in F6). Group settings are those of src/make_timing_batch.py SENSF5/SENSF6
(revision_round1/02_plan/F5_敏感性清单.md); reviewer comments as cited in 05_response/response_F6_bilingual.md.
Writes si_data/si_s9_stats.json and patches the tables between the BEGIN/END markers of sections_F5/SI_S9_sensitivity.md
(--write). Usage: python make_si_s9_table.py [--write]"""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RES = HERE.parents[2] / '27_PyPSA_rebuild_20261016' / 'results'
SEC_FILE = HERE.parent / 'sections_F5' / 'SI_S9_sensitivity.md'
df = pd.read_csv(RES / 'sensF6_20261030' / 'sensF6_summary.csv', index_col='group')
f5c = {c: json.loads((RES / 'sensF5_20261030' / f'coh4_t10__{c}' / 'summary.json').read_text())['termination_condition'] for c in ('C0', 'CH')}

# group -> (category, reviewer comments, setting EN, setting ZH); base values in parentheses
G = {
    'minload030': ('H2', 'R1.5c', 'Electrolyzer minimum load 0.30 (0.20)', '电解槽最低负荷0.30（0.20）'),
    'startcost': ('H2', 'R1.5c', 'Electrolyzer start-up cost 8,000 JPY/MW rated, code 8,944 (1,000; 1,118)', '电解槽启动成本每MW额定8,000日元，代码8,944（1,000；1,118）'),
    'startenergy': ('H2', 'R1.5c', 'Electrolyzer cold-start energy 0.15 MWh/MW rated, code 0.168 (0)', '电解槽冷启动耗电每MW额定0.15 MWh，代码0.168（0）'),
    'stack10': ('H2', 'R1.5c, R2.3b', 'Electrolyzer stack replaced every 10 years; average stack age 4.5 years (15; 7)', '电解槽每10年换堆；平均电堆年龄4.5年（15；7）'),
    'stack40': ('H2', 'R1.5c, R2.3b', 'Electrolyzer stack replaced every 40 years (F5 value); average stack age 19.5 years (15; 7)', '电解槽每40年换堆（F5取值）；平均电堆年龄19.5年（15；7）'),
    'pem': ('H2', 'R1.5c', 'PEM electrolyzer: capital cost 250/65/50/37.5 kJPY/kW (2025/2030/2040/2050), system consumption 57.4/53.6/50.6/47.5 kWh/kg, minimum load 0.10, no cold-start delay, no start-up cost, stack 15% every 15 years, ageing 0.3%/yr',
            'PEM电解槽：造价250/65/50/37.5千日元/kW（2025/2030/2040/2050），系统耗电57.4/53.6/50.6/47.5 kWh/kg，最低负荷0.10，无冷启动延迟，无启动成本，每15年换堆、费用15%，老化0.3%/年'),
    'avail090': ('H2', 'R1.5c, R2.3c', 'Availability 0.90 for electrolyzer and fuel cell (0.97; 0.95)', '电解槽和燃料电池可用率0.90（0.97；0.95）'),
    'eff_hi': ('H2', 'R1.5b, R2.3b, R2.6a', 'Electrolyzer system consumption 54.92/52.6/50.6/48.0 kWh/kg (59/57/56/54)', '电解槽系统耗电54.92/52.6/50.6/48.0 kWh/kg（59/57/56/54）'),
    'eff_lo': ('H2', 'R1.5b, R2.3b, R2.6a', 'No efficiency improvement: electrolyzer 59 kWh/kg, fuel cell 60.6 kg/MWh in all years', '效率不改善：电解槽各年59 kWh/kg，燃料电池各年60.6 kg/MWh'),
    'leak01': ('H2', 'R2.3a', 'Tank standing loss 0.1% per day (0)', '储罐损失每天0.1%（0）'),
    'leak10': ('H2', 'R2.3a', 'Tank standing loss 1% per day (0)', '储罐损失每天1%（0）'),
    'capex070': ('H2', 'R2.6a', 'Capital cost of electrolyzer, fuel cell and tank ×0.7', '电解槽、燃料电池和储罐造价×0.7'),
    'capex130': ('H2', 'R2.6a, R2.6b', 'Capital cost of electrolyzer, fuel cell and tank ×1.3', '电解槽、燃料电池和储罐造价×1.3'),
    'tank043': ('H2', 'R2.6a', 'Tank capacity in service at most 43 t (none)', '在役储罐容量上限43 t（无）'),
    'coh3_t05': ('EV', 'R1.4a', 'Managed fleet split into 3 cohorts, θ = 0.5 (1 cohort)', '受控车队分为3组，θ = 0.5（1组）'),
    'coh3_t075': ('EV', 'R1.4a', '3 cohorts, θ = 0.75', '3组，θ = 0.75'),
    'coh4_t05': ('EV', 'R1.4a', '4 cohorts, θ = 0.5', '4组，θ = 0.5'),
    'coh4_t10': ('EV', 'R1.4a', '4 cohorts, θ = 1 (solved in sensF5 only)', '4组，θ = 1（只在sensF5中求解）'),
    'v2g6': ('EV', 'R1.5a', 'V2G battery-wear cost 6 JPY/kWh (3)', 'V2G电池损耗成本6日元/kWh（3）'),
    'v2g10': ('EV', 'R1.5a', 'V2G battery-wear cost 10 JPY/kWh (3)', 'V2G电池损耗成本10日元/kWh（3）'),
    'evcap080': ('EV', 'R1.5a', 'Usable battery capacity 0.8 of nominal (0.9); uncontrolled profile rebuilt', '电池可用容量为名义容量的0.8（0.9）；无序充电曲线重新生成'),
    'part025': ('EV', 'R2.6a', 'Participation 25% (50%)', '参与率25%（50%）'),
    'part075': ('EV', 'R2.6a', 'Participation 75% (50%)', '参与率75%（50%）'),
    'part100': ('EV', 'R2.6a', 'Participation 100% (50%)', '参与率100%（50%）'),
    'chg6': ('EV', 'R2.6a', 'Charger 6 kW per vehicle (10 kW); uncontrolled profile rebuilt', '每车充电桩6 kW（10 kW）；无序充电曲线重新生成'),
    'mkt100': ('SYS', 'R1.6a, R2.6a', 'Interface limit 100 MW (118)', '接口上限100 MW（118）'),
    'mkt150': ('SYS', 'R1.6a, R2.6a', 'Interface limit 150 MW (118)', '接口上限150 MW（118）'),
    'price090': ('SYS', 'R1.6c', 'Electricity prices ×0.9', '电价×0.9'),
    'price110': ('SYS', 'R1.6c', 'Electricity prices ×1.1', '电价×1.1'),
    'wind075': ('SYS', 'R1.6c', 'Wind output ×0.75', '风电出力×0.75'),
    'joint090': ('SYS', 'R1.6c, R2.2b', 'Wind and PV output, EV connection availability and prices all ×0.9; uncontrolled profile rebuilt', '风光出力、EV接入率和电价同时×0.9；无序充电曲线重新生成'),
    'load090': ('SYS', 'R2.2b', 'Non-EV local load ×0.9', '非EV本地负荷×0.9'),
    'load110': ('SYS', 'R2.2b', 'Non-EV local load ×1.1', '非EV本地负荷×1.1'),
    'netcharge': ('SYS', 'R1.3c', 'Network charges: +2 JPY/kWh on purchases, −1 JPY/kWh on sales (0)', '网费：购电加2日元/kWh，售电扣1日元/kWh（0）'),
    'aperp': ('SYS', 'R1.3b', 'Perpetual annuities instead of truncation at 2050', '永续年金代替截断到2050年'),
}
CAT = {'H2': ('hydrogen', '氢能'), 'EV': ('EV fleet', 'EV车队'), 'SYS': ('system-wide', '全系统')}
assert set(G) - {'coh4_t10'} == set(df.index) - {'BASE'}, 'group list differs from sensF6_summary.csv'
for g, (cat, *_) in G.items():   # category check against the scenarios actually re-solved
    if g == 'coh4_t10':
        continue
    want = {'H2': ('S2,CH', ''), 'EV': ('CH', 'C0'), 'SYS': ('S2,CH', 'S1,C0')}[cat]
    r = df.loc[g]
    assert (r.solved_F6, '' if pd.isna(r.from_sensF5) else r.from_sensF5) == want, g

m = lambda x: '–' if pd.isna(x) else f'{x:.2f}'.replace('-', '−')
kg = lambda x: '–' if pd.isna(x) else f'{x:,.0f}'
yr = lambda a, b: '–' if pd.isna(a) else (f'{a:.0f}' if a == b else f'{a:.0f}/{b:.0f}')


def settings(lang):
    z = lang == 'zh'
    out = ['| 类别 | 组 | 设定（括号内为基准值） | 审稿意见 | sensF6中求解 | 取自sensF5 |' if z else
           '| Category | Group | Setting (base value in parentheses) | Comment | Solved in sensF6 | From sensF5 |', '|:--|:--|:--|:--|:--|:--|']
    for g, (cat, com, en, zh) in G.items():
        if g == 'coh4_t10':
            sol, f5 = '–', ('C0, CH（不可行）' if z else 'C0, CH (infeasible)')
        else:
            r = df.loc[g]
            sol, f5 = r.solved_F6.replace(',', ', '), ('–' if pd.isna(r.from_sensF5) else r.from_sensF5.replace(',', ', '))
        out.append(f'| {CAT[cat][1 if z else 0]} | {g} | {zh if z else en} | {com} | {sol} | {f5} |')
    return '\n'.join(out)


def results(cat, lang):
    z = lang == 'zh'
    ev = cat == 'EV'
    hd = ['组' if z else 'Group', 'S1', 'S2', 'C0', 'CH', 'ΔH(S)', 'ΔH(C)', 'I^S^~C~', 'ΔH(C)/ΔH(S)'] + (['C0−A0'] if ev else []) + \
         (['2050年电解槽 S2/CH（kg/h）', 'CH 2050年储罐（t）', '首建年 S2/CH'] if z else ['Electrolyzer 2050 S2/CH (kg/h)', 'Tank CH 2050 (t)', 'First H~2~ build S2/CH'])
    out = ['| ' + ' | '.join(hd) + ' |', '|:--|' + '--:|' * (len(hd) - 1)]
    for g in ['BASE'] + [k for k, v in G.items() if v[0] == cat]:
        nm = ('基准F6' if z else 'Base F6') if g == 'BASE' else g
        if g == 'coh4_t10':   # S1, S2 not affected (base); C0 and CH infeasible in sensF5
            b, inf = df.loc['BASE'], ('不可行' if z else 'infeasible')
            out.append('| ' + ' | '.join([nm, m(b.S1), m(b.S2), inf, inf] + ['–'] * (len(hd) - 5)) + ' |')
            continue
        r = df.loc[g]
        row = [nm, m(r.S1), m(r.S2), m(r.C0), m(r.CH), m(r.dH_S), m(r.dH_C), m(r.I_S), m(r.ratio)] + ([m(r.EV_flex_CA)] if ev else []) + \
              [f'{kg(r.el_S2_kgph)}/{kg(r.el_CH_kgph)}', f'{r.tank_CH_t:.1f}', yr(r.first_h2_S2, r.first_h2_CH)]
        out.append('| ' + ' | '.join(row) + ' |')
    return '\n'.join(out)


g34 = df.drop(index='BASE')
stats = {'n_groups': int(len(g34)), 'n_cases_sensF6': int(sum(len(s.split(',')) for s in g34.solved_F6)),
         'n_cases_from_sensF5': int(sum(len(s.split(',')) for s in g34.from_sensF5.dropna())),
         'n_IS_negative': int((g34.I_S < 0).sum()), 'ratio_min': float(g34.ratio.min()), 'ratio_min_group': g34.ratio.idxmin(),
         'ratio_max': float(g34.ratio.max()), 'ratio_max_group': g34.ratio.idxmax(),
         'ratio_min_excl_capex130': float(g34.drop(index='capex130').ratio.min()),
         'ratio_min_excl_capex130_group': g34.drop(index='capex130').ratio.idxmin(),
         'dH_S_min': float(g34.dH_S.min()), 'dH_S_min_group': g34.dH_S.idxmin(), 'dH_S_max': float(g34.dH_S.max()), 'dH_S_max_group': g34.dH_S.idxmax(),
         'coh4_t10_sensF5': f5c, 'base': {k: float(df.at['BASE', k]) for k in ('dH_S', 'dH_C', 'I_S', 'ratio', 'EV_flex_CA')}}
stats['n_cases_total'] = stats['n_cases_sensF6'] + stats['n_cases_from_sensF5']
(HERE / 'si_s9_stats.json').write_text(json.dumps(stats, indent=1, ensure_ascii=False), encoding='utf-8')
block = {'SET_EN': settings('en'), 'SET_ZH': settings('zh')}
for c in ('H2', 'EV', 'SYS'):
    block[f'{c}_EN'], block[f'{c}_ZH'] = results(c, 'en'), results(c, 'zh')
print(json.dumps(stats, indent=1, ensure_ascii=False))
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
