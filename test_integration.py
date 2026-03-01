"""
独立测试集成功能
"""

import numpy as np
from typing import List, Dict
import json


# 简化Factor类
class Factor:
    def __init__(self, id, expression, topic, alpha=1.0, beta=1.0):
        self.id = id
        self.expression = expression
        self.topic = topic
        self.alpha = alpha
        self.beta = beta
        self.performance_history = []
    
    def add_performance(self, date_str, icir=None, rank_percentile=None):
        self.performance_history.append({
            'date': date_str,
            'icir': icir,
            'rank_percentile': rank_percentile
        })


# 简化MVPBayesianSelector类
class MVPBayesianSelector:
    def __init__(self, factors, target_size=50):
        self.factors = {f.id: f for f in factors}
        self.target_size = target_size
    
    def select_factors(self, date_str):
        # 使用Thompson Sampling选择
        selected = []
        scores = []
        
        for fid, factor in self.factors.items():
            # 从Beta分布采样
            bayesian_score = np.random.beta(factor.alpha, factor.beta)
            scores.append((fid, bayesian_score))
        
        # 按得分排序
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # 选择前target_size个
        selected = [fid for fid, _ in scores[:self.target_size]]
        
        print(f"  Thompson Sampling选择完成: {len(selected)} 个因子")
        return selected
    
    def update_from_performance(self, selected_ids, performance_data):
        print(f"  更新 {len(selected_ids)} 个因子的贝叶斯参数")
        
        for fid in selected_ids:
            if fid in self.factors and fid in performance_data:
                factor = self.factors[fid]
                perf = performance_data[fid]
                
                # 简化成功条件：ICIR > 0
                if perf.get('icir', 0) > 0:
                    factor.alpha += 1  # 成功
                    print(f"    因子 {fid}: 成功 (α={factor.alpha}, β={factor.beta})")
                else:
                    factor.beta += 1   # 失败
                    print(f"    因子 {fid}: 失败 (α={factor.alpha}, β={factor.beta})")


# 简化ProperStockSimulator类
class ProperStockSimulator:
    def __init__(self, seed=42):
        np.random.seed(seed)
    
    def simulate_stock_returns(self, num_stocks=100, num_days=252, start_date="2023-01-01"):
        print(f"  模拟股票收益率: {num_stocks}股票, {num_days}天")
        
        class StockData:
            def __init__(self):
                # 生成日期
                from datetime import datetime, timedelta
                start = datetime.strptime(start_date, "%Y-%m-%d")
                self.dates = [(start + timedelta(days=i)).strftime("%Y-%m-%d") 
                             for i in range(num_days)]
                self.dates = np.array(self.dates)
                
                # 生成收益率
                self.returns = np.random.randn(num_days, num_stocks) * 0.02 + 0.0002
        
        return StockData()
    
    def simulate_factor_data(self, stock_data, num_factors=50, ic_mean_range=(0.02, 0.06), ic_std_fixed=0.01):
        print(f"  模拟因子数据: {num_factors}因子")
        
        T, N = stock_data.returns.shape
        
        class FactorData:
            def __init__(self):
                self.factor_ids = [f"F{i:03d}" for i in range(num_factors)]
                self.factor_scores = np.random.randn(T, num_factors, N)
                self.ic_means = np.random.uniform(*ic_mean_range, size=num_factors)
        
        return FactorData()
    
    def calculate_weighted_long_short_return(self, scores, returns, leverage=2.0):
        # 简化计算
        N = len(scores)
        if N == 0:
            return 0.0
        
        # 标准化得分
        scores_std = scores.std()
        if scores_std < 1e-8:
            return 0.0
        scores_norm = scores / scores_std
        
        total_return = 0.0
        
        # 多头部分
        long_mask = scores_norm > 0
        if np.any(long_mask):
            long_scores = scores_norm[long_mask]
            long_returns = returns[long_mask]
            long_weights = long_scores / long_scores.sum() * (leverage / 2)
            total_return += np.sum(long_weights * long_returns)
        
        # 空头部分
        short_mask = scores_norm < 0
        if np.any(short_mask):
            short_scores = scores_norm[short_mask]
            short_returns = returns[short_mask]
            short_scores_pos = -short_scores
            short_weights = -short_scores_pos / short_scores_pos.sum() * (leverage / 2)
            total_return += np.sum(short_weights * short_returns)
        
        return total_return


class IntegratedBayesianSelector:
    """集成贝叶斯选择器（简化版本）"""
    
    def __init__(self, num_stocks=50, num_factors=20, target_selection_size=5, seed=42):
        self.num_stocks = num_stocks
        self.num_factors = num_factors
        self.target_selection_size = target_selection_size
        self.seed = seed
        
        self.simulator = ProperStockSimulator(seed=seed)
        self.stock_data = None
        self.factor_data = None
        self.factors = []
        self.bayesian_selector = None
        self.selection_history = []
        
        print(f"集成贝叶斯选择器初始化")
        print(f"  股票: {num_stocks}, 因子: {num_factors}, 选择数: {target_selection_size}")
    
    def initialize_simulation(self, num_days=100):
        print(f"\n初始化模拟数据 ({num_days}天)")
        
        # 模拟数据
        self.stock_data = self.simulator.simulate_stock_returns(
            num_stocks=self.num_stocks,
            num_days=num_days
        )
        
        self.factor_data = self.simulator.simulate_factor_data(
            stock_data=self.stock_data,
            num_factors=self.num_factors
        )
        
        # 创建Factor对象
        self.factors = []
        for k in range(self.num_factors):
            factor_id = self.factor_data.factor_ids[k]
            factor = Factor(
                id=factor_id,
                expression=f"simulated_{factor_id}",
                topic="simulated"
            )
            factor.ic_mean = self.factor_data.ic_means[k]
            self.factors.append(factor)
        
        # 初始化选择器
        self.bayesian_selector = MVPBayesianSelector(
            factors=self.factors,
            target_size=self.target_selection_size
        )
        
        print(f"  创建了 {len(self.factors)} 个Factor对象")
    
    def monthly_selection(self, date):
        print(f"\n月度选择: {date}")
        
        # 简化：随机生成表现数据
        performance_data = {}
        for factor in self.factors:
            # 基于IC均值生成表现（高IC均值 -> 高ICIR）
            base_icir = factor.ic_mean * 100  # 放大
            noise = np.random.randn() * 0.5
            icir = max(0.1, base_icir + noise)  # 确保为正
            
            performance_data[factor.id] = {
                'icir': icir,
                'rank_percentile': np.random.uniform(0.3, 0.8)
            }
        
        # 贝叶斯选择
        selected_ids = self.bayesian_selector.select_factors(date)
        
        # 更新参数
        self.bayesian_selector.update_from_performance(selected_ids, performance_data)
        
        # 记录历史
        self.selection_history.append({
            'date': date,
            'selected': selected_ids,
            'performance': {fid: performance_data[fid] for fid in selected_ids if fid in performance_data}
        })
        
        return selected_ids
    
    def run_backtest(self, num_selections=5):
        print(f"\n=== 运行回测 ({num_selections}次选择) ===")
        
        dates = self.stock_data.dates
        if len(dates) < num_selections:
            num_selections = len(dates)
        
        for i in range(num_selections):
            date_idx = i * (len(dates) // num_selections)
            if date_idx >= len(dates):
                break
            
            date = dates[date_idx]
            self.monthly_selection(date)
        
        print(f"\n回测完成!")
        print(f"  总选择次数: {len(self.selection_history)}")
    
    def print_summary(self):
        print(f"\n=== 结果摘要 ===")
        
        if not self.selection_history:
            print("  无选择历史")
            return
        
        # 计算平均选中因子数
        avg_selected = np.mean([len(h['selected']) for h in self.selection_history])
        print(f"  平均选中因子数: {avg_selected:.1f}")
        
        # 显示因子成功率
        success_rates = []
        for factor in self.factors:
            if factor.alpha + factor.beta > 0:
                success_rate = factor.alpha / (factor.alpha + factor.beta)
                success_rates.append(success_rate)
        
        if success_rates:
            print(f"  因子成功率:")
            print(f"    平均: {np.mean(success_rates):.3f}")
            print(f"    范围: {np.min(success_rates):.3f} - {np.max(success_rates):.3f}")
        
        # 显示最近选择
        last = self.selection_history[-1]
        print(f"\n  最近选择 ({last['date']}):")
        print(f"    选中因子: {last['selected']}")
        
        if last['performance']:
            avg_icir = np.mean([p['icir'] for p in last['performance'].values()])
            print(f"    平均ICIR: {avg_icir:.3f}")


def main():
    print("=" * 70)
    print("集成贝叶斯选择器 - 简化测试")
    print("=" * 70)
    
    # 创建选择器
    selector = IntegratedBayesianSelector(
        num_stocks=30,      # 小规模测试
        num_factors=15,
        target_selection_size=3,
        seed=42
    )
    
    # 初始化
    selector.initialize_simulation(num_days=50)
    
    # 运行回测
    selector.run_backtest(num_selections=5)
    
    # 打印摘要
    selector.print_summary()
    
    # 保存简化结果
    results = {
        'parameters': {
            'num_stocks': selector.num_stocks,
            'num_factors': selector.num_factors,
            'target_selection_size': selector.target_selection_size
        },
        'selection_history': selector.selection_history,
        'factors': [
            {
                'id': f.id,
                'alpha': f.alpha,
                'beta': f.beta,
                'success_rate': f.alpha / (f.alpha + f.beta) if (f.alpha + f.beta) > 0 else 0
            }
            for f in selector.factors
        ]
    }
    
    with open('simplified_integration_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n结果已保存到: simplified_integration_results.json")
    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)
    
    return selector


if __name__ == "__main__":
    selector = main()