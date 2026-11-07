"""Write sections_F5/SI_S10_lhs.md (Supplementary Section S10, Latin hypercube sample) from the F6 LHS batch.
Inputs (read only): 27_PyPSA_rebuild_20261016/results/lhsF6_20261031/lhs_samples.csv, lhs_results.csv, lhs_prcc.csv,
lhs_timescale_2050.csv (make_lhs_f6.py, analyze_lhs_f6.py, lhs_timescale_f6.py); base values from
results/f6_20261030/F6_summary.csv and postprocess/timescale_metrics.csv. Also writes si_data/si_s10_summary.csv.
Usage: python si_s10_lhs.py [--tables-only | --rewrite-text]
Existing prose is preserved by default; --rewrite-text explicitly regenerates the narrative template."""
from pathlib import Path
import re
import sys

import pandas as pd

HERE = Path(__file__).resolve().parent
RES = HERE.parents[2] / '27_PyPSA_rebuild_20261016' / 'results'
D = RES / 'lhsF6_20261031'
OUT = HERE.parent / 'sections_F5' / 'SI_S10_lhs.md'
smp = pd.read_csv(D / 'lhs_samples.csv', index_col=0)
r = pd.read_csv(D / 'lhs_results.csv', index_col=0)
P = pd.read_csv(D / 'lhs_prcc.csv', index_col=0)
ts = pd.read_csv(D / 'lhs_timescale_2050.csv')
assert (r.n_optimal == 6).all() and len(r) == 40
s = pd.read_csv(RES / 'f6_20261030' / 'F6_summary.csv')
s = s[s.batch == 'F6'].set_index('case')
bt = pd.read_csv(RES / 'f6_20261030' / 'postprocess' / 'timescale_metrics.csv')
bt = bt[bt.year == 2050].set_index(['case', 'storage'])
n = s.npv
B = {'dH_S': n.S2 - n.S1, 'dH_A': n.AH - n.A0, 'dH_C': n.CH - n.C0, 'EV_CA': n.C0 - n.A0, 'EV_CA_H': n.CH - n.AH}
B['I_A'] = B['dH_C'] - B['dH_A']; B['ratio_A'] = B['dH_C'] / B['dH_A']
B['el_change_AH_CH'] = s.el_kgph_2050.CH / s.el_kgph_2050.AH - 1
BUILT = 0.01
b = r[r.dH_A > BUILT]
nb = r[r.dH_A <= BUILT]
h = ts[(ts.storage == 'H2') & ts['sample'].isin(b.index) & ts.case.isin(['S2', 'CH'])]
e = ts[ts.storage == 'EV managed']
f2 = lambda x: f'{x:.2f}'.replace('-0.00', '0.00').replace('-', '−')
f1 = lambda x: f'{x:.1f}'.replace('-', '−')
pc = lambda x: f'{100 * x:.0f}'.replace('-', '−')
row = lambda c: '| ' + ' | '.join(c) + ' |'

