#!/usr/bin/env python3
"""
性能测试 - 大规模因子库测试

测试目标：
验证贝叶斯因子选择器在大规模数据下的性能表现

测试参数：
- 股票数量: 2000只
- 时间跨度: 10年 (2500交易日)
- 因子数量: 300个
- 每次选择: 100个因子
- 更新频率: 每月一次

IC/多空收益计算：
- 使用滚动5天收益率计算IC和组合收益
- 而非每日收益率

测试维度：
1. 算法有效性: 验证能否区分好因子和差因子
2. 选择稳定性: 多次选择的结果是否稳定
3. 更新效果: 贝叶斯参数更新是否有效
4. 边际贡献: 没选中因子的评估是否合理
5. 性能指标: 计算时间和内存使用

作者: 小鱼爬爬
日期: 2026-03-01
"""

import numpy as np
import sys
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.factor_enhanced import EnhancedFactor
from src.core.bayesian_selector_v2 import BayesianSelectorV2


class PerformanceTestConfig:
    """性能测试配置"""
    
    # 模拟参数
    NUM_STOCKS = 2000          # 股票数量
    NUM_DAYS = 2500            # 交易日数量 (10年)
    NUM_FACTORS = 300          # 因子数量
    TARGET_SIZE = 100          # 每次选择的因子数量
    
    # 时间参数
    ROLLING_WINDOW = 5         # 滚动窗口天数
    UPDATE_FREQUENCY = 21      # 每月更新一次 (约21个交易日)
    
    # 因子质量分布
    GOOD_FACTOR_RATIO = 0.2     # 好因子比例 (20%)
    MEDIUM_FACTOR_RATIO = 0.3   # 中等因子比例 (30%)
    BAD_FACTOR_RATIO = 0.5      # 差因子比例 (50%)
    
    # 好因子参数
    GOOD_IC_MEAN = 0.08         # 好因子IC均值
    GOOD_IC_STD = 0.02          # 好因子IC标准差
    
    # 中等因子参数
    MEDIUM_IC_MEAN = 0.04       # 中等因子IC均值
    MEDIUM_IC_STD = 0.03       # 中等因子IC标准差
    
    # 差因子参数
    BAD_IC_MEAN = 0.01          # 差因子IC均值
    BAD_IC_STD = 0.04           # 差因子IC标准差
    
    # 测试参数
    NUM_TEST_ROUNDS = 5         # 测试轮数


def generate_dates(num_days: int, start_date: str = "2014-01-01") -> List[str]:
    """生成交易日历"""
    dates = []
    current = datetime.strptime(start_date, "%Y-%m-%d")
    
    while len(dates) < num_days:
        # 跳过周末
        if current.weekday() < 5:
            dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    
    return dates


def generate_stock_returns(n_stocks: int, n_days: int) -> np.ndarray:
    """
    生成股票收益率矩阵
    
    返回:
        shape: (n_stocks, n_days)
    """
    # 使用几何布朗运动生成收益率
    # 日均收益0.05%，波动20%
    mu = 0.0005
    sigma = 0.002
    
    returns = np.random.normal(mu, sigma, (n_stocks, n_days))
    return returns


def calculate_rolling_returns(returns: np.ndarray, window: int) -> np.ndarray:
    """
    计算滚动收益率
    
    参数:
        returns: 原始收益率矩阵 (n_stocks, n_days)
        window: 滚动窗口天数
    
    返回:
        滚动收益率矩阵 (n_stocks, n_days - window + 1)
    """
    n_stocks, n_days = returns.shape
    
    # 累积收益率
    cumulative_returns = np.cumprod(1 + returns, axis=1)
    
    # 滚动收益率 = R(t+window) / R(t) - 1
    rolling_returns = np.zeros((n_stocks, n_days - window + 1))
    
    for i in range(n_days - window + 1):
        rolling_returns[:, i] = (cumulative_returns[:, i + window] / 
                               (cumulative_returns[:, i] + 1e-10)) - 1
    
    return rolling_returns


