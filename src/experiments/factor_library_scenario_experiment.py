"""
多场景因子库实验编排

定义实验配置与场景对比器，供 tests/demo 入口调用。
"""

import copy
import csv
import os
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import numpy as np

from workflows.factor_library_iteration_engine import FactorLibraryIterationEngine


@dataclass
class PerformanceTestConfig:
    """性能测试配置（实验层）。"""

    NUM_STOCKS: int = 1000
    NUM_DAYS: int = 250
    NUM_FACTORS: int = 100
    TARGET_SIZE: int = 30

    ROLLING_WINDOW: int = 5
    UPDATE_FREQUENCY: int = 21
    SPLIT_GAP_DAYS: Optional[int] = None
    SHOW_PROGRESS: bool = False

    GOOD_FACTOR_RATIO: float = 0.2
    MEDIUM_FACTOR_RATIO: float = 0.3
    BAD_FACTOR_RATIO: float = 0.5

    GOOD_IC_MEAN: float = 0.08
    GOOD_IC_STD: float = 0.02
    MEDIUM_IC_MEAN: float = 0.04
    MEDIUM_IC_STD: float = 0.03
    BAD_IC_MEAN: float = 0.01
    BAD_IC_STD: float = 0.04

    NUM_TEST_ROUNDS: Optional[int] = 5
    RANDOM_SEED: int = 42
    SCENARIO_NAME: str = "baseline"

    STOCK_RETURN_MU: float = 0.0005
    STOCK_RETURN_SIGMA: float = 0.002

    OOS_HORIZON: int = 21
    EVAL_MODE: str = "strict_holdout"  # strict_holdout | walk_forward_test
    ENABLE_ASOF_FILTER: bool = False
    TRAIN_RATIO: float = 0.7
    VALIDATION_RATIO: float = 0.2
    TEST_RATIO: float = 0.1
    EARLY_STOP_WINDOW: int = 3
    EARLY_STOP_MIN_ROUNDS: int = 3
    EARLY_STOP_EPS_TURNOVER: float = 0.15
    EARLY_STOP_EPS_PERF: float = 0.05
    EARLY_STOP_DELTA: float = 0.02

    LATENT_STATES: Tuple[str, str, str] = ("good", "medium", "bad")
    INIT_STATE_PROBS: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "good": {"good": 0.75, "medium": 0.20, "bad": 0.05},
        "medium": {"good": 0.20, "medium": 0.60, "bad": 0.20},
        "bad": {"good": 0.05, "medium": 0.20, "bad": 0.75},
    })
    TRANSITION_PROBS: Dict[str, Dict[str, float]] = field(default_factory=lambda: {
        "good": {"good": 0.80, "medium": 0.17, "bad": 0.03},
        "medium": {"good": 0.20, "medium": 0.60, "bad": 0.20},
        "bad": {"good": 0.05, "medium": 0.20, "bad": 0.75},
    })
    PHASE_TRANSITION_PROBS: Dict[str, Dict[str, Dict[str, float]]] = field(default_factory=dict)
    ANCHOR_REVERSION_PROB: Dict[str, float] = field(default_factory=lambda: {
        "good": 0.08,
        "medium": 0.05,
        "bad": 0.08,
    })
    EXPORT_SIM_DATA_AS_REAL_FORMAT: bool = False
    EXPORT_SIM_OUTPUT_ROOT: str = "data/simulated"
    EXPORT_SIM_POOL_NAME: str = "all_stocks"
    EXPORT_SIM_INCLUDE_FORWARD_LABELS: bool = True
    START_DATE: str = "2014-01-01"
    END_DATE: Optional[str] = None
    ASOF_FILTER_REF_DATE: Optional[str] = None


