# 代码架构速查文档（Iteration3 当前实现）

> 更新时间: 2026-03-09
> 目的: 快速理解当前代码模块关系、核心流程与跟踪输出

## 1. 模块关系图

```mermaid
graph TB
    subgraph 入口层
        A[src/tests/test_performance.py<br/>性能测试入口]
        A2[src/tests/experiment_generate_sim_data.py<br/>模拟数据落盘入口]
        A3[src/tests/experiment_real_data_single.py<br/>真实数据单场景入口]
        A4[src/tests/experiment_real_data_asof_rolling.py<br/>多asof滚动出库入口]
    end

    subgraph 实验编排层
        K[ScenarioComparator<br/>多场景对比]
        M[StabilityExperimentRunner<br/>长周期稳定性实验]
        L[FactorLibraryIterationEngine<br/>单场景迭代引擎]
        L2[RealDataIterationEngine<br/>真实数据单场景迭代引擎]
        L3[AsOfLibraryGenerator<br/>多asof滚动出库器]
    end

    subgraph 核心选择层
        B[BayesianSelectorV2<br/>选择与更新主控制器]
        C[EnhancedFactor<br/>因子状态与历史表现]
    end

    subgraph 评估层
        D[CorrelationCalculator<br/>相关性计算]
        E[PortfolioSimulator<br/>组合构建与替换模拟]
        F[MarginalContributionEvaluator<br/>未选中因子边际评估]
    end

    subgraph 数据模拟层
        J[LatentFactorDataSimulator<br/>测试数据模拟器]
    end

    subgraph 数据接入层
        R[RealDataLoader<br/>真实数据文件读取]
    end

    subgraph 跟踪与输出层
        G[FactorLibraryTracker<br/>轮次/因子状态跟踪]
    end

    subgraph 配置层
        H[ConfigManager]
        I[config/evaluation_config.yaml]
    end

    A --> K
    A --> M
    A2 --> J
    A3 --> L2
    A4 --> L3
    L2 --> R
    L2 --> L
    L3 --> L2
    K --> L
    M --> L
    L --> B
    L --> G
    L --> J
    B --> C
    B --> D
    B --> F
    B --> H
    F --> D
    F --> E
    H --> I
```

## 2. 核心模块

说明:
- `src/core/__archive/` 与 `src/simulation/__archive/` 存放历史MVP链路模块，不参与当前主流程。

### 2.1 `src/core/bayesian_selector_v2.py`
- `select_factors(current_date, target_size)`
- `update_from_performance(selected_ids, performance_data, current_date)`
- `verbose` 开关（可关闭过程明细日志，仅保留外层关键统计）
- `SelectionResult`: 记录当轮选中与候选得分
- `UpdateResult`: 记录选中/未选中更新结果、统计、`marginal_details`

关键逻辑:
- 选择: `final_score = 0.7 * aggregate_score + 0.3 * Beta(alpha,beta)采样`
- 更新:
- 选中因子按 selected success 规则更新 alpha/beta
- 未选中因子走边际贡献评估（SUCCESS/FAILURE/NEUTRAL/UNCERTAIN）

### 2.2 `src/core/factor_enhanced.py`
- 因子数据与历史表现容器
- 提供多窗口统计、ICIR、LS 统计、综合分
- 管理贝叶斯参数 `alpha/beta`

### 2.3 `src/evaluation/marginal_contrib.py`
- 对未选中因子执行边际贡献评估
- 组合模拟 + 相关性 + 候选质量综合打分
- 输出 `MarginalContributionResult`

### 2.4 `src/evaluation/portfolio_simulator.py`
- 组合构建与替换评估
- 支持 `equal_weight/icir_weighted/sharpe_optimized/...`
- 输出边际改善 `marginal_improvement` 与替换可行性

### 2.5 `src/core/correlation_calculator.py`
- 因子收益序列相关性矩阵
- 相关性显著性与汇总指标

### 2.6 `src/evaluation/library_tracker.py`
- 每轮跟踪:
- 选中结构: good/medium/bad
- 选中成功结构: good/medium/bad
- 每因子逐轮状态: 是否选中、是否成功、边际评估、打分、更新前后 alpha/beta
- 因子库整体指标: all vs selected 的 ICIR/LS 分布
- 导出文件:
- `round_summary.csv`
- `factor_round_status.csv`
- `library_metrics.json`
- `final_library.json`（最终固化因子库版本，由测试入口生成）