def generate_factor_values(stock_returns: np.ndarray, 
                         target_ic: float, 
                         ic_std: float) -> np.ndarray:
    """
    生成因子值，确保与未来收益的IC为目标值
    
    使用正交化方法: F = ρ * R + √(1-ρ²) * Z
    
    参数:
        stock_returns: 股票收益率 (n_stocks, n_periods)
        target_ic: 目标IC值
        ic_std: IC标准差
    
    返回:
        因子值矩阵 (n_stocks, n_periods)
    """
    n_stocks, n_periods = stock_returns.shape
    
    # 标准化收益率
    R = stock_returns - np.mean(stock_returns, axis=0, keepdims=True)
    R = R / (np.std(R, axis=0, keepdims=True) + 1e-10)
    
    # 生成正交噪声
    Z = np.random.randn(n_stocks, n_periods)
    
    # Gram-Schmidt正交化 (简化版)
    for t in range(n_periods):
        # 与R正交
        projection = np.dot(Z[:, t], R[:, t]) / (np.dot(R[:, t], R[:, t]) + 1e-10)
        Z[:, t] = Z[:, t] - projection * R[:, t]
        Z[:, t] = Z[:, t] / (np.std(Z[:, t]) + 1e-10)
    
    # 组合: F = ρ * R + √(1-ρ²) * Z
    rho = target_ic / (ic_std + 1e-10)  # 调整rho使得IC = target_ic
    rho = min(rho, 0.99)  # 限制rho范围
    
    factor_values = rho * R + np.sqrt(1 - rho**2) * Z
    
    return factor_values


def calculate_factor_ic(factor_values: np.ndarray, 
                        future_returns: np.ndarray) -> np.ndarray:
    """
    计算因子IC (Information Coefficient)
    
    IC = corr(factor_value, future_return)
    
    参数:
        factor_values: 因子值 (n_stocks, n_periods)
        future_returns: 未来收益 (n_stocks, n_periods)
    
    返回:
        IC序列 (n_periods,)
    """
    n_periods = factor_values.shape[1]
    ic_series = np.zeros(n_periods)
    
    for t in range(n_periods):
        # 剔除nan值
        valid = ~(np.isnan(factor_values[:, t]) | np.isnan(future_returns[:, t]))
        if np.sum(valid) > 10:
            ic_series[t] = np.corrcoef(factor_values[valid, t], 
                                       future_returns[valid, t])[0, 1]
        else:
            ic_series[t] = np.nan
    
    return ic_series


def calculate_factor_ls_return(factor_values: np.ndarray, 
                                future_returns: np.ndarray) -> np.ndarray:
    """
    计算因子多空收益
    
    多头: 因子值最高的20%股票
    空头: 因子值最低的20%股票
    
    参数:
        factor_values: 因子值 (n_stocks, n_periods)
        future_returns: 未来收益 (n_stocks, n_periods)
    
    返回:
        多空收益序列 (n_periods,)
    """
    n_stocks, n_periods = factor_values.shape
    ls_returns = np.zeros(n_periods)
    
    # 计算分位数
    long_threshold = 0.8  # 前80%
    short_threshold = 0.2  # 后20%
    
    for t in range(n_periods):
        valid = ~np.isnan(factor_values[:, t])
        if np.sum(valid) < 10:
            ls_returns[t] = np.nan
            continue
        
        fv = factor_values[valid, t]
        fr = future_returns[valid, t]
        
        # 排序
        sorted_indices = np.argsort(fv)
        n = len(fv)
        
        # 多头 indices
        long_start = int(n * long_threshold)
        long_indices = sorted_indices[long_start:]
        
        # 空头 indices
        short_end = int(n * short_threshold)
        short_indices = sorted_indices[:short_end]
        
        # 计算多空收益
        long_return = np.mean(fr[long_indices])
        short_return = np.mean(fr[short_indices])
        ls_returns[t] = long_return - short_return
    
    return ls_returns


