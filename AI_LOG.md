# Codex Modification Log

## 2026-03-09 - phase_regime 增加 seed + 模块归档审阅 + 真实数据接入文档

### 修改
1. `experiment_phase_regime_comparison` 增加 seed 参数
- `src/tests/experiment_phase_regime_comparison.py` 新增 `--seed`
- `src/experiments/phase_regime_comparison_experiment.py` 增加 `seed` 参数并映射到 `cfg.RANDOM_SEED`

2. 模块归档整理
- 移动到归档目录：
  - `src/core/mvp_selector.py` -> `src/core/__archive/mvp_selector.py`
  - `src/core/integrated_selector.py` -> `src/core/__archive/integrated_selector.py`
  - `src/simulation/stock_simulator.py` -> `src/simulation/__archive/stock_simulator.py`
- `src/__init__.py` 改为导出当前主链路模块（`bayesian_selector_v2 / factor_enhanced / latent_factor_data_simulator`）

3. 新增真实数据接入文档
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

2. OOS年化输出
- 文件：`src/workflows/factor_library_iteration_engine.py`
- `oos_icir/oos_sharpe/oos_ls_mean` 改为年化口径输出
- 同时保留原始值字段（`*_raw`）用于稳定性判据与delta计算

3. round_compact 分位点
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

2. 场景对比汇总增强
- 文件：`src/experiments/factor_library_scenario_experiment.py`
- 汇总表新增 `avg_ls_rtn`（平均多空收益率）
- 新增场景汇总CSV导出：
  - `outputs/performance_tracking/scenario_comparison_summary_<ts>.csv`
- 默认对比场景调整为3个（baseline / low_persist_good / high_return_noise）

3. 每轮紧凑CSV
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

2. 轮次标记增强
- 橙色实心圆：`selected_round`（最终出库轮次）
- 蓝色方块：`last_round`（最后一轮对照）
- 绿色空心圆：`stability_pass=True` 轮次
- 图标题新增 `stable rounds: x/total` 统计

3. 新增测试集动态图
- 新文件输出：`test_dynamics.svg`（当 `TEST_RATIO>0`）
- 每轮显示：
  - `test_oos_icir`
  - `test_oos_sharpe`（基于多空收益序列）
  - `test_oos_ls_mean`（test rtn）

4. 引擎接入
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

2. 最终选库逻辑分模式
- `strict_holdout`:
  - 在 `stability_pass=True` 的轮次中选 Validation 最优（Sharpe优先，ICIR次级）`S_r`
  - 若无通过轮次，回退为全轮次 Validation 最优
  - 同时输出最后一轮库作为对照
- `walk_forward_test`:
  - 保留早停逻辑

3. 输出增强
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

2. tests 入口
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

2. 轮次控制升级
- `NUM_TEST_ROUNDS` 支持 `None`
- 为 `None` 时不截断轮次，自动迭代到目标区间末尾

3. 分阶段状态转移（模拟器）
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

2. 固定验证集OOS评估
- 文件：`src/workflows/factor_library_iteration_engine.py`
  - 新增 `_build_dataset_split()`，按比例切分 train/validation/test。
  - 选择轮次仅在 train 区间内执行。
  - OOS评估改为 `_evaluate_oos_library_on_validation()`，每轮在同一 validation 区间评估。
  - 日志从“未来21天”改为“固定验证集起止日期”。
  - `results/final_library.json` 新增 `dataset_split` 元数据。

3. 模拟多空收益口径改造
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

2. 迭代顺序改造（B前置）
- 文件：`src/workflows/factor_library_iteration_engine.py`
- 每轮改为：
  - 先用 `(t_{r-1}, t_r]` 新信息更新上一轮选中库（B）
  - 再在 `t_r` 选本轮库（A）
- 控制台输出同步调整：
  - 当前轮输出 `选中结构`
  - 额外输出 `上轮更新成功结构`

3. 跟踪器字段补充
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

2. 同步说明文档
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

2. 新增稳定性实验入口（tests 仅保留入口）
- 新文件：`src/tests/experiment_stability_early_stop.py`
- 作用：运行长历史实验并打印输出产物路径。

3. 新增可视化与报告输出
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

4. 文档同步（按 AI_CONTEXT 强制规则）
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

2. 新增实验管理层
- 新文件：`src/experiments/factor_library_scenario_experiment.py`
- 提供：
  - `PerformanceTestConfig`
  - `build_scenario()`
  - `ScenarioComparator`（多场景批量对比）

