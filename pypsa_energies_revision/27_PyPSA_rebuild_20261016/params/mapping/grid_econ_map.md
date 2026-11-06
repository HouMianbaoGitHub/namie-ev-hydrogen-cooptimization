# 电网、市场、可再生能源、负荷与经济参数：登记表与代码的对应核查

日期：2026-10-28
范围：`params/grid_econ.yaml` 中的全部 64 条记录
代码：`src/model.py`（当前 739 行版本，与 bigmem 上的 `model_reg1.py` 相同）
D2 参数：依次取 argparse 默认值、`PRESET_PLEXOS`（L622–631）、`src/default_D2_args.txt`，后者覆盖前者
逐条映射：`params/mapping/grid_econ_map.yaml`
计算脚本：`params/mapping/scripts/grid_econ/`
- `compute_grid_econ.py`：用 ast 从 model.py 取出函数和常数，再按 build() 的公式重算逐时映射。不 import model，也不求解。结果写入 `effective_values.json`。
- `check_price_model.py`：用 ast 读取 `build_future_prices.py` 的常数，并用 processed 数据复算派生值。不运行原脚本，也不覆盖任何文件。结果写入 `price_model_values.json`。

## 1. 判定统计

| 判定 | 条数 | 记录 |
|---|---|---|
| match | 47 | 其余全部 |
| mismatch | 4 | grid_reinforcement_capex、grid_reinforcement_fom、grid_reinforcement_life、grid_reinforcement_start_year |
| not_in_code | 0 | — |
| doc_only | 9 | end_treatment_robustness、currency_price_base_year、grid_reinforcement_levels、grid_reinforcement_max_mw、price_model_validation、tohoku_tokyo_interconnector_plan、wind_cf_validation、horizon_extension_2060、foresight_robustness |
| cannot_verify | 4 | price_offshore_shape、pv_profile_spec、wind_profile_spec、time_zone |

D2 基准实际使用的数值全部与登记表一致。4 条 mismatch 都只在接口扩容时起作用，而 D2 的 `--grid-max-mw` 为 0，所以不影响 D2 基准结果。

主要的实际生效值如下。

- 折现率为 3%。W2050 = 1.03^-25/0.03 = 15.9202，即 2050 年及以后按永续计。它在运行权重中占 47.76%。
- 风光投资按 PLEXOS 现值计入。各年单位现值除以 1.03^-(y−2025)，再减去原稿造价，余额在 26 个建设年里都是 33.356 千円/kW。这个余额就是 FO&M 1,000 円/kW·年的永续现值，计算式为 1,000/0.03 × 8,766/8,760。由此可以确认三点：造价一次付清，投资按年初贴现，FO&M 按 3% 永续。
- 建设年造价：风电 293.35、248.00、177.24、126.68 千円/kW，光伏 189.15、172.00、142.23、117.61，屋顶光伏 265.39、234.00、181.91、141.42（依次为 2025、2030、2040、2050 年）。中间年按几何插值，逐年比值恒定。`scale_annuity` 只改动了 78 条氢能记录，风光的记录与输入文件逐位相同。
- 接口：S0–S4 的买入、卖出 p_nom 都是 118 MW。PLEXOS 文件中的 150 MW 已被覆盖。网费为 0/0，fees 算例为 +2/−1 円/kWh。
- 电价：价格文件与 `price_model/future_prices.parquet` 完全相同，227,904 个快照全部有值，最低价为 0.01 円/kWh。各年平均价与汇总表相差不超过 0.004 円/kWh，原因是非闰年跳过了 2024-02-29。
- 出口弃电：凡是 curt_rate > 0 的小时，电价都在地板价。按 118 MW 计，2050 年最多少送 71,182 MWh，按地板价算不超过 0.71 百万円/年。
- 风光 CF：非闰年光伏 15.854%（1,388.8 h），风电 32.325%（2,831.6 h）。所用风电文件是 80 m 的 `namie_h80_wind_2024.csv`。`--wind-scale 0.75` 时风电 CF 降到 24.24%，光伏不变。
- 负荷：2025 年 50.622 GWh，2050 年 109.118 GWh。两年逐时之比恒为 2.1555，说明负荷形状不变。
- 水电：1 MW，月度上限合计 7.7376 GWh/年，实际最多可发 7.6896 GWh/年。

## 2. 非 match 项：影响与修改建议（只建议，未改代码）

### 2.1 mismatch：接口扩容的四个成本参数没有进入 D2 参数

| 记录 | 登记表 | D2 实际值（argparse 默认） | 差值 |
|---|---|---|---|
| grid_reinforcement_capex | 105,000 円/kW | 0 | −105,000 |
| grid_reinforcement_fom | 0.019 /年 | 0.01 | −0.009 |
| grid_reinforcement_life | 28 年 | 40 | +12 |
| grid_reinforcement_start_year | 2031 | 2030 | −1 年 |

