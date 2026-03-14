# Tests 运行示例（example）

更新时间: 2026-03-09
适用目录: `src/tests/`

说明:
- 本文档用于快速复现实验入口的调用方式。
- 每个示例包含“目的 + 可直接运行命令”。
- 年化天数统一读取 `config/evaluation_config.yaml` 中 `annualization_days`（不再提供 `--annual-days`）。

## 1) `test_performance.py`

目的:
- 运行主性能实验（可 baseline-only，也可多场景对比）。
- 支持 as-of 过滤、split gap、模拟数据落盘。

示例:
```bash
python src/tests/test_performance.py \
  --baseline-only \
  --seed 42 \
  --num-stocks 1000 \
  --num-factors 100 \
  --target-size 30 \
  --num-days 500 \
  --horizon-days 5 \
  --split-gap-days 5 \
  --asof-filter \
  --progress
```

常用可测参数:
- `--baseline-only`
- `--seed`
- `--num-stocks --num-factors --target-size --num-days`
- `--horizon-days`
- `--split-gap-days`
- `--asof-filter`
- `--progress`
- `--export-sim-data --export-root --export-pool --no-export-labels`

---

## 2) `experiment_generate_sim_data.py`

目的:
- 仅生成模拟数据并写盘到真实数据格式目录，不运行因子库迭代。

示例A（标准版）:
```bash
python src/tests/experiment_generate_sim_data.py \
  --seed 42 \
  --num-stocks 1000 \
  --num-days 250 \
  --start-date 2014-01-01 \
  --end-date 2014-12-31 \
  --num-factors 100 \
  --horizon-days 5 \
  --output-root data/sim_progress_demo \
  --pool-name all_stocks \
  --progress
```

示例B（不写标签）:
```bash
python src/tests/experiment_generate_sim_data.py \
  --output-root data/sim_no_labels \
  --no-labels \
  --progress
```

常用可测参数:
- `--seed`
- `--num-stocks --num-days --num-factors`
- `--start-date --end-date`（若给 `end-date`，按日期区间生成，优先于 `num-days`）
- `--horizon-days`
- `--output-root --pool-name`
- `--no-labels`
- `--progress`

---

## 3) `experiment_real_data_single.py`

目的:
- 从真实数据目录读数，运行单场景因子库迭代（无场景对比）。

示例:
```bash
python src/tests/experiment_real_data_single.py \
  --daily-returns data/sim_progress_demo/base/daily_returns.csv \
  --factors-dir data/sim_progress_demo/factors \
  --pool-file data/sim_progress_demo/pools/all_stocks.csv \
  --factor-glob "*.csv" \
  --target-size 30 \
  --update-frequency 21 \
  --horizon-days 5 \
  --split-gap-days 5 \
  --asof-filter \
  --train-ratio 0.7 \
  --validation-ratio 0.2 \
  --test-ratio 0.1 \
  --eval-mode strict_holdout
```

常用可测参数:
- 数据路径: `--daily-returns --factors-dir --pool-file --factor-glob`
- 训练参数: `--target-size --update-frequency --horizon-days`
- 切分与评估: `--train-ratio --validation-ratio --test-ratio --eval-mode`
- 防泄露: `--split-gap-days --asof-filter`
- 调试轮次: `--num-test-rounds`

---

## 4) `experiment_phase_regime_comparison.py`

目的:
- 运行分阶段状态转移对照实验（train/validation/test regime变化）。

示例:
```bash
python src/tests/experiment_phase_regime_comparison.py \
  --baseline-only \
  --seed 42 \
  --num-stocks 1000 \
  --num-factors 100 \
  --target-size 30 \
  --num-days 800 \
  --horizon-days 5 \
  --split-gap-days 5 \
  --asof-filter \
  --progress
```

常用可测参数:
- `--baseline-only --seed`
- `--num-stocks --num-factors --target-size --num-days`
- `--horizon-days`
- `--split-gap-days --asof-filter`
- `--progress`
- `--export-sim-data --export-root --export-pool --no-export-labels`

---

## 5) `experiment_real_data_asof_rolling.py`

目的:
- 指定单个或多个 `asof_date`，在每个日期独立回看窗口内生成最终因子库。
- 输出跨日期对比（重叠度/Jaccard/换手率）与各自验证集表现。

示例A（显式日期列表）:
```bash
python src/tests/experiment_real_data_asof_rolling.py \
  --daily-returns data/sim_progress_demo/base/daily_returns.csv \
  --factors-dir data/sim_progress_demo/factors \
  --pool-file data/sim_progress_demo/pools/all_stocks.csv \
  --asof-dates 2014-10-15,2014-12-10 \
  --lookback-days 1000 \
  --target-size 30 \
  --horizon-days 5 \
  --split-gap-days 5 \
  --train-ratio 0.7 \
  --validation-ratio 0.3 \
  --test-ratio 0.0 \
  --asof-filter \
  --output-dir outputs/performance_tracking/asof_daily_run
```

示例B（区间自动生成 asof）:
```bash
python src/tests/experiment_real_data_asof_rolling.py \
  --daily-returns data/sim_progress_demo/base/daily_returns.csv \
  --factors-dir data/sim_progress_demo/factors \
  --pool-file data/sim_progress_demo/pools/all_stocks.csv \
  --asof-start 2014-08-01 \
  --asof-end 2014-12-10 \
  --asof-step-days 21 \
  --lookback-days 1000 \
  --target-size 30 \
  --horizon-days 5 \
  --split-gap-days 5 \
  --train-ratio 0.7 \
  --validation-ratio 0.3 \
  --test-ratio 0.0 \
  --asof-filter \
```

常用可测参数:
- asof输入: `--asof-dates` 或 `--asof-start/--asof-end/--asof-step-days`
- 窗口: `--lookback-days`
- 切分: `--train-ratio --validation-ratio --test-ratio`
- 防泄露: `--split-gap-days --asof-filter`
- 训练参数: `--target-size --update-frequency --horizon-days`
- 汇总输出: `--output-dir`

输出:
- `asof_library_summary.csv`
- `asof_library_overlap.csv`
- `asof_library_seq_turnover.csv`
- `asof_library_factors.json`

---

## 6) `experiment_stability_early_stop.py`

目的:
- 长周期稳定性/早停实验（当前脚本内参数写死，直接运行）。

示例:
```bash
python src/tests/experiment_stability_early_stop.py
```

说明:
- 若需参数化运行，建议后续为该入口补充 argparse。

---

## 7) 历史数学校验脚本（已归档）

目的:
- 验证底层数学逻辑（IC控制、相关性构造、权重归一化），不走完整迭代引擎。
- 当前不属于主实验入口，已移动到归档目录。

示例:
```bash
python src/tests/_archive/experiment_math_smoke_ic_control.py
python src/tests/_archive/experiment_math_validation_correlation.py
```

---

## 8) 结果产物位置

- 实验产物默认在: `outputs/performance_tracking/<run_tag>/`
- 模拟数据写盘目录由 `--output-root` 或 `--export-root` 决定。
