"""Read-only reverse inventory: every number that can affect D2, mapped to the registry.

Writes params/mapping/code_inventory.yaml. Line numbers refer to src/model.py (738 lines, 2026-10-28)
unless another file is named. Effective argparse values come from effective_args.py (ast, no import).
Registry ids are checked against params/{h2,ev,grid_econ}.yaml; an unknown id raises.
"""
import json
from collections import Counter
from pathlib import Path
import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PARAMS = ROOT / 'params'
ids = {r['id'] for f in ('h2', 'ev', 'grid_econ') for r in yaml.safe_load((PARAMS / f'{f}.yaml').read_text(encoding='utf-8'))}
eff = json.loads((HERE / 'effective_args.json').read_text(encoding='utf-8'))['args']

items = []


def E(item, where, d2, origin, rid, verdict, notes='', suggest=None):
    for r in ([rid] if isinstance(rid, str) else (rid or [])):
        if r not in ids:
            raise KeyError(r)
    d = dict(item=item, where=where, d2_value=d2, origin=origin, registry_id=rid, verdict=verdict, notes=notes)
    if suggest:
        d['suggest'] = suggest
    items.append(d)


def num(v):
    if isinstance(v, str):
        try:
            f = float(v)
            return int(f) if f.is_integer() and '.' not in v else f
        except ValueError:
            return v
    return v


