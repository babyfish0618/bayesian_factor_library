"""
股票数据模拟器 - 简化版本

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
        
        使用因子模型方法：
        收益率 = 共同因子部分 + 特异部分
        """
        print(f"模拟股票收益率: {num_stocks}只股票, {num_days}个交易日")
        
        # 1. 生成日期序列
        dates = self._generate_dates(start_date, num_days)
        
        # 2. 生成股票ID
        stock_ids = [f"stock_{i:03d}" for i in range(num_stocks)]
        
        # 3. 使用因子模型生成相关收益率
        returns = self._generate_factor_model_returns(
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
    
    def _generate_factor_model_returns(
        self,
        num_stocks: int,
        num_days: int,
        return_mean: float,
        return_std: float,
        correlation_level: float
    ) -> np.ndarray:
        """使用因子模型生成相关收益率"""
        
        # 1. 生成共同因子
        num_factors = max(3, int(np.sqrt(num_stocks)))
        
        # 因子收益率
        factor_returns = np.random.randn(num_days, num_factors)
        
        # 因子暴露
        factor_loadings = np.random.randn(num_stocks, num_factors) * 0.5
        
        # 2. 计算共同部分
        common_returns = factor_returns @ factor_loadings.T
        
        # 3. 计算特异部分
        specific_ratio = np.sqrt(1 - correlation_level)
        specific_returns = np.random.randn(num_days, num_stocks) * specific_ratio
        
        # 4. 合并
        raw_returns = common_returns + specific_returns
        
        # 5. 调整统计量
        returns_normalized = (raw_returns - raw_returns.mean()) / (raw_returns.std() + 1e-8)
        returns_adjusted = return_mean + return_std * returns_normalized
        
        return returns_adjusted
    
    def calculate_factor_performance(
        self,
        factor_data: FactorData,
        stock_data: StockData
    ) -> List[Dict]:
        """计算因子表现"""
        print("计算因子表现...")
        
        T, K, N = factor_data.factor_scores.shape
        results = []
        
        for k in range(K):
            factor_id = factor_data.factor_ids[k]
            
            ic_values = []
            ls_returns = []
            
            for t in range(1, T):  # 从第2天开始，需要滞后一期
                # t-1期的因子得分
                scores_t_minus_1 = factor_data.factor_scores[t-1, k, :]
                
                # t期的收益率
                returns_t = stock_data.returns[t, :]
                
                # 计算IC
                valid_mask = ~(np.isnan(scores_t_minus_1) | np.isnan(returns_t))
                if np.sum(valid_mask) > 10:
                    ic = np.corrcoef(
                        scores_t_minus_1[valid_mask],
                        returns_t[valid_mask]
                    )[0, 1]
                    ic_values.append(ic)
                
                # 计算多空收益（杠杆2倍）
                sorted_idx = np.argsort(scores_t_minus_1)
                long_count = max(1, int(N * 0.1))  # 前10%
                short_count = max(1, int(N * 0.1))  # 后10%
                
                long_idx = sorted_idx[-long_count:]
                short_idx = sorted_idx[:short_count]
                
                long_ret = returns_t[long_idx].mean()
                short_ret = returns_t[short_idx].mean()
                ls_ret = long_ret - short_ret  # 多头-空头
                ls_returns.append(ls_ret)
            
            if len(ic_values) > 10:  # 至少10个有效观测
                ic_array = np.array(ic_values)
                ic_mean = ic_array.mean()
                ic_std = ic_array.std()
                icir = ic_mean / (ic_std + 1e-8)
                
                ls_array = np.array(ls_returns)
                ls_mean = ls_array.mean() * 252  # 年化
                ls_std = ls_array.std() * np.sqrt(252)
                sharpe = ls_mean / (ls_std + 1e-8)
                
                results.append({
                    'factor_id': factor_id,
                    'ic_mean': ic_mean,
                    'ic_std': ic_std,
                    'icir': icir,
                    'ls_return_annual': ls_mean,
                    'ls_sharpe': sharpe,
                    'obs_count': len(ic_values)
                })
        
        # 按ICIR排序
        results.sort(key=lambda x: x['icir'], reverse=True)
        
        print(f"计算完成: {len(results)} 个因子")
        if results:
            print(f"最佳因子: {results[0]['factor_id']}, ICIR={results[0]['icir']:.3f}")
            print(f"最差因子: {results[-1]['factor_id']}, ICIR={results[-1]['icir']:.3f}")
        
        return results


def test_simulator():
    """测试模拟器"""
    print("=" * 60)
    print("股票数据模拟器测试")
    print("=" * 60)
    
    simulator = StockDataSimulator(seed=42)
    
    # 1. 模拟股票数据
    print("\n1. 模拟股票收益率...")
    stock_data = simulator.simulate_stock_returns(
        num_stocks=50,  # 减少数量加快测试
        num_days=100,   # 减少天数
        start_date="2023-01-01"
    )
    
    # 2. 模拟因子数据
    print("\n2. 模拟因子数据...")
    factor_data = simulator.simulate_factor_data(
        stock_data=stock_data,
        num_factors=20,  # 减少因子数
        ic_mean_range=(0.02, 0.08),
        noise_level=0.4
    )
    
    # 3. 计算表现
    print("\n3. 计算因子表现...")
    performance = simulator.calculate_factor_performance(factor_data, stock_data)
    
    # 4. 显示结果
    print("\n4. 前10个因子表现:")
    print("-" * 80)
    print(f"{'因子ID':<12} {'IC均值':<8} {'ICIR':<8} {'年化收益':<10} {'夏普':<8}")
    print("-" * 80)
    
    for r in performance[:10]:
        print(f"{r['factor_id']:<12} {r['ic_mean']:<8.3f} "
              f"{r['icir']:<8.3f} {r['ls_return_annual']:<10.3f} "
              f"{r['ls_sharpe']:<8.3f}")
    
    # 5. 统计
    print("\n5. 统计信息:")
    icirs = [r['icir'] for r in performance]
    if icirs:
        print(f"ICIR范围: {min(icirs):.3f} 到 {max(icirs):.3f}")
        print(f"平均ICIR: {np.mean(icirs):.3f}")
        print(f"正ICIR比例: {sum(1 for x in icirs if x > 0)/len(icirs):.1%}")
    
    return stock_data, factor_data, performance


if __name__ == "__main__":
    print("股票数据模拟器 - 简化版本")
    print("=" * 60)
    
    stock_data, factor_data, performance = test_simulator()
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)