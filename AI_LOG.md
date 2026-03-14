# Codex Modification Log

## 2026-03-14 20:14

### 时间
2026-03-14 20:14

### 本次任务
增强 `test_dynamics.svg` 排名可读性：将排名标注下沉到每个 test 子图，分别对应 ICIR/Sharpe/rtn 各自指标。

### 修改文件
- src/evaluation/library_dynamics_plotter.py
- AI_LOG.md

### 主要改动
- 在 `library_dynamics_plotter.py` 新增 `_valid_count()`，统计每个指标可参与排名的有效轮次。
- 扩展 `_panel()` 支持子图级排名注释参数：
- `selected_rank`
- `last_rank`
- `rank_denominator`
- 在 `export_test_dynamics_svg()` 中对三个 test 子图分别传入对应排名：
- Test ICIR 使用 ICIR 序列排名；
- Test Sharpe 使用 Sharpe 序列排名；
- Test rtn 使用 rtn 序列排名；
- 每图新增文字：`rank(desc) sel: x/N | last: y/N`。

### 测试情况
是否新增测试：否
是否运行测试：是
测试结果：通过
- `python3 -m compileall -q src/evaluation/library_dynamics_plotter.py`

### 风险与待办
- 当前图顶仍保留汇总排名行，与子图排名信息并存；若你希望更简洁，可在下一次改动中移除顶部汇总行。

## 2026-03-14 19:41

### 时间
2026-03-14 19:41

### 本次任务
补全评价标准文档口径：明确 `min_periods_abs + min_periods_ratio` 在选择标准中的同时生效规则，补齐未选中四类判定定义，并说明边际贡献组合构建与对比基准。

### 修改文件
- docs/EVALUATION_STANDARDS.md
- AI_LOG.md

### 主要改动
- 更新 `docs/EVALUATION_STANDARDS.md` 时间戳到 `2026-03-14`。
- 在 A（选择标准）中明确：
- `time_windows.ic_calculation.min_periods_abs` 与 `time_windows.ic_calculation.min_periods_ratio` 同时生效；
- 每窗口统一门槛 `required_points = max(min_periods_abs, ceil(window * min_periods_ratio))`；
- 样本不足时 ICIR 为 `NaN`，通过权重重归一化处理。
- 在 B2（未选中评估）中补充：
- 四种结果 `SUCCESS/FAILURE/NEUTRAL/UNCERTAIN` 的完整定义；
- `UNCERTAIN` 触发条件（数据不足）；
- 边际贡献的组合构建方法（`marginal_contribution.method`）与对比基准（`Baseline` vs `Replacement`）；
- 边际改善口径 `Sharpe(Replacement)-Sharpe(Baseline)`；
- 替换策略配置来源 `marginal_contribution.replacement_strategy`。
- 在第5节补充 A/B1/B2 对双门槛规则的统一使用说明。

### 测试情况
是否新增测试：否
是否运行测试：否
测试结果：未运行（本次为文档更新）

### 风险与待办
- 当前文档已覆盖核心口径；若后续替换策略新增具体算法分支，需在该文档同步补充“各策略如何选被替换因子”的细节。

## 2026-03-14 14:21

### 时间
2026-03-14 14:21

### 本次任务
将 IC/ICIR 的最小样本门槛改为“绝对值+比例”双参数，并将样本不足时的 ICIR 语义从 `0` 调整为 `NaN`；同时为聚合评分增加缺失重归一化，避免 `final_score` 被 NaN 污染。

### 修改文件
- src/core/factor_enhanced.py
- src/core/bayesian_selector_v2.py
- src/utils/config_manager.py
- src/evaluation/library_tracker.py
- src/evaluation/portfolio_simulator.py
- config/evaluation_config.yaml
- docs/EVALUATION_STANDARDS.md
- docs/PARAMETER_MAPPING.md
- docs/FACTOR_LIBRARY_EVAL_PROTOCOL.md
- AI_LOG.md

### 主要改动
- `ICIR` 计算口径更新：
- 新增 `time_windows.ic_calculation.min_periods_abs`
- 新增 `time_windows.ic_calculation.min_periods_ratio`
- 使用统一门槛公式：`required_points = max(min_periods_abs, ceil(window * min_periods_ratio))`
- 当有效 IC 样本不足时，`calculate_icir()` 返回 `NaN`（不可计算），不再返回 `0`。
- 选中因子 success 判定改为基于上述动态门槛（不足直接失败）。
- `get_aggregate_score()` 新增双层重归一化：
- 窗口内：缺失指标（如 ICIR 为 NaN）按有效指标重归一化指标权重；
- 窗口间：缺失窗口按有效窗口重归一化窗口权重。
- 为避免 NaN 连锁影响：
- `library_tracker` 的均值/方差统计改为忽略非有限值；
- `portfolio_simulator` 的 ICIR 加权对 NaN/非数值自动降为 0，避免权重异常。
- 文档与配置同步：
- `evaluation_config.yaml` 改为新参数键；
- `EVALUATION_STANDARDS.md`、`PARAMETER_MAPPING.md`、`FACTOR_LIBRARY_EVAL_PROTOCOL.md` 更新为新口径与变量名。

### 测试情况
是否新增测试：否
是否运行测试：是
测试结果：通过
- `python3 -m compileall -q src/core/factor_enhanced.py src/core/bayesian_selector_v2.py src/utils/config_manager.py src/evaluation/library_tracker.py src/evaluation/portfolio_simulator.py`

### 风险与待办
- 部分展示字段（如 `recent_icir`）在样本不足阶段会出现 `NaN`，语义正确但下游可视化若希望“不可计算”显式标签，建议后续统一格式化。
- 目前 `min_periods_ratio` 限制在 `[0,1]`，若后续要支持“超过窗口长度”的更严格门槛，需要放宽配置校验。

## 2026-03-14 00:52

### 时间
2026-03-14 00:52

### 本次任务
落地“双基准出库标准”配置化实现，并增强 test_dynamics 排名标注与文档映射。

### 修改文件
- config/evaluation_config.yaml
- src/utils/config_manager.py
- src/workflows/factor_library_iteration_engine.py
- src/evaluation/library_dynamics_plotter.py
- docs/EVALUATION_STANDARDS.md
- docs/PARAMETER_MAPPING.md
- docs/CODE_ARCHITECTURE.md
- AI_LOG.md

### 主要改动
- 新增 `library_selection` 配置块（YAML）：
  - anchor / objective / thresholds / stability_gate / fallback 全参数化。
- `strict_holdout` 出库逻辑改造：
  - 每轮新增 `improve_primary_vs_prev`、`improve_primary_vs_anchor`、`improve_secondary_vs_anchor`。
  - 按 `library_selection.stability_gate` 计算 `stability_pass`（支持 `all` 或 `k_of_n`）。
  - 按双基准阈值 + 稳定门控生成 `selection_candidate`。
  - 最终在 `selection_candidate=True` 轮次中选 Validation 最优；无候选按 fallback 回退。
- `round_compact_summary.csv` 新增字段：
  - `selection_candidate`
  - `oos_excess_vs_anchor`
  - `improve_primary_vs_prev`
  - `improve_primary_vs_anchor`
  - `improve_secondary_vs_anchor`
- `test_dynamics.svg` 新增标注：
  - selected_round / last_round 在 test ICIR/Sharpe/rtn 中的全轮次降序排名。
- `ConfigManager` 增加 `library_selection` 默认配置与保存支持。
- 文档同步更新（标准、参数映射、架构描述）。

### 测试情况
是否新增测试：否
是否运行测试：是
测试结果：通过
- `python3 -m compileall -q`（关键修改文件）
- `aienv313` 下运行 `experiment_real_data_single.py`（strict_holdout, 3轮）成功
- 生成的 `test_dynamics.svg` 已出现排名标注行

### 风险与待办
- 当前锚库 `method` 仅实现 `round_1`；`fixed_formula/custom_ids` 为参数预留，尚未实现执行分支。
- 若 pool 日期覆盖短于 returns（本次 500 vs 1565），仍可能出现 OOS=0（已保留 warning 提示）。

## 2026-03-14 00:37

### 时间
2026-03-14 00:37

### 本次任务
增强 `test_dynamics.svg`：标注 selected/last 轮次在 test 指标中的全轮次排名。

### 修改文件
- src/evaluation/library_dynamics_plotter.py
- AI_LOG.md

### 主要改动
- 新增 `_rank_desc(...)`：
  - 对指定轮次计算降序排名（1=最好），仅在非空样本内排名。
  - 并列采用 competition ranking（1,2,2,4）。
