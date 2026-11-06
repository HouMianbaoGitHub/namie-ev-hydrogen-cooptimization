# D2 反向盘点：代码中的数值来源与参数登记表的对应

2026-10-28。逐条清单见 `code_inventory.yaml`（281 条），由 `scripts/inventory/build_inventory.py` 生成；D2 实际生效的 argparse 取值由 `scripts/inventory/effective_args.py` 用 ast 解析 `model.py` 后，按“argparse 默认值 → PRESET_PLEXOS → `default_D2_args.txt`”的顺序算出，结果在 `effective_args.json`。两个脚本都是只读的，没有 import model，也没有运行模型。行号均指 `src/model.py`（738 行），另注明的除外。

盘点范围包括：argparse 的全部 116 个参数；模块级常数；函数体内写死的数字；`param(cfg, …)` 读取的 PLEXOS 属性，以及 PLEXOS 中虽未经 `param()` 读取、但另以硬编码进入模型的同值属性；模型读取的每个输入文件及列；`prepare_inputs.py` 和固定充电曲线脚本 `build_fixed_profile.py` 中的常数。求解器设置不在 `default_D2_args.txt` 中，取自 `src/make_reg1_batch.py` L29。

## 1. 统计

| 判定 | 条数 |
|---|---|
| covered（登记表有对应） | 164 |
| inactive_in_D2（D2 中不起作用） | 82 |
| numerical（纯数值、单位或求解设置） | 28 |
| orphan（影响 D2，但登记表没有） | 7 条，归并后为 5 个概念 |
| 合计 | 281 |

按来源统计：hardcoded 103 条，argparse_default 74 条，cli 44 条，plexos_param 38 条，input_file 20 条，preset_plexos 2 条。PRESET_PLEXOS 中实际生效的只有 `investment_method='plexos'`，其余键都被命令行覆盖，或与命令行取值相同（`ev_departure_hour=7`）。

总体来看，登记表对物理和经济参数的覆盖相当完整。游离参数集中在两类：一类是情景和控制方式这样的“开关”，另一类是“取 0 所以没写”的可变成本。

## 2. 游离参数（orphan），按影响大小排序

| 序 | 内容 | 位置 | D2 取值 | 影响 | 建议 |
|---|---|---|---|---|---|
| 1 | EV 控制方式 `--ev-control`（含 charge_only/fixed 时禁止放电） | L634 定义；L278、L285、L361、L367、L564–565 | C 组取 argparse 默认 `bidirectional`；A 组 `fixed`、B 组 `charge_only` 由 make_reg1_batch.py L17–18 指定 | 决定是否允许 V2G，也就决定了 EV 的全部系统价值。登记表有 V2G 成本、参与率、出发约束，却没有“控制方式”本身。C 组依赖的是 argparse 默认值，没有显式写入 | 补，**ev**，`ev_control_regimes`（A = 固定曲线、B = 只充电、C = 双向；写明 C 依赖默认值） |
| 2 | 情景定义 `--scenario` S0–S4（以及 cfg 中有无 EV/H2 对象、哪些对象可扩建） | L209、L307–308 | S0/S1/S2/S3/S4，由批处理设定 | 决定参与优化的技术集合，是所有结果的前提 | 补，**grid_econ**，`scenario_design`（列出 S0–S4 的技术集合，以及与 A/B/C 的组合） |
| 3 | 氢气不外售（`--h2-sale-price 0`） | L341–344 | 0（关闭） | 模型边界假设：氢只能回发电。数值上只是一个关闭的开关，但它限定了氢储能价值的来源 | 补，**h2**，`h2_offsite_sale`（值为“不外售”，附代码入口） |
| 4 | 燃料电池可变运维 = 0（Link 未设 marginal_cost） | L345 | 0（PLEXOS 原稿 VO&M Charge 也是 0） | 燃料电池放电没有可变成本，会使氢回发电的调度略偏乐观。电解槽有水费 4 円/kg（`h2_el_water_vom`），燃料电池却没有对应条目 | 补，**h2**，`h2_fc_vom`（采用 0，注明来源为原稿） |
| 5 | 风光与水电可变成本 = 0 | L314–316 | 0 | 弃电无成本，风光总是先于进口调度。影响小，但属于经济假设 | 补，**grid_econ**，`re_vom`（采用 0） |

另有一项登记表缺失、但 D2 中不起作用的参数：`--grid-wacc`（argparse 默认 0.03，L96）。接口扩容敏感性会用到它，建议补为 **grid_econ** `grid_reinforcement_wacc`。

## 3. D2 中被静默忽略的参数

这些参数可以在命令行中设置，程序不报错，但在 D2（PLEXOS 投资方法，`--h2-unlimited`，`--price-series`）下对结果没有作用。