### 2.12 `src/evaluation/library_dynamics_plotter.py`
- 根据每轮验证指标生成 `validation_dynamics.svg`
- 标注稳定性通过轮次与最终出库轮次
- 可选生成 `test_dynamics.svg`（含 test ICIR/Sharpe/rtn）

### 2.7 `src/simulation/latent_factor_data_simulator.py`（模拟数据逻辑）
- 统一封装测试数据生成逻辑（日期、股票收益、滚动收益、因子历史表现）
- 标签收益口径: `R(t+1->t+n)`（不含t当日）
- 多空收益口径: 因子加权多空（多头权重和=1，空头权重和=1）
- 因子仍保留长期分类标签，并引入潜在状态按期切换
- 可选按 `train/validation/test` 使用不同状态转移矩阵（`PHASE_TRANSITION_PROBS`）
- 对测试入口提供稳定接口：
- `build_market_data()`
- `generate_factors()`
- `export_as_real_data_format()`（可选导出为真实数据目录结构）
- 进度显示（新增）：
- `show_progress=True` 时可显示“状态转移/因子生成/写盘”进度条（tqdm可用时）
- 日期生成规则（新增）：
- 若提供 `start_date+end_date`，按闭区间交易日生成（优先于 `num_days`）
- 若未提供 `end_date`，按 `num_days` 从 `start_date` 向后生成
- `meta/simulation_manifest.json` 中：
- `start_date/end_date/num_days` 表示“实际输出数据”的起止与天数
- `config_start_date/config_end_date/config_num_days` 表示“输入配置参数”
- 后续接入真实数据时，可在 simulation/data-source 层替换，不改测试评估主流程

### 2.8 `src/workflows/factor_library_iteration_engine.py`（流程编排）
- 封装单场景完整流程：
- 数据准备 -> 选择更新 -> OOS评估 -> 稳定性评估 -> 早停判定 -> 最终库固化
- 支持两种评估模式：
- `strict_holdout`（train迭代 + 固定validation评估）
- `walk_forward_test`（滚动到test末尾）
- `strict_holdout` 最终选库使用“参数化双基准规则”：
- 先按 `library_selection.stability_gate` 计算 `stability_pass`
- 再按 `vs_prev + vs_anchor` 阈值计算 `selection_candidate`
- 在候选轮次中选 Validation 最优；若无候选按 `library_selection.fallback` 回退
- 同时保留最后一轮对照
- 输出 `final_library.json`，作为后续融合阶段输入候选
- 数据准备步骤已抽象为 `_prepare_data()`，支持子类覆写
- 新增切分边界隔离：
- `SPLIT_GAP_DAYS`（默认=`ROLLING_WINDOW`）
- 在 train-val、val-test 之间保留 gap，避免边界标签泄露

### 2.9 `src/workflows/real_data_iteration_engine.py`（真实数据单场景）
- 继承 `FactorLibraryIterationEngine`
- 仅覆写 `_prepare_data()`：
- 从真实数据文件读取收益/暴露/股票池
- 计算 `R(t+1->t+n)` 标签
- 构造 `EnhancedFactor.performance_history`
- 其余选择、更新、稳定性、导出流程完全复用主引擎
- 支持 `REAL_DATA_ASOF_DATE + REAL_DATA_LOOKBACK_DAYS`：
- 对任意asof构建“回看窗口子样本”后独立出库

### 2.10 `src/workflows/asof_library_generator.py`（多asof滚动出库）
- 循环多个 `asof_date`：
- 每个asof独立调用 `RealDataIterationEngine` 生成最终库
- 导出跨日期对比文件：
- `asof_library_summary.csv`
- `asof_library_overlap.csv`
- `asof_library_seq_turnover.csv`
- `asof_library_factors.json`

### 2.11 `src/data/real_data_loader.py`（数据接入）
- 读取：
- `base/daily_returns.csv`
- `factors/*.csv`
- `pools/<pool>.csv`（可选）
- 输出对齐后的面板矩阵：
- `returns[stock,date]`
- `in_pool[stock,date]`
- `factor_scores[factor_id][stock,date]`

### 2.12 `src/experiments/factor_library_scenario_experiment.py`（实验管理）
- 封装多场景构造与批量运行
- 输出场景对比汇总（good选中率、召回率、更新成功率等）

### 2.13 `src/experiments/phase_regime_comparison_experiment.py`
- 分阶段状态转移（train/validation/test）对照实验
- 用于验证“验证/测试阶段环境变化”对最终出库质量的影响