- 在 `export_test_dynamics_svg(...)` 标题区域新增两行标注：
  - `selected_round rank(desc): ICIR #x, Sharpe #y, rtn #z`
  - `last_round rank(desc): ICIR #x, Sharpe #y, rtn #z`

### 测试情况
是否新增测试：否
是否运行测试：是
测试结果：通过（`python3 -m compileall -q src/evaluation/library_dynamics_plotter.py`）

### 风险与待办
- 当某指标在目标轮次为空时，排名显示为 `None`；属预期行为，表示该轮该指标无有效样本。

## 2026-03-14 00:29

### 时间
2026-03-14 00:29

### 本次任务
修复结果落盘时机问题，并新增 strict_holdout 防泄露边界校验。

### 修改文件
- src/workflows/factor_library_iteration_engine.py
- AI_LOG.md

### 主要改动
- 修复 `final_library.json` 落盘顺序：
  - 将 `final_library_file` 写盘从“最终评估前”移动到“最终评估字段写入后”，避免产物中 `final_eval_*` 与 `last_round_eval_*` 为空。
- 新增 `strict_holdout` 防泄露校验函数 `_assert_strict_holdout_no_leakage(...)`：
  - 约束更新轮次不得超过 `train_end_idx`。
  - 约束 `val_start_idx > train_end_idx`。
  - 若存在测试集，约束 `test_start_idx > val_end_idx`。
  - 启动时打印边界日志，明确 update/val/test 日期范围。

### 测试情况
是否新增测试：否
是否运行测试：是
测试结果：通过（`python3 -m compileall -q src/workflows/factor_library_iteration_engine.py`）

### 风险与待办
- 当前仅增加边界校验与日志，不改变指标口径；标准层改造（选中/未选中成功判定）待讨论后再实施。

## 2026-03-14 00:01

### 时间

2026-03-14 00:01

### 本次任务

统一 AI_LOG 维护顺序规则：改为倒序（从近到远），并同步到协作规范文件。

### 修改文件

- AGENTS.md
- AI_CONTEXT.md
- AI_LOG.md

### 主要改动

- 将 `AGENTS.md` 中 AI_LOG 记录规则由“追加”改为“倒序写入（新增放最前面）”。
- 在 `AI_CONTEXT.md` 的历史记录说明中补充相同规则，避免执行歧义。
- 在 `AI_LOG.md` 顶部新增本条记录，作为新规则下的首条示例。

### 测试情况

是否新增测试：否
是否运行测试：否
测试结果：未运行

### 风险与待办

- 现有历史日志主体仍保持原有顺序；后续新增将统一按倒序插入顶部。



## 2026-03-13 22:22

### 时间

2026-03-13 22:22

### 本次任务

按用户要求补充协作规则：明确 `archive` 历史目录默认可跳过，并完成项目主链路阅读与理解摘要准备。

### 修改文件

- AGENTS.md
- AI_LOG.md

### 主要改动

- 在 `AGENTS.md` 的“修改代码前步骤”中新增补充规则：
- 明确 `archive/`、`__archive/`、`docs/_archive/` 默认可跳过，不作为当前主链路依据。
- 明确仅在用户要求排查历史实现时才进入历史目录读取/修改。
- 在 `AI_LOG.md` 追加本次变更记录。

### 测试情况

是否新增测试：否  
是否运行测试：否  
测试结果：未运行

### 风险与待办

- 当前仓库中 `src/workflows/real_data_iteration_engine.py` 依赖 `data.real_data_loader`，但未发现对应实现文件；若运行真实数据入口可能报模块缺失错误，建议后续补齐或修正文档/导入路径。

## 2026-03-13 22:35

### 时间

2026-03-13 22:35

### 本次任务

README 与当前迭代主链路对齐；清理非主链路测试脚本到归档；补充核心代码文档注释以提升可读性。

### 修改文件

- README.md
- docs/example.md
- src/core/bayesian_selector_v2.py
- src/core/factor_enhanced.py
- src/workflows/factor_library_iteration_engine.py
- src/workflows/real_data_iteration_engine.py
- src/tests/_archive/experiment_math_smoke_ic_control.py
- src/tests/_archive/experiment_math_validation_correlation.py

### 主要改动

- 重写 `README.md`，删除旧模块（如 `mvp_selector/test_mvp`）描述，完整对齐当前主链路（workflows/core/evaluation/simulation/tests）。
- 归档非主链路数学验算脚本：
  - `src/tests/experiment_math_smoke_ic_control.py` -> `src/tests/_archive/experiment_math_smoke_ic_control.py`
  - `src/tests/experiment_math_validation_correlation.py` -> `src/tests/_archive/experiment_math_validation_correlation.py`
- 同步更新 `docs/example.md` 的脚本路径，标记为“已归档历史数学校验脚本”。
- 在核心文件补充统一风格 docstring（模块职责、函数边界与关键业务规则）：
  - `BayesianSelectorV2` 的打分与成功判定逻辑说明
  - `EnhancedFactor` 的回看窗口口径与综合打分方向说明
  - `FactorLibraryIterationEngine` 的最终选库、OOS评估、切分与早停规则说明
  - `RealDataIterationEngine` 的 asof 切片与真实面板转因子逻辑说明

### 测试情况

是否新增测试：否  
是否运行测试：是  
测试结果：通过（`python3 -m compileall -q ...` 语法检查通过）

### 风险与待办

- 当前仓库仍缺少 `data.real_data_loader` 实现，真实数据入口仍存在运行阻塞风险（与本次改动无关）。

## 2026-03-13 22:42

### 时间

2026-03-13 22:42

### 本次任务

补齐真实数据加载接口 `RealDataLoader`，按当前 `data/sim_progress_demo` 模拟导出格式设计并增强容错。

### 修改文件

- src/data/real_data_loader.py
- README.md
- AI_LOG.md

### 主要改动

- 重写 `src/data/real_data_loader.py`：
  - 明确支持的输入格式（long table）：
    - daily returns: `end_date,stock_code,rtn`
    - factor: `end_date,stock_code,score`
    - pool(optional): `end_date,stock_code,in_pool`
  - 输出统一面板结构（`dates/stock_codes/returns/in_pool/factor_scores`）与 `RealDataIterationEngine` 对齐。
  - 增加字段校验、数值解析校验、文件存在性校验。
  - 增加重复键处理策略（同键后值覆盖并输出 warning）。
  - 增加缺失与对齐处理：
    - 无 pool 文件时默认 `in_pool = ~isnan(returns)`。
    - 因子文件超出收益面板范围的数据自动忽略。
    - 全 NaN 因子保留并 warning（便于排查数据对齐问题）。
- 更新 `README.md`：
  - 删除“缺少 real_data_loader”过期提示，改为真实数据运行前置条件说明。

### 测试情况

是否新增测试：否  
是否运行测试：是  
测试结果：通过（`python3 -m compileall -q src/data/real_data_loader.py src/workflows/real_data_iteration_engine.py`）

### 风险与待办

- 当前环境未安装运行依赖（如 numpy），未执行真实入口端到端运行；已完成语法级校验，建议在目标环境安装依赖后执行 `experiment_real_data_single.py` 做联调验证。

## 2026-03-13 23:14

### 时间

2026-03-13 23:14

### 本次任务

定位真实数据场景下 `OOS=0` 原因并重跑验证；补充数据加载防呆提示。

### 修改文件

- src/data/real_data_loader.py
- AI_LOG.md

### 主要改动

- 定位结果：
  - `daily_returns/factors` 覆盖 500 个交易日，但本次运行使用的 `pools/all_stocks.csv` 仅覆盖 250 个交易日。
  - 在真实数据流程中，超出 pool 覆盖范围的样本会被视为不在池内，导致后半段标签被屏蔽，验证/测试区间无有效样本，OOS 全为 0。
- 重跑验证：
  - 使用 `pools/csi_all.csv`（覆盖 500 天）重跑同参数后，OOS 指标恢复为非零。
- 防呆增强：
  - 在 `RealDataLoader._load_pool` 增加覆盖率 warning：
    - 当 pool 日期覆盖少于收益面板日期时，输出强警告提示可能导致 OOS=0。

### 测试情况

是否新增测试：否  
是否运行测试：是  
测试结果：通过

- `experiment_real_data_single.py`（aienv313）:
  - 使用 `all_stocks.csv`：流程可运行但 OOS=0（复现问题）
  - 使用 `csi_all.csv`：流程可运行且 OOS>0（问题解除）
