"""Single source of numbers for the F6 manuscript and response (revision_round1/02_plan/F6_facts.md).
Every table is generated from result files; writers cite only from this file. Usage: python make_f6_facts.py"""
from pathlib import Path

import pandas as pd

R = Path(__file__).resolve().parents[1] / 'results'
F = R / 'f6_20261030'
P = F / 'postprocess'
OUT = Path(__file__).resolve().parents[2] / 'revision_round1' / '02_plan' / 'F6_facts.md'
md = lambda df, fmt='{:.2f}': df.to_markdown(floatfmt='.2f') if fmt == '{:.2f}' else df.to_markdown()
s = pd.read_csv(F / 'F6_summary.csv')
n6 = s[s.batch == 'F6'].set_index('case')
npv6 = n6.npv
L = ['# F6 数字总表（自动生成：src/make_f6_facts.py；不要手改）', '',
     '单位：十亿日元，2024 年现值，折现率 3%；容量为当年在役。F6 = F5 + 电解槽启停磨损 1,000 円/MW 额定、热备用 2%、电堆 15 年；燃料电池无 UC（D2_模型设定.md）。',
     '规则：正文与回复信只引用本表数字；敏感性结果用占位符 `[SENS:组名]`、`[LHS:...]`，跑完后统一替换。',
     f'口径说明：first_h2 是第一个非零建设年，正文写"2040 年代初"，不把首建年份作为结论（作者要求）。'
     f'挤出比例 (CH−C0)/(AH−A0) = {(npv6.CH - npv6.C0) / (npv6.AH - npv6.A0):.3f}，即 V2G 使氢能价值降约 {100 * (1 - (npv6.CH - npv6.C0) / (npv6.AH - npv6.A0)):.0f}%；'
     f'电解槽缩小用同一车队的 AH→CH（{100 * (n6.at['CH', 'el_kgph_2050'] / n6.at['AH', 'el_kgph_2050'] - 1):.0f}%），不用 S2→CH（含车队负荷效应）。', '']
for b in ('F6', 'F6t2060'):
    t = s[s.batch == b].set_index('case')
    L += [f'## 1{"a" if b == "F6" else "b"}. 九情景（{b}，来源 results/f6_20261030/F6_summary.csv）', '',
          t[['npv', 'wind_MW_2050', 'el_kgph_2050', 'el_MW_2050', 'fc_MW_2050', 'tank_t_2050', 'first_h2', 'term']].to_markdown(floatfmt='.2f'), '']
    n = t.npv
    v = {'H2 value no EV (S2−S1)': n.S2 - n.S1, 'H2 value A (AH−A0)': n.AH - n.A0, 'H2 value B (BH−B0)': n.BH - n.B0,
         'H2 value C (CH−C0)': n.CH - n.C0, 'EV travel load (A0−S1)': n.A0 - n.S1, 'smart charging (B0−A0)': n.B0 - n.A0,
         'V2G over smart (C0−B0)': n.C0 - n.B0, 'EV flexibility (C0−A0)': n.C0 - n.A0, 'smart charging with H2 (BH−AH)': n.BH - n.AH,
         'V2G with H2 (CH−BH)': n.CH - n.BH, 'EV flexibility with H2 (CH−AH)': n.CH - n.AH,
         'interaction I_B = (BH−B0)−(AH−A0)': (n.BH - n.B0) - (n.AH - n.A0), 'interaction I_C = (CH−C0)−(AH−A0)': (n.CH - n.C0) - (n.AH - n.A0),
         'crowding-out ratio (CH−C0)/(AH−A0)': (n.CH - n.C0) / (n.AH - n.A0),
         'sensitivity interaction I^S_C = (CH−C0)−(S2−S1)': (n.CH - n.C0) - (n.S2 - n.S1), 'sensitivity ratio (CH−C0)/(S2−S1)': (n.CH - n.C0) / (n.S2 - n.S1)}
    L += [f'### 价值指标（{b}）', '', pd.Series(v, name='value').round(3).to_markdown(), '']
f4 = pd.read_csv(R / 'f4_20261029' / 'F4_base_summary.csv').set_index('scen').npv
v4 = {'H2 value no EV (S2−S1)': f4.S2 - f4.S1, 'H2 value A (AH−A0)': f4.AH - f4.A0, 'H2 value B (BH−B0)': f4.BH - f4.B0, 'H2 value C (CH−C0)': f4.CH - f4.C0,
      'EV flexibility (C0−A0)': f4.C0 - f4.A0, 'interaction I_C': (f4.CH - f4.C0) - (f4.AH - f4.A0), 'crowding-out ratio (CH−C0)/(AH−A0)': (f4.CH - f4.C0) / (f4.AH - f4.A0)}