# ---------------------------------------------------------------- 1. argparse (L634) ----------
# dest -> (usage lines, registry id(s), verdict, notes, suggest)
A = {
 'scenario': ('L209 cfg 读取；L307 has_ev/has_h2；L308 candidates', None, 'orphan',
              'D2 值由批处理给出（src/make_reg1_batch.py L16–19：S0/S1/S2 与 A0/AH/B0/BH/C0/CH），决定参与优化的技术集合（has_ev、has_h2、可扩建对象）。登记表没有情景定义条目。',
              {'domain': 'grid_econ', 'id': 'scenario_design'}),
 'days_per_year': ('L218–221、L295–296、L592–595', 'time_resolution', 'covered', ''),
 'only_year': ('L213–214', 'planning_horizon', 'inactive_in_D2', '诊断用单年切片'),
 'end_year': ('L215–216、L634 HEND', 'planning_horizon', 'inactive_in_D2', '诊断用；HEND 只在截断年金法 vintage_pv 中使用'),
 'continuous': ('L643（只写入 stats）', None, 'numerical', '兼容开关，不进入模型'),
 'market_limit_mw': ('L317、L320、L636', 'grid_interface_mw', 'covered', '覆盖 PLEXOS TohokuPowerMarket Max Purchases/Max Sales 150'),
 'renewable_scale': ('L237–238', 're_profile_source', 'covered', ''),
 'ev_availability_scale': ('L253–255、L640', 'ev_availability_scale', 'covered', ''),
 'price_scale': ('L239', 'price_series', 'covered', ''),
 'ev_control': ('L278、L285、L361、L367、L384、L410、L564–565', None, 'orphan',
                'D2 C 组取 argparse 默认 bidirectional（允许 V2G）；A 组 fixed、B 组 charge_only 由批处理 make_reg1_batch.py L17–18 指定。是否允许 V2G 决定 EV 的全部系统价值，但登记表只有 V2G 成本、参与率等，没有控制方式本身的条目。',
                {'domain': 'ev', 'id': 'ev_control_regimes'}),
 'fixed_charge_profile': ('L279、L286–290', 'ev_uncontrolled_charging_profile', 'covered', '已用 newbase 参数（0.07×0.9、0.93、0.98、0.0005、0.96、10 kW）逐时复算前 500 h，误差 0'),
 'solver': ('L646、L653', None, 'numerical', 'argparse 默认 highs；批处理 make_reg1_batch.py L29 改为 gurobi。default_D2_args.txt 不含求解器设定'),
 'time_limit': ('L646', None, 'numerical', 'argparse 默认 120 s；批处理 L29 为 36000 s。只用 default_D2_args.txt 运行会在 120 s 截断'),
 'threads': ('L646', None, 'numerical', '批处理为 5'),
 'ev_max_soc': ('L394、L414', 'ev_soc_max', 'covered', '未设，取 cfg Max SoC/100 = 0.96；注意 e_initial 的 0.96 是另外硬编码的，不随本参数变化'),
 'v2g_cost_jpy_per_kwh': ('L408、L422', 'ev_v2g_cost', 'covered', ''),
 'ev_cohorts': ('L384', 'ev_cohort_test', 'covered', 'D2 = 1（不分组）'),
 'ev_cohort_theta': ('L391', 'ev_cohort_test', 'inactive_in_D2', '只在 ev_cohorts > 1 时使用'),
 'ev_capacity_scale': ('L206', 'ev_soh_capacity_scale', 'covered', ''),
 'h2_electrolysis_mwh_per_kg': ('L334、L339、L434、L475、L662', 'h2_el_linear_coeff', 'covered', '同时决定物理上限的块数 2000/(10×0.04912) = 4071.7'),
 'h2_availability': ('L473–474', None, 'inactive_in_D2', '被 --el-availability / --fc-availability 覆盖，静默不起作用'),
 'h2_standing_loss_per_day': ('L335、L338', 'h2_tank_standing_loss', 'covered', ''),
 'h2_limit_scale': ('L336、L432–433', 'h2_build_caps', 'inactive_in_D2', '--h2-unlimited 下不起作用'),
 'h2_unlimited': ('L336、L432–436、L661', 'h2_build_caps', 'covered', ''),
 'h2_annual_unlimited': ('L433', 'h2_build_caps', 'inactive_in_D2', ''),
 'h2_total_unlimited': ('L336、L432', 'h2_build_caps', 'inactive_in_D2', ''),
 'h2_uc': ('L356、L487–515、L519–524', 'h2_uc_enabled', 'covered', ''),
 'el_min_load': ('L481、L501', 'h2_el_min_load', 'covered', ''),
 'fc_min_load': ('L481、L504', 'h2_fc_min_load', 'covered', ''),
 'el_startup_cost': ('L481、L510', 'h2_el_startup_cost', 'covered', ''),
 'fc_startup_cost': ('L481、L510', 'h2_fc_standby_startup', 'covered', ''),
 'el_ramp': ('L481、L511–514', 'h2_el_ramp', 'covered', '1 ≤ 1，生成冗余约束'),
 'fc_ramp': ('L481、L511–514', 'h2_fc_ramp', 'covered', ''),
 'investment_method': ('L173、L440–448', 'investment_cost_method', 'covered', '来自 PRESET_PLEXOS L631'),
 'h2_capex': ('L167（只在 annuity_pv）', 'h2_el_capex', 'inactive_in_D2', 'PLEXOS 方法下静默忽略'),
 'wacc': ('L155（只在 annuity_pv）', 'wacc_build_cost', 'inactive_in_D2', 'PLEXOS 方法下静默忽略；D2 的 3% 来自各处硬编码 1.03'),
 'grid_max_mw': ('L318–321、L540', 'grid_reinforcement_max_mw', 'covered', 'D2 = 0（不扩容）；登记值 82 是敏感性用'),
 'grid_capex_jpy_per_kw': ('L98', 'grid_reinforcement_capex', 'inactive_in_D2', 'gmax = 0 时不用。注意 --preset plexos 下默认 0（扩容免费），登记值 105000 只在 PRESET_NEWBASE'),
 'grid_fom': ('L98', 'grid_reinforcement_fom', 'inactive_in_D2', 'argparse 默认 0.01 ≠ 登记值 0.019'),
 'grid_life': ('L96', 'grid_reinforcement_life', 'inactive_in_D2', 'argparse 默认 40 ≠ 登记值 28'),
 'grid_wacc': ('L96', None, 'inactive_in_D2', 'D2 不用；扩容敏感性会用到，但登记表无条目', {'domain': 'grid_econ', 'id': 'grid_reinforcement_wacc'}),
 'grid_start_year': ('L541', 'grid_reinforcement_start_year', 'inactive_in_D2', 'argparse 默认 2030 ≠ 登记值 2031'),
 'capex_electrolyzer': ('L64–65、L75', ['h2_el_capex', 'h2_el_block_kw_basis'], 'covered', '65904 = 120 kJPY/kW × 549.2 kW/块；登记表 h2_el_capex 的 code_now 仍写 63600（530 kW/块），应更新'),
 'capex_fuelcell': ('L64–65、L67、L75', 'h2_fc_capex', 'covered', 'kJPY/kW × UNIT_KW[fuelcell] 10000'),
 'capex_tank': ('L64–65、L75', 'h2_tank_capex', 'covered', 'kJPY/t × 1 t/块'),
 'h2_om_set': ('L131–142（只在 annuity_pv）', 'h2_el_fom', 'inactive_in_D2', 'PLEXOS 方法下静默忽略'),
 'h2_sale_price': ('L341–344', None, 'orphan',
                   'D2 = 0，即氢气不外售（只能回发电）。这是模型边界假设，数值上表现为一个关闭的开关，登记表没有说明',
                   {'domain': 'h2', 'id': 'h2_offsite_sale'}),
 'h2_sale_max_kgph': ('L343', None, 'inactive_in_D2', '只在 h2_sale_price > 0 时使用'),
 'h2_capex_scale': ('L167（只在 annuity_pv）', 'h2_el_capex', 'inactive_in_D2', 'PLEXOS 方法下静默忽略：用 --h2-capex-scale 做造价敏感性在 D2 中无效'),
 'h2_cost_flat_from': ('L161–162（只在 annuity_pv）', None, 'inactive_in_D2', 'PLEXOS 方法下静默忽略'),
 'h2_life': ('L129（只在 tech_life，年金法）', 'h2_el_system_life', 'inactive_in_D2', 'PLEXOS 方法下静默忽略'),
 'tsam_segments': ('L276–282', 'time_resolution', 'covered', 'D2 = 0（逐时）'),
 'unit_scaling': ('L204–205、L430、L679、L696', None, 'numerical', 'hu、bu、BSC 缩放，只改数值条件'),
 'model_fixes': ('L281、L377、L381、L408、L422、L524、L551–556、L560–563、L572–574', ['h2_tank_terminal_condition', 'ev_terminal_condition'], 'covered',
                 '是多项设定的总开关，各子项见本表 model_fixes 条目'),
 'degradation_average': ('L347、L350', 'h2_degradation_method', 'covered', ''),
 'fc_kg_per_mwh': ('L340、L476、L486、L538、L696', 'h2_fc_kg_per_mwh', 'covered', 'argparse 默认 60.6；与 PLEXOS H2 Supply Node Generation Coefficient −60.6 相同'),
 'ev_station_eff': ('L207、L406–408、L419–422、L559–561', 'ev_station_efficiency', 'covered', ''),
 'ev_batt_charge_eff': ('L207、L407、L420', 'ev_battery_charge_efficiency', 'covered', ''),
 'ev_batt_discharge_eff': ('L207、L408、L422、L561', 'ev_battery_discharge_efficiency', 'covered', ''),
 're_fom_jpy_per_kw': ('L166（只在 annuity_pv）', ['re_fom', 'generator_side_kw_charge'], 'inactive_in_D2', 'PLEXOS 方法下静默忽略；风光 FO&M 1000 来自 S*_annuity.json c17'),
 'export_curtail_share': ('L256–268', 'regional_curtailment_rate', 'inactive_in_D2', '即使设为 > 0，只要用 --price-series（df 含 curt_rate），L321 也优先用 curt_rate，curt_flag 被静默忽略'),
 'export_curtail_level': ('L321', 'regional_curtailment_rate', 'inactive_in_D2', '同上'),
 'curtail_wind_weight': ('L264', None, 'inactive_in_D2', '旧弃电代理，--price-series 下不用'),
 'curtail_calendar': ('L265–266', None, 'inactive_in_D2', '旧弃电代理（季节 0.5、周末 1.15）'),
 'price_wind_beta': ('L241–252', None, 'inactive_in_D2', 'D2 = 0。注意帮助文字说 --price-series 取代 beta，但代码在价格序列之后仍会施加 beta（若非 0）'),
 'price_series': ('L228–236', ['price_series', 'regional_curtailment_rate'], 'covered', ''),
 'series_curtail_scale': ('L321', 'export_curtailment_application', 'covered', ''),
 'renewable_profile': ('L222–227', 're_profile_source', 'covered', ''),
 'price_wind_beta_path': ('L241', None, 'inactive_in_D2', ''),
 'price_wind_beta_scale': ('L241', None, 'inactive_in_D2', ''),
 'export_curtail_share_path': ('L256', None, 'inactive_in_D2', ''),
 'export_curtail_share_scale': ('L256', None, 'inactive_in_D2', ''),
 'import_limit_mw': ('L582–583', None, 'inactive_in_D2', ''),
 'self_sufficiency': ('L584–590', None, 'inactive_in_D2', ''),
 'island_days': ('L531–539', None, 'inactive_in_D2', ''),
 'island_load_share': ('L534', None, 'inactive_in_D2', ''),
 'island_start_year': ('L535', None, 'inactive_in_D2', ''),
 'import_adder_jpy_per_kwh': ('L319', 'network_import_adder', 'covered', ''),
 'export_deduction_jpy_per_kwh': ('L321', 'network_export_deduction', 'covered', ''),
 'ev_charger_kw': ('L208、L406–408、L419–422、L559–561', 'ev_charger_power', 'covered', '固定充电曲线脚本 build_fixed_profile.py L19 另写死 0.01 MW，不随本参数变化'),
 'ev_participation': ('L278、L285、L367–374', 'ev_participation', 'covered', ''),
 'ev_departure_soc': ('L379–383', 'ev_departure_soc', 'covered', ''),
 'ev_departure_hour': ('L281、L380–382', 'ev_departure_hour', 'covered', 'model_fixes 下约束放在 06:00 快照'),
 'ev_departure_groups': ('L376、L403、L415', 'ev_departure_groups', 'covered', ''),
 'ev_v2g_efc_cap': ('L566–570、L712–718', 'ev_v2g_efc_cap', 'covered', ''),
 'h2_startup_hours': ('L497–501、L524', 'h2_el_startup_hours', 'covered', ''),
 'fc_startup_hours': ('L497', 'h2_fc_startup_hours', 'covered', ''),
 'el_noload': ('L352、L519–521', 'h2_el_noload', 'covered', ''),
 'el_curve': ('L352、L522–525', 'h2_el_partload_curve', 'covered', ''),
 'el_degradation': ('L346–348', 'h2_el_degradation', 'covered', ''),
 'el_stack_life': ('L347', 'h2_el_stack_life', 'covered', 'D2 = 40 → 寿命平均 age 19.5 年，δ = 1 + 0.0024×19.5 = 1.0468；须与 --h2-stack-repl 的 40 手动保持一致'),
 'fc_degradation': ('L349–351', 'h2_fc_degradation', 'covered', ''),
 'fc_stack_life': ('L350', 'h2_fc_stack_life', 'covered', 'age 4.5 年，δ = 1.027'),
 'el_standby_power': ('L356、L490–494', 'h2_el_standby_power', 'covered', ''),
 'fc_standby_power': ('L356、L490', 'h2_fc_standby_startup', 'covered', ''),
 'el_startup_energy': ('L356、L491、L507', 'h2_el_startup_energy', 'covered', ''),
 'fc_startup_energy': ('L356、L491', 'h2_fc_standby_startup', 'covered', ''),
 'el_availability': ('L473、L475', 'h2_el_availability', 'covered', ''),
 'fc_availability': ('L474、L476', 'h2_fc_availability', 'covered', ''),
 'gurobi_method': ('L648', None, 'numerical', '批处理未设'),
 'gurobi_numeric_focus': ('L650', None, 'numerical', '批处理 make_reg1_batch.py L29 = 1'),
 'gurobi_bar_homogeneous': ('L651', None, 'numerical', '批处理 = 1'),
 'gurobi_crossover': ('L652、L727', None, 'numerical', '未设；决定平衡残差容差 1e-5'),
 'bar_conv_tol': ('L649', None, 'numerical', ''),
 'fix_builds': ('L449–455、L635', 'foresight_robustness', 'inactive_in_D2', ''),
 'fix_before': ('L449–452', 'foresight_robustness', 'inactive_in_D2', ''),
 'no_perpetuity': ('L634 PERP', 'end_treatment', 'covered', 'PRESET_PLEXOS 未设 → PERP = True'),
 'perpetuity': ('L634 PERP', 'end_treatment', 'covered', ''),
 'h2_no_build_from': ('L456–459', None, 'inactive_in_D2', '期末效应检验'),
 'h2_fom': ('L68、L77–80', ['h2_el_fom', 'h2_fc_fom', 'h2_tank_fom'], 'covered',
            '永续 FO&M = 造价 × 份额 / 0.03。登记表 model_entry 仍写"PLEXOS 方法下没有入口"，已过时'),
 'h2_stack_repl': ('L69、L81', ['h2_el_stack_replacement_cost', 'h2_fc_stack_replacement_cost', 'h2_el_stack_life', 'h2_fc_stack_life'], 'covered',
                   '永续换堆现值 = 造价 × 份额 / (1.03^L − 1)。登记表 code_now 仍写"D2 不计"，已过时'),
 'wind_scale': ('L238', 'wind_scale_sensitivity', 'covered', '登记表写"无此参数"，已过时（代码已有）'),
 'extend_to': ('L634 YEND、L43–48、L50–54', ['planning_horizon', 'horizon_extension_2060'], 'covered', ''),
 'output': ('L271、L642', None, 'numerical', '输出路径'),
 'build_only': ('L645', None, 'numerical', ''),
 'preset': ('L634', 'investment_cost_method', 'covered', 'D2 = plexos'),
}
for dest, spec in A.items():
    where, rid, verdict, notes = spec[:4]
    sug = spec[4] if len(spec) > 4 else None
    e = eff[dest]
    origin = e['origin']
    origin = 'preset_plexos' if origin.startswith('preset_plexos') else origin
    v = num(e['d2_value'])
    if dest in ('scenario',):
        v, origin = 'S0–S4（批处理）', 'cli'
    E(f"argparse {e['flag']}", f"model.py L634（定义）；{where}", v, origin, rid, verdict, notes, sug)

