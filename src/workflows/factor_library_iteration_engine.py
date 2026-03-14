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
import yaml

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

    def _prepare_data(self) -> Tuple[Dict[str, object], Dict[str, str], float]:
        """准备样本数据与因子对象（默认：模拟数据）。"""
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
            start_date=getattr(self.config, "START_DATE", "2014-01-01"),
            end_date=getattr(self.config, "END_DATE", None),
            show_progress=bool(getattr(self.config, "SHOW_PROGRESS", False)),
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
        if split_info.get("gap_days", 0) > 0:
            print(f"   split gap: {split_info['gap_days']} 天")
        if split_info["test_size"] > 0:
            print(f"   test区间: {split_info['test_start_date']} ~ {split_info['test_end_date']}")

        print("   生成因子...")
        self.factors = self.simulator.generate_factors_with_regime(
            self.dates,
            self.forward_returns,
            phase_boundaries=split_info,
            phase_transition_probs=getattr(self.config, "PHASE_TRANSITION_PROBS", None),
        )
        sim_export_files = {}
        if bool(getattr(self.config, "EXPORT_SIM_DATA_AS_REAL_FORMAT", False)):
            export_root = os.path.join(
                getattr(self.config, "EXPORT_SIM_OUTPUT_ROOT", "data/simulated"),
                self.config.SCENARIO_NAME,
            )
            sim_export_files = self.simulator.export_as_real_data_format(
                output_root=export_root,
                pool_name=getattr(self.config, "EXPORT_SIM_POOL_NAME", "all_stocks"),
                include_forward_returns=bool(
                    getattr(self.config, "EXPORT_SIM_INCLUDE_FORWARD_LABELS", True)
                ),
            )
            print(f"   已导出模拟数据到真实格式目录: {sim_export_files.get('output_root')}")

        data_time = time.time() - start_time
        return split_info, sim_export_files, data_time

    @staticmethod
    def _resolve_global_annualization_days(default: float = 250.0) -> float:
        """读取统一年化天数配置（evaluation_config.yaml）。"""
        cfg_path = os.path.join("config", "evaluation_config.yaml")
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            return float(cfg.get("annualization_days", default))
        except Exception:
            return float(default)

    def _resolve_min_start_day(self) -> int:
        """由配置窗口推导最早可开始轮次，避免硬编码。"""
        # 选择打分依赖 selection 多窗口
        selection_windows = list(self.selector.config.time_windows.get("selection", {}).values())
        selection_max = max([int(w) for w in selection_windows], default=60)

        # 选中更新依赖 selected_short 评估窗口
        eval_windows = self.selector.config.time_windows.get("evaluation", {})
        selected_short = int(eval_windows.get("selected_short", 10))

        # 信号 x(t) 对应标签在 t+ROLLING_WINDOW 可得
        # 因子 performance_history 日期是 realized_idx=t+ROLLING_WINDOW
        # 为获得足够回看样本，至少应覆盖 rolling_window + required_window
        required_window = max(selection_max, selected_short)
        return int(self.config.ROLLING_WINDOW + required_window)

    def run_full_test(self) -> Dict:
        """运行完整实验（单场景）。"""
        np.random.seed(self.config.RANDOM_SEED)

        print("=" * 80)
        print("贝叶斯因子选择器 - 性能测试")
        print("=" * 80)
        print(f"场景: {self.config.SCENARIO_NAME}")
        real_data_mode = bool(getattr(self.config, "REAL_DATA_MODE", False))
        print("测试参数:")
        if real_data_mode:
            print("  股票数量: (from files)")
            print("  时间跨度: (from files)")
            print("  因子数量: (from files)")
        else:
            print(f"  股票数量: {self.config.NUM_STOCKS}")
            print(f"  时间跨度: {self.config.NUM_DAYS} 交易日")
            print(f"  因子数量: {self.config.NUM_FACTORS}")
        print(f"  每次选择: {self.config.TARGET_SIZE} 个因子")
        print(f"  更新频率: 每月 ({self.config.UPDATE_FREQUENCY} 交易日)")
        print(f"  滚动窗口: {self.config.ROLLING_WINDOW} 天")
        print(f"  年化天数: {self._resolve_global_annualization_days():.0f} (from evaluation_config.yaml)")
        if real_data_mode:
            print("  数据来源: real_data_files")
            print(f"  daily_returns: {getattr(self.config, 'REAL_DATA_DAILY_RETURNS_FILE', '')}")
            print(f"  factors_dir: {getattr(self.config, 'REAL_DATA_FACTORS_DIR', '')}")
            if getattr(self.config, "REAL_DATA_POOL_FILE", None):
                print(f"  pool_file: {getattr(self.config, 'REAL_DATA_POOL_FILE')}")
        elif hasattr(self.config, "STOCK_RETURN_MU") and hasattr(self.config, "STOCK_RETURN_SIGMA"):
            print(f"  收益率mu/sigma: {self.config.STOCK_RETURN_MU:.6f}/{self.config.STOCK_RETURN_SIGMA:.6f}")
        if (not real_data_mode) and hasattr(self.config, "TRANSITION_PROBS"):
            print(f"  转移概率 good->good: {self.config.TRANSITION_PROBS['good']['good']:.2f}")
        print(
            f"  数据切分 train/val/test: "
            f"{self.config.TRAIN_RATIO:.0%}/{self.config.VALIDATION_RATIO:.0%}/{self.config.TEST_RATIO:.0%}"
        )
        asof_on = bool(getattr(self.config, "ENABLE_ASOF_FILTER", False))
        print(f"  as-of过滤: {asof_on}")
        print(f"  评估模式: {self.config.EVAL_MODE}")
        print()

        print("1. 生成测试数据...")
        split_info, sim_export_files, data_time = self._prepare_data()
        print(f"   数据生成完成, 耗时: {data_time:.2f}秒")
        print()

        print("2. 初始化贝叶斯选择器...")
        self.selector = BayesianSelectorV2(verbose=False)
        self.selector.add_factors(self.factors)
        print(f"   已添加 {len(self.factors)} 个因子")
        print(f"   年化天数(统一配置): {self.selector.annualization_days:.0f}")
        print()

        print("3. 运行多轮选择测试...")
        min_start_day = self._resolve_min_start_day()
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
        if eval_mode == "strict_holdout":
            self._assert_strict_holdout_no_leakage(
                split_info=split_info,
                update_points=update_points,
                iter_end_idx=iter_end_idx,
            )

        print(f"   将进行 {len(update_points)} 轮选择测试")
        print(f"   最早起始轮次索引(min_start_day): {min_start_day}")
        print()

        all_selection_results = []
        all_update_results = []
        round_iteration_metrics = []
        prev_selected_ids = None
        prev_selection_result = None
        early_stop_triggered = False
        early_stop_round = None
        use_asof_filter = bool(getattr(self.config, "ENABLE_ASOF_FILTER", False))
        asof_filter_ref = getattr(self.config, "ASOF_FILTER_REF_DATE", None)
        if use_asof_filter and asof_filter_ref is None:
            asof_filter_ref = self.dates[-1]
        library_selection_cfg = self._get_library_selection_cfg()
        anchor_cfg = library_selection_cfg.get("anchor", {})
        anchor_enabled = bool(anchor_cfg.get("enabled", True))
        anchor_method = str(anchor_cfg.get("method", "round_1"))
        anchor_library_ids = None
        anchor_eval_cached = None

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
                    lookback_days=int(self.selector.config.time_windows.get("evaluation", {}).get("selected_long", 20)),
                )
                all_update_results.append(update_result)
            else:
                round_summary = None

            round_time = time.time() - round_start

            all_selection_results.append(selection_result)
            if use_asof_filter:
                asof_date = asof_filter_ref if asof_filter_ref is not None else self.dates[-1]
            else:
                asof_date = None

            if eval_mode == "strict_holdout":
                oos_current = self._evaluate_oos_library_on_date_range(
                    selection_result.selected_factors,
                    start_date=split_info["val_start_date"],
                    end_date=split_info["val_end_date"],
                    asof_date=asof_date,
                )
            else:
                oos_current = self._evaluate_oos_library_forward(
                    selection_result.selected_factors,
                    start_day=update_day + 1,
                    horizon=self.config.OOS_HORIZON,
                    end_cap_day=iter_end_idx,
                    asof_date=asof_date,
                )
            if prev_selected_ids is not None:
                if eval_mode == "strict_holdout":
                    oos_prev = self._evaluate_oos_library_on_date_range(
                        prev_selected_ids,
                        start_date=split_info["val_start_date"],
                        end_date=split_info["val_end_date"],
                        asof_date=asof_date,
                    )
                else:
                    oos_prev = self._evaluate_oos_library_forward(
                        prev_selected_ids,
                        start_day=update_day + 1,
                        horizon=self.config.OOS_HORIZON,
                        end_cap_day=iter_end_idx,
                        asof_date=asof_date,
                    )
                oos_excess_vs_prevlib = oos_current["ls_mean"] - oos_prev["ls_mean"]
            else:
                oos_excess_vs_prevlib = 0.0

            if anchor_enabled and anchor_method == "round_1" and anchor_library_ids is None:
                anchor_library_ids = list(selection_result.selected_factors)

            oos_anchor = None
            if anchor_enabled and anchor_library_ids:
                if eval_mode == "strict_holdout":
                    if anchor_eval_cached is None:
                        anchor_eval_cached = self._evaluate_oos_library_on_date_range(
                            anchor_library_ids,
                            start_date=split_info["val_start_date"],
                            end_date=split_info["val_end_date"],
                            asof_date=asof_date,
                        )
                    oos_anchor = anchor_eval_cached
                else:
                    oos_anchor = self._evaluate_oos_library_forward(
                        anchor_library_ids,
                        start_day=update_day + 1,
                        horizon=self.config.OOS_HORIZON,
                        end_cap_day=iter_end_idx,
                        asof_date=asof_date,
                    )

            overlap_prev = (
                self._jaccard_overlap(selection_result.selected_factors, prev_selected_ids or [])
                if prev_selected_ids is not None
                else 0.0
            )
            turnover = 1.0 - overlap_prev if prev_selected_ids is not None else 1.0

            round_metric = {
                "round": i + 1,
                "date": self.dates[update_day],
                "asof_date": asof_date,
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
                "oos_excess_vs_anchor": (
                    (oos_current["ls_mean"] - oos_anchor["ls_mean"]) if oos_anchor is not None else None
                ),
                "anchor_metric_oos_sharpe": (oos_anchor.get("sharpe") if oos_anchor is not None else None),
                "anchor_metric_oos_icir": (oos_anchor.get("icir") if oos_anchor is not None else None),
                "anchor_metric_oos_ls_mean": (oos_anchor.get("ls_mean") if oos_anchor is not None else None),
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
                    asof_date=asof_date,
                )
                round_metric["test_oos_icir"] = test_eval_current["icir"]
                round_metric["test_oos_sharpe"] = test_eval_current["sharpe"]
                round_metric["test_oos_ls_mean"] = test_eval_current["ls_mean"]
                round_metric["test_oos_icir_raw"] = test_eval_current.get("icir_raw")
                round_metric["test_oos_sharpe_raw"] = test_eval_current.get("sharpe_raw")
                round_metric["test_oos_ls_mean_raw"] = test_eval_current.get("ls_mean_raw")
            prev_metric = round_iteration_metrics[-1] if round_iteration_metrics else None
            if prev_metric is None:
                round_metric["d_oos_sharpe"] = None
                round_metric["d_oos_icir"] = None
            else:
                round_metric["d_oos_sharpe"] = abs(
                    float(round_metric["oos_sharpe_raw"]) - float(prev_metric["oos_sharpe_raw"])
                )
                round_metric["d_oos_icir"] = abs(
                    float(round_metric["oos_icir_raw"]) - float(prev_metric["oos_icir_raw"])
                )

            primary_metric_name = str(
                library_selection_cfg.get("objective", {}).get("primary_metric", "oos_sharpe")
            )
            secondary_metric_name = str(
                library_selection_cfg.get("objective", {}).get("secondary_metric", "oos_icir")
            )
            primary_value = float(round_metric.get(self._metric_to_round_key(primary_metric_name), 0.0))
            secondary_value = float(round_metric.get(self._metric_to_round_key(secondary_metric_name), 0.0))
            if prev_metric is None:
                prev_primary_value = primary_value
            else:
                prev_primary_value = float(prev_metric.get(self._metric_to_round_key(primary_metric_name), 0.0))

            if oos_anchor is None:
                anchor_primary_value = primary_value
                anchor_secondary_value = secondary_value
            else:
                anchor_primary_value = self._metric_value_from_eval(oos_anchor, primary_metric_name)
                anchor_secondary_value = self._metric_value_from_eval(oos_anchor, secondary_metric_name)

            round_metric["improve_primary_vs_prev"] = primary_value - prev_primary_value
            round_metric["improve_primary_vs_anchor"] = primary_value - anchor_primary_value
            round_metric["improve_secondary_vs_anchor"] = secondary_value - anchor_secondary_value
            round_metric["stability_pass"] = self._evaluate_stability_gate(
                round_metric=round_metric,
                gate_cfg=library_selection_cfg.get("stability_gate", {}),
                prev_metric=prev_metric,
            )
            round_metric["selection_candidate"] = self._is_selection_candidate(
                round_metric=round_metric,
                selection_cfg=library_selection_cfg,
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
            if asof_date is not None:
                print(f"     as-of可得日期: {asof_date}")
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
        if sim_export_files:
            results["sim_data_export"] = sim_export_files
        if hasattr(self, "_asof_window_start") and hasattr(self, "_asof_window_end"):
            results["data_window"] = {
                "window_start": getattr(self, "_asof_window_start", None),
                "window_end": getattr(self, "_asof_window_end", None),
                "effective_asof_date": getattr(self, "_effective_asof_date", None),
            }

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
        results["scenario_name"] = self.config.SCENARIO_NAME
        results["scenario_params"] = {
            "random_seed": self.config.RANDOM_SEED,
            "stock_return_mu": self.config.STOCK_RETURN_MU,
            "stock_return_sigma": self.config.STOCK_RETURN_SIGMA,
            "transition_good_to_good": self.config.TRANSITION_PROBS["good"]["good"],
            "horizon_days": self.config.ROLLING_WINDOW,
            "annualization_days": self.selector.annualization_days,
            "train_ratio": self.config.TRAIN_RATIO,
            "validation_ratio": self.config.VALIDATION_RATIO,
            "test_ratio": self.config.TEST_RATIO,
            "split_gap_days": split_info.get("gap_days"),
            "enable_asof_filter": bool(getattr(self.config, "ENABLE_ASOF_FILTER", False)),
            "eval_mode": eval_mode,
        }
        if split_info["val_size"] > 0:
            results["final_eval_validation"] = self._evaluate_oos_library_on_date_range(
                final_library_ids,
                split_info["val_start_date"],
                split_info["val_end_date"],
                asof_date=self.dates[-1] if use_asof_filter else None,
            )
        if split_info["test_size"] > 0:
            results["final_eval_test"] = self._evaluate_oos_library_on_date_range(
                final_library_ids,
                split_info["test_start_date"],
                split_info["test_end_date"],
                asof_date=self.dates[-1] if use_asof_filter else None,
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
                asof_date=self.dates[-1] if use_asof_filter else None,
            )
            if split_info["test_size"] > 0:
                results["last_round_eval_test"] = self._evaluate_oos_library_on_date_range(
                    list(last_selection.selected_factors),
                    split_info["test_start_date"],
                    split_info["test_end_date"],
                    asof_date=self.dates[-1] if use_asof_filter else None,
                )

        # 在所有评估字段写入完成后再落盘，避免 final_library.json 缺少最终评估结果。
        results["final_library_file"] = self._save_final_library_artifact(
            tracking_files.get("output_dir"), results
        )

        self._print_final_results(results)
        return results

    def _assert_strict_holdout_no_leakage(
        self,
        split_info: Dict[str, object],
        update_points: List[int],
        iter_end_idx: int,
    ) -> None:
        """strict_holdout 模式下的防泄露边界检查。

        核心约束:
        - 更新轮次只能落在 train 区间内；
        - validation/test 区间必须严格晚于 train（中间允许 gap）。
        """
        train_end = int(split_info["train_end_idx"])
        val_start = int(split_info["val_start_idx"])
        val_end = int(split_info["val_end_idx"])

        if iter_end_idx != train_end:
            raise ValueError(
                f"strict_holdout 边界异常: iter_end_idx={iter_end_idx} 与 train_end_idx={train_end} 不一致"
            )
        if update_points and max(update_points) > train_end:
            raise ValueError(
                f"strict_holdout 泄露风险: update_points 最大值 {max(update_points)} 超过 train_end_idx {train_end}"
            )
        if val_start <= train_end:
            raise ValueError(
                f"strict_holdout 切分异常: val_start_idx={val_start} 必须大于 train_end_idx={train_end}"
            )

        test_start = split_info.get("test_start_idx")
        if test_start is not None and int(test_start) <= val_end:
            raise ValueError(
                f"strict_holdout 切分异常: test_start_idx={test_start} 必须大于 val_end_idx={val_end}"
            )

        print(
            "   防泄露检查(strict_holdout): "
            f"update_end={self.dates[train_end]} | "
            f"val={split_info['val_start_date']}~{split_info['val_end_date']} | "
            f"test={split_info.get('test_start_date')}~{split_info.get('test_end_date')}"
        )

    def _get_library_selection_cfg(self) -> Dict[str, object]:
        """获取 strict_holdout 的因子库出库配置。"""
        cfg = getattr(self.selector.config, "library_selection", None)
        return cfg if isinstance(cfg, dict) else {}

    @staticmethod
    def _metric_to_round_key(metric_name: str) -> str:
        name = str(metric_name or "").strip().lower()
        if name.startswith("oos_"):
            return name
        if name in {"sharpe", "icir", "ls_mean"}:
            return f"oos_{name}"
        if name in {"ls_return", "ls_rtn", "rtn"}:
            return "oos_ls_mean"
        return "oos_sharpe"

    def _metric_value_from_eval(self, eval_dict: Dict[str, float], metric_name: str) -> float:
        key = self._metric_to_round_key(metric_name)
        eval_key = key.replace("oos_", "")
        return float(eval_dict.get(eval_key, 0.0))

    def _evaluate_stability_gate(
        self,
        round_metric: Dict[str, object],
        gate_cfg: Dict[str, object],
        prev_metric: Dict[str, object],
    ) -> bool:
        """按配置判定轮次是否通过稳定性门控。"""
        if not bool(gate_cfg.get("enabled", True)):
            return True
        if prev_metric is None:
            return False

        turnover_max = float(gate_cfg.get("turnover_max", self.config.EARLY_STOP_EPS_TURNOVER))
        delta_sharpe_max = float(gate_cfg.get("delta_sharpe_raw_max", self.config.EARLY_STOP_EPS_PERF))
        delta_icir_max = float(gate_cfg.get("delta_icir_raw_max", self.config.EARLY_STOP_EPS_PERF))
        excess_vs_prev_min = float(gate_cfg.get("excess_vs_prev_min", -self.config.EARLY_STOP_DELTA))

        conditions = [
            float(round_metric.get("turnover", 1.0)) <= turnover_max,
            float(round_metric.get("d_oos_sharpe", 1e9)) <= delta_sharpe_max,
            float(round_metric.get("d_oos_icir", 1e9)) <= delta_icir_max,
            float(round_metric.get("oos_excess_vs_prevlib", -1e9)) >= excess_vs_prev_min,
        ]

        mode = str(gate_cfg.get("mode", "all")).lower()
        if mode == "k_of_n":
            kn_cfg = gate_cfg.get("k_of_n", {}) if isinstance(gate_cfg.get("k_of_n", {}), dict) else {}
            k = int(kn_cfg.get("k", 3))
            n = int(kn_cfg.get("n", len(conditions)))
            n = max(1, min(n, len(conditions)))
            return sum(1 for x in conditions[:n] if x) >= max(1, k)
        return all(conditions)

    def _is_selection_candidate(
        self,
        round_metric: Dict[str, object],
        selection_cfg: Dict[str, object],
    ) -> bool:
        """判定该轮是否满足 strict_holdout 的双基准出库候选条件。"""
        thresholds = selection_cfg.get("thresholds", {}) if isinstance(selection_cfg.get("thresholds", {}), dict) else {}
        gate_cfg = selection_cfg.get("stability_gate", {}) if isinstance(selection_cfg.get("stability_gate", {}), dict) else {}
        need_gate = bool(gate_cfg.get("enabled", True))

        cond_prev = float(round_metric.get("improve_primary_vs_prev", 0.0)) >= float(
            thresholds.get("min_improve_vs_prev", 0.0)
        )
        cond_anchor = float(round_metric.get("improve_primary_vs_anchor", 0.0)) >= float(
            thresholds.get("min_improve_vs_anchor", 0.0)
        )
        cond_anchor_secondary = float(round_metric.get("improve_secondary_vs_anchor", 0.0)) >= float(
            thresholds.get("min_improve_vs_anchor_secondary", 0.0)
        )
        cond_gate = bool(round_metric.get("stability_pass", False)) if need_gate else True
        return cond_prev and cond_anchor and cond_anchor_secondary and cond_gate

    def _resolve_final_library_index(
        self,
        all_selection_results: List,
        round_metrics: List[Dict],
        eval_mode: str,
        early_stop_triggered: bool,
        early_stop_round: int,
    ) -> Tuple[int, str]:
        """确定最终出库轮次及其原因标签。

        规则:
        - walk_forward_test: 早停触发则取触发轮，否则取最后一轮。
        - strict_holdout: 优先在 `stability_pass=True` 的轮次中选验证最优；
          若无稳定轮次，再在全体轮次中选验证最优（回退）。
        """
        if not all_selection_results:
            return -1, "empty"

        if eval_mode == "walk_forward_test":
            if early_stop_triggered and early_stop_round is not None:
                return early_stop_round - 1, "walk_forward_early_stop"
            return len(all_selection_results) - 1, "walk_forward_last_round"

        # strict_holdout: 先在 selection_candidate=True 的轮次中选验证最优
        strict_candidates = [
            m for m in round_metrics if bool(m.get("selection_candidate", False))
        ]
        if strict_candidates:
            best = max(
                strict_candidates,
                key=lambda x: (float(x.get("oos_sharpe", 0.0)), float(x.get("oos_icir", 0.0))),
            )
            return int(best["round"]) - 1, "strict_holdout_best_candidate_validation"

        fallback_mode = str(
            self._get_library_selection_cfg().get("fallback", {}).get("when_no_candidate", "best_validation")
        )
        if fallback_mode == "last_round":
            return len(all_selection_results) - 1, "strict_holdout_fallback_last_round"

        # 回退：若无候选轮次，则取验证集最优轮次
        best_any = max(
            round_metrics,
            key=lambda x: (float(x.get("oos_sharpe", 0.0)), float(x.get("oos_icir", 0.0))),
        )
        return int(best_any["round"]) - 1, "strict_holdout_fallback_best_validation"

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
        self, selected_ids: List[str], start_date: str, end_date: str, asof_date: str = None
    ) -> Dict[str, float]:
        """在固定日期区间评估候选库 OOS 表现。

        注意:
        - 支持 `asof_date` 过滤，只使用在该时点已“可得”的标签样本。
        - 返回同时包含 raw 指标与年化指标，稳定性判定优先使用 raw 口径。
        """
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
                if asof_date is not None and p.date > asof_date:
                    continue
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
        annual_days = float(getattr(self.selector, "annualization_days", 250.0))
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
        self, selected_ids: List[str], start_day: int, horizon: int, end_cap_day: int, asof_date: str = None
    ) -> Dict[str, float]:
        """在滚动前瞻窗口上评估 OOS（walk-forward 使用）。"""
        if start_day >= len(self.dates) or not selected_ids:
            return {"ic_mean": 0.0, "icir": 0.0, "ls_mean": 0.0, "sharpe": 0.0, "win_rate": 0.0}
        end_day = min(len(self.dates) - 1, start_day + horizon - 1, end_cap_day)
        if end_day < start_day:
            return {"ic_mean": 0.0, "icir": 0.0, "ls_mean": 0.0, "sharpe": 0.0, "win_rate": 0.0}
        return self._evaluate_oos_library_on_date_range(
            selected_ids=selected_ids,
            start_date=self.dates[start_day],
            end_date=self.dates[end_day],
            asof_date=asof_date,
        )

    def _build_dataset_split(self, total_days: int) -> Dict[str, object]:
        """按 train/validation/test 比例构建时间切分并加入 split gap。

        边界规则:
        - 先扣除 train-val、val-test 间隔天数（gap），再按比例切分有效样本。
        - `test_ratio <= 0` 时自动并入 validation。
        - 若切分后 train/validation 不足 1 天，直接报错。
        """
        train_ratio = float(getattr(self.config, "TRAIN_RATIO", 0.7))
        val_ratio = float(getattr(self.config, "VALIDATION_RATIO", 0.2))
        test_ratio = float(getattr(self.config, "TEST_RATIO", 0.1))
        if train_ratio <= 0 or val_ratio <= 0:
            raise ValueError("TRAIN_RATIO和VALIDATION_RATIO必须为正数")
        if train_ratio + val_ratio + test_ratio > 1.000001:
            raise ValueError("TRAIN/VALIDATION/TEST比例之和不能超过1")

        gap_days = int(
            getattr(self.config, "SPLIT_GAP_DAYS", self.config.ROLLING_WINDOW)
            if getattr(self.config, "SPLIT_GAP_DAYS", None) is not None
            else self.config.ROLLING_WINDOW
        )
        gap_days = max(gap_days, 0)

        gap_1 = gap_days if val_ratio > 0 else 0
        gap_2 = gap_days if test_ratio > 0 else 0
        effective_days = total_days - gap_1 - gap_2
        if effective_days < 3:
            raise ValueError("样本不足：扣除split gap后可用天数过少")

        train_size = int(effective_days * train_ratio)
        val_size = int(effective_days * val_ratio)
        if test_ratio <= 0:
            test_size = 0
            remainder = effective_days - train_size - val_size
            if remainder > 0:
                val_size += remainder
        else:
            used = train_size + val_size
            test_size = int(effective_days * test_ratio)
            if used + test_size < effective_days:
                test_size = effective_days - used
        if train_size < 1 or val_size < 1:
            raise ValueError("样本切分后train/validation至少各需要1天")

        train_end = train_size - 1
        val_start = train_end + 1 + gap_days
        val_end = val_start + val_size - 1
        if val_end >= total_days:
            raise ValueError("样本不足：请减小TRAIN/VAL比例或减小SPLIT_GAP_DAYS")
        if test_size <= 0:
            test_start = None
            test_end = None
            actual_test_size = 0
        else:
            test_start = val_end + 1 + gap_days
            if test_start >= total_days:
                test_start = None
                test_end = None
                actual_test_size = 0
            else:
                test_end = min(total_days - 1, test_start + test_size - 1)
                actual_test_size = test_end - test_start + 1

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
            "gap_days": gap_days,
            "train_start_date": self.dates[0],
            "train_end_date": self.dates[train_end],
            "val_start_date": self.dates[val_start],
            "val_end_date": self.dates[val_end],
            "test_start_date": self.dates[test_start] if test_start is not None and test_end is not None else None,
            "test_end_date": self.dates[test_end] if test_start is not None and test_end is not None else None,
        }

    @staticmethod
    def _jaccard_overlap(current_ids: List[str], prev_ids: List[str]) -> float:
        s1, s2 = set(current_ids), set(prev_ids)
        union = s1 | s2
        if not union:
            return 0.0
        return len(s1 & s2) / len(union)

    def _check_early_stop(self, metrics: List[Dict]) -> bool:
        """判断是否满足连续窗口早停条件（仅 walk-forward 模式使用）。"""
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
        """将最终出库结果与各轮指标固化为 `final_library.json`。"""
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
        """为上一轮已选因子构造本轮更新输入 `performance_data`。

        该函数输出是 `update_from_performance` 的输入，不直接参与当轮排序。
        """
        performance_data = {}
        icir_by_factor = {}
        ls_by_factor = {}
        lookback = int(self.selector.config.time_windows.get("evaluation", {}).get("selected_long", 20))

        for fid in selected_ids:
            factor = self.selector.factors.get(fid)
            if factor:
                recent_perf = factor.get_recent_performance(lookback, self.dates[day])
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
            "avg_update_success_rate": float(np.mean(update_success)) if update_success else 0.0,
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
            candidate_count = sum(1 for x in round_metrics if bool(x.get("selection_candidate", False)))
            print("\n3. OOS与稳定性:")
            if split:
                print(f"   验证集区间: {split.get('val_start_date')} ~ {split.get('val_end_date')}")
            print(f"   平均OOS ICIR: {avg_oos_icir:.3f}")
            print(f"   平均OOS LS均值: {avg_oos_ls:.6f}")
            print(f"   平均换手率: {avg_turnover:.1%}")
            print(f"   稳定性通过轮次: {stable_count}/{len(round_metrics)}")
            print(f"   出库候选轮次: {candidate_count}/{len(round_metrics)}")

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
                "asof_date": m.get("asof_date"),
                "stability_pass": bool(m.get("stability_pass", False)),
                "selection_candidate": bool(m.get("selection_candidate", False)),
                "is_selected_round": (selected_round == r),
                "is_last_round": (last_round == r),
                "oos_icir": m.get("oos_icir"),
                "oos_sharpe": m.get("oos_sharpe"),
                "oos_ls_rtn": m.get("oos_ls_mean"),
                "turnover": m.get("turnover"),
                "oos_excess_vs_prevlib": m.get("oos_excess_vs_prevlib"),
                "oos_excess_vs_anchor": m.get("oos_excess_vs_anchor"),
                "d_oos_sharpe": m.get("d_oos_sharpe"),
                "d_oos_icir": m.get("d_oos_icir"),
                "improve_primary_vs_prev": m.get("improve_primary_vs_prev"),
                "improve_primary_vs_anchor": m.get("improve_primary_vs_anchor"),
                "improve_secondary_vs_anchor": m.get("improve_secondary_vs_anchor"),
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
