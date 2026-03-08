# 评价标准与参数清单（Iteration3 当前实现）

更新时间: 2026-03-07
配置来源: `config/evaluation_config.yaml`
核心实现: `src/core/bayesian_selector_v2.py`, `src/evaluation/marginal_contrib.py`
协议文档: `docs/FACTOR_LIBRARY_EVAL_PROTOCOL.md`（Draft v2）
流程编排: `src/workflows/factor_library_iteration_engine.py`
稳定性实验: `src/experiments/factor_library_stability_experiment.py`

## 1. 三套评价标准

说明:
- 当前实现已对齐协议v2主时序：`Observe/Update -> Select -> Validate`。
- 每个 `tau_r` 先用 `(tau_{r-1}, tau_r]` 新信息更新后验，再选 `S_r`。
- 信号-标签配对口径: `x(t)` 对应 `R(t+1->t+n)`，不包含 `t` 当日收益。
- C层OOS采用固定验证集窗口（不参与alpha/beta更新），非滚动21天口径。

### 1.1 采样打分标准（用于选择）
- 目标: 在利用历史效果与探索不确定性之间平衡
- 计算:
- `aggregate_score`: 多窗口多指标得分
- `bayesian_score`: `Beta(alpha, beta)` 采样
- `final_score = 0.7 * aggregate_score + 0.3 * bayesian_score`
- 选择方式: 按 `final_score` 降序取 Top-K

### 1.2 判断成功（选中因子）
- 回看窗口: `time_windows.evaluation.selected_short`（默认 10）
- 最少有效数据: 5 条
- success 条件（AND）:
- `icir > success_thresholds.selected.icir`（默认 0.8）
- `ls_sharpe > 0`
- `rank_percentile < success_thresholds.selected.rank_percentile`（默认 0.7）
- `win_rate > success_thresholds.selected.win_rate`（默认 0.55）

说明:
- 这里 `rank_percentile` 在 `test_performance.py` 中按“本轮选中集合内 ICIR 排名”构造，0 最好，1 最差。

### 1.3 判断成功（未选中因子）
- 方式: 边际贡献评估（相关性 + 组合替换 + 候选质量）
- 输出: `SUCCESS/FAILURE/NEUTRAL/UNCERTAIN`
- 核心判定:
- SUCCESS: `score >= min_score_for_success(默认0.7)` 且 `improvement > 0` 且 `max_correlation <= max_correlation(默认0.6)`
- FAILURE: `score < 0.3` 或 `improvement < -0.1` 或 `max_correlation > 1.2 * max_allowed`

## 2. 更新规则（alpha/beta）

- 选中 success: `alpha += bayesian.update_rules.selected_success`（默认 +1.0）
- 选中 failure: `beta += bayesian.update_rules.selected_failure`（默认 +1.0）
- 未选中 success: `alpha += bayesian.update_rules.unselected_success`（默认 +0.5）
- 未选中 failure: `beta += bayesian.update_rules.unselected_failure`（默认 +0.0）
- 未选中 `NEUTRAL/UNCERTAIN`: 不更新

## 3. 默认参数（当前配置）

### 3.1 时间窗口
- 选择窗口: 5/20/60
- 评估窗口:
- selected: 10/20
- unselected: 20/40
- 数据集切分参数:
- `TRAIN_RATIO`（默认 0.7）
- `VALIDATION_RATIO`（默认 0.2）
- `TEST_RATIO`（默认 0.1，可设为0）
- 指标共享窗口参数:
- `ROLLING_WINDOW`（前瞻窗口n天，`x(t)->R(t+1->t+n)`，IC与LS共用）
- 年化参数:
- `ANNUAL_DAYS`（默认250）
- 评估模式参数:
- `EVAL_MODE`: `strict_holdout` 或 `walk_forward_test`
- 轮次参数:
- `NUM_TEST_ROUNDS`: 若为 `None`，迭代直到目标区间结束

### 3.2 选择指标权重
- `icir: 0.4`
- `ls_return: 0.3`
- `rank_percentile: 0.2`
- `stability: 0.1`

### 3.3 成功阈值
- selected:
- `icir: 0.8`
- `rank_percentile: 0.7`
- `win_rate: 0.55`
- unselected:
- `icir: 1.5`
- `rank_percentile: 0.5`
- `win_rate: 0.60`
- `max_correlation: 0.6`

## 4. 跟踪与评估输出标准（新增）

模块: `src/evaluation/library_tracker.py`

### 4.1 轮次级输出
- 文件: `round_summary.csv`
- 关键字段:
- `selected_good/selected_medium/selected_bad`
- `selected_success_good/selected_success_medium/selected_success_bad`
- `selected_failure_*`
- `unselected_success_total/unselected_failure_total`

### 4.2 因子级输出
- 文件: `factor_round_status.csv`
- 关键字段:
- 状态: `selected`, `selected_success`, `unselected_evaluation`
- 分数: `score_final`, `score_aggregate`, `score_bayesian`
- 参数: `alpha_before`, `beta_before`, `alpha_after`, `beta_after`
- 统计: `recent_icir_lookback`, `recent_ls_*`, `recent_win_rate_lookback`

### 4.3 全库级输出
- 文件: `library_metrics.json`
- 关键对象:
- `all_factors`: ICIR/LS 分布统计
- `selected_factors`: ICIR/LS 分布统计

### 4.4 最终因子库输出
- 文件: `final_library.json`
- 关键字段:
- `early_stop`（是否触发、触发轮次）
- `final_library`（最终库日期、规模、因子ID列表）
- `oos_metrics_by_round`（每轮C类指标与稳定性指标）