# ---------------------------------------------------------------- 2. module constants ---------
E('TECH 对象名与容量属性映射', 'model.py L15–22', 'wind/roof/solar: Max Capacity；fuelcell: Max Capacity；electrolyzer: Max Operating Level；tank: Max Inventory',
  'hardcoded', ['h2_el_block_size', 'h2_fc_block_size', 'h2_tank_block_size', 'new_build_limit_wind'], 'covered', '结构映射，数值来自 S*_parameters.json')
E('OLD_CAPEX', 'model.py L32–34', '原稿氢能造价', 'hardcoded', None, 'inactive_in_D2', '全文件无引用（死代码）')
E('CAPEX（风光造价路径）', 'model.py L101–102', 'wind 293/248/177/127 等', 'hardcoded', ['capex_onshore_wind', 'capex_pv_utility', 'capex_pv_rooftop'], 'inactive_in_D2', '只在年金法；D2 风光造价来自 S*_annuity.json c17')
E('H2_CAPEX（base/low/high/old）', 'model.py L103–107', 'low 与 D2 CLI 相同', 'hardcoded', ['h2_el_capex', 'h2_fc_capex', 'h2_tank_capex'], 'inactive_in_D2', '只在年金法')
E('H2_FOM', 'model.py L108', "low = {el .02, fc .03, tank .005}", 'hardcoded', ['h2_el_fom', 'h2_fc_fom', 'h2_tank_fom'], 'inactive_in_D2', '只在年金法；与 D2 的 --h2-fom 数值重复')
E('H2_LIFE', 'model.py L109', '20/20/30', 'hardcoded', ['h2_el_system_life', 'h2_fc_system_life', 'h2_tank_life'], 'inactive_in_D2', '')
E("UNIT_KW['fuelcell'] = 10000", 'model.py L110；L67 使用', 10000, 'hardcoded', 'h2_fc_block_size', 'covered', 'scale_annuity 中把 kJPY/kW 换成 JPY/块')
E("UNIT_KW['electrolyzer'] = 549.2", 'model.py L110', 549.2, 'hardcoded', 'h2_el_block_kw_basis', 'inactive_in_D2', '只在年金法；D2 的 549.2 隐含在 --capex-electrolyzer 65904 中')
E("UNIT_KW wind/solar/roof/tank", 'model.py L110', '40000/20000/20/1', 'hardcoded', None, 'inactive_in_D2', '只在年金法')
E('PERP（永续开关）', 'model.py L112、L634', True, 'argparse_default', 'end_treatment', 'covered', '')
E('HEND', 'model.py L113、L634', 2050, 'argparse_default', None, 'inactive_in_D2', '只在 vintage_pv 截断分支')
E('YEND', 'model.py L114、L634', 2050, 'argparse_default', 'planning_horizon', 'covered', '')
E('W2050 = 1.03^-(YEND-2025)/0.03', 'model.py L115–116；L298、L579、L678、L716', 15.92, 'hardcoded', ['end_treatment', 'discount_rate'], 'covered', '2050 年运行与持有费的永续权重')
E('annuity_factor()', 'model.py L118–119', None, 'hardcoded', None, 'inactive_in_D2', '只在 grid_pv_per_mw（gmax = 0）')
E('H2_PHYS', 'model.py L121；L338、L339、L345、L434、L662', {'electrolyzer_MW': 2000, 'fuelcell_MW': 500, 'tank_t': 10000}, 'hardcoded', 'h2_physical_caps', 'covered', '')
E('EL_LIFE_PATH', 'model.py L125', {2025: 20, 2030: 25, 2040: 30, 2050: 35}, 'hardcoded', 'h2_el_system_life', 'inactive_in_D2', '')
E('H2_STACK', 'model.py L126', {'electrolyzer': [0.11, 15], 'fuelcell': [0.2, 10]}, 'hardcoded', ['h2_el_stack_replacement_cost', 'h2_fc_stack_replacement_cost'], 'inactive_in_D2',
  '只在年金法；电解槽间隔 15 与 D2 的 40 不一致')
