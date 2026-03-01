"""
简化但正确的股票数据模拟器
实现研究员的所有要求：
1. 生成因子得分，使其与t+1期收益的相关性 = 设定的IC
2. IC方差固定，只用均值区分因子质量
3. 多空收益使用得分加权，杠杆2倍
"""

import numpy as np
from typing import List, Tuple


class SimpleStockSimulator:
    """简化但正确的股票数据模拟器"""
    
    def __init__(self, seed: int = 42):
        np.random.seed(seed)
    
    def generate_factor_scores(
        self,
        returns_next_period: np.ndarray,  # 下一期收益率，形状(N,)
        target_ic: float  # 目标IC值
    ) -> np.ndarray:
        """
        生成因子得分，使其与下一期收益的相关性 = target_ic
        
        数学原理：
        设 R = 标准化后的下一期收益
        生成因子得分 F = ρR + √(1-ρ²)Z
        其中 ρ = target_ic，Z~N(0,1)且与R独立
        """
        N = len(returns_next_period)
        
        # 标准化收益
        R_mean = returns_next_period.mean()
        R_std = returns_next_period.std()
        if R_std < 1e-8:
            R_norm = np.zeros(N)
        else:
            R_norm = (returns_next_period - R_mean) / R_std
        
        # 生成独立噪声
        Z = np.random.randn(N)
        
        # 使Z与R_norm正交
        if np.dot(R_norm, R_norm) > 1e-8:
            # 计算Z在R_norm上的投影
            proj = np.dot(Z, R_norm) / np.dot(R_norm, R_norm)
            Z_ortho = Z - proj * R_norm
        else:
            Z_ortho = Z
        
        # 标准化正交噪声
        Z_std = Z_ortho.std()
        if Z_std < 1e-8:
            Z_norm = np.zeros_like(Z_ortho)
        else:
            Z_norm = Z_ortho / Z_std
        
        # 生成因子得分
        rho = np.clip(target_ic, -0.99, 0.99)  # 避免数值问题
        factor_scores = rho * R_norm + np.sqrt(1 - rho**2) * Z_norm
        
        return factor_scores
    
    def calculate_weighted_ls_return(
        self,
        factor_scores: np.ndarray,
        returns: np.ndarray,
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
        
        scores_norm = factor_scores / scores_std
        
        # 多头部分（得分>0）
        long_mask = scores_norm > 0
        if np.any(long_mask):
            long_scores = scores_norm[long_mask]
            long_returns = returns[long_mask]
            long_weights = long_scores / long_scores.sum() * (leverage / 2)
            long_return = np.sum(long_weights * long_returns)
        else:
            long_return = 0.0
        
        # 空头部分（得分<0）
        short_mask = scores_norm < 0
        if np.any(short_mask):
            short_scores = scores_norm[short_mask]
            short_returns = returns[short_mask]
            short_scores_pos = -short_scores  # 负得分变正
            short_weights = -short_scores_pos / short_scores_pos.sum() * (leverage / 2)
            short_return = np.sum(short_weights * short_returns)
        else:
            short_return = 0.0
        
        return long_return + short_return
    
    def simulate(
        self,
        num_stocks: int = 100,
        num_days: int = 252,
        num_factors: int = 50,
        ic_mean_range: Tuple[float, float] = (0.01, 0.10),
        ic_std_fixed: float = 0.02
    ) -> dict:
        """
        完整模拟
        
        返回：
            stock_returns: 股票收益率矩阵，形状(T, N)
            factor_scores: 因子得分矩阵，形状(T, K, N)
            ic_means: 每个因子的IC均值，形状(K,)
            performance: 因子表现列表
        """
        print("开始模拟...")
        print(f"参数: {num_stocks}股票, {num_days}天, {num_factors}因子")
        print(f"IC均值范围: {ic_mean_range}, IC标准差固定: {ic_std_fixed}")
        
        # 1. 生成股票收益率
        stock_returns = np.random.randn(num_days, num_stocks) * 0.02 + 0.0002
        
        # 2. 生成因子IC参数
        ic_means = np.random.uniform(*ic_mean_range, size=num_factors)
        factor_ids = [f"factor_{i:03d}" for i in range(num_factors)]
        
        # 3. 生成因子得分
        factor_scores = np.zeros((num_days, num_factors, num_stocks))
        
        # 第一天随机初始化
        factor_scores[0, :, :] = np.random.randn(num_factors, num_stocks)
        
        # 为每个因子生成IC序列
        ic_sequences = np.zeros((num_days, num_factors))
        for k in range(num_factors):
            ic_sequences[:, k] = np.random.normal(ic_means[k], ic_std_fixed, num_days)
        
        # 生成因子得分
        for t in range(1, num_days):
            returns_next = stock_returns[t, :]  # t期收益（用t-1期因子预测）
            
            for k in range(num_factors):
                current_ic = ic_sequences[t-1, k]
                factor_scores[t, k, :] = self.generate_factor_scores(returns_next, current_ic)
        
        # 4. 评估因子表现
        performance = []
        for k in range(num_factors):
            factor_id = factor_ids[k]
            
            ic_values = []
            ls_returns = []
            
            for t in range(1, num_days):
                # 计算IC
                scores = factor_scores[t-1, k, :]
                returns = stock_returns[t, :]
                ic = np.corrcoef(scores, returns)[0, 1]
                if not np.isnan(ic):
                    ic_values.append(ic)
                
                # 计算多空收益
                ls_return = self.calculate_weighted_ls_return(scores, returns, 2.0)
                ls_returns.append(ls_return)
            
            if len(ic_values) > 20:
                ic_array = np.array(ic_values)
                ic_mean = ic_array.mean()
                ic_std = ic_array.std()
                icir = ic_mean / (ic_std + 1e-8)
                
                ls_array = np.array(ls_returns)
                ls_mean = ls_array.mean() * 252
                ls_std = ls_array.std() * np.sqrt(252)
                sharpe = ls_mean / (ls_std + 1e-8)
                
                performance.append({
                    'factor_id': factor_id,
                    'target_ic_mean': ic_means[k],
                    'actual_ic_mean': ic_mean,
                    'ic_std': ic_std,
                    'icir': icir,
                    'ls_return_annual': ls_mean,
                    'ls_sharpe': sharpe,
                    'ic_error': abs(ic_mean - ic_means[k])
                })
        
        # 排序
        performance.sort(key=lambda x: x['icir'], reverse=True)
        
        print(f"\n模拟完成!")
        print(f"有效因子数: {len(performance)}/{num_factors}")
        
        return {
            'stock_returns': stock_returns,
            'factor_scores': factor_scores,
            'ic_means': ic_means,
            'performance': performance
        }


def main():
    """主函数"""
    print("=" * 70)
    print("简化但正确的股票数据模拟器")
    print("=" * 70)
    
    simulator = SimpleStockSimulator(seed=42)
    
    # 运行模拟
    results = simulator.simulate(
        num_stocks=100,
        num_days=252,
        num_factors=30,
        ic_mean_range=(0.02, 0.08),
        ic_std_fixed=0.015
    )
    
    performance = results['performance']
    
    # 显示结果
    if performance:
        print("\n因子表现排名 (前15名):")
        print("-" * 85)
        print(f"{'排名':<4} {'因子ID':<12} {'目标IC':<8} {'实际IC':<8} {'IC误差':<8} {'ICIR':<8} {'年化收益':<10} {'夏普':<8}")
        print("-" * 85)
        
        for i, r in enumerate(performance[:15]):
            print(f"{i+1:<4} {r['factor_id']:<12} {r['target_ic_mean']:<8.3f} "
                  f"{r['actual_ic_mean']:<8.3f} {r['ic_error']:<8.3f} "
                  f"{r['icir']:<8.3f} {r['ls_return_annual']:<10.3f} "
                  f"{r['ls_sharpe']:<8.3f}")
        
        # 统计信息
        print("\n统计信息:")
        ic_errors = [r['ic_error'] for r in performance]
        icirs = [r['icir'] for r in performance]
        target_ics = [r['target_ic_mean'] for r in performance]
        
        print(f"IC控制精度:")
        print(f"  平均IC误差: {np.mean(ic_errors):.4f}")
        print(f"  最大IC误差: {np.max(ic_errors):.4f}")
        print(f"  IC误差<0.01比例: {sum(1 for e in ic_errors if e < 0.01)/len(ic_errors):.1%}")
        print(f"  IC误差<0.02比例: {sum(1 for e in ic_errors if e < 0.02)/len(ic_errors):.1%}")
        
        print(f"\n因子表现:")
        print(f"  ICIR范围: {min(icirs):.3f} 到 {max(icirs):.3f}")
        print(f"  平均ICIR: {np.mean(icirs):.3f}")
        print(f"  正ICIR比例: {sum(1 for x in icirs if x > 0)/len(icirs):.1%}")
        
        # 目标IC与ICIR的关系
        if len(target_ics) > 1:
            corr = np.corrcoef(target_ics, icirs)[0, 1]
            print(f"  目标IC与ICIR相关性: {corr:.3f}")
            
            # 验证ICIR公式：ICIR ≈ μ/σ
            expected_icirs = [t / 0.015 for t in target_ics]  # σ_fixed = 0.015
            actual_vs_expected_corr = np.corrcoef(icirs, expected_icirs)[0, 1]
            print(f"  实际ICIR vs 理论ICIR(μ/σ)相关性: {actual_vs_expected_corr:.3f}")
    
    print("\n" + "=" * 70)
    print("模拟完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()