s5 = pd.read_csv(R / 'f5_20261030' / 'F5_summary.csv')
cmp = []
for b5, b6 in (('F5', 'F6'), ('F5t2060', 'F6t2060')):
    a, b = s5[s5.batch == b5].set_index('case'), s[s.batch == b6].set_index('case')
    for k, f in (('H2 value S (S2−S1)', lambda n: n.S2 - n.S1), ('H2 value A (AH−A0)', lambda n: n.AH - n.A0), ('H2 value C (CH−C0)', lambda n: n.CH - n.C0),
                 ('ratio (CH−C0)/(AH−A0)', lambda n: (n.CH - n.C0) / (n.AH - n.A0)), ('ratio (CH−C0)/(S2−S1)', lambda n: (n.CH - n.C0) / (n.S2 - n.S1)),
                 ('EV flexibility C0−A0', lambda n: n.C0 - n.A0), ('EV flexibility with H2 CH−AH', lambda n: n.CH - n.AH)):
        cmp.append({'horizon': b6, 'metric': k, 'F5': f(a.npv), 'F6': f(b.npv)})
    for c in ('S2', 'AH', 'BH', 'CH'):
        for col in ('el_kgph_2050', 'fc_MW_2050', 'tank_t_2050'):
            cmp.append({'horizon': b6, 'metric': f'{c} {col}', 'F5': a.at[c, col], 'F6': b.at[c, col]})
cmp = pd.DataFrame(cmp).assign(diff=lambda x: x.F6 - x.F5)
L += ['## 1c. F5 → F6 对照（F5: results/f5_20261030/F5_summary.csv；无氢情景两者相同）', '', cmp.round(3).to_markdown(index=False), '']
L += ['## 2. R1.3 现值分项账（results/r13_ledger_f6/table_r13_f6.md；启停磨损一行取自求解器目标项）', '', (R / 'r13_ledger_f6' / 'table_r13_f6.md').read_text(encoding='utf-8'), '']
L += ['## 3. 隐含残值（results/f6_20261030/r13_salvage_by_tech.csv）', '', pd.read_csv(F / 'r13_salvage_by_tech.csv').round(3).to_markdown(index=False), '']
cap = pd.read_csv(P / 'capacity_summary.csv')
L += ['## 4. 容量路径（postprocess/capacity_summary.csv）', '',
      cap[cap.case.isin(['S1', 'S2', 'A0', 'AH', 'B0', 'BH', 'C0', 'CH'])][['case', 'year', 'wind_new_MW', 'el_kgph', 'el_MW_at_54kWh_per_kg', 'fc_MW', 'tank_t', 'el_FLH_h2_output']].round(1).to_markdown(index=False), '']
ts = pd.read_csv(P / 'timescale_metrics.csv')
ts = ts[ts.year == 2050]
L += ['## 5. 时间尺度指标 2050（postprocess/timescale_metrics.csv；EV 只计受控 50%，A 为输入的无序曲线）', '',
      ts[['case', 'storage', 'var_lt1d_7_28', 'var_1to7d', 'var_7to28d', 'var_gt28d', 'acf_12h', 'acf_24h', 'throughput_over_capacity', 'fifo_mean_days', 'fifo_median_days', 'lifo_share_le_24h', 'fifo_share_gt_168h']].round(3).to_markdown(index=False), '']
ws = pd.read_csv(P / 'window_sensitivity.csv')
L += ['## 6. 窗口敏感性 7/28 天 vs 5/20 天（postprocess/window_sensitivity.csv）', '', ws.round(1).to_markdown(index=False), '']
eb = pd.read_csv(P / 'energy_balance_summary.csv')
cols = ['case', 'period', 'vre_curtail_rate', 'curtail_incl_aux_dump_ub_rate', 'net_import_GWh', 'net_export_GWh', 'el_elec_GWh', 'fc_out_GWh', 'ev_ch_GWh', 'ev_dis_grid_GWh']
L += ['## 7. 电量与弃电（postprocess/energy_balance_summary.csv；只用净购售电，毛量因同价买卖而无意义；含 dump 的弃电率为上界）', '', eb[[c for c in cols if c in eb]].round(3).to_markdown(index=False), '']
me = pd.read_csv(P / 'mechanism_2050.csv')
L += ['## 8. 挤出机制 2050（postprocess/mechanism_2050.csv；定义见 f6_postprocess.py，与 F5 相同）', '', me.T.to_markdown(), '']
ev = pd.read_csv(P / 'ev_feasibility.csv')
L += ['## 9. R1.4b EV 可行性（postprocess/ev_feasibility.csv）', '', ev.round(4).to_markdown(index=False), '']
uc = pd.read_csv(P / 'el_uc_stats.csv')
L += ['## 10. 电解槽启停与热备用（postprocess/el_uc_stats.csv；等效满容量，以 2050 年容量折算）', '', uc.round(2).to_markdown(index=False), '']
sf = R / 'sensF6_20261030' / 'sensF6_summary.csv'
if sf.exists():
    L += ['## 11. 敏感性 F6（results/sensF6_20261030/sensF6_summary.csv；S1/A0/C0 取 sensF5 同组或基准）', '', pd.read_csv(sf).round(3).to_markdown(index=False), '']
OUT.write_text('\n'.join(L), encoding='utf-8')
print(OUT, len(L))