**只在年金法中起作用（PLEXOS 方法下忽略）**

- `--h2-capex`、`--h2-capex-scale`：L167。用 `--h2-capex-scale` 做造价敏感性，在 D2 中没有任何效果；D2 的造价只能通过 `--capex-*` 修改。
- `--h2-om-set`、`--h2-life`、`--h2-cost-flat-from`：L129–142、L161–162。
- `--wacc`：L155。D2 的 3% 来自各处写死的 1.03（见第 4 节），改 `--wacc` 不会改变 D2 的贴现。
- `--re-fom-jpy-per-kw`：L166。D2 风光的 FO&M 1000 円/kW·年来自 `S*_annuity.json` c17。

**被其他参数覆盖**

- `--h2-availability`：被 `--el-availability 0.97`、`--fc-availability 0.95` 覆盖（L473–474）。
- `--h2-limit-scale`、`--h2-annual-unlimited`、`--h2-total-unlimited`：在 `--h2-unlimited` 下不起作用；PLEXOS 的氢能 Max Units Built 50/30/50 和 Max Units Built in Year 10/10/4 也只用于判定候选技术（L308）。
- PLEXOS `TohokuPowerMarket` 的 Max Purchases/Max Sales 150：被 `--market-limit-mw 118` 覆盖（L317、L320）。
- `--export-curtail-share`、`--export-curtail-level`、`--export-curtail-share-path/-scale`、`--curtail-wind-weight`、`--curtail-calendar`：只要用了 `--price-series`（df 中有 curt_rate），L321 就优先使用 curt_rate。即使把这些参数设为非零，也会被静默忽略。
- `profiles.parquet` 的 `price_JPY_MWh`、`solar_pu`、`wind_pu` 三列：分别被价格序列和 ninja 曲线整列覆盖。

**条件未满足**

- `--grid-capex-jpy-per-kw`、`--grid-fom`、`--grid-life`、`--grid-wacc`、`--grid-start-year`：在 `gmax = 0` 时都不使用。需要注意的是，在 `--preset plexos` 上做扩容敏感性时，如果不显式给出这些参数，argparse 默认值是造价 0（扩容免费）、FO&M 0.01、寿命 40、起始年 2030，与登记值 105000 / 0.019 / 28 / 2031 都不同。
- `--ev-cohort-theta`（`ev_cohorts = 1`）、`--h2-sale-max-kgph`、`--continuous`（无操作）。

**与帮助文字不一致**

- `--price-wind-beta`：帮助文字说 `--price-series` 会取代 beta，但 L241–252 在价格序列之后仍会施加 beta（只要它非零）。D2 中取 0，不受影响。
- `--no-perpetuity`：scale_annuity 不读 PERP，所以氢能的 FO&M 和换堆仍按永续计（L80–81）。登记表 `end_treatment_robustness` 已有说明。

## 4. 多处写死、可能不一致的数字

