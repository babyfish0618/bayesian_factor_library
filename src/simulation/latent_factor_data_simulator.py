"""
潜在状态因子数据模拟器

将测试用的数据生成逻辑从 tests 中抽离，便于未来替换为真实数据源。
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Union

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


class LatentFactorDataSimulator:
    """长期锚定 + 短期潜在状态切换的数据模拟器。"""

    def __init__(self, config: LatentFactorSimulationConfig):
        self.config = config
        np.random.seed(config.random_seed)

    def generate_dates(self, num_days: int = None, start_date: str = None) -> List[str]:
        """生成交易日历（跳过周末）。"""
        n = num_days if num_days is not None else self.config.num_days
        s = start_date if start_date is not None else self.config.start_date
        dates = []
        current = datetime.strptime(s, "%Y-%m-%d")
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

        for i in range(n_good):
            factor = EnhancedFactor(factor_id=f"good_{i:03d}", expression=f"GOOD_FACTOR_{i}", topic="good")
            factor.alpha, factor.beta = 8.0, 2.0
            self._add_factor_performance(
                factor, "good", dates, forward_returns, n_periods, phase_boundaries, phase_transition_probs
            )
            factors.append(factor)

        for i in range(n_medium):
            factor = EnhancedFactor(factor_id=f"medium_{i:03d}", expression=f"MEDIUM_FACTOR_{i}", topic="medium")
            factor.alpha, factor.beta = 5.0, 5.0
            self._add_factor_performance(
                factor, "medium", dates, forward_returns, n_periods, phase_boundaries, phase_transition_probs
            )
            factors.append(factor)

        for i in range(n_bad):
            factor = EnhancedFactor(factor_id=f"bad_{i:03d}", expression=f"BAD_FACTOR_{i}", topic="bad")
            factor.alpha, factor.beta = 2.0, 8.0
            self._add_factor_performance(
                factor, "bad", dates, forward_returns, n_periods, phase_boundaries, phase_transition_probs
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
        for t in range(1, n_periods):
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
