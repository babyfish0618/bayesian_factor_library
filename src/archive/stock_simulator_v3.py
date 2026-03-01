"""
股票数据模拟器 V3 - 精确控制IC版本

核心：生成因子得分，使其与t+1期收益的相关性精确等于设定的IC
方法：使用Cholesky分解精确控制相关性
"""

import numpy as np
from typing import List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class StockData:
    """股票数据容器"""
    dates: np.ndarray
    stock_ids: List[str]
    returns: np.ndarray


@dataclass
class FactorData:
    """因子数据容器"""
    factor_ids: List[str]
    dates: np.ndarray
    stock_ids: List[str]
    factor_scores: np.ndarray
    ic_means: np.ndarray


class StockDataSimulatorV3:
    """股票数据模拟器 V3 - 精确控制IC"""
    
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
        
        dates = self._generate_dates(start_date, num_days)
        stock_ids = [f"stock_{i:03d}" for i in range(num_stocks)]
        
        # 生成收益率
        returns = self._generate_returns(num_stocks, num_days, return_mean, return_std, correlation_level)
        
        stock_data = StockData(dates=dates, stock_ids=stock_ids, returns=returns)
        print(f"股票数据生成完成")
        
        return stock_data
    
    def simulate_factor_data(
        self,
        stock_data: StockData,
        num_factors: int = 50,
        ic_mean_range: Tuple[float, float] = (0.01, 0.10),
        ic_std_fixed: float = 0.03
    ) -> FactorData:
        """
        精确生成因子得分，控制与未来收益的相关性
        
        方法：
        1. 生成二元正态分布（因子得分，未来收益）
        2. 相关系数矩阵 = [[1, ic], [ic, 1]]
        3. Cholesky分解生成相关序列
        """
        print(f"模拟因子数据: {num_factors}个因子")
        print(f"IC标准差固定: {ic_std_fixed}")
        
        T, N = stock_data.returns.shape
        dates = stock_data.dates
        stock_ids = stock_data.stock_ids
        
        # 生成因子ID和IC均值
        factor_ids = [f"factor_{i:03d}" for i in range(num_factors)]
        ic_means = np.random.uniform(*ic_mean_range, size=num_factors)
        
        print(f"IC均值范围: {ic_means.min():.3f} 到 {ic_means.max():.3f}")
        
        # 生成因子得分矩阵
        factor_scores = np.zeros((T, num_factors, N))
        
        # 第一天随机初始化
        factor_scores[0, :, :] = np.random.randn(num_factors, N)
        
        # 为每个因子生成得分
        for k in range(num_factors):
            ic_mean = ic_means[k]
            
            # 生成该因子的IC序列
            ic_series = np.random.normal(ic_mean, ic_std_fixed, T)
            
            for t in range(1, T):
                # 目标：生成因子得分，使其与t期收益的相关性 = ic_series[t-1]
                current_ic = ic_series[t-1]
                
                # t期收益率（要预测的目标）
                target_returns = stock_data.returns[t, :].copy()
                
                # 标准化收益率
                target_mean = target_returns.mean()
                target_std = target_returns.std()
                if target_std < 1e-8:
                    target_normalized = np.zeros_like(target_returns)
                else:
                    target_normalized = (target_returns - target_mean) / target_std
                
                # 方法1：直接构造相关序列
                # 因子得分 = IC * 标准化收益 + sqrt(1-IC^2) * 独立噪声
                # 但需要确保噪声与收益独立
                
                # 生成独立标准正态噪声
                independent_noise = np.random.randn(N)
                
                # 使噪声与目标收益正交（相关系数为0）
                # 通过Gram-Schmidt正交化
                if np.abs(current_ic) < 0.99:  # 避免IC接近1时的数值问题
                    # 计算噪声在目标上的投影
                    projection = np.dot(independent_noise, target_normalized) / np.dot(target_normalized, target_normalized)
                    orthogonal_noise = independent_noise - projection * target_normalized
                    
                    # 标准化正交噪声
                    noise_std = orthogonal_noise.std()
                    if noise_std < 1e-8:
                        noise_normalized = np.zeros_like(orthogonal_noise)
                    else:
                        noise_normalized = orthogonal_noise / noise_std
                    
                    # 构造因子得分
                    # 确保：corr(得分, 收益) = current_ic
                    # 且得分方差为1
                    factor_raw = current_ic * target_normalized + np.sqrt(1 - current_ic**2) * noise_normalized
                    
                    # 验证相关性
                    actual_corr = np.corrcoef(factor_raw, target_normalized)[0, 1]
                    corr_error = abs(actual_corr - current_ic)
                    
                    if corr_error > 0.1:
                        print(f"警告: 因子{k}, t={t}, IC误差={corr_error:.3f}")
                    
                    # 存储因子得分
                    factor_scores[t, k, :] = factor_raw
                else:
                    # IC接近1，直接使用标准化收益
                    factor_scores[t, k, :] = target_normalized
        
        # 创建FactorData对象
        factor_data = FactorData(
            factor_ids=factor_ids,
            dates=dates,
            stock_ids=stock_ids,
            factor_scores=factor_scores,
            ic_means=ic_means
        )
        
        print(f"因子数据生成完成")
        return factor_data
    
    def calculate_factor_performance(
        self,
        factor_data: FactorData,
        stock_data: StockData
    ) -> List[Dict]:
        """计算因子表现（得分加权多空）"""
        print("计算因子表现...")
        
        T, K, N = factor_data.factor_scores.shape
        results = []
        
        for k in range(K):
            factor_id = factor_data.factor_ids[k]
            
            ic_values = []
            ls_returns = []
            
            for t in range(1, T):
                # t-1期因子得分
                scores = factor_data.factor_scores[t-1, k, :].copy()
                # t期收益率
                returns = stock_data.returns[t, :].copy()
                
                # 有效数据
                valid_mask = ~(np.isnan(scores) | np.isnan(returns))
                if np.sum(valid_mask) < 10:
                    continue
                    
                scores_valid = scores[valid_mask]
                returns_valid = returns[valid_mask]
                
                # 计算IC
                ic = np.corrcoef(scores_valid, returns_valid)[0, 1]
                if not np.isnan(ic):
                    ic_values.append(ic)
                
                # 计算多空收益（得分加权）
                # 多头：得分正的部分，权重正比于得分
                # 空头：得分负的部分，权重正比于得分的绝对值（负权重）
                
                # 标准化得分作为权重基础
                scores_std = scores_valid.std()
                if scores_std < 1e-8:
                    continue
                    
                scores_normalized = scores_valid / scores_std
                
                # 多头部分（得分>0）
                long_mask = scores_normalized > 0
                if np.sum(long_mask) > 0:
                    long_scores = scores_normalized[long_mask]
                    long_returns = returns_valid[long_mask]
                    
                    # 权重：正比于得分，和为1
                    long_weights = long_scores / long_scores.sum()
                    long_return = np.sum(long_weights * long_returns)
                else:
                    long_return = 0
                
                # 空头部分（得分<0）
                short_mask = scores_normalized < 0
                if np.sum(short_mask) > 0:
                    short_scores = scores_normalized[short_mask]
                    short_returns = returns_valid[short_mask]
                    
                    # 权重：正比于得分绝对值，和为-1
                    # 注意：short_scores是负的，取绝对值
                    short_weights_abs = np.abs(short_scores) / np.abs(short_scores).sum()
                    short_weights = -short_weights_abs  # 负权重
                    short_return = np.sum(short_weights * short_returns)
                else:
                    short_return = 0
                
                # 多空组合收益
                ls_return = long_return + short_return  # short_return已经是负权重计算
                ls_returns.append(ls_return)
            
            if len(ic_values) > 10:
                ic_array = np.array(ic_values)
                ic_mean = ic_array.mean()
                ic_std = ic_array.std()
                icir = ic_mean / (ic_std + 1e-8)
                
                ls_array = np.array(ls_returns)
                ls_mean = ls_array.mean() * 252
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
        
        # 排序
        results.sort(key=lambda x: x['icir'], reverse=True)
        
        print(f"计算完成: {len(results)} 个因子")
        if results:
            print(f"最佳因子: {results[0]['factor_id']}, ICIR={results[0]['icir']:.3f}")
        
        return results
    
    def _generate_dates(self, start_date: str, num_days: int) -> np.ndarray:
        """生成日期序列"""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        dates = [start + timedelta(days=i) for i in range(num_days)]
        return np.array([d.strftime("%Y-%m-%d") for d in dates])
    
    def _generate_returns(
        self,
        num_stocks: int,
        num_days: int,
        return_mean: float,
        return_std: float,
        correlation_level: float
    ) -> np.ndarray:
        """生成股票收益率"""
        # 简单生成，先不考虑复杂相关性
        returns = np.random.randn(num_days, num_stocks) * return_std + return_mean
        return returns
    
    def verify_ic_control(
        self,
        factor_data: FactorData,
        stock_data: StockData,
        num_factors_to_check: int = 5
    ) -> Dict:
        """验证IC控制精度"""
        print(f"\n验证IC控制精度（检查前{num_factors_to_check}个因子）:")
        print("-" * 60)
        
        T, K, N = factor_data.factor_scores.shape
        errors = []
        
        for k in range(min(num_factors_to_check, K)):
            factor_id = factor_data.factor_ids[k]
            target_ic = factor_data.ic_means[k]
            
            actual_ics = []
            for t in range(1, T):
                scores = factor_data.factor_scores[t-1, k, :]
                returns = stock_data.returns[t, :]
                
                valid_mask = ~(np.isnan(scores) | np.isnan(returns))
                if np.sum(valid_mask) > 10:
                    ic = np.corrcoef(scores[valid_mask], returns[valid_mask])[0, 1]
                    if not np.isnan(ic):
                        actual_ics.append(ic)
            
            if actual_ics:
                actual_ic_mean = np.mean(actual_ics)
                error = abs(actual_ic_mean - target_ic)
                errors.append(error)
                
                print(f"{factor_id}: 目标IC={target_ic:.4f}, 实际IC={actual_ic_mean:.4f}, 误差={error:.4f}")
        
        if errors:
            avg_error = np.mean(errors)
            max_error = np.max(errors)
            print(f"\n平均IC误差: {avg_error:.4f}")
            print(f"最大IC误差: {max_error:.4f}")
            
            return {
                'avg_error': avg_error,
                'max_error': max_error,
                'errors': errors
            }
        
        return {}


