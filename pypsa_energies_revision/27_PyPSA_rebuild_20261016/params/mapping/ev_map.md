# EV 参数登记表与模型代码的映射核查（D2 默认设定）

- 核查日期：2026-10-28
- 登记表：`params/ev.yaml`（28 条）
- 模型：`src/model.py`（738 行，SHA-256 `35a2bc2d…ab45a`；按任务说明，与 bigmem 上运行的 `model_reg1.py` 相同）
- D2 参数：`src/default_D2_args.txt`。先载入 `--preset plexos`，再用命令行参数覆盖。场景映射取自 `src/make_reg1_batch.py` 的 DESIGN：A0/AH = S3/S4 + `fixed`，B0/BH = `charge_only`，C0/CH = `bidirectional`。
- 逐条映射：`params/mapping/ev_map.yaml`
- 计算脚本：`params/mapping/scripts/ev/check_ev_map.py`，结果写入同目录的 `ev_effective_values.json`。31 项检查全部通过。

## 1. 方法

1. **复原 D2 参数。** 用 ast 从 `model.py` 中取出 `main()` 里构造 argparse 的语句和 `PRESET_PLEXOS`，依次加上 DESIGN 中的场景参数和 D2 参数文件，按模型本身的解析顺序得到 6 个 EV 算例的 `args`。整个过程没有 `import model`，也没有建模或求解。
2. **从输入重算生效值。** 读取 `profiles.parquet`、S3/S4 参数 JSON 和原始 csv（车队、行驶、接入率），按 `prepare_inputs.py` 与 `model.py` 中的公式重算进入约束或目标函数的数值，再与登记表的 value 和 unit 比较。
3. **复现固定曲线。** 在临时目录运行 `build_fixed_profile.py --preset newbase`，将输出的 SHA-256 与 `inputs/fixed_fleet_charging_newbase.parquet` 比较，并逐项比较脚本中的常数与 D2 参数。
4. **确认 PyPSA 的约定。** 查阅本机 pypsa 1.2.4（与 `requirements-bigmem.txt` 版本相同）的 `define_store_constraints`，确认 Store 的能量平衡为 $e_t=(1-\text{standing\_loss})^{w}e_{t-1}+p_t w$，且 $e_t$ 是时段末的状态。据此可知，出发约束作用在 06:00 快照上，对应的就是 07:00 的电量。

## 2. 判定统计

| 判定 | 条数 | 条目 |
|---|---|---|
| match | 27 | 其余全部 |
| doc_only | 1 | `ev_annual_mileage`（派生量，不进入模型） |
| mismatch | 0 | — |
| not_in_code | 0 | — |
| cannot_verify | 0 | — |

主要生效值如下（B/C 受控部分；每车数值不受参与率影响）：

| 项目 | 生效值 |
|---|---|
| 每车可用电量 | 0.07 × 0.9 = 63 kWh |
| SoC 下限（绝对口径） | 0.35 × 70 = 24.5 kWh，相当于可用容量的 38.9% |
| SoC 上限 | 0.96 × 63 = 60.48 kWh，取自 cfg 中的 Max SoC，相当于名义容量的 86.4% |
| 出发下限 | 每天 06:00 快照末（即 07:00），0.8 × 63 = 50.4 kWh；作用于两个车队 |
| 效率 | 单程 0.93 × 0.98 = 0.9114；往返 0.8306 |
| 充电桩功率 | 直流侧 10 kW（L561）；交流侧最大取电 10.75 kW |
| 停放损失 | 每个逐时快照 5×10⁻⁴，相当于每天 1.19%；按电量的比例计 |
| V2G 成本 | 放电 Link 的 marginal_cost 为 0.003 百万円/MWh（电池侧），按贴现权重计入目标函数，只在 C 中出现 |
| 参与率 0.5 | 车辆数和行驶耗电乘 0.5（L374），由此 e_nom、功率和约束右端都随之缩放；非参与部分是 0.5 × 固定曲线（L372）；A 不适用 |
| 末年条件 | 稳态约束，车辆数比值为商业 1.0184、居民 1.0132；`terminal_recycle` 不生效 |
| 固定曲线 | 重建结果与现有文件的 SHA-256 完全一致（`3e0b0b15…`）；06:00 最低 SoC 为 0.96 |