- `python3 -m compileall -q src/data/real_data_loader.py`：通过

### 风险与待办

- pool 文件稀疏/短覆盖属于高风险输入，建议后续在入口层增加显式一致性检查（可选 strict 模式直接报错）。

## 2026-03-13 23:53

### 时间

2026-03-13 23:53

### 本次任务

定位并修复“给定 start_date/end_date 时模拟输出日期不足”的根因，确保收益率/股票池/因子日期轴一致。

### 修改文件

- src/simulation/latent_factor_data_simulator.py
- AI_LOG.md

### 主要改动

- 根因说明：
  - `generate_dates()` 在有 `end_date` 时按日期区间生成交易日（例如 2014-2019）。
  - 但 `build_market_data()` 之前调用 `generate_stock_returns()` 未显式传入天数，仍使用 `config.num_days`（例如 250）。
  - 导致收益率天数短于日期轴，进而让导出后的 `daily_returns` 少于 `pool/factors`，最终出现“日期不足/OOS异常”。
- 修复：
  - `build_market_data()` 改为 `generate_stock_returns(n_days=len(dates))`，以日期轴长度为准生成收益矩阵。
  - 增加函数注释，明确该一致性约束，避免后续回归。
- 验证：
  - 在 aienv313 下最小复现参数验证：
    - `start_date=2014-01-01, end_date=2019-12-31, num_days=250`
    - 修复后 `dates_len=1565`, `returns_shape=(n_stocks,1565)`, `forward_shape=(n_stocks,1560)`，轴对齐成立。

### 测试情况

是否新增测试：否  
是否运行测试：是  
测试结果：通过（aienv313 环境下构造配置并调用 `build_market_data()` 验证）

### 风险与待办

- 建议后续在导出函数增加“日期轴/收益矩阵长度断言”，在开发阶段更早暴露类似问题。



## 2026-03-09 - phase_regime 增加 seed + 模块归档审阅 + 真实数据接入文档

### 修改

1. `experiment_phase_regime_comparison` 增加 seed 参数

- `src/tests/experiment_phase_regime_comparison.py` 新增 `--seed`
- `src/experiments/phase_regime_comparison_experiment.py` 增加 `seed` 参数并映射到 `cfg.RANDOM_SEED`

1. 模块归档整理

- 移动到归档目录：
  - `src/core/mvp_selector.py` -> `src/core/__archive/mvp_selector.py`
  - `src/core/integrated_selector.py` -> `src/core/__archive/integrated_selector.py`
  - `src/simulation/stock_simulator.py` -> `src/simulation/__archive/stock_simulator.py`
- `src/__init__.py` 改为导出当前主链路模块（`bayesian_selector_v2 / factor_enhanced / latent_factor_data_simulator`）

1. 新增真实数据接入文档

- 新文件：`docs/REAL_DATA_INTEGRATION_GUIDE.md`
- 内容覆盖：
  - 数据分层架构建议
  - 必备输入表与字段
  - 标签定义 `x(t) -> R(t+1->t+n)`
  - IC/LS/Sharpe/ICIR 年化口径
  - 数据质量检查清单
  - 接入步骤与常见风险

## 2026-03-08 - 年化指标与test分位点增强

### 背景

- 用户要求：
  - `round_compact_summary.csv` 增加 test 三指标分位点列。
  - `LS return / Sharpe / ICIR` 做年化处理。
  - 前瞻窗口与年化天数可作为参数传入。

### 修改

1. 年化参数

- `PerformanceTestConfig` 新增 `ANNUAL_DAYS`（默认250）
- CLI 新增：
  - `--horizon-days`（映射 `ROLLING_WINDOW`，IC与LS共用）
  - `--annual-days`

1. OOS年化输出

- 文件：`src/workflows/factor_library_iteration_engine.py`
- `oos_icir/oos_sharpe/oos_ls_mean` 改为年化口径输出
- 同时保留原始值字段（`*_raw`）用于稳定性判据与delta计算

1. round_compact 分位点

- 文件：`src/workflows/factor_library_iteration_engine.py`
- `round_compact_summary.csv` 新增：
  - `test_oos_icir_pct`
  - `test_oos_sharpe_pct`
  - `test_oos_ls_rtn_pct`

### 文档

- 更新：
  - `docs/EVALUATION_STANDARDS.md`
  - `docs/CODE_ARCHITECTURE.md`

## 2026-03-08 - 实验入口增加规模参数覆盖

### 目标

- 支持在命令行快速调整核心规模参数，便于做敏感性实验。

### 修改

- `src/tests/test_performance.py`:
  - 新增参数：`--num-stocks --num-factors --target-size --num-days`
  - 可与 `--baseline-only --seed` 组合使用
- `src/tests/experiment_phase_regime_comparison.py`:
  - 新增参数：`--num-stocks --num-factors --target-size --num-days`
  - 可与 `--baseline-only` 组合使用
- `src/experiments/phase_regime_comparison_experiment.py`:
  - `run_phase_regime_comparison(...)` 支持接收并应用以上覆盖参数

## 2026-03-08 - 实验入口参数化 + 场景汇总CSV + 轮次紧凑CSV

### 背景

- 用户要求：
  1. `test_performance.py` 支持仅运行 baseline 场景。
  2. 场景汇总表增加 long-short return 并导出 CSV。
  3. 生成每轮紧凑小表 CSV 便于复盘。

### 修改内容

1. 实验入口参数化

- 文件：`src/tests/test_performance.py`
- 新增参数：
  - `--baseline-only`：仅跑 baseline
  - `--seed`：设置随机种子

1. 场景对比汇总增强

- 文件：`src/experiments/factor_library_scenario_experiment.py`
- 汇总表新增 `avg_ls_rtn`（平均多空收益率）
- 新增场景汇总CSV导出：
  - `outputs/performance_tracking/scenario_comparison_summary_<ts>.csv`
- 默认对比场景调整为3个（baseline / low_persist_good / high_return_noise）

1. 每轮紧凑CSV

- 文件：`src/workflows/factor_library_iteration_engine.py`
- 新增导出：
  - `round_compact_summary.csv`
- 字段包括：
  - `stability_pass`
  - `is_selected_round`
  - `is_last_round`
  - validation/test 的 `ICIR/Sharpe/rtn`

## 2026-03-08 - 动态图升级（分指标面板 + test_dynamics）

### 背景

- 用户反馈：
  - `selected_round` 点在中间易误解，希望同时标注最后一轮对照。
  - 不同指标应拆分成独立图面板。
  - 需要新增 `test_dynamics.svg`，展示每轮 test 轨迹（ICIR/Sharpe/rtn）。

### 修改内容

1. 动态图拆分

- 文件：`src/evaluation/library_dynamics_plotter.py`
- `validation_dynamics.svg` 从混合曲线改为单指标面板：
  - `oos_sharpe`
  - `oos_icir`
  - `oos_ls_mean`（validation rtn）
  - `turnover`
  - `oos_excess_vs_prevlib`
  - `|Δoos_sharpe|`
  - `|Δoos_icir|`

1. 轮次标记增强

- 橙色实心圆：`selected_round`（最终出库轮次）
- 蓝色方块：`last_round`（最后一轮对照）
- 绿色空心圆：`stability_pass=True` 轮次
- 图标题新增 `stable rounds: x/total` 统计

1. 新增测试集动态图

- 新文件输出：`test_dynamics.svg`（当 `TEST_RATIO>0`）
- 每轮显示：
  - `test_oos_icir`
  - `test_oos_sharpe`（基于多空收益序列）
  - `test_oos_ls_mean`（test rtn）

1. 引擎接入

- 文件：`src/workflows/factor_library_iteration_engine.py`
- 每轮记录 test 轨迹字段（若存在 test 集）：
  - `test_oos_icir`
  - `test_oos_sharpe`
  - `test_oos_ls_mean`
- 运行结束导出：
  - `validation_dynamics.svg`
  - `test_dynamics.svg`（可选）

### 文档同步

- 更新：
  - `docs/EVALUATION_STANDARDS.md`
  - `docs/ITERATION3_SUMMARY.md`
  - `docs/CODE_ARCHITECTURE.md`

## 2026-03-08 - strict_holdout 出库策略改造（稳定性筛选 + 验证最优）

### 背景

- 用户确认：`strict_holdout` 不应以早停截断训练为主；应充分利用训练样本。
- 目标：把早停条件作为“稳定性标准”，对每轮打标，再在验证集选最优 `S_r`。