E('H2_FOM_V', 'model.py L127', {'electrolyzer': 0.04, 'fuelcell': 0.04, 'tank': 0.01}, 'hardcoded', ['h2_el_fom', 'h2_fc_fom'], 'inactive_in_D2', '')
E('tech_life 写死寿命（风光 30、fc 20、tank 30）', 'model.py L130、L132', '30/20/30', 'hardcoded', ['re_lifetime', 'h2_fc_system_life', 'h2_tank_life'], 'inactive_in_D2', '只在年金法')
E('s_inf / vintage_pv', 'model.py L144–151', None, 'hardcoded', None, 'inactive_in_D2', '年金法')
E('BSC 建设变量缩放', 'model.py L429–431', {'wind': 40, 'solar': 20, 'roof': 0.02, 'fuelcell': 10, 'electrolyzer': 1, 'tank': 1}, 'hardcoded', None, 'numerical', '')
E('PRESET_NEWBASE', 'model.py L603–620', '整组', 'hardcoded', None, 'inactive_in_D2', 'D2 不载入；其中 el_degradation .006、stack 15、annuity、网费 2/1、no_perpetuity 等与 D2 不同')
E('PRESET_PLEXOS 生效部分', 'model.py L622–631', "investment_method='plexos'", 'preset_plexos', 'investment_cost_method', 'covered', '其余键被 CLI 覆盖或与 CLI 同值（ev_departure_hour 7）')

