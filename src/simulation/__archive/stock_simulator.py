"""
正确的股票数据模拟器
实现研究员的所有要求
"""

import numpy as np
from typing import List, Tuple


class ProperStockSimulator:
    """正确的股票数据模拟器"""
    
    def __init__(self, seed: int = 42):
        np.random.seed(seed)
    
    def generate_correlated_series(
        self,
        reference_series: np.ndarray,  # 参考序列（未来收益）
        target_correlation: float      # 目标相关系数
    ) -> np.ndarray:
        """
        生成与参考序列有目标相关性的序列
        
        数学原理：
        设 R = 标准化后的参考序列
        设 Z ~ N(0,1) 且与R独立
        设 ρ = 目标相关系数
        
        则生成：X = ρR + √(1-ρ²)Z
        满足：corr(X, R) = ρ
        """
        N = len(reference_series)
        
        # 1. 标准化参考序列
        R = reference_series.copy()
        R_mean = R.mean()
        R_std = R.std()
        if R_std < 1e-8:
            R_norm = np.zeros(N)
        else:
            R_norm = (R - R_mean) / R_std
        
        # 2. 生成独立标准正态变量
        Z = np.random.randn(N)
        
        # 3. 使Z与R_norm正交（相关系数=0）
        # 计算Z在R_norm上的投影
        if np.dot(R_norm, R_norm) > 1e-8:
            projection_coef = np.dot(Z, R_norm) / np.dot(R_norm, R_norm)
            Z_ortho = Z - projection_coef * R_norm
        else:
            Z_ortho = Z
        
        # 4. 标准化正交部分
        Z_ortho_std = Z_ortho.std()
        if Z_ortho_std < 1e-8:
            Z_norm = np.zeros_like(Z_ortho)
        else:
            Z_norm = Z_ortho / Z_ortho_std
        
        # 5. 生成目标序列
        rho = np.clip(target_correlation, -0.99, 0.99)
        X = rho * R_norm + np.sqrt(1 - rho**2) * Z_norm
        
        return X
    
    def calculate_weighted_long_short_return(
        self,
        factor_scores: np.ndarray,
        future_returns: np.ndarray,
        leverage: float = 2.0
    ) -> float:
        """
        计算得分加权多空收益
        
        参数：
            leverage: 杠杆率，2.0表示多头权重和=1，空头权重和=-1
        """
        N = len(factor_scores)
        
        # 1. 标准化因子得分
        scores_std = factor_scores.std()
        if scores_std < 1e-8:
            return 0.0
        scores_norm = factor_scores / scores_std
        
        total_return = 0.0
        
        # 2. 多头部分（得分>0）
        long_mask = scores_norm > 0
        if np.any(long_mask):
            long_scores = scores_norm[long_mask]
            long_returns = future_returns[long_mask]
            
            # 权重正比于得分，和为 leverage/2
            long_weights = long_scores / long_scores.sum() * (leverage / 2)
            total_return += np.sum(long_weights * long_returns)
        
        # 3. 空头部分（得分<0）
        short_mask = scores_norm < 0
        if np.any(short_mask):
            short_scores = scores_norm[short_mask]
            short_returns = future_returns[short_mask]
            
            # 对于空头，得分越负，做空权重越大
            # 所以用 -short_scores（负得分变正）计算权重
            short_scores_pos = -short_scores
            
            # 权重和为 -leverage/2
            short_weights = -short_scores_pos / short_scores_pos.sum() * (leverage / 2)
            total_return += np.sum(short_weights * short_returns)
        
        return total_return
    
    def simulate(
        self,
        num_stocks: int = 100,
        num_days: int = 252,
        num_factors: int = 30,
        ic_mean_range: Tuple[float, float] = (0.02, 0.06),
        ic_std_fixed: float = 0.01
    ) -> dict:
        """
        运行完整模拟
        
        时间对齐：
        - t期因子得分 F_t
        - t+1期收益 R_{t+1}
        - 要求：corr(F_t, R_{t+1}) = IC_t
        """
        print("=" * 70)
        print("正确的股票数据模拟器")
        print("=" * 70)
        print(f"参数: {num_stocks}股票, {num_days}天, {num_factors}因子")
        print(f"IC均值范围: {ic_mean_range[0]:.3f}-{ic_mean_range[1]:.3f}")
        print(f"IC标准差固定: {ic_std_fixed}")
        
        # 1. 生成股票收益率
        # 日收益：均值0.02%，波动2%
        stock_returns = np.random.randn(num_days, num_stocks) * 0.02 + 0.0002
        
        # 2. 生成因子IC参数
        ic_means = np.random.uniform(*ic_mean_range, size=num_factors)
        factor_ids = [f"F{i:03d}" for i in range(num_factors)]
        
        # 3. 为每个因子生成IC序列
        ic_sequences = np.zeros((num_days, num_factors))
        for k in range(num_factors):
            ic_sequences[:, k] = np.random.normal(ic_means[k], ic_std_fixed, num_days)
        
        # 4. 生成因子得分
        factor_scores = np.zeros((num_days, num_factors, num_stocks))
        
        # 第一天：随机初始化
        factor_scores[0, :, :] = np.random.randn(num_factors, num_stocks)
        
        # 后续天数：t期因子预测t+1期收益
        for t in range(num_days - 1):
            # t+1期收益（要预测的目标）
            returns_next = stock_returns[t + 1, :]
            
            for k in range(num_factors):
                # t期的IC值
                current_ic = ic_sequences[t, k]
                
                # 生成t期因子得分，使其与t+1期收益的相关性 = current_ic
                factor_scores[t, k, :] = self.generate_correlated_series(
                    returns_next, current_ic
                )
        
        # 最后一天没有未来收益，用随机值
        factor_scores[-1, :, :] = np.random.randn(num_factors, num_stocks)
        
        # 5. 评估因子表现
        print("\n评估因子表现...")
        performance = []
        
        for k in range(num_factors):
            factor_id = factor_ids[k]
            
            ic_values = []
            ls_returns = []
            
            # 评估期：从第0天到第T-2天（因为最后一天没有未来收益）
            for t in range(num_days - 1):
                # t期因子得分
                scores_t = factor_scores[t, k, :]
                # t+1期实际收益
                returns_tplus1 = stock_returns[t + 1, :]
                
                # 计算IC
                ic = np.corrcoef(scores_t, returns_tplus1)[0, 1]
                if not np.isnan(ic):
                    ic_values.append(ic)
                
                # 计算多空收益
                ls_return = self.calculate_weighted_long_short_return(
                    scores_t, returns_tplus1, leverage=2.0
                )
                ls_returns.append(ls_return)
            
            if len(ic_values) > 20:
                ic_array = np.array(ic_values)
                ic_mean = ic_array.mean()
                ic_std = ic_array.std()
                icir = ic_mean / (ic_std + 1e-8)
                
                ls_array = np.array(ls_returns)
                ls_mean = ls_array.mean() * 252  # 年化
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
        
        # 按ICIR排序
        performance.sort(key=lambda x: x['icir'], reverse=True)
        
        return {
            'stock_returns': stock_returns,
            'factor_scores': factor_scores,
            'ic_means': ic_means,
            'ic_sequences': ic_sequences,
            'performance': performance
        }
    
    def print_results(self, results: dict):
        """打印结果"""
        performance = results['performance']
        
        if not performance:
            print("没有有效的因子表现数据")
            return
        
        print(f"\n有效因子数: {len(performance)}")
        
        # 显示前10名
        print("\n前10名因子表现:")
        print("-" * 85)
        print(f"{'排名':<4} {'因子ID':<8} {'目标IC':<8} {'实际IC':<8} {'IC误差':<8} {'ICIR':<8} {'年化收益':<10} {'夏普':<8}")
        print("-" * 85)
        
        for i, r in enumerate(performance[:10]):
            print(f"{i+1:<4} {r['factor_id']:<8} {r['target_ic_mean']:<8.3f} "
                  f"{r['actual_ic_mean']:<8.3f} {r['ic_error']:<8.3f} "
                  f"{r['icir']:<8.3f} {r['ls_return_annual']:<10.3f} "
                  f"{r['ls_sharpe']:<8.3f}")
        
        # 统计信息
        print("\n=== 统计信息 ===")
        
        # IC控制精度
        ic_errors = [r['ic_error'] for r in performance]
        print(f"\n1. IC控制精度:")
        print(f"   平均IC误差: {np.mean(ic_errors):.4f}")
        print(f"   最大IC误差: {np.max(ic_errors):.4f}")
        print(f"   误差<0.01: {sum(1 for e in ic_errors if e < 0.01)/len(ic_errors):.1%}")
        print(f"   误差<0.02: {sum(1 for e in ic_errors if e < 0.02)/len(ic_errors):.1%}")
        
        # 因子表现
        icirs = [r['icir'] for r in performance]
        target_ics = [r['target_ic_mean'] for r in performance]
        actual_ics = [r['actual_ic_mean'] for r in performance]
        
        print(f"\n2. 因子表现:")
        print(f"   ICIR范围: {min(icirs):.3f} 到 {max(icirs):.3f}")
        print(f"   平均ICIR: {np.mean(icirs):.3f}")
        print(f"   正ICIR比例: {sum(1 for x in icirs if x > 0)/len(icirs):.1%}")
        
        # 相关性分析
        if len(target_ics) > 1:
            # 目标IC vs 实际IC
            corr_target_actual = np.corrcoef(target_ics, actual_ics)[0, 1]
            print(f"\n3. 相关性分析:")
            print(f"   目标IC vs 实际IC: {corr_target_actual:.3f}")
            
            # 目标IC vs ICIR
            corr_target_icir = np.corrcoef(target_ics, icirs)[0, 1]
            print(f"   目标IC vs ICIR: {corr_target_icir:.3f}")
            
            # 理论ICIR vs 实际ICIR
            # 理论ICIR = μ / σ_fixed
            theoretical_icirs = [t / 0.01 for t in target_ics]  # σ_fixed = 0.01
            corr_theory_actual = np.corrcoef(theoretical_icirs, icirs)[0, 1]
            print(f"   理论ICIR(μ/σ) vs 实际ICIR: {corr_theory_actual:.3f}")
        
        # 验证ICIR公式
        print(f"\n4. ICIR验证:")
        print(f"   理论ICIR范围: {min(theoretical_icirs):.3f} 到 {max(theoretical_icirs):.3f}")
        print(f"   实际ICIR范围: {min(icirs):.3f} 到 {max(icirs):.3f}")


