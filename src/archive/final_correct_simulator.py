"""
最终正确的股票数据模拟器
修正时间对齐问题
"""

import numpy as np
from typing import List, Tuple


class FinalStockSimulator:
    """最终正确的股票数据模拟器"""
    
    def __init__(self, seed: int = 42):
        np.random.seed(seed)
    
    def generate_factor_scores_correlated(
        self,
        future_returns: np.ndarray,  # 未来一期收益率
        target_correlation: float    # 目标相关性（IC）
    ) -> np.ndarray:
        """
        生成与未来收益有目标相关性的因子得分
        
        正确的时间对齐：
        - t期因子得分 F_t
        - t+1期收益 R_{t+1}
        - 要求：corr(F_t, R_{t+1}) = target_correlation
        """
        N = len(future_returns)
        
        # 标准化未来收益
        R = future_returns.copy()
        R_mean = R.mean()
        R_std = R.std()
        if R_std < 1e-8:
            R_norm = np.zeros(N)
        else:
            R_norm = (R - R_mean) / R_std
        
        # 生成独立标准正态变量
        Z = np.random.randn(N)
        
        # 方法：使用Cholesky分解的思想
        # 想要 corr(F, R) = ρ
        # 可以构造：F = ρ*R_norm + sqrt(1-ρ²)*Z'
        # 其中Z'是与R_norm独立的标准正态
        
        # 使Z与R_norm正交
        if np.dot(R_norm, R_norm) > 1e-8:
            # 计算Z在R_norm上的投影
            proj_coef = np.dot(Z, R_norm) / np.dot(R_norm, R_norm)
            Z_ortho = Z - proj_coef * R_norm
        else:
            Z_ortho = Z
        
        # 标准化正交部分
        Z_ortho_std = Z_ortho.std()
        if Z_ortho_std < 1e-8:
            Z_ortho_norm = np.zeros_like(Z_ortho)
        else:
            Z_ortho_norm = Z_ortho / Z_ortho_std
        
        # 限制相关系数范围
        rho = np.clip(target_correlation, -0.99, 0.99)
        
        # 生成因子得分
        F = rho * R_norm + np.sqrt(1 - rho**2) * Z_ortho_norm
        
        # 验证（调试用）
        actual_corr = np.corrcoef(F, R_norm)[0, 1]
        error = abs(actual_corr - rho)
        
        if error > 0.05:
            print(f"  警告: 目标ρ={rho:.3f}, 实际ρ={actual_corr:.3f}, 误差={error:.3f}")
        
        return F
    
    def calculate_weighted_long_short(
        self,
        factor_scores: np.ndarray,
        future_returns: np.ndarray,
        leverage: float = 2.0
    ) -> float:
        """计算得分加权多空收益"""
        N = len(factor_scores)
        
        # 标准化因子得分
        scores_std = factor_scores.std()
        if scores_std < 1e-8:
            return 0.0
        
        scores_norm = factor_scores / scores_std
        
        total_return = 0.0
        
        # 多头部分（得分>0）
        long_mask = scores_norm > 0
        if np.any(long_mask):
            long_scores = scores_norm[long_mask]
            long_returns = future_returns[long_mask]
            
            # 权重正比于得分，和为 leverage/2
            long_weights = long_scores / long_scores.sum() * (leverage / 2)
            total_return += np.sum(long_weights * long_returns)
        
        # 空头部分（得分<0）
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
    
    def run_simulation(
        self,
        num_stocks: int = 100,
        num_days: int = 252,
        num_factors: int = 30,
        ic_mean_range: Tuple[float, float] = (0.02, 0.06),
        ic_std_fixed: float = 0.01
    ) -> dict:
        """运行完整模拟"""
        print("=" * 70)
        print("最终正确的股票数据模拟器")
        print("=" * 70)
        print(f"参数: {num_stocks}股票, {num_days}天, {num_factors}因子")
        print(f"IC均值: {ic_mean_range[0]:.3f}-{ic_mean_range[1]:.3f}, IC标准差固定: {ic_std_fixed}")
        
        # 1. 生成股票收益率
        # 简单生成，日收益均值0.02%，波动2%
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
        
        # 第一天随机
        factor_scores[0, :, :] = np.random.randn(num_factors, num_stocks)
        
        # 后续天数：用t期因子预测t+1期收益
        for t in range(num_days - 1):  # t从0到T-2
            # t+1期收益（要预测的）
            returns_next = stock_returns[t + 1, :]
            
            for k in range(num_factors):
                # t期的IC值，用于预测t+1期收益
                current_ic = ic_sequences[t, k]
                
                # 生成t期因子得分，使其与t+1期收益的相关性 = current_ic
                factor_scores[t, k, :] = self.generate_factor_scores_correlated(
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
            
            # 评估期：从第1天到第T-1天（因为最后一天没有未来收益）
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
                ls_return = self.calculate_weighted_long_short(
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
        
        # 排序
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
        
        # 分组分析
        print(f"\n4. 按目标IC分组:")
        ic_bins = np.percentile(target_ics, [0, 25, 50, 75, 100])
        for i in range(len(ic_bins)-1):
            low, high = ic_bins[i], ic_bins[i+1]
            mask = (target_ics >= low) & (target_ics < high)
            
            if np.any(mask):
                indices = [j for j in range(len(target_ics)) if mask[j]]
                group_icir = np.mean([icirs[j] for j in indices])
                group_ls = np.mean([performance[j]['ls_return_annual'] for j in indices])
                group_error = np.mean([ic_errors[j] for j in indices])
                
                print(f"   目标IC {low:.3f}-{high:.3f}: "
                      f"平均ICIR={group_icir:.3f}, 年化收益={group_ls:.3f}, IC误差={group_error:.3f}")


def main():
    """主函数"""
    simulator = FinalStockSimulator(seed=42)
    
    # 运行模拟
    results = simulator.run_simulation(
        num_stocks=100,
        num_days=252,
        num_factors=30,
        ic_mean_range=(0.02, 0.06),  # IC均值2%-6%
        ic_std_fixed=0.01  # IC标准差固定1%
    )
    
    # 打印结果
    simulator.print_results(results)
    
    print("\n" + "=" * 70)
    print("模拟完成!")
    print("=" * 70)


if __name__ == "__main__":
    main()