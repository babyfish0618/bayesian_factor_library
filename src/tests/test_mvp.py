"""
MVP测试代码 - 贝叶斯因子选择器基础功能测试

测试目标：
验证MVP版本的贝叶斯因子选择器基本功能

测试参数：
- 因子数量: 100个
- 历史数据: 12个月
- 每次选择: 50个因子

测试维度：
1. 算法有效性: 能否区分好因子和差因子
2. 因子类型识别: 能否正确识别5种因子类型
   - 稳定好因子: 持续高ICIR
   - 波动大因子: ICIR波动大
   - 近期失效因子: 前期好，近期变差
   - 新兴好因子: 前期差，近期变好
   - 一直差因子: 持续低ICIR
3. 边界情况: 因子数不足、全差因子、空列表等
4. 学习能力: 贝叶斯参数能否正确反映因子质量

测试流程：
1. 生成5种类型的测试因子
2. 运行选择算法
3. 验证选择结果
4. 测试边界情况
5. 分析算法有效性

作者: 小鱼爬爬
日期: 2026-02-28
"""

import numpy as np
import random
from datetime import datetime, timedelta
from typing import List, Dict
from mvp_selector import Factor, MVPBayesianSelector


def generate_test_factors(num_factors: int = 100, num_months: int = 12) -> List[Factor]:
    """生成测试因子
    
    设计决策：创建有不同特性的测试因子，模拟真实场景：
    1. 稳定好因子：持续高ICIR
    2. 波动大因子：ICIR波动大
    3. 近期失效因子：前期好，近期变差
    4. 新兴好因子：近期变好
    5. 一直差因子：持续低ICIR
    """
    print(f"生成 {num_factors} 个测试因子，{num_months} 个月历史数据")
    
    factors = []
    topics = ['momentum', 'value', 'quality', 'growth', 'volatility']
    
    for i in range(num_factors):
        factor_id = f"factor_{i:03d}"
        topic = random.choice(topics)
        
        # 根据ID决定因子类型（确保可重复）
        factor_type = i % 5
        
        factor = Factor(id=factor_id, expression=f"expr_{i}", topic=topic)
        
        # 生成历史表现数据
        base_date = datetime(2023, 1, 1)
        
        for month in range(num_months):
            date_str = (base_date + timedelta(days=month*30)).strftime("%Y-%m-%d")
            
            # 根据因子类型生成不同的ICIR模式
            if factor_type == 0:  # 稳定好因子
                icir = np.random.normal(2.0, 0.3)  # 均值2.0，波动小
            elif factor_type == 1:  # 波动大因子
                icir = np.random.normal(1.0, 0.8)  # 均值1.0，波动大
            elif factor_type == 2:  # 近期失效因子
                if month < num_months * 0.7:  # 前70%时间好
                    icir = np.random.normal(1.8, 0.4)
                else:  # 后30%时间差
                    icir = np.random.normal(0.5, 0.3)
            elif factor_type == 3:  # 新兴好因子
                if month < num_months * 0.3:  # 前30%时间差
                    icir = np.random.normal(0.5, 0.3)
                else:  # 后70%时间好
                    icir = np.random.normal(1.8, 0.4)
            else:  # 一直差因子
                icir = np.random.normal(0.3, 0.2)  # 均值0.3，一直差
            
            # 确保ICIR非负
            icir = max(icir, 0.1)
            
            # 排名百分位（模拟）
            rank_percentile = random.uniform(0, 1)
            
            # 贡献（模拟）
            contribution = icir * 0.01  # 简单线性关系
            
            factor.add_performance(date_str, icir, rank_percentile, contribution)
        
        factors.append(factor)
    
    print(f"因子生成完成，类型分布:")
    print(f"  稳定好因子: {num_factors//5} 个")
    print(f"  波动大因子: {num_factors//5} 个")
    print(f"  近期失效因子: {num_factors//5} 个")
    print(f"  新兴好因子: {num_factors//5} 个")
    print(f"  一直差因子: {num_factors//5} 个")
    
    return factors


def generate_performance_data(selected_ids: List[str], all_factors: Dict[str, Factor]) -> Dict[str, Dict]:
    """生成表现数据（模拟）
    
    设计决策：模拟真实表现数据，包含噪声。
    """
    performance_data = {}
    
    for fid in selected_ids:
        factor = all_factors[fid]
        
        # 基于最近表现生成，加入一些噪声
        recent_icir = factor.get_recent_icir()
        noise = np.random.normal(0, 0.2)  # 加入噪声
        icir = max(recent_icir + noise, 0.1)
        
        # 排名（模拟）：ICIR越高，排名越好
        rank_percentile = max(0, min(1, 1 - icir/3.0 + np.random.normal(0, 0.1)))
        
        performance_data[fid] = {
            'icir': icir,
            'rank_percentile': rank_percentile,
            'contribution': icir * 0.01
        }
    
    return performance_data