### 代码改动

1. 轮次稳定性标记

- 文件：`src/workflows/factor_library_iteration_engine.py`
- 每轮新增字段：
  - `d_oos_sharpe`
  - `d_oos_icir`
  - `stability_pass`

1. 最终选库逻辑分模式

- `strict_holdout`:
  - 在 `stability_pass=True` 的轮次中选 Validation 最优（Sharpe优先，ICIR次级）`S_r`
  - 若无通过轮次，回退为全轮次 Validation 最优
  - 同时输出最后一轮库作为对照
- `walk_forward_test`:
  - 保留早停逻辑

1. 输出增强

- `final_library` 新增：
  - `selected_round`
  - `selection_reason`
- 结果新增：
  - `last_round_library`
  - `last_round_eval_validation`
  - `last_round_eval_test`
- `final_library.json` 同步写入以上字段和 `eval_mode`

### 文档同步

- 更新：
  - `docs/FACTOR_LIBRARY_EVAL_PROTOCOL.md`
  - `docs/EVALUATION_STANDARDS.md`
  - `docs/CODE_ARCHITECTURE.md`
  - `docs/ITERATION3_SUMMARY.md`

## 2026-03-07 - 新增分阶段状态转移对照实验入口

### 背景

- 用户希望增加一个新的 tests 实验文件，用于对比验证/测试阶段环境变化对结果的影响。

### 新增文件

1. 可复用实验模块

- `src/experiments/phase_regime_comparison_experiment.py`
- 提供三类场景：
  - `stationary_baseline`
  - `val_test_easier`
  - `val_test_harder`

1. tests 入口

- `src/tests/experiment_phase_regime_comparison.py`
- 仅负责调用 experiments 层，不承载可复用逻辑。

### 文档同步

- 更新：
  - `docs/CODE_ARCHITECTURE.md`
  - `docs/EVALUATION_STANDARDS.md`
  - `docs/ITERATION3_SUMMARY.md`

## 2026-03-07 - 迭代模式升级（strict_holdout / walk_forward_test）与阶段化转移矩阵

### 背景

- 用户要求不再固定24轮，支持迭代到测试集末尾。
- 用户希望评估验证/测试有效性，并讨论是否在不同数据阶段设置不同状态机制。

### 新增能力

1. 双评估模式

- `strict_holdout`:
  - 仅在train迭代
  - 每轮在固定validation集评估
  - test仅做最终验收
- `walk_forward_test`:
  - 从train继续滚动迭代到test末尾（若无test则到val末尾）
  - OOS按滚动未来窗口评估

1. 轮次控制升级

- `NUM_TEST_ROUNDS` 支持 `None`
- 为 `None` 时不截断轮次，自动迭代到目标区间末尾

1. 分阶段状态转移（模拟器）

- `PHASE_TRANSITION_PROBS` 支持按 `train/validation/test` 指定不同转移矩阵
- 若未设置，沿用统一 `TRANSITION_PROBS`

### 涉及文件

- `src/experiments/factor_library_scenario_experiment.py`
- `src/experiments/factor_library_stability_experiment.py`
- `src/workflows/factor_library_iteration_engine.py`
- `src/simulation/latent_factor_data_simulator.py`
- `src/tests/experiment_stability_early_stop.py`

### 文档同步

- `docs/FACTOR_LIBRARY_EVAL_PROTOCOL.md`
- `docs/EVALUATION_STANDARDS.md`
- `docs/CODE_ARCHITECTURE.md`
- `docs/ITERATION3_SUMMARY.md`

## 2026-03-07 - 固定验证集OOS + 数据集切分参数 + 因子加权多空

### 背景

- 用户反馈当前仍显示“OOS 21天滚动”，希望改为固定验证集（如 2017-07~2017-12）用于出库，不参与后验更新。
- 用户要求模拟多空收益不再使用 topq-bottomq，而使用因子加权多空（多头/空头权重各归一为1）。

### 代码改动

1. 数据集切分参数

- 文件：`src/experiments/factor_library_scenario_experiment.py`
  - `PerformanceTestConfig` 新增：
    - `TRAIN_RATIO`
    - `VALIDATION_RATIO`
    - `TEST_RATIO`（允许0）
- 文件：`src/experiments/factor_library_stability_experiment.py`
  - `StabilityExperimentConfig` 同步新增上述参数，并映射到引擎配置。

1. 固定验证集OOS评估

- 文件：`src/workflows/factor_library_iteration_engine.py`
  - 新增 `_build_dataset_split()`，按比例切分 train/validation/test。
  - 选择轮次仅在 train 区间内执行。
  - OOS评估改为 `_evaluate_oos_library_on_validation()`，每轮在同一 validation 区间评估。
  - 日志从“未来21天”改为“固定验证集起止日期”。
  - `results/final_library.json` 新增 `dataset_split` 元数据。

1. 模拟多空收益口径改造

- 文件：`src/simulation/latent_factor_data_simulator.py`
  - `calculate_factor_ls_return()` 从 top/bottom 分组改为因子加权多空：
    - `w+ ∝ max(x,0)`, `w- ∝ max(-x,0)`
    - `sum(w+)=1`, `sum(w-)=1`
    - `LS = w+·R - w-·R`

### 文档同步

- 更新：
  - `docs/FACTOR_LIBRARY_EVAL_PROTOCOL.md`
  - `docs/EVALUATION_STANDARDS.md`
  - `docs/CODE_ARCHITECTURE.md`
  - `docs/ITERATION3_SUMMARY.md`
- 关键同步点：
  - C层采用固定 validation 口径
  - 支持 train/validation/test 比例参数
  - 多空收益改为因子加权多空（2x gross）

### 验证

- 运行通过：`python3 -u src/tests/experiment_stability_early_stop.py`
- 输出中已显示：
  - 数据切分比例与区间
  - `OOS(固定验证集 start~end)`（不再是“未来21天”）

## 2026-03-07 - 时序对齐修复（x(t) -> R(t+1->t+n)）与B步前置

### 背景

- 用户确认：因子信号 `x(t)` 在 `t` 收盘后可得，标签必须为 `R(t+1->t+n)`，不包含 `t` 当日收益。
- 要求将流程时序改为：每个 `t` 先更新后验（基于上一轮之后的新观测），再选本轮因子。

### 代码修改

1. 模拟标签严格前瞻化

- 文件：`src/simulation/latent_factor_data_simulator.py`
- 新口径：
  - 前瞻收益改为 `R(t+1->t+n)`（函数：`calculate_forward_returns_ex_t`）
  - 不再使用包含当日的滚动收益定义
  - 因子表现记录日期改为标签实现日 `t+n`（防止在 `t` 提前可见）

1. 迭代顺序改造（B前置）

- 文件：`src/workflows/factor_library_iteration_engine.py`
- 每轮改为：
  - 先用 `(t_{r-1}, t_r]` 新信息更新上一轮选中库（B）
  - 再在 `t_r` 选本轮库（A）
- 控制台输出同步调整：
  - 当前轮输出 `选中结构`
  - 额外输出 `上轮更新成功结构`

1. 跟踪器字段补充

- 文件：`src/evaluation/library_tracker.py`
- `record_round()` 新增参数 `update_selected_ids`
- 新增因子级字段：
  - `updated_in_b_step`
- 新增轮次字段：
  - `updated_selected_total`

### 文档同步

- 更新：`docs/FACTOR_LIBRARY_EVAL_PROTOCOL.md`
  - 统一改为 `R(t+1->t+n)` 表达
- 更新：`docs/CODE_ARCHITECTURE.md`
  - 主流程改为“先更新后选择”
- 更新：`docs/EVALUATION_STANDARDS.md`
- 更新：`docs/ITERATION3_SUMMARY.md`

### 其他

- 更新 `# AI_CONTEXT.md`：
  - 将“从 `test_performance.py` 开始追踪”改为“从给定 tests 文件或用户指定函数开始追踪”。

### 验证

- 编译通过：
  - `py_compile` 覆盖修改文件
- 运行通过：
  - `python3 -u src/tests/experiment_stability_early_stop.py`
  - 新时序日志已生效，产物正常导出。

## 2026-03-07 - 评估协议升级（Draft v2，严格时序与防未来函数）

### 背景

- 用户确认目标流程应为：每个时点先用新增观测更新后验，再进行当期选因子。
- 要求在正式协议中明确 `t` 因子与 `t+n` 收益配对规则，避免未来数据泄露。

### 本次更新

