"""
指定多个 asof_date 的滚动因子库生成器

用途:
- 对每个 asof_date 独立构建“回看窗口 -> train/val切分 -> 最终因子库”
- 汇总跨日期因子库重叠度与换手率
"""

import copy
import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from experiments.factor_library_scenario_experiment import PerformanceTestConfig
from workflows.real_data_iteration_engine import RealDataIterationEngine


@dataclass
class AsOfRollingConfig:
    scenario_name: str = "real_asof_rolling"
    asof_dates: Optional[List[str]] = None
    lookback_days: int = 1000
    target_size: int = 30
    update_frequency: int = 21
    horizon_days: int = 5
    split_gap_days: Optional[int] = None
    asof_filter: bool = True
    train_ratio: float = 0.7
    validation_ratio: float = 0.3
    test_ratio: float = 0.0
    eval_mode: str = "strict_holdout"
    num_test_rounds: Optional[int] = None
    factor_glob: str = "*.csv"
    # 数据路径
    daily_returns_file: str = ""
    factors_dir: str = ""
    pool_file: Optional[str] = None
    output_dir: Optional[str] = None


class AsOfLibraryGenerator:
    def __init__(self, cfg: AsOfRollingConfig):
        if not cfg.asof_dates:
            raise ValueError("asof_dates 不能为空")
        self.cfg = cfg

    @staticmethod
    def _jaccard(a: List[str], b: List[str]) -> float:
        sa, sb = set(a), set(b)
        if not sa and not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    @staticmethod
    def _overlap_min(a: List[str], b: List[str]) -> float:
        sa, sb = set(a), set(b)
        denom = min(len(sa), len(sb))
        if denom == 0:
            return 0.0
        return len(sa & sb) / denom

    def _build_engine_config(self, asof_date: str) -> PerformanceTestConfig:
        c = PerformanceTestConfig()
        c.SCENARIO_NAME = f"{self.cfg.scenario_name}_{asof_date}"
        c.TARGET_SIZE = self.cfg.target_size
        c.UPDATE_FREQUENCY = self.cfg.update_frequency
        c.ROLLING_WINDOW = self.cfg.horizon_days
        if self.cfg.split_gap_days is not None:
            c.SPLIT_GAP_DAYS = self.cfg.split_gap_days
        c.ENABLE_ASOF_FILTER = bool(self.cfg.asof_filter)
        c.TRAIN_RATIO = self.cfg.train_ratio
        c.VALIDATION_RATIO = self.cfg.validation_ratio
        c.TEST_RATIO = self.cfg.test_ratio
        c.EVAL_MODE = self.cfg.eval_mode
        c.NUM_TEST_ROUNDS = self.cfg.num_test_rounds
        c.EXPORT_SIM_DATA_AS_REAL_FORMAT = False
        c.REAL_DATA_MODE = True
        c.REAL_DATA_DAILY_RETURNS_FILE = self.cfg.daily_returns_file
        c.REAL_DATA_FACTORS_DIR = self.cfg.factors_dir
        c.REAL_DATA_POOL_FILE = self.cfg.pool_file
        c.REAL_DATA_FACTOR_GLOB = self.cfg.factor_glob
        c.REAL_DATA_ASOF_DATE = asof_date
        c.REAL_DATA_LOOKBACK_DAYS = self.cfg.lookback_days
        return c

    def run(self) -> Dict[str, object]:
        out_dir = self.cfg.output_dir or os.path.join(
            "outputs/performance_tracking",
            f"asof_rolling_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        )
        os.makedirs(out_dir, exist_ok=True)

        asof_runs = []
        for asof in self.cfg.asof_dates:
            print(f"\n{'=' * 80}\n[asof] {asof}\n{'=' * 80}")
            engine_cfg = self._build_engine_config(asof)
            engine = RealDataIterationEngine(engine_cfg)
            result = engine.run_full_test()
            final_lib = result.get("final_library", {}) or {}
            val_eval = result.get("final_eval_validation", {}) or {}
            dataset_split = result.get("dataset_split", {}) or {}
            data_window = result.get("data_window", {}) or {}
            asof_runs.append({
                "asof_date": asof,
                "effective_asof_date": data_window.get("effective_asof_date"),
                "window_start": data_window.get("window_start") or dataset_split.get("train_start_date"),
                "window_end": data_window.get("window_end") or dataset_split.get("test_end_date") or dataset_split.get("val_end_date"),
                "final_library_size": final_lib.get("size", 0),
                "selected_round": final_lib.get("selected_round"),
                "selection_reason": final_lib.get("selection_reason"),
                "val_icir": val_eval.get("icir"),
                "val_sharpe": val_eval.get("sharpe"),
                "val_ls_rtn": val_eval.get("ls_mean"),
                "tracking_output_dir": (result.get("tracking_output") or {}).get("output_dir"),
                "factor_ids": list(final_lib.get("factor_ids", [])),
            })

        summary_csv = os.path.join(out_dir, "asof_library_summary.csv")
        self._export_summary(summary_csv, asof_runs)

        overlap_csv = os.path.join(out_dir, "asof_library_overlap.csv")
        self._export_overlap(overlap_csv, asof_runs)

        seq_csv = os.path.join(out_dir, "asof_library_seq_turnover.csv")
        self._export_seq_turnover(seq_csv, asof_runs)

        json_path = os.path.join(out_dir, "asof_library_factors.json")
        payload = {
            "created_at": datetime.now().isoformat(),
            "config": {
                "lookback_days": self.cfg.lookback_days,
                "train_ratio": self.cfg.train_ratio,
                "validation_ratio": self.cfg.validation_ratio,
                "test_ratio": self.cfg.test_ratio,
                "target_size": self.cfg.target_size,
                "horizon_days": self.cfg.horizon_days,
                "split_gap_days": self.cfg.split_gap_days,
                "asof_filter": self.cfg.asof_filter,
            },
            "runs": [
                {
                    "asof_date": r["asof_date"],
                    "effective_asof_date": r["effective_asof_date"],
                    "factor_ids": r["factor_ids"],
                    "val_icir": r["val_icir"],
                    "val_sharpe": r["val_sharpe"],
                    "val_ls_rtn": r["val_ls_rtn"],
                }
                for r in asof_runs
            ],
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

        print("\n滚动出库完成:")
        print(f"  summary: {summary_csv}")
        print(f"  overlap: {overlap_csv}")
        print(f"  seq_turnover: {seq_csv}")
        print(f"  factors_json: {json_path}")

        return {
            "output_dir": out_dir,
            "summary_csv": summary_csv,
            "overlap_csv": overlap_csv,
            "seq_turnover_csv": seq_csv,
            "factors_json": json_path,
        }

    @staticmethod
    def _export_summary(path: str, runs: List[Dict[str, object]]) -> None:
        rows = []
        for r in runs:
            row = copy.deepcopy(r)
            row.pop("factor_ids", None)
            rows.append(row)
        if not rows:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def _export_overlap(self, path: str, runs: List[Dict[str, object]]) -> None:
        rows = []
        for i in range(len(runs)):
            for j in range(i + 1, len(runs)):
                a = runs[i]
                b = runs[j]
                jacc = self._jaccard(a["factor_ids"], b["factor_ids"])
                ov = self._overlap_min(a["factor_ids"], b["factor_ids"])
                rows.append({
                    "asof_date_a": a["asof_date"],
                    "asof_date_b": b["asof_date"],
                    "jaccard": jacc,
                    "overlap_min": ov,
                    "turnover_by_jaccard": 1.0 - jacc,
                })
        if not rows:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def _export_seq_turnover(self, path: str, runs: List[Dict[str, object]]) -> None:
        ordered = sorted(runs, key=lambda x: x["asof_date"])
        rows = []
        for i in range(1, len(ordered)):
            prev = ordered[i - 1]
            cur = ordered[i]
            jacc = self._jaccard(prev["factor_ids"], cur["factor_ids"])
            rows.append({
                "prev_asof_date": prev["asof_date"],
                "curr_asof_date": cur["asof_date"],
                "jaccard": jacc,
                "turnover": 1.0 - jacc,
            })
        if not rows:
            return
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