# ---- Table S10.1 parameters
PAR = [('price_scale', 'Price level (multiplier on the Tohoku price path)', '电价水平（东北电价路径的乘数）', '1', '0.9–1.1', 'price090, price110'),
       ('wind_scale', 'Wind output (multiplier on the hourly capacity factor)', '风电出力（逐时容量因子的乘数）', '1', '0.8–1.1', 'wind075'),
       ('market_limit_mw', 'Interface capacity, purchases and sales (MW)', '接口容量，购电与售电（MW）', '118', '100–150', 'mkt100, mkt150'),
       ('load_scale', 'Non-EV demand (multiplier)', '非EV需求（乘数）', '1', '0.9–1.1', 'load090, load110'),
       ('h2_capex_scale', 'Hydrogen capital cost: electrolyzer, fuel cell and tank (multiplier)', '氢能造价：电解槽、燃料电池和储罐（乘数）', '1', '0.7–1.3', 'capex070, capex130'),
       ('el_sec_scale', 'Electrolyzer specific consumption path 59/57/56/54 kWh/kg (multiplier)', '电解槽单位耗电路径59/57/56/54 kWh/kg（乘数）', '1', '0.89–1.09', 'eff_hi, eff_lo'),
       ('fc_kg_scale', 'Fuel-cell specific consumption path 60.6/57.7/54.6/53.6 kg/MWh (multiplier)', '燃料电池单位耗氢路径60.6/57.7/54.6/53.6 kg/MWh（乘数）', '1', '0.95–1.13', 'eff_hi, eff_lo'),
       ('ev_participation', 'Share of the fleet in managed charging', '参与受控充电的车队比例', '0.5', '0.25–1.0', 'part025, part075, part100'),
       ('v2g_cost', 'V2G wear cost (JPY/kWh, battery-side discharge)', 'V2G损耗成本（JPY/kWh，电池侧放电）', '3', '0–10', 'v2g6, v2g10')]
for k, *_ in PAR:
    assert k in smp.columns
T1 = [row(['Parameter', 'Base', 'Range', 'Sample min–max', 'One-at-a-time groups']), '|:--|--:|--:|--:|:--|']
def parameter_display(k, x):
    if k == 'market_limit_mw': return f'{x:.0f}'
    if k == 'v2g_cost': return f'{x:.3f}' if 0 < abs(x) < 0.05 else f'{x:.1f}'
    return f'{x:.3f}'
T1 += [row([f'{en} [{zh}]{{.zh}}', base, rg, parameter_display(k, smp[k].min())+'–'+parameter_display(k, smp[k].max()), g]) for k, en, zh, base, rg, g in PAR]

# ---- Table S10.2 distributions
q = lambda x: [f2(x.min()), f2(x.quantile(.25)), f2(x.median()), f2(x.quantile(.75)), f2(x.max())]
qp = lambda x: [pc(x.min()), pc(x.quantile(.25)), pc(x.median()), pc(x.quantile(.75)), pc(x.max())]
q1 = lambda x: [f1(x.min()), f1(x.quantile(.25)), f1(x.median()), f1(x.quantile(.75)), f1(x.max())]
ROWS = [('ΔH(S) = S2 − S1 (billion JPY)', '无车队时的氢能价值', 'all', q(r.dH_S), f2(B['dH_S'])),
        ('ΔH(A) = AH − A0', '无序充电时的氢能价值', 'all', q(r.dH_A), f2(B['dH_A'])),
        ('ΔH(C) = CH − C0', 'V2G时的氢能价值', 'all', q(r.dH_C), f2(B['dH_C'])),
        ('I_C = ΔH(C) − ΔH(A)', '交互项', 'built', q(b.I_A), f2(B['I_A'])),
        ('I^S^_C = ΔH(C) − ΔH(S)', '以S为参照的交互项', 'built', q(b.I_S), f2(B['dH_C'] - B['dH_S'])),
        ('Crowding-out ratio ΔH(C)/ΔH(A)', '挤出比例', 'built', q(b.ratio_A), f2(B['ratio_A'])),
        ('Electrolyzer 2050, CH vs AH (%)', '2050年电解槽，CH相对AH（%）', 'built', qp(b.el_change_AH_CH), pc(B['el_change_AH_CH'])),
        ('EV flexibility C0 − A0 (billion JPY)', '无氢时的EV灵活性', 'all', q(r.EV_CA), f2(B['EV_CA'])),
        ('EV flexibility CH − AH', '有氢时的EV灵活性', 'all', q(r.EV_CA_H), f2(B['EV_CA_H'])),
        ('H~2~ FIFO mean residence, S2 and CH (days)', '氢FIFO平均驻留时间（天）', 'built', q(h.fifo_mean_days),
         f'{bt.at[("S2", "H2"), "fifo_mean_days"]:.2f} / {bt.at[("CH", "H2"), "fifo_mean_days"]:.2f}'),
        ('H~2~ variance share 1–7 d (%)', '氢1–7天方差份额（%）', 'built', q1(h.var_1to7d),
         f'{bt.at[("S2", "H2"), "var_1to7d"]:.1f} / {bt.at[("CH", "H2"), "var_1to7d"]:.1f}'),
        ('H~2~ variance share >28 d (%)', '氢28天以上方差份额（%）', 'built', q1(h.var_gt28d),
         f'{bt.at[("S2", "H2"), "var_gt28d"]:.1f} / {bt.at[("CH", "H2"), "var_gt28d"]:.1f}'),
        ('V2G fleet intraday variance share, CH (%)', 'V2G车队日内方差份额（%）', 'all', q1(e.var_lt1d_7_28), f'{bt.at[("CH", "EV managed"), "var_lt1d_7_28"]:.1f}'),
        ('V2G fleet FIFO mean residence, CH (days)', 'V2G车队FIFO平均驻留时间（天）', 'all', q(e.fifo_mean_days), f'{bt.at[("CH", "EV managed"), "fifo_mean_days"]:.2f}')]
