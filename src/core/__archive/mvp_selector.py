"""
MVP贝叶斯因子选择器

最小可行产品版本，验证核心算法逻辑。
使用模拟数据进行测试。
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import random


@dataclass
class Factor:
    """因子数据结构 - MVP简化版
    
    注意：真实应用中会有更多字段，但MVP阶段只保留核心字段。
    设计决策：先验证算法逻辑，再扩展数据结构。
    """
    id: str                    # 因子ID
    expression: str            # 因子表达式
    topic: str                 # 主题分类
    alpha: float = 1.0         # 贝叶斯成功次数（先验α=1）
    beta: float = 1.0          # 贝叶斯失败次数（先验β=1）
    performance: List[Dict] = field(default_factory=list)  # 历史表现记录
    
    def add_performance(self, date: str, icir: float, rank_percentile: float, 
                        contribution: float = 0.0) -> None:
        """添加表现记录
        
        设计决策：简化表现数据结构，只保留核心指标。
        后续可以扩展更多指标（夏普、最大回撤等）。
        """
        self.performance.append({
            'date': date,
            'icir': icir,
            'rank_percentile': rank_percentile,  # 排名百分位（0-1，越小越好）
            'contribution': contribution         # 对组合的贡献
        })
    
    def get_recent_icir(self, lookback: int = 3) -> float:
        """获取近期ICIR
        
        设计决策：默认看最近3期，平衡及时性与稳定性。
        与AlphaPROBE不同：他们可能用更复杂的滚动窗口。
        """
        if not self.performance:
            return 1.0  # 默认值
        
        recent = self.performance[-lookback:] if len(self.performance) >= lookback else self.performance
        return np.mean([p.get('icir', 0) for p in recent])
    
    def get_success_rate(self) -> float:
        """计算历史成功率
        
        设计决策：α/(α+β)就是后验期望的成功概率。
        这是Thompson Sampling的核心。
        """
        return self.alpha / (self.alpha + self.beta) if (self.alpha + self.beta) > 0 else 0.5


class MVPBayesianSelector:
    """MVP贝叶斯因子选择器
    
    核心功能：
    1. 使用Thompson Sampling选择因子
    2. 根据表现更新贝叶斯参数
    3. 区分选中和没选中因子的评价标准
    
    设计决策：先实现最简版本，验证算法可行性。
    """
    
    def __init__(self, factors: List[Factor], target_size: int = 50, 
                 config: Optional[Dict] = None):
        """初始化
        
        参数：
            factors: 所有因子列表
            target_size: 需要选择的因子数量
            config: 配置参数（MVP阶段简化）
            
        设计决策：使用字典存储因子便于查找，同时保留列表顺序。
        """
        self.factors = {f.id: f for f in factors}
        self.target_size = target_size
        self.config = config or self._get_default_config()
        self.selected_history = []  # 历史选择记录
        self.performance_history = []  # 历史表现记录
        
    def _get_default_config(self) -> Dict:
        """获取默认配置
        
        设计决策：硬编码默认值，便于快速测试。
        后续应该从配置文件读取。
        """
        return {
            # 采样打分权重
            'scoring_weights': {
                'bayesian': 0.7,      # 贝叶斯部分权重
                'recent_perf': 0.3,   # 近期表现权重
            },
            # 成功阈值
            'success_thresholds': {
                'selected_icir': 0.8,      # 选中因子ICIR阈值
                'selected_rank': 0.7,      # 选中因子排名阈值（前70%）
                'unselected_icir': 1.5,    # 没选中因子ICIR阈值（更严格）
                'unselected_corr': 0.6,    # 没选中因子相关性阈值
            },
            # 时间窗口
            'time_windows': {
                'recent_performance': 3,  # 近期表现回看期数
            }
        }
    
    def select_factors(self, current_date: str) -> List[str]:
        """选择因子 - Thompson Sampling实现
        
        算法步骤：
        1. 为每个候选因子计算综合得分
        2. 选择得分最高的K个因子
        
        设计决策：使用Thompson Sampling平衡利用与探索。
        与AlphaPROBE相同：都使用Beta分布采样。
        """
        selected = []
        candidate_ids = list(self.factors.keys())
        
        print(f"[{current_date}] 开始选择因子，目标数量: {self.target_size}")
        
        while len(selected) < self.target_size and candidate_ids:
            scores = {}
            
            for fid in candidate_ids:
                if fid in selected:
                    continue
                    
                factor = self.factors[fid]
                
                # 1. 贝叶斯部分：从后验Beta分布采样
                # 这是Thompson Sampling的核心
                bayesian_score = np.random.beta(factor.alpha, factor.beta)
                
                # 2. 近期表现部分
                recent_icir = factor.get_recent_icir(
                    self.config['time_windows']['recent_performance']
                )
                recent_score = self._normalize_icir_score(recent_icir)
                
                # 3. 综合得分
                weights = self.config['scoring_weights']
                total_score = (
                    weights['bayesian'] * bayesian_score + 
                    weights['recent_perf'] * recent_score
                )
                
                scores[fid] = {
                    'total': total_score,
                    'bayesian': bayesian_score,
                    'recent': recent_score,
                    'recent_icir': recent_icir,
                    'success_rate': factor.get_success_rate()
                }
            
            if scores:
                # 选择得分最高的因子
                best_id = max(scores, key=lambda fid: scores[fid]['total'])
                selected.append(best_id)
                candidate_ids.remove(best_id)
                
                # 输出调试信息（前几个选择）
                if len(selected) <= 3:
                    score_info = scores[best_id]
                    print(f"  选择 {best_id}: 总分={score_info['total']:.3f}, "
                          f"贝叶斯={score_info['bayesian']:.3f}, "
                          f"近期ICIR={score_info['recent_icir']:.3f}")
            else:
                break
        
        # 记录选择历史
        self.selected_history.append({
            'date': current_date,
            'selected': selected.copy(),
            'total_candidates': len(self.factors)
        })
        
        print(f"[{current_date}] 选择完成，实际选择: {len(selected)} 个因子")
        return selected
    
    def update_from_performance(self, selected_ids: List[str], 
                                performance_data: Dict[str, Dict]) -> None:
        """根据表现更新贝叶斯参数
        
        这是学习过程的核心：
        1. 对于选中因子：基于实际表现更新
        2. 对于没选中因子：基于边际贡献（模拟）更新
        
        设计决策：区分选中和没选中因子，使用不同标准。
        这是我们的创新点之一。
        """
        print(f"开始更新贝叶斯参数，选中因子: {len(selected_ids)} 个")
        
        update_stats = {'selected_success': 0, 'selected_failure': 0,
                       'unselected_success': 0}
        
        for fid, factor in self.factors.items():
            if fid in selected_ids:
                # 选中因子：基于实际表现更新
                perf = performance_data.get(fid, {})
                success = self._evaluate_selected_success(factor, perf)
                
                if success:
                    factor.alpha += 1
                    update_stats['selected_success'] += 1
                else:
                    factor.beta += 1
                    update_stats['selected_failure'] += 1
                    
                # 记录更新详情
                if fid in list(self.factors.keys())[:3]:  # 只记录前3个
                    print(f"  更新选中因子 {fid}: 成功={success}, "
                          f"新参数: α={factor.alpha:.1f}, β={factor.beta:.1f}")
            else:
                # 没选中因子：基于边际贡献更新
                success = self._evaluate_unselected_success(
                    factor, selected_ids, performance_data
                )
                
                if success:
                    factor.alpha += 1  # 只增加α，不轻易增加β
                    update_stats['unselected_success'] += 1
        
        # 记录表现历史
        self.performance_history.append({
            'date': 'latest',  # 实际应该有日期
            'update_stats': update_stats,
            'avg_success_rate': np.mean([f.get_success_rate() for f in self.factors.values()])
        })
        
        print(f"更新完成: 选中成功={update_stats['selected_success']}, "
              f"选中失败={update_stats['selected_failure']}, "
              f"没选中成功={update_stats['unselected_success']}")
    
    def _evaluate_selected_success(self, factor: Factor, 
                                   performance: Dict) -> bool:
        """评估选中因子是否成功
        
        设计决策：相对宽松的标准，因为已经被选中。
        后续可以扩展更多维度。
        """
        thresholds = self.config['success_thresholds']
        
        icir = performance.get('icir', 0)
        rank = performance.get('rank_percentile', 1.0)  # 1.0是最差
        
        # 简单标准：ICIR > 阈值 且排名在前X%
        success = (
            icir > thresholds['selected_icir'] and 
            rank < thresholds['selected_rank']
        )
        
        return success
    
    def _evaluate_unselected_success(self, factor: Factor, 
                                     selected_ids: List[str], 
                                     performance_data: Dict) -> bool:
        """评估没选中因子是否成功（边际贡献法）
        
        设计决策：非常严格的标准，因为没被选中。
        核心思想：如果这个因子很好但没被选中，系统可能"错过"了。
        
        与AlphaPROBE不同：他们主要评估选中因子。
        这是我们的创新点：为没选中因子设计评价标准。
        """
        thresholds = self.config['success_thresholds']
        
        # 1. 近期ICIR必须很高
        recent_icir = factor.get_recent_icir()
        if recent_icir < thresholds['unselected_icir']:
            return False
        
        # 2. 与选中因子的平均相关性不能太高
        # （简化：这里用随机模拟，实际应从历史数据计算）
        avg_correlation = self._estimate_average_correlation(factor, selected_ids)
        if avg_correlation > thresholds['unselected_corr']:
            return False
        
        # 3. 模拟边际贡献（简化版）
        # 实际应该计算加入后的组合改善
        marginal_improvement = self._simulate_marginal_improvement(
            factor, selected_ids
        )
        
        # 成功：ICIR高、相关性低、有正边际贡献
        success = (
            recent_icir > thresholds['unselected_icir'] and
            avg_correlation < thresholds['unselected_corr'] and
            marginal_improvement > 0
        )
        
        return success
    
    def _normalize_icir_score(self, icir: float) -> float:
        """标准化ICIR得分到[0,1]区间
        
        设计决策：简单线性归一化，ICIR=3.0时得1.0。
        后续可以用更复杂的函数（如sigmoid）。
        """
        return min(max(icir / 3.0, 0.0), 1.0)
    
    def _estimate_average_correlation(self, factor: Factor, 
                                      selected_ids: List[str]) -> float:
        """估计与选中因子的平均相关性
        
        设计决策：MVP阶段用随机数模拟。
        后续应从历史数据计算真实相关性。
        """
        # 简化：随机生成，但保持一定模式
        # 实际应该从因子值时间序列计算
        np.random.seed(hash(factor.id) % 1000)  # 固定随机种子，使结果可重复
        return np.random.uniform(0.2, 0.8)
    
    def _simulate_marginal_improvement(self, factor: Factor, 
                                       selected_ids: List[str]) -> float:
        """模拟边际贡献（简化版）
        
        设计决策：MVP阶段简单模拟。
        后续应实现完整的边际贡献评估。
        """
        # 简化：基于ICIR和相关性估计
        recent_icir = factor.get_recent_icir()
        
        # 估计与选中因子的平均相关性
        avg_corr = self._estimate_average_correlation(factor, selected_ids)
        
        # 简单启发式：ICIR越高、相关性越低，边际贡献越大
        marginal_improvement = recent_icir * (1 - avg_corr) * 0.1
        
        return max(marginal_improvement, 0)
    
    def get_selection_stats(self) -> Dict:
        """获取选择统计信息"""
        if not self.selected_history:
            return {}
        
        latest = self.selected_history[-1]
        return {
            'date': latest['date'],
            'num_selected': len(latest['selected']),
            'num_candidates': latest['total_candidates'],
            'selection_ratio': len(latest['selected']) / latest['total_candidates']
        }
    
    def get_factor_stats(self, top_n: int = 5) -> List[Dict]:
        """获取因子统计信息（前N个）"""
        factors_sorted = sorted(
            self.factors.values(), 
            key=lambda f: f.get_success_rate(), 
            reverse=True
        )[:top_n]
        
        return [
            {
                'id': f.id,
                'topic': f.topic,
                'alpha': f.alpha,
                'beta': f.beta,
                'success_rate': f.get_success_rate(),
                'recent_icir': f.get_recent_icir(),
                'performance_count': len(f.performance)
            }
            for f in factors_sorted
        ]