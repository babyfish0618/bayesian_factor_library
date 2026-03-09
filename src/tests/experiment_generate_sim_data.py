#!/usr/bin/env python3
"""
实验入口：仅生成模拟数据并写入本地（真实数据格式）
"""

import argparse
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from experiments.factor_library_scenario_experiment import PerformanceTestConfig
from simulation.latent_factor_data_simulator import (
    LatentFactorDataSimulator,
    LatentFactorSimulationConfig,
)


def main():
    parser = argparse.ArgumentParser(description="生成模拟数据到本地文件夹")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-stocks", type=int, default=1000)
    parser.add_argument("--num-days", type=int, default=250)
    parser.add_argument("--start-date", type=str, default="2014-01-01", help="起始日期 YYYY-MM-DD")
    parser.add_argument("--end-date", type=str, default=None, help="结束日期 YYYY-MM-DD；若提供则优先按日期区间生成")
    parser.add_argument("--num-factors", type=int, default=100)
    parser.add_argument("--horizon-days", type=int, default=5)
    parser.add_argument("--output-root", type=str, default="data/simulated_standalone")
    parser.add_argument("--pool-name", type=str, default="all_stocks")
    parser.add_argument("--no-labels", action="store_true")
    parser.add_argument("--progress", action="store_true", help="显示模拟/写盘进度条")
    args = parser.parse_args()

    cfg = PerformanceTestConfig()
    cfg.RANDOM_SEED = args.seed
    cfg.NUM_STOCKS = args.num_stocks
    cfg.NUM_DAYS = args.num_days
    cfg.START_DATE = args.start_date
    cfg.END_DATE = args.end_date
    cfg.NUM_FACTORS = args.num_factors
    cfg.ROLLING_WINDOW = args.horizon_days

    sim_cfg = LatentFactorSimulationConfig(
        num_stocks=cfg.NUM_STOCKS,
        num_days=cfg.NUM_DAYS,
        num_factors=cfg.NUM_FACTORS,
        rolling_window=cfg.ROLLING_WINDOW,
        stock_return_mu=cfg.STOCK_RETURN_MU,
        stock_return_sigma=cfg.STOCK_RETURN_SIGMA,
        good_ratio=cfg.GOOD_FACTOR_RATIO,
        medium_ratio=cfg.MEDIUM_FACTOR_RATIO,
        bad_ratio=cfg.BAD_FACTOR_RATIO,
        good_ic_mean=cfg.GOOD_IC_MEAN,
        good_ic_std=cfg.GOOD_IC_STD,
        medium_ic_mean=cfg.MEDIUM_IC_MEAN,
        medium_ic_std=cfg.MEDIUM_IC_STD,
        bad_ic_mean=cfg.BAD_IC_MEAN,
        bad_ic_std=cfg.BAD_IC_STD,
        latent_states=cfg.LATENT_STATES,
        init_state_probs=cfg.INIT_STATE_PROBS,
        transition_probs=cfg.TRANSITION_PROBS,
        anchor_reversion_prob=cfg.ANCHOR_REVERSION_PROB,
        random_seed=cfg.RANDOM_SEED,
        start_date=cfg.START_DATE,
        end_date=cfg.END_DATE,
        show_progress=bool(args.progress),
    )
    simulator = LatentFactorDataSimulator(sim_cfg)
    dates, _, forward_returns = simulator.build_market_data()
    simulator.generate_factors_with_regime(
        dates=dates,
        forward_returns=forward_returns,
        phase_boundaries=None,
        phase_transition_probs=None,
    )
    out = simulator.export_as_real_data_format(
        output_root=args.output_root,
        pool_name=args.pool_name,
        include_forward_returns=(not args.no_labels),
    )
    print("模拟数据导出完成:")
    for k, v in out.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
