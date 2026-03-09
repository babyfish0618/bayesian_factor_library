# 评价标准（当前实现）

更新时间: 2026-03-09  
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
- 其中权重来自:
- `bayesian.selection_blend.aggregate_score`
- `bayesian.selection_blend.bayesian_score`

### B1. 选中因子成功标准（Selected Success）
- 回看窗口: `time_windows.evaluation.selected_short`
- 样本门槛: `time_windows.ic_calculation.min_periods`
- 同时满足:
- `icir > success_thresholds.selected.icir`
- `ls_sharpe > 0`
- `rank_percentile < success_thresholds.selected.rank_percentile`
- `win_rate > success_thresholds.selected.win_rate`

备注:
- 这里的 `min_periods` 不是“IC窗口长度”，而是“最小有效样本数门槛”。
- 若回看窗口内有效样本 `< min_periods`，本轮不判 success。

### B2. 未选中因子成功标准（Unselected Success）
- 使用边际贡献评估（相关性 + 替换改进 + 候选质量）输出 `SUCCESS/FAILURE/NEUTRAL/UNCERTAIN`。
- SUCCESS 条件:
- `score >= decision_success_score`
- `improvement > 0`
- `max_correlation <= success_thresholds.unselected.max_correlation`
- FAILURE 条件（任一满足）:
- `score < decision_failure_score`
- `improvement < decision_failure_improvement`
- `max_correlation > decision_corr_fail_multiplier * max_correlation_threshold`

### C. 因子库出库标准（Validation）
- 每轮记录 Validation 指标与稳定性指标：
- `oos_icir`, `oos_sharpe`, `oos_ls_mean`
- `overlap_prev`, `turnover`, `oos_excess_vs_prevlib`
- `strict_holdout`:
1. 先按稳定性规则计算 `stability_pass`
2. 在通过轮次中选 Validation 最优 `S_r`
3. 若无通过轮次，回退到全轮次 Validation 最优
4. 同时输出最后一轮库做对照
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

## 5. min_periods 的准确含义

`time_windows.ic_calculation.min_periods` 当前用于两个地方：
- 选中因子成功判定的最小样本门槛
- `calculate_icir()` 的最小 IC 样本门槛（不足则返回 0）

它不控制回看窗口长度。窗口长度由 `selected_short/selected_long/unselected_long` 控制。

## 6. 输出文件

- 轮次摘要: `round_summary.csv`
- 因子逐轮状态: `factor_round_status.csv`
- 因子库指标: `library_metrics.json`
- 最终库: `final_library.json`
- 动态图:
- `validation_dynamics.svg`
- `test_dynamics.svg`（若有 test 集）
- 紧凑表: `round_compact_summary.csv`

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