def build_scenario(
    name: str,
    good_to_good: float,
    stock_sigma: float,
    seed: int = 42,
    target_size: int = 30,
) -> PerformanceTestConfig:
    """构建单个场景配置。"""
    cfg = PerformanceTestConfig()
    cfg.SCENARIO_NAME = name
    cfg.RANDOM_SEED = seed
    cfg.STOCK_RETURN_SIGMA = stock_sigma
    cfg.TARGET_SIZE = target_size

    cfg.TRANSITION_PROBS = copy.deepcopy(cfg.TRANSITION_PROBS)
    cfg.TRANSITION_PROBS["good"]["good"] = good_to_good

    residual = max(1.0 - good_to_good, 0.0)
    base_mid_bad = (
        PerformanceTestConfig().TRANSITION_PROBS["good"]["medium"]
        + PerformanceTestConfig().TRANSITION_PROBS["good"]["bad"]
    )
    if base_mid_bad > 0:
        cfg.TRANSITION_PROBS["good"]["medium"] = residual * (
            PerformanceTestConfig().TRANSITION_PROBS["good"]["medium"] / base_mid_bad
        )
        cfg.TRANSITION_PROBS["good"]["bad"] = residual * (
            PerformanceTestConfig().TRANSITION_PROBS["good"]["bad"] / base_mid_bad
        )

    return cfg


class ScenarioComparator:
    """多场景对比运行器。"""

    def __init__(self, scenarios):
        self.scenarios = scenarios

    def run(self):
        scenario_results = []
        summary_rows = []
        print("\n" + "#" * 80)
        print("多场景模拟对比实验")
        print("#" * 80)

        for idx, cfg in enumerate(self.scenarios, start=1):
            print(f"\n>>> 场景 {idx}/{len(self.scenarios)}: {cfg.SCENARIO_NAME}")
            engine = FactorLibraryIterationEngine(cfg)
            result = engine.run_full_test()
            scenario_results.append(result)

        print("\n" + "=" * 80)
        print("场景对比汇总（关注 good 因子选中率）")
        print("=" * 80)
        print(
            f"{'scenario':<24} {'good->good':>10} {'ret_sigma':>10} "
            f"{'avg_good_sel':>14} {'avg_good_recall':>16} {'avg_update_succ':>16} {'avg_ls_rtn':>12}"
        )
        for res in scenario_results:
            params = res["scenario_params"]
            ls_values = [x.get("oos_ls_mean", 0.0) for x in res.get("round_iteration_metrics", [])]
            avg_ls = float(np.mean(ls_values)) if ls_values else 0.0
            print(
                f"{res['scenario_name']:<24} "
                f"{params['transition_good_to_good']:>10.2f} "
                f"{params['stock_return_sigma']:>10.4f} "
                f"{res['avg_good_selection_rate']:>14.2%} "
                f"{res['avg_good_recall']:>16.2%} "
                f"{res['avg_update_success_rate']:>16.2%} "
                f"{avg_ls:>12.6f}"
            )
            summary_rows.append({
                "scenario": res["scenario_name"],
                "eval_mode": res.get("eval_mode"),
                "transition_good_to_good": params["transition_good_to_good"],
                "stock_return_sigma": params["stock_return_sigma"],
                "avg_good_selection_rate": res["avg_good_selection_rate"],
                "avg_good_recall": res["avg_good_recall"],
                "avg_update_success_rate": res["avg_update_success_rate"],
                "avg_oos_ls_rtn": avg_ls,
                "final_val_icir": (res.get("final_eval_validation") or {}).get("icir"),
                "final_val_sharpe": (res.get("final_eval_validation") or {}).get("sharpe"),
                "final_test_icir": (res.get("final_eval_test") or {}).get("icir"),
                "final_test_sharpe": (res.get("final_eval_test") or {}).get("sharpe"),
            })

        csv_path = self._export_summary_csv(summary_rows)
        print(f"\n场景汇总CSV: {csv_path}")

        return scenario_results

    @staticmethod
    def _export_summary_csv(rows):
        out_dir = "outputs/performance_tracking"
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(out_dir, f"scenario_comparison_summary_{ts}.csv")
        if rows:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
        return path


def build_default_scenarios():
    """默认对比场景。"""
    return [
        build_scenario("baseline", good_to_good=0.80, stock_sigma=0.002, seed=42),
        build_scenario("low_persist_good", good_to_good=0.60, stock_sigma=0.002, seed=42),
        build_scenario("high_return_noise", good_to_good=0.80, stock_sigma=0.0035, seed=42),
    ]