def run_mvp_test():
    """运行MVP测试"""
    print("=" * 60)
    print("MVP贝叶斯因子选择器测试")
    print("=" * 60)
    
    # 1. 生成测试因子
    factors = generate_test_factors(num_factors=100, num_months=12)
    
    # 2. 初始化选择器
    selector = MVPBayesianSelector(factors, target_size=50)
    
    print("\n" + "=" * 60)
    print("开始模拟月度维护流程")
    print("=" * 60)
    
    # 3. 模拟12个月的维护
    for month in range(1, 13):
        current_date = f"2024-{month:02d}-28"
        print(f"\n--- 月份 {month} ({current_date}) ---")
        
        # 选择因子
        selected_ids = selector.select_factors(current_date)
        
        # 生成表现数据
        performance_data = generate_performance_data(selected_ids, selector.factors)
        
        # 更新贝叶斯参数
        selector.update_from_performance(selected_ids, performance_data)
        
        # 显示统计信息
        if month % 3 == 0:  # 每3个月显示一次详细统计
            stats = selector.get_selection_stats()
            print(f"\n  选择统计: 日期={stats['date']}, "
                  f"选择数={stats['num_selected']}, "
                  f"候选数={stats['num_candidates']}, "
                  f"选择比例={stats['selection_ratio']:.1%}")
    
    # 4. 显示最终结果
    print("\n" + "=" * 60)
    print("测试完成，最终结果")
    print("=" * 60)
    
    # 显示前10个因子的统计
    top_factors = selector.get_factor_stats(top_n=10)
    print("\nTop 10 因子统计:")
    print("-" * 80)
    print(f"{'ID':<12} {'主题':<10} {'α':<6} {'β':<6} {'成功率':<8} {'近期ICIR':<10} {'历史数':<6}")
    print("-" * 80)
    
    for f in top_factors:
        print(f"{f['id']:<12} {f['topic']:<10} {f['alpha']:<6.1f} {f['beta']:<6.1f} "
              f"{f['success_rate']:<8.2f} {f['recent_icir']:<10.2f} {f['performance_count']:<6}")
    
    # 分析不同类型因子的表现
    print("\n" + "=" * 60)
    print("因子类型分析")
    print("=" * 60)
    
    factor_types = ['稳定好因子', '波动大因子', '近期失效因子', '新兴好因子', '一直差因子']
    
    for i, type_name in enumerate(factor_types):
        # 获取该类型的所有因子
        type_factors = [f for f in selector.factors.values() 
                       if int(f.id.split('_')[1]) % 5 == i]
        
        if type_factors:
            avg_success_rate = np.mean([f.get_success_rate() for f in type_factors])
            avg_recent_icir = np.mean([f.get_recent_icir() for f in type_factors])
            
            print(f"{type_name:<12}: 平均成功率={avg_success_rate:.2f}, "
                  f"平均近期ICIR={avg_recent_icir:.2f}, "
                  f"数量={len(type_factors)}")
    
    # 5. 验证算法有效性
    print("\n" + "=" * 60)
    print("算法有效性验证")
    print("=" * 60)
    
    # 检查：好因子的成功率是否更高？
    good_factors = [f for f in selector.factors.values() 
                   if int(f.id.split('_')[1]) % 5 in [0, 3]]  # 稳定好 + 新兴好
    bad_factors = [f for f in selector.factors.values() 
                  if int(f.id.split('_')[1]) % 5 in [2, 4]]   # 近期失效 + 一直差
    
    if good_factors and bad_factors:
        good_success = np.mean([f.get_success_rate() for f in good_factors])
        bad_success = np.mean([f.get_success_rate() for f in bad_factors])
        
        print(f"好因子平均成功率: {good_success:.3f}")
        print(f"差因子平均成功率: {bad_success:.3f}")
        print(f"差异: {good_success - bad_success:.3f} "
              f"({'显著' if good_success > bad_success + 0.1 else '不显著'})")
    
    return selector


def test_edge_cases():
    """测试边界情况"""
    print("\n" + "=" * 60)
    print("边界情况测试")
    print("=" * 60)
    
    # 测试1：因子数量少于目标数量
    print("\n测试1: 因子数量少于目标数量")
    factors = generate_test_factors(num_factors=30, num_months=6)
    selector = MVPBayesianSelector(factors, target_size=50)
    selected = selector.select_factors("2024-01-31")
    print(f"  因子数: 30, 目标数: 50, 实际选择: {len(selected)}")
    
    # 测试2：所有因子表现都很差
    print("\n测试2: 所有因子表现都很差")
    factors = []
    for i in range(50):
        f = Factor(id=f"bad_{i}", expression=f"expr_{i}", topic="bad")
        # 添加很差的性能数据
        for month in range(6):
            f.add_performance(f"2024-{month+1:02d}-28", 
                             icir=0.1,  # 很低的ICIR
                             rank_percentile=0.9,  # 很差的排名
                             contribution=0.0)
        factors.append(f)
    
    selector = MVPBayesianSelector(factors, target_size=20)
    selected = selector.select_factors("2024-07-31")
    print(f"  差因子选择数: {len(selected)}")
    
    # 测试3：空因子列表
    print("\n测试3: 空因子列表")
    try:
        selector = MVPBayesianSelector([], target_size=10)
        selected = selector.select_factors("2024-01-31")
        print(f"  空列表选择: {len(selected)}")
    except Exception as e:
        print(f"  错误: {e}")


if __name__ == "__main__":
    print("贝叶斯因子库维护系统 - MVP测试")
    print("版本: 0.1.0")
    print("作者: 小鱼爬爬量化研究助手")
    print("=" * 60)
    
    # 设置随机种子，使结果可重复
    np.random.seed(42)
    random.seed(42)
    
    # 运行主测试
    selector = run_mvp_test()
    
    # 运行边界测试
    test_edge_cases()
    
    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)