| 数字 | 出现位置 | 现状 |
|---|---|---|
| 折现率 3% | model.py 写死 1.03 或 0.03 共 13 处：L53、L76、L80、L81、L116、L119、L145、L149–150、L297、L579、L678、L716；另有 `--wacc` 默认 0.03（只用于年金法）、`--grid-wacc` 默认 0.03，以及 `S*_annuity.json` c17 中 PLEXOS 隐含的 3% | 目前数值一致，但没有统一入口，改 `--wacc` 不会影响 D2。建议收成一个常数 |
| 电解槽每块电功率 | 链路口径 491.2 kW（10 × 49.12，L434、L475）；满负荷口径 549.2 kW（UNIT_KW L110，`--capex-electrolyzer` 65904 = 120 × 549.2）；登记表 `h2_el_capex` 的单位与 code_now 仍写 530 kW / 63600 | 代码与 D2 参数一致（按 549.2）；登记表文字已过时 |
| 电解槽换堆间隔 | `--el-stack-life 40`（老化）、`--h2-stack-repl …:40`（成本）、H2_STACK L126 = 15（年金法）、PRESET_NEWBASE 15 | D2 中两个 40 需要手动保持一致；15 的两处不影响 D2 |
| EV 0.96 | model.py L403、L404、L415、L417、L574 写死；e_max 取 cfg Max SoC 96（L394、L414）；build_fixed_profile.py L20；PLEXOS Initial SoC 96 | 值一致。但改 `--ev-max-soc` 只会改上限，不会改初始和新增车辆带入的 0.96；若设为低于 0.96，第一小时即不可行 |
| EV 0.35 | L377（有效）；L376、L380 的 dep_floor 是死代码；build_fixed_profile.py L21；PLEXOS Min SoC 35 | 一致；dep_floor 建议删除 |
| EV 0.07 MWh | L206、L377（model_fixes 下用名义容量）；build_fixed_profile.py L18、L31–32；PLEXOS Capacity 70 | 一致 |
| 自放电 0.0005/h | L403、L415；build_fixed_profile.py L22；PLEXOS Self Discharge Rate 0.05 %/h | 一致 |
| 充电功率 10 kW | `--ev-charger-kw` 默认 10（L208）；build_fixed_profile.py L19 写死 0.01 MW；PLEXOS Max Charge Rate 10 | 一致。但改 `--ev-charger-kw` 时，非参与部分的固定曲线不会随之改变 |
| EV 充电效率 | D2 CLI 0.93/0.98；build_fixed_profile.py PRESETS newbase 0.93/0.98（实际使用）；同文件模块常数 0.90/0.95（L23–27，未使用） | 已用 newbase 参数逐时复算 `fixed_fleet_charging_newbase.parquet` 前 500 h，误差为 0，确认一致。未使用的常数容易误读 |
| 出发 SoC | D2 0.8；build_fixed_profile.py newbase 0.6（只用于校核） | 不影响曲线，登记表已注明 |
| 生物质 | L324–325 写死 100000/10000 GJ、20 GJ/h、0.1；PLEXOS BioMass 100/10、Namie Biomass 2 MW、Heat Rate 10 | 等值（PLEXOS 库存 ×1000 解释为 GJ），但代码不读 cfg |
| 持有费 10 円/GJ | L579（目标函数）、L679（账本）；PLEXOS Inventory Charge 10 | 一致 |
| 水费 4 円/kg | L339 写死；PLEXOS VO&M Charge 4 | 一致；登记表写 L323，现为 L339 |
| 电解耗电 | D2 CLI 0.04912；argparse 默认与 PRESET_PLEXOS 0.053；PLEXOS Conversion Factor 0.053 | D2 由 CLI 决定 |
| 单位缩放 1e-3 | L204–205、L679、L696 分别写出 | 一致 |

## 5. model_fixes 包含的各项（D2 中开启）

`--model-fixes` 是一个总开关。登记表只在 `h2_tank_terminal_condition`、`ev_terminal_condition` 两处提到它，各子项分散在不同条目中，但都有覆盖：

1. EV 最低电量按名义容量 0.07 计（L377）：`ev_soc_min`
2. 出发约束放在 departure_hour − 1 的快照（L381）：`ev_departure_hour`
3. 放电 Link 的 p_nom 按 kw/ebd，即直流侧计量（L408、L422）：`ev_charger_power`
4. 共享功率约束 es·充 + ebd·放 ≤ N·kw·a（L560–561）：`ev_charger_power`
5. 部分负荷曲线以 u − su 为参照（L524）：`h2_el_partload_curve`
6. 末年稳态：生物质、氢、EV 按车辆数比（L551–555、L571–573）：`biomass_namie`、`h2_tank_terminal_condition`、`ev_terminal_condition`
7. tsam 出发标记前移（L281）：D2 中不起作用

## 6. 顺带发现：登记表中已过时的 code_now 和 model_entry

这一节不属于反向盘点，留给正向核查参考。

- `h2_el_fom`、`h2_fc_fom`、`h2_tank_fom` 的 model_entry 写“PLEXOS 方法下没有入口”，但 D2 已通过 `--h2-fom` 进入 scale_annuity（L77–80）。
- `h2_el_stack_replacement_cost`、`h2_fc_stack_replacement_cost` 的 code_now 写“D2 不计”，但 D2 已通过 `--h2-stack-repl` 计入（L81）。
- `h2_fc_capex` 的 code_now 写“另含原稿 FO&M 永续现值 320.2 kJPY/kW”。实际上 L82 已把 PLEXOS 现值整体替换，原稿 9600 円/kW·年不再进入。
- `h2_el_capex` 的 code_now 写 63600（530 kW），D2 实际为 65904（549.2 kW）。
- `h2_el_degradation`、`h2_el_stack_life`、`h2_degradation_method` 的 code_now 仍是 0.006、15 年、age 7；D2 实际为 0.0024、40 年、age 19.5，δ = 1.0468。
- `wind_scale_sensitivity` 写“无此参数”，但代码已有 `--wind-scale`（L238）。
- 登记表多处行号对应的是旧版 722 行的 model.py。

## 7. 运行设定提示

`default_D2_args.txt` 不含求解器设定。如果只用它来运行，会得到 HiGHS、120 s 时间上限（argparse 默认）。D2 的实际结果来自 make_reg1_batch.py L29 的设定：Gurobi，5 线程，36000 s，NumericFocus 1，BarHomogeneous 1。这些不是物理或经济假设，不必进入登记表，但建议在 D2 参数文件或运行说明中写明。