## 3. 非 match 项及其他发现

### 3.1 doc_only：`ev_annual_mileage`

年里程是派生量，模型中没有对应入口，这与登记表的定位一致。按输入推算，商业车约 36,226 km/车·年，居民车约 20,622 km/车·年，与登记表 `code_now` 一致。这一项不需要改代码。

### 3.2 不影响 D2 数值、但建议处理的问题（均只是建议，未改任何文件）

1. **登记表中的行号已过时。** 登记表和 `04_ev.md` 引用的是 722 行旧版本（`model_before_registry1.py`）的行号。当前 `model.py` 在 L68–93 新增了氢能 FOM 和电堆更换的代码，使 EV 部分整体下移 16 行，例如 L190→L206、L345–406→L361–422、L541–558→L557–574、argparse L618→L634、PRESET_PLEXOS L606→L622。EV 代码本身没有变化（已用 diff 核对）。
   - 建议：把 `ev.yaml` 中的 `model_entry` 改为以本映射表为准；或者今后只引用模式（例如 `ecap=.07*`），不写死行号。
2. **敏感性算例与固定曲线口径不一致**（只影响敏感性，不影响 D2）。`make_sensitivity_batch.py` 中的 `soh08`（L23）和 `evlow`（L26）只改了模型参数，A 情景和 B/C 非参与部分仍使用按 SOH 0.9、效率 0.93/0.98 生成的 newbase 曲线。`avail08` 和 `comb09` 已换用对应的曲线，而模型 L638–641 也只对接入率缩放做了防护。
   - 建议：给 `build_fixed_profile.py` 增加 `--soh`、`--station-eff`、`--battery-charge-eff`、`--charger-kw` 参数，为上述敏感性分别生成曲线；并在模型中检查固定曲线的生成参数（例如读取 check.json）是否与 args 一致。
3. **常数硬编码，与 cfg 和命令行都不联动。** 下列常数在模型中是硬编码的：名义容量 0.07（L206、L377）、下限 0.35（L377）、初始 SoC 0.96（L415、L417）、停放损失 0.0005（L403、L415）、每公里耗电 0.0002（prepare_inputs.py L71）。固定曲线脚本中也有同样的常数（L18–22），另外还有充电功率 0.01 MW（L19）。目前这些数值与登记表和 cfg 都一致，但任何一个改值都需要同时改两处，并重建曲线。
   - 建议：把这些常数写进自动核对脚本（见第 4 节）。
4. **`ev_fleet_count_commercial` 的敏感性 `ev_share` 在 model.py 中没有入口。** 这一项属于原 PLEXOS 批次。若要在 D2 框架下复现，需要新增车队缩放参数，并配套生成相应的固定曲线。
5. **死代码与记录缺口。** L376 和 L380 的 `dep_floor` 计算后从未被使用；在 `model_fixes` 下，L559 的 `allowed` 也未被使用。另外，L600 只在 `ev_control=='fixed'` 时记录固定曲线的 SHA，而 B/C 同样使用这条曲线。
   - 建议：删除死代码，并把 SHA 的记录条件改为 `uses_fixed`。
6. **固定曲线脚本中 newbase 预设的 `departure_soc=0.6`。** 这个值只用于 check.json 中的校核，不影响曲线本身。建议改为 0.8，使校核口径与 D2 一致。
7. **两处登记表措辞可以更准确。**
   - `ev_availability_profile` 写的是"两车队均用 '~CS_JR Namie Commercial Area' 列"。实际上两个车队各自使用自己的列（`EV JR Namie Commercial Area~CS_…` 和 `EV Residential Cars~CS_…`），两列的数值不同，只是充电站相同。
   - `ev_participation` 写的是"其余 50% 按固定曲线"，这只适用于 B/C；A 情景是 100% 按固定曲线充电。

### 3.3 核查的边界

