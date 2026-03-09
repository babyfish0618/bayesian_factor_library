"""
真实数据单场景迭代引擎

复用 FactorLibraryIterationEngine 的主流程，只重写数据准备步骤。
"""

import os
import time
from typing import Dict, Tuple

import numpy as np

from core.factor_enhanced import EnhancedFactor
from data.real_data_loader import RealDataLoader
from simulation.latent_factor_data_simulator import LatentFactorDataSimulator
from workflows.factor_library_iteration_engine import FactorLibraryIterationEngine


class RealDataIterationEngine(FactorLibraryIterationEngine):
    """基于本地真实格式CSV文件运行单场景因子库迭代。"""

    @staticmethod
    def _resolve_asof_index(dates, asof_date: str) -> int:
        # 若 asof_date 非交易日，取不晚于它的最近交易日
        idx = -1
        for i, d in enumerate(dates):
            if d <= asof_date:
                idx = i
            else:
                break
        if idx < 0:
            raise ValueError(f"asof_date={asof_date} 早于数据起始日期 {dates[0]}")
        return idx

    def _slice_panel_for_asof(self, panel: Dict[str, object]) -> Dict[str, object]:
        asof_date = getattr(self.config, "REAL_DATA_ASOF_DATE", None)
        lookback_days = getattr(self.config, "REAL_DATA_LOOKBACK_DAYS", None)
        if asof_date is None and lookback_days is None:
            return panel

        dates = panel["dates"]
        returns = panel["returns"]
        in_pool = panel["in_pool"]
        factor_scores = panel["factor_scores"]
        asof_idx = self._resolve_asof_index(dates, asof_date) if asof_date is not None else (len(dates) - 1)

        if lookback_days is None:
            start_idx = 0
        else:
            lookback_days = int(lookback_days)
            if lookback_days < 1:
                raise ValueError("REAL_DATA_LOOKBACK_DAYS 必须>=1")
            start_idx = max(0, asof_idx - lookback_days + 1)

        dates_new = dates[start_idx:asof_idx + 1]
        returns_new = returns[:, start_idx:asof_idx + 1]
        in_pool_new = in_pool[:, start_idx:asof_idx + 1]
        factor_scores_new = {
            fid: arr[:, start_idx:asof_idx + 1]
            for fid, arr in factor_scores.items()
        }
        if len(dates_new) <= int(getattr(self.config, "ROLLING_WINDOW", 5)) + 2:
            raise ValueError("asof窗口过短，无法构造有效前瞻标签")

        self._effective_asof_date = dates_new[-1]
        self._asof_window_start = dates_new[0]
        self._asof_window_end = dates_new[-1]
        if bool(getattr(self.config, "ENABLE_ASOF_FILTER", False)):
            self.config.ASOF_FILTER_REF_DATE = self._effective_asof_date
        return {
            "dates": dates_new,
            "stock_codes": panel["stock_codes"],
            "returns": returns_new,
            "in_pool": in_pool_new,
            "factor_scores": factor_scores_new,
        }

    def _prepare_data(self) -> Tuple[Dict[str, object], Dict[str, str], float]:
        start_time = time.time()

        daily_returns_file = getattr(self.config, "REAL_DATA_DAILY_RETURNS_FILE", "")
        factors_dir = getattr(self.config, "REAL_DATA_FACTORS_DIR", "")
        pool_file = getattr(self.config, "REAL_DATA_POOL_FILE", None)
        factor_glob = getattr(self.config, "REAL_DATA_FACTOR_GLOB", "*.csv")
        if not daily_returns_file or not factors_dir:
            raise ValueError("REAL_DATA_DAILY_RETURNS_FILE 和 REAL_DATA_FACTORS_DIR 不能为空")
        if not os.path.exists(daily_returns_file):
            raise FileNotFoundError(f"daily returns file not found: {daily_returns_file}")
        if not os.path.isdir(factors_dir):
            raise FileNotFoundError(f"factors dir not found: {factors_dir}")

        print("   读取真实数据文件...")
        loader = RealDataLoader(
            daily_returns_file=daily_returns_file,
            factors_dir=factors_dir,
            pool_file=pool_file,
            factor_glob=factor_glob,
        )
        panel = self._slice_panel_for_asof(loader.load())
        self.dates = panel["dates"]
        self.stock_returns = panel["returns"]
        self._in_pool = panel["in_pool"]
        factor_scores = panel["factor_scores"]

        self.config.NUM_DAYS = len(self.dates)
        self.config.NUM_STOCKS = self.stock_returns.shape[0]
        self.config.NUM_FACTORS = len(factor_scores)
        self.config.TARGET_SIZE = min(self.config.TARGET_SIZE, self.config.NUM_FACTORS)

        self.forward_returns = LatentFactorDataSimulator.calculate_forward_returns_ex_t(
            self.stock_returns, self.config.ROLLING_WINDOW
        )
        n_periods = self.forward_returns.shape[1]
        print(f"   有效期数: {n_periods}")
        if getattr(self, "_effective_asof_date", None) is not None:
            print(
                f"   asof窗口: {self._asof_window_start} ~ {self._asof_window_end} "
                f"(effective_asof={self._effective_asof_date})"
            )
        split_info = self._build_dataset_split(len(self.dates))
        print(
            f"   train区间: {split_info['train_start_date']} ~ {split_info['train_end_date']} | "
            f"validation区间: {split_info['val_start_date']} ~ {split_info['val_end_date']}"
        )
        if split_info.get("gap_days", 0) > 0:
            print(f"   split gap: {split_info['gap_days']} 天")
        if split_info["test_size"] > 0:
            print(f"   test区间: {split_info['test_start_date']} ~ {split_info['test_end_date']}")

        print("   构建因子历史表现...")
        self.factors = self._build_factors_from_real_panel(factor_scores)
        data_time = time.time() - start_time
        return split_info, {}, data_time

    @staticmethod
    def _topic_from_factor_id(factor_id: str) -> str:
        lower = factor_id.lower()
        if lower.startswith("good_"):
            return "good"
        if lower.startswith("bad_"):
            return "bad"
        if lower.startswith("medium_"):
            return "medium"
        return "real"

    def _build_factors_from_real_panel(self, factor_scores: Dict[str, np.ndarray]):
        factors = []
        n_periods = self.forward_returns.shape[1]
        pool_for_signal = self._in_pool[:, :n_periods]
        forward_for_signal = np.array(self.forward_returns, copy=True)
        forward_for_signal[~pool_for_signal] = np.nan

        for factor_id, score_arr in factor_scores.items():
            factor = EnhancedFactor(
                factor_id=factor_id,
                expression=f"REAL_FACTOR_{factor_id}",
                topic=self._topic_from_factor_id(factor_id),
            )
            factor.alpha, factor.beta = 1.0, 1.0

            values = np.array(score_arr[:, :n_periods], copy=True)
            values[~pool_for_signal] = np.nan
            ic_series = LatentFactorDataSimulator.calculate_factor_ic(values, forward_for_signal)
            ls_returns = LatentFactorDataSimulator.calculate_factor_ls_return(values, forward_for_signal)

            for t in range(n_periods):
                if np.isnan(ic_series[t]) or np.isnan(ls_returns[t]):
                    continue
                realized_idx = t + self.config.ROLLING_WINDOW
                if realized_idx >= len(self.dates):
                    continue
                factor.add_daily_performance(
                    date=self.dates[realized_idx],
                    ic=float(ic_series[t]),
                    ls_return=float(ls_returns[t]),
                    rank_percentile=0.5,
                )
            factors.append(factor)
        return factors
