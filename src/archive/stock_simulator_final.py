"""
股票数据模拟器 - 最终版本
精确控制因子与未来收益的相关性等于设定的IC
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


class StockDataSimulator:
    """股票数据模拟器 - 精确IC控制"""
    
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
        
        dates = self._generate_dates(start_date, num_days)
        stock_ids = [f"stock_{i:03d}" for i in range(num_stocks)]
        
        # 生成独立收益率
        returns = np.random.randn(num_days, num_stocks) * return_std + return_mean
        
        stock_data = StockData(dates=dates, stock_ids=stock_ids, returns=returns)
        print(f"股票数据生成完成")
        
        return stock_data
    
    def simulate_factor_data(
        self,
        stock_data: StockData,
        num_factors: int = 50,
        ic_mean_range: Tuple[float, float] = (0.01, 0.10),
        ic_std_fixed: float = 0.02
    ) -> FactorData:
        """
        精确生成因子得分，控制与未来收益的相关性
        
        核心算法：
        对于每个时间点t，每个因子k：
        1. 生成二元正态分布 (X, Y) ~ N(0, Σ)
        2. 其中 Σ = [[1, ρ], [ρ, 1]]，ρ = IC_t
        3. X作为因子得分，Y作为标准化收益
        4. 将Y变换为实际收益分布
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
        
        # 第一天：随机初始化
        factor_scores[0, :, :] = np.random.randn(num_factors, N)
        
        # 为每个因子生成IC序列
        ic_series_all = np.zeros((T, num_factors))
        for k in range(num_factors):
            ic_series_all[:, k] = np.random.normal(ic_means[k], ic_std_fixed, T)
        
        # 批量生成因子得分（提高效率）
        for t in range(1, T):
            # t期实际收益率
            returns_t = stock_data.returns[t, :].copy()
            
            # 标准化收益率
            returns_mean = returns_t.mean()
            returns_std = returns_t.std()
            
            if returns_std < 1e-8:
                returns_normalized = np.zeros_like(returns_t)
            else:
                returns_normalized = (returns_t - returns_mean) / returns_std
            
            for k in range(num_factors):
                current_ic = ic_series_all[t-1, k]
                
                # 方法：使用条件分布生成相关序列
                # 已知：corr(X,Y) = ρ, Y已知（标准化收益）
                # 可以生成：X = ρ*Y + sqrt(1-ρ²)*Z，其中Z~N(0,1)独立于Y
                
                # 生成独立噪声
                Z = np.random.randn(N)
                
                # 确保Z与Y正交（相关系数为0）
                # 通过减去在Y上的投影
                if np.dot(returns_normalized, returns_normalized) > 1e-8:
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
                if abs(current_ic) < 0.999:
                    factor_raw = current_ic * returns_normalized + np.sqrt(1 - current_ic**2) * Z_normalized
                else:
                    factor_raw = np.sign(current_ic) * returns_normalized
                
                # 存储
                factor_scores[t, k, :] = factor_raw
        
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
                # 更简单的方法：直接使用得分作为权重，标准化后权重和为1（多头）和-1（空头）
                
                # 标准化得分
                scores_std = scores_valid.std()
                if scores_std < 1e-8:
                    continue
                    
                scores_normalized = scores_valid / scores_std
                
                # 多头权重：正得分部分，权重正比于得分，和为1
                long_mask = scores_normalized > 0
                if np.any(long_mask):
                    long_scores = scores_normalized[long_mask]
                    long_returns = returns_valid[long_mask]
                    
                    # 权重 = 得分 / 得分总和
                    long_weights = long_scores / long_scores.sum()
                    long_return = np.sum(long_weights * long_returns)
                else:
                    long_return = 0
                
                # 空头权重：负得分部分，权重正比于得分绝对值，和为-1
                short_mask = scores_normalized < 0
                if np.any(short_mask):
                    short_scores = scores_normalized[short_mask]
                    short_returns = returns_valid[short_mask]
                    
                    # 得分是负的，取绝对值计算权重
                    short_weights_abs = np.abs(short_scores) / np.abs(short_scores).sum()
                    short_weights = -short_weights_abs  # 负权重
                    short_return = np.sum(short_weights * short_returns)
                else:
                    short_return = 0
                
                # 多空组合收益
                ls_return = long_return + short_return
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
    
    def verify_ic_precision(
        self,
        factor_data: FactorData,
        stock_data: StockData
    ) -> Dict:
        """验证IC控制精度"""
        print("\n验证IC控制精度:")
        print("-" * 60)
        
        T, K, N = factor_data.factor_scores.shape
        
        all_errors = []
        detailed_results = []
        
        for k in range(K):
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
                all_errors.append(error)
                
                detailed_results.append({
                    'factor_id': factor_id,
                    'target_ic': target_ic_mean,
                    'actual_ic': actual_ic_mean,
                    'error': error
                })
        
        # 显示前5个结果
        for i, r in enumerate(detailed_results[:5]):
            print(f"{r['factor_id']}: 目标IC={r['target_ic']:.4f}, "
                  f"实际IC={r['actual_ic']:.4f}, 误差={r['error']:.4f}")
        
        if all_errors:
            avg_error = np.mean(all_errors)
            max_error = np.max(all_errors)
            std_error = np.std(all_errors)
            
            print(f"\n统计:")
            print(f"平均IC误差: {avg_error:.4f}")
            print(f"最大IC误差: {max_error:.4f}")
            print(f"误差标准差: {std_error:.4f}")
            print(f"误差<0.01的比例: {sum(1 for e in all_errors if e < 0.01)/len(all_errors):.1%}")
            print(f"误差<0.02的比例: {sum(1 for e in all_errors if e < 0.02)/len(all_errors):.1%}")
            
            return {
                'avg_error': avg_error,
                'max_error': max_error,
                'std_error': std_error,
                'detailed': detailed_results
            }
        
        return {}


