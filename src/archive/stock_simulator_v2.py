"""
股票数据模拟器 V2 - 修正版本

修正问题：
1. 因子生成：精确控制与未来收益的相关性等于设定的IC
2. 多空收益：使用得分加权，而非等权
3. IC参数：方差固定，只用均值区分因子质量
"""

import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class StockData:
    """股票数据容器"""
    dates: np.ndarray  # 日期序列，长度T
    stock_ids: List[str]  # 股票ID列表，长度N
    returns: np.ndarray  # 收益率矩阵，形状(T, N)


@dataclass
class FactorData:
    """因子数据容器"""
    factor_ids: List[str]  # 因子ID列表，长度K
    dates: np.ndarray  # 日期序列，长度T
    stock_ids: List[str]  # 股票ID列表，长度N
    factor_scores: np.ndarray  # 因子得分矩阵，形状(T, K, N)
    ic_means: np.ndarray  # 每个因子的IC均值，长度K


class StockDataSimulatorV2:
    """股票数据模拟器 V2"""
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        np.random.seed(seed)
    
    def simulate_stock_returns(
        self,
        num_stocks: int = 100,
        num_days: int = 252,
        start_date: str = "2023-01-01",
        return_mean: float = 0.0002,
        return_std: float = 0.02,
        correlation_level: float = 0.3
    ) -> StockData:
        """模拟股票收益率序列"""
        print(f"模拟股票收益率: {num_stocks}只股票, {num_days}个交易日")
        
        # 生成日期序列
        dates = self._generate_dates(start_date, num_days)
        stock_ids = [f"stock_{i:03d}" for i in range(num_stocks)]
        
        # 使用因子模型生成相关收益率
        returns = self._generate_factor_model_returns(
            num_stocks, num_days, return_mean, return_std, correlation_level
        )
        
        stock_data = StockData(dates=dates, stock_ids=stock_ids, returns=returns)
        print(f"股票数据生成完成: {dates[0]} 到 {dates[-1]}")
        print(f"收益率统计: 均值={returns.mean():.6f}, 标准差={returns.std():.6f}")
        
        return stock_data
    
    def simulate_factor_data(
        self,
        stock_data: StockData,
        num_factors: int = 50,
        ic_mean_range: Tuple[float, float] = (0.01, 0.10),
        ic_std_fixed: float = 0.03,  # 固定IC标准差
        noise_level: float = 0.3
    ) -> FactorData:
        """
        基于股票收益率生成因子得分
        
        核心逻辑：
        1. 为每个因子设定IC均值（决定因子质量）
        2. 生成IC序列：IC_t ~ N(ic_mean, ic_std_fixed^2)
        3. 生成因子得分，使其与t+1期收益的相关性 = IC_t
        """
        print(f"模拟因子数据: {num_factors}个因子")
        print(f"IC标准差固定为: {ic_std_fixed}")
        
        T, N = stock_data.returns.shape
        dates = stock_data.dates
        stock_ids = stock_data.stock_ids
        
        # 1. 生成因子ID和IC均值
        factor_ids = [f"factor_{i:03d}" for i in range(num_factors)]
        ic_means = np.random.uniform(*ic_mean_range, size=num_factors)
        
        print(f"IC均值范围: {ic_means.min():.3f} 到 {ic_means.max():.3f}")
        
        # 2. 生成因子得分矩阵（T, K, N）
        factor_scores = np.zeros((T, num_factors, N))
        
        for k in range(num_factors):
            ic_mean = ic_means[k]
            
            # 生成该因子的IC序列（正态分布）
            ic_series = np.random.normal(ic_mean, ic_std_fixed, T)
            
            # 第一天：随机初始化
            factor_scores[0, k, :] = np.random.randn(N)
            
            # 后续天数：基于IC生成因子得分
            for t in range(1, T):
                # 目标：生成因子得分，使其与t期收益的相关性 = ic_series[t-1]
                # 因为t-1期因子预测t期收益
                
                # t期收益率（要预测的目标）
                target_returns = stock_data.returns[t, :]
                
                # 标准化目标收益率
                target_std = target_returns.std()
                if target_std < 1e-8:
                    target_normalized = np.zeros_like(target_returns)
                else:
                    target_normalized = (target_returns - target_returns.mean()) / target_std
                
                # 当前IC值
                current_ic = ic_series[t-1]
                
                # 方法：因子得分 = IC * 标准化收益 + sqrt(1-IC^2) * 独立噪声
                # 这样可以保证相关性恰好等于IC
                
                # 信号部分：与收益相关的部分
                signal_part = current_ic * target_normalized
                
                # 噪声部分：独立随机部分
                # 需要保证噪声与信号正交，且总方差为1
                noise = np.random.randn(N)
                
                # 使噪声与信号正交（相关系数为0）
                # 通过减去在信号上的投影
                if np.abs(current_ic) > 1e-8:
                    # 计算噪声在信号上的投影
                    projection = np.dot(noise, signal_part) / np.dot(signal_part, signal_part)
                    noise_orthogonal = noise - projection * signal_part
                else:
                    noise_orthogonal = noise
                
                # 标准化正交噪声
                noise_std = noise_orthogonal.std()
                if noise_std < 1e-8:
                    noise_normalized = np.zeros_like(noise_orthogonal)
                else:
                    noise_normalized = noise_orthogonal / noise_std
                
                # 组合：信号 + 正交噪声
                # 权重保证总方差为1，且与目标的相关性为IC
                signal_weight = np.abs(current_ic)
                noise_weight = np.sqrt(1 - current_ic**2)
                
                raw_scores = signal_weight * signal_part + noise_weight * noise_normalized
                
                # 加入额外噪声（模拟因子不完美）
                extra_noise = np.random.randn(N) * noise_level
                raw_scores = raw_scores + extra_noise
                
                # 标准化为N(0,1)
                score_std = raw_scores.std()
                if score_std < 1e-8:
                    factor_scores[t, k, :] = np.zeros_like(raw_scores)
                else:
                    factor_scores[t, k, :] = (raw_scores - raw_scores.mean()) / score_std
        
        # 创建FactorData对象
        factor_data = FactorData(
            factor_ids=factor_ids,
            dates=dates,
            stock_ids=stock_ids,
            factor_scores=factor_scores,
            ic_means=ic_means
        )
        
        print(f"因子数据生成完成")
        print(f"因子得分形状: {factor_scores.shape}")
        
        return factor_data
    
    def calculate_factor_performance(
        self,
        factor_data: FactorData,
        stock_data: StockData
    ) -> List[Dict]:
        """计算因子表现（使用得分加权多空组合）"""
        print("计算因子表现（得分加权）...")
        
        T, K, N = factor_data.factor_scores.shape
        results = []
        
        for k in range(K):
            factor_id = factor_data.factor_ids[k]
            
            ic_values = []
            ls_returns = []
            
            for t in range(1, T):  # 从第2天开始，需要滞后一期
                # t-1期的因子得分
                scores_t_minus_1 = factor_data.factor_scores[t-1, k, :].copy()
                
                # t期的收益率
                returns_t = stock_data.returns[t, :].copy()
                
                # 去除NaN
                valid_mask = ~(np.isnan(scores_t_minus_1) | np.isnan(returns_t))
                if np.sum(valid_mask) < 10:
                    continue
                    
                scores_valid = scores_t_minus_1[valid_mask]
                returns_valid = returns_t[valid_mask]
                
                # 计算IC（横截面相关性）
                ic = np.corrcoef(scores_valid, returns_valid)[0, 1]
                if not np.isnan(ic):
                    ic_values.append(ic)
                
                # 计算多空收益（得分加权，杠杆2倍）
                # 多头：得分最高的前30%
                # 空头：得分最低的前30%
                
                # 排序
                sorted_indices = np.argsort(scores_valid)
                n_valid = len(scores_valid)
                
                long_count = max(1, int(n_valid * 0.3))
                short_count = max(1, int(n_valid * 0.3))
                
                long_indices = sorted_indices[-long_count:]
                short_indices = sorted_indices[:short_count]
                
                # 计算权重（与得分成正比，标准化后权重和为1）
                # 多头权重：正比于得分，且和为1
                long_scores = scores_valid[long_indices]
                if long_scores.sum() > 0:
                    long_weights = long_scores / long_scores.sum()
                else:
                    long_weights = np.ones_like(long_scores) / len(long_scores)
                
                # 空头权重：负向得分（得分越低，做空权重越大），权重和为-1
                short_scores = scores_valid[short_indices]
                # 对空头得分取负，使得得分越低的股票做空权重越大
                short_scores_neg = -short_scores
                if short_scores_neg.sum() > 0:
                    short_weights = -short_scores_neg / short_scores_neg.sum()  # 和为-1
                else:
                    short_weights = -np.ones_like(short_scores) / len(short_scores)
                
                # 计算加权收益
                long_return = np.sum(long_weights * returns_valid[long_indices])
                short_return = np.sum(short_weights * returns_valid[short_indices])
                
                # 多空组合收益 = 多头收益 - 空头收益
                # 注意：short_return已经是负权重计算的，所以这里直接相加
                ls_return = long_return + short_return  # 因为short_weights已经是负的
                ls_returns.append(ls_return)
            
            if len(ic_values) > 10:
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
        num_factors = max(3, int(np.sqrt(num_stocks)))
        
        # 因子收益率
        factor_returns = np.random.randn(num_days, num_factors)
        
        # 因子暴露
        factor_loadings = np.random.randn(num_stocks, num_factors) * 0.5
        
        # 共同部分
        common_returns = factor_returns @ factor_loadings.T
        
        # 特异部分
        specific_ratio = np.sqrt(1 - correlation_level)
        specific_returns = np.random.randn(num_days, num_stocks) * specific_ratio
        
        # 合并
        raw_returns = common_returns + specific_returns
        
        # 调整统计量
        returns_normalized = (raw_returns - raw_returns.mean()) / (raw_returns.std() + 1e-8)
        returns_adjusted = return_mean + return_std * returns_normalized
        
        return returns_adjusted
    
    def verify_factor_generation(
        self,
        factor_data: FactorData,
        stock_data: StockData,
        factor_index: int = 0
    ) -> Dict:
        """验证因子生成是否正确"""
        print(f"\n验证因子生成: {factor_data.factor_ids[factor_index]}")
        
        T, K, N = factor_data.factor_scores.shape
        target_ic_mean = factor_data.ic_means[factor_index]
        
        # 计算实际IC序列
        actual_ics = []
        for t in range(1, T):
            scores = factor_data.factor_scores[t-1, factor_index, :]
            returns = stock_data.returns[t, :]
            
            valid_mask = ~(np.isnan(scores) | np.isnan(returns))
            if np.sum(valid_mask) > 10:
                ic = np.corrcoef(scores[valid_mask], returns[valid_mask])[0, 1]
                if not np.isnan(ic):
                    actual_ics.append(ic)
        
        if actual_ics:
            actual_ic_mean = np.mean(actual_ics)
            actual_ic_std = np.std(actual_ics)
            
            print(f"目标IC均值: {target_ic_mean:.4f}")
            print(f"实际IC均值: {actual_ic_mean:.4f}")
            print(f"实际IC标准差: {actual_ic_std:.4f}")
            print(f"IC误差: {abs(actual_ic_mean - target_ic_mean):.4f}")
            
            return {
                'target_ic': target_ic_mean,
                'actual_ic': actual_ic_mean,
                'ic_std': actual_ic_std,
                'error': abs(actual_ic_mean - target_ic_mean)
            }
        
        return {}


