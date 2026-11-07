# 氢能参数登记表与模型代码的对应核查（D2）

- 日期：2026-10-28
- 依据：`params/h2.yaml`（48 条）
- 代码：`src/model.py`（739 行；与 bigmem 上的 model_reg1.py 相同）
- 运行参数：`src/default_D2_args.txt`
- 逐条映射：`params/mapping/h2_map.yaml`
- 计算脚本：`params/mapping/scripts/h2/check_h2_map.py`，结果写入同目录的 `h2_map_results.json`

## 1. 方法

脚本用 ast 从 model.py 中读出 `main()` 的全部 `add_argument` 调用，重建参数解析器，然后按 model.py L634 的顺序取值：先取 argparse 默认值，再用 PRESET_PLEXOS 覆盖，最后用 D2 命令行覆盖。这样得到的参数与实际运行时完全相同。

`scale_annuity`、`parse_kv`、`_interp` 和相关常数（TECH、UNIT_KW、H2_PHYS、PRESET_PLEXOS）直接取自 model.py 源码执行。脚本不 `import model`，也不建立模型。

在此基础上，每条参数都从输入文件（S2_annuity.json、S2_parameters.json、h2_buildcost_original_plexos.csv）和 D2 参数出发，按代码公式算出实际生效值，再与登记表比较。具体做法如下：

- **成本项**：逐年（2025–2050）比较。FO&M 和换堆分开反算：先关掉其中一项，再用 PV/d/造价 − 1 求出另一项的份额。
- **电耗**：按约束 L519–525 和效率 L348 计算各负荷率下的 SEC。
- **其他项**：核对解析后的参数值，以及它在约束中的作用对象。

脚本运行结果：48 条全部覆盖。三种设备在 2025–2050 年的全额单位成本（造价 + FO&M + 换堆）均与登记表一致，共 0 处偏差。`params/check_h2_costs.py` 的复跑结果也是 all match。

## 2. 判定统计

| 判定 | 条数 | 条目 |
|---|---|---|
| match | 43 | 其余全部 |
| mismatch | 1 | h2_el_water_vom |
| doc_only | 4 | h2_el_system_life、h2_fc_system_life、h2_tank_life、h2_el_sec_reference_53 |
| not_in_code | 0 | — |
| cannot_verify | 0 | — |

## 3. 非 match 项

### 3.1 mismatch：h2_el_water_vom（水费 4 円/kg）

代码在 L339 写的是 `marginal_cost = (4/a_el)/1e6`，即按每 MWh 链路输入收 81.43 円。老化（L348）使每 kg 氢的耗电增加到 a_el·δ_el，所以按实际产出的每 kg 氢计，水费是 4 × 1.0468 = **4.19 円/kg**，比登记值高 0.19 円/kg（+4.7 %）。

- **影响**：可以忽略。多计部分约为电解槽水费总额的 4.5 %。
- **建议**：如果要严格等于 4 円/kg，把该行改为 `4/(a_el·δ_el)`；否则在登记表 notes 中说明"按未老化电耗换算"。另外，登记表中的行号 L323 应改为 L339。

### 3.2 doc_only：系统寿命（电解槽 20/25/30/35、燃料电池 20、储罐 30）

D2 用 PLEXOS 方法（`investment_method = plexos`）。`scale_annuity` 不含寿命，装机只累加不退役（L446–448），所以三项寿命都不进入 D2。这与登记表的决定一致。

但有一处需要作者注意。登记表把决定写成"正文写明寿命在期内不起作用"，这个说法只在原稿的 30 年寿命下成立。按登记表的新寿命：

- 2025–2027 年建成的电解槽，在 2050 年前已到寿命；
- 2025–2030 年建成的燃料电池，在 2050 年前已到寿命。

模型却让这些设备免费服役到 2050 年并永续。燃料电池每 10 年 20 % 的换堆已经计入，但系统更换没有计入。这个问题是否实际影响结果，取决于 D2 在 2030 年以前有没有建氢能设备。该算例的建设结果不在本地，本次未核对。

建议从以下两种做法中选一种：

1. 正文改写为"PLEXOS 方法不计期内的系统更换"，并给出早期建设量；
2. 在 `scale_annuity` 中加入系统更换的永续项 `nv/(1.03^L − 1)`。

### 3.3 doc_only：h2_el_sec_reference_53

53 kWh/kg 只是推导 a_lin = 47.12 的依据。PRESET_PLEXOS 中的 0.053 已被 D2 覆盖，不需要处理。

## 4. 数值一致、但登记表文字过时或口径需注意的项

以下各项的数值都判为 match，问题在登记表的文字或口径，建议在下一版 h2.yaml 中更新。

1. **两处造价与电耗记录仍是旧值。**
   - h2_el_capex 的 unit/notes/code_now、h2_el_block_kw_basis 的 code_now，仍写"按 530 kW/块，63,600 kJPY"。实际 D2 为 549.2 kW/块，即 65,904 / 28,558.4 / 21,968 / 16,476 kJPY/块。
   - D2_模型设定.md §2 中的命令行也还是旧版。§1 中的"老化 0.6 %/年"和"49.12 含压缩与辅机"同样需要更新。