### 4.5 稳定性实验附加输出（长周期实验）
- 文件目录: `outputs/performance_tracking/<run_tag>/stability_experiment/`
- `stability_convergence.svg`:
- 曲线面板包括 `turnover/overlap`、`oos_sharpe/oos_icir`、`oos_ls_mean`、`convergence_index`
- `stability_report_*.json`:
- 包含上述曲线原始时序，及 `selected_good/medium/bad`、`selected_success_total` 等结构字段
- `convergence_index` 口径:
- 将早停各条件转为归一化尺度后取最大值（<=1 表示该轮达到或接近单轮早停阈值）

### 4.6 验证集动态曲线输出（引擎自动）
- 文件: `validation_dynamics.svg`
- 维度:
- Validation OOS: `oos_sharpe`, `oos_icir`
- 稳定性: `turnover`, `oos_excess_vs_prevlib`
- 变化幅度: `|Δoos_sharpe|`, `|Δoos_icir|`
- 图上标识:
- 绿色空心点：`stability_pass=True` 的轮次
- 橙色实心点：最终出库轮次

### 4.7 测试集动态曲线输出（引擎自动）
- 文件: `test_dynamics.svg`（仅 `TEST_RATIO>0` 时输出）
- 维度:
- `test_oos_icir`
- `test_oos_sharpe`（基于多空收益序列的Sharpe）
- `test_oos_ls_mean`（test rtn）
- 图上标识:
- 绿色空心点：`stability_pass=True` 的轮次（与Validation判据一致）
- 橙色实心点：最终出库轮次
- 蓝色方块：最后一轮轮次

### 4.8 轮次紧凑小表（CSV）
- 文件: `round_compact_summary.csv`
- 关键字段:
- `stability_pass`
- `is_selected_round`（最终出库轮次）
- `is_last_round`（最后一轮对照）
- `oos_icir/oos_sharpe/oos_ls_rtn`
- `test_oos_icir/test_oos_sharpe/test_oos_ls_rtn`
- `test_oos_icir_pct/test_oos_sharpe_pct/test_oos_ls_rtn_pct`（各轮test指标分位点）

## 5.1 年化口径（当前实现）
- 设 `n = ROLLING_WINDOW`，`A = ANNUAL_DAYS`，`ppy = A / n`
- `LS_rtn_annual = mean(LS_period_return) * ppy`
- `Sharpe_annual = (mean/std)_period * sqrt(ppy)`
- `ICIR_annual = (mean(IC)/std(IC)) * sqrt(ppy)`
- 注：稳定性判据中的 `ΔSharpe/ΔICIR` 使用未年化原始值，避免阈值失真。

## 5. OOS与早停（当前测试入口实现）

- OOS窗口: 固定 validation 区间（由 `TRAIN_RATIO/VALIDATION_RATIO/TEST_RATIO` 切分）
- `strict_holdout`: 固定validation区间
- `walk_forward_test`: 滚动未来 `OOS_HORIZON`，并迭代到test末尾（或val末尾）
- 每轮记录:
- `oos_ic_mean/oos_icir/oos_ls_mean/oos_sharpe/oos_win_rate`
- `overlap_prev/turnover`
- `oos_excess_vs_prevlib`
- 早停判据:
- 连续 `m=3` 轮满足
- `turnover <= 0.15`
- `|Δoos_sharpe| <= 0.05`
- `|Δoos_icir| <= 0.05`
- `oos_excess_vs_prevlib >= -0.02`
- 最终因子库规则:
- `strict_holdout`:
- 先计算每轮 `stability_pass`（由turnover/Δsharpe/Δicir/excess阈值判定）
- 在 `stability_pass=True` 轮次里取 Validation 最优 `S_r`
- 若无通过轮次，回退到全轮次 Validation 最优 `S_r`
- 同时输出“最后一轮库”作为对照
- `walk_forward_test`:
- 触发早停时：取触发轮因子库
- 未触发时：取最后一轮因子库

## 6. 模拟数据评价口径（测试专用）

- `good/medium/bad` 标签仅用于模拟数据真值对照，不用于真实市场评价。
- 当前模拟生成机制：
- 每个因子有长期锚定分类（good/medium/bad）
- 每期潜在状态可在三态间切换，状态决定当期IC参数
- 可选分阶段转移矩阵：
- `PHASE_TRANSITION_PROBS` 可按 `train/validation/test` 配置不同转移概率
- 因此“长期可区分 + 短期会波动”，用于检验因子库逻辑是否能处理有效性变化。
- 代码位置：`src/simulation/latent_factor_data_simulator.py`（已从 tests 目录抽离）
- 对照实验入口：`src/tests/experiment_phase_regime_comparison.py`

## 7. 变更同步要求
若出现以下变更，必须同步维护本文档:
- 成功判定逻辑变更
- 阈值/权重/窗口参数变更
- 跟踪输出字段变更
- 选择或更新流程变更
- 模拟数据机制变更（状态模型/参数映射）

同时必须同步更新:
- `docs/CODE_ARCHITECTURE.md`
- `docs/ITERATION3_SUMMARY.md`

补充:
- 多场景对比会导出 `scenario_comparison_summary_<timestamp>.csv`
- 字段包含 `avg_oos_ls_rtn`（平均多空收益率）与最终Validation/Test指标
- 实验入口支持规模参数覆盖：
- `num_stocks / num_factors / target_size / num_days`
- `experiment_phase_regime_comparison` 入口新增 `seed` 参数用于可重复实验
