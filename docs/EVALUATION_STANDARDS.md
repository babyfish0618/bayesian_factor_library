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
- 4个分项在每个窗口都做“当期全候选截面分位数标准化”（位置分，范围 `[0,1]`）：
- `icir`（高值高分）
- `ls_return`（高值高分）
- `rank`（由 `1-avg_rank` 转同向后再做截面分位）
- `stability`（`ls_return_sharpe`，高值高分）
- 即 A 层是“4个分项都是位置排序得分”，再按权重聚合。
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
- 其中 `rank_percentile` 口径为：上一轮已选因子在“全候选可评估因子集合”中的排名百分位（越小越好）。

备注:
- 这里不是“IC窗口长度”，而是“最小有效样本数门槛”。
- 若回看窗口内有效 IC 样本 `< required_points`，本轮不判 success。
- 当前实现里，选中因子 success 判定只使用 `time_windows.evaluation.selected_short`；
- `time_windows.evaluation.selected_long` 主要用于统计展示/追踪（如 recent_icir 等），不参与 success 判定阈值。

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

未选中因子 `x` 的完整判定流程（当前实现）:
1. 准备数据（候选 `x` + 已选集合 `S`）  
- 使用 `lookback = time_windows.evaluation.unselected_long` 回看窗口。  
- 若样本不足（核心门槛：`correlation.min_common_periods`），直接 `UNCERTAIN`。  
2. 决定“替换谁”（由 `marginal_contribution.replacement_strategy` 决定）  
- `correlation_based`：替换 `S` 中与 `x` 的 `|corr|` 最大者。  
- `effectiveness_based`：替换 `S` 中 ICIR 最低者。  
- `portfolio_optimization`：不替换，直接将 `x` 加入组合。  
3. 计算边际改善  
- 构建基准组合 `Baseline(S)` 与新组合 `New(S')`（组合构建方法由 `marginal_contribution.method` 决定）。  
- `improvement = Sharpe(New) - Sharpe(Baseline)`。  
- `can_replace = (improvement > marginal_contribution.improvement_threshold)`。  
4. 计算综合分 `score`（四分项加权）  
- improvement 分项  
- correlation 分项  
- quality 分项（候选因子 ICIR/Sharpe）  
- feasibility 分项（由 `can_replace` 决定）  
5. 输出四类结果  
- `SUCCESS`：`score`、`improvement`、`max_correlation` 同时满足成功条件。  
- `FAILURE`：触发任一失败条件。  
- `NEUTRAL`：不满足成功，也未触发失败。  
- `UNCERTAIN`：步骤1数据不足，无法进入步骤2~5。

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

## 6. 参数 -> 影响路径（未选中评估核心）

| 参数键 | 影响步骤 | 直接作用 |
|---|---|---|
| `time_windows.evaluation.unselected_long` | 步骤1 | 未选中因子边际评估回看区间长度 |
| `correlation.min_common_periods` | 步骤1 | 最小共同样本门槛；不足触发 `UNCERTAIN` |
| `time_windows.ic_calculation.min_periods_abs` | 步骤1/4 | ICIR 最小样本绝对门槛（候选质量相关） |
| `time_windows.ic_calculation.min_periods_ratio` | 步骤1/4 | ICIR 最小样本比例门槛（候选质量相关） |
| `marginal_contribution.replacement_strategy` | 步骤2 | 决定替换对象选择规则 |
| `marginal_contribution.method` | 步骤3 | 决定组合构建方式（equal_weight / icir_weighted / sharpe_optimized / risk_parity / min_variance） |
| `marginal_contribution.improvement_threshold` | 步骤3/4 | 用于 `can_replace` 判定，影响 feasibility 分项 |
| `success_thresholds.unselected.max_correlation` | 步骤5 | SUCCESS 的相关性上限基准 |
| `marginal_contribution.scoring.weights.improvement` | 步骤4 | improvement 分项权重 |
| `marginal_contribution.scoring.weights.correlation` | 步骤4 | correlation 分项权重 |
| `marginal_contribution.scoring.weights.quality` | 步骤4 | quality 分项权重 |
| `marginal_contribution.scoring.weights.feasibility` | 步骤4 | feasibility 分项权重 |
| `marginal_contribution.scoring.grade_scores.*` | 步骤4 | 各分项分段映射分值（high/medium/low/fallback） |
| `marginal_contribution.scoring.quality_thresholds.*` | 步骤4 | quality 分项分段阈值（ICIR/Sharpe） |
| `marginal_contribution.scoring.feasibility_scores.replace` | 步骤4 | `can_replace=True` 时 feasibility 分值 |
| `marginal_contribution.scoring.feasibility_scores.no_replace` | 步骤4 | `can_replace=False` 时 feasibility 分值 |
| `marginal_contribution.scoring.correlation_low_ratio` | 步骤4 | correlation 分项中“低相关高分段”比例阈值 |
| `marginal_contribution.scoring.decision_success_score` | 步骤5 | SUCCESS 的综合分门槛 |
| `marginal_contribution.scoring.decision_failure_score` | 步骤5 | FAILURE 的低分门槛 |
| `marginal_contribution.scoring.decision_failure_improvement` | 步骤5 | FAILURE 的改善下限门槛 |
| `marginal_contribution.scoring.decision_corr_fail_multiplier` | 步骤5 | FAILURE 的高相关倍数门槛 |

## 7. 输出文件

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

## 8. 变更同步要求

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
