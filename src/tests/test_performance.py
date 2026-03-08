#!/usr/bin/env python3
"""
实验入口：多场景因子库性能实验

说明：
- 本文件仅作为实验/demo入口。
- 迭代引擎位于 `src/workflows/`。
- 场景构建与对比器位于 `src/experiments/`。
"""

import os
import sys
import argparse

# 添加项目根目录到 Python 路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from experiments.factor_library_scenario_experiment import (
    ScenarioComparator,
    build_scenario,
    build_default_scenarios,
)


def main():
    parser = argparse.ArgumentParser(description="因子库实验入口")
    parser.add_argument(
        "--baseline-only",
        action="store_true",
        help="仅运行baseline场景，不做多场景对比",
    )
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--num-stocks", type=int, default=None, help="股票数量覆盖")
    parser.add_argument("--num-factors", type=int, default=None, help="因子数量覆盖")
    parser.add_argument("--target-size", type=int, default=None, help="入库因子数量覆盖")
    parser.add_argument("--num-days", type=int, default=None, help="总交易日覆盖")
    parser.add_argument("--horizon-days", type=int, default=None, help="前瞻窗口天数(共享于IC/LS)")
    parser.add_argument("--annual-days", type=int, default=250, help="年化天数")
    args = parser.parse_args()

    if args.baseline_only:
        scenarios = [
            build_scenario("baseline", good_to_good=0.80, stock_sigma=0.002, seed=args.seed)
        ]
    else:
        scenarios = build_default_scenarios()

    for cfg in scenarios:
        cfg.RANDOM_SEED = args.seed
        if args.num_stocks is not None:
            cfg.NUM_STOCKS = args.num_stocks
        if args.num_factors is not None:
            cfg.NUM_FACTORS = args.num_factors
        if args.target_size is not None:
            cfg.TARGET_SIZE = args.target_size
        if args.num_days is not None:
            cfg.NUM_DAYS = args.num_days
        if args.horizon_days is not None:
            cfg.ROLLING_WINDOW = args.horizon_days
        cfg.ANNUAL_DAYS = args.annual_days
        if cfg.TARGET_SIZE > cfg.NUM_FACTORS:
            raise ValueError("target-size 不能大于 num-factors")

    comparator = ScenarioComparator(scenarios)
    return comparator.run()


if __name__ == "__main__":
    main()
