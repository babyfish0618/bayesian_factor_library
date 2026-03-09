"""
分阶段状态转移对照实验

目标：
- 对比 train/validation/test 采用不同转移矩阵时，因子库表现与稳定性变化
"""

import copy
from typing import Dict, List

from experiments.factor_library_scenario_experiment import PerformanceTestConfig, ScenarioComparator


def _build_transition(good_to_good: float) -> Dict[str, Dict[str, float]]:
    base = {
        "good": {"good": 0.80, "medium": 0.17, "bad": 0.03},
        "medium": {"good": 0.20, "medium": 0.60, "bad": 0.20},
        "bad": {"good": 0.05, "medium": 0.20, "bad": 0.75},
    }
    out = copy.deepcopy(base)
    residual = max(1.0 - good_to_good, 0.0)
    mid_bad = base["good"]["medium"] + base["good"]["bad"]
    out["good"]["good"] = good_to_good
    out["good"]["medium"] = residual * (base["good"]["medium"] / mid_bad)
    out["good"]["bad"] = residual * (base["good"]["bad"] / mid_bad)
    return out


def build_phase_regime_scenarios() -> List[PerformanceTestConfig]:
    scenarios = []

    baseline = PerformanceTestConfig()
    baseline.SCENARIO_NAME = "stationary_baseline"
    baseline.NUM_DAYS = 1400
    baseline.NUM_TEST_ROUNDS = None
    baseline.EVAL_MODE = "strict_holdout"
    baseline.TRAIN_RATIO = 0.70
    baseline.VALIDATION_RATIO = 0.20
    baseline.TEST_RATIO = 0.10
    baseline.TARGET_SIZE = 30
    baseline.UPDATE_FREQUENCY = 21
    baseline.STOCK_RETURN_SIGMA = 0.0025
    baseline.TRANSITION_PROBS = _build_transition(0.72)
    scenarios.append(baseline)

    easier = copy.deepcopy(baseline)
    easier.SCENARIO_NAME = "val_test_easier"
    easier.PHASE_TRANSITION_PROBS = {
        "train": _build_transition(0.72),
        "validation": _build_transition(0.88),
        "test": _build_transition(0.88),
    }
    scenarios.append(easier)

    harder = copy.deepcopy(baseline)
    harder.SCENARIO_NAME = "val_test_harder"
    harder.PHASE_TRANSITION_PROBS = {
        "train": _build_transition(0.72),
        "validation": _build_transition(0.55),
        "test": _build_transition(0.55),
    }
    scenarios.append(harder)

    return scenarios


def run_phase_regime_comparison(
    baseline_only: bool = False,
    seed: int = 42,
    num_stocks: int = None,
    num_factors: int = None,
    target_size: int = None,
    num_days: int = None,
    horizon_days: int = None,
    split_gap_days: int = None,
    show_progress: bool = False,
    asof_filter: bool = False,
    export_sim_data: bool = False,
    export_root: str = "data/simulated_phase_regime",
    export_pool: str = "all_stocks",
    export_labels: bool = True,
):
    scenarios = build_phase_regime_scenarios()
    if baseline_only:
        scenarios = [scenarios[0]]
    for cfg in scenarios:
        cfg.RANDOM_SEED = seed
        if num_stocks is not None:
            cfg.NUM_STOCKS = num_stocks
        if num_factors is not None:
            cfg.NUM_FACTORS = num_factors
        if target_size is not None:
            cfg.TARGET_SIZE = target_size
        if num_days is not None:
            cfg.NUM_DAYS = num_days
        if horizon_days is not None:
            cfg.ROLLING_WINDOW = horizon_days
        if split_gap_days is not None:
            cfg.SPLIT_GAP_DAYS = split_gap_days
        cfg.SHOW_PROGRESS = bool(show_progress)
        cfg.ENABLE_ASOF_FILTER = bool(asof_filter)
        cfg.EXPORT_SIM_DATA_AS_REAL_FORMAT = bool(export_sim_data)
        cfg.EXPORT_SIM_OUTPUT_ROOT = export_root
        cfg.EXPORT_SIM_POOL_NAME = export_pool
        cfg.EXPORT_SIM_INCLUDE_FORWARD_LABELS = bool(export_labels)
        if cfg.TARGET_SIZE > cfg.NUM_FACTORS:
            raise ValueError("target_size cannot exceed num_factors")
    comparator = ScenarioComparator(scenarios)
    results = comparator.run()

    print("\n" + "=" * 80)
    print("分阶段场景附加汇总（最终库 Validation/Test）")
    print("=" * 80)
    print(
        f"{'scenario':<22} {'mode':<16} {'final_val_icir':>14} {'final_test_icir':>15} "
        f"{'final_val_sharpe':>16} {'final_test_sharpe':>17}"
    )
    for res in results:
        val = res.get("final_eval_validation", {})
        test = res.get("final_eval_test", {})
        print(
            f"{res.get('scenario_name',''):<22} "
            f"{res.get('eval_mode',''):<16} "
            f"{val.get('icir', 0.0):>14.3f} "
            f"{test.get('icir', 0.0):>15.3f} "
            f"{val.get('sharpe', 0.0):>16.3f} "
            f"{test.get('sharpe', 0.0):>17.3f}"
        )

    return results