# ---------------------------------------------------------------- 3. hardcoded in functions ---
H = [
 ('load_annuity：2050 年后造价 ×1.03^-(y-2050)', 'model.py L53', 1.03, None, 'inactive_in_D2', 'YEND = 2050 时不执行'),
 ('scale_annuity：原稿造价 csv 列映射与 old 值', 'model.py L66–67、L75、L83', None, None, 'inactive_in_D2', 'D2 三类氢能设备都给了 --h2-fom，走 L77–82 分支，old 被计算但不使用'),
 ('scale_annuity：造价锚点线性插值，2050 后取 2050', 'model.py L36–37、L75', 'np.interp', 'h2_el_capex', 'covered', '登记表 code_now 给出 2035 年插值结果'),
 ('scale_annuity：造价贴现 d = 1.03^-(y-2025)', 'model.py L76', 1.03, ['discounting_convention', 'discount_rate'], 'covered', ''),
 ('scale_annuity：FO&M 永续 = 份额 × 造价 / 0.03', 'model.py L80', 0.03, ['h2_el_fom', 'discount_rate'], 'covered', '不读 PERP：--no-perpetuity 时仍按永续'),
 ('scale_annuity：换堆永续 = 份额 × 造价 / (1.03^L − 1)', 'model.py L81', 1.03, ['h2_el_stack_replacement_cost', 'discount_rate'], 'covered', '第一次换堆在建设后第 L 年'),
 ('scale_annuity：氢能现值整体替换 PLEXOS 原值', 'model.py L82', None, 'investment_cost_method', 'covered',
  '原稿燃料电池 FO&M 9600 円/kW·年、电解槽 FO&M 20 不再进入 D2。登记表 h2_fc_capex code_now 仍写"另含 320.2 kJPY/kW"，已过时'),
 ('hu = 1e-3（氢 kg→t）', 'model.py L204；L679、L696 重复', 0.001, None, 'numerical', ''),
 ('bu = 1e-3（生物质 GJ→TJ）', 'model.py L205；L679 重复', 0.001, None, 'numerical', ''),
 ('ecap = 0.07 × ev_capacity_scale', 'model.py L206', 0.063, 'ev_battery_nominal_capacity', 'covered', ''),
 ('kw_ev = ev_charger_kw / 1000', 'model.py L208', 0.01, 'ev_charger_power', 'numerical', '单位换算'),
 ('风光曲线按（月,日,时）映射，缺值 interpolate/bfill/ffill', 'model.py L224–227', None, 're_profile_time_mapping', 'covered', ''),
 ('价格序列映射：min(年, ylast)，×1000 JPY/kWh→JPY/MWh', 'model.py L232–236', 'ylast = 2050', ['price_series', 'leap_year_handling'], 'covered', ''),
 ('风光 p_max_pu clip(upper=1)', 'model.py L237–238', 1, None, 'numerical', ''),
 ('beta 价格调整：168 h 窗、min_periods 24、地板 10 JPY/MWh', 'model.py L247–252', None, 'price_floor', 'inactive_in_D2', 'beta = 0'),
 ('旧弃电代理：季节 1/0.5、周末 1.15', 'model.py L264–268', None, None, 'inactive_in_D2', ''),
 ('grid_conditions_by_year.csv 输出', 'model.py L270–274', None, None, 'numerical', '只输出'),
 ('tsam 出发标记 h_dep0', 'model.py L281', None, None, 'inactive_in_D2', ''),
 ('days_per_year 权重 365/366', 'model.py L296', None, None, 'inactive_in_D2', ''),
 ('运行贴现 1.03^-(y-2024)，末年 W2050', 'model.py L297–298', 1.03, ['discount_rate', 'discounting_convention', 'end_treatment'], 'covered', ''),
 ('snapshot_weightings（objective/generators/stores）', 'model.py L301–303', 1, None, 'numerical', ''),
 ('非 EV 负荷 p_set = load_MW', 'model.py L306', None, ['load_annual_trajectory', 'load_hourly_shape'], 'covered', ''),
 ('现有光伏 = 名称含 UtilityPV 或 Namie RooftopPV 的 Units×Max Capacity', 'model.py L310', 103, 'existing_pv_mw', 'covered', ''),
 ('现有风电 = Fukushima Revitalization OnshoreWind', 'model.py L311', 38, 'existing_wind_mw', 'covered', ''),
 ('风光、水电可变成本 = 0（marginal_cost 未设）', 'model.py L314–316', 0, None, 'orphan',
  'PLEXOS 原稿也没有 VO&M。决定弃电无成本、风光先于进口调度。影响小，但属于经济假设',
  {'domain': 'grid_econ', 'id': 're_vom'}),
 ('水电 p_nom（cfg 缺省时 1）', 'model.py L316', 1, 'hydro_ukedo', 'covered', ''),
 ('市场上限缺省 150（cfg Max Purchases/Sales）', 'model.py L317、L320', 150, 'grid_interface_mw', 'inactive_in_D2', '被 --market-limit-mw 118 覆盖'),
 ('进口成本 = 价格 + adder；/1e6 百万円', 'model.py L319', None, ['price_series', 'network_import_adder'], 'covered', ''),
 ('出口 p_max_pu = 1 − curt_rate × scale；收入 = 价格 − deduction', 'model.py L321', None, ['export_curtailment_application', 'network_export_deduction'], 'covered', ''),
 ('生物质库存 e_nom 100000 GJ、初始 10000 GJ、非循环', 'model.py L324', {'e_nom_GJ': 100000, 'e_initial_GJ': 10000}, 'biomass_namie', 'covered', 'e_nom 不起约束（无补给）'),
 ('生物质机组 p_nom 20 GJ/h（2 MW）、效率 0.1 MWh/GJ', 'model.py L325', {'p_nom_GJh': 20, 'eff': 0.1}, 'biomass_namie', 'covered', '与 PLEXOS Namie Biomass Max Capacity 2、Heat Rate 10 同值，但为硬编码'),
 ('生物质燃料出售 p_nom 100000 GJ/h，价格 BiomassMarket', 'model.py L326–331', None, 'biomass_namie', 'covered', '出售能力事实上不限'),
 ('氢罐日损失 → 小时损失换算', 'model.py L335', None, 'h2_tank_standing_loss', 'numerical', ''),
 ('氢能有限上限分支 50000 kg、500×a_el MW、300×fk', 'model.py L336–337', None, 'h2_build_caps', 'inactive_in_D2', '--h2-unlimited 下改用 H2_PHYS'),
 ('氢罐 e_initial = 0、e_cyclic = False', 'model.py L338', 0, 'h2_tank_initial_inventory', 'covered', ''),
 ('电解槽水费 4 JPY/kg：marginal_cost = (4/a_el)/1e6', 'model.py L339', 4, 'h2_el_water_vom', 'covered', '登记表写 L323，现为 L339；与 PLEXOS VO&M Charge 4 同值但为硬编码'),
 ('燃料电池可变成本 = 0（marginal_cost 未设）', 'model.py L345', 0, None, 'orphan',
  'PLEXOS 原稿 FC VO&M Charge = 0。燃料电池放电无可变成本，影响氢储能调度经济性；文献 PEMFC O&M 常按 ct/kWh 计',
  {'domain': 'h2', 'id': 'h2_fc_vom'}),
 ('h2_sale 小时上限缺省 1e5 kg/h', 'model.py L343', 100000, None, 'inactive_in_D2', ''),
 ('老化 age = (stack_life − 1)/2', 'model.py L347、L350', {'el': 19.5, 'fc': 4.5}, 'h2_degradation_method', 'covered', '登记表单位栏仍写电解槽 7 年（对应 stack life 15）'),
 ('电解槽老化效率 hu/(a_el(1+δ·age))', 'model.py L348', 1.0468, 'h2_el_degradation', 'covered', ''),
 ('燃料电池老化效率 1/(fk(1+δ·age))', 'model.py L351', 1.027, 'h2_fc_degradation', 'covered', ''),
 ('el_eff_aux / h2_eff_sink p_nom 1000 MW', 'model.py L354–355', 1000, None, 'numerical', '额外耗电上界；在 2000 MW 链路上限下最大约 236 MW，不起约束'),
 ('h2_aux_power / sink p_nom 500 MW', 'model.py L358–359', 500, None, 'inactive_in_D2', '待机与启动能耗均为 0，不建'),
 ('dep_floor（0.35，max(.35, soc)）', 'model.py L376、L380', 0.35, 'ev_soc_min', 'numerical', '死代码：赋值后从未使用'),
 ('EV 最低电量 0.35 × 0.07 MWh/车（model_fixes 用名义容量）', 'model.py L377', 0.0245, 'ev_soc_min', 'covered', ''),
 ('出发约束快照 = departure_hour − 1（model_fixes）', 'model.py L381–382', 6, 'ev_departure_hour', 'covered', ''),
 ('出发电量 = departure_soc × ecap', 'model.py L383', 0.0504, 'ev_departure_soc', 'covered', ''),
 ('非参与车辆负荷 = (1 − p) × 固定曲线；参与车辆数与行驶 × p', 'model.py L371–374', 0.5, ['ev_participation', 'ev_uncontrolled_charging_profile'], 'covered', ''),
 ('cohort 分支', 'model.py L384–409', None, 'ev_cohort_test', 'inactive_in_D2', ''),
 ('EV Store e_nom = max(车辆数) × ecap', 'model.py L413', None, None, 'numerical', ''),
 ('EV e_initial = 车辆数₀ × ecap × 0.96', 'model.py L415', 0.96, 'ev_initial_soc', 'covered', '与 cfg Max SoC 分别取值'),
 ('EV standing_loss = 0.0005/h', 'model.py L415（cohort 分支 L403）', 0.0005, 'ev_self_discharge', 'covered', ''),
 ('EV e_cyclic = False', 'model.py L415', False, 'ev_terminal_condition', 'covered', ''),
 ('新增车辆带入电量 diff(车辆数) × ecap × 0.96', 'model.py L417', 0.96, 'ev_initial_soc', 'covered', ''),
 ('EV 行驶负荷 = drive_MWh − 新增车辆电量', 'model.py L418', None, 'ev_traction_profile', 'covered', ''),
 ('充电 Link p_nom = max(车辆数)×kw/es，p_max_pu = 车辆比 × 接入率', 'model.py L419–420', None, ['ev_charger_power', 'ev_availability_profile'], 'covered', ''),
 ('放电 Link p_nom = max(车辆数)×kw/ebd（model_fixes）', 'model.py L422', None, 'ev_charger_power', 'covered', ''),
 ('氢能物理上限块数：2000/(10·a_el)、500/10、10000', 'model.py L434', {'electrolyzer': 4071.7, 'fuelcell': 50, 'tank': 10000}, 'h2_physical_caps', 'covered', ''),
 ('年建设上限：风光取 cfg Max Units Built in Year，氢能取物理上限', 'model.py L437', None, ['new_build_limit_wind', 'new_build_limit_pv_utility', 'new_build_limit_pv_rooftop', 'h2_build_caps'], 'covered', ''),
 ('PLEXOS 方法累计装机不退役', 'model.py L446–448', None, ['investment_cost_method', 're_lifetime'], 'covered', ''),
 ('总建设上限', 'model.py L460–463', None, ['new_build_limit_wind', 'h2_build_caps'], 'covered', ''),
 ('投资系数 = ann / 1e6 / bsc', 'model.py L464–465', None, 'investment_cost_method', 'numerical', '单位换算'),
 ('电解槽/燃料电池容量 = 块 × a_el × av；块 × fk × av', 'model.py L473–476', None, ['h2_el_availability', 'h2_fc_availability', 'h2_el_block_kw_basis'], 'covered', '链路口径 491.2 kW/块'),
 ('启动成本权重 ow = 目标权重 / 小时', 'model.py L479、L510', None, 'h2_el_startup_cost', 'inactive_in_D2', '启动成本为 0'),
 ('冷启动：p ≤ u − su/h，p ≥ pmin(u − su/h)', 'model.py L497–504', None, ['h2_el_startup_hours', 'h2_el_min_load'], 'covered', ''),
 ('启动定义 su ≥ warm − warm(t−1)，su ≤ warm', 'model.py L506、L509', None, 'h2_uc_enabled', 'covered', ''),
 ('部分负荷曲线参照容量 = u − su（model_fixes 且 h2_uc）', 'model.py L524', None, 'h2_el_partload_curve', 'covered', ''),
 ('储罐容量 = 块 × 1000 kg × hu', 'model.py L530', None, 'h2_tank_block_size', 'covered', ''),
 ('孤岛约束', 'model.py L531–539', None, None, 'inactive_in_D2', ''),
 ('电网扩容变量与成本', 'model.py L540–550', None, 'grid_reinforcement_max_mw', 'inactive_in_D2', ''),
 ('model_fixes：末年稳态（生物质、氢、EV 按车辆数比）', 'model.py L551–555、L571–573', None, ['h2_tank_terminal_condition', 'ev_terminal_condition', 'biomass_namie'], 'covered', ''),
 ('非 model_fixes 末端：氢回零、居民 EV 回 0.96', 'model.py L556、L574', None, ['h2_tank_terminal_condition', 'ev_terminal_condition'], 'inactive_in_D2', ''),
 ('model_fixes：EV 直流侧共享功率 es·充 + ebd·放 ≤ N·kw·a', 'model.py L560–563', None, 'ev_charger_power', 'covered', ''),
 ('charge_only/fixed 禁止放电', 'model.py L564–565', None, None, 'orphan', '属于 --ev-control 条目（建议 ev_control_regimes）', {'domain': 'ev', 'id': 'ev_control_regimes'}),
 ('生物质期末库存持有费 10 円/GJ·年（含永续）', 'model.py L576–581；账本 L679 重复', 10, 'biomass_namie', 'covered', '与 PLEXOS BioMass Inventory Charge 10 同值，硬编码'),
 ('进口上限、自给率约束', 'model.py L582–590', None, None, 'inactive_in_D2', ''),
 ('水电月度电量上限（GWh × 1000）', 'model.py L591–599', None, 'hydro_ukedo', 'covered', ''),
 ('参数检查 parser.error', 'model.py L635–641', None, None, 'numerical', ''),
 ('physical_cap_check 0.99 判定', 'model.py L661–664', 0.99, 'h2_physical_caps', 'numerical', '只报告'),
 ('账本与平衡检查容差 1e-5/1e-3、max(0.01, 1e-6·obj)', 'model.py L727–731', None, None, 'numerical', '检查不通过会中止输出，但不改解'),
]
for it in H:
    item, where, val, rid, verdict, notes = it[:6]
    sug = it[6] if len(it) > 6 else None
    E(item, where, val, 'hardcoded', rid, verdict, notes, sug)