NB = {'all': f'{len(r)}', 'built': f'{len(b)}'}
T2 = [row(['Metric', 'n', 'Min', 'P25', 'Median', 'P75', 'Max', 'F6 base']), '|:--|--:|--:|--:|--:|--:|--:|--:|']
for en, zh, sel, vals, base in ROWS:
    nn = NB[sel] if 'H~2~' not in en else f'{len(h)}'
    T2.append(row([f'{en} [{zh}]{{.zh}}', nn] + vals + [base]))
pd.DataFrame([dict(metric=en, n=NB[sel], min=v[0], p25=v[1], median=v[2], p75=v[3], max=v[4], base=base)
              for en, zh, sel, v, base in ROWS]).to_csv(HERE / 'si_s10_summary.csv', index=False)

# ---- Table S10.3 PRCC
YC = [('dH_S', 'ΔH(S)'), ('dH_C', 'ΔH(C)'), ('I_A', 'I_C'), ('ratio_A', 'Ratio'), ('EV_CA', 'C − A')]
T3 = [row(['Parameter'] + [c for _, c in YC]), '|:--|' + '--:|' * len(YC)]
for k, en, zh, *_ in PAR:
    T3.append(row([en.split(' (')[0]] + [f'{P.at[k, y]:+.2f}'.replace('-0.00', '0.00').replace('-', '−') for y, _ in YC]))

# ---- Table S10.4 per sample
T4 = [row(['Sample', 'Price', 'Wind', 'MW', 'Load', 'Capex', 'El.', 'FC', 'Part.', 'V2G', 'ΔH(S)', 'ΔH(A)', 'ΔH(C)', 'I_C', 'Ratio', 'C − A']),
      '|:--|' + '--:|' * 15]
for sid, x in r.iterrows():
    T4.append(row([sid, f'{x.price_scale:.3f}', f'{x.wind_scale:.3f}', f'{x.market_limit_mw:.0f}', f'{x.load_scale:.3f}',
                   f'{x.h2_capex_scale:.3f}', f'{x.el_sec_scale:.3f}', f'{x.fc_kg_scale:.3f}', f'{x.ev_participation:.2f}',
                   parameter_display('v2g_cost', x.v2g_cost), f2(x.dH_S), f2(x.dH_A), f2(x.dH_C), f2(x.I_A),
                   f2(x.ratio_A) if x.dH_A > BUILT else '–', f2(x.EV_CA)]))