2. **多条 code_now 仍描述加入 --h2-fom/--h2-stack-repl 之前的状态。** 涉及 h2_el_fom、h2_fc_fom、h2_tank_fom、h2_el_stack_life、h2_el_stack_replacement_cost、h2_fc_stack_replacement_cost、h2_el_degradation。例如"PLEXOS 方法下没有入口""--el-stack-life 15""δ = 1.042""原稿 FO&M 320.2 kJPY/kW 仍计入"等，均已不符合现状。
3. **老化系数需要更新。**
   - 电堆寿命改为 40 年后，平均年龄从 7 年变为 19.5 年，δ_el 从 1.042 增大到 **1.0468**。
   - 需要更新的地方：h2_degradation_method 的 unit（"电解槽 7 年"）、h2_el_sec_basis 的老化敏感性（54.11/57.23 应为 **54.36/57.49** kWh/kg）、h2_el_compression_energy 的 notes（4.2 % 应为 4.68 %）。
   - h2_el_degradation 的 notes 说寿命平均系数"应为 1.017–1.033"，但新设定反而更大。这在按小时计时是自洽的（80,000 h × 0.12 %/1,000 h ÷ 2 = 4.8 %），只是正文的表述需要相应更新。
4. **燃料电池可用率的口径。** 0.95 作用于氢输入容量（L476），而老化不进容量，所以每 MW 装机的最大电出力是 0.95/1.027 = **0.925 MW**。如果本意是电出力降额 5 %，应在容量中除以 δ_fc；否则正文要写明这一口径。
5. **电解槽实际产氢能力。** 名义 10 kg/h/块，可用率和老化之后为 9.27 kg/h/块。正文报告产能时应说明用的是哪一种口径。
6. **行号已变。** 登记表中的 L322（初始库存）、L323（水费）、L535–539（期末条件）分别应为 L338、L339、L551–556。文件头写的"722 行版本"应为 739 行。
7. **燃料电池耗氢依赖默认值。** 60.6 kg/MWh 取自 argparse 默认值，PRESET_PLEXOS 和 D2 都没有设置。建议写入 D2 参数文件，以免默认值改动后结果随之改变。
8. **电解槽 MW 的报告口径。** model.py 的 summary 不输出电解槽 MW。登记表说"summary 中 el_MW 按 549.2 kW/块报告"，实际应在后处理脚本中，本次未核对。

## 5. 适合写进自动核对脚本的检查项

`check_h2_map.py` 已实现以下各项，可以作为回归检查，每次改代码或改 D2 后运行：

1. **参数解析**：从 model.py 源码重建解析器，按"argparse 默认 → PRESET_PLEXOS → D2"的顺序得到 args，不手抄默认值。
2. **造价**：D2 的 `--capex-*` 经 parse_kv 和 _interp 处理，除以块容量（电解槽 549.2 kW，燃料电池 10,000 kW，储罐 1,000 kg）后，与登记表逐年比较，相对误差 < 1e-6。
3. **FO&M**：在 scale_annuity 中关掉换堆，(PV/d/造价 − 1)×0.03 应等于登记 FOM，逐年、逐设备核对。
4. **换堆**：在 scale_annuity 中关掉 FO&M，PV/d/造价 − 1 应等于 share/(1.03^L − 1)。同时核对换堆间隔等于 `--el-stack-life`/`--fc-stack-life`，使老化与换堆口径一致。
5. **全额单位成本**：与 check_h2_costs.py 相同，统计偏差的设备-年数，应为 0。
6. **电耗链**：a_el×1000 = 登记线性系数；满负荷系数 1 + noload + max s_j(1 − b_j) = 1.1181；分段斜率换成 kWh/kg 后为 5.19/4.82；两段交点 x = 0.70；SEC(1.0) = 54.92；老化后的 SEC 与登记表敏感性一致（目前不一致，见 §4 第 3 条）。
7. **块容量**：10 × a_el × F = 549.2 kW，并且与 D2 造价换算所用的 kW 相同。
8. **老化**：δ_el、δ_fc 按 (L − 1)/2 计算，与登记表 unit 中写的平均年龄一致。
9. **水费**：4 × δ_el 与登记值比较（目前为 mismatch）。
10. **期限与寿命**：当 investment_method = plexos 时，列出 2050 年前已到登记寿命的建设年份，并与结果中的 annual_build 交叉检查，确认这些年份的建设量为 0 或已在正文说明。
11. **上限**：H2_PHYS 与登记一致；`--h2-unlimited` 为真；el_eff_aux 的 p_nom（1,000 MW）大于满上限时的附加耗电（约 229 MW）；结果中 physical_cap_check 的 binding 均为 false。
12. **硬编码项**：在源码中确认 `e_initial=0`、`hydrogen_steady_final_year`、`marginal_cost=(4/a_el)` 存在；储氢初始库存与 S2_parameters.json 中的 Opening Inventory 一致。
13. **覆盖率**：登记表 id 集合与映射 id 集合相同，没有遗漏或多余。
