"""
因子库迭代引擎

封装单场景下的数据生成、因子选择更新、OOS评估、早停与最终出库流程。
"""

import csv
import json
import os
import time
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np

from core.bayesian_selector_v2 import BayesianSelectorV2
from evaluation.library_dynamics_plotter import export_test_dynamics_svg, export_validation_dynamics_svg
from evaluation.library_tracker import FactorLibraryTracker
from simulation.latent_factor_data_simulator import (
    LatentFactorDataSimulator,
    LatentFactorSimulationConfig,
)


class FactorLibraryIterationEngine:
    """单场景因子库迭代引擎。"""

    def __init__(self, config):
        self.config = config
        run_tag = f"{self.config.SCENARIO_NAME}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.tracker = FactorLibraryTracker(run_tag=run_tag)

    def run_full_test(self) -> Dict:
        """运行完整实验（单场景）。"""
        np.random.seed(self.config.RANDOM_SEED)

        print("=" * 80)
        print("贝叶斯因子选择器 - 性能测试")
        print("=" * 80)
        print(f"场景: {self.config.SCENARIO_NAME}")
        print("测试参数:")
        print(f"  股票数量: {self.config.NUM_STOCKS}")
        print(f"  时间跨度: {self.config.NUM_DAYS} 交易日")
        print(f"  因子数量: {self.config.NUM_FACTORS}")
        print(f"  每次选择: {self.config.TARGET_SIZE} 个因子")
        print(f"  更新频率: 每月 ({self.config.UPDATE_FREQUENCY} 交易日)")
        print(f"  滚动窗口: {self.config.ROLLING_WINDOW} 天")
        print(f"  年化天数: {getattr(self.config, 'ANNUAL_DAYS', 250)}")
        print(f"  收益率mu/sigma: {self.config.STOCK_RETURN_MU:.6f}/{self.config.STOCK_RETURN_SIGMA:.6f}")
        print(f"  转移概率 good->good: {self.config.TRANSITION_PROBS['good']['good']:.2f}")
        print(
            f"  数据切分 train/val/test: "
            f"{self.config.TRAIN_RATIO:.0%}/{self.config.VALIDATION_RATIO:.0%}/{self.config.TEST_RATIO:.0%}"
        )
        print(f"  评估模式: {self.config.EVAL_MODE}")
        print()

        print("1. 生成测试数据...")
        start_time = time.time()

        sim_config = LatentFactorSimulationConfig(
            num_stocks=self.config.NUM_STOCKS,
            num_days=self.config.NUM_DAYS,
            num_factors=self.config.NUM_FACTORS,
            rolling_window=self.config.ROLLING_WINDOW,
            stock_return_mu=self.config.STOCK_RETURN_MU,
            stock_return_sigma=self.config.STOCK_RETURN_SIGMA,
            good_ratio=self.config.GOOD_FACTOR_RATIO,
            medium_ratio=self.config.MEDIUM_FACTOR_RATIO,
            bad_ratio=self.config.BAD_FACTOR_RATIO,
            good_ic_mean=self.config.GOOD_IC_MEAN,
            good_ic_std=self.config.GOOD_IC_STD,
            medium_ic_mean=self.config.MEDIUM_IC_MEAN,
            medium_ic_std=self.config.MEDIUM_IC_STD,
            bad_ic_mean=self.config.BAD_IC_MEAN,
            bad_ic_std=self.config.BAD_IC_STD,
            latent_states=self.config.LATENT_STATES,
            init_state_probs=self.config.INIT_STATE_PROBS,
            transition_probs=self.config.TRANSITION_PROBS,
            anchor_reversion_prob=self.config.ANCHOR_REVERSION_PROB,
            random_seed=self.config.RANDOM_SEED,
        )
        self.simulator = LatentFactorDataSimulator(sim_config)

        print("   生成股票收益率与前瞻收益标签...")
        self.dates, self.stock_returns, self.forward_returns = self.simulator.build_market_data()

        n_periods = self.forward_returns.shape[1]
        print(f"   有效期数: {n_periods}")
        split_info = self._build_dataset_split(len(self.dates))
        print(
            f"   train区间: {split_info['train_start_date']} ~ {split_info['train_end_date']} | "
            f"validation区间: {split_info['val_start_date']} ~ {split_info['val_end_date']}"
        )
        if split_info["test_size"] > 0:
            print(f"   test区间: {split_info['test_start_date']} ~ {split_info['test_end_date']}")

        print("   生成因子...")
        self.factors = self.simulator.generate_factors_with_regime(
            self.dates,
            self.forward_returns,
            phase_boundaries=split_info,
            phase_transition_probs=getattr(self.config, "PHASE_TRANSITION_PROBS", None),
        )

        data_time = time.time() - start_time
        print(f"   数据生成完成, 耗时: {data_time:.2f}秒")
        print()

        print("2. 初始化贝叶斯选择器...")
        self.selector = BayesianSelectorV2(verbose=False)
        self.selector.add_factors(self.factors)
        print(f"   已添加 {len(self.factors)} 个因子")
        print()

        print("3. 运行多轮选择测试...")
        min_start_day = max(100, self.config.ROLLING_WINDOW + 20)
        eval_mode = getattr(self.config, "EVAL_MODE", "strict_holdout")
        if eval_mode == "strict_holdout":
            iter_end_idx = split_info["train_end_idx"]
        elif eval_mode == "walk_forward_test":
            iter_end_idx = split_info["test_end_idx"] if split_info["test_size"] > 0 else split_info["val_end_idx"]
        else:
            raise ValueError(f"未知EVAL_MODE: {eval_mode}")

        update_points = list(range(min_start_day, iter_end_idx + 1, self.config.UPDATE_FREQUENCY))
        if self.config.NUM_TEST_ROUNDS is not None:
            update_points = update_points[: self.config.NUM_TEST_ROUNDS]

        print(f"   将进行 {len(update_points)} 轮选择测试")
        print()

        all_selection_results = []
        all_update_results = []
        round_iteration_metrics = []
        prev_selected_ids = None
        prev_selection_result = None
        early_stop_triggered = False
        early_stop_round = None

        for i, update_day in enumerate(update_points):
            print(f"   第{i+1}轮选择 (日期: {self.dates[update_day]})...")
            round_start = time.time()

            # Step B: 在t_r先用(t_{r-1}, t_r]新增观测更新上一轮选中因子
            update_result = None
            performance_data = {}
            alpha_beta_before = {}
            update_success_by_group = {"good": 0, "medium": 0, "bad": 0}
            if prev_selection_result is not None:
                performance_data = self._evaluate_selected_factors(
                    prev_selection_result.selected_factors,
                    update_day,
                )
                alpha_beta_before = {
                    fid: {"alpha": factor.alpha, "beta": factor.beta}
                    for fid, factor in self.selector.factors.items()
                }
                update_result = self.selector.update_from_performance(
                    prev_selection_result.selected_factors,
                    performance_data,
                    self.dates[update_day],
                )
                for fid, succ in update_result.selected_updates.items():
                    if not succ:
                        continue
                    if fid.startswith("good_"):
                        update_success_by_group["good"] += 1
                    elif fid.startswith("medium_"):
                        update_success_by_group["medium"] += 1
                    elif fid.startswith("bad_"):
                        update_success_by_group["bad"] += 1

            # Step A: 在t_r基于更新后的后验再进行本轮选因子
            selection_result = self.selector.select_factors(
                self.dates[update_day], target_size=self.config.TARGET_SIZE
            )

            selected_counts = self._count_factor_groups(selection_result.selected_factors)
            if update_result is not None:
                round_summary = self.tracker.record_round(
                    round_index=i + 1,
                    current_date=self.dates[update_day],
                    selector=self.selector,
                    selection_result=selection_result,
                    update_result=update_result,
                    performance_data=performance_data,
                    alpha_beta_before=alpha_beta_before,
                    update_selected_ids=prev_selection_result.selected_factors,
                    lookback_days=20,
                )
                all_update_results.append(update_result)
            else:
                round_summary = None

            round_time = time.time() - round_start

            all_selection_results.append(selection_result)

            if eval_mode == "strict_holdout":
                oos_current = self._evaluate_oos_library_on_date_range(
                    selection_result.selected_factors,
                    start_date=split_info["val_start_date"],
                    end_date=split_info["val_end_date"],
                )
            else:
                oos_current = self._evaluate_oos_library_forward(
                    selection_result.selected_factors,
                    start_day=update_day + 1,
                    horizon=self.config.OOS_HORIZON,
                    end_cap_day=iter_end_idx,
                )
            if prev_selected_ids is not None:
                if eval_mode == "strict_holdout":
                    oos_prev = self._evaluate_oos_library_on_date_range(
                        prev_selected_ids,
                        start_date=split_info["val_start_date"],
                        end_date=split_info["val_end_date"],
                    )
                else:
                    oos_prev = self._evaluate_oos_library_forward(
                        prev_selected_ids,
                        start_day=update_day + 1,
                        horizon=self.config.OOS_HORIZON,
                        end_cap_day=iter_end_idx,
                    )
                oos_excess_vs_prevlib = oos_current["ls_mean"] - oos_prev["ls_mean"]
            else:
                oos_excess_vs_prevlib = 0.0

            overlap_prev = (
                self._jaccard_overlap(selection_result.selected_factors, prev_selected_ids or [])
                if prev_selected_ids is not None
                else 0.0
            )
            turnover = 1.0 - overlap_prev if prev_selected_ids is not None else 1.0

            round_metric = {
                "round": i + 1,
                "date": self.dates[update_day],
                "overlap_prev": overlap_prev,
                "turnover": turnover,
                "oos_ic_mean": oos_current["ic_mean"],
                "oos_icir": oos_current["icir"],
                "oos_ls_mean": oos_current["ls_mean"],
                "oos_sharpe": oos_current["sharpe"],
                "oos_win_rate": oos_current["win_rate"],
                "oos_excess_vs_prevlib": oos_excess_vs_prevlib,
                "oos_icir_raw": oos_current.get("icir_raw"),
                "oos_sharpe_raw": oos_current.get("sharpe_raw"),
                "oos_ls_mean_raw": oos_current.get("ls_mean_raw"),
                "test_oos_icir": None,
                "test_oos_sharpe": None,
                "test_oos_ls_mean": None,
                "test_oos_icir_raw": None,
                "test_oos_sharpe_raw": None,
                "test_oos_ls_mean_raw": None,
            }
            if split_info["test_size"] > 0:
                test_eval_current = self._evaluate_oos_library_on_date_range(
                    selection_result.selected_factors,
                    split_info["test_start_date"],
                    split_info["test_end_date"],
                )
                round_metric["test_oos_icir"] = test_eval_current["icir"]
                round_metric["test_oos_sharpe"] = test_eval_current["sharpe"]
                round_metric["test_oos_ls_mean"] = test_eval_current["ls_mean"]
                round_metric["test_oos_icir_raw"] = test_eval_current.get("icir_raw")
                round_metric["test_oos_sharpe_raw"] = test_eval_current.get("sharpe_raw")
                round_metric["test_oos_ls_mean_raw"] = test_eval_current.get("ls_mean_raw")
            if len(round_iteration_metrics) == 0:
                round_metric["d_oos_sharpe"] = None
                round_metric["d_oos_icir"] = None
                round_metric["stability_pass"] = False
            else:
                prev_metric = round_iteration_metrics[-1]
                d_sharpe = abs(round_metric["oos_sharpe_raw"] - prev_metric["oos_sharpe_raw"])
                d_icir = abs(round_metric["oos_icir_raw"] - prev_metric["oos_icir_raw"])
                round_metric["d_oos_sharpe"] = d_sharpe
                round_metric["d_oos_icir"] = d_icir
                round_metric["stability_pass"] = (
                    round_metric["turnover"] <= self.config.EARLY_STOP_EPS_TURNOVER
                    and d_sharpe <= self.config.EARLY_STOP_EPS_PERF
                    and d_icir <= self.config.EARLY_STOP_EPS_PERF
                    and round_metric["oos_excess_vs_prevlib"] >= -self.config.EARLY_STOP_DELTA
                )
            round_iteration_metrics.append(round_metric)

            print(f"     选中: {len(selection_result.selected_factors)} 个因子")
            print(
                f"     选中结构: good={selected_counts['good']}, "
                f"medium={selected_counts['medium']}, bad={selected_counts['bad']}"
            )
            if update_result is not None:
                print(
                    f"     上轮更新成功结构: good={update_success_by_group['good']}, "
                    f"medium={update_success_by_group['medium']}, bad={update_success_by_group['bad']}"
                )
            if eval_mode == "strict_holdout":
                print(
                    f"     OOS(固定验证集 {split_info['val_start_date']}~{split_info['val_end_date']}): "
                    f"ICIR={round_metric['oos_icir']:.3f}, "
                    f"LS均值={round_metric['oos_ls_mean']:.6f}, "
                    f"Sharpe={round_metric['oos_sharpe']:.3f}"
                )
            else:
                print(
                    f"     OOS(滚动未来{self.config.OOS_HORIZON}天, 截止{self.dates[iter_end_idx]}): "
                    f"ICIR={round_metric['oos_icir']:.3f}, "
                    f"LS均值={round_metric['oos_ls_mean']:.6f}, "
                    f"Sharpe={round_metric['oos_sharpe']:.3f}"
                )
            if prev_selected_ids is not None:
                print(
                    f"     稳定性: overlap={round_metric['overlap_prev']:.1%}, "
                    f"turnover={round_metric['turnover']:.1%}, "
                    f"OOS超额(vs上轮库)={round_metric['oos_excess_vs_prevlib']:.6f}"
                )
            print(f"     耗时: {round_time:.2f}秒")
            print()

            prev_selected_ids = list(selection_result.selected_factors)
            prev_selection_result = selection_result

            if eval_mode == "walk_forward_test" and self._check_early_stop(round_iteration_metrics):
                early_stop_triggered = True
                early_stop_round = i + 1
                print(
                    f"   早停触发: 第{early_stop_round}轮满足收敛条件，"
                    f"将该轮因子库固化为当前版本。"
                )
                print()
                break

        print("4. 分析测试结果...")

        results = self._analyze_results(all_selection_results, all_update_results)
        results["round_iteration_metrics"] = round_iteration_metrics
        results["early_stop"] = {"triggered": early_stop_triggered, "round": early_stop_round}
        results["dataset_split"] = split_info
        results["eval_mode"] = eval_mode

        final_idx, final_reason = self._resolve_final_library_index(
            all_selection_results=all_selection_results,
            round_metrics=round_iteration_metrics,
            eval_mode=eval_mode,
            early_stop_triggered=early_stop_triggered,
            early_stop_round=early_stop_round,
        )
        if all_selection_results:
            final_selection = all_selection_results[final_idx]
            final_library_ids = list(final_selection.selected_factors)
            final_library_date = final_selection.date
        else:
            final_library_ids = []
            final_library_date = None

        results["final_library"] = {
            "date": final_library_date,
            "size": len(final_library_ids),
            "factor_ids": final_library_ids,
            "selected_round": (final_idx + 1) if final_idx >= 0 else None,
            "selection_reason": final_reason,
        }

        tracking_files = self.tracker.export()
        results["tracking_output"] = tracking_files
        compact_csv = self._export_round_compact_csv(
            output_dir=tracking_files.get("output_dir"),
            round_metrics=round_iteration_metrics,
            selected_round=results["final_library"].get("selected_round"),
            last_round=len(all_selection_results) if all_selection_results else None,
        )
        results["round_compact_csv"] = compact_csv
        dynamics_svg = self._export_dynamics_plot(
            output_dir=tracking_files.get("output_dir"),
            round_metrics=round_iteration_metrics,
            selected_round=results["final_library"].get("selected_round"),
            last_round=len(all_selection_results) if all_selection_results else None,
            test_enabled=split_info["test_size"] > 0,
        )
        results["dynamics_plot_svg"] = dynamics_svg.get("validation")
        results["test_dynamics_plot_svg"] = dynamics_svg.get("test")
        results["final_library_file"] = self._save_final_library_artifact(
            tracking_files.get("output_dir"), results
        )
        results["scenario_name"] = self.config.SCENARIO_NAME
        results["scenario_params"] = {
            "random_seed": self.config.RANDOM_SEED,
            "stock_return_mu": self.config.STOCK_RETURN_MU,
            "stock_return_sigma": self.config.STOCK_RETURN_SIGMA,
            "transition_good_to_good": self.config.TRANSITION_PROBS["good"]["good"],
            "horizon_days": self.config.ROLLING_WINDOW,
            "annual_days": getattr(self.config, "ANNUAL_DAYS", 250),
            "train_ratio": self.config.TRAIN_RATIO,
            "validation_ratio": self.config.VALIDATION_RATIO,
            "test_ratio": self.config.TEST_RATIO,
            "eval_mode": eval_mode,
        }
        if split_info["val_size"] > 0:
            results["final_eval_validation"] = self._evaluate_oos_library_on_date_range(
                final_library_ids, split_info["val_start_date"], split_info["val_end_date"]
            )
        if split_info["test_size"] > 0:
            results["final_eval_test"] = self._evaluate_oos_library_on_date_range(
                final_library_ids, split_info["test_start_date"], split_info["test_end_date"]
            )
        if all_selection_results:
            last_selection = all_selection_results[-1]
            results["last_round_library"] = {
                "date": last_selection.date,
                "size": len(last_selection.selected_factors),
                "factor_ids": list(last_selection.selected_factors),
                "round": len(all_selection_results),
            }
            results["last_round_eval_validation"] = self._evaluate_oos_library_on_date_range(
                list(last_selection.selected_factors),
                split_info["val_start_date"],
                split_info["val_end_date"],
            )
            if split_info["test_size"] > 0:
                results["last_round_eval_test"] = self._evaluate_oos_library_on_date_range(
                    list(last_selection.selected_factors),
                    split_info["test_start_date"],
                    split_info["test_end_date"],
                )

        self._print_final_results(results)
        return results

    def _resolve_final_library_index(
        self,
        all_selection_results: List,
        round_metrics: List[Dict],
        eval_mode: str,
        early_stop_triggered: bool,
        early_stop_round: int,
    ) -> Tuple[int, str]:
        if not all_selection_results:
            return -1, "empty"

        if eval_mode == "walk_forward_test":
            if early_stop_triggered and early_stop_round is not None:
                return early_stop_round - 1, "walk_forward_early_stop"
            return len(all_selection_results) - 1, "walk_forward_last_round"

        # strict_holdout: 在稳定性通过轮次里选择验证集最优轮次
        stable_candidates = [
            m for m in round_metrics if bool(m.get("stability_pass", False))
        ]
        if stable_candidates:
            best = max(
                stable_candidates,
                key=lambda x: (float(x.get("oos_sharpe", 0.0)), float(x.get("oos_icir", 0.0))),
            )
            return int(best["round"]) - 1, "strict_holdout_best_stable_validation"

        # 回退：若无稳定性通过轮次，则取验证集最优轮次
        best_any = max(
            round_metrics,
            key=lambda x: (float(x.get("oos_sharpe", 0.0)), float(x.get("oos_icir", 0.0))),
        )
        return int(best_any["round"]) - 1, "strict_holdout_best_validation_fallback"

    @staticmethod
    def _count_factor_groups(factor_ids: List[str]) -> Dict[str, int]:
        counts = {"good": 0, "medium": 0, "bad": 0}
        for fid in factor_ids:
            if fid.startswith("good_"):
                counts["good"] += 1
            elif fid.startswith("medium_"):
                counts["medium"] += 1
            elif fid.startswith("bad_"):
                counts["bad"] += 1
        return counts

    def _evaluate_oos_library_on_date_range(
        self, selected_ids: List[str], start_date: str, end_date: str
    ) -> Dict[str, float]:
        if not selected_ids:
            return {
                "ic_mean": 0.0, "icir": 0.0, "ls_mean": 0.0, "sharpe": 0.0, "win_rate": 0.0,
                "icir_raw": 0.0, "ls_mean_raw": 0.0, "sharpe_raw": 0.0,
            }

        ic_values = []
        ls_values = []
        for fid in selected_ids:
            factor = self.selector.factors.get(fid)
            if factor is None:
                continue
            perf = factor.get_performance_in_range(start_date, end_date)
            for p in perf:
                if p.ic is not None:
                    ic_values.append(p.ic)
                if p.ls_return is not None:
                    ls_values.append(p.ls_return)

        if not ic_values or not ls_values:
            return {
                "ic_mean": 0.0, "icir": 0.0, "ls_mean": 0.0, "sharpe": 0.0, "win_rate": 0.0,
                "icir_raw": 0.0, "ls_mean_raw": 0.0, "sharpe_raw": 0.0,
            }

        ic_arr = np.array(ic_values, dtype=float)
        ls_arr = np.array(ls_values, dtype=float)
        ic_mean = float(np.mean(ic_arr))
        icir_raw = float(ic_mean / (np.std(ic_arr) + 1e-8))
        ls_mean_raw = float(np.mean(ls_arr))
        sharpe_raw = float(ls_mean_raw / (np.std(ls_arr) + 1e-8))
        annual_days = float(getattr(self.config, "ANNUAL_DAYS", 250))
        horizon_days = float(max(getattr(self.config, "ROLLING_WINDOW", 5), 1))
        periods_per_year = annual_days / horizon_days
        icir = float(icir_raw * np.sqrt(periods_per_year))
        ls_mean = float(ls_mean_raw * periods_per_year)
        sharpe = float(sharpe_raw * np.sqrt(periods_per_year))
        win_rate = float(np.sum(ls_arr > 0) / len(ls_arr))

        return {
            "ic_mean": ic_mean,
            "icir": icir,
            "ls_mean": ls_mean,
            "sharpe": sharpe,
            "win_rate": win_rate,
            "icir_raw": icir_raw,
            "ls_mean_raw": ls_mean_raw,
            "sharpe_raw": sharpe_raw,
        }

    def _evaluate_oos_library_forward(
        self, selected_ids: List[str], start_day: int, horizon: int, end_cap_day: int
    ) -> Dict[str, float]:
        if start_day >= len(self.dates) or not selected_ids:
            return {"ic_mean": 0.0, "icir": 0.0, "ls_mean": 0.0, "sharpe": 0.0, "win_rate": 0.0}
        end_day = min(len(self.dates) - 1, start_day + horizon - 1, end_cap_day)
        if end_day < start_day:
            return {"ic_mean": 0.0, "icir": 0.0, "ls_mean": 0.0, "sharpe": 0.0, "win_rate": 0.0}
        return self._evaluate_oos_library_on_date_range(
            selected_ids=selected_ids,
            start_date=self.dates[start_day],
            end_date=self.dates[end_day],
        )

    def _build_dataset_split(self, total_days: int) -> Dict[str, object]:
        train_ratio = float(getattr(self.config, "TRAIN_RATIO", 0.7))
        val_ratio = float(getattr(self.config, "VALIDATION_RATIO", 0.2))
        test_ratio = float(getattr(self.config, "TEST_RATIO", 0.1))
        if train_ratio <= 0 or val_ratio <= 0:
            raise ValueError("TRAIN_RATIO和VALIDATION_RATIO必须为正数")
        if train_ratio + val_ratio + test_ratio > 1.000001:
            raise ValueError("TRAIN/VALIDATION/TEST比例之和不能超过1")

        train_size = int(total_days * train_ratio)
        val_size = int(total_days * val_ratio)
        used = train_size + val_size
        test_size = int(total_days * test_ratio)
        # 优先保证train+val按比例；剩余全部给test
        if used + test_size < total_days:
            test_size = total_days - used
        if train_size < 1 or val_size < 1:
            raise ValueError("样本切分后train/validation至少各需要1天")

        train_end = train_size - 1
        val_start = train_end + 1
        val_end = val_start + val_size - 1
        if val_end >= total_days:
            val_end = total_days - 1
        test_start = val_end + 1
        test_end = total_days - 1 if test_start < total_days else None
        actual_test_size = 0 if test_end is None else (test_end - test_start + 1)

        return {
            "train_start_idx": 0,
            "train_end_idx": train_end,
            "val_start_idx": val_start,
            "val_end_idx": val_end,
            "test_start_idx": test_start if test_end is not None else None,
            "test_end_idx": test_end,
            "train_size": train_end + 1,
            "val_size": val_end - val_start + 1,
            "test_size": actual_test_size,
            "train_start_date": self.dates[0],
            "train_end_date": self.dates[train_end],
            "val_start_date": self.dates[val_start],
            "val_end_date": self.dates[val_end],
            "test_start_date": self.dates[test_start] if test_end is not None else None,
            "test_end_date": self.dates[test_end] if test_end is not None else None,
        }

    @staticmethod
    def _jaccard_overlap(current_ids: List[str], prev_ids: List[str]) -> float:
        s1, s2 = set(current_ids), set(prev_ids)
        union = s1 | s2
        if not union:
            return 0.0
        return len(s1 & s2) / len(union)

    def _check_early_stop(self, metrics: List[Dict]) -> bool:
        m = self.config.EARLY_STOP_WINDOW
        if len(metrics) < max(self.config.EARLY_STOP_MIN_ROUNDS, m):
            return False

        window = metrics[-m:]
        if not all(item["turnover"] <= self.config.EARLY_STOP_EPS_TURNOVER for item in window):
            return False
        if not all(item["oos_excess_vs_prevlib"] >= -self.config.EARLY_STOP_DELTA for item in window):
            return False

        for i in range(1, len(window)):
            d_sharpe = abs(window[i]["oos_sharpe"] - window[i - 1]["oos_sharpe"])
            d_icir = abs(window[i]["oos_icir"] - window[i - 1]["oos_icir"])
            if d_sharpe > self.config.EARLY_STOP_EPS_PERF or d_icir > self.config.EARLY_STOP_EPS_PERF:
                return False

        return True

    def _export_dynamics_plot(
        self,
        output_dir: str,
        round_metrics: List[Dict],
        selected_round: int,
        last_round: int,
        test_enabled: bool,
    ) -> Dict[str, str]:
        if not output_dir:
            output_dir = "outputs/performance_tracking"
        path = f"{output_dir}/validation_dynamics.svg"
        export_validation_dynamics_svg(
            output_path=path,
            round_metrics=round_metrics,
            selected_round=selected_round,
            last_round=last_round,
            title_suffix=f"[{getattr(self.config, 'EVAL_MODE', 'unknown')}]",
        )
        result = {"validation": path}
        if test_enabled:
            test_path = f"{output_dir}/test_dynamics.svg"
            export_test_dynamics_svg(
                output_path=test_path,
                round_metrics=round_metrics,
                selected_round=selected_round,
                last_round=last_round,
                title_suffix=f"[{getattr(self.config, 'EVAL_MODE', 'unknown')}]",
            )
            result["test"] = test_path
        return result

    def _save_final_library_artifact(self, output_dir: str, results: Dict) -> str:
        if not output_dir:
            output_dir = "outputs/performance_tracking"

        final_path = f"{output_dir}/final_library.json"
        payload = {
            "scenario": results.get("scenario_name", self.config.SCENARIO_NAME),
            "created_at": datetime.now().isoformat(),
            "early_stop": results.get("early_stop", {}),
            "dataset_split": results.get("dataset_split", {}),
            "eval_mode": results.get("eval_mode"),
            "final_library": results.get("final_library", {}),
            "final_eval_validation": results.get("final_eval_validation", {}),
            "final_eval_test": results.get("final_eval_test", {}),
            "last_round_library": results.get("last_round_library", {}),
            "last_round_eval_validation": results.get("last_round_eval_validation", {}),
            "last_round_eval_test": results.get("last_round_eval_test", {}),
            "oos_metrics_by_round": results.get("round_iteration_metrics", []),
            "dynamics_plot_svg": results.get("dynamics_plot_svg"),
            "test_dynamics_plot_svg": results.get("test_dynamics_plot_svg"),
            "round_compact_csv": results.get("round_compact_csv"),
        }
        with open(final_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return final_path

    def _evaluate_selected_factors(self, selected_ids: List[str], day: int) -> Dict:
        performance_data = {}
        icir_by_factor = {}
        ls_by_factor = {}

        for fid in selected_ids:
            factor = self.selector.factors.get(fid)
            if factor:
                recent_perf = factor.get_recent_performance(20, self.dates[day])
                if recent_perf:
                    ic_values = [p.ic for p in recent_perf]
                    ls_values = [p.ls_return for p in recent_perf]
                    icir_by_factor[fid] = np.mean(ic_values) / (np.std(ic_values) + 1e-8)
                    ls_by_factor[fid] = np.mean(ls_values)

        ranked = sorted(icir_by_factor.items(), key=lambda x: x[1], reverse=True)
        n = len(ranked)
        rank_percentile = {}
        for idx, (fid, _) in enumerate(ranked):
            rank_percentile[fid] = (idx / (n - 1)) if n > 1 else 0.5

        for fid in icir_by_factor:
            performance_data[fid] = {
                "icir": icir_by_factor[fid],
                "rank_percentile": rank_percentile[fid],
                "ls_return": ls_by_factor[fid],
            }

        return performance_data

    def _analyze_results(self, selection_results, update_results) -> Dict:
        good_selected_count = []
        medium_selected_count = []
        bad_selected_count = []
        good_recall = []
        n_good_total = int(self.config.NUM_FACTORS * self.config.GOOD_FACTOR_RATIO)

        for result in selection_results:
            good_count = sum(1 for fid in result.selected_factors if fid.startswith("good_"))
            medium_count = sum(1 for fid in result.selected_factors if fid.startswith("medium_"))
            bad_count = sum(1 for fid in result.selected_factors if fid.startswith("bad_"))
            good_selected_count.append(good_count / len(result.selected_factors) if result.selected_factors else 0)
            medium_selected_count.append(medium_count / len(result.selected_factors) if result.selected_factors else 0)
            bad_selected_count.append(bad_count / len(result.selected_factors) if result.selected_factors else 0)
            good_recall.append(good_count / max(n_good_total, 1))

        update_success = []
        for result in update_results:
            stats = result.update_stats
            total = stats.get("selected_success", 0) + stats.get("selected_failure", 0)
            if total > 0:
                update_success.append(stats.get("selected_success", 0) / total)
            else:
                update_success.append(0)

        alpha_changes = []
        beta_changes = []
        for factor in list(self.selector.factors.values())[:10]:
            alpha_changes.append(factor.alpha)
            beta_changes.append(factor.beta)

        return {
            "good_selection_rate": good_selected_count,
            "medium_selection_rate": medium_selected_count,
            "bad_selection_rate": bad_selected_count,
            "avg_good_selection_rate": np.mean(good_selected_count),
            "avg_medium_selection_rate": np.mean(medium_selected_count),
            "avg_bad_selection_rate": np.mean(bad_selected_count),
            "good_recall": good_recall,
            "avg_good_recall": np.mean(good_recall),
            "update_success_rate": update_success,
            "avg_update_success_rate": np.mean(update_success),
            "factor_alpha_mean": np.mean(alpha_changes),
            "factor_beta_mean": np.mean(beta_changes),
        }

    def _print_final_results(self, results: Dict):
        print()
        print("=" * 80)
        print("测试结果总结")
        print("=" * 80)

        print("\n1. 选择有效性:")
        print(f"   平均好因子选中率: {results['avg_good_selection_rate']:.1%}")
        print(f"   平均好因子召回率: {results['avg_good_recall']:.1%}")
        print(f"   平均中因子选中率: {results['avg_medium_selection_rate']:.1%}")
        print(f"   平均差因子选中率: {results['avg_bad_selection_rate']:.1%}")
        print("   每轮选中结构(good/medium/bad):")
        for i, (g, m, b) in enumerate(
            zip(results["good_selection_rate"], results["medium_selection_rate"], results["bad_selection_rate"]),
            start=1,
        ):
            print(f"     第{i}轮: {g:.1%} / {m:.1%} / {b:.1%}")

        print("\n2. 更新效果:")
        print(f"   平均更新成功率: {results['avg_update_success_rate']:.1%}")
        print("   每轮成功率: ", end="")
        print(", ".join([f"{r:.1%}" for r in results["update_success_rate"]]))

        round_metrics = results.get("round_iteration_metrics", [])
        split = results.get("dataset_split", {})
        if round_metrics:
            avg_oos_icir = np.mean([x["oos_icir"] for x in round_metrics])
            avg_oos_ls = np.mean([x["oos_ls_mean"] for x in round_metrics])
            avg_turnover = np.mean([x["turnover"] for x in round_metrics[1:]]) if len(round_metrics) > 1 else 1.0
            stable_count = sum(1 for x in round_metrics if bool(x.get("stability_pass", False)))
            print("\n3. OOS与稳定性:")
            if split:
                print(f"   验证集区间: {split.get('val_start_date')} ~ {split.get('val_end_date')}")
            print(f"   平均OOS ICIR: {avg_oos_icir:.3f}")
            print(f"   平均OOS LS均值: {avg_oos_ls:.6f}")
            print(f"   平均换手率: {avg_turnover:.1%}")
            print(f"   稳定性通过轮次: {stable_count}/{len(round_metrics)}")

        print("\n4. 因子参数:")
        print(f"   平均α: {results['factor_alpha_mean']:.2f}")
        print(f"   平均β: {results['factor_beta_mean']:.2f}")

        early_stop = results.get("early_stop", {})
        final_lib = results.get("final_library", {})
        print("\n5. 最终因子库:")
        print(
            f"   早停触发: {early_stop.get('triggered', False)}"
            + (f" (第{early_stop.get('round')}轮)" if early_stop.get("triggered") else "")
        )
        print(f"   因子库日期: {final_lib.get('date')}")
        print(f"   因子库规模: {final_lib.get('size', 0)}")
        if results.get("eval_mode"):
            print(f"   评估模式: {results.get('eval_mode')}")
        if final_lib.get("selected_round"):
            print(
                f"   选定轮次: 第{final_lib.get('selected_round')}轮 "
                f"({final_lib.get('selection_reason')})"
            )

        val_eval = results.get("final_eval_validation")
        if val_eval:
            print(
                f"   最终库Validation: ICIR={val_eval['icir']:.3f}, "
                f"LS均值={val_eval['ls_mean']:.6f}, Sharpe={val_eval['sharpe']:.3f}"
            )
        test_eval = results.get("final_eval_test")
        if test_eval:
            print(
                f"   最终库Test: ICIR={test_eval['icir']:.3f}, "
                f"LS均值={test_eval['ls_mean']:.6f}, Sharpe={test_eval['sharpe']:.3f}"
            )
        last_val_eval = results.get("last_round_eval_validation")
        if last_val_eval:
            print(
                f"   对照(最后一轮)Validation: ICIR={last_val_eval['icir']:.3f}, "
                f"LS均值={last_val_eval['ls_mean']:.6f}, Sharpe={last_val_eval['sharpe']:.3f}"
            )
        last_test_eval = results.get("last_round_eval_test")
        if last_test_eval:
            print(
                f"   对照(最后一轮)Test: ICIR={last_test_eval['icir']:.3f}, "
                f"LS均值={last_test_eval['ls_mean']:.6f}, Sharpe={last_test_eval['sharpe']:.3f}"
            )

        tracking = results.get("tracking_output", {})
        if tracking:
            print("\n6. 跟踪输出文件:")
            print(f"   输出目录: {tracking.get('output_dir')}")
            print(f"   轮次摘要: {tracking.get('round_summary_csv')}")
            print(f"   因子逐轮状态: {tracking.get('factor_round_status_csv')}")
            print(f"   因子库绩效指标: {tracking.get('library_metrics_json')}")
            if results.get("round_compact_csv"):
                print(f"   轮次紧凑汇总CSV: {results.get('round_compact_csv')}")
            if results.get("dynamics_plot_svg"):
                print(f"   验证动态曲线图: {results.get('dynamics_plot_svg')}")
            if results.get("test_dynamics_plot_svg"):
                print(f"   测试动态曲线图: {results.get('test_dynamics_plot_svg')}")
        if results.get("final_library_file"):
            print(f"   最终因子库文件: {results['final_library_file']}")

    def _export_round_compact_csv(
        self,
        output_dir: str,
        round_metrics: List[Dict],
        selected_round: int,
        last_round: int,
    ) -> str:
        if not output_dir:
            output_dir = "outputs/performance_tracking"
        os.makedirs(output_dir, exist_ok=True)
        path = os.path.join(output_dir, "round_compact_summary.csv")
        rows = []
        for m in round_metrics:
            r = int(m.get("round", 0))
            rows.append({
                "round": r,
                "date": m.get("date"),
                "stability_pass": bool(m.get("stability_pass", False)),
                "is_selected_round": (selected_round == r),
                "is_last_round": (last_round == r),
                "oos_icir": m.get("oos_icir"),
                "oos_sharpe": m.get("oos_sharpe"),
                "oos_ls_rtn": m.get("oos_ls_mean"),
                "turnover": m.get("turnover"),
                "oos_excess_vs_prevlib": m.get("oos_excess_vs_prevlib"),
                "d_oos_sharpe": m.get("d_oos_sharpe"),
                "d_oos_icir": m.get("d_oos_icir"),
                "test_oos_icir": m.get("test_oos_icir"),
                "test_oos_sharpe": m.get("test_oos_sharpe"),
                "test_oos_ls_rtn": m.get("test_oos_ls_mean"),
            })
        if rows:
            self._append_test_percentiles(rows)
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
        return path

    @staticmethod
    def _append_test_percentiles(rows: List[Dict]) -> None:
        def add_pct(field: str, out_field: str):
            vals = [(i, r.get(field)) for i, r in enumerate(rows) if r.get(field) is not None]
            if not vals:
                for r in rows:
                    r[out_field] = None
                return
            sorted_vals = sorted(vals, key=lambda x: x[1])
            n = len(sorted_vals)
            rank_map = {}
            for rank, (idx, _) in enumerate(sorted_vals):
                rank_map[idx] = (rank + 1) / n
            for i, r in enumerate(rows):
                r[out_field] = rank_map.get(i)

        add_pct("test_oos_icir", "test_oos_icir_pct")
        add_pct("test_oos_sharpe", "test_oos_sharpe_pct")
        add_pct("test_oos_ls_rtn", "test_oos_ls_rtn_pct")

        print()
        print("=" * 80)
        print("测试完成")
        print("=" * 80)