3. tests入口精简
- `src/tests/test_performance.py` 改为纯入口脚本：
  - 构建默认场景
  - 调用 `ScenarioComparator.run()`

4. tests目录清理与命名优化
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

2. 精简测试入口
- 文件：`src/tests/test_performance.py`
- 删除/迁移了原有数据模拟函数与模拟内部方法（如 `_generate_factors`, `_add_factor_performance` 等）。
- 通过 `LatentFactorDataSimulator.build_market_data()` 和 `generate_factors()` 获取测试数据。

3. 文档同步
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

2. 早停判据与出库
- 连续窗口 `m=3` 满足以下条件触发早停：
  - `turnover <= 0.15`
  - `|Δoos_sharpe| <= 0.05`
  - `|Δoos_icir| <= 0.05`
  - `oos_excess_vs_prevlib >= -0.02`
- 触发即固化当前因子库；未触发则取最后一轮。

3. 最终因子库版本文件
- 每个场景输出：
  - `final_library.json`
- 内容包含：
  - 早停状态
  - 最终因子库日期/规模/因子ID
  - 各轮 OOS 与稳定性指标

4. 输出精简
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

2. 多场景实验入口
- `main()` 改为运行 4 个场景并输出汇总表：
  - `baseline`：`good->good=0.80, sigma=0.0020`
  - `low_persist_good`：`good->good=0.60, sigma=0.0020`
  - `high_return_noise`：`good->good=0.80, sigma=0.0035`
  - `low_persist_and_noise`：`good->good=0.60, sigma=0.0035`

3. 指标增强（避免容量上限误导）
- 将场景实验的 `TARGET_SIZE` 设为 30（原 50），避免“总 good=20 导致总被选满”的上限效应。
- 新增指标：
  - `good_recall = 选中good数 / good总数`
  - 汇总输出 `avg_good_selection_rate` + `avg_good_recall`。

4. 跟踪输出
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

2. 升级模拟数据生成逻辑（`src/tests/test_performance.py`）
- 保留长期分类标签：`good_*/medium_*/bad_*`（用于长期倾向跟踪）。
- 引入按期潜在状态：每期状态可在 `good/medium/bad` 切换。
- 机制采用“锚定回归 + 状态转移”：
  - 既保证长期分类可区分（多数停留锚定状态）
  - 又允许短期失效/修复（有效性波动）
- `generate_factor_values()` 支持按期输入 `target_ic` / `ic_std`（数组），不再限制固定均值与固定波动。
- 每个因子附加 `simulation_profile`（锚定分类、状态占比）便于后续分析。

3. 文档同步（按 AI_CONTEXT 强制规则）
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

2. 选中因子是否“成功”（`_evaluate_selected_success`）
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

3. 未选中因子是否“成功”（边际贡献）
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

2. 接入位置
- `src/tests/test_performance.py`
  - 每轮更新前记录 `alpha/beta` 快照。
  - 更新后调用 tracker 记录轮次。
  - 控制台每轮新增输出：
    - `选中结构: good/medium/bad`
    - `选中成功结构: good/medium/bad`
  - 测试结束自动导出文件路径。

3. 输出文件（默认目录 `outputs/performance_tracking/<run_tag>/`）
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

2. 模拟 IC 生成逻辑导致 ICIR 失真
- `generate_factor_values()` 中使用 `rho = target_ic / ic_std`，并截断到 `0.99`，导致每期 IC 近似常数。
- IC 标准差趋近 0，`ICIR = mean/std` 在防除零逻辑下被压成 0，进而导致成功判定大量失败。

3. 评估 rank_percentile 的构造不合理
- `test_performance` 的 `performance_data` 中 `rank_percentile` 未按“当轮选中集合的相对名次”构造，导致阈值判定信息失真。

### 修改逻辑
1. 修复边际贡献评估的数据闭环
- 在 `_simulate_portfolios()` 中合并“候选因子 + 已选因子”的收益与 ICIR，再统一传给组合模拟器。
- 目标是保证替换评估路径的数据完整性。

2. 修复模拟 IC 序列生成
- 改为按期采样 `rho_t ~ N(target_ic, ic_std)`，并裁剪到 `[-0.99, 0.99]`。
- 逐期构造 `F_t = rho_t * R_t + sqrt(1-rho_t^2) * Z_t`，保留目标均值并引入合理波动。

3. 修复测试评估中的 rank_percentile
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
