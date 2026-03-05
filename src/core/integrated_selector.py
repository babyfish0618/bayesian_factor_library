"""
集成贝叶斯选择器
将正确的股票数据模拟器与MVP贝叶斯选择器集成
"""

import numpy as np
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json

# 导入现有模块
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 尝试导入，如果失败则内联定义
try:
    from simulation.stock_simulator import ProperStockSimulator
    from core.mvp_selector import Factor, MVPBayesianSelector
except ImportError:
    # 如果导入失败，提供简化版本
    print("警告: 无法导入模块，使用简化版本")
    
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
            # 简化选择：随机选择
            import random
            factor_ids = list(self.factors.keys())
            selected = random.sample(factor_ids, min(self.target_size, len(factor_ids)))
            return selected
        
        def update_from_performance(self, selected_ids, performance_data):
            # 简化更新
            for fid in selected_ids:
                if fid in self.factors and fid in performance_data:
                    factor = self.factors[fid]
                    perf = performance_data[fid]
                    if perf.get('icir', 0) > 0.5:  # 简化成功条件
                        factor.alpha += 1
                    else:
                        factor.beta += 1
    
    # 简化ProperStockSimulator类
    class ProperStockSimulator:
        def __init__(self, seed=42):
            import numpy as np
            np.random.seed(seed)
        
        def simulate_stock_returns(self, **kwargs):
            # 返回简化数据
            class StockData:
                def __init__(self):
                    self.dates = ["2023-01-01", "2023-01-02"]
                    self.returns = np.random.randn(2, 10)
            return StockData()
        
        def simulate_factor_data(self, **kwargs):
            # 返回简化数据
            class FactorData:
                def __init__(self):
                    self.factor_ids = ["F001", "F002"]
                    self.factor_scores = np.random.randn(2, 2, 10)
                    self.ic_means = np.array([0.03, 0.05])
            return FactorData()
        
        def calculate_weighted_long_short_return(self, scores, returns, leverage=2.0):
            return 0.01  # 简化返回值