# ---------------------------------------------------------------- 4. PLEXOS params via param() ---
P = [
 ('NewOnshoreWInd OnshoreWind', 'Max Units Built', 30, 'L308、L312–313、L462', 'new_build_limit_wind', 'covered', ''),
 ('NewOnshoreWInd OnshoreWind', 'Max Units Built in Year', 3, 'L437', 'new_build_limit_wind', 'covered', ''),
 ('NewOnshoreWInd OnshoreWind', 'Max Capacity', 40, 'L312–313、L466', 'new_build_limit_wind', 'covered', ''),
 ('NewUtilityPV UtilityPV', 'Max Units Built', 20, 'L308、L312、L462', 'new_build_limit_pv_utility', 'covered', ''),
 ('NewUtilityPV UtilityPV', 'Max Units Built in Year', 2, 'L437', 'new_build_limit_pv_utility', 'covered', ''),
 ('NewUtilityPV UtilityPV', 'Max Capacity', 20, 'L312、L466', 'new_build_limit_pv_utility', 'covered', ''),
 ('NewRooftopPV RooftopPV', 'Max Units Built', 3000, 'L308、L312、L462', 'new_build_limit_pv_rooftop', 'covered', ''),
 ('NewRooftopPV RooftopPV', 'Max Units Built in Year', 20, 'L437', 'new_build_limit_pv_rooftop', 'covered', ''),
 ('NewRooftopPV RooftopPV', 'Max Capacity', 0.02, 'L312、L466', 'new_build_limit_pv_rooftop', 'covered', ''),
 ('FH2R Fuel Cell Power Station Hydrogen', 'Max Units Built', 30, 'L308（>0 判定）、L462', 'h2_build_caps', 'inactive_in_D2', '只用于判定候选；上限被 H2_PHYS 代替'),
 ('FH2R Fuel Cell Power Station Hydrogen', 'Max Units Built in Year', 10, 'L437', 'h2_build_caps', 'inactive_in_D2', ''),
 ('FH2R Fuel Cell Power Station Hydrogen', 'Max Capacity', 10, 'L466', 'h2_fc_block_size', 'covered', 'MW/块'),
 ('Power to H2 Facility', 'Max Units Built', 50, 'L308、L462', 'h2_build_caps', 'inactive_in_D2', ''),
 ('Power to H2 Facility', 'Max Units Built in Year', 10, 'L437', 'h2_build_caps', 'inactive_in_D2', ''),
 ('Power to H2 Facility', 'Max Operating Level', 10, 'L466', 'h2_el_block_size', 'covered', 'kg/h/块'),
 ('H2 Storage Tank', 'Max Units Built', 50, 'L308、L462', 'h2_build_caps', 'inactive_in_D2', ''),
 ('H2 Storage Tank', 'Max Units Built in Year', 4, 'L437', 'h2_build_caps', 'inactive_in_D2', ''),
 ('H2 Storage Tank', 'Max Inventory', 1000, 'L466、L530', 'h2_tank_block_size', 'covered', 'kg/块'),
 ('FH2R UtilityPV / Namie Sakai Solar No1/No2 UtilityPV / Namie Yatsuda Revitalization UtilityPV / Namie RooftopPV', 'Units × Max Capacity', '20+20+16+38+9 = 103', 'L310', 'existing_pv_mw', 'covered', ''),
 ('Fukushima Revitalization OnshoreWind', 'Max Capacity × Units', 38, 'L311', 'existing_wind_mw', 'covered', ''),
 ('Ukedo Gawa Hydro', 'Max Capacity', 1, 'L316', 'hydro_ukedo', 'covered', ''),
 ('TohokuPowerMarket', 'Max Purchases', 150, 'L317', 'grid_interface_mw', 'inactive_in_D2', '被 --market-limit-mw 118 覆盖'),
 ('TohokuPowerMarket', 'Max Sales', 150, 'L320', 'grid_interface_mw', 'inactive_in_D2', '同上'),
 ('EV JR Namie Commercial Area', 'Max SoC', 96, 'L394、L414', 'ev_soc_max', 'covered', ''),
 ('EV Residential Cars', 'Max SoC', 96, 'L394、L414', 'ev_soc_max', 'covered', ''),
 ("'EV Residential Cars' / 'H2 Storage Tank' 是否存在", '对象存在性', 'S3/S4 有 EV；S2/S4 有氢', 'L307', None, 'orphan', '情景开关，归入 scenario_design', {'domain': 'grid_econ', 'id': 'scenario_design'}),
]
for it in P:
    obj, key, val, where, rid, verdict, notes = it[:7]
    sug = it[7] if len(it) > 7 else None
    E(f"param: {obj} / {key}", f"model.py {where}；inputs/S*_parameters.json", val, 'plexos_param', rid, verdict, notes, sug)