def test_core_logic():
    """测试核心逻辑"""
    print("\n" + "=" * 70)
    print("测试核心逻辑")
    print("=" * 70)
    
    np.random.seed(42)
    
    # 测试相关性生成
    print("\n1. 测试相关性生成精度:")
    N = 10000  # 大样本提高精度
    
    # 生成参考序列
    R = np.random.randn(N)
    R_norm = (R - R.mean()) / R.std()
    
    test_rhos = [0.02, 0.04, 0.06, 0.08, 0.10]
    
    for rho_target in test_rhos:
        # 生成独立噪声
        Z = np.random.randn(N)
        
        # 使Z与R_norm正交
        proj = np.dot(Z, R_norm) / np.dot(R_norm, R_norm)
        Z_ortho = Z - proj * R_norm
        Z_norm = Z_ortho / Z_ortho.std()
        
        # 生成相关序列
        X = rho_target * R_norm + np.sqrt(1 - rho_target**2) * Z_norm
        
        # 计算实际相关性
        rho_actual = np.corrcoef(X, R_norm)[0, 1]
        error = abs(rho_actual - rho_target)
        
        print(f"   目标ρ={rho_target:.3f}, 实际ρ={rho_actual:.3f}, 误差={error:.4f} ({error/rho_target:.1%})")
    
    # 测试权重计算
    print("\n2. 测试得分加权权重:")
    N = 100
    scores = np.random.randn(N)
    scores_norm = scores / scores.std()
    
    # 多头权重
    long_mask = scores_norm > 0
    if np.any(long_mask):
        long_scores = scores_norm[long_mask]
        long_weights = long_scores / long_scores.sum()
        print(f"   多头股票数: {np.sum(long_mask)}")
        print(f"   多头权重和: {np.sum(long_weights):.6f} (应为1.000000)")
    
    # 空头权重
    short_mask = scores_norm < 0
    if np.any(short_mask):
        short_scores = scores_norm[short_mask]
        short_scores_pos = -short_scores
        short_weights = -short_scores_pos / short_scores_pos.sum()
        print(f"   空头股票数: {np.sum(short_mask)}")
        print(f"   空头权重和: {np.sum(short_weights):.6f} (应为-1.000000)")


def main():
    """主函数"""
    # 先测试核心逻辑
    test_core_logic()
    
    print("\n" + "=" * 70)
    print("运行完整模拟")
    print("=" * 70)
    
    simulator = ProperStockSimulator(seed=42)
    
    # 运行模拟
    results = simulator.simulate(
        num_stocks=100,
        num_days=252,
        num_factors=30,
        ic_mean_range=(0.02, 0.06),
        ic_std_fixed=0.01
    )
    
    # 打印结果
    simulator.print_results(results)
    
    print("\n" + "=" * 70)
    print("模拟完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()