1. 协议文档重写升级

- 文件：`docs/FACTOR_LIBRARY_EVAL_PROTOCOL.md`
- 版本：`Draft v2`
- 关键变化：
  - 明确每轮顺序：`Observe/Update -> Select -> Record -> Validate`
  - 明确 `x_t` 仅可配对 `R_{t->t+n}`
  - 新增 IC/LS 计算口径与禁止项（防未来函数）
  - 新增推荐切分：`Train / Validation / Test`
  - 固定验证窗口用于出库判定，不参与后验更新
  - 补充协议级输出字段与元数据字段

1. 同步说明文档

- 更新：`docs/EVALUATION_STANDARDS.md`
  - 增加“当前实现 vs 协议v2目标时序”说明，避免口径混淆
- 更新：`docs/ITERATION3_SUMMARY.md`
  - 增加“后续代码需对齐协议v2时序”说明

## 2026-03-07 - 长周期稳定性/早停实验与收敛曲线输出

### 背景

- 用户要求进入新实验阶段：固定参数，重点观察因子库在更长历史中的稳定性与早停行为。
- 需要像模型训练那样输出“收敛/变化曲线”，可视化查看换手率、稳定性与样本外表现。

### 本次新增

1. 新增稳定性实验模块（复用层）

- 新文件：`src/experiments/factor_library_stability_experiment.py`
- 提供：
  - `StabilityExperimentConfig`（长周期实验参数）
  - `StabilityExperimentRunner`（运行实验并导出可视化/报告）
- 复用 `FactorLibraryIterationEngine` 的迭代结果，不在 tests 内重复实现核心逻辑。

1. 新增稳定性实验入口（tests 仅保留入口）

- 新文件：`src/tests/experiment_stability_early_stop.py`
- 作用：运行长历史实验并打印输出产物路径。

1. 新增可视化与报告输出

- 输出目录：
  - `outputs/performance_tracking/<run_tag>/stability_experiment/`
- 输出文件：
  - `stability_convergence.svg`
  - `stability_report_<timestamp>.json`
- `SVG` 面板：
  - 稳定性：`turnover` / `overlap`
  - OOS质量：`oos_sharpe` / `oos_icir`
  - OOS水平：`oos_ls_mean`
  - 收敛指标：`convergence_index`（归一化早停约束，`<=1` 表示接近/达到单轮阈值）

1. 文档同步（按 AI_CONTEXT 强制规则）

- 更新：
  - `docs/CODE_ARCHITECTURE.md`
  - `docs/EVALUATION_STANDARDS.md`
  - `docs/ITERATION3_SUMMARY.md`
- 变更内容：补充稳定性实验模块、入口、输出文件与指标口径。

### 验证

- 已运行：
  - `python3 -u src/tests/experiment_stability_early_stop.py`
- 结果：
  - 24轮完成，当前参数下未触发早停（`early_stop.triggered=False`）
  - 成功生成 `stability_convergence.svg` 与 `stability_report_*.json`

## 2026-03-07 - 实验代码分层重构（tests职责收敛）

### 背景

- 用户要求：`src/tests` 仅作为实验入口/demo，不承载可复用业务逻辑。
- 可复用类应迁移至 `src` 正式模块，便于未来反复调用与真实数据替换。

### 本次重构

1. 新增流程编排层

- 新文件：`src/workflows/factor_library_iteration_engine.py`
- 抽离原 `test_performance.py` 中 `PerformanceTester` 相关能力：
  - 单场景迭代主流程
  - OOS评估
  - 稳定性评估
  - 早停与最终出库
  - 结果汇总打印

1. 新增实验管理层

- 新文件：`src/experiments/factor_library_scenario_experiment.py`
- 提供：
  - `PerformanceTestConfig`
  - `build_scenario()`
  - `ScenarioComparator`（多场景批量对比）

1. tests入口精简

- `src/tests/test_performance.py` 改为纯入口脚本：
  - 构建默认场景
  - 调用 `ScenarioComparator.run()`

1. tests目录清理与命名优化

- 归档：
  - `src/tests/test_mvp.py` -> `src/tests/_archive/experiment_legacy_mvp_selector.py`
- 重命名（保留实验意义，更清晰）：
  - `minimal_test.py` -> `experiment_math_validation_correlation.py`
  - `quick_test.py` -> `experiment_math_smoke_ic_control.py`

### 结果

- `tests` 目录职责已收敛为“实验脚本入口”。
- 可复用功能分层至 `workflows/experiments/simulation`，后续真实数据替换更直接。

## 2026-03-07 - 模拟逻辑分层重构（tests -> simulation）

### 目的

- 清理 `src/tests` 目录职责：仅保留实验编排与评估逻辑。
- 将未来可替换为真实数据的数据生成逻辑迁移到 `src/simulation`。

### 修改内容

1. 新增模拟模块

- 新文件：`src/simulation/latent_factor_data_simulator.py`
- 包含：
  - `LatentFactorSimulationConfig`
  - `LatentFactorDataSimulator`
  - 日期/收益/滚动收益生成
  - 潜在状态因子历史生成
  - 因子IC/多空收益计算

1. 精简测试入口

- 文件：`src/tests/test_performance.py`
- 删除/迁移了原有数据模拟函数与模拟内部方法（如 `_generate_factors`, `_add_factor_performance` 等）。
- 通过 `LatentFactorDataSimulator.build_market_data()` 和 `generate_factors()` 获取测试数据。

1. 文档同步

- `docs/CODE_ARCHITECTURE.md`
- `docs/EVALUATION_STANDARDS.md`
- `docs/ITERATION3_SUMMARY.md`

## 2026-03-07 - 因子库迭代逻辑升级（A/B/C + OOS + 早停出库）

### 目标

- 按 `FACTOR_LIBRARY_EVAL_PROTOCOL.md` 将测试流程从“仅选择/更新”升级为“可收敛的因子库构建流程”。
- 输出可落地的最终因子库版本文件，供后续因子融合使用。

### 核心改动

1. `test_performance.py` 增加 C 类样本外评估

- 每轮对选中库做未来 `OOS_HORIZON=21` 天评估：
  - `oos_ic_mean`, `oos_icir`, `oos_ls_mean`, `oos_sharpe`, `oos_win_rate`
- 同时评估稳定性：
  - `overlap_prev`（Jaccard）
  - `turnover = 1 - overlap_prev`
  - `oos_excess_vs_prevlib`（本轮库 vs 上轮库，在同一未来窗口的LS均值差）

1. 早停判据与出库

- 连续窗口 `m=3` 满足以下条件触发早停：
  - `turnover <= 0.15`
  - `|Δoos_sharpe| <= 0.05`
  - `|Δoos_icir| <= 0.05`
  - `oos_excess_vs_prevlib >= -0.02`
- 触发即固化当前因子库；未触发则取最后一轮。

1. 最终因子库版本文件

- 每个场景输出：
  - `final_library.json`
- 内容包含：
  - 早停状态
  - 最终因子库日期/规模/因子ID
  - 各轮 OOS 与稳定性指标

1. 输出精简

- `BayesianSelectorV2` 新增 `verbose` 参数。
- 在测试入口中使用 `verbose=False`，不输出选中因子明细，仅保留关键统计。

### 验证

- 已完整运行多场景测试，流程正常：
  - A/B 指标、C类OOS指标、稳定性指标均输出
  - `final_library.json` 文件按场景生成

## 2026-03-07 - 多场景仿真对照实验（验证数据扰动对good选中率影响）

### 目标

- 在 `test_performance.py` 中引入多数据集仿真，对比以下变化是否影响 good 因子被选中概率：
  - 降低 `good -> good` 状态转移概率
  - 提高股票收益噪声（收益率 sigma）

### 代码修改

- 文件：`src/tests/test_performance.py`

1. 场景化配置与可控参数

- 新增配置项：
  - `RANDOM_SEED`
  - `SCENARIO_NAME`
  - `STOCK_RETURN_MU`
  - `STOCK_RETURN_SIGMA`
- `generate_stock_returns()` 支持 `mu/sigma` 参数化输入。

1. 多场景实验入口

- `main()` 改为运行 4 个场景并输出汇总表：
  - `baseline`：`good->good=0.80, sigma=0.0020`
  - `low_persist_good`：`good->good=0.60, sigma=0.0020`
  - `high_return_noise`：`good->good=0.80, sigma=0.0035`
  - `low_persist_and_noise`：`good->good=0.60, sigma=0.0035`

1. 指标增强（避免容量上限误导）

