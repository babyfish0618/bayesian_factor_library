#!/usr/bin/env python3
"""
实验入口：真实数据单场景运行（无场景对比）
"""

import argparse
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from experiments.factor_library_scenario_experiment import PerformanceTestConfig
from workflows.real_data_iteration_engine import RealDataIterationEngine


def main():
    parser = argparse.ArgumentParser(description="真实数据单场景因子库迭代")
    parser.add_argument("--daily-returns", type=str, required=True, help="base/daily_returns.csv")
    parser.add_argument("--factors-dir", type=str, required=True, help="factors目录")
    parser.add_argument("--pool-file", type=str, default=None, help="pools/<pool>.csv，可选")
    parser.add_argument("--factor-glob", type=str, default="*.csv", help="因子文件匹配表达式")
    parser.add_argument("--target-size", type=int, default=30)
    parser.add_argument("--update-frequency", type=int, default=21)
    parser.add_argument("--horizon-days", type=int, default=5)
    parser.add_argument("--split-gap-days", type=int, default=None, help="train/val/test之间的间隔天数")
    parser.add_argument("--asof-filter", action="store_true", help="开启as-of可得性过滤评估")
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--test-ratio", type=float, default=0.1)
    parser.add_argument("--eval-mode", type=str, default="strict_holdout", choices=["strict_holdout", "walk_forward_test"])
    parser.add_argument("--num-test-rounds", type=int, default=None, help="限制轮次；默认跑完整训练区间")
    parser.add_argument("--scenario-name", type=str, default="real_data_single")
    args = parser.parse_args()

    cfg = PerformanceTestConfig()
    cfg.SCENARIO_NAME = args.scenario_name
    cfg.TARGET_SIZE = args.target_size
    cfg.UPDATE_FREQUENCY = args.update_frequency
    cfg.ROLLING_WINDOW = args.horizon_days
    if args.split_gap_days is not None:
        cfg.SPLIT_GAP_DAYS = args.split_gap_days
    cfg.ENABLE_ASOF_FILTER = bool(args.asof_filter)
    cfg.TRAIN_RATIO = args.train_ratio
    cfg.VALIDATION_RATIO = args.validation_ratio
    cfg.TEST_RATIO = args.test_ratio
    cfg.EVAL_MODE = args.eval_mode
    cfg.NUM_TEST_ROUNDS = args.num_test_rounds
    cfg.EXPORT_SIM_DATA_AS_REAL_FORMAT = False
    cfg.REAL_DATA_MODE = True

    cfg.REAL_DATA_DAILY_RETURNS_FILE = args.daily_returns
    cfg.REAL_DATA_FACTORS_DIR = args.factors_dir
    cfg.REAL_DATA_POOL_FILE = args.pool_file
    cfg.REAL_DATA_FACTOR_GLOB = args.factor_glob

    engine = RealDataIterationEngine(cfg)
    engine.run_full_test()


if __name__ == "__main__":
    main()
