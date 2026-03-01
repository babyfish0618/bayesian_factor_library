#!/usr/bin/env python3
"""
贝叶斯因子库维护系统 - 演示程序
使用新的分层目录结构
"""

import sys
import os

# 添加src目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from core.mvp_selector import Factor, MVPBayesianSelector
from simulation.stock_simulator import ProperStockSimulator
from core.integrated_selector import IntegratedBayesianSelector

def demo_mvp_selector():
    """演示MVP贝叶斯选择器"""
    print("=" * 70)
    print("演示: MVP贝叶斯选择器")
    print("=" * 70)
    
    # 创建一些测试因子
    factors = [
        Factor(id="momentum_001", expression="Return(20)", topic="momentum"),
        Factor(id="value_001", expression="PE_ratio", topic="value"),
        Factor(id="quality_001", expression="ROE", topic="quality"),
        Factor(id="size_001", expression="MarketCap", topic="size"),
        Factor(id="volatility_001", expression="Std(60)", topic="volatility"),
    ]
    
    # 初始化选择器
    selector = MVPBayesianSelector(factors, target_size=3)
    
    # 模拟选择
    print(f"\n1. 初始选择 (从{len(factors)}个因子中选择3个):")
    selected = selector.select_factors("2024-01-31")
    print(f"   选中: {selected}")
    
    # 模拟表现数据
    print(f"\n2. 模拟表现数据并更新:")
    performance_data = {
        "momentum_001": {"icir": 1.8, "rank_percentile": 0.2},
        "value_001": {"icir": 1.2, "rank_percentile": 0.4},
        "quality_001": {"icir": 0.8, "rank_percentile": 0.6},
    }
    
    selector.update_from_performance(selected, performance_data)
    
    # 显示更新后的参数
    print(f"\n3. 更新后的贝叶斯参数:")
    for factor in factors:
        if factor.alpha + factor.beta > 1:
            success_rate = factor.alpha / (factor.alpha + factor.beta)
            print(f"   {factor.id}: α={factor.alpha:.1f}, β={factor.beta:.1f}, 成功率={success_rate:.3f}")

def demo_stock_simulator():
    """演示股票数据模拟器"""
    print("\n" + "=" * 70)
    print("演示: 股票数据模拟器")
    print("=" * 70)
    
    # 需要numpy
    try:
        import numpy as np
    except ImportError:
        print("⚠️ 需要numpy库")
        return
    
    # 创建模拟器
    simulator = ProperStockSimulator(seed=42)
    
    print("\n1. 测试相关性生成:")
    
    # 生成测试数据
    np.random.seed(42)
    N = 1000
    returns = np.random.randn(N) * 0.02
    
    # 测试不同IC值
    test_ics = [0.02, 0.05, 0.10]
    
    for target_ic in test_ics:
        # 生成相关序列
        factor_scores = simulator.generate_correlated_series(returns, target_ic)
        
        # 计算实际相关性
        actual_ic = np.corrcoef(factor_scores, returns)[0, 1]
        error = abs(actual_ic - target_ic)
        
        print(f"   目标IC={target_ic:.3f}, 实际IC={actual_ic:.3f}, 误差={error:.4f}")
    
    print("\n2. 测试得分加权多空收益:")
    
    # 生成测试数据
    scores = np.random.randn(100)
    future_returns = np.random.randn(100) * 0.02
    
    # 计算多空收益
    ls_return = simulator.calculate_weighted_long_short_return(scores, future_returns)
    print(f"   多空收益: {ls_return:.6f}")

def demo_integrated_system():
    """演示集成系统"""
    print("\n" + "=" * 70)
    print("演示: 集成系统")
    print("=" * 70)
    
    # 创建集成选择器（小规模测试）
    selector = IntegratedBayesianSelector(
        num_stocks=30,
        num_factors=10,
        target_selection_size=3,
        seed=42
    )
    
    print(f"\n1. 初始化模拟数据:")
    selector.initialize_simulation(num_days=50)
    
    print(f"\n2. 运行简单回测:")
    results = selector.run_backtest(num_selections=3)
    
    print(f"\n3. 结果摘要:")
    selector.print_summary()

def main():
    """主函数"""
    print("贝叶斯因子库维护系统 - 分层结构演示")
    print("版本: 1.0.0")
    print("目录结构:")
    print("  src/core/        - 核心算法")
    print("  src/simulation/  - 数据模拟")
    print("  src/evaluation/  - 评估系统")
    print("  src/tests/       - 测试代码")
    print("  src/archive/     - 历史版本")
    
    # 运行演示
    demo_mvp_selector()
    demo_stock_simulator()
    
    # 集成系统演示需要numpy
    try:
        import numpy as np
        demo_integrated_system()
    except ImportError:
        print("\n⚠️ 需要numpy库来运行集成系统演示")
        print("   安装: pip install numpy")
    
    print("\n" + "=" * 70)
    print("演示完成!")
    print("=" * 70)

if __name__ == "__main__":
    main()