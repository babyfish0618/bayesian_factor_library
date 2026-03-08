# 真实数据接入指南（因子库筛选系统）

更新时间: 2026-03-09
适用范围: 当前 `src/workflows/factor_library_iteration_engine.py` 主流程

## 1. 目标

将当前模拟数据链路替换为真实市场数据链路，同时保持以下时序约束：
- 信号: `x(t)`（t日收盘后可见）
- 标签: `R(t+1->t+n)`（不含t当日）
- 严禁未来数据泄露

## 2. 建议数据分层

建议新增 `src/data/`（或 `src/datasource/`）目录，分层如下：
- `readers/`: 原始数据读取（parquet/csv/db）
- `cleaning/`: 复权、停牌、缺失值处理
- `alignment/`: 交易日对齐、股票池对齐、因子-收益对齐
- `features/`: 因子暴露计算（x）
- `labels/`: 前瞻收益标签计算（R(t+1->t+n)）
- `quality/`: 数据质量检查

## 3. 最小必备输入表

### 3.1 日行情表（面板）
- 主键: `date`, `asset_id`
- 字段:
  - `close_adj`（后复权收盘价）
  - `volume`
  - `is_tradable`（是否可交易）
  - `is_st` / `is_suspended`（可选）

### 3.2 因子暴露表（面板）
- 主键: `date`, `asset_id`
- 字段:
  - `factor_id`
  - `exposure`（因子值，建议已去极值/标准化或提供原值+处理标记）

### 3.3 股票池表（可选）
- 主键: `date`, `asset_id`
- 字段:
  - `in_universe`（是否在当日股票池）

## 4. 标签定义（统一）

设前瞻窗口 `n = horizon_days`：
- `R(t+1->t+n) = P(t+n)/P(t) - 1`

说明：
- 因子暴露使用 `t` 当天收盘后可得信息。
- 标签收益从 `t+1` 开始，直到 `t+n`。

## 5. 指标计算口径

### 5.1 IC
- 横截面IC: `IC_t = corr_i(x_{i,t}, R_{i,t+1->t+n})`
- `ICIR_raw = mean(IC_t)/std(IC_t)`
- `ICIR_annual = ICIR_raw * sqrt(ANNUAL_DAYS / n)`

### 5.2 多空收益（因子加权）
- `w_i^+ = max(x_i,0)/sum_j max(x_j,0)`
- `w_i^- = max(-x_i,0)/sum_j max(-x_j,0)`
- `LS_t = sum_i w_i^+ R_i - sum_i w_i^- R_i`
- 约束: `sum(w^+)=1`, `sum(w^-)=1`（2x gross）

### 5.3 年化
- `LS_rtn_annual = mean(LS_t) * (ANNUAL_DAYS / n)`
- `Sharpe_raw = mean(LS_t)/std(LS_t)`
- `Sharpe_annual = Sharpe_raw * sqrt(ANNUAL_DAYS / n)`

## 6. 数据质量检查清单

每次构建数据后建议输出质检报告：
- 缺失率（按字段/按日期）
- 可交易样本占比（`is_tradable`）
- 股票池覆盖率（每期有效资产数）
- 因子暴露分布（均值/标准差/偏度/峰度）
- 标签收益分布（均值/波动/极值）
- 对齐检查：随机抽样验证 `x(t)` 与 `R(t+1->t+n)` 的时间偏移是否正确

## 7. 接入步骤（建议）

1. 替换模拟器输出接口
- 当前流程需要：
  - `dates`
  - 因子对象（含 `performance_history`）
- 先实现“真实数据版数据构建器”，输出同结构对象，最小改动接入引擎。

2. 双跑校验
- 同时跑模拟版与真实版，验证输出字段一致性（CSV/JSON/SVG 是否完整）。

3. 小样本灰度
- 先在短时间区间、较小股票池运行，确认性能与时序正确后再全量。

## 8. 参数建议（实盘首版）

- `horizon_days`: 5/10/20（建议先10）
- `annual_days`: 250
- `eval_mode`: `strict_holdout`
- `train/val/test`: 0.7/0.2/0.1（或按日期硬切分）
- `target_size`: 先从 `num_factors` 的 20%-40% 扫描

## 9. 风险点（接入时常见）

- 复权口径不统一导致标签偏差
- 停牌/涨跌停处理不一致导致不可实现收益
- 股票池漂移未显式记录
- 因子值预处理（去极值/标准化）在 train/val/test 之间口径不一致
- 不同数据源时区/交易日历不一致
