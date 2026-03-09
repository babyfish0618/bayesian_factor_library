#!/usr/bin/env python3
"""
实验入口：train/validation/test 分阶段状态转移对照

说明：
- 本文件仅作为实验入口。
- 复用逻辑位于 `src/experiments/phase_regime_comparison_experiment.py`。
"""

import os
import sys
import argparse

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from experiments.phase_regime_comparison_experiment import run_phase_regime_comparison


def main():
    parser = argparse.ArgumentParser(description="分阶段状态转移对照实验入口")
    parser.add_argument(
        "--baseline-only",
        action="store_true",
        help="仅运行stationary_baseline场景",
    )
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--num-stocks", type=int, default=None, help="股票数量覆盖")
    parser.add_argument("--num-factors", type=int, default=None, help="因子数量覆盖")
    parser.add_argument("--target-size", type=int, default=None, help="入库因子数量覆盖")
    parser.add_argument("--num-days", type=int, default=None, help="总交易日覆盖")
    parser.add_argument("--horizon-days", type=int, default=None, help="前瞻窗口天数(共享于IC/LS)")
    parser.add_argument("--split-gap-days", type=int, default=None, help="train/val/test之间的间隔天数")
    parser.add_argument("--progress", action="store_true", help="显示模拟进度条")
    parser.add_argument("--asof-filter", action="store_true", help="开启as-of可得性过滤评估")
    parser.add_argument(
        "--export-sim-data",
        action="store_true",
        help="将模拟数据按真实数据格式写入 data 目录",
    )
    parser.add_argument(
        "--export-root",
        type=str,
        default="data/simulated_phase_regime",
        help="模拟数据导出根目录",
    )
    parser.add_argument(
        "--export-pool",
        type=str,
        default="all_stocks",
        help="导出的股票池文件名（不含扩展名）",
    )
    parser.add_argument(
        "--no-export-labels",
        action="store_true",
        help="导出时不写前瞻收益标签文件",
    )
    args = parser.parse_args()
    run_phase_regime_comparison(
        baseline_only=args.baseline_only,
        seed=args.seed,
        num_stocks=args.num_stocks,
        num_factors=args.num_factors,
        target_size=args.target_size,
        num_days=args.num_days,
        horizon_days=args.horizon_days,
        split_gap_days=args.split_gap_days,
        show_progress=args.progress,
        asof_filter=args.asof_filter,
        export_sim_data=args.export_sim_data,
        export_root=args.export_root,
        export_pool=args.export_pool,
        export_labels=(not args.no_export_labels),
    )


if __name__ == "__main__":
    main()
