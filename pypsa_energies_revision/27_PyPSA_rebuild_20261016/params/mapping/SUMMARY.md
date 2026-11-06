# 登记表 ↔ 代码映射核查汇总（2026-10-28）

核查对象：`params/h2.yaml`、`ev.yaml`、`grid_econ.yaml`（140 条）↔ `src/model.py`（= bigmem `model_reg1.py`，MD5 a3d25812…）+ `src/default_D2_args.txt` + `inputs/`。bigmem 输入目录 16 个关键文件与本地 MD5 完全一致。

## 1. 正向（登记表 → 代码）

| 领域 | 条数 | match | mismatch | doc_only | cannot_verify | not_in_code | 映射文件 |
|---|---|---|---|---|---|---|---|
| 氢能 | 48 | 43 | 1 | 4 | 0 | 0 | h2_map.yaml / .md |
| EV | 28 | 27 | 0 | 1 | 0 | 0 | ev_map.yaml / .md |
| 电网、市场、经济 | 64 | 47 | 4 | 9 | 4 | 0 | grid_econ_map.yaml / .md |
| 合计 | 140 | 117 | 5 | 14 | 4 | 0 | |

**D2 基准实际用到的数值全部与登记表一致。** 5 条 mismatch：

| id | 登记表 | 代码实际 | 影响 |
|---|---|---|---|
| h2_el_water_vom | 4 円/kg | 4.19 円/kg（按未老化电耗换算，×1.047） | 可忽略 |
| grid_reinforcement_capex / fom / life / start_year | 105,000 円/kW、0.019、28 年、2031 | 0、0.01、40 年、2030（只在 PRESET_NEWBASE 中设定，PLEXOS 预设与 D2 参数都没有） | D2 基准不受影响（不扩容）；grid150/200 与 LHS 的接口扩容在 D2 上不计成本 |

cannot_verify（4）：ninja 风光出力的机型、倾角等元数据未保存（3 条）；负荷时区无法从文件判断（1 条）。

## 2. 反向（代码 → 登记表），code_inventory.yaml

281 项：covered 164、inactive_in_D2 82、numerical 28、orphan 7（5 个概念）。

游离参数（影响结果但登记表没有）：
1. EV 控制方式 `--ev-control`（C 组取 argparse 默认值 bidirectional）→ 建议补 `ev_control_regimes`
2. 情景定义 S0–S4 → `scenario_design`
3. 氢不外售（h2_sale_price = 0）→ `h2_offsite_sale`
4. 燃料电池可变成本 0 → `h2_fc_vom`
5. 风光、水电可变成本 0 → `re_vom`

D2 中被静默忽略的参数：`--h2-capex`、`--h2-capex-scale`、`--h2-om-set`、`--h2-life`、`--wacc`、`--re-fom-jpy-per-kw`（只在年金方法中起作用）；`--h2-availability`（被 el/fc 可用率覆盖）；`--export-curtail-*`（使用 `--price-series` 时不起作用）。

多处写死：折现率 3% 在 model.py 中写死 13 处，`--wacc` 管不到 D2；电解槽每块的电功率有 491.2 / 549.2 / 530 三种口径（530 仍出现在部分说明中）。

## 3. 其他需要处理的事项

- 系统寿命：PLEXOS 方法不使用系统寿命；但按登记表寿命，2025–2027 年的电解槽和 2025–2030 年的燃料电池在 2050 年前到期，模型不计其系统更换 → 正文不能写"寿命在期内不起作用"，应说明。
- 燃料电池可用率 0.95 作用于氢输入，折成电出力为 0.925。
- 登记表的 code_now 与行号是旧版（722 行）代码的，多处需更新（530 kW、δ = 1.042 等）。
- 敏感性 `soh08`、`evlow` 仍用 newbase 固定曲线，口径不一致；`ev_share` 没有命令行入口；固定曲线脚本的校核出发 SoC 是 0.6（D2 为 0.8）。

## 4. 自动核对

可直接组合为每次运行前的核对：`params/check_h2_costs.py`、`mapping/scripts/h2/check_h2_map.py`、`mapping/scripts/ev/check_ev_map.py`（31 项）、`mapping/scripts/grid_econ/compute_grid_econ.py`、`check_price_model.py`。