# PLEXOS properties duplicated by hard-coded numbers (not read by param()).
NR = [
 ('EV * / Capacity 70 kWh', 70, 'model.py L206、L377 写死 0.07', 'ev_battery_nominal_capacity'),
 ('EV * / Min SoC 35 %', 35, 'model.py L377 写死 0.35', 'ev_soc_min'),
 ('EV * / Initial SoC 96 %', 96, 'model.py L415、L417 写死 0.96', 'ev_initial_soc'),
 ('EV * / Self Discharge Rate 0.05 %/h', 0.05, 'model.py L415 写死 0.0005', 'ev_self_discharge'),
 ('EV * / Max Charge Rate 10 kW', 10, '--ev-charger-kw 默认 10', 'ev_charger_power'),
 ('EV * / Efficiency 200 Wh/km', 200, 'prepare_inputs.py L71 写死 0.0002', 'ev_energy_per_km'),
 ('Power to H2 Facility / VO&M Charge 4', 4, 'model.py L339 写死 4', 'h2_el_water_vom'),
 ('Electricity / Conversion Factor 0.053', 0.053, '--h2-electrolysis-mwh-per-kg（D2 0.04912）', 'h2_el_sec_reference_53'),
 ('H2 Supply Node / Generation Coefficient −60.6', -60.6, '--fc-kg-per-mwh 默认 60.6', 'h2_fc_kg_per_mwh'),
 ('Namie Biomass / Max Capacity 2、Heat Rate 10', '2 MW / 10 GJ/MWh', 'model.py L325 写死', 'biomass_namie'),
 ('BioMass / Max Inventory 100、Opening Inventory 10、Inventory Charge 10', '100 / 10 / 10', 'model.py L324、L579 写死（×1000 解释为 GJ）', 'biomass_namie'),
 ('FH2R Fuel Cell / FO&M Charge 9600、Power to H2 Facility / FO&M Charge 20', '9600 / 20', 'D2 中被 --h2-fom 取代（L82）', 'h2_fc_fom'),
]
for item, val, where, rid in NR:
    E(f"PLEXOS 属性未经 param() 读取：{item}", f"{where}；inputs/S4_parameters.json", val, 'plexos_param', rid, 'covered', '同一数值另以硬编码或 CLI 进入模型，二者独立')

