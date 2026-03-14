"""
因子库跟踪模块
用于记录每轮因子选择/更新明细，并导出可分析文件。
"""

import csv
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np


class FactorLibraryTracker:
    """跟踪因子库整体与单因子逐轮状态。"""

    def __init__(self, output_root: str = "outputs/performance_tracking", run_tag: Optional[str] = None):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_tag = run_tag or timestamp
        self.output_dir = os.path.join(output_root, self.run_tag)
        os.makedirs(self.output_dir, exist_ok=True)

        self.round_summaries: List[Dict] = []
        self.factor_round_records: List[Dict] = []
        self.library_metrics: List[Dict] = []

    @staticmethod
    def _factor_group(factor_id: str) -> str:
        if factor_id.startswith("good_"):
            return "good"
        if factor_id.startswith("medium_"):
            return "medium"
        if factor_id.startswith("bad_"):
            return "bad"
        return "unknown"

    @staticmethod
    def _safe_mean(values: List[float]) -> float:
        if not values:
            return 0.0
        arr = np.array(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        return float(np.mean(arr)) if arr.size > 0 else 0.0

    @staticmethod
    def _safe_std(values: List[float]) -> float:
        if not values:
            return 0.0
        arr = np.array(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        return float(np.std(arr)) if arr.size > 0 else 0.0

    def record_round(
        self,
        round_index: int,
        current_date: str,
        selector,
        selection_result,
        update_result,
        performance_data: Dict[str, Dict],
        alpha_beta_before: Dict[str, Dict[str, float]],
        update_selected_ids: Optional[List[str]] = None,
        lookback_days: int = 20
    ) -> Dict:
        """记录一轮结果并返回轮次摘要。"""
        selected_set = set(selection_result.selected_factors)
        update_selected_set = set(update_selected_ids) if update_selected_ids is not None else selected_set
        selected_updates = update_result.selected_updates
        marginal_details = update_result.marginal_details if hasattr(update_result, "marginal_details") else {}

        selected_counts = {"good": 0, "medium": 0, "bad": 0, "unknown": 0}
        selected_success_counts = {"good": 0, "medium": 0, "bad": 0, "unknown": 0}
        selected_failure_counts = {"good": 0, "medium": 0, "bad": 0, "unknown": 0}

        all_recent_icir = []
        all_recent_ls_mean = []
        selected_recent_icir = []
        selected_recent_ls_mean = []

        for fid, factor in selector.factors.items():
            group = self._factor_group(fid)
            is_selected = fid in selected_set
            is_updated = fid in update_selected_set
            candidate_score = selection_result.candidate_scores.get(fid, {})

            recent_perf = factor.get_recent_performance(lookback_days, current_date)
            recent_icir = factor.calculate_icir(recent_perf) if recent_perf else 0.0
            ls_stats = factor.calculate_ls_return_stats(recent_perf) if recent_perf else {
                "mean": 0.0, "sharpe": 0.0, "win_rate": 0.0
            }
            recent_ls_mean = float(ls_stats.get("mean", 0.0))
            recent_ls_sharpe = float(ls_stats.get("sharpe", 0.0))
            recent_win_rate = float(ls_stats.get("win_rate", 0.0))

            all_recent_icir.append(recent_icir)
            all_recent_ls_mean.append(recent_ls_mean)

            selected_success = None
            unselected_eval = None
            unselected_score = None
            unselected_improvement = None

            if is_selected:
                selected_counts[group] += 1
                selected_recent_icir.append(recent_icir)
                selected_recent_ls_mean.append(recent_ls_mean)

            if is_updated:
                selected_success = selected_updates.get(fid)
                if selected_success is not None and bool(selected_success):
                    selected_success_counts[group] += 1
                elif selected_success is not None and not bool(selected_success):
                    selected_failure_counts[group] += 1
            elif not is_selected:
                detail = marginal_details.get(fid, {})
                if detail:
                    unselected_eval = detail.get("evaluation")
                    unselected_score = detail.get("score")
                    unselected_improvement = detail.get("improvement")

            before = alpha_beta_before.get(fid, {})
            perf_input = performance_data.get(fid, {})

            self.factor_round_records.append({
                "round": round_index,
                "date": current_date,
                "factor_id": fid,
                "group": group,
                "selected": is_selected,
                "updated_in_b_step": is_updated,
                "selected_success": selected_success,
                "unselected_evaluation": unselected_eval,
                "unselected_score": unselected_score,
                "unselected_improvement": unselected_improvement,
                "alpha_before": float(before.get("alpha", factor.alpha)),
                "beta_before": float(before.get("beta", factor.beta)),
                "alpha_after": float(factor.alpha),
                "beta_after": float(factor.beta),
                "success_rate_after": float(factor.get_success_rate()),
                "score_final": float(candidate_score.get("final_score", 0.0)),
                "score_aggregate": float(candidate_score.get("aggregate_score", 0.0)),
                "score_bayesian": float(candidate_score.get("bayesian_score", 0.0)),
                "perf_rank_percentile_input": perf_input.get("rank_percentile"),
                "perf_icir_input": perf_input.get("icir"),
                "perf_ls_return_input": perf_input.get("ls_return"),
                "recent_icir_lookback": recent_icir,
                "recent_ls_mean_lookback": recent_ls_mean,
                "recent_ls_sharpe_lookback": recent_ls_sharpe,
                "recent_win_rate_lookback": recent_win_rate
            })

        round_summary = {
            "round": round_index,
            "date": current_date,
            "selected_total": len(selected_set),
            "updated_selected_total": len(update_selected_set),
            "selected_good": selected_counts["good"],
            "selected_medium": selected_counts["medium"],
            "selected_bad": selected_counts["bad"],
            "selected_success_good": selected_success_counts["good"],
            "selected_success_medium": selected_success_counts["medium"],
            "selected_success_bad": selected_success_counts["bad"],
            "selected_failure_good": selected_failure_counts["good"],
            "selected_failure_medium": selected_failure_counts["medium"],
            "selected_failure_bad": selected_failure_counts["bad"],
            "selected_success_total": int(update_result.update_stats.get("selected_success", 0)),
            "selected_failure_total": int(update_result.update_stats.get("selected_failure", 0)),
            "unselected_success_total": int(update_result.update_stats.get("unselected_success", 0)),
            "unselected_failure_total": int(update_result.update_stats.get("unselected_failure", 0)),
            "marginal_evaluations_total": int(update_result.update_stats.get("marginal_evaluations", 0))
        }

        selected_sf_total = round_summary["selected_success_total"] + round_summary["selected_failure_total"]
        unselected_sf_total = round_summary["unselected_success_total"] + round_summary["unselected_failure_total"]
        candidate_sf_total = selected_sf_total + unselected_sf_total

        round_summary["selected_success_ratio"] = (
            round_summary["selected_success_total"] / selected_sf_total if selected_sf_total > 0 else 0.0
        )
        round_summary["selected_failure_ratio"] = (
            round_summary["selected_failure_total"] / selected_sf_total if selected_sf_total > 0 else 0.0
        )
        round_summary["unselected_success_ratio"] = (
            round_summary["unselected_success_total"] / unselected_sf_total if unselected_sf_total > 0 else 0.0
        )
        round_summary["unselected_failure_ratio"] = (
            round_summary["unselected_failure_total"] / unselected_sf_total if unselected_sf_total > 0 else 0.0
        )
        round_summary["candidate_success_ratio"] = (
            (round_summary["selected_success_total"] + round_summary["unselected_success_total"]) / candidate_sf_total
            if candidate_sf_total > 0 else 0.0
        )
        round_summary["candidate_failure_ratio"] = (
            (round_summary["selected_failure_total"] + round_summary["unselected_failure_total"]) / candidate_sf_total
            if candidate_sf_total > 0 else 0.0
        )

        self.round_summaries.append(round_summary)

        metrics = {
            "round": round_index,
            "date": current_date,
            "all_factors": {
                "count": len(all_recent_icir),
                "icir_mean": self._safe_mean(all_recent_icir),
                "icir_std": self._safe_std(all_recent_icir),
                "ls_mean": self._safe_mean(all_recent_ls_mean),
                "ls_std": self._safe_std(all_recent_ls_mean)
            },
            "selected_factors": {
                "count": len(selected_recent_icir),
                "icir_mean": self._safe_mean(selected_recent_icir),
                "icir_std": self._safe_std(selected_recent_icir),
                "ls_mean": self._safe_mean(selected_recent_ls_mean),
                "ls_std": self._safe_std(selected_recent_ls_mean)
            }
        }
        self.library_metrics.append(metrics)
        return round_summary

    def export(self):
        """导出跟踪文件。"""
        round_csv = os.path.join(self.output_dir, "round_summary.csv")
        factor_csv = os.path.join(self.output_dir, "factor_round_status.csv")
        metrics_json = os.path.join(self.output_dir, "library_metrics.json")

        if self.round_summaries:
            with open(round_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(self.round_summaries[0].keys()))
                writer.writeheader()
                writer.writerows(self.round_summaries)

        if self.factor_round_records:
            with open(factor_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(self.factor_round_records[0].keys()))
                writer.writeheader()
                writer.writerows(self.factor_round_records)

        with open(metrics_json, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "run_tag": self.run_tag,
                    "round_metrics": self.library_metrics
                },
                f,
                indent=2,
                ensure_ascii=False
            )

        return {
            "output_dir": self.output_dir,
            "round_summary_csv": round_csv,
            "factor_round_status_csv": factor_csv,
            "library_metrics_json": metrics_json
        }