- 将场景实验的 `TARGET_SIZE` 设为 30（原 50），避免“总 good=20 导致总被选满”的上限效应。
- 新增指标：
  - `good_recall = 选中good数 / good总数`
  - 汇总输出 `avg_good_selection_rate` + `avg_good_recall`。

1. 跟踪输出

- 每个场景独立输出目录（tracker `run_tag` 带场景名）。

### 验证结果（本次运行）

- 汇总如下：
  - baseline: `avg_good_sel=63.33%`, `avg_good_recall=95.00%`
  - low_persist_good: `62.67%`, `94.00%`
  - high_return_noise: `61.33%`, `92.00%`
  - low_persist_and_noise: `62.00%`, `93.00%`
- 观察：
  - 增大噪声与降低 good 持续性后，good 选中率/召回率有下降趋势（幅度温和）。

## 2026-03-07 - 评估协议文档 + 模拟数据状态化升级

### 背景

- 为后续引入 A/B/C 三层标准、样本外评估与早停机制，需要先形成一份“无代码精确定义”协议。
- 同时，原测试数据中 good/medium/bad 因子长期过于静态，不利于验证“因子有效性会波动”的现实特征。

### 本次修改

1. 新增正式协议模板文档

- 新文件：`docs/FACTOR_LIBRARY_EVAL_PROTOCOL.md`
- 内容覆盖：
  - 每轮时间切分（lookback / OOS）
  - A/B/C 三类指标定义
  - 早停判据公式
  - 时间示例（按月滚动）
  - 仿真数据口径与复杂度控制原则

1. 升级模拟数据生成逻辑（`src/tests/test_performance.py`）

- 保留长期分类标签：`good_*/medium_*/bad_*`（用于长期倾向跟踪）。
- 引入按期潜在状态：每期状态可在 `good/medium/bad` 切换。
- 机制采用“锚定回归 + 状态转移”：
  - 既保证长期分类可区分（多数停留锚定状态）
  - 又允许短期失效/修复（有效性波动）
- `generate_factor_values()` 支持按期输入 `target_ic` / `ic_std`（数组），不再限制固定均值与固定波动。
- 每个因子附加 `simulation_profile`（锚定分类、状态占比）便于后续分析。

1. 文档同步（按 AI_CONTEXT 强制规则）

- 更新：`docs/CODE_ARCHITECTURE.md`
- 更新：`docs/EVALUATION_STANDARDS.md`
- 更新：`docs/ITERATION3_SUMMARY.md`
- 更新：`AI_CONTEXT.md`（新增协议文档到主要文件列表）

### 验证结果

- `python3 -u src/tests/test_performance.py` 运行通过。
- 输出显示更符合“有效性波动”预期：
  - 每轮仍以 good+medium 为主，但 bad 因子有一定概率被选中（约 10%~16%）。
  - 不再出现“结构过于僵化”的现象。

## 2026-03-07 - 因子选择规则澄清与全量跟踪模块

### 用户问题与结论

- 问题：`test_performance.py` 每轮看起来“只选中 good 因子”，是打印口径问题还是程序逻辑问题。
- 结论：不是“只输出前几名导致误解”。当前配置下每轮实际常见为 `20 good + 30 medium + 0 bad`（目标选 50，因子总数 100，其中 good=20、medium=30、bad=50）。
- 原因：`select_factors()` 是按全体候选因子 `final_score` 降序取 Top-K（K=50）；不是只打印前几个。打印“前5个选中因子”仅是展示，不影响真实选中集合。

### 当前程序中“选中/成功”的判定规则（详细）

1. 选中规则（`src/core/bayesian_selector_v2.py`）

- 对每个因子计算：
  - `aggregate_score`: 多窗口综合分（来自 `EnhancedFactor.get_aggregate_score`）。
  - `bayesian_score`: `Beta(alpha, beta)` 的一次采样（Thompson Sampling）。
  - `final_score = 0.7 * aggregate_score + 0.3 * bayesian_score`。
- 将全部因子按 `final_score` 降序排序，取前 `target_size` 个作为选中因子。

1. 选中因子是否“成功”（`_evaluate_selected_success`）

- 评估窗口：默认看最近 `selected_short=10` 天（配置文件）。
- 若有效表现数据不足 5 条，直接失败。
- 计算：
  - `icir = mean(IC) / std(IC)`（最近窗口）。
  - `ls_stats = {sharpe, win_rate, ...}`（最近窗口的多空收益统计）。
  - `rank_percentile` 从 `performance_data[fid]['rank_percentile']` 读取（在 `test_performance.py` 中按“当轮选中集合的 ICIR 排名”构造，0最好，1最差）。
- 成功需同时满足（AND）：
  - `icir > 0.8`
  - `ls_stats['sharpe'] > 0`
  - `rank_percentile < 0.7`
  - `win_rate > 0.55`

1. 未选中因子是否“成功”（边际贡献）

- 对每个未选中因子运行 `MarginalContributionEvaluator.evaluate_factor`。
- 先通过组合模拟得到边际改善 `improvement`、相关性、是否可替换等，再形成综合分 `score`。
- 判定：
  - `SUCCESS`: `score >= min_score_for_success(默认0.7)` 且 `improvement > 0` 且 `max_correlation <= 0.6`
  - `FAILURE`: `score < 0.3` 或 `improvement < -0.1` 或 `max_correlation > 0.72`
  - 其他为 `NEUTRAL/UNCERTAIN`
- 贝叶斯更新：
  - 未选中 `SUCCESS`：按 `unselected_success` 权重更新（默认 `alpha += 0.5`）。
  - 未选中 `FAILURE`：按 `unselected_failure` 权重更新（默认 0，即通常不惩罚）。
  - `NEUTRAL/UNCERTAIN`：不更新。

### 新增模块与输出文件

1. 新增模块

- `src/evaluation/library_tracker.py`
- 作用：
  - 每轮统计选中结构（good/medium/bad）与成功结构。
  - 跟踪每个因子在每轮的状态：是否选中、是否成功、边际评估结果、更新前后 alpha/beta、分数与统计变量。
  - 汇总因子库整体绩效分布（ICIR/LS 均值与标准差，all vs selected）。

1. 接入位置

- `src/tests/test_performance.py`
  - 每轮更新前记录 `alpha/beta` 快照。
  - 更新后调用 tracker 记录轮次。
  - 控制台每轮新增输出：
    - `选中结构: good/medium/bad`
    - `选中成功结构: good/medium/bad`
  - 测试结束自动导出文件路径。

1. 输出文件（默认目录 `outputs/performance_tracking/<run_tag>/`）

- `round_summary.csv`
  - 每轮汇总：`selected_good/medium/bad`、`selected_success_good/medium/bad`、`selected_failure_*`、`unselected_success_total` 等。
- `factor_round_status.csv`
  - 粒度：每轮 × 每个因子（一行一个因子）。
  - 关键列：
    - 状态：`selected`、`selected_success`、`unselected_evaluation`
    - 分数：`score_final`、`score_aggregate`、`score_bayesian`
    - 参数：`alpha_before/after`、`beta_before/after`、`success_rate_after`
    - 统计：`recent_icir_lookback`、`recent_ls_mean_lookback`、`recent_ls_sharpe_lookback`、`recent_win_rate_lookback`
    - 输入：`perf_rank_percentile_input`、`perf_icir_input`、`perf_ls_return_input`
- `library_metrics.json`
  - 每轮整体分布指标：
    - `all_factors`: ICIR/LS 的均值与标准差
    - `selected_factors`: ICIR/LS 的均值与标准差

## 2026-03-07 - test_performance 异常排查与修复

### 背景问题

- 运行 `src/tests/test_performance.py` 时，边际贡献评估阶段反复出现“因子收益率数据不存在”。
- 每轮 `selected_success` 很低（原始表现为接近 0），与模拟设定不匹配。

### 根因分析

1. 边际贡献评估数据传递缺失

- 在边际贡献评估调用组合模拟时，仅传入了“已选因子”的收益/ICIR字典，未传入候选因子的收益/ICIR。
- 在相关性替换路径中，候选因子被加入待构建组合后触发数据校验失败，报“收益数据不存在”。

1. 模拟 IC 生成逻辑导致 ICIR 失真

- `generate_factor_values()` 中使用 `rho = target_ic / ic_std`，并截断到 `0.99`，导致每期 IC 近似常数。
- IC 标准差趋近 0，`ICIR = mean/std` 在防除零逻辑下被压成 0，进而导致成功判定大量失败。