- bigmem 上的实际运行读取的是 `inputs/`（`make_reg1_batch.py` 中的 INP），模型 ROOT 也指向该目录。按任务约定，本次以本地 `27_PyPSA_rebuild_20261016/inputs/` 作为 `{INP}`，没有 ssh 去核对远端文件。
- 已有的旁证：本地 `results/d2_base/base__A0/summary.json` 记录的固定曲线 SHA 为 `3e0b0b15…`，与本地文件一致；`base__C0` 记录的 EV 参数与本次复原的结果相同。远端 `profiles.parquet` 和 `S3/S4_parameters.json` 的哈希没有记录，因此无法核对。
- 车队序列的来源问题（居民车队 = 商业 + 东居民）已由作者在 10-28 决定沿用，本次只确认代码忠实使用了该序列。
- 行驶 csv 的单位"km/车·h"是由公式反推的，属于合理推断，并非直接核实。

## 4. 适合写进自动核对脚本的检查项

以下检查项都已在 `check_ev_map.py` 中实现，可以直接并入总的核对流程。

1. 用模型自身的 argparse 和 PRESET 复原 6 个 EV 算例的 args，确认 A/B/C 的 `ev_control` 正确，并且 `model_fixes=True`、`tsam_segments=0`、`days_per_year=0`、全期运行、`extend_to=2050`。
2. 登记表数值与 args 逐项相等：`ev_capacity_scale`、`ev_station_eff`、`ev_batt_charge_eff`、`ev_batt_discharge_eff`、`ev_charger_kw`、`v2g_cost_jpy_per_kwh`、`ev_departure_soc`、`ev_departure_hour`、`ev_departure_groups`、`ev_participation`、`ev_availability_scale`、`ev_cohorts`；`ev_v2g_efc_cap` 和 `ev_max_soc` 应为 None。
3. 用正则在 model.py 中确认以下硬编码常数存在，且与登记表一致：`ecap=.07*`、`.35*(.07 if args.model_fixes`、`standing_loss=.0005`（应出现 2 处）、`ecap*.96`（e_initial 和 energy_arrivals）、`marginal_cost=args.v2g_cost_jpy_per_kwh/1000`，以及 L561 形式的直流共享功率约束。
4. S3/S4 cfg 中两个 EV 对象的 Max SoC、Initial SoC、Min SoC、Capacity、Efficiency 应分别为 96、96、35、70、200，并与模型中的硬编码一致。
5. 按年核对 `profiles.parquet` 的车辆数：等于 csv，等于登记表，并且年内恒定。逐时核对 `drive_MWh = 车辆数 × 0.0002 × csv`，以及 `availability = csv / 100`（最大差应为 0，且 availability ≤ 1）。
6. 出发约束：受约束的快照是 `(hour−1)%24 = 6`，每年的受约束小时数等于当年天数；出发下限为 0.0504 MWh/车，应满足下限 ≤ 出发下限 ≤ 上限（0.0245 ≤ 0.0504 ≤ 0.06048）。
7. 末年稳态：`model_fixes=True` 且快照中有 2049 年；输出 2050 年与 2049 年的车辆数比值。
8. 目标函数中不能出现 `capital_cost`，也不能出现与 EV 相关的投资项；EV 的成本只有放电 Link 的 marginal_cost。
9. 固定曲线：
   - 生成脚本的常数（可用电量、桩效率、电池充电效率、停放损失、充电功率、目标 SoC、是否为绝对下限）与 D2 args 及模型硬编码一致；
   - 在临时目录重建后，SHA-256 与 `--fixed-charge-profile` 指向的文件相同；
   - 每天 06:00 的 SoC 不低于出发 SoC，下限缺口为 0；
   - 曲线的索引与 `profiles.parquet` 相同。
10. 建议新增：对每个敏感性算例，检查它使用的固定曲线是否与该算例的 SOH、效率、充电功率和接入率一致（对应第 3.2 节第 2 点）。
11. 建议新增：在 summary.json 中写入 `model.py`、`profiles.parquet` 和 S3/S4 参数 JSON 的哈希，以便核对远端输入与本地是否相同（对应第 3.3 节）。