### 2.14 `src/experiments/factor_library_stability_experiment.py`（稳定性实验）
- 面向“长历史 + 多轮次”实验，观察因子库收敛行为
- 复用 `FactorLibraryIterationEngine` 跑单场景
- 追加稳定性产物导出：
- `stability_convergence.svg`（稳定性/换手率/OOS/收敛指标曲线）
- `stability_report_*.json`（同口径时序数据）

## 3. 主流程

### 3.1 模拟实验流程（`test_performance.py` / `experiment_stability_early_stop.py`）

```text
生成模拟数据
  -> experiments层构造场景
  -> workflows层驱动单场景迭代
  -> simulation层提供市场数据与因子历史表现
  -> 按 train/validation/test 比例切分时间轴
  -> 先基于上一轮库在新观测区间的表现执行 posterior 更新
  -> selector.select_factors() 选出当轮库
  -> 构造用于更新的 performance_data（信号-标签配对: x(t) -> R(t+1->t+n)）
  -> tracker.record_round()
循环多轮后:
  -> 在固定validation区间计算OOS与稳定性指标(overlap/turnover)
  -> 检查早停条件（收敛则提前结束）
  -> tracker.export()
  -> 导出 round_compact_summary.csv（每轮紧凑指标）
  -> 导出 final_library.json
  -> （稳定性实验）导出 stability_convergence.svg + stability_report.json
  -> 打印总体指标与输出路径
```

`src/tests/test_performance.py` 参数:
- `--baseline-only`：仅运行 baseline，不做多场景对比
- `--seed`：设置随机种子
- `--num-stocks/--num-factors/--target-size/--num-days`：覆盖核心规模参数
- `--horizon-days`：覆盖共享前瞻窗口（IC/LS共用）
- `--export-sim-data/--export-root/--export-pool/--no-export-labels`：可选模拟数据落盘
- `--split-gap-days`：切分边界隔离天数
- `--asof-filter`：开启按 `asof_date` 可得性过滤评估
- `--progress`：显示模拟进度条（tqdm可用时）

`src/tests/experiment_phase_regime_comparison.py` 参数:
- `--baseline-only`
- `--num-stocks/--num-factors/--target-size/--num-days`
- `--horizon-days`

### 3.2 模拟数据独立落盘（`experiment_generate_sim_data.py`）
- 仅生成并写盘，不跑选择迭代
- 输出目录结构：
- `base/daily_returns.csv`
- `factors/<factor_id>.csv`
- `pools/<pool_name>.csv`
- `labels/forward_returns_h{window}.csv`（可选）
- `meta/simulation_manifest.json`

### 3.3 真实数据单场景（`experiment_real_data_single.py`）
- 输入：
- `--daily-returns`
- `--factors-dir`
- `--pool-file`（可选）
- 输出：
- 与模拟实验相同的因子库跟踪产物（round/tracker/final_library/svg/csv）

### 3.4 多asof滚动出库（`experiment_real_data_asof_rolling.py`）
- 支持两种 asof 输入方式：
- 显式列表：`--asof-dates`
- 区间生成：`--asof-start/--asof-end/--asof-step-days`
- 每个 asof 独立执行：
- 以 `lookback_days` 构造回看窗口
- 按 `train/validation/test` 切分并出最终库
- 仅关注最终库与跨日期对比，不依赖每轮细节

## 4. 关键配置映射

配置文件: `config/evaluation_config.yaml`

- `time_windows.selection`: 选择阶段多窗口（默认 5/20/60）
- `time_windows.evaluation.selected_short`: 选中因子 success 回看窗口（默认 10）
- `annualization_days`: 全链路年化天数（selector/factor/marginal/OOS统一口径）
- `success_thresholds.selected`: 选中因子 success 阈值
- `success_thresholds.unselected`: 未选中因子边际评估阈值
- `bayesian.update_rules`: alpha/beta 更新权重
- `marginal_contribution`: 组合方法、替换策略、最小改善阈值

## 5. 架构变更同步要求

若出现以下任一变更，必须同步更新文档:
- 模块职责/调用链变更
- 选择逻辑或更新逻辑变更
- 成功判定阈值或参数变更
- 输出文件结构或字段变更

必须同步更新:
- `docs/CODE_ARCHITECTURE.md`
- `docs/EVALUATION_STANDARDS.md`
- `docs/ITERATION3_SUMMARY.md`

补充协议文档:
- `docs/FACTOR_LIBRARY_EVAL_PROTOCOL.md`