big = b[b.dH_A > 0.2]
low = b[b.ratio_A < 0.5]
txt = f'''---
title: "Supplementary Section S10: Latin hypercube sample of joint parameter uncertainty [补充材料S10节：参数联合不确定性的拉丁超立方抽样]{{.zh}}"
bibliography: ../references.bib
link-citations: true
lang: en-US
---

# S10. Latin hypercube sample [拉丁超立方抽样]{{.zh}} {{#si:lhs .unnumbered}}

This section documents the joint sample of Section [](#sec:sensitivity) (comments R2.2, R2.4a and R2.6b): the sampled parameters and ranges, the distributions of the value metrics, the partial rank correlation coefficients and the result of every sample. All values are billion JPY, present value in 2024 at 3%, unless stated otherwise.

::: zh
本节给出正文第 [](#sec:sensitivity) 节联合抽样的细节（对应审稿意见R2.2、R2.4a和R2.6b）：抽样参数及其范围、各价值指标的分布、偏秩相关系数以及每个样本的结果。除另有说明外，所有数值为十亿日元，按3%贴现到2024年的现值。
:::

## S10.1 Design [抽样设计]{{.zh}} {{#si:lhs_design .unnumbered}}

Nine parameters are drawn jointly by Latin hypercube sampling [@mckay1979Comparison] ({len(r)} samples, seed 20261031, uniform over each range; registry entry lhs_F6_20261031). Every sample keeps all other settings of the F6 base and is solved for S1, S2, A0, AH, C0 and CH, so that each sample gives the hydrogen value under every EV regime, the interaction $I_\\mathrm{{C}}=\\Delta H(\\mathrm{{C}})-\\Delta H(\\mathrm{{A}})$ of Equation (11) and EV flexibility C − A ({6 * len(r)} LP solves, all optimal). The ranges follow the one-at-a-time groups of Supplementary Section S9 (Table S10.1). The wind range extends to ×1.1 so that the sample covers wind years better than 2024 as well as the poorer ones of the group wind075. The two efficiency multipliers scale the whole path of specific consumption, so a value below 1 means a more efficient plant. Charger power and EV availability are not sampled because they change the fixed charging profile of case A (Supplementary Section S6). The samples weight the ranges equally; they are a designed exploration, not a probability forecast. Hydrogen counts as built when ΔH(A) exceeds 0.01 billion JPY.

::: zh
九个参数用拉丁超立方抽样 [@mckay1979Comparison] 联合抽取（{len(r)}组样本，随机种子20261031，在各自范围内均匀分布；登记表条目lhs_F6_20261031）。每组样本保持F6基准的其余设定不变，求解S1、S2、A0、AH、C0和CH，因此每组都能给出各充电方式下的氢能价值、式(11)的交互项$I_\\mathrm{{C}}=\\Delta H(\\mathrm{{C}})-\\Delta H(\\mathrm{{A}})$以及EV灵活性C − A（共{6 * len(r)}次线性规划求解，全部最优）。范围沿用补充材料S9节的单因素敏感性组（表S10.1）。风电范围上限取×1.1，使抽样既覆盖wind075组那样较差的风况，也覆盖优于2024年的风况。两个效率乘数作用于整条单位耗电（耗氢）路径，小于1表示装置更高效。充电功率和EV可用率未纳入抽样，因为它们会改变A的固定充电曲线（补充材料S6节）。各样本对范围等权覆盖，是设计好的探索，不是概率预测。ΔH(A)超过0.01十亿日元即视为建设了氢能。
:::

Table: Table S10.1. Sampled parameters, base values, ranges and the corresponding one-at-a-time groups (Supplementary Section S9). [表S10.1　抽样参数、基准值、范围以及对应的单因素敏感性组（补充材料S9节）。]{{.zh}}

{chr(10).join(T1)}

## S10.2 Distributions [结果分布]{{.zh}} {{#si:lhs_dist .unnumbered}}

Hydrogen is built in {len(b)} of the {len(r)} samples. In the other {len(nb)} ({', '.join(nb.index)}) its value is below 0.01 billion JPY under every EV regime; these samples combine a high hydrogen capital cost (×{nb.h2_capex_scale.min():.2f}–{nb.h2_capex_scale.max():.2f}) with a low price level (×{nb.price_scale.min():.2f}–{nb.price_scale.max():.2f}) and are excluded from the interaction statistics. In every sample with hydrogen the interaction is negative (Table S10.2), from {f2(b.I_A.min())} to {f2(b.I_A.max())} billion JPY, and V2G reduces the 2050 electrolyzer capacity by {pc(-b.el_change_AH_CH.max())}% to {pc(-b.el_change_AH_CH.min())}%. Measured against the no-fleet reference, $I^\\mathrm{{S}}_\\mathrm{{C}}$, the interaction is almost the same (median {f2(b.I_S.median())}), because uncontrolled charging barely changes the hydrogen value (ΔH(A) − ΔH(S) between {f2((r.dH_A - r.dH_S).min())} and {f2((r.dH_A - r.dH_S).max())}). The crowding-out ratio has a median of {f2(b.ratio_A.median())}. Ratios below 0.5 occur in {len(low)} samples, all with ΔH(A) below {f2(low.dH_A.max())} billion JPY: where hydrogen is barely worth building, the fleet displaces most of it. In the {len(big)} samples with ΔH(A) above 0.2 billion JPY the ratio lies between {f2(big.ratio_A.min())} and {f2(big.ratio_A.max())}. EV flexibility C − A exceeds the hydrogen value ΔH(A) in all {len(r)} samples.

::: zh
{len(r)}组样本中有{len(b)}组建设了氢能。其余{len(nb)}组（{'、'.join(nb.index)}）在各充电方式下的氢能价值都低于0.01十亿日元；这些样本同时具有较高的氢能造价（×{nb.h2_capex_scale.min():.2f}–{nb.h2_capex_scale.max():.2f}）和较低的电价水平（×{nb.price_scale.min():.2f}–{nb.price_scale.max():.2f}），不计入交互项统计。在所有建设了氢能的样本中，交互项均为负（表S10.2），在{f2(b.I_A.min())}至{f2(b.I_A.max())}十亿日元之间，V2G使2050年电解槽容量减少{pc(-b.el_change_AH_CH.max())}%至{pc(-b.el_change_AH_CH.min())}%。以无车队为参照的交互项$I^\\mathrm{{S}}_\\mathrm{{C}}$几乎相同（中位数{f2(b.I_S.median())}），因为无序充电几乎不改变氢能价值（ΔH(A) − ΔH(S)在{f2((r.dH_A - r.dH_S).min())}至{f2((r.dH_A - r.dH_S).max())}之间）。挤出比例的中位数为{f2(b.ratio_A.median())}。比例低于0.5的样本有{len(low)}组，其ΔH(A)都低于{f2(low.dH_A.max())}十亿日元：氢能几乎不值得建设时，车队会挤出其大部分价值。在ΔH(A)高于0.2十亿日元的{len(big)}组中，该比例在{f2(big.ratio_A.min())}至{f2(big.ratio_A.max())}之间。在全部{len(r)}组中，EV灵活性C − A都高于氢能价值ΔH(A)。
:::

The timescale metrics of Supplementary Section S11 were recomputed for every sample ({len(h)} hydrogen series in S2 and CH of the samples with hydrogen, {len(e)} fleet series in CH). The mean hydrogen residence time ranges from {h.fifo_mean_days.min():.2f} to {h.fifo_mean_days.max():.2f} days and the share of hydrogen variance in the 1–7-day band from {h.var_1to7d.min():.1f}% to {h.var_1to7d.max():.1f}%; at most {100 * h.fifo_share_gt_168h.max():.1f}% of the hydrogen stays in the tank longer than one week. The intraday variance share of the V2G fleet ranges from {e.var_lt1d_7_28.min():.1f}% to {e.var_lt1d_7_28.max():.1f}%. The division of roles, intraday for the fleet and a few days for hydrogen, holds in every sample.

::: zh
我们对每个样本重新计算了补充材料S11节的时间尺度指标（建设了氢能的样本中S2和CH的{len(h)}条氢序列，CH中的{len(e)}条车队序列）。氢的平均驻留时间在{h.fifo_mean_days.min():.2f}至{h.fifo_mean_days.max():.2f}天之间，氢在1–7天频段的方差份额在{h.var_1to7d.min():.1f}%至{h.var_1to7d.max():.1f}%之间；按FIFO在储罐中停留超过一周的氢最多为{100 * h.fifo_share_gt_168h.max():.1f}%。V2G车队的日内方差份额在{e.var_lt1d_7_28.min():.1f}%至{e.var_lt1d_7_28.max():.1f}%之间。"车队在日内、氢能在数日"的分工在每个样本中都成立。
:::

Table: Table S10.2. Distribution of the value and timescale metrics over the samples (n = number of samples or series; "built" metrics only over the {len(b)} samples with hydrogen). The F6 base column gives S2 / CH where two values are shown. [表S10.2　各价值指标与时间尺度指标在样本上的分布（n为样本数或序列数；与交互项有关的指标只统计建设了氢能的{len(b)}组）。F6基准一列中有两个数值时分别对应S2 / CH。]{{.zh}}

{chr(10).join(T2)}

## S10.3 Partial rank correlation [偏秩相关系数]{{.zh}} {{#si:lhs_prcc .unnumbered}}

Partial rank correlation coefficients [@marino2008Methodology] measure the monotonic influence of each parameter on a metric after the linear effect of the other parameters' ranks is removed (Table S10.3; ΔH(S), ΔH(C), $I_\\mathrm{{C}}$ and C − A over all {len(r)} samples, the crowding-out ratio over the {len(b)} samples with hydrogen). The hydrogen value is driven by the hydrogen capital cost, fuel-cell consumption and the price level. The interaction follows the size of the hydrogen plant: it becomes more negative with a higher price level and lower hydrogen costs, and with a larger participating fleet. The crowding-out ratio, which removes the scale, depends most on EV participation, the hydrogen capital cost and the V2G wear cost. EV flexibility depends on participation, the wear cost and the price level, and hardly on the hydrogen parameters.

::: zh
偏秩相关系数 [@marino2008Methodology] 在剔除其他参数秩的线性影响后，衡量各参数对某一指标的单调影响（表S10.3；ΔH(S)、ΔH(C)、$I_\\mathrm{{C}}$和C − A基于全部{len(r)}组样本，挤出比例基于建设了氢能的{len(b)}组）。氢能价值主要取决于氢能造价、燃料电池耗氢和电价水平。交互项随氢能装置规模变化：电价越高、氢能成本越低、参与车队越大，交互项越负。挤出比例剔除了规模的影响，最依赖于EV参与率、氢能造价和V2G损耗成本。EV灵活性取决于参与率、损耗成本和电价水平，几乎不受氢能参数影响。
:::

Table: Table S10.3. Partial rank correlation coefficients of the sampled parameters with the value metrics. A negative coefficient for $I_\\mathrm{{C}}$ means a more negative interaction. [表S10.3　抽样参数与各价值指标的偏秩相关系数。$I_\\mathrm{{C}}$的系数为负表示交互项更负。]{{.zh}}

{chr(10).join(T3)}

## S10.4 Results by sample [逐样本结果]{{.zh}} {{#si:lhs_samples .unnumbered}}

Table: Table S10.4. Sampled parameter values and value metrics of every sample (Price, Wind, Load, Capex, El., FC: multipliers; MW: interface capacity; Part.: EV participation share; V2G: wear cost in JPY/kWh; values in billion JPY; ratio ΔH(C)/ΔH(A), "–" where hydrogen is not built). [表S10.4　每个样本的抽样参数与价值指标（Price、Wind、Load、Capex、El.、FC为乘数；MW为接口容量；Part.为EV参与比例；V2G为损耗成本，JPY/kWh；数值单位为十亿日元；比例为ΔH(C)/ΔH(A)，未建设氢能时记为"–"）。]{{.zh}}

{chr(10).join(T4)}

<!-- sources:
Generated by revision_round1/04_manuscript/si_data/si_s10_lhs.py (do not edit by hand; rerun the script).
Samples: 27_PyPSA_rebuild_20261016/results/lhsF6_20261031/lhs_samples.csv (src/make_lhs_f6.py, registry lhs_F6_20261031, params/h2.yaml).
Values: lhs_results.csv (src/analyze_lhs_f6.py; summary.json npv_billion_JPY and installed_units.csv of each <sample>__<case> run; all 240 runs termination optimal).
PRCC: lhs_prcc.csv (rank-regression residuals, analyze_lhs_f6.py). Timescale: lhs_timescale_2050.csv (src/lhs_timescale_f6.py, f6_postprocess definitions).
Base: results/f6_20261030/F6_summary.csv (npv, el_kgph_2050) and postprocess/timescale_metrics.csv (2050). Summary table also in si_data/si_s10_summary.csv.
-->
'''
# --tables-only retains manually revised scientific prose and captions.
if OUT.exists() and '--rewrite-text' not in sys.argv:
    txt = OUT.read_text(encoding='utf-8')
    blocks = list(re.finditer(r'(?m)^\|[^\n]*\n(?:\|[^\n]*\n)+', txt))
    assert len(blocks) == 4, 'Expected the four S10 tables'
    for match, table in reversed(list(zip(blocks, [T1, T2, T3, T4]))):
        txt = txt[:match.start()] + '\n'.join(table) + '\n' + txt[match.end():]
