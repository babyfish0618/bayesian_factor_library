"""
股票数据模拟器

按照研究员的设计：
1. 模拟股票收益率序列（T×N）
2. 基于IC序列生成因子得分（T×K×N）
3. 支持滞后一期评估
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass
class StockData:
    """股票数据容器"""
    dates: np.ndarray  # 日期序列，长度T
    stock_ids: List[str]  # 股票ID列表，长度N
    returns: np.ndarray  # 收益率矩阵，形状(T, N)
    
    def __post_init__(self):
        """验证数据形状"""
        assert len(self.dates) == self.returns.shape[0], "日期数与收益率行数不一致"
        assert len(self.stock_ids) == self.returns.shape[1], "股票数与收益率列数不一致"
    
    def get_date_range(self) -> Tuple[str, str]:
        """获取日期范围"""
        return self.dates[0], self.dates[-1]
    
    def get_returns_for_date(self, date: str) -> np.ndarray:
        """获取某一天的收益率"""
        idx = np.where(self.dates == date)[0]
        if len(idx) == 0:
            raise ValueError(f"日期 {date} 不存在")
        return self.returns[idx[0], :]
    
    def get_returns_for_period(self, start_date: str, end_date: str) -> np.ndarray:
        """获取时间段内的收益率"""
        start_idx = np.where(self.dates >= start_date)[0][0]
        end_idx = np.where(self.dates <= end_date)[0][-1]
        return self.returns[start_idx:end_idx+1, :]


@dataclass
class FactorData:
    """因子数据容器"""
    factor_ids: List[str]  # 因子ID列表，长度K
    dates: np.ndarray  # 日期序列，长度T
    stock_ids: List[str]  # 股票ID列表，长度N
    factor_scores: np.ndarray  # 因子得分矩阵，形状(T, K, N)
    ic_means: np.ndarray  # 每个因子的IC均值，长度K
    ic_stds: np.ndarray  # 每个因子的IC标准差，长度K
    
    def __post_init__(self):
        """验证数据形状"""
        T, K, N = self.factor_scores.shape
        assert len(self.dates) == T, "日期数不一致"
        assert len(self.factor_ids) == K, "因子数不一致"
        assert len(self.stock_ids) == N, "股票数不一致"
        assert len(self.ic_means) == K, "IC均值数不一致"
        assert len(self.ic_stds) == K, "IC标准差数不一致"
    
    def get_factor_scores(self, factor_id: str, date: str) -> np.ndarray:
        """获取某个因子在某一天的得分"""
        factor_idx = self.factor_ids.index(factor_id)
        date_idx = np.where(self.dates == date)[0][0]
        return self.factor_scores[date_idx, factor_idx, :]
    
    def get_factor_time_series(self, factor_id: str, stock_id: str) -> np.ndarray:
        """获取某个因子对某个股票的时间序列"""
        factor_idx = self.factor_ids.index(factor_id)
        stock_idx = self.stock_ids.index(stock_id)
        return self.factor_scores[:, factor_idx, stock_idx]


class StockDataSimulator:
    """股票数据模拟器"""
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        np.random.seed(seed)
    
    def simulate_stock_returns(
        self,
        num_stocks: int = 100,
        num_days: int = 252,
        start_date: str = "2023-01-01",
        return_mean: float = 0.0002,  # 日均收益
        return_std: float = 0.02,     # 日收益波动
        correlation_level: float = 0.3  # 股票间相关性
    ) -> StockData:
        """
        模拟股票收益率序列
        
        参数：
            num_stocks: 股票数量
            num_days: 交易日数量
            start_date: 开始日期
            return_mean: 平均日收益率
            return_std: 日收益率标准差
            correlation_level: 股票间平均相关性
            
        返回：StockData对象
        """
        print(f"模拟股票收益率: {num_stocks}只股票, {num_days}个交易日")
        
        # 1. 生成日期序列
        dates = self._generate_dates(start_date, num_days)
        
        # 2. 生成股票ID
        stock_ids = [f"stock_{i:03d}" for i in range(num_stocks)]
        
        # 3. 生成收益率序列（考虑相关性）
        returns = self._generate_correlated_returns(
            num_stocks, num_days, return_mean, return_std, correlation_level
        )
        
        # 创建StockData对象
        stock_data = StockData(
            dates=dates,
            stock_ids=stock_ids,
            returns=returns
        )
        
        print(f"股票数据生成完成: {dates[0]} 到 {dates[-1]}")
        print(f"收益率统计: 均值={returns.mean():.6f}, 标准差={returns.std():.6f}")
        
        return stock_data
    
    def simulate_factor_data(
        self,
        stock_data: StockData,
        num_factors: int = 50,
        ic_mean_range: Tuple[float, float] = (0.01, 0.10),  # IC均值范围
        ic_std_range: Tuple[float, float] = (0.02, 0.05),   # IC标准差范围
        noise_level: float = 0.5  # 噪声水平（0-1）
    ) -> FactorData:
        """
        基于股票收益率生成因子得分
        
        设计思路：
        1. 为每个因子生成IC序列（正态分布）
        2. 基于IC和收益率生成因子得分
        3. 加入噪声，使因子不完全预测收益率
        
        参数：
            stock_data: 股票数据
            num_factors: 因子数量
            ic_mean_range: IC均值范围（越小预测能力越弱）
            ic_std_range: IC标准差范围
            noise_level: 噪声水平（0=完美预测，1=完全噪声）
            
        返回：FactorData对象
        """
        print(f"模拟因子数据: {num_factors}个因子")
        
        T, N = stock_data.returns.shape
        dates = stock_data.dates
        stock_ids = stock_data.stock_ids
        
        # 1. 生成因子ID
        factor_ids = [f"factor_{i:03d}" for i in range(num_factors)]
        
        # 2. 为每个因子生成IC参数
        ic_means = np.random.uniform(*ic_mean_range, size=num_factors)
        ic_stds = np.random.uniform(*ic_std_range, size=num_factors)
        
        print(f"IC均值范围: {ic_means.min():.3f} 到 {ic_means.max():.3f}")
        print(f"IC标准差范围: {ic_stds.min():.3f} 到 {ic_stds.max():.3f}")
        
        # 3. 生成因子得分矩阵（T, K, N）
        factor_scores = np.zeros((T, num_factors, N))
        
        for k in range(num_factors):
            # 生成该因子的IC序列
            ic_series = np.random.normal(ic_means[k], ic_stds[k], T)
            
            # 基于IC生成因子得分
            for t in range(T):
                if t == 0:
                    # 第一天：随机初始化
                    factor_scores[t, k, :] = np.random.randn(N)
                else:
                    # 后续天数：基于IC和收益率生成
                    # 理想因子得分 = 标准化后的下一期收益率
                    next_returns = stock_data.returns[t, :]  # t期收益率
                    ideal_scores = (next_returns - next_returns.mean()) / (next_returns.std() + 1e-8)
                    
                    # 加入IC调节：IC越高，因子越能预测收益
                    ic = ic_series[t-1]  # 用t-1期的IC预测t期收益
                    effective_ic = ic * (1 - noise_level)  # 噪声降低有效性
                    
                    # 生成因子得分：理想得分（按IC加权） + 噪声
                    signal_part = effective_ic * ideal_scores
                    noise_part = np.sqrt(1 - effective_ic**2) * np.random.randn(N)
                    raw_scores = signal_part + noise_part
                    
                    # 标准化为N(0,1)
                    factor_scores[t, k, :] = (raw_scores - raw_scores.mean()) / (raw_scores.std() + 1e-8)
        
        # 创建FactorData对象
        factor_data = FactorData(
            factor_ids=factor_ids,
            dates=dates,
            stock_ids=stock_ids,
            factor_scores=factor_scores,
            ic_means=ic_means,
            ic_stds=ic_stds
        )
        
        print(f"因子数据生成完成")
        print(f"因子得分形状: {factor_scores.shape}")
        
        return factor_data
    
    def _generate_dates(self, start_date: str, num_days: int) -> np.ndarray:
        """生成日期序列"""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        dates = [start + timedelta(days=i) for i in range(num_days)]
        return np.array([d.strftime("%Y-%m-%d") for d in dates])
    
    def _generate_correlated_returns(
        self,
        num_stocks: int,
        num_days: int,
        return_mean: float,
        return_std: float,
        correlation_level: float
    ) -> np.ndarray:
        """生成有相关性的收益率序列"""
        
        # 1. 生成相关系数矩阵
        # 使用随机相关矩阵，平均相关性为correlation_level
        base_corr = np.eye(num_stocks)
        for i in range(num_stocks):
            for j in range(i+1, num_stocks):
                # 随机相关性，围绕correlation_level波动
                corr = correlation_level + np.random.uniform(-0.1, 0.1)
                corr = np.clip(corr, -0.9, 0.9)  # 避免极端值
                base_corr[i, j] = corr
                base_corr[j, i] = corr
        
        # 2. 确保相关矩阵是正定的
        # 添加小的正则项
        corr_matrix = base_corr + np.eye(num_stocks) * 0.01
        
        # 3. 简化：使用因子模型生成相关性
        # 避免复杂的Cholesky分解，使用更简单的方法
        # 生成几个共同因子，股票收益率 = 因子暴露 * 因子收益 + 特异收益
        
        num_factors = 3  # 3个共同因子
        factor_returns = np.random.randn(num_days, num_factors)
        factor_loadings = np.random.randn(num_stocks, num_factors)
        
        # 共同部分
        common_returns = factor_returns @ factor_loadings.T
        
        # 特异部分
        specific_returns = np.random.randn(num_days, num_stocks) * 0.5
        
        # 合并
        correlated_returns = common_returns + specific_returns
        
        # 4. 生成独立随机序列并转换
        independent_returns = np.random.randn(num_days, num_stocks)
        correlated_returns = independent_returns @ L.T
        
        # 5. 调整均值和标准差
        # 先标准化，再调整
        returns_normalized = (correlated_returns - correlated_returns.mean()) / correlated_returns.std()
        returns_adjusted = return_mean + return_std * returns_normalized
        
        return returns_adjusted
    
    def create_factor_performance_report(
        self,
        factor_data: FactorData,
        stock_data: StockData,
        evaluation_lag: int = 1
    ) -> List[Dict]:
        """
        创建因子表现报告
        
        计算每个因子的：
        1. IC均值、ICIR
        2. 多空收益（杠杆2倍）
        3. 夏普比率
        """
        print("计算因子表现...")
        
        T, K, N = factor_data.factor_scores.shape
        results = []
        
        for k in range(K):
            factor_id = factor_data.factor_ids[k]
            ic_mean = factor_data.ic_means[k]
            ic_std = factor_data.ic_stds[k]
            
            # 计算实际IC序列（滞后一期）
            ic_values = []
            long_short_returns = []
            
            for t in range(evaluation_lag, T):
                # t-1期的因子得分
                factor_scores_t_minus_1 = factor_data.factor_scores[t-1, k, :]
                
                # t期的收益率
                returns_t = stock_data.returns[t, :]
                
                # 计算IC（横截面相关性）
                valid_mask = ~(np.isnan(factor_scores_t_minus_1) | np.isnan(returns_t))
                if np.sum(valid_mask) > 10:  # 至少10个有效数据
                    ic = np.corrcoef(
                        factor_scores_t_minus_1[valid_mask],
                        returns_t[valid_mask]
                    )[0, 1]
                    ic_values.append(ic)
                
                # 计算多空收益（杠杆2倍）
                # 按因子值排序
                sorted_indices = np.argsort(factor_scores_t_minus_1)
                
                # 多头：前20%
                long_count = max(1, int(N * 0.2))
                long_indices = sorted_indices[-long_count:]
                
                # 空头：后20%
                short_count = max(1, int(N * 0.2))
                short_indices = sorted_indices[:short_count]
                
                # 等权组合，杠杆2倍（多头权重和=1，空头权重和=-1）
                long_return = returns_t[long_indices].mean()
                short_return = returns_t[short_indices].mean()
                
                # 多空组合收益 = 多头收益 - 空头收益
                ls_return = long_return - short_return
                long_short_returns.append(ls_return)
            
            if len(ic_values) > 0:
                # 计算IC统计
                ic_array = np.array(ic_values)
                ic_mean_actual = ic_array.mean()
                ic_std_actual = ic_array.std()
                icir = ic_mean_actual / (ic_std_actual + 1e-8) if ic_std_actual > 0 else 0
                
                # 计算多空收益统计
                ls_array = np.array(long_short_returns)
                ls_mean = ls_array.mean() * 252  # 年化
                ls_std = ls_array.std() * np.sqrt(252)  # 年化
                sharpe = ls_mean / (ls_std + 1e-8) if ls_std > 0 else 0
                
                results.append({
                    'factor_id': factor_id,
                    'ic_mean_target': ic_mean,      # 目标IC均值
                    'ic_std_target': ic_std,        # 目标IC标准差
                    'ic_mean_actual': ic_mean_actual,  # 实际IC均值
                    'ic_std_actual': ic_std_actual,    # 实际IC标准差
                    'icir': icir,                      # IC信息比率
                    'ls_return_annual': ls_mean,       # 年化多空收益
                    'ls_sharpe': sharpe,               # 多空夏普
                    'num_observations': len(ic_values) # 观测数
                })
        
        # 按ICIR排序
        results.sort(key=lambda x: x['icir'], reverse=True)
        
        print(f"表现报告生成完成: {len(results)} 个因子")
        if results:
            print(f"最佳因子: {results[0]['factor_id']}, ICIR={results[0]['icir']:.3f}")
            print(f"最差因子: {results[-1]['factor_id']}, ICIR={results[-1]['icir']:.3f}")
        
        return results


# 测试函数
def test_stock_simulator():
    """测试股票数据模拟器"""
    print("=" * 60)
    print("股票数据模拟器测试")
    print("=" * 60)
    
    # 创建模拟器
    simulator = StockDataSimulator(seed=42)
    
    # 1. 模拟股票收益率
    print("\n1. 模拟股票收益率...")
    stock_data = simulator.simulate_stock_returns(
        num_stocks=100,
        num_days=252,  # 1年交易日
        start_date="2023-01-01"
    )
    
    print(f"股票数据形状: {stock_data.returns.shape}")
    print(f"日期范围: {stock_data.get_date_range()}")
    
    # 2. 模拟因子数据
    print("\n2. 模拟因子数据...")
    factor_data = simulator.simulate_factor_data(
        stock_data=stock_data,
        num_factors=50,
        ic_mean_range=(0.01, 0.10),  # IC均值1%-10%
        ic_std_range=(0.02, 0.05),   # IC波动2%-5%
        noise_level=0.3  # 30%噪声
    )
    
    print(f"因子数据形状: {factor_data.factor_scores.shape}")
    
    # 3. 计算因子表现
    print("\n3. 计算因子表现...")
    performance_df = simulator.create_factor_performance_report(factor_data, stock_data)
    
    # 4. 显示结果
    print("\n4. 因子表现统计:")
    print("-" * 80)
    print(f"{'因子ID':<12} {'目标IC':<8} {'实际IC':<8} {'ICIR':<8} {'年化收益':<10} {'夏普':<8}")
    print("-" * 80)
    
    for row in performance_df[:10]:  # 前10个
        print(f"{row['factor_id']:<12} {row['ic_mean_target']:<8.3f} "
              f"{row['ic_mean_actual']:<8.3f} {row['icir']:<8.3f} "
              f"{row['ls_return_annual']:<10.3f} {row['ls_sharpe']:<8.3f}")
    
    # 5. 验证设计效果
    print("\n5. 设计验证:")
    
    # 计算目标IC和实际IC的相关性
    ic_targets = [r['ic_mean_target'] for r in performance_df]
    ic_actuals = [r['ic_mean_actual'] for r in performance_df]
    if len(ic_targets) > 1:
        corr = np.corrcoef(ic_targets, ic_actuals)[0, 1]
        print(f"目标IC vs 实际IC相关性: {corr:.3f}")
    
    icirs = [r['icir'] for r in performance_df]
    if icirs:
        print(f"ICIR范围: {min(icirs):.3f} 到 {max(icirs):.3f}")
        positive_ratio = sum(1 for icir in icirs if icir > 0) / len(icirs)
        print(f"正ICIR比例: {positive_ratio:.1%}")
    
    # 6. 检查滞后一期关系
    print("\n6. 滞后一期验证:")
    # 随机选一个因子检查
    if performance_df:
        test_factor_id = performance_df[0]['factor_id']
    factor_idx = factor_data.factor_ids.index(test_factor_id)
    
    # 计算不同滞后的IC
    ic_lag0 = []  # 同期（应该很低）
    ic_lag1 = []  # 滞后一期（应该较高）
    
    T, K, N = factor_data.factor_scores.shape
    for t in range(1, min(20, T)):  # 只看前20天
        # 同期：t期因子 vs t期收益
        factor_t = factor_data.factor_scores[t, factor_idx, :]
        returns_t = stock_data.returns[t, :]
        mask = ~(np.isnan(factor_t) | np.isnan(returns_t))
        if np.sum(mask) > 10:
            ic0 = np.corrcoef(factor_t[mask], returns_t[mask])[0, 1]
            ic_lag0.append(ic0)
        
        # 滞后一期：t-1期因子 vs t期收益
        factor_t_minus_1 = factor_data.factor_scores[t-1, factor_idx, :]
        ic1 = np.corrcoef(factor_t_minus_1[mask], returns_t[mask])[0, 1]
        ic_lag1.append(ic1)
    
    print(f"测试因子: {test_factor_id}")
    print(f"同期IC均值: {np.mean(ic_lag0):.3f} (应该接近0)")
    print(f"滞后一期IC均值: {np.mean(ic_lag1):.3f} (应该接近目标IC)")
    
    return stock_data, factor_data, performance_df


if __name__ == "__main__":
    print("股票数据模拟器 - 测试运行")
    print("版本: 0.1.0")
    print("=" * 60)
    
    stock_data, factor_data, performance_df = test_stock_simulator()
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)