def test_simulator_v3():
    """测试V3模拟器"""
    print("=" * 60)
    print("股票数据模拟器 V3 - 精确IC控制测试")
    print("=" * 60)
    
    simulator = StockDataSimulatorV3(seed=42)
    
    # 1. 模拟股票数据
    print("\n1. 模拟股票收益率...")
    stock_data = simulator.simulate_stock_returns(
        num_stocks=50,
        num_days=200,  # 增加天数提高统计稳定性
        start_date="2023-01-01"
    )
    
    # 2. 模拟因子数据
    print("\n2. 模拟因子数据...")
    factor_data = simulator.simulate_factor_data(
        stock_data=stock_data,
        num_factors=20,
        ic_mean_range=(0.03, 0.08),  # 提高IC均值范围
        ic_std_fixed=0.02  # 减小IC波动
    )
    
    # 3. 验证IC控制
    print("\n3. 验证IC控制精度...")
    ic_verification = simulator.verify_ic_control(factor_data, stock_data, 5)
    
    # 4. 计算表现
    print("\n4. 计算因子表现...")
    performance = simulator.calculate_factor_performance(factor_data, stock_data)
    
    # 5. 显示结果
    if performance:
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
        ic_means = [r['ic_mean'] for r in performance]
        
        print(f"ICIR范围: {min(icirs):.3f} 到 {max(icirs):.3f}")
        print(f"平均ICIR: {np.mean(icirs):.3f}")
        print(f"正ICIR比例: {sum(1 for x in icirs if x > 0)/len(icirs):.1%}")
        
        # IC与ICIR关系
        if len(ic_means) > 1:
            corr = np.corrcoef(ic_means, icirs)[0, 1]
            print(f"IC均值与ICIR相关性: {corr:.3f}")
    
    return stock_data, factor_data, performance, ic_verification


if __name__ == "__main__":
    print("股票数据模拟器 V3 - 精确IC控制")
    print("=" * 60)
    
    stock_data, factor_data, performance, ic_verification = test_simulator_v3()
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)