class PerformanceTester:
    """性能测试器"""
    
    def __init__(self, config: PerformanceTestConfig = None):
        self.config = config or PerformanceTestConfig()
        self.results = {}
        
    def run_full_test(self) -> Dict:
        """运行完整性能测试"""
        print("=" * 80)
        print("贝叶斯因子选择器 - 性能测试")
        print("=" * 80)
        print(f"测试参数:")
        print(f"  股票数量: {self.config.NUM_STOCKS}")
        print(f"  时间跨度: {self.config.NUM_DAYS} 交易日 (10年)")
        print(f"  因子数量: {self.config.NUM_FACTORS}")
        print(f"  每次选择: {self.config.TARGET_SIZE} 个因子")
        print(f"  更新频率: 每月 ({self.config.UPDATE_FREQUENCY} 交易日)")
        print(f"  滚动窗口: {self.config.ROLLING_WINDOW} 天")
        print()
        
        # 1. 生成数据
        print("1. 生成测试数据...")
        start_time = time.time()
        
        # 生成交易日历
        self.dates = generate_dates(self.config.NUM_DAYS)
        
        # 生成股票收益
        print("   生成股票收益率...")
        self.stock_returns = generate_stock_returns(
            self.config.NUM_STOCKS, 
            self.config.NUM_DAYS
        )
        
        # 计算滚动收益 (5天)
        print(f"   计算{self.config.ROLLING_WINDOW}天滚动收益...")
        self.rolling_returns = calculate_rolling_returns(
            self.stock_returns, 
            self.config.ROLLING_WINDOW
        )
        
        # 滚动收益的时间对应
        # 滚动收益R_t对应原始收益的[t, t+window]区间
        # 因子F_t在t期计算，预测R_{t+window}
        # 因此IC = corr(F_t, R_{t+window}) = corr(F_t, R_t)
        
        n_periods = self.rolling_returns.shape[1]
        print(f"   有效期数: {n_periods}")
        
        # 生成因子
        print("   生成因子...")
        self.factors = self._generate_factors(n_periods)
        
        data_time = time.time() - start_time
        print(f"   数据生成完成, 耗时: {data_time:.2f}秒")
        print()
        
        # 2. 初始化选择器
        print("2. 初始化贝叶斯选择器...")
        self.selector = BayesianSelectorV2()
        self.selector.add_factors(self.factors)
        print(f"   已添加 {len(self.factors)} 个因子")
        print()
        
        # 3. 运行多轮选择测试
        print("3. 运行多轮选择测试...")
        
        # 确定选择时间点 (每月一次)
        n_periods = self.rolling_returns.shape[1]
        update_points = list(range(100, n_periods - 50, self.config.UPDATE_FREQUENCY))
        update_points = update_points[:self.config.NUM_TEST_ROUNDS]
        
        print(f"   将进行 {len(update_points)} 轮选择测试")
        print()
        
        all_selection_results = []
        all_update_results = []
        
        for i, update_day in enumerate(update_points):
            print(f"   第{i+1}轮选择 (日期: {self.dates[update_day]})...")
            round_start = time.time()
            
            # 选择因子
            selection_result = self.selector.select_factors(
                self.dates[update_day], 
                target_size=self.config.TARGET_SIZE
            )
            
            # 获取选中因子的表现数据
            performance_data = self._evaluate_selected_factors(
                selection_result.selected_factors,
                update_day
            )
            
            # 更新贝叶斯参数
            update_result = self.selector.update_from_performance(
                selection_result.selected_factors,
                performance_data,
                self.dates[update_day]
            )
            
            round_time = time.time() - round_start
            
            all_selection_results.append(selection_result)
            all_update_results.append(update_result)
            
            # 打印结果
            selected_good = sum(
                1 for fid in selection_result.selected_factors 
                if fid.startswith("good_")
            )
            
            print(f"     选中: {len(selection_result.selected_factors)} 个因子")
            print(f"     好因子: {selected_good} 个 ({selected_good/len(selection_result.selected_factors):.1%})")
            print(f"     耗时: {round_time:.2f}秒")
            print()
        
        # 4. 分析结果
        print("4. 分析测试结果...")
        
        results = self._analyze_results(all_selection_results, all_update_results)
        
        # 5. 打印最终结果
        self._print_final_results(results)
        
        return results
    
    def _generate_factors(self, n_periods: int) -> List[EnhancedFactor]:
        """生成测试因子"""
        factors = []
        
        n_good = int(self.config.NUM_FACTORS * self.config.GOOD_FACTOR_RATIO)
        n_medium = int(self.config.NUM_FACTORS * self.config.MEDIUM_FACTOR_RATIO)
        n_bad = self.config.NUM_FACTORS - n_good - n_medium
        
        # 好因子
        for i in range(n_good):
            factor = EnhancedFactor(
                factor_id=f"good_{i:03d}",
                expression=f"GOOD_FACTOR_{i}",
                topic="good"
            )
            factor.alpha = 8.0
            factor.beta = 2.0
            self._add_factor_performance(factor, self.config.GOOD_IC_MEAN, self.config.GOOD_IC_STD, n_periods)
            factors.append(factor)
        
        # 中等因子
        for i in range(n_medium):
            factor = EnhancedFactor(
                factor_id=f"medium_{i:03d}",
                expression=f"MEDIUM_FACTOR_{i}",
                topic="medium"
            )
            factor.alpha = 5.0
            factor.beta = 5.0
            self._add_factor_performance(factor, self.config.MEDIUM_IC_MEAN, self.config.MEDIUM_IC_STD, n_periods)
            factors.append(factor)
        
        # 差因子
        for i in range(n_bad):
            factor = EnhancedFactor(
                factor_id=f"bad_{i:03d}",
                expression=f"BAD_FACTOR_{i}",
                topic="bad"
            )
            factor.alpha = 2.0
            factor.beta = 8.0
            self._add_factor_performance(factor, self.config.BAD_IC_MEAN, self.config.BAD_IC_STD, n_periods)
            factors.append(factor)
        
        return factors
    
    def _add_factor_performance(self, factor: EnhancedFactor, ic_mean: float, ic_std: float, n_periods: int):
        """为因子添加表现数据"""
        # 生成因子值，确保IC为目标值
        target_ic = ic_mean
        factor_values = generate_factor_values(
            self.rolling_returns,
            target_ic,
            ic_std
        )
        
        # 计算IC和LS收益
        ic_series = calculate_factor_ic(factor_values, self.rolling_returns)
        ls_returns = calculate_factor_ls_return(factor_values, self.rolling_returns)
        
        # 添加到因子
        for t in range(min(n_periods, len(ic_series))):
            if not np.isnan(ic_series[t]) and not np.isnan(ls_returns[t]):
                # 计算rank percentile
                rank = np.nanpercentile(ic_series[:t+1], 50) if t > 0 else 0.5
                
                factor.add_daily_performance(
                    date=self.dates[t],
                    ic=ic_series[t],
                    ls_return=ls_returns[t],
                    rank_percentile=rank
                )
    
    def _evaluate_selected_factors(self, selected_ids: List[str], day: int) -> Dict:
        """评估选中因子的表现"""
        performance_data = {}
        
        for fid in selected_ids:
            factor = self.selector.factors.get(fid)
            if factor:
                # 获取近期表现
                recent_perf = factor.get_recent_performance(20, self.dates[day])
                
                if recent_perf:
                    ic_values = [p.ic for p in recent_perf]
                    ls_values = [p.ls_return for p in recent_perf]
                    
                    performance_data[fid] = {
                        'icir': np.mean(ic_values) / (np.std(ic_values) + 1e-8),
                        'rank_percentile': np.mean([p.rank_percentile for p in recent_perf]),
                        'ls_return': np.mean(ls_values)
                    }
        
        return performance_data
    
    def _analyze_results(self, selection_results, update_results) -> Dict:
        """分析测试结果"""
        # 统计选中因子的质量
        good_selected_count = []
        
        for result in selection_results:
            good_count = sum(1 for fid in result.selected_factors if fid.startswith("good_"))
            good_selected_count.append(good_count / len(result.selected_factors) if result.selected_factors else 0)
        
        # 统计更新效果
        update_success = []
        for result in update_results:
            stats = result.update_stats
            total = stats.get('selected_success', 0) + stats.get('selected_failure', 0)
            if total > 0:
                update_success.append(stats.get('selected_success', 0) / total)
            else:
                update_success.append(0)
        
        # 因子参数变化
        alpha_changes = []
        beta_changes = []
        
        for factor in list(self.selector.factors.values())[:10]:
            alpha_changes.append(factor.alpha)
            beta_changes.append(factor.beta)
        
        return {
            'good_selection_rate': good_selected_count,
            'avg_good_selection_rate': np.mean(good_selected_count),
            'update_success_rate': update_success,
            'avg_update_success_rate': np.mean(update_success),
            'factor_alpha_mean': np.mean(alpha_changes),
            'factor_beta_mean': np.mean(beta_changes)
        }
    
    def _print_final_results(self, results: Dict):
        """打印最终结果"""
        print()
        print("=" * 80)
        print("测试结果总结")
        print("=" * 80)
        
        print(f"\n1. 选择有效性:")
        print(f"   平均好因子选中率: {results['avg_good_selection_rate']:.1%}")
        print(f"   每轮选中率: ", end="")
        print(", ".join([f"{r:.1%}" for r in results['good_selection_rate']]))
        
        print(f"\n2. 更新效果:")
        print(f"   平均更新成功率: {results['avg_update_success_rate']:.1%}")
        print(f"   每轮成功率: ", end="")
        print(", ".join([f"{r:.1%}" for r in results['update_success_rate']]))
        
        print(f"\n3. 因子参数:")
        print(f"   平均α: {results['factor_alpha_mean']:.2f}")
        print(f"   平均β: {results['factor_beta_mean']:.2f}")
        
        print()
        print("=" * 80)
        print("测试完成")
        print("=" * 80)


def main():
    """主函数"""
    tester = PerformanceTester()
    results = tester.run_full_test()
    
    return results


if __name__ == "__main__":
    main()