**原因。** 这四个值只写在 `PRESET_NEWBASE`（L619）中。D2 改用 `--preset plexos` 后，`PRESET_PLEXOS` 和 `default_D2_args.txt` 都没有包含它们。

**影响。** D2 基准的 gmax 为 0，L540 的扩容模块不会建立，因此基准结果不受影响。但在 D2 参数上做扩容敏感性时，扩容不计成本，而且从 2030 年起就可以扩容。按登记表的四个值计算，2031 年每扩容 1 MW 的现值应为 211.9 百万円；现在是 0。受影响的算例包括：
- `make_sensitivity_batch.py` L36 的 grid150 和 grid200；
- `make_lhs_batch.py` L27 的 grid_expansion_mw。

**建议。** 二选一：
- 在 `default_D2_args.txt` 中补上 `--grid-capex-jpy-per-kw 105000 --grid-fom 0.019 --grid-life 28 --grid-start-year 2031`；
- 或在 `PRESET_PLEXOS` 中加入这四个值。

另外有两个口径问题需要作者决定，并在正文中写明：
- `grid_pv_per_mw` 按年金乘 `annuity_factor` 计价，相当于无限期重置，而其他设备按一次付清计价。
- 扩容敏感性是外生给定 150/200 MW，还是内生扩容（上限 32/82 MW）。现有批次用的是后者。

### 2.2 cannot_verify

- **price_offshore_shape、pv_profile_spec、wind_profile_spec。** ninja CSV 下载时用了 `header=false`，文件里没有请求参数，因此无法核实风机型号、倾角、方位角和系统损失。能确认的有三点：
  - 所用文件就是 `namie_pv_2024.csv` 和 `namie_h80_wind_2024.csv`，两者与 parquet 逐值相同；
  - `fetch_ninja.py` 的默认参数与登记表相同；
  - 海上风电各海域的权重与登记表相同。

  建议以后用 `header=true` 重新下载一次，并把元数据存档，或者把下载命令写进 data/README。
- **time_zone。** 光伏和电价可以确认是 JST，光伏日内峰值在 11 时。负荷的时区，以及时间戳是否为小时起点，无法从文件判断。这与登记表的 notes 一致，需要查原稿的负荷生成脚本。

### 2.3 doc_only 中值得注意的三处

- **end_treatment_robustness。** 代码不阻止「PLEXOS 方法 + `--no-perpetuity`」这种不一致的组合。`make_attribend_batch.py` L30（L5a）和 `make_attribrev_batch.py` L30（r4）都用了这个组合。建议在 `main()` 中对它报错或警告。截断检验应当只用 L5c 的口径，即 annuity 加 no-perpetuity。
- **horizon_extension_2060。** 生物质价格 CSV 只到 2050 年，因此 2051–2060 年的出售价被映射为 NaN（L328）。NaN 边际成本在 linopy/PyPSA 中如何处理，本次没有核实。已有的 ext2060 算例都能求解，生物质的作用也很小。建议在 L328 后加 `.ffill()`，确保与「2050 年条件不变」的设定一致。
- **currency_price_base_year。** 代码没有基准年的概念，输入都是各自口径下的名义值。「2024 年価格（実質）」只是一个标注，正文需要说明各项成本没有做年份换算。

### 2.4 其他发现（不影响判定）

- **登记表行号过时。** 登记表引用的是 723 行的旧版 model.py，当前版本中多数行号后移了约 16 行。例如：

  | 内容 | 登记表行号 | 当前行号 |
  |---|---|---|
  | W2050 / annuity_factor | L99–103 | L115–119 |
  | 运行贴现 | L281–285 | L297–301 |
  | 接口 | L301–305 | L317–321 |
  | 风光映射 | L206–211 | L222–227 |
  | 价格映射 | L212–220 | L228–236 |
  | 风光缩放 | L221–222 | L237–238 |
  | 价格下限 | L236 | L252 |
  | 现有机组 | L294–299 | L310–315 |
  | 生物质 | L307–315 | L322–331 |
  | 水电 | L575–583 | L591–599 |
  | 扩容 | L524–525 | L540–541 |
  | grid_pv_per_mw | L78–83 | L94–99 |
  | PRESET_PLEXOS | L606–615 | L622–631 |
  | argparse | L618 | L634 |
  | 滚动窗口保护 | L619 | L635 |
  | CAPEX 字典 | L85–86 | L101–102 |
  | crf | L139 | L155 |

  映射文件中用的都是当前行号。建议重新生成登记表的 model_entry 字段，或者改为按函数名或参数名引用。