# ---------------------------------------------------------------- 5. input files ---------------
F = [
 ('inputs/S*_annuity.json：风光对象 pv_per_unit（PLEXOS 诊断 c17）', 'model.py L50–54、L210、L464；prepare_inputs.py L42', 'PV/块（JPY）', ['capex_onshore_wind', 'capex_pv_utility', 'capex_pv_rooftop', 're_fom', 'wacc_build_cost'], 'covered', '含造价贴现与 FO&M 永续'),
 ('inputs/S*_annuity.json：氢能对象 pv_per_unit', 'model.py L72、L82', None, 'investment_cost_method', 'inactive_in_D2', '被 scale_annuity 新值整体替换'),
 ('inputs/h2_buildcost_original_plexos.csv', 'model.py L66、L75', None, 'investment_cost_method', 'inactive_in_D2', '读入但 old 不用'),
 ('inputs/profiles.parquet：load_MW', 'model.py L212、L306、L534、L589', None, ['load_annual_trajectory', 'load_hourly_shape'], 'covered', ''),
 ('inputs/profiles.parquet：price_JPY_MWh', 'model.py L212、L236', None, 'price_series', 'inactive_in_D2', '被 --price-series 覆盖'),
 ('inputs/profiles.parquet：solar_pu、wind_pu', 'model.py L212、L226', None, 're_profile_source', 'inactive_in_D2', '被 --renewable-profile 逐时覆盖'),
 ('inputs/profiles.parquet：commercial/residential_vehicles', 'model.py L374、L413；prepare_inputs.py L66、L70', None, ['ev_fleet_count_commercial', 'ev_fleet_count_residential'], 'covered', '按年阶梯（reindex 年份）'),
 ('inputs/profiles.parquet：commercial/residential_drive_MWh', 'model.py L374、L418；prepare_inputs.py L67、L71', None, ['ev_traction_profile', 'ev_energy_per_km'], 'covered', ''),
 ('inputs/profiles.parquet：commercial/residential_availability', 'model.py L255、L419、L558；prepare_inputs.py L68、L72', None, 'ev_availability_profile', 'covered', '两车队都用商业区 CS 列'),
 ('inputs/namie_renewables_ninja_2024.parquet：solar_pu、wind_pu', 'model.py L224–227', None, ['re_profile_source', 'pv_profile_spec', 'wind_profile_spec', 're_profile_time_mapping'], 'covered', '起点 2024-01-01 09:00，前 9 h 回卷补齐'),
 ('inputs/tohoku_price_plan_ref2024.parquet：price、curtail_rate', 'model.py L231–236、L321', None, ['price_series', 'regional_curtailment_rate'], 'covered', '年份 2025–2050'),
 ('inputs/fixed_fleet_charging_newbase.parquet：commercial/residential_grid_charge_MW', 'model.py L279、L286–290、L365、L371', None, 'ev_uncontrolled_charging_profile', 'covered', '其余 8 列不读'),
 ('inputs/historical_s4/DataFiles/Hydrogen_Biomass_Market_Benchmark_Price_yearly.csv：BiomassMarket', 'model.py L326–331', '2025 22.9 … 2050 33.3 円/GJ', 'biomass_namie', 'covered', ''),
 ('inputs/hydro_monthly.parquet：hydro_GWh', 'model.py L591–599；prepare_inputs.py L76–81', None, 'hydro_ukedo', 'covered', 'PLEXOS 变化点序列按月 ffill'),
 ('inputs/S*_parameters.json（整体）', 'model.py L209', None, None, 'covered', '各属性见 plexos_param 条目'),
]
for item, where, val, rid, verdict, notes in F:
    E(item, where, val, 'input_file', rid, verdict, notes)

PI = [
 ('prepare_inputs：负荷 = 有 Load 文件的对象之和', 'prepare_inputs.py L58–60', None, 'load_annual_trajectory', 'covered', ''),
 ('prepare_inputs：RF 百分数 /100，2 月 29 日回退 2 月 28 日', 'prepare_inputs.py L62–65', None, 're_profile_source', 'inactive_in_D2', 'D2 风光被 ninja 覆盖'),
 ('prepare_inputs：行驶耗电 0.0002 MWh/km', 'prepare_inputs.py L71', 0.0002, 'ev_energy_per_km', 'covered', ''),
 ('prepare_inputs：两车队接入率都取 ~CS_JR Namie Commercial Area', 'prepare_inputs.py L72', None, 'ev_availability_profile', 'covered', ''),
 ('prepare_inputs：水电变化点 ffill', 'prepare_inputs.py L76–79', None, 'hydro_ukedo', 'covered', ''),
 ('build_fixed_profile.py 常数 0.07/0.01/0.96/0.35/0.0005', 'revision_round1/03_analysis/fixed_fleet_charging/build_fixed_profile.py L18–22', None,
  ['ev_battery_nominal_capacity', 'ev_charger_power', 'ev_initial_soc', 'ev_soc_min', 'ev_self_discharge'], 'covered', '与 model.py 同值；CHARGER_MW_PER_EV 不随 --ev-charger-kw 变化'),
 ('build_fixed_profile.py newbase 预设 soh 0.9、桩 0.93、电池 0.98', 'build_fixed_profile.py L32', None, ['ev_soh_capacity_scale', 'ev_station_efficiency', 'ev_battery_charge_efficiency'], 'covered', '已复算确认 D2 所用 parquet 由此预设生成'),
 ('build_fixed_profile.py 模块常数 0.90/0.95', 'build_fixed_profile.py L23–27', None, None, 'numerical', '未被使用（P 预设覆盖），易误读'),
 ('build_fixed_profile.py 出发 SoC 0.6（只用于校核）', 'build_fixed_profile.py L32、L83', 0.6, 'ev_departure_soc', 'inactive_in_D2', '不影响曲线'),
]
for item, where, val, rid, verdict, notes in PI:
    E(item, where, val, 'input_file' if 'prepare' in item else 'hardcoded', rid, verdict, notes)

out = ROOT / 'params' / 'mapping' / 'code_inventory.yaml'
header = ('# D2 反向盘点：模型代码中影响结果的数值来源 → 参数登记表\n'
          '# 由 params/mapping/scripts/inventory/build_inventory.py 生成（只读脚本，2026-10-28）。\n'
          '# 行号指 src/model.py（738 行），另注明的除外。D2 = --preset plexos + src/default_D2_args.txt；\n'
          '# 求解器设置来自 src/make_reg1_batch.py L29。\n')
out.write_text(header + yaml.safe_dump(items, allow_unicode=True, sort_keys=False, width=200), encoding='utf-8')
c = Counter(i['verdict'] for i in items)
print(len(items), dict(c))
for i in items:
    if i['verdict'] == 'orphan':
        print('ORPHAN', i['item'], i.get('suggest'))
