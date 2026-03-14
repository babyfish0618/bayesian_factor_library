# 因子库迭代评估协议（无代码规范模板）

更新时间: 2026-03-09
状态: Draft v2（目标时序规范）

## 1. 目标

通过多轮迭代形成可出库的固定规模因子库 `S*`（N个因子），用于后续融合。

核心原则:
- A/B/C 三层分工明确
- B 必须基于“新观测”更新后验
- C 使用独立验证窗口做最终裁判
- 全流程严禁未来数据泄露

## 2. 时间与符号定义（防未来函数）

- `tau_r`: 第 `r` 轮调仓决策时点（如月末）
- `S_r`: 在 `tau_r` 选出的因子库
- `L`: 选择时回看窗口长度（如 60 日）
- `H_B`: B层更新观察窗口（如 1个月）
- `H_C`: C层验证窗口（建议 3-6个月）
- `x_{i,t}`: 股票 `i` 在 `t` 时刻可观测到的因子值（仅使用 `t` 及之前信息）
- `R_{i,t+1->t+n}`: 前瞻收益，定义为 `P_{i,t+n}/P_{i,t} - 1`（不含t当日收益）

强约束:
- 任何 `t` 时刻信号只能与 `R_{t+1->t+n}` 配对，不允许与 `R_{t-k->t}` 配对。
- IC、多空收益、胜率、Sharpe 的标签期必须严格落在信号时点之后。
- 标签可“离线批量预计算”，但训练/更新/验证使用时必须按 `asof` 可得性过滤：
- 仅可使用满足 `label_end_date <= asof_date` 的样本。

## 3. 三层标准（A/B/C）

### A. Selection（选库质量）

反映“如何选”，不直接作为出库依据。

建议字段:
- `selected_count`
- `selected_overlap_prev = |S_r ∩ S_{r-1}| / |S_r ∪ S_{r-1}|`
- `turnover = 1 - selected_overlap_prev`
- `score_dispersion`
- 仿真专用: `selected_good/selected_medium/selected_bad`

### B. Bayesian Update（学习质量）

反映“本轮后验更新是否使用了新增信息”。

建议字段:
- `selected_success_rate`
- `unselected_success_rate`
- `success_calibration`
- `failure_calibration`
- `posterior_shift_alpha_beta`（更新前后参数变化）

### C. Validation OOS（最终质量）

反映“候选因子库是否具备出库价值”。

建议字段:
- `OOS_ls_return_mean`
- `OOS_sharpe`
- `OOS_ic_mean`
- `OOS_icir`
- `OOS_max_drawdown`
- `OOS_excess_vs_prevlib`
- `OOS_excess_vs_baseline`

## 4. 每轮严格时序（关键）

第 `r` 轮在 `tau_r` 的操作顺序必须是：

1. `Observe`（先观察新信息并更新后验）
- 使用区间 `(tau_{r-1}, tau_r]` 的新观测，评估上一轮库 `S_{r-1}` 的 success/failure。
- 按 B层规则更新后验参数（alpha/beta），得到本轮先验。

2. `Select`（再选本轮库）
- 在 `tau_r` 用更新后的先验 + 历史可用统计（至 `tau_r`）打分，选出 `S_r`。

3. `Record`
- 记录本轮 A/B 字段与因子级状态快照。

4. `Validate`（仅评估，不反哺训练）
- 在 C层口径下对候选库做独立验证评估（详见第5节）。

这意味着输出口径上，B属于“进入 `tau_r` 前完成的更新”，不是“选完 `S_r` 后立即更新 `S_r`”。

## 5. 推荐评估框架：Train / Validation / Test

为避免“滚动OOS过短噪声大”导致误判，推荐固定验证集方案：

1. Train阶段（可更新后验）
- 时间: `[T_train_start, T_train_end]`
- 运行第4节时序，得到多轮候选库 `S_1...S_R`。

2. Validation阶段（固定窗口，不更新后验）
- 时间: `[T_val_start, T_val_end]`（统一窗口，建议 3-6 个月）
- 对每个候选库 `S_r` 在同一验证窗口计算 C指标。
- 根据 C + 稳定性选择出库版本 `S*`。
- 切分参数建议显式配置：`TRAIN_RATIO/VALIDATION_RATIO/TEST_RATIO`（允许 `TEST_RATIO=0`）。

3. Test阶段（可选，最终验收）
- 时间: `[T_test_start, T_test_end]`
- 仅评估 `S*`，不参与选择与参数更新。

实现扩展（实验模式）:
- `strict_holdout`: 仅在train迭代，validation固定评估，test仅最终验收。
- `walk_forward_test`: 从train继续滚动迭代到test末尾，用于在线仿真稳定性评估。

边界泄露控制（新增）:
- 引入 `split_gap_days`（建议默认 `= horizon_days`）：
- train 与 validation 之间留出 gap
- validation 与 test 之间留出 gap
- 目的：避免边界附近标签窗口与下一区间发生重叠污染。
- 可选 `as-of` 过滤模式:
- 每个决策日 `tau_r` 仅允许使用 `label_end_date <= tau_r` 的样本参与评估。