- **wind_scale_sensitivity 的描述过时。** 这一条的 code_now 写着「无此参数」，model_entry 写着「需新增」。实际上该参数已经实现（L238 和 argparse），应当更新。
- **弃电率的两种口径。** `grid_conditions_by_year.csv` 中的 curtail_share 列（L272）是逐时弃电率的简单平均，2050 年为 6.89%。按区域 VRE 电量加权的弃电率是 14.78%。报告时不要混用这两个数。
- **三条上限记录的 value 为 null。** new_build_limit_wind、new_build_limit_pv_utility、new_build_limit_pv_rooftop 的 value 都是 null，但作者已经决定沿用原稿的上限。建议把 value 填为 1200/400/60 MW，并另列年上限 120/40/0.4 MW/年。

## 3. 自动核对脚本可以检查的项目

以下各项都可以在不求解的情况下完成。阈值一栏给出建议的容差。

| # | 检查 | 方法 | 期望（阈值） |
|---|---|---|---|
| 1 | D2 合成参数 | argparse 默认值 ← PRESET_PLEXOS ← D2 文件（ast 解析 add_argument） | market_limit_mw = 118；import_adder = export_deduction = 0；investment_method = plexos；PERP = True；extend_to = 2050；days_per_year = tsam_segments = 0；renewable_scale = wind_scale = price_scale = series_curtail_scale = 1；price_wind_beta = 0 且无 path；export_curtail_share = 0 且无 path |
| 2 | 扩容参数完整性 | 若批次中出现 `--grid-max-mw` > 0，检查 grid_capex/fom/life/start_year 是否等于登记表 | 105000 / 0.019 / 28 / 2031（目前不通过） |
| 3 | W2050 与 2050 年权重 | 执行 model.py 的 W2050() | 15.9202；占运行权重 0.4776（1e-4） |
| 4 | 风光单位成本 | scale_annuity(S2_annuity.json)/1.03^-(y−2025)/UNIT_KW − Build_Cost CSV | FO&M 部分 = 1000/0.03 × 8766/8760 = 33.356 千円/kW（1e-2）；风光行不被 scale_annuity 改动 |
| 5 | 造价锚点 | 第 4 项中的造价与登记表锚点比较 | 差值 ≤ 0.5 千円/kW |
| 6 | 接口 p_nom | 各情景 market + gmax | S0–S4 均为 118 |
| 7 | 价格文件一致性 | 与 price_model/future_prices.parquet 逐值比较；按 model.py 的键映射后检查缺失 | 完全相同；缺失 0；最低价 0.01 |
| 8 | 年均价 | 映射后的逐年均值与 future_prices_summary.csv 比较 | 差值 ≤ 0.01 円/kWh |
| 9 | 弃电只出现在地板价小时 | curt_rate > 0 且 price > 0.01 的小时数 | 0 |
| 10 | 风光文件 | parquet 与 raw/ninja/namie_pv_2024.csv、namie_h80_wind_2024.csv 逐值比较 | 最大差 0 |
| 11 | 风光 CF | 映射后 2025 年平均 | 光伏 15.85%、风电 32.33%（0.01 个百分点）；光伏日内峰值 11 时；映射后 NaN 为 0 |
| 12 | wind-scale 只作用于风电 | 0.75 倍时风电 CF 与光伏 CF | 风电 24.24%，光伏不变 |
| 13 | 现有容量与上限 | 按 L310–313、L437、L462 的公式从 S*_parameters.json 计算 | 光伏 103、风电 38；风电 1,200 MW（120/年），地面光伏 400（40/年），屋顶光伏 60（0.4/年） |
| 14 | 负荷 | profiles.parquet 逐年合计；2050/2025 逐时比 | 2050 年 109.118 GWh；比值恒为 2.1555 |
| 15 | 水电 | hydro_monthly 年合计；各年是否相同 | 7.7376 GWh；26 年相同 |
| 16 | 快照数 | profiles.parquet 行数 | 227,904 |
| 17 | 电价模型常数 | ast 读取 build_future_prices.py | REF 2024；PV/风电参考容量 9.05/2.24 GW；核电 0.825 GW × 0.72；地板价 0.01；T_SPLIT 5500；DATC、SITES 与登记表相同；T_MIN 复算 2,491 |
| 18 | 规划组合 | tohoku_penetration_beta.csv（plan） | 与登记表四个锚点年相同 |
| 19 | 不一致组合 | 批次文件中，有 `--no-perpetuity` 而 investment_method 不是 annuity | 应为 0 个（目前 L5a、r4 两处） |
| 20 | 延长到 2060 年 | load_annuity 记录数，2055/2050 单位现值比，生物质价格是否覆盖 2051–2060 | 216 条；0.8626；目前生物质价格不覆盖（预警） |

`compute_grid_econ.py` 和 `check_price_model.py` 已经输出上表中除第 2、19 项以外的全部数值。第 2、19 项需要再解析批次文件。可以参照 `params/check_h2_costs.py` 的写法，把它们合并成一个返回通过或失败的检查脚本。
