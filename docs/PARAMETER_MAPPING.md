# 参数-代码映射表（当前主流程）

更新时间: 2026-03-09  
配置主文件: `config/evaluation_config.yaml`

说明:
- 本表只保留“当前主流程已使用”的参数。
- 每次改参数、改判定逻辑、改窗口口径，必须同步更新本文件。

## 1) 全局口径

| 参数 | 默认值 | 代码位置 | 作用 |
|---|---:|---|---|
| `annualization_days` | `250` | `src/core/bayesian_selector_v2.py` | 统一 selector/factor/marginal 内部年化口径 |

## 2) 时间窗口

| 参数 | 默认值 | 代码位置 | 作用 |
|---|---:|---|---|
| `time_windows.selection.short_term` | `5` | `src/utils/config_manager.py#get_window_weights` | 选择打分短窗 |
| `time_windows.selection.medium_term` | `20` | 同上 | 选择打分中窗 |
| `time_windows.selection.long_term` | `60` | 同上 | 选择打分长窗 |
| `time_windows.evaluation.selected_short` | `10` | `src/core/bayesian_selector_v2.py#_evaluate_selected_success` | 选中因子 success 判定回看窗口 |
| `time_windows.evaluation.selected_long` | `20` | `src/workflows/factor_library_iteration_engine.py` / `src/core/bayesian_selector_v2.py` | 选中因子统计展示与更新评估长窗 |
| `time_windows.evaluation.unselected_long` | `40` | `src/core/bayesian_selector_v2.py#update_from_performance` | 未选中因子边际贡献评估回看窗口 |
| `time_windows.ic_calculation.min_periods` | `10` | `src/core/factor_enhanced.py#calculate_icir` / `src/core/bayesian_selector_v2.py` | IC/ICIR最小样本门槛；不足则不判定或返回0 |

## 3) 选择打分（A类）

| 参数 | 默认值 | 代码位置 | 作用 |
|---|---:|---|---|
| `indicator_weights.selection.icir` | `0.4` | `src/core/factor_enhanced.py#get_aggregate_score` | 选择打分中 ICIR 权重 |
| `indicator_weights.selection.ls_return` | `0.3` | 同上 | 选择打分中 LS 收益权重 |
| `indicator_weights.selection.rank_percentile` | `0.2` | 同上 | 选择打分中排名权重 |
| `indicator_weights.selection.stability` | `0.1` | 同上 | 选择打分中稳定性（Sharpe归一化）权重 |
| `bayesian.selection_blend.aggregate_score` | `0.7` | `src/core/bayesian_selector_v2.py#_calculate_factor_scores` | `final_score` 中聚合分权重 |
| `bayesian.selection_blend.bayesian_score` | `0.3` | 同上 | `final_score` 中 Thompson 采样权重 |

## 4) 选中因子成功判定（B类-selected）

| 参数 | 默认值 | 代码位置 | 作用 |
|---|---:|---|---|
| `success_thresholds.selected.icir` | `0.8` | `src/core/bayesian_selector_v2.py#_evaluate_selected_success` | 选中 success 的 ICIR 阈值 |
| `success_thresholds.selected.rank_percentile` | `0.7` | 同上 | 选中 success 的排名阈值（越小越好） |
| `success_thresholds.selected.win_rate` | `0.55` | 同上 | 选中 success 的胜率阈值 |
| （固定规则）`ls_sharpe > 0` | - | 同上 | 选中 success 的 Sharpe 正值约束 |

## 5) 未选中因子判定（B类-unselected）

| 参数 | 默认值 | 代码位置 | 作用 |
|---|---:|---|---|
| `success_thresholds.unselected.max_correlation` | `0.6` | `src/evaluation/marginal_contrib.py` | 未选中 success/failure 判定相关性上限 |
| `marginal_contribution.method` | `equal_weight` | `src/evaluation/portfolio_simulator.py` | 边际贡献内部组合构造方式 |
| `marginal_contribution.replacement_strategy` | `correlation_based` | 同上 | 候选替换策略 |
| `marginal_contribution.improvement_threshold` | `0.01` | 同上 | can_replace 判定门槛 |
| `marginal_contribution.scoring.weights.*` | `0.4/0.3/0.2/0.1` | `src/evaluation/marginal_contrib.py#_calculate_comprehensive_score` | 未选中综合分四个维度权重 |
| `marginal_contribution.scoring.grade_scores.*` | `1.0/0.7/0.4/0.1` | 同上 | 分段评分取值 |
| `marginal_contribution.scoring.quality_thresholds.*` | `2.0/1.0/0.5` | 同上 | 候选质量(ICIR/Sharpe)分段阈值 |
| `marginal_contribution.scoring.feasibility_scores.*` | `1.0/0.3` | 同上 | 可替换性打分 |
| `marginal_contribution.scoring.correlation_low_ratio` | `0.5` | 同上 | 低相关分段比例阈值 |
| `marginal_contribution.scoring.decision_success_score` | `0.7` | `src/evaluation/marginal_contrib.py#_determine_evaluation_result` | SUCCESS score 门槛 |
| `marginal_contribution.scoring.decision_failure_score` | `0.3` | 同上 | FAILURE score 门槛 |
| `marginal_contribution.scoring.decision_failure_improvement` | `-0.1` | 同上 | FAILURE 改善门槛 |
| `marginal_contribution.scoring.decision_corr_fail_multiplier` | `1.2` | 同上 | FAILURE 相关性倍数门槛 |

## 6) 贝叶斯更新

| 参数 | 默认值 | 代码位置 | 作用 |
|---|---:|---|---|
| `bayesian.update_rules.selected_success` | `1.0` | `src/core/bayesian_selector_v2.py#update_from_performance` | 选中成功时 `alpha +=` |
| `bayesian.update_rules.selected_failure` | `1.0` | 同上 | 选中失败时 `beta +=` |
| `bayesian.update_rules.unselected_success` | `0.5` | 同上 | 未选中成功时 `alpha +=` |
| `bayesian.update_rules.unselected_failure` | `0.0` | 同上 | 未选中失败时 `beta +=` |

## 7) 相关性计算

| 参数 | 默认值 | 代码位置 | 作用 |
|---|---:|---|---|
| `correlation.method` | `pearson` | `src/core/correlation_calculator.py` | 相关性计算方法 |
| `correlation.min_common_periods` | `20` | `src/evaluation/marginal_contrib.py` / `src/core/correlation_calculator.py` | 共同样本最小门槛 |
| `correlation.significance_level` | `0.05` | `src/core/correlation_calculator.py` | 相关性显著性检验阈值 |

## 8) 引擎级（非 YAML）关键参数

| 参数 | 默认值 | 代码位置 | 作用 |
|---|---:|---|---|
| `ROLLING_WINDOW` | `5` | `src/workflows/factor_library_iteration_engine.py` | 前瞻窗口 `x(t)->R(t+1..t+n)` |
| `TRAIN_RATIO/VALIDATION_RATIO/TEST_RATIO` | `0.7/0.2/0.1` | 同上 | 数据切分比例 |
| `SPLIT_GAP_DAYS` | `ROLLING_WINDOW` | 同上 | 切分边界隔离 |
| `EVAL_MODE` | `strict_holdout` | 同上 | 验证模式 |
| `ENABLE_ASOF_FILTER` | `False` | 同上 | 按 as-of 过滤可得标签 |
| `EARLY_STOP_*` | 见实验配置 | 同上 | 早停阈值与窗口 |
