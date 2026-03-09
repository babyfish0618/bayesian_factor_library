"""
潜在状态因子数据模拟器

将测试用的数据生成逻辑从 tests 中抽离，便于未来替换为真实数据源。
"""

import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, Tuple, Union

import numpy as np

from core.factor_enhanced import EnhancedFactor


@dataclass
class LatentFactorSimulationConfig:
    """模拟配置（测试入口可映射到该配置）。"""

    num_stocks: int
    num_days: int
    num_factors: int
    rolling_window: int
    stock_return_mu: float
    stock_return_sigma: float
    good_ratio: float
    medium_ratio: float
    bad_ratio: float
    good_ic_mean: float
    good_ic_std: float
    medium_ic_mean: float
    medium_ic_std: float
    bad_ic_mean: float
    bad_ic_std: float
    latent_states: Tuple[str, str, str]
    init_state_probs: Dict[str, Dict[str, float]]
    transition_probs: Dict[str, Dict[str, float]]
    anchor_reversion_prob: Dict[str, float]
    random_seed: int = 42
    start_date: str = "2014-01-01"
    end_date: Optional[str] = None
    show_progress: bool = False


class LatentFactorDataSimulator:
    """长期锚定 + 短期潜在状态切换的数据模拟器。"""

    def __init__(self, config: LatentFactorSimulationConfig):
        self.config = config
        np.random.seed(config.random_seed)
        self._warned_no_tqdm = False
        self._factor_values_map: Dict[str, np.ndarray] = {}
        self._latest_dates: Optional[List[str]] = None
        self._latest_stock_returns: Optional[np.ndarray] = None
        self._latest_forward_returns: Optional[np.ndarray] = None

    def _iter_progress(
        self,
        iterable: Iterable,
        desc: str,
        total: Optional[int] = None,
    ) -> Iterable:
        if not bool(getattr(self.config, "show_progress", False)):
            return iterable
        try:
            from tqdm.auto import tqdm
            return tqdm(iterable, desc=desc, total=total, leave=False)
        except Exception:
            if not self._warned_no_tqdm:
                print("[progress] 未检测到 tqdm，使用文本进度输出（可安装 tqdm 获得更好显示）。")
                self._warned_no_tqdm = True

            if total is None:
                try:
                    total = len(iterable)  # type: ignore[arg-type]
                except Exception:
                    total = None

            def _fallback_generator():
                if total is None:
                    for idx, item in enumerate(iterable, start=1):
                        if idx == 1 or idx % 1000 == 0:
                            print(f"[progress] {desc}: {idx} items")
                        yield item
                    print(f"[progress] {desc}: done")
                    return

                step = max(total // 10, 1)
                next_mark = step
                seen = 0
                for item in iterable:
                    seen += 1
                    if seen == 1 or seen >= next_mark or seen == total:
                        pct = 100.0 * seen / max(total, 1)
                        print(f"[progress] {desc}: {seen}/{total} ({pct:.1f}%)")
                        while next_mark <= seen:
                            next_mark += step
                    yield item
                if seen < total:
                    print(f"[progress] {desc}: {seen}/{total}")
                print(f"[progress] {desc}: done")

            return _fallback_generator()

    def generate_dates(
        self,
        num_days: int = None,
        start_date: str = None,
        end_date: str = None,
    ) -> List[str]:
        """生成交易日历（跳过周末）。

        规则:
        - 若给定 end_date（或配置中存在 end_date），按 [start_date, end_date] 闭区间生成。
        - 否则按 num_days 生成。
        """
        n = num_days if num_days is not None else self.config.num_days
        s = start_date if start_date is not None else self.config.start_date
        e = end_date if end_date is not None else self.config.end_date
        dates = []
        current = datetime.strptime(s, "%Y-%m-%d")
        if e is not None:
            end_dt = datetime.strptime(e, "%Y-%m-%d")
            if end_dt < current:
                raise ValueError("end_date 不能早于 start_date")
            while current <= end_dt:
                if current.weekday() < 5:
                    dates.append(current.strftime("%Y-%m-%d"))
                current += timedelta(days=1)
            return dates

        while len(dates) < n:
            if current.weekday() < 5:
                dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)
        return dates

    def generate_stock_returns(self, n_stocks: int = None, n_days: int = None) -> np.ndarray:
        """生成股票收益率。"""
        ns = n_stocks if n_stocks is not None else self.config.num_stocks
        nd = n_days if n_days is not None else self.config.num_days
        return np.random.normal(
            self.config.stock_return_mu,
            self.config.stock_return_sigma,
            (ns, nd)
        )

    @staticmethod
    def calculate_forward_returns_ex_t(returns: np.ndarray, window: int) -> np.ndarray:
        """计算前瞻收益率 R(t+1->t+window)，不包含t当日收益。"""
        n_stocks, n_days = returns.shape
        n_signals = n_days - window
        if n_signals <= 0:
            return np.zeros((n_stocks, 0))

        cumulative_returns = np.cumprod(1 + returns, axis=1)
        forward_returns = np.zeros((n_stocks, n_signals))
        for t in range(n_signals):
            start_idx = t + 1
            end_idx = t + window
            base = cumulative_returns[:, start_idx - 1]
            tail = cumulative_returns[:, end_idx]
            forward_returns[:, t] = (tail / (base + 1e-10)) - 1
        return forward_returns

    @staticmethod
    def generate_factor_values(
        stock_returns: np.ndarray,
        target_ic: Union[float, np.ndarray],
        ic_std: Union[float, np.ndarray]
    ) -> np.ndarray:
        """生成与未来收益相关的因子值。"""
        n_stocks, n_periods = stock_returns.shape
        R = stock_returns - np.mean(stock_returns, axis=0, keepdims=True)
        R = R / (np.std(R, axis=0, keepdims=True) + 1e-10)

        Z = np.random.randn(n_stocks, n_periods)
        for t in range(n_periods):
            projection = np.dot(Z[:, t], R[:, t]) / (np.dot(R[:, t], R[:, t]) + 1e-10)
            Z[:, t] = Z[:, t] - projection * R[:, t]
            Z[:, t] = Z[:, t] / (np.std(Z[:, t]) + 1e-10)

        if np.isscalar(target_ic):
            target_ic_series = np.full(n_periods, float(target_ic))
        else:
            target_ic_series = np.asarray(target_ic, dtype=float)
            if target_ic_series.shape[0] != n_periods:
                raise ValueError("target_ic数组长度必须等于n_periods")

        if np.isscalar(ic_std):
            ic_std_series = np.full(n_periods, float(ic_std))
        else:
            ic_std_series = np.asarray(ic_std, dtype=float)
            if ic_std_series.shape[0] != n_periods:
                raise ValueError("ic_std数组长度必须等于n_periods")

        rho_series = np.random.normal(target_ic_series, ic_std_series)
        rho_series = np.clip(rho_series, -0.99, 0.99)

        factor_values = np.zeros((n_stocks, n_periods))
        for t in range(n_periods):
            rho_t = rho_series[t]
            factor_values[:, t] = rho_t * R[:, t] + np.sqrt(1 - rho_t**2) * Z[:, t]
        return factor_values

    @staticmethod
    def calculate_factor_ic(factor_values: np.ndarray, future_returns: np.ndarray) -> np.ndarray:
        """计算因子IC序列。"""
        n_periods = factor_values.shape[1]
        ic_series = np.zeros(n_periods)
        for t in range(n_periods):
            valid = ~(np.isnan(factor_values[:, t]) | np.isnan(future_returns[:, t]))
            if np.sum(valid) > 10:
                ic_series[t] = np.corrcoef(
                    factor_values[valid, t], future_returns[valid, t]
                )[0, 1]
            else:
                ic_series[t] = np.nan
        return ic_series

    @staticmethod
    def calculate_factor_ls_return(factor_values: np.ndarray, future_returns: np.ndarray) -> np.ndarray:
        """计算因子加权多空收益序列（多头权重和=1，空头权重和=1）。"""
        n_stocks, n_periods = factor_values.shape
        ls_returns = np.zeros(n_periods)
        for t in range(n_periods):
            valid = ~np.isnan(factor_values[:, t])
            if np.sum(valid) < 10:
                ls_returns[t] = np.nan
                continue
            fv = factor_values[valid, t]
            fr = future_returns[valid, t]

            long_raw = np.clip(fv, 0.0, None)
            short_raw = np.clip(-fv, 0.0, None)
            long_sum = np.sum(long_raw)
            short_sum = np.sum(short_raw)
            if long_sum < 1e-10 or short_sum < 1e-10:
                ls_returns[t] = np.nan
                continue

            w_long = long_raw / long_sum
            w_short = short_raw / short_sum
            ls_returns[t] = float(np.dot(w_long, fr) - np.dot(w_short, fr))
        return ls_returns

    def build_market_data(self) -> Tuple[List[str], np.ndarray, np.ndarray]:
        """生成交易日历、股票收益和前瞻收益标签。"""
        dates = self.generate_dates()
        stock_returns = self.generate_stock_returns()
        forward_returns = self.calculate_forward_returns_ex_t(stock_returns, self.config.rolling_window)
        self._latest_dates = dates
        self._latest_stock_returns = stock_returns
        self._latest_forward_returns = forward_returns
        return dates, stock_returns, forward_returns

    def generate_factors(self, dates: List[str], forward_returns: np.ndarray) -> List[EnhancedFactor]:
        """生成包含历史表现的因子对象列表。"""
        return self.generate_factors_with_regime(
            dates=dates,
            forward_returns=forward_returns,
            phase_boundaries=None,
            phase_transition_probs=None,
        )

    def generate_factors_with_regime(
        self,
        dates: List[str],
        forward_returns: np.ndarray,
        phase_boundaries: Optional[Dict[str, int]] = None,
        phase_transition_probs: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None,
    ) -> List[EnhancedFactor]:
        """生成包含历史表现的因子对象列表（可选按train/val/test分阶段转移矩阵）。"""
        factors = []
        n_periods = forward_returns.shape[1]
        n_good = int(self.config.num_factors * self.config.good_ratio)
        n_medium = int(self.config.num_factors * self.config.medium_ratio)
        n_bad = self.config.num_factors - n_good - n_medium
        factor_specs = (
            [("good", i, 8.0, 2.0) for i in range(n_good)]
            + [("medium", i, 5.0, 5.0) for i in range(n_medium)]
            + [("bad", i, 2.0, 8.0) for i in range(n_bad)]
        )
        for topic, i, alpha, beta in self._iter_progress(
            factor_specs,
            desc="模拟因子暴露与历史表现",
            total=len(factor_specs),
        ):
            factor = EnhancedFactor(
                factor_id=f"{topic}_{i:03d}",
                expression=f"{topic.upper()}_FACTOR_{i}",
                topic=topic,
            )
            factor.alpha, factor.beta = alpha, beta
            self._add_factor_performance(
                factor, topic, dates, forward_returns, n_periods, phase_boundaries, phase_transition_probs
            )
            factors.append(factor)

        return factors

    def _state_ic_params(self, state: str) -> Tuple[float, float]:
        if state == "good":
            return self.config.good_ic_mean, self.config.good_ic_std
        if state == "medium":
            return self.config.medium_ic_mean, self.config.medium_ic_std
        return self.config.bad_ic_mean, self.config.bad_ic_std

    def _sample_state(self, probs: Dict[str, float]) -> str:
        states = list(self.config.latent_states)
        p = np.array([probs[s] for s in states], dtype=float)
        p = p / p.sum()
        return str(np.random.choice(states, p=p))

    def _phase_for_signal_index(self, t: int, phase_boundaries: Dict[str, int]) -> str:
        realized_idx = t + self.config.rolling_window
        if realized_idx <= phase_boundaries.get("train_end_idx", -1):
            return "train"
        if realized_idx <= phase_boundaries.get("val_end_idx", -1):
            return "validation"
        return "test"

    def _generate_latent_state_series(
        self,
        anchor_label: str,
        n_periods: int,
        phase_boundaries: Optional[Dict[str, int]] = None,
        phase_transition_probs: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None,
    ) -> List[str]:
        init_probs = self.config.init_state_probs[anchor_label]
        default_transition_probs = self.config.transition_probs
        reversion_prob = self.config.anchor_reversion_prob[anchor_label]

        states = [self._sample_state(init_probs)]
        for t in self._iter_progress(
            range(1, n_periods),
            desc=f"状态转移[{anchor_label}]",
            total=max(n_periods - 1, 0),
        ):
            prev = states[-1]
            transition_probs = default_transition_probs
            if phase_boundaries is not None and phase_transition_probs:
                phase_name = self._phase_for_signal_index(t, phase_boundaries)
                transition_probs = phase_transition_probs.get(phase_name, default_transition_probs)
            if np.random.rand() < reversion_prob:
                states.append(anchor_label)
            else:
                states.append(self._sample_state(transition_probs[prev]))
        return states

    def _add_factor_performance(
        self,
        factor: EnhancedFactor,
        anchor_label: str,
        dates: List[str],
        forward_returns: np.ndarray,
        n_periods: int,
        phase_boundaries: Optional[Dict[str, int]] = None,
        phase_transition_probs: Optional[Dict[str, Dict[str, Dict[str, float]]]] = None,
    ):
        latent_states = self._generate_latent_state_series(
            anchor_label,
            n_periods,
            phase_boundaries=phase_boundaries,
            phase_transition_probs=phase_transition_probs,
        )
        target_ic_series = np.zeros(n_periods)
        ic_std_series = np.zeros(n_periods)
        for t, state in enumerate(latent_states):
            mean_t, std_t = self._state_ic_params(state)
            target_ic_series[t] = mean_t
            ic_std_series[t] = std_t

        factor_values = self.generate_factor_values(forward_returns, target_ic_series, ic_std_series)
        self._factor_values_map[factor.id] = factor_values
        ic_series = self.calculate_factor_ic(factor_values, forward_returns)
        ls_returns = self.calculate_factor_ls_return(factor_values, forward_returns)

        for t in range(min(n_periods, len(ic_series))):
            if not np.isnan(ic_series[t]) and not np.isnan(ls_returns[t]):
                rank = np.nanpercentile(ic_series[:t+1], 50) if t > 0 else 0.5
                # 信号在 dates[t]，标签为 R(t+1->t+n)，可用时点为 dates[t+n]。
                realized_idx = t + self.config.rolling_window
                if realized_idx >= len(dates):
                    continue
                factor.add_daily_performance(
                    date=dates[realized_idx],
                    ic=ic_series[t],
                    ls_return=ls_returns[t],
                    rank_percentile=rank
                )

        state_counts = {s: latent_states.count(s) for s in self.config.latent_states}
        factor.simulation_profile = {
            'anchor_label': anchor_label,
            'state_counts': state_counts,
            'state_ratios': {k: v / max(len(latent_states), 1) for k, v in state_counts.items()}
        }

    @staticmethod
    def _build_stock_codes(n_stocks: int) -> List[str]:
        return [f"S{i:06d}" for i in range(n_stocks)]

    def export_as_real_data_format(
        self,
        output_root: str = "data",
        pool_name: str = "all_stocks",
        include_forward_returns: bool = True,
    ) -> Dict[str, str]:
        """
        将最近一次模拟数据按“真实数据接入格式”写盘（CSV）。

        目录结构：
        - {output_root}/base/daily_returns.csv
        - {output_root}/factors/{factor_id}.csv
        - {output_root}/pools/{pool_name}.csv
        - {output_root}/labels/forward_returns_h{window}.csv (可选)
        - {output_root}/meta/simulation_manifest.json
        """
        if self._latest_dates is None or self._latest_stock_returns is None or self._latest_forward_returns is None:
            raise ValueError("尚未生成市场数据，请先调用 build_market_data()")
        if not self._factor_values_map:
            raise ValueError("尚未生成因子暴露，请先调用 generate_factors()/generate_factors_with_regime()")

        os.makedirs(output_root, exist_ok=True)
        base_dir = os.path.join(output_root, "base")
        factors_dir = os.path.join(output_root, "factors")
        pools_dir = os.path.join(output_root, "pools")
        labels_dir = os.path.join(output_root, "labels")
        meta_dir = os.path.join(output_root, "meta")
        os.makedirs(base_dir, exist_ok=True)
        os.makedirs(factors_dir, exist_ok=True)
        os.makedirs(pools_dir, exist_ok=True)
        os.makedirs(meta_dir, exist_ok=True)
        if include_forward_returns:
            os.makedirs(labels_dir, exist_ok=True)

        dates = self._latest_dates
        stock_returns = self._latest_stock_returns
        forward_returns = self._latest_forward_returns
        n_stocks, n_days = stock_returns.shape
        stock_codes = self._build_stock_codes(n_stocks)
        n_signals = forward_returns.shape[1]

        daily_returns_path = os.path.join(base_dir, "daily_returns.csv")
        with open(daily_returns_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["end_date", "stock_code", "rtn"])
            writer.writeheader()
            for day_idx in self._iter_progress(
                range(n_days),
                desc="写出base/daily_returns",
                total=n_days,
            ):
                d = dates[day_idx]
                for stock_idx, code in enumerate(stock_codes):
                    writer.writerow({
                        "end_date": d,
                        "stock_code": code,
                        "rtn": float(stock_returns[stock_idx, day_idx]),
                    })

        pool_path = os.path.join(pools_dir, f"{pool_name}.csv")
        with open(pool_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["end_date", "stock_code", "in_pool"])
            writer.writeheader()
            for d in self._iter_progress(
                dates,
                desc="写出pools",
                total=len(dates),
            ):
                for code in stock_codes:
                    writer.writerow({
                        "end_date": d,
                        "stock_code": code,
                        "in_pool": 1,
                    })

        factor_file_count = 0
        factor_items = list(self._factor_values_map.items())
        for factor_id, values in self._iter_progress(
            factor_items,
            desc="写出factors",
            total=len(factor_items),
        ):
            out_path = os.path.join(factors_dir, f"{factor_id}.csv")
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["end_date", "stock_code", "score"])
                writer.writeheader()
                for signal_idx in range(min(n_signals, values.shape[1])):
                    d = dates[signal_idx]
                    for stock_idx, code in enumerate(stock_codes):
                        writer.writerow({
                            "end_date": d,
                            "stock_code": code,
                            "score": float(values[stock_idx, signal_idx]),
                        })
            factor_file_count += 1

        labels_path = ""
        if include_forward_returns:
            labels_path = os.path.join(labels_dir, f"forward_returns_h{self.config.rolling_window}.csv")
            with open(labels_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=["end_date", "label_start_date", "label_end_date", "stock_code", "forward_rtn"],
                )
                writer.writeheader()
                for signal_idx in self._iter_progress(
                    range(n_signals),
                    desc="写出labels",
                    total=n_signals,
                ):
                    signal_date = dates[signal_idx]
                    label_start = dates[signal_idx + 1]
                    label_end = dates[signal_idx + self.config.rolling_window]
                    for stock_idx, code in enumerate(stock_codes):
                        writer.writerow({
                            "end_date": signal_date,
                            "label_start_date": label_start,
                            "label_end_date": label_end,
                            "stock_code": code,
                            "forward_rtn": float(forward_returns[stock_idx, signal_idx]),
                        })

        manifest_path = os.path.join(meta_dir, "simulation_manifest.json")
        manifest = {
            "start_date": dates[0] if dates else None,
            "end_date": dates[-1] if dates else None,
            "num_days": n_days,
            "generation_mode": "date_range" if self.config.end_date is not None else "num_days",
            "config_start_date": self.config.start_date,
            "config_end_date": self.config.end_date,
            "config_num_days": self.config.num_days,
            "num_stocks": n_stocks,
            "num_factors": factor_file_count,
            "rolling_window": self.config.rolling_window,
            "daily_returns_file": daily_returns_path,
            "pool_file": pool_path,
            "factors_dir": factors_dir,
            "labels_file": labels_path if include_forward_returns else None,
            "time_alignment": "signal x(t,end_of_day) -> label R(t+1->t+n), excludes t-day return",
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        return {
            "output_root": output_root,
            "daily_returns_file": daily_returns_path,
            "pool_file": pool_path,
            "factors_dir": factors_dir,
            "labels_file": labels_path if include_forward_returns else "",
            "manifest_file": manifest_path,
        }