def test_simulator_v2():
    """测试V2模拟器"""
    print("=" * 60)
    print("股票数据模拟器 V2 测试")
    print("=" * 60)
    
    simulator = StockDataSimulatorV2(seed=42)
    
    # 1. 模拟股票数据
    print("\n1. 模拟股票收益率...")
    stock_data = simulator.simulate_stock_returns(
        num_stocks=50,
        num_days=100,
        start_date="2023-01-01"
    )
    
    # 2. 模拟因子数据
    print("\n2. 模拟因子数据...")
    factor_data = simulator.simulate_factor_data(
        stock_data=stock_data,
        num_factors=20,
        ic_mean_range=(0.02, 0.08),
        ic_std_fixed=0.03,  # 固定IC标准差
        noise_level=0.2
    )
    
    # 3. 验证因子生成
    print("\n3. 验证因子生成...")
    for i in range(3):  # 验证前3个因子
        simulator.verify_factor_generation(factor_data, stock_data, i)
    
    # 4. 计算表现
    print("\n4. 计算因子表现...")
    performance = simulator.calculate_factor_performance(factor_data, stock_data)
    
    # 5. 显示结果
    print("\n5. 前10个因子表现:")
    print("-" * 80)
    print(f"{'因子ID':<12} {'IC均值':<8} {'ICIR':<8} {'年化收益':<10} {'夏普':<8}")
    print("-" * 80)
    
    for r in performance[:10]:
        print(f"{r['factor_id']:<12} {r['ic_mean']:<8.3f} "
              f"{r['icir']:<8.3f} {r['ls_return_annual']:<10.3f} "
              f"{r['ls_sharpe']:<8.3f}")
    
    # 6. 统计
    print("\n6. 统计信息:")
    icirs = [r['icir'] for r in performance]
    if icirs:
        print(f"ICIR范围: {min(icirs):.3f} 到 {max(icirs):.3f}")
        print(f"平均ICIR: {np.mean(icirs):.3f}")
        print(f"正ICIR比例: {sum(1 for x in icirs if x > 0)/len(icirs):.1%}")
        
        # IC均值与ICIR的关系
        ic_means = [r['ic_mean'] for r in performance]
        icir_corr = np.corrcoef(ic_means, icirs)[0, 1]
        print(f"IC均值与ICIR相关性: {icir_corr:.3f}")
    
    return stock_data, factor_data, performance


if __name__ == "__main__":
    print("股票数据模拟器 V2 - 修正版本")
    print("=" * 60)
    
    stock_data, factor_data, performance = test_simulator_v2()
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)