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
    parser.add_argument("--annual-days", type=int, default=250, help="年化天数")
    args = parser.parse_args()
    run_phase_regime_comparison(
        baseline_only=args.baseline_only,
        seed=args.seed,
        num_stocks=args.num_stocks,
        num_factors=args.num_factors,
        target_size=args.target_size,
        num_days=args.num_days,
        horizon_days=args.horizon_days,
        annual_days=args.annual_days,
    )


if __name__ == "__main__":
    main()