出库决策建议:
- `strict_holdout`:
- 不以“早停截断训练”为主机制；优先利用完整train信息。
- 将早停条件转化为“稳定性约束”，对每轮打 `stability_pass` 标记。
- 在满足 `stability_pass` 的轮次中，选择 Validation 指标最优的 `S_r` 作为最终库。
- 同时保留“最后一轮 `S_T`”作为对照报告。
- `walk_forward_test`:
- 可继续使用连续窗口早停，作为在线维护中的运营策略。

## 6. 指标计算细节（必须遵守）

### 6.1 IC

在信号日 `t`：
- 横截面IC: `IC_t = corr_i(x_{i,t}, R_{i,t+1->t+n})`
- `IC_mean`, `ICIR = mean(IC_t) / std(IC_t)` 在样本期内汇总。
- 样本充足性门槛（配置项）：
- `time_windows.ic_calculation.min_periods_abs`
- `time_windows.ic_calculation.min_periods_ratio`
- 动态门槛：`required_points = max(min_periods_abs, ceil(window * min_periods_ratio))`
- 当有效 IC 样本 `< required_points` 时，`ICIR` 记为不可计算（`NaN`），不使用 `0` 代替。

### 6.2 多空收益

在信号日 `t`：
- 采用因子加权多空（非top-bottom分组）：
- `w_i^+ = max(x_{i,t}, 0) / sum_j max(x_{j,t}, 0)`
- `w_i^- = max(-x_{i,t}, 0) / sum_j max(-x_{j,t}, 0)`
- `LS_t = sum_i w_i^+ * R_{i,t+1->t+n} - sum_i w_i^- * R_{i,t+1->t+n}`
- 约束：`sum_i w_i^+ = 1`，`sum_i w_i^- = 1`（2x gross exposure）
- `LS_mean`, `Sharpe`, `WinRate` 在样本期内汇总。

### 6.3 绝对禁止

- 用 `t+1` 才知道的因子值参与 `t` 的分组
- 用 `R_{t->t+n}` 更新 `tau_t` 之前的后验
- 重叠窗口统计但未注明重叠口径（需在输出元数据标记）

### 6.4 计算与使用分离（新增）
- 可先一次性计算全样本 `R(t+1->t+n)` 以提升效率；
- 但在任意时点 `T` 的训练/更新中，只能使用 `t+n <= T` 的标签；
- 在滚动训练 `T -> T+1` 时，使用窗口同步滚动并重新执行该可得性过滤。

## 7. 早停与出库判据（Validation口径）

定义窗口长度 `m`，阈值 `eps_perf`, `eps_turnover`, `delta`。

连续 `m` 轮候选满足时触发“可出库”：
1. `turnover_r <= eps_turnover`
2. `|OOS_sharpe_r - OOS_sharpe_{r-1}| <= eps_perf`
3. `|OOS_icir_r - OOS_icir_{r-1}| <= eps_perf`
4. `OOS_excess_vs_prevlib_r >= -delta`

示例:
- `m=3`, `eps_turnover=0.15`, `eps_perf=0.05`, `delta=0.02`

若未触发:
1. 默认: 取最后一轮候选库
2. 稳健: 在满足稳定性下选 C 指标最优 `S_r`

当前实现对应配置键（`strict_holdout`）：
- 主/次目标: `library_selection.objective.primary_metric` / `library_selection.objective.secondary_metric`
- 双基准阈值:
- `library_selection.thresholds.min_improve_vs_prev`
- `library_selection.thresholds.min_improve_vs_anchor`
- `library_selection.thresholds.min_improve_vs_anchor_secondary`
- 稳定门控:
- `library_selection.stability_gate.mode` (`all` / `k_of_n`)
- `library_selection.stability_gate.k_of_n.k`
- `library_selection.stability_gate.k_of_n.n`
- `library_selection.stability_gate.turnover_max`
- `library_selection.stability_gate.delta_sharpe_raw_max`
- `library_selection.stability_gate.delta_icir_raw_max`
- `library_selection.stability_gate.excess_vs_prev_min`
- 无候选回退: `library_selection.fallback.when_no_candidate`

## 8. 输出字段规范（协议级）

### 8.1 轮次级（round_summary）
- `round`, `tau_r`, `selected_count`
- `selected_overlap_prev`, `turnover`
- `selected_success_rate`, `unselected_success_rate`
- `oos_icir`, `oos_sharpe`, `oos_ls_mean`
- `oos_excess_vs_prevlib`

### 8.2 因子级（factor_round_status）
- `round`, `tau_r`, `factor_id`
- `selected`, `selected_success`, `unselected_evaluation`
- `alpha_before`, `beta_before`, `alpha_after`, `beta_after`
- `score_final`, `score_aggregate`, `score_bayesian`
- `ic_signal_horizon_n`, `ls_signal_horizon_n`（用于追溯信号-标签配对）

### 8.3 元数据（metadata）
- `train/validation/test` 时间边界
- `n_horizon`（`R_{t+1->t+n}` 中的 `n`）
- 是否重叠窗口
- 早停参数

## 9. 仿真数据协议（测试专用）

- 保留长期标签：`good/medium/bad`
- 每期潜在状态可切换：`good/medium/bad`
- good 因子应“多数时间”处于 good，但允许短期退化
- 真实市场评估不得依赖该标签，只能依赖 C指标

## 10. 文档联动维护

本协议若调整，需同步更新:
- `docs/CODE_ARCHITECTURE.md`
- `docs/EVALUATION_STANDARDS.md`
- `docs/ITERATION3_SUMMARY.md`