class IntegratedBayesianSelector:
    """集成贝叶斯选择器"""
    
    def __init__(
        self,
        num_stocks: int = 100,
        num_factors: int = 50,
        target_selection_size: int = 20,
        seed: int = 42
    ):
        """
        初始化集成选择器
        
        参数：
            num_stocks: 股票数量
            num_factors: 因子数量
            target_selection_size: 目标选择数量
            seed: 随机种子
        """
        self.num_stocks = num_stocks
        self.num_factors = num_factors
        self.target_selection_size = target_selection_size
        self.seed = seed
        
        # 初始化模拟器
        self.simulator = ProperStockSimulator(seed=seed)
        
        # 初始化数据容器
        self.stock_data = None
        self.factor_data = None
        self.factors = []  # Factor对象列表
        self.bayesian_selector = None
        
        # 历史记录
        self.selection_history = []  # 选择历史
        self.performance_history = []  # 表现历史
        
        # 当前状态
        self.current_date = None
        self.current_date_index = 0
        
        print(f"集成贝叶斯选择器初始化完成")
        print(f"  股票数: {num_stocks}")
        print(f"  因子数: {num_factors}")
        print(f"  目标选择数: {target_selection_size}")
    
    def initialize_simulation(
        self,
        num_days: int = 252,
        start_date: str = "2023-01-01",
        ic_mean_range: tuple = (0.02, 0.06),
        ic_std_fixed: float = 0.01
    ):
        """初始化模拟数据"""
        print(f"\n初始化模拟数据...")
        print(f"  天数: {num_days}")
        print(f"  开始日期: {start_date}")
        print(f"  IC均值范围: {ic_mean_range}")
        print(f"  IC标准差固定: {ic_std_fixed}")
        
        # 1. 模拟股票数据
        self.stock_data = self.simulator.simulate_stock_returns(
            num_stocks=self.num_stocks,
            num_days=num_days,
            start_date=start_date
        )
        
        # 2. 模拟因子数据
        self.factor_data = self.simulator.simulate_factor_data(
            stock_data=self.stock_data,
            num_factors=self.num_factors,
            ic_mean_range=ic_mean_range,
            ic_std_fixed=ic_std_fixed
        )
        
        # 3. 创建Factor对象列表
        self._create_factor_objects()
        
        # 4. 初始化贝叶斯选择器
        self.bayesian_selector = MVPBayesianSelector(
            factors=self.factors,
            target_size=self.target_selection_size
        )
        
        # 5. 设置当前日期
        self.current_date = start_date
        self.current_date_index = 0
        
        print(f"模拟数据初始化完成")
        print(f"  股票收益率形状: {self.stock_data.returns.shape}")
        print(f"  因子得分形状: {self.factor_data.factor_scores.shape}")
        print(f"  因子对象数: {len(self.factors)}")
    
    def _create_factor_objects(self):
        """从模拟数据创建Factor对象"""
        print(f"创建Factor对象...")
        
        self.factors = []
        T, K, N = self.factor_data.factor_scores.shape
        
        for k in range(K):
            factor_id = self.factor_data.factor_ids[k]
            ic_mean = self.factor_data.ic_means[k]
            
            # 创建Factor对象
            factor = Factor(
                id=factor_id,
                expression=f"simulated_{factor_id}",  # 模拟因子，无实际表达式
                topic="simulated",
                alpha=1.0,  # 初始α
                beta=1.0    # 初始β
            )
            
            # 添加IC均值信息
            factor.ic_mean = ic_mean
            
            self.factors.append(factor)
        
        print(f"  创建了 {len(self.factors)} 个Factor对象")
    
    def get_factor_performance_at_date(
        self,
        date: str,
        lookback_days: int = 20
    ) -> Dict[str, Dict]:
        """
        获取指定日期的因子表现
        
        计算每个因子在最近lookback_days天的表现：
        1. IC均值
        2. ICIR
        3. 多空收益
        """
        # 找到日期索引
        date_idx = np.where(self.stock_data.dates == date)[0]
        if len(date_idx) == 0:
            raise ValueError(f"日期 {date} 不存在")
        
        date_idx = date_idx[0]
        
        # 计算开始索引
        start_idx = max(0, date_idx - lookback_days)
        
        performance_data = {}
        
        for k in range(self.num_factors):
            factor_id = self.factor_data.factor_ids[k]
            
            ic_values = []
            ls_returns = []
            
            # 计算过去lookback_days天的表现
            for t in range(start_idx, date_idx):
                if t >= 1:  # 需要至少前一天的数据
                    # t-1期因子得分
                    scores = self.factor_data.factor_scores[t-1, k, :]
                    # t期收益
                    returns = self.stock_data.returns[t, :]
                    
                    # 计算IC
                    valid_mask = ~(np.isnan(scores) | np.isnan(returns))
                    if np.sum(valid_mask) > 10:
                        ic = np.corrcoef(scores[valid_mask], returns[valid_mask])[0, 1]
                        if not np.isnan(ic):
                            ic_values.append(ic)
                    
                    # 计算多空收益
                    ls_return = self.simulator.calculate_weighted_long_short_return(
                        scores, returns, leverage=2.0
                    )
                    ls_returns.append(ls_return)
            
            if len(ic_values) > 5:  # 至少5个有效观测
                ic_array = np.array(ic_values)
                ic_mean = ic_array.mean()
                ic_std = ic_array.std()
                icir = ic_mean / (ic_std + 1e-8)
                
                ls_array = np.array(ls_returns)
                ls_mean = ls_array.mean()
                
                performance_data[factor_id] = {
                    'ic_mean': ic_mean,
                    'ic_std': ic_std,
                    'icir': icir,
                    'ls_return': ls_mean,
                    'obs_count': len(ic_values)
                }
        
        return performance_data
    
    def monthly_selection(self, date: str) -> List[str]:
        """
        月度因子选择
        
        步骤：
        1. 获取当前因子表现
        2. 贝叶斯选择
        3. 更新贝叶斯参数
        4. 记录历史
        """
        print(f"\n=== 月度因子选择: {date} ===")
        
        # 1. 获取因子表现
        print(f"1. 获取因子表现...")
        performance_data = self.get_factor_performance_at_date(date, lookback_days=20)
        
        if not performance_data:
            print(f"  警告: 没有有效的因子表现数据")
            return []
        
        print(f"  有效因子数: {len(performance_data)}")
        
        # 2. 准备选择数据
        # 将表现数据转换为选择器需要的格式
        selection_performance = {}
        for factor_id, perf in performance_data.items():
            # 使用ICIR作为选择标准
            selection_performance[factor_id] = {
                'icir': perf['icir'],
                'rank_percentile': 0.5  # 简化，实际应该计算排名
            }
        
        # 3. 贝叶斯选择
        print(f"2. 贝叶斯选择...")
        selected_ids = self.bayesian_selector.select_factors(date)
        
        print(f"  选择了 {len(selected_ids)} 个因子")
        if selected_ids:
            print(f"  前5个选中因子: {selected_ids[:5]}")
        
        # 4. 模拟更新（实际应该用未来表现更新）
        # 这里简化：用当前表现作为"未来表现"更新
        print(f"3. 更新贝叶斯参数...")
        
        # 准备更新数据
        update_data = {}
        for factor_id in selected_ids:
            if factor_id in performance_data:
                perf = performance_data[factor_id]
                update_data[factor_id] = {
                    'icir': perf['icir'],
                    'rank_percentile': 0.5  # 简化
                }
        
        # 更新贝叶斯参数
        self.bayesian_selector.update_from_performance(selected_ids, update_data)
        
        # 5. 记录历史
        self.selection_history.append({
            'date': date,
            'selected_factors': selected_ids,
            'performance_data': {k: v for k, v in performance_data.items() if k in selected_ids}
        })
        
        # 6. 更新当前日期索引
        self.current_date_index += 1
        if self.current_date_index < len(self.stock_data.dates):
            self.current_date = self.stock_data.dates[self.current_date_index]
        
        return selected_ids
    
    def run_backtest(
        self,
        start_date: str,
        end_date: str,
        selection_frequency: int = 20  # 每20天选择一次
    ) -> Dict:
        """
        运行回测
        
        参数：
            selection_frequency: 选择频率（天数）
        """
        print(f"\n=== 开始回测 ===")
        print(f"  开始日期: {start_date}")
        print(f"  结束日期: {end_date}")
        print(f"  选择频率: 每 {selection_frequency} 天")
        
        # 找到日期范围
        dates = self.stock_data.dates
        start_idx = np.where(dates >= start_date)[0][0]
        end_idx = np.where(dates <= end_date)[0][-1]
        
        backtest_results = {
            'dates': [],
            'selected_factors': [],
            'portfolio_returns': [],
            'factor_performance': []
        }
        
        # 按频率进行选择
        for idx in range(start_idx, end_idx + 1, selection_frequency):
            if idx >= len(dates):
                break
            
            current_date = dates[idx]
            print(f"\n处理日期: {current_date} (索引: {idx}/{end_idx})")
            
            # 月度选择
            selected_factors = self.monthly_selection(current_date)
            
            # 记录结果
            backtest_results['dates'].append(current_date)
            backtest_results['selected_factors'].append(selected_factors)
            
            # 计算组合表现（简化：使用等权组合）
            if selected_factors:
                # 获取选中因子的表现
                perf_data = self.get_factor_performance_at_date(current_date, lookback_days=10)
                selected_perf = {fid: perf_data.get(fid, {}) for fid in selected_factors if fid in perf_data}
                
                # 计算平均ICIR作为组合"得分"
                avg_icir = np.mean([p.get('icir', 0) for p in selected_perf.values()]) if selected_perf else 0
                backtest_results['portfolio_returns'].append(avg_icir)
                backtest_results['factor_performance'].append(selected_perf)
        
        print(f"\n回测完成!")
        print(f"  总选择次数: {len(backtest_results['dates'])}")
        print(f"  平均选中因子数: {np.mean([len(f) for f in backtest_results['selected_factors']]):.1f}")
        
        return backtest_results
    
    def save_results(self, filename: str = "integration_results.json"):
        """保存结果到文件"""
        results = {
            'parameters': {
                'num_stocks': self.num_stocks,
                'num_factors': self.num_factors,
                'target_selection_size': self.target_selection_size,
                'seed': self.seed
            },
            'selection_history': self.selection_history,
            'factor_info': [
                {
                    'id': factor.id,
                    'alpha': factor.alpha,
                    'beta': factor.beta,
                    'success_rate': factor.alpha / (factor.alpha + factor.beta) if (factor.alpha + factor.beta) > 0 else 0
                }
                for factor in self.factors
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"结果已保存到: {filename}")
    
    def print_summary(self):
        """打印摘要信息"""
        print(f"\n=== 集成选择器摘要 ===")
        print(f"当前日期: {self.current_date}")
        print(f"股票数: {self.num_stocks}")
        print(f"因子数: {self.num_factors}")
        print(f"目标选择数: {self.target_selection_size}")
        print(f"选择历史记录数: {len(self.selection_history)}")
        
        if self.factors:
            # 计算因子成功率统计
            success_rates = []
            for factor in self.factors:
                if factor.alpha + factor.beta > 0:
                    success_rates.append(factor.alpha / (factor.alpha + factor.beta))
            
            if success_rates:
                print(f"因子成功率统计:")
                print(f"  平均: {np.mean(success_rates):.3f}")
                print(f"  最小: {np.min(success_rates):.3f}")
                print(f"  最大: {np.max(success_rates):.3f}")
        
        # 显示最近一次选择
        if self.selection_history:
            last_selection = self.selection_history[-1]
            print(f"\n最近一次选择 ({last_selection['date']}):")
            print(f"  选中因子数: {len(last_selection['selected_factors'])}")
            if last_selection['selected_factors']:
                print(f"  前5个因子: {last_selection['selected_factors'][:5]}")


def test_integration():
    """测试集成"""
    print("=" * 70)
    print("测试集成贝叶斯选择器")
    print("=" * 70)
    
    # 创建集成选择器
    selector = IntegratedBayesianSelector(
        num_stocks=50,      # 减少数量加快测试
        num_factors=20,     # 减少因子数
        target_selection_size=5,
        seed=42
    )
    
    # 初始化模拟数据
    selector.initialize_simulation(
        num_days=100,       # 减少天数
        start_date="2023-01-01",
        ic_mean_range=(0.02, 0.06),
        ic_std_fixed=0.01
    )
    
    # 运行简单回测
    results = selector.run_backtest(
        start_date="2023-01-20",
        end_date="2023-04-10",
        selection_frequency=10  # 每10天选择一次
    )
    
    # 打印摘要
    selector.print_summary()
    
    # 保存结果
    selector.save_results("test_integration_results.json")
    
    print("\n" + "=" * 70)
    print("集成测试完成!")
    print("=" * 70)
    
    return selector, results


if __name__ == "__main__":
    selector, results = test_integration()