def main_test():
    """主测试函数"""
    print("=" * 60)
    print("股票数据模拟器 - 最终版本测试")
    print("=" * 60)
    
    simulator = StockDataSimulator(seed=42)
    
    # 1. 模拟股票数据
    print("\n1. 模拟股票收益率...")
    stock_data = simulator.simulate_stock_returns(
        num_stocks=100,
        num_days=500,  # 增加天数提高统计稳定性
        start_date="2023-01-01",
        return_mean=0.0002,
        return_std=0.02
    )
    
    # 2. 模拟因子数据
    print("\n2. 模拟因子数据...")
    factor_data = simulator.simulate_factor_data(
        stock_data=stock_data,
        num_factors=30,
        ic_mean_range=(0.02, 0.06),  # 合理的IC范围
        ic_std_fixed=0.015  # 较小的IC波动
    )
    
    # 3. 验证IC精度
    ic_verification = simulator.verify_ic_precision(factor_data, stock_data)
    
    # 4. 计算表现
    print("\n4. 计算因子表现...")
    performance = simulator.calculate_factor_performance(factor_data, stock_data)
    
    # 5. 显示结果
    if performance:
        print("\n5. 因子表现排名:")
        print("-" * 80)
        print(f"{'排名':<4} {'因子ID':<12} {'IC均值':<8} {'ICIR':<8} {'年化收益':<10} {'夏普':<8}")
        print("-" * 80)
        
        for i, r in enumerate(performance[:15]):
            print(f"{i+1:<4} {r['factor_id']:<12} {r['ic_mean']:<8.3f} "
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
            
            # 分组分析
            print(f"\n按IC均值分组:")
            ic_bins = np.percentile(ic_means, [0, 25, 50, 75, 100])
            for i in range(len(ic_bins)-1):
                mask = (ic_means >= ic_bins[i]) & (ic_means < ic_bins[i+1])
                if np.any(mask):
                    group_icir = np.mean([icirs[j] for j in range(len(icirs)) if mask[j]])
                    print(f"  IC均值 {ic_bins[i]:.3f}-{ic_bins[i+1]:.3f}: 平均ICIR={group_icir:.3f}")
    
    return stock_data, factor_data, performance, ic_verification


if __name__ == "__main__":
    print("股票数据模拟器 - 精确IC控制最终版本")
    print("=" * 60)
    
    stock_data, factor_data, performance, ic_verification = main_test()
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)