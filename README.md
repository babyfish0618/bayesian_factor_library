# 贝叶斯因子库维护系统

本仓库实现一个面向“因子库维护”的贝叶斯选择系统：在已有因子池中，按轮次选择固定规模因子库，并根据新增观测持续更新后验参数。

当前主链路为 Iteration3+（多窗口打分、边际贡献评估、稳定性筛选出库、真实数据/模拟数据双入口）。

## 当前主链路（与代码一致）

核心流程：

1. 数据准备（模拟或真实数据）
2. Observe/Update：使用上一轮入库因子的新增表现更新后验
3. Select：`aggregate_score + Thompson Sampling` 选新库
4. Validation/Test 评估：计算 OOS 指标
5. 稳定性判定与最终出库（按 `EVAL_MODE`）

关键实现文件：

- `src/workflows/factor_library_iteration_engine.py`：单场景迭代引擎（主流程）
- `src/core/bayesian_selector_v2.py`：因子选择与贝叶斯更新
- `src/core/factor_enhanced.py`：因子状态与多窗口统计
- `src/evaluation/marginal_contrib.py`：未选中因子边际贡献评估
- `src/evaluation/portfolio_simulator.py`：组合模拟与替换评估
- `src/core/correlation_calculator.py`：相关性计算
- `src/simulation/latent_factor_data_simulator.py`：模拟数据与标签生成
- `src/workflows/real_data_iteration_engine.py`：真实数据单场景流程
- `src/workflows/asof_library_generator.py`：多 `asof_date` 滚动出库

说明：

- 历史路径（`src/archive`、`src/core/__archive`、`src/simulation/__archive`、`src/tests/_archive`）不是当前主链路。
- README 不再描述 `mvp_selector`、`integrated_selector`、`test_mvp.py` 等旧模块。

## 项目结构（主链路视角）

```text
.
├── src/
│   ├── core/
│   │   ├── bayesian_selector_v2.py
│   │   ├── factor_enhanced.py
│   │   └── correlation_calculator.py
│   ├── evaluation/
│   │   ├── marginal_contrib.py
│   │   ├── portfolio_simulator.py
│   │   ├── library_tracker.py
│   │   └── library_dynamics_plotter.py
│   ├── simulation/
│   │   └── latent_factor_data_simulator.py
│   ├── workflows/
│   │   ├── factor_library_iteration_engine.py
│   │   ├── real_data_iteration_engine.py
│   │   └── asof_library_generator.py
│   ├── experiments/
│   │   ├── factor_library_scenario_experiment.py
│   │   ├── factor_library_stability_experiment.py
│   │   └── phase_regime_comparison_experiment.py
│   └── tests/
│       ├── test_performance.py
│       ├── experiment_generate_sim_data.py
│       ├── experiment_phase_regime_comparison.py
│       ├── experiment_real_data_single.py
│       ├── experiment_real_data_asof_rolling.py
│       └── experiment_stability_early_stop.py
├── config/
│   └── evaluation_config.yaml
├── docs/
│   ├── CODE_ARCHITECTURE.md
│   ├── EVALUATION_STANDARDS.md
│   ├── FACTOR_LIBRARY_EVAL_PROTOCOL.md
│   ├── PARAMETER_MAPPING.md
│   └── example.md
└── AI_CONTEXT.md / AGENTS.md / AI_LOG.md
```

## 运行方式

环境：

- Python 3.10+（纯 Python 项目）
- 依赖安装：`pip install -r requirements.txt`

常用入口：

```bash
# 1) 模拟数据多场景实验（默认）
python src/tests/test_performance.py

# 2) 仅 baseline 场景
python src/tests/test_performance.py --baseline-only --seed 42

# 3) 分阶段状态转移对照实验
python src/tests/experiment_phase_regime_comparison.py --baseline-only

# 4) 仅生成模拟数据（真实数据格式）
python src/tests/experiment_generate_sim_data.py --output-root data/simulated_demo

# 5) 真实数据单场景
python src/tests/experiment_real_data_single.py \
  --daily-returns <path/to/daily_returns.csv> \
  --factors-dir <path/to/factors_dir>

# 6) 多 asof 滚动出库
python src/tests/experiment_real_data_asof_rolling.py \
  --daily-returns <path/to/daily_returns.csv> \
  --factors-dir <path/to/factors_dir> \
  --asof-dates 2025-07-01,2025-08-01
```

参数细节见 `docs/example.md` 与 `docs/PARAMETER_MAPPING.md`。

## 配置与评估口径

统一配置文件：

- `config/evaluation_config.yaml`

重点参数：

- `annualization_days`：全局年化天数
- `time_windows`：选择/评估窗口与 `min_periods`
- `success_thresholds`：选中/未选中判定阈值
- `bayesian.selection_blend`：`aggregate_score` 与 Thompson 采样融合权重
- `marginal_contribution.scoring`：边际贡献综合评分规则

评估协议与口径：

- `docs/FACTOR_LIBRARY_EVAL_PROTOCOL.md`
- `docs/EVALUATION_STANDARDS.md`

## 主要输出产物

默认输出目录：`outputs/performance_tracking/<run_tag>/`

常见文件：

- `round_summary.csv`
- `factor_round_status.csv`
- `library_metrics.json`
- `round_compact_summary.csv`
- `validation_dynamics.svg`
- `test_dynamics.svg`（有测试集时）
- `final_library.json`

多 asof 任务额外输出：

- `asof_library_summary.csv`
- `asof_library_overlap.csv`
- `asof_library_seq_turnover.csv`
- `asof_library_factors.json`

## 文档与协作约束

- 先读：`AI_CONTEXT.md`、`AGENTS.md`、`AI_LOG.md`
- 主文档：`docs/CODE_ARCHITECTURE.md`、`docs/example.md`
- 历史代码/文档默认可跳过：`archive`、`__archive`、`docs/_archive`

## 已知注意事项

- 运行真实数据入口前请先安装 `requirements.txt` 依赖。
- `daily_returns / factors / pool` 需遵循本文与 `docs/REAL_DATA_INTEGRATION_GUIDE.md` 的字段约定。