precision_en = ('Display precision: parameters are rounded for reading; all runs use the unrounded samples in lhs_samples.csv. '
                'The L40 V2G wear cost is shown as 0.006 JPY/kWh, not zero. Monetary 0.00 includes values with absolute magnitude below 0.005 billion JPY. '
                'In L31 and L38, ΔH(A) is approximately '+f'{r.at["L31", "dH_A"]*1e6:.1f}'+' and '+f'{r.at["L38", "dH_A"]*1e6:.0f}'+
                ' thousand JPY, respectively; CH has no hydrogen, so the small interactions are negative even though displayed as 0.00. '
                'The same monetary rounding applies to Table S10.2. Ratios and threshold classifications use unrounded results.')
precision_zh = ('展示精度：参数为便于阅读而舍入，实际运行使用lhs_samples.csv中的未舍入样本。L40的V2G损耗成本显示为0.006日元/kWh，并非零。'
                '金额0.00包括绝对值小于0.005十亿日元的数值。L31和L38的ΔH(A)分别约为'+f'{r.at["L31", "dH_A"]*1e6:.1f}'+'和'+f'{r.at["L38", "dH_A"]*1e6:.0f}'+
                '千日元；CH不建氢，因此其小额交互项为负，虽然显示为0.00。表S10.2的金额也采用同一舍入规则。比例及阈值分类使用未舍入结果。')
block = '<!-- precision-note:start -->\n'+precision_en+'\n\n::: zh\n'+precision_zh+'\n:::\n<!-- precision-note:end -->\n\n'
txt = re.sub(r'<!-- precision-note:start -->.*?<!-- precision-note:end -->\n*', '', txt, flags=re.S)
txt = txt.replace('Table: Table S10.1.', block+'Table: Table S10.1.', 1)
OUT.write_text(txt, encoding='utf-8')
print('wrote', OUT)
print('not built:', nb.index.tolist(), nb[['h2_capex_scale', 'fc_kg_scale', 'price_scale']].round(3).to_dict('index'))
print('low ratio:', len(low), low.dH_A.max())
