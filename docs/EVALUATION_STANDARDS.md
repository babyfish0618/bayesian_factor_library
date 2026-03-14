# 评价标准（当前实现）

更新时间: 2026-03-14  
配置来源: `config/evaluation_config.yaml`  
参数映射: `docs/PARAMETER_MAPPING.md`

## 1. 时序与口径

- 轮次顺序: `Observe/Update -> Select -> Validate`。
- 信号标签: `x(t)` 仅用于 `R(t+1 -> t+n)`，不包含 `t` 当日收益。
- `n` 由 `ROLLING_WINDOW` 指定。
- Validation 集用于出库评估，不参与 `alpha/beta` 更新。

## 2. A/B/C 三层标准

### A. 选择标准（Select）
- 先计算 `aggregate_score`（多窗口多指标）
- 再采样 `bayesian_score ~ Beta(alpha, beta)`
- 最终分:  
  `final_score = w_agg * aggregate_score + w_bayes * bayesian_score`
- 多窗口 IC/ICIR 样本门槛（同时生效）：
- `time_windows.ic_calculation.min_periods_abs`
- `time_windows.ic_calculation.min_periods_ratio`
- 在每个窗口 `window` 上统一使用：
- `required_points = max(min_periods_abs, ceil(window * min_periods_ratio))`
- 当窗口内有效 IC 样本 `< required_points` 时，该窗口 ICIR 记为 `NaN`（不可计算）
- 当某窗口或某指标不可计算（如 ICIR 样本不足返回 `NaN`）时：
- 在窗口内先按“有效指标”重归一化指标权重；
- 在窗口间再按“有效窗口”重归一化窗口权重；
- 避免 `NaN` 传播污染 `final_score`。
- 其中权重来自:
- `bayesian.selection_blend.aggregate_score`
- `bayesian.selection_blend.bayesian_score`

### B1. 选中因子成功标准（Selected Success）
- 回看窗口: `time_windows.evaluation.selected_short`
- 样本门槛:
- `time_windows.ic_calculation.min_periods_abs`
- `time_windows.ic_calculation.min_periods_ratio`
- 动态门槛: `required_points = max(min_periods_abs, ceil(window * min_periods_ratio))`
- 同时满足:
- `icir > success_thresholds.selected.icir`
- `ls_sharpe > 0`
- `rank_percentile < success_thresholds.selected.rank_percentile`
- `win_rate > success_thresholds.selected.win_rate`

备注:
- 这里不是“IC窗口长度”，而是“最小有效样本数门槛”。
- 若回看窗口内有效 IC 样本 `< required_points`，本轮不判 success。

### B2. 未选中因子成功标准（Unselected Success）
- 评估输入窗口:
- `lookback = time_windows.evaluation.unselected_long`
- 数据充足性前置门槛:
- `correlation.min_common_periods`（不足直接判 `UNCERTAIN`）
- 其中候选与已选因子的 ICIR 计算同样遵循 A/B1 的双门槛（`min_periods_abs + min_periods_ratio`）。
- 组合构建与比较基准:
- 先构建当前已选库基准组合 `Baseline(S)`；
- 再按替换策略构建候选替换组合 `Replacement(S')`；
- 边际改善定义为 `improvement = Sharpe(Replacement) - Sharpe(Baseline)`。
- 组合方法由 `marginal_contribution.method` 决定（默认 `equal_weight`，也支持 `icir_weighted/sharpe_optimized/risk_parity/min_variance`）。
- 替换策略由 `marginal_contribution.replacement_strategy` 决定（默认 `correlation_based`）。
- 四种输出结果:
- `SUCCESS`: 应该被选中。条件同时满足
- `score >= marginal_contribution.scoring.decision_success_score`
- `improvement > 0`
- `max_correlation <= success_thresholds.unselected.max_correlation`
- `FAILURE`: 不应被选中。任一满足
- `score < marginal_contribution.scoring.decision_failure_score`
- `improvement < marginal_contribution.scoring.decision_failure_improvement`
- `max_correlation > decision_corr_fail_multiplier * success_thresholds.unselected.max_correlation`
- 其中 `decision_corr_fail_multiplier = marginal_contribution.scoring.decision_corr_fail_multiplier`
- `NEUTRAL`: 介于 SUCCESS/FAILURE 之间，信息不足以支持替换，也不足以判定明显失败。
- `UNCERTAIN`: 数据不足（如共同样本不足）导致本轮无法评估。