1. 评估 rank_percentile 的构造不合理

- `test_performance` 的 `performance_data` 中 `rank_percentile` 未按“当轮选中集合的相对名次”构造，导致阈值判定信息失真。

### 修改逻辑

1. 修复边际贡献评估的数据闭环

- 在 `_simulate_portfolios()` 中合并“候选因子 + 已选因子”的收益与 ICIR，再统一传给组合模拟器。
- 目标是保证替换评估路径的数据完整性。

1. 修复模拟 IC 序列生成

- 改为按期采样 `rho_t ~ N(target_ic, ic_std)`，并裁剪到 `[-0.99, 0.99]`。
- 逐期构造 `F_t = rho_t * R_t + sqrt(1-rho_t^2) * Z_t`，保留目标均值并引入合理波动。

1. 修复测试评估中的 rank_percentile

- 在 `_evaluate_selected_factors()` 中先计算当轮选中因子的 ICIR，再按 ICIR 降序生成相对 `rank_percentile`（0最好，1最差）。

### 涉及代码文件

- `src/evaluation/marginal_contrib.py`
  - `_simulate_portfolios()`：传入完整 `all_returns` / `all_icirs`（含候选因子）。
- `src/tests/test_performance.py`
  - `generate_factor_values()`：按期采样 rho，修复 IC 动态生成。
  - `_evaluate_selected_factors()`：按当轮相对排序生成 `rank_percentile`。

### 验证结果

- 原告警“因子收益率数据不存在”不再出现。
- `test_performance` 中更新成功率由原先接近 0 提升到稳定水平（本次验证约 70%）。

## 2026-03-09 - 模拟数据导出为真实数据格式（可选）

### 目标

- 在不改变当前实验主流程的前提下，为 `simulation` 增加“可选写盘”能力。
- 导出文件结构对齐真实数据接入接口，便于后续直接做 `mock -> real` 切换联调。

### 实现内容

1. `src/simulation/latent_factor_data_simulator.py`

- 新增内部缓存：
  - 最近一次 `dates/stock_returns/forward_returns`
  - 每个因子的截面暴露矩阵（`factor_id -> [stock, signal_date]`）
- 新增方法 `export_as_real_data_format(...)`，可输出：
  - `base/daily_returns.csv`：`end_date, stock_code, rtn`
  - `factors/<factor_id>.csv`：`end_date, stock_code, score`
  - `pools/<pool_name>.csv`：`end_date, stock_code, in_pool`
  - `labels/forward_returns_h{window}.csv`（可选）：`end_date, label_start_date, label_end_date, stock_code, forward_rtn`
  - `meta/simulation_manifest.json`（导出清单与关键元信息）
- 时间对齐说明写入 manifest：
  - `x(t)` 对应 `R(t+1->t+n)`，不包含 t 日收益。

1. `src/workflows/factor_library_iteration_engine.py`

- 增加可选导出触发：
  - `EXPORT_SIM_DATA_AS_REAL_FORMAT`
  - `EXPORT_SIM_OUTPUT_ROOT`
  - `EXPORT_SIM_POOL_NAME`
  - `EXPORT_SIM_INCLUDE_FORWARD_LABELS`
- 导出路径按场景自动分目录，避免多场景覆盖：
  - `{EXPORT_SIM_OUTPUT_ROOT}/{SCENARIO_NAME}/...`
- 导出结果路径写入 `results["sim_data_export"]`。

1. `src/experiments/factor_library_scenario_experiment.py`

- `PerformanceTestConfig` 新增上述导出参数（默认关闭）。

1. 实验入口参数

- `src/tests/test_performance.py` 新增：
  - `--export-sim-data`
  - `--export-root`
  - `--export-pool`
  - `--no-export-labels`
- `src/tests/experiment_phase_regime_comparison.py` 与
`src/experiments/phase_regime_comparison_experiment.py` 同步新增对应参数透传。

### 验证

- 通过命令（baseline-only 小样本）验证成功写盘：
  - `python3 -u src/tests/test_performance.py --baseline-only --seed 7 --num-stocks 120 --num-factors 20 --target-size 8 --num-days 180 --horizon-days 5 --export-sim-data --export-root data/simulated --export-pool hs300 --annual-days 250`
- 生成目录示例：
  - `data/simulated/baseline/base/daily_returns.csv`
  - `data/simulated/baseline/factors/good_000.csv`（每因子一个文件）
  - `data/simulated/baseline/pools/hs300.csv`
  - `data/simulated/baseline/labels/forward_returns_h5.csv`
  - `data/simulated/baseline/meta/simulation_manifest.json`

## 2026-03-09 - 新增“独立数据生成入口 + 真实数据单场景入口”

### 新增文件

1. `src/tests/experiment_generate_sim_data.py`

- 仅负责生成模拟数据并写入本地，不运行因子库迭代。
- 主要参数：
  - `--num-stocks --num-days --num-factors --horizon-days`
  - `--output-root --pool-name`
  - `--no-labels`

1. `src/data/real_data_loader.py`

- 负责从真实格式目录读取：
  - `base/daily_returns.csv`
  - `factors/*.csv`
  - `pools/<pool>.csv`（可选）
- 输出统一对齐后的面板矩阵：
  - `returns [stock, date]`
  - `in_pool [stock, date]`
  - `factor_scores[factor_id] [stock, date]`

1. `src/workflows/real_data_iteration_engine.py`

- 新建 `RealDataIterationEngine`，继承 `FactorLibraryIterationEngine`。
- 复用主迭代流程，仅重写 `_prepare_data()`：
  - 从文件夹读真实数据
  - 计算 `R(t+1->t+n)`
  - 构建每个因子的 `EnhancedFactor.performance_history`

1. `src/tests/experiment_real_data_single.py`

- 真实数据单场景入口（无场景对比）。
- 主要参数：
  - `--daily-returns --factors-dir --pool-file`
  - `--target-size --horizon-days --update-frequency`
  - `--train-ratio --validation-ratio --test-ratio`
  - `--eval-mode --num-test-rounds`

### 复用性改造

- `src/workflows/factor_library_iteration_engine.py`
  - 抽出 `_prepare_data()`（默认模拟数据实现）以支持子类覆写。
  - `REAL_DATA_MODE=True` 时，打印真实数据来源路径，避免显示模拟参数误导。

### 验证

- 已验证闭环：
  1. 用 `experiment_generate_sim_data.py` 生成文件；
  2. 用 `experiment_real_data_single.py` 从该目录读取并跑完整迭代成功。

## 2026-03-09 - 进度条与标签可得性边界控制

### 1) 模拟数据进度显示（可选）

- `src/simulation/latent_factor_data_simulator.py`
  - 新增 `show_progress` 配置。
  - 因子生成、潜在状态转移、写出 base/pools/factors/labels 时支持进度条。
  - 若环境存在 `tqdm` 则显示；不存在时自动退化为无进度条（不报错）。

### 2) 新增切分间隔参数（防边界泄露）

- `src/experiments/factor_library_scenario_experiment.py`
  - 新增 `SPLIT_GAP_DAYS`（默认 `None`，运行时按 `ROLLING_WINDOW` 解释）。
- `src/workflows/factor_library_iteration_engine.py`
  - `train/validation/test` 切分新增 gap：
    - train 与 validation 之间插入 `gap_days`
    - validation 与 test 之间插入 `gap_days`
  - 目的：避免边界附近标签窗口跨区间污染。
  - `scenario_params` 输出新增 `split_gap_days`。

### 3) 测试入口参数新增

- `src/tests/test_performance.py`
  - `--split-gap-days`
  - `--progress`
- `src/tests/experiment_phase_regime_comparison.py`
  - `--split-gap-days`
  - `--progress`
- `src/experiments/phase_regime_comparison_experiment.py`
  - 同步透传 `split_gap_days/show_progress`
- `src/tests/experiment_generate_sim_data.py`
  - 新增 `--progress`
- `src/tests/experiment_real_data_single.py`
  - 新增 `--split-gap-days`

### 4) 标签计算口径确认

- 继续采用“可一次性预计算前瞻标签”的工程实现。
- 规范要求：训练/更新/验证时必须满足标签可得性边界，且边界由 `split_gap_days` 隔离，避免未来数据泄露。

## 2026-03-09 - 新增 as-of 可得性过滤模式

### 功能

- 在每轮评估中引入 `asof_date = tau_r`（本轮决策日期）。
- 当 `ENABLE_ASOF_FILTER=True` 时，仅统计 `performance.date <= asof_date` 的标签样本。
- 适用于模拟线上日滚动可得性约束。

