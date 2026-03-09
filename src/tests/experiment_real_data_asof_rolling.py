#!/usr/bin/env python3
"""
实验入口：指定单日/多日 asof_date，滚动生成最终因子库并做跨日期对比
"""

import argparse
import csv
import os
import sys
from typing import List

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from workflows.asof_library_generator import AsOfLibraryGenerator, AsOfRollingConfig


def _load_trading_dates(daily_returns_file: str) -> List[str]:
    dates = set()
    with open(daily_returns_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dates.add(row["end_date"])
    return sorted(dates)


def _build_asof_dates(
    explicit_asof_dates: str,
    daily_returns_file: str,
    asof_start: str,
    asof_end: str,
    asof_step_days: int,
) -> List[str]:
    if explicit_asof_dates:
        return [x.strip() for x in explicit_asof_dates.split(",") if x.strip()]

    if not (asof_start and asof_end):
        raise ValueError("请提供 --asof-dates，或同时提供 --asof-start/--asof-end")
    if asof_step_days < 1:
        raise ValueError("--asof-step-days 必须>=1")

    trading_dates = _load_trading_dates(daily_returns_file)
    in_range = [d for d in trading_dates if asof_start <= d <= asof_end]
    if not in_range:
        raise ValueError("给定区间内无交易日")
    return in_range[::asof_step_days]


def main():
    parser = argparse.ArgumentParser(description="真实数据 asof 滚动出库")
    parser.add_argument("--daily-returns", type=str, required=True, help="base/daily_returns.csv")
    parser.add_argument("--factors-dir", type=str, required=True, help="factors目录")
    parser.add_argument("--pool-file", type=str, default=None, help="pools/<pool>.csv，可选")
    parser.add_argument("--factor-glob", type=str, default="*.csv", help="因子文件匹配表达式")
    parser.add_argument("--output-dir", type=str, default="", help="汇总输出目录（默认自动时间戳）")

    parser.add_argument("--asof-dates", type=str, default="", help="逗号分隔，如 2025-07-01,2025-08-01")
    parser.add_argument("--asof-start", type=str, default="", help="asof起始日期（用于区间生成）")
    parser.add_argument("--asof-end", type=str, default="", help="asof结束日期（用于区间生成）")
    parser.add_argument("--asof-step-days", type=int, default=21, help="区间生成时每隔多少个交易日取一个asof")

    parser.add_argument("--lookback-days", type=int, default=1000, help="每个asof回看窗口长度")
    parser.add_argument("--target-size", type=int, default=30)
    parser.add_argument("--update-frequency", type=int, default=21)
    parser.add_argument("--horizon-days", type=int, default=5)
    parser.add_argument("--split-gap-days", type=int, default=None)
    parser.add_argument("--asof-filter", action="store_true", help="开启as-of可得性过滤评估")
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--validation-ratio", type=float, default=0.3)
    parser.add_argument("--test-ratio", type=float, default=0.0)
    parser.add_argument("--eval-mode", type=str, default="strict_holdout", choices=["strict_holdout", "walk_forward_test"])
    parser.add_argument("--num-test-rounds", type=int, default=None, help="限制轮次")
    parser.add_argument("--scenario-name", type=str, default="real_asof_rolling")
    args = parser.parse_args()

    asof_dates = _build_asof_dates(
        explicit_asof_dates=args.asof_dates,
        daily_returns_file=args.daily_returns,
        asof_start=args.asof_start,
        asof_end=args.asof_end,
        asof_step_days=args.asof_step_days,
    )
    print(f"asof日期数量: {len(asof_dates)}")
    print("asof列表:", ", ".join(asof_dates))

    cfg = AsOfRollingConfig(
        scenario_name=args.scenario_name,
        asof_dates=asof_dates,
        lookback_days=args.lookback_days,
        target_size=args.target_size,
        update_frequency=args.update_frequency,
        horizon_days=args.horizon_days,
        split_gap_days=args.split_gap_days,
        asof_filter=bool(args.asof_filter),
        train_ratio=args.train_ratio,
        validation_ratio=args.validation_ratio,
        test_ratio=args.test_ratio,
        eval_mode=args.eval_mode,
        num_test_rounds=args.num_test_rounds,
        factor_glob=args.factor_glob,
        daily_returns_file=args.daily_returns,
        factors_dir=args.factors_dir,
        pool_file=args.pool_file,
        output_dir=(args.output_dir or None),
    )
    runner = AsOfLibraryGenerator(cfg)
    runner.run()


if __name__ == "__main__":
    main()
