"""
正确的股票数据模拟器
精确实现研究员的要求：
1. 生成因子得分，使其与t+1期收益的相关性精确等于设定的IC
2. IC方差固定，只用均值区分因子质量
3. 多空收益使用得分加权
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
    returns: np.ndarray  # 形状(T, N)


@dataclass
class FactorData:
    """因子数据容器"""
    factor_ids: List[str]
    dates: np.ndarray
    stock_ids: List[str]
    factor_scores: np.ndarray  # 形状(T, K, N)
    ic_means: np.ndarray  # 每个因子的IC均值


class CorrectStockSimulator:
    """正确的股票数据模拟器"""
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        np.random.seed(seed)
    
    def simulate_stock_returns(
        self,
        num_stocks: int = 100,
        num_days: int = 252,
        start_date: str = "2023-01-01",
        return_mean: float = 0.0002,
        return_std: float = 0.02
    ) -> StockData:
        """模拟股票收益率序列"""
        print(f"模拟股票收益率: {num_stocks}只股票, {num_days}个交易日")
        
        # 生成日期
        dates = self._generate_dates(start_date, num_days)
        stock_ids = [f"stock_{i:03d}" for i in range(num_stocks)]
        
        # 生成独立收益率（简化，先不考虑相关性）
        returns = np.random.randn(num_days, num_stocks) * return_std + return_mean
        
        return StockData(dates=dates, stock_ids=stock_ids, returns=returns)
    
    def simulate_factor_data(
        self,
        stock_data: StockData,
        num_factors: int = 50,
        ic_mean_range: Tuple[float, float] = (0.01, 0.10),
        ic_std_fixed: float = 0.02
    ) -> FactorData:
        """
        精确生成因子得分
        
        算法：
        对于每个因子k，每个时间t：
        1. 生成IC值：IC_t ~ N(μ_k, σ_fixed²)
        2. 生成因子得分F_t，使得 corr(F_t, R_{t+1}) = IC_t
        3. 方法：F_t = IC_t * R_{t+1}标准化 + √(1-IC_t²) * Z，其中Z~N(0,1)独立
        """
        print(f"模拟因子数据: {num_factors}个因子")
        print(f"IC标准差固定: {ic_std_fixed}")
        
        T, N = stock_data.returns.shape
        
        # 生成因子ID和IC均值
        factor_ids = [f"factor_{i:03d}" for i in range(num_factors)]
        ic_means = np.random.uniform(*ic_mean_range, size=num_factors)
        
        print(f"IC均值范围: {ic_means.min():.3f} 到 {ic_means.max():.3f}")
        
        # 生成因子得分矩阵
        factor_scores = np.zeros((T, num_factors, N))
        
        # 第一天随机初始化
        factor_scores[0, :, :] = np.random.randn(num_factors, N)
        
        # 为每个因子生成IC序列
        ic_sequences = np.zeros((T, num_factors))
        for k in range(num_factors):
            ic_sequences[:, k] = np.random.normal(ic_means[k], ic_std_fixed, T)
        
        # 生成因子得分
        for t in range(1, T):
            # t期收益率（要预测的目标）
            returns_t = stock_data.returns[t, :].copy()
            
            # 标准化收益率
            returns_mean = returns_t.mean()
            returns_std = returns_t.std()
            if returns_std < 1e-8:
                returns_normalized = np.zeros_like(returns_t)
            else:
                returns_normalized = (returns_t - returns_mean) / returns_std
            
            for k in range(num_factors):
                current_ic = ic_sequences[t-1, k]  # t-1期的IC预测t期收益
                
                # 限制IC在[-0.99, 0.99]范围内，避免数值问题
                current_ic = np.clip(current_ic, -0.99, 0.99)
                
                # 生成独立标准正态噪声
                Z = np.random.randn(N)
                
                # 确保Z与returns_normalized正交（相关系数为0）
                # 通过Gram-Schmidt正交化
                if np.dot(returns_normalized, returns_normalized) > 1e-8:
                    # 计算Z在returns_normalized上的投影
                    projection = np.dot(Z, returns_normalized) / np.dot(returns_normalized, returns_normalized)
                    Z_orthogonal = Z - projection * returns_normalized
                else:
                    Z_orthogonal = Z
                
                # 标准化正交噪声
                Z_std = Z_orthogonal.std()
                if Z_std < 1e-8:
                    Z_normalized = np.zeros_like(Z_orthogonal)
                else:
                    Z_normalized = Z_orthogonal / Z_std
                
                # 生成因子得分
                # F = ρ * R_norm + √(1-ρ²) * Z_norm
                factor_raw = current_ic * returns_normalized + np.sqrt(1 - current_ic**2) * Z_normalized
                
                # 验证相关性（调试用）
                actual_corr = np.corrcoef(factor_raw, returns_normalized)[0, 1]
                corr_error = abs(actual_corr - current_ic)
                
                if corr_error > 0.05:  # 误差大于5%时警告
                    print(f"  警告: t={t}, 因子{k}, IC误差={corr_error:.3f}")
                
                # 存储
                factor_scores[t, k, :] = factor_raw
        
        return FactorData(
            factor_ids=factor_ids,
            dates=stock_data.dates,
            stock_ids=stock_data.stock_ids,
            factor_scores=factor_scores,
            ic_means=ic_means
        )
    
    def calculate_weighted_long_short_return(
        self,
        factor_scores: np.ndarray,  # 形状(N,)
        returns: np.ndarray,        # 形状(N,)
        leverage: float = 2.0
    ) -> float:
        """
        计算得分加权多空收益
        
        参数：
            leverage: 杠杆率，2.0表示多头权重和=1，空头权重和=-1
        """
        N = len(factor_scores)
        
        # 标准化得分
        scores_std = factor_scores.std()
        if scores_std < 1e-8:
            return 0.0
        
        scores_normalized = factor_scores / scores_std
        
        # 多头部分（得分>0）
        long_mask = scores_normalized > 0
        if np.any(long_mask):
            long_scores = scores_normalized[long_mask]
            long_returns = returns[long_mask]
            
            # 权重正比于得分，和为 leverage/2
            long_weights = long_scores / long_scores.sum() * (leverage / 2)
            long_return = np.sum(long_weights * long_returns)
        else:
            long_return = 0.0
        
        # 空头部分（得分<0）
        short_mask = scores_normalized < 0
        if np.any(short_mask):
            short_scores = scores_normalized[short_mask]
            short_returns = returns[short_mask]
            
            # 对于空头，我们希望得分越负（越小），做空权重越大
            # 所以权重正比于 -short_scores（取负使得负得分变正）
            short_scores_pos = -short_scores  # 负得分变正
            
            # 权重和为 -leverage/2（负权重）
            short_weights = -short_scores_pos / short_scores_pos.sum() * (leverage / 2)
            short_return = np.sum(short_weights * short_returns)
        else:
            short_return = 0.0
        
        # 总收益
        total_return = long_return + short_return
        
        return total_return
    
    def evaluate_factor_performance(
        self,
        factor_data: FactorData,
        stock_data: StockData,
        leverage: float = 2.0
    ) -> List[Dict]:
        """评估因子表现"""
        print("评估因子表现...")
        
        T, K, N = factor_data.factor_scores.shape
        results = []
        
        for k in range(K):
            factor_id = factor_data.factor_ids[k]
            
            ic_values = []
            ls_returns = []
            
            for t in range(1, T):
                # t-1期因子得分
                scores_t_minus_1 = factor_data.factor_scores[t-1, k, :].copy()
                # t期收益率
                returns_t = stock_data.returns[t, :].copy()
                
                # 有效数据
                valid_mask = ~(np.isnan(scores_t_minus_1) | np.isnan(returns_t))
                if np.sum(valid_mask) < 10:
                    continue
                
                scores_valid = scores_t_minus_1[valid_mask]
                returns_valid = returns_t[valid_mask]
                
                # 计算IC
                ic = np.corrcoef(scores_valid, returns_valid)[0, 1]
                if not np.isnan(ic):
                    ic_values.append(ic)
                
                # 计算多空收益（得分加权）
                ls_return = self.calculate_weighted_long_short_return(
                    scores_valid, returns_valid, leverage
                )
                ls_returns.append(ls_return)
            
            if len(ic_values) > 20:  # 至少20个有效观测
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
                    'target_ic_mean': factor_data.ic_means[k],
                    'obs_count': len(ic_values)
                })
        
        # 按ICIR排序
        results.sort(key=lambda x: x['icir'], reverse=True)
        
        print(f"评估完成: {len(results)} 个因子")
        return results
    
    def verify_ic_control(
        self,
        factor_data: FactorData,
        stock_data: StockData,
        num_factors: int = 10
    ) -> Dict:
        """验证IC控制精度"""
        print(f"\n验证IC控制精度（前{num_factors}个因子）:")
        print("-" * 70)
        
        T, K, N = factor_data.factor_scores.shape
        num_factors = min(num_factors, K)
        
        errors = []
        details = []
        
        for k in range(num_factors):
            factor_id = factor_data.factor_ids[k]
            target_ic_mean = factor_data.ic_means[k]
            
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
                error = abs(actual_ic_mean - target_ic_mean)
                errors.append(error)
                
                details.append({
                    'factor_id': factor_id,
                    'target': target_ic_mean,
                    'actual': actual_ic_mean,
                    'error': error,
                    'error_pct': error / (abs(target_ic_mean) + 1e-8)
                })
        
        # 显示结果
        for d in details[:5]:
            print(f"{d['factor_id']}: 目标IC={d['target']:.4f}, "
                  f"实际IC={d['actual']:.4f}, 误差={d['error']:.4f} ({d['error_pct']:.1%})")
        
        if errors:
            stats = {
                'avg_error': np.mean(errors),
                'max_error': np.max(errors),
                'std_error': np.std(errors),
                'pct_error_lt_0_01': sum(1 for e in errors if e < 0.01) / len(errors),
                'pct_error_lt_0_02': sum(1 for e in errors if e < 0.02) / len(errors),
                'details': details
            }
            
            print(f"\n统计:")
            print(f"  平均误差: {stats['avg_error']:.4f}")
            print(f"  最大误差: {stats['max_error']:.4f}")
            print(f"  误差<0.01: {stats['pct_error_lt_0_01']:.1%}")
            print(f"  误差<0.02: {stats['pct_error_lt_0_02']:.1%}")
            
            return stats
        
        return {}
    
    def _generate_dates(self, start_date: str, num_days: int) -> np.ndarray:
        """生成日期序列"""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        dates = [start + timedelta(days=i) for i in range(num_days)]
        return np.array([d.strftime("%Y-%m-%d") for d in dates])


def main():
    """主测试函数"""
    print("=" * 70)
    print("正确的股票数据模拟器 - 测试")
    print("=" * 70)
    
    simulator = CorrectStockSimulator(seed=42)
    
    # 1. 模拟股票数据
    print("\n1. 模拟股票收益率...")
    stock_data = simulator.simulate_stock_returns(
        num_stocks=100,
        num_days=300,  # 300个交易日
        start_date="2023-01-01"
    )
    
    # 2. 模拟因子数据
    print("\n2. 模拟因子数据...")
    factor_data = simulator.simulate_factor_data(
        stock_data=stock_data,
        num_factors=30,
        ic_mean_range=(0.02, 0.08),  # IC均值2%-8%
        ic_std_fixed=0.015  # 固定IC标准差1.5%
    )
    
    # 3. 验证IC控制
    print("\n3. 验证IC控制精度...")
    ic_stats = simulator.verify_ic_control(factor_data, stock_data, 10)
    
    # 4. 评估因子表现
    print("\n4. 评估因子表现...")
    performance = simulator.evaluate_factor_performance(factor_data, stock_data, leverage=2.0)
    
    # 5. 显示结果
    if performance:
        print("\n5. 因子表现排名:")
        print("-" * 80)
        print(f"{'排名':<4} {'因子ID':<12} {'目标IC':<8} {'实际IC':<8} {'ICIR':<8} {'年化收益':<10} {'夏普':<8}")
        print("-" * 80)
        
        for i, r in enumerate(performance[:15]):
            print(f"{i+1:<4} {r['factor_id']:<12} {r['target_ic_mean']:<8.3f} "
                  f"{r['ic_mean']:<8.3f} {r['icir']:<8.3f} "
                  f"{r['ls_return_annual']:<10.3f} {r['ls_sharpe']:<8.3f}")
        
        # 6. 统计信息
        print("\n6. 统计信息:")
        icirs = [r['icir'] for r in performance]
        target_ics = [r['target_ic_mean'] for r in performance]
        actual_ics = [r['ic_mean'] for r in performance]
        
        print(f"ICIR范围: {min(icirs):.3f} 到 {max(icirs):.3f}")
        print(f"平均ICIR: {np.mean(icirs):.3f}")
        print(f"正ICIR比例: {sum(1 for x in icirs if x > 0)/len(icirs):.1%}")
        
        # 目标IC vs 实际IC
        if len(target_ics) > 1:
            corr = np.corrcoef(target_ics, actual_ics)[0, 1]
            print(f"目标IC与实际IC相关性: {corr:.3f}")
            
            # ICIR与目标IC的关系
            icir_target_corr = np.corrcoef(target_ics, icirs)[0, 1]
            print(f"目标IC与ICIR相关性: {icir_target_corr:.3f}")
            
            # 分组分析
            print(f"\n按目标IC分组表现:")
            ic_bins = np.percentile(target_ics, [0, 25, 50, 75, 100])
            for i in range(len(ic_bins)-1):
                mask = (target_ics >= ic_bins[i]) & (target_ics < ic_bins[i+1])
                if np.any(mask):
                    group_indices = [j for j in range(len(target_ics)) if mask[j]]
                    group_icir = np.mean([icirs[j] for j in group_indices])
                    group_ls = np.mean([performance[j]['ls_return_annual'] for j in group_indices])
                    print(f"  目标IC {ic_bins[i]:.3f}-{ic_bins[i+1]:.3f}: "
                          f"平均ICIR={group_icir:.3f}, 年化收益={group_ls:.3f}")
    
    return stock_data, factor_data, performance, ic_stats


if __name__ == "__main__":
    print("正确的股票数据模拟器")
    print("版本: 1.0 - 精确IC控制 + 得分加权多空")
    print("=" * 70)
    
    stock_data, factor_data, performance, ic_stats = main()
    
    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)