后续语义收敛（2026-03-09）:

- 最终收敛为单一语义：
  - `ENABLE_ASOF_FILTER=True` 时固定使用本次运行截止日 `T` 作为 asof。
  - 不再暴露 `round_date` 入口参数，避免离线出库场景误用。

### 代码变更

- `src/workflows/factor_library_iteration_engine.py`
  - `_evaluate_oos_library_on_date_range(..., asof_date=None)`
  - `_evaluate_oos_library_forward(..., asof_date=None)`
  - 每轮 `round_metric` 新增 `asof_date`
  - `round_compact_summary.csv` 新增 `asof_date` 列
- 配置项：
  - `PerformanceTestConfig.ENABLE_ASOF_FILTER`（默认 `False`）
- 入口参数：
  - `test_performance.py --asof-filter`
  - `experiment_phase_regime_comparison.py --asof-filter`
  - `experiment_real_data_single.py --asof-filter`

### 说明

- “一次性预计算标签”与“未来数据泄露”并不矛盾；
- 关键在使用阶段是否按 `asof_date` 过滤标签可得性。

## 2026-03-09 - 多asof滚动出库（真实场景）

### 新增能力

- 支持“指定单个/多个 asof_date，独立生成最终因子库并做跨日期对比”。
- 适用于生产场景中的定时出库（单日时即为 daily run）。

### 代码新增

1. `src/workflows/asof_library_generator.py`

- `AsOfRollingConfig` + `AsOfLibraryGenerator`
- 对每个 asof 独立调用 `RealDataIterationEngine`
- 导出：
  - `asof_library_summary.csv`
  - `asof_library_overlap.csv`
  - `asof_library_seq_turnover.csv`
  - `asof_library_factors.json`

1. `src/tests/experiment_real_data_asof_rolling.py`

- 支持两种 asof 输入：
  - `--asof-dates`（显式列表）
  - `--asof-start/--asof-end/--asof-step-days`（交易日步进生成）

### 相关增强

- `src/workflows/real_data_iteration_engine.py`
  - 新增 `REAL_DATA_ASOF_DATE + REAL_DATA_LOOKBACK_DAYS` 切片能力
  - 非交易日 asof 自动对齐到最近不晚于asof的交易日
- `src/workflows/factor_library_iteration_engine.py`
  - `_build_dataset_split` 修复：先扣除 split gap 再按比例切分，兼容 `test_ratio=0`
  - 结果中补充 `data_window`（window_start/window_end/effective_asof_date）

### 后续修订

- 新增 `--output-dir`（`experiment_real_data_asof_rolling.py`）：
  - 允许汇总产物输出到固定目录，便于日报/调度系统接入。
- 修复“asof滚动场景下 OOS=0”体验问题：
  - 在该场景中 `asof_filter` 默认参考固定 `effective_asof_date=T`（而非每轮`tau_r`），
  使每轮验证统计在T时点可得，避免全零。

## 2026-03-09 - 硬编码参数化与配置标注补充

### 已参数化

- `src/core/bayesian_selector_v2.py`
  - 因子综合分与Thompson采样混合权重由硬编码 `0.7/0.3` 改为配置驱动：
    - `bayesian.selection_blend.aggregate_score`
    - `bayesian.selection_blend.bayesian_score`
- `src/evaluation/marginal_contrib.py`
  - 未选中因子边际贡献评估中的评分权重/分段阈值/失败判据由硬编码改为配置驱动：
    - `marginal_contribution.scoring.weights.*`
    - `marginal_contribution.scoring.grade_scores.*`
    - `marginal_contribution.scoring.quality_thresholds.*`
    - `marginal_contribution.scoring.feasibility_scores.*`
    - `marginal_contribution.scoring.correlation_low_ratio`
    - `marginal_contribution.scoring.decision_*`

## 2026-03-09 - 年化常数统一与配置精简

### 年化常数统一

- `src/core/factor_enhanced.py`
  - 将 `sqrt(252)` 与 `ls_return * 252` 改为从因子配置读取：
    - `annualization_days`（默认250）
- `src/evaluation/portfolio_simulator.py`
  - 默认 `annualization_factor` 从 `252` 调整为 `250`。
- `src/core/bayesian_selector_v2.py`
  - 初始化时读取 `evaluation_config.yaml` 的 `annualization_days`；
  - 强制将 `marginal_contribution.annualization_factor` 与全局 `annualization_days` 对齐；
  - 在 `add_factor()` 时为每个因子注入：
    - `annualization_days`
    - `ic_min_periods`

### IC最小样本数语义对齐

- `src/core/factor_enhanced.py`
  - `calculate_icir()` 最小有效样本由硬编码5改为配置驱动 `ic_min_periods`（默认10）。

### 配置精简（减少歧义）

- `config/evaluation_config.yaml`
  - 新增全局 `annualization_days: 250`
  - 删除主流程未使用字段：
    - `time_windows.evaluation.unselected_short`
    - `time_windows.ic_calculation.rolling_window`
    - `indicator_weights.evaluation.*`
    - `success_thresholds.*` 中未接入判定的字段
    - `normalization.*`
  - 保留并明确主流程使用字段（selection权重、selected阈值、unselected相关性阈值、marginal_contribution.scoring等）。
- `src/utils/config_manager.py`
  - 默认配置结构同步精简；
  - 阈值校验改为“按字段存在性校验”，兼容精简配置；
  - `print_summary()` 兼容可选阈值字段，避免None格式化报错。

## 2026-03-09 - 参数映射文档与标准文档对齐

- 新增 `docs/PARAMETER_MAPPING.md`
  - 以“参数-默认值-代码位置-作用”方式列出当前主流程有效参数。
  - 区分 `evaluation_config.yaml` 参数与引擎级参数（如 `ROLLING_WINDOW/ANNUAL_DAYS`）。
- 重写 `docs/EVALUATION_STANDARDS.md`
  - 清理过时字段（如未接入的 evaluation 权重/阈值描述）
  - 明确 `min_periods` 含义：最小样本门槛，不是窗口长度
  - 明确当前 A/B/C 判定与年化口径一致性
- 更新 `# AI_CONTEXT.md`
  - 文档清单与同步规则新增 `docs/PARAMETER_MAPPING.md`

## 2026-03-09 - 年化参数单一来源化（移除双入口）

### 变更目标

- 取消引擎侧 `ANNUAL_DAYS/--annual-days` 链路，避免与 `evaluation_config.yaml` 双轨并存。
- 全流程统一读取 `annualization_days`（单一来源）。

### 代码变更

- 删除实验配置字段 `PerformanceTestConfig.ANNUAL_DAYS` 及相关赋值链路。
- 删除测试入口参数 `--annual-days`：
  - `src/tests/test_performance.py`
  - `src/tests/experiment_phase_regime_comparison.py`
  - `src/tests/experiment_real_data_single.py`
  - `src/tests/experiment_real_data_asof_rolling.py`
- 删除实验/工作流中 annual_days 透传：
  - `src/experiments/phase_regime_comparison_experiment.py`
  - `src/workflows/asof_library_generator.py`
  - `src/experiments/factor_library_stability_experiment.py`
- 引擎初始化 selector 改为不注入年化覆盖值：
  - `src/workflows/factor_library_iteration_engine.py`
- 引擎年化计算改为读取 `self.selector.annualization_days`。

### 文档同步

- 完整同步并去除双参数表述：
  - `docs/EVALUATION_STANDARDS.md`
  - `docs/PARAMETER_MAPPING.md`
  - `docs/CODE_ARCHITECTURE.md`
  - `docs/ITERATION3_SUMMARY.md`
  - `docs/example.md`
  - `docs/REAL_DATA_INTEGRATION_GUIDE.md`

### 备注

- 引擎运行日志现在显示：
  - 年化天数 = 从 `config/evaluation_config.yaml` 读取到的 `annualization_days`。

### 配置文件注释补充

- `config/evaluation_config.yaml`
  - 对当前未直接使用字段增加显式注释：
    - `time_windows.evaluation.unselected_short`
    - `time_windows.ic_calculation.rolling_window`
    - `indicator_weights.evaluation.*`
    - `success_thresholds.selected.ls_return_annual`
    - `success_thresholds.unselected.icir/ls_return_annual/rank_percentile/win_rate`
    - `marginal_contribution.simulation_method`
    - `marginal_contribution.portfolio_methods`
    - `normalization.*` 区块
