#!/usr/bin/env python3
"""
实验入口：长周期稳定性/早停跟踪

说明：
- 本文件仅作为实验入口。
- 复用逻辑在 `src/experiments/factor_library_stability_experiment.py`。
"""

import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from experiments.factor_library_stability_experiment import (
    StabilityExperimentConfig,
    StabilityExperimentRunner,
)


def main():
    cfg = StabilityExperimentConfig(
        scenario_name="stability_long_horizon_v1",
        num_days=1200,
        num_test_rounds=None,
        target_size=30,
        good_to_good=0.72,
        stock_return_sigma=0.0025,
        eval_mode="walk_forward_test",
        train_ratio=0.7,
        validation_ratio=0.2,
        test_ratio=0.1,
        early_stop_window=3,
        early_stop_min_rounds=5,
        early_stop_eps_turnover=0.15,
        early_stop_eps_perf=0.05,
        early_stop_delta=0.02,
    )
    runner = StabilityExperimentRunner(cfg)
    result = runner.run()

    artifact = result.get("stability_artifacts", {})
    print("\n稳定性实验输出:")
    print(f"  目录: {artifact.get('stability_output_dir')}")
    print(f"  曲线图: {artifact.get('stability_svg')}")
    print(f"  报告: {artifact.get('stability_report_json')}")


if __name__ == "__main__":
    main()
