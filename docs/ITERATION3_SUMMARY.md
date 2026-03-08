# 迭代3总结（当前落地版本）

## 概述
迭代3已落地为“多指标 + 多时间窗口 + 边际贡献评估 + 全量跟踪输出”的闭环框架。

更新时间: 2026-03-07

## 当前能力

### 1. 因子选择（Top-K）
- 模块: `src/core/bayesian_selector_v2.py`
- 公式:
- `final_score = 0.7 * aggregate_score + 0.3 * bayesian_score`
- `bayesian_score` 来自 `Beta(alpha, beta)` 采样（Thompson Sampling）
- 对全体候选按 `final_score` 排序取 Top-K（不是只看打印的前几个）

### 2. 选中因子更新
- 模块: `BayesianSelectorV2._evaluate_selected_success`
- success 条件（AND）:
- `icir > 0.8`
- `ls_sharpe > 0`
- `rank_percentile < 0.7`
- `win_rate > 0.55`
- 更新权重（默认）:
- success: `alpha += 1.0`
- failure: `beta += 1.0`

### 3. 未选中因子更新（边际贡献）
- 模块: `src/evaluation/marginal_contrib.py`
- 输出分类: `SUCCESS/FAILURE/NEUTRAL/UNCERTAIN`
- 判定核心:
- SUCCESS: `score >= 0.7` 且 `improvement > 0` 且 `max_correlation <= 0.6`
- FAILURE: `score < 0.3` 或 `improvement < -0.1` 或 `max_correlation > 0.72`
- 更新权重（默认）:
- unselected success: `alpha += 0.5`
- unselected failure: `beta += 0.0`（通常不惩罚）

### 4. 因子库跟踪与导出（新增）
- 模块: `src/evaluation/library_tracker.py`
- 接入: `src/tests/test_performance.py`
- 每轮新增可见输出:
- `选中结构: good/medium/bad`
- `选中成功结构: good/medium/bad`
- 导出文件:
- `outputs/performance_tracking/<run_tag>/round_summary.csv`
- `outputs/performance_tracking/<run_tag>/factor_round_status.csv`
- `outputs/performance_tracking/<run_tag>/library_metrics.json`
- `outputs/performance_tracking/<run_tag>/final_library.json`

### 5. 模拟数据机制（更新）
- 模块: `src/simulation/latent_factor_data_simulator.py`
- 设计:
- 保留长期分类标签（good/medium/bad）
- 引入按期潜在状态（good/medium/bad）切换
- 通过“锚定回归 + 状态转移”让因子有效性随时间波动
- 目的:
- 避免“好因子永远好”的过度理想化假设
- 在可控复杂度下检验因子库迭代逻辑的鲁棒性

### 6. 因子库迭代逻辑（更新）
- 每轮 C 类样本外评估改为固定 validation 集评估（不参与更新）：
- `oos_icir`, `oos_ls_mean`, `oos_sharpe`, `oos_win_rate`
- 每轮新增稳定性指标：
- `overlap_prev`, `turnover`, `oos_excess_vs_prevlib`
- 引入早停判据（连续窗口）用于“收敛出库”：
- 满足阈值则提前停止迭代并固化当轮因子库
- 最终因子库固化规则：
- 早停触发 -> 取触发轮
- 未触发 -> 取最后一轮
- 数据切分参数支持：
- `TRAIN_RATIO / VALIDATION_RATIO / TEST_RATIO`（测试集可为0）
- 评估模式支持：
- `strict_holdout` 与 `walk_forward_test`
- 当 `NUM_TEST_ROUNDS=None` 时，迭代可自动跑到目标区间末尾（非固定24轮）
- `strict_holdout` 出库策略升级：
- 不做早停截断训练；按每轮 `stability_pass` 筛选后取 Validation 最优 `S_r`
- 并输出最后一轮 `S_T` 作为对照
- `walk_forward_test` 仍保留早停策略

### 7. 架构分层（更新）
- `src/tests/test_performance.py` 仅保留实验入口职责
- `src/tests/experiment_stability_early_stop.py` 作为长周期稳定性实验入口
- `src/tests/experiment_phase_regime_comparison.py` 作为分阶段状态转移对照实验入口
- 两个入口均支持核心规模参数覆盖：
- `num_stocks / num_factors / target_size / num_days`
- 可复用流程类已抽离：
- `src/workflows/factor_library_iteration_engine.py`（单场景迭代引擎）
- `src/experiments/factor_library_scenario_experiment.py`（多场景对比）
- `src/experiments/factor_library_stability_experiment.py`（稳定性收敛实验与可视化）
- 模拟数据逻辑位于：
- `src/simulation/latent_factor_data_simulator.py`
- 历史MVP模块已归档至：
- `src/core/__archive/`
- `src/simulation/__archive/`

### 8. 稳定性可视化输出（新增）
- 长周期实验会额外导出：
- `stability_convergence.svg`
- `stability_report_*.json`
- 核心观察维度：
- 因子库稳定性：`overlap_prev`, `turnover`
- 样本外表现：`oos_sharpe`, `oos_icir`, `oos_ls_mean`
- 收敛信号：`convergence_index`（按早停条件归一化）
- 引擎自动输出 `validation_dynamics.svg`：
- 标注 `stability_pass` 轮次与最终出库轮次，便于观察训练结束后验证指标动态。
- 引擎可输出 `test_dynamics.svg`（当存在test集）：
- 显示每轮 test 的 `ICIR/Sharpe/rtn` 轨迹，并标注最终与最后一轮。
- 引擎可输出 `round_compact_summary.csv`：
- 每轮验证/测试关键指标 + `stability_pass` + 最终/最后轮次标记。

### 9. 多空收益口径（更新）
- 模拟中的因子多空收益不再使用 `topq-bottomq`。
- 采用因子加权多空：
- 多头权重 `w+ ∝ max(x,0)`，空头权重 `w- ∝ max(-x,0)`
- 归一化后满足 `sum(w+)=1`、`sum(w-)=1`（总杠杆2x）

## 本轮（2026-03-07）关键修订
- 新增 `FactorLibraryTracker`，支持“轮次级 + 因子级 + 全库级”三层跟踪。
- `UpdateResult` 新增 `marginal_details`，保存未选中因子边际评估明细。
- `test_performance.py` 已接入跟踪模块并自动导出输出文件。
- 文档中的 success 规则统一为当前代码逻辑（选中因子条件含 `sharpe > 0`，而非年化收益阈值）。

## 结果解读口径
- 若看到“前5个选中因子几乎都是 good”，只是展示片段。
- 应以 `round_summary.csv` 的 `selected_good/selected_medium/selected_bad` 为每轮真实结构口径。
- 单因子逐轮状态与统计值以 `factor_round_status.csv` 为准。

## 维护约束
未来若发生架构、阈值、参数、输出字段变化，必须同步更新:
- `docs/CODE_ARCHITECTURE.md`
- `docs/EVALUATION_STANDARDS.md`
- `docs/ITERATION3_SUMMARY.md`

评估流程与早停规范见:
- `docs/FACTOR_LIBRARY_EVAL_PROTOCOL.md`

补充:
- 协议已升级至 Draft v2，明确目标时序为:
- `Observe/Update(基于新观测) -> Select -> Validate`
- 后续代码改造应按该时序对齐，确保不存在未来数据泄露。
- 信号收益配对按 `x(t)` -> `R(t+1->t+n)`（不含t当日收益）。