### C. 因子库出库标准（Validation）
- 每轮记录 Validation 指标与稳定性指标：
- `oos_icir`, `oos_sharpe`, `oos_ls_mean`
- `overlap_prev`, `turnover`, `oos_excess_vs_prevlib`
- `oos_excess_vs_anchor`（相对锚库）
- `improve_primary_vs_prev / improve_primary_vs_anchor / improve_secondary_vs_anchor`
- `strict_holdout`:
1. 先按 `library_selection.stability_gate` 计算 `stability_pass`
2. 按双基准阈值（`vs_prev + vs_anchor`）计算 `selection_candidate`
3. 在 `selection_candidate=True` 轮次中选 Validation 最优 `S_r`
4. 若无候选轮次，按 `library_selection.fallback.when_no_candidate` 回退
5. 同时输出最后一轮库做对照
- `walk_forward_test`:
1. 触发早停则取触发轮
2. 否则取最后一轮

## 3. 贝叶斯更新规则

- selected success: `alpha += selected_success`
- selected failure: `beta += selected_failure`
- unselected success: `alpha += unselected_success`
- unselected failure: `beta += unselected_failure`
- `NEUTRAL/UNCERTAIN`: 不更新

配置项: `bayesian.update_rules.*`

## 4. 年化口径

- 全局年化天数: `annualization_days`（默认 250）
- 引擎/selector/factor/marginal 全部读取同一配置源，不再存在第二套年化参数。

公式（设 `ppy = annualization_days / ROLLING_WINDOW`）:
- `LS_rtn_annual = mean(LS_period) * ppy`
- `Sharpe_annual = (mean/std)_period * sqrt(ppy)`
- `ICIR_annual = (mean(IC)/std(IC)) * sqrt(ppy)`

## 5. IC/ICIR 样本门槛的准确含义

`time_windows.ic_calculation` 当前使用两个参数：
- `min_periods_abs`: 绝对最小样本门槛
- `min_periods_ratio`: 相对窗口的最小样本比例

统一规则：
- `required_points = max(min_periods_abs, ceil(window * min_periods_ratio))`
- `calculate_icir()` 在有效 IC 样本不足 `required_points` 时返回 `NaN`（不可计算）
- A层选择打分中：不可计算项不置零，按有效指标/窗口重归一化继续打分
- B1选中成功判定中：样本不足直接判失败
- B2未选中边际贡献中：ICIR相关项沿用同一规则；若总体数据不足触发 `UNCERTAIN`

这两个参数不控制回看窗口长度。窗口长度由 `selected_short/selected_long/unselected_long` 控制。

## 6. 输出文件

- 轮次摘要: `round_summary.csv`
- 因子逐轮状态: `factor_round_status.csv`
- 因子库指标: `library_metrics.json`
- 最终库: `final_library.json`
- 动态图:
- `validation_dynamics.svg`
- `test_dynamics.svg`（若有 test 集）
- 紧凑表: `round_compact_summary.csv`

补充:
- `test_dynamics.svg` 会标注 `selected_round` 与 `last_round` 在 test 指标中的全轮次排名（降序，1=最好）。

## 7. 变更同步要求

当以下内容变更时，必须同步更新：
- 判定逻辑（A/B/C）
- 参数默认值
- 评价窗口与年化口径
- 输出字段

同步文件：
- `docs/EVALUATION_STANDARDS.md`
- `docs/PARAMETER_MAPPING.md`
- `docs/CODE_ARCHITECTURE.md`
- `docs/ITERATION3_SUMMARY.md`
