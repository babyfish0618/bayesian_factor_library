"""
边际贡献评估模块
集成相关性计算和组合模拟，提供完整的边际贡献评估
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Union
import pandas as pd
from dataclasses import dataclass, field
from enum import Enum

# 导入相关模块 (使用绝对导入)
from core.correlation_calculator import CorrelationCalculator
from evaluation.portfolio_simulator import PortfolioSimulator, PortfolioMethod, ReplacementStrategy
from core.factor_enhanced import EnhancedFactor


class EvaluationResult(Enum):
    """评估结果"""
    SUCCESS = "success"          # 成功：应该被选中
    FAILURE = "failure"          # 失败：不应该被选中
    NEUTRAL = "neutral"          # 中性：保持现状
    UNCERTAIN = "uncertain"      # 不确定：需要更多数据


@dataclass
class MarginalContributionResult:
    """边际贡献评估结果"""
    factor_id: str                          # 因子ID
    evaluation: EvaluationResult            # 评估结果
    score: float                           # 边际贡献得分 (0-1)
    improvement: float                     # 边际改善 (夏普比率改善)
    can_replace: bool                      # 是否可以替换现有因子
    replaced_factor: Optional[str] = None  # 被替换的因子ID
    details: Dict = field(default_factory=dict)  # 详细评估信息
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'factor_id': self.factor_id,
            'evaluation': self.evaluation.value,
            'score': self.score,
            'improvement': self.improvement,
            'can_replace': self.can_replace,
            'replaced_factor': self.replaced_factor,
            'details': self.details
        }


class MarginalContributionEvaluator:
    """边际贡献评估器
    
    集成功能：
    1. 计算因子相关性
    2. 模拟组合表现
    3. 评估边际贡献
    4. 提供决策建议
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化边际贡献评估器
        
        参数：
            config: 配置参数
        """
        self.config = config or {
            # 相关性计算配置
            'correlation': {
                'method': 'pearson',
                'min_common_periods': 20,
                'significance_level': 0.05
            },
            # 组合模拟配置
            'portfolio': {
                'method': 'equal_weight',
                'replacement_strategy': 'correlation_based',
                'improvement_threshold': 0.01
            },
            # 评估阈值
            'thresholds': {
                'high_improvement': 0.05,    # 高改善阈值
                'medium_improvement': 0.02,  # 中等改善阈值
                'low_improvement': 0.01,     # 低改善阈值
                'min_score_for_success': 0.7,  # 成功最小得分
                'max_correlation': 0.6       # 最大允许相关性
            }
        }
        
        # 初始化子模块
        self.correlation_calculator = CorrelationCalculator(
            self.config.get('correlation', {})
        )
        
        self.portfolio_simulator = PortfolioSimulator(
            self.config.get('portfolio', {})
        )
        
        # 缓存
        self._cache = {}
    
    def evaluate_factor(
        self,
        candidate_factor: EnhancedFactor,
        selected_factors: List[EnhancedFactor],
        evaluation_date: str,
        lookback_days: int = 60
    ) -> MarginalContributionResult:
        """
        评估单个因子的边际贡献
        
        参数：
            candidate_factor: 候选因子
            selected_factors: 已选中因子列表
            evaluation_date: 评估日期
            lookback_days: 回看天数
        
        返回：
            边际贡献评估结果
        """
        # 生成缓存键
        cache_key = f"{candidate_factor.id}_{evaluation_date}_{lookback_days}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 1. 准备数据
        factor_data = self._prepare_factor_data(
            candidate_factor, selected_factors, evaluation_date, lookback_days
        )
        
        if factor_data is None:
            # 数据不足
            result = MarginalContributionResult(
                factor_id=candidate_factor.id,
                evaluation=EvaluationResult.UNCERTAIN,
                score=0.0,
                improvement=0.0,
                can_replace=False,
                details={'error': 'insufficient_data'}
            )
            self._cache[cache_key] = result
            return result
        
        # 2. 计算相关性
        correlation_results = self._calculate_correlations(factor_data)
        
        # 3. 模拟组合表现
        portfolio_results = self._simulate_portfolios(factor_data, correlation_results)
        
        # 4. 评估边际贡献
        evaluation = self._evaluate_marginal_contribution(
            candidate_factor.id, factor_data, correlation_results, portfolio_results
        )
        
        # 5. 计算综合得分
        score = self._calculate_comprehensive_score(evaluation, correlation_results, portfolio_results)
        
        # 6. 确定评估结果
        final_result = self._determine_evaluation_result(
            candidate_factor.id, score, evaluation, correlation_results
        )
        
        self._cache[cache_key] = final_result
        return final_result
    
    def evaluate_multiple_factors(
        self,
        candidate_factors: List[EnhancedFactor],
        selected_factors: List[EnhancedFactor],
        evaluation_date: str,
        lookback_days: int = 60
    ) -> Dict[str, MarginalContributionResult]:
        """
        评估多个因子的边际贡献
        
        返回：
            每个候选因子的评估结果字典
        """
        results = {}
        
        for factor in candidate_factors:
            result = self.evaluate_factor(
                factor, selected_factors, evaluation_date, lookback_days
            )
            results[factor.id] = result
        
        return results
    
    def _prepare_factor_data(
        self,
        candidate_factor: EnhancedFactor,
        selected_factors: List[EnhancedFactor],
        evaluation_date: str,
        lookback_days: int
    ) -> Optional[Dict]:
        """准备因子数据"""
        # 获取候选因子的近期表现
        candidate_perf = candidate_factor.get_recent_performance(lookback_days, evaluation_date)
        
        if len(candidate_perf) < 20:  # 最少20个有效数据点
            return None
        
        # 提取收益序列和ICIR
        candidate_returns = self._extract_returns(candidate_perf)
        candidate_icir = candidate_factor.calculate_icir(candidate_perf)
        
        # 准备选中因子数据
        selected_data = {}
        selected_returns = {}
        selected_icirs = {}
        
        for factor in selected_factors:
            factor_perf = factor.get_recent_performance(lookback_days, evaluation_date)
            
            if len(factor_perf) >= 20:
                returns = self._extract_returns(factor_perf)
                icir = factor.calculate_icir(factor_perf)
                
                selected_data[factor.id] = {
                    'returns': returns,
                    'icir': icir,
                    'performance': factor_perf
                }
                selected_returns[factor.id] = returns
                selected_icirs[factor.id] = icir
        
        if not selected_data:
            # 没有有效的选中因子数据
            return None
        
        return {
            'candidate': {
                'id': candidate_factor.id,
                'returns': candidate_returns,
                'icir': candidate_icir,
                'performance': candidate_perf
            },
            'selected': selected_data,
            'selected_returns': selected_returns,
            'selected_icirs': selected_icirs,
            'evaluation_date': evaluation_date,
            'lookback_days': lookback_days
        }
    
    def _extract_returns(self, performance_data) -> np.ndarray:
        """从表现数据中提取收益序列"""
        returns = []
        for perf in performance_data:
            if perf.ls_return is not None:
                returns.append(perf.ls_return)
        
        return np.array(returns)
    
    def _calculate_correlations(self, factor_data: Dict) -> Dict:
        """计算相关性"""
        candidate_id = factor_data['candidate']['id']
        candidate_returns = factor_data['candidate']['returns']
        selected_returns = factor_data['selected_returns']
        
        # 合并所有收益序列
        all_returns = {candidate_id: candidate_returns}
        all_returns.update(selected_returns)
        
        # 计算相关性矩阵
        corr_matrix, pvalue_matrix = self.correlation_calculator.calculate_correlation_matrix(
            all_returns
        )
        
        # 计算候选因子与选中因子的平均相关性
        avg_correlation = self.correlation_calculator.calculate_average_correlation(
            candidate_id,
            list(selected_returns.keys()),
            all_returns
        )
        
        return {
            'correlation_matrix': corr_matrix,
            'pvalue_matrix': pvalue_matrix,
            'average_correlation': avg_correlation,
            'max_correlation': avg_correlation.get('max', 0.0)
        }
    
    def _simulate_portfolios(self, factor_data: Dict, correlation_results: Dict) -> Dict:
        """模拟组合表现"""
        candidate_id = factor_data['candidate']['id']
        selected_ids = list(factor_data['selected_returns'].keys())
        
        # 组合模拟需要同时拿到候选因子和已选因子的收益/ICIR
        all_returns = dict(factor_data['selected_returns'])
        all_returns[candidate_id] = factor_data['candidate']['returns']
        
        all_icirs = dict(factor_data['selected_icirs'])
        all_icirs[candidate_id] = factor_data['candidate']['icir']
        
        # 获取组合方法配置
        portfolio_method = self.config['portfolio'].get('method', 'equal_weight')
        replacement_strategy = self.config['portfolio'].get('replacement_strategy', 'correlation_based')
        
        # 评估边际贡献
        marginal_result = self.portfolio_simulator.evaluate_marginal_contribution(
            candidate_id,
            selected_ids,
            all_returns,
            all_icirs,
            correlation_results['correlation_matrix'],
            portfolio_method,
            replacement_strategy
        )
        
        return {
            'marginal_result': marginal_result,
            'portfolio_method': portfolio_method,
            'replacement_strategy': replacement_strategy
        }
    
    def _evaluate_marginal_contribution(
        self,
        candidate_id: str,
        factor_data: Dict,
        correlation_results: Dict,
        portfolio_results: Dict
    ) -> Dict:
        """评估边际贡献"""
        marginal_result = portfolio_results['marginal_result']
        
        # 提取关键指标
        improvement = marginal_result.get('marginal_improvement', 0.0)
        can_replace = marginal_result.get('can_replace', False)
        replaced_factor = marginal_result.get('replaced_factor')
        
        # 获取相关性信息
        avg_correlation = correlation_results['average_correlation'].get('average', 0.0)
        max_correlation = correlation_results['max_correlation']
        
        # 获取候选因子ICIR
        candidate_icir = factor_data['candidate']['icir']
        
        # 计算候选因子单独表现
        candidate_returns = factor_data['candidate']['returns']
        candidate_perf = self.portfolio_simulator._calculate_single_factor_performance(candidate_returns)
        
        return {
            'improvement': improvement,
            'can_replace': can_replace,
            'replaced_factor': replaced_factor,
            'avg_correlation': avg_correlation,
            'max_correlation': max_correlation,
            'candidate_icir': candidate_icir,
            'candidate_sharpe': candidate_perf.get('sharpe', 0.0),
            'candidate_annual_return': candidate_perf.get('annual_return', 0.0),
            'improvement_details': marginal_result.get('improvement_details', {})
        }
    
    def _calculate_comprehensive_score(
        self,
        evaluation: Dict,
        correlation_results: Dict,
        portfolio_results: Dict
    ) -> float:
        """计算综合得分"""
        scores = []
        weights = []
        
        # 1. 边际改善得分 (权重0.4)
        improvement = evaluation['improvement']
        thresholds = self.config.get('thresholds', {})
        high_imp = thresholds.get('high_improvement', 0.05)
        medium_imp = thresholds.get('medium_improvement', 0.02)
        low_imp = thresholds.get('low_improvement', 0.01)

        if improvement >= high_imp:
            improvement_score = 1.0
        elif improvement >= medium_imp:
            improvement_score = 0.7
        elif improvement >= low_imp:
            improvement_score = 0.4
        else:
            improvement_score = 0.1
        
        scores.append(improvement_score)
        weights.append(0.4)
        
        # 2. 相关性得分 (权重0.3)
        max_correlation = evaluation['max_correlation']
        max_allowed = thresholds.get('max_correlation', 0.6)
        
        if max_correlation <= max_allowed * 0.5:
            correlation_score = 1.0
        elif max_correlation <= max_allowed:
            correlation_score = 0.6
        else:
            correlation_score = 0.2
        
        scores.append(correlation_score)
        weights.append(0.3)
        
        # 3. 候选因子质量得分 (权重0.2)
        candidate_icir = evaluation['candidate_icir']
        candidate_sharpe = evaluation['candidate_sharpe']
        
        # ICIR得分
        if candidate_icir >= 2.0:
            icir_score = 1.0
        elif candidate_icir >= 1.0:
            icir_score = 0.7
        elif candidate_icir >= 0.5:
            icir_score = 0.4
        else:
            icir_score = 0.1
        
        # 夏普得分
        if candidate_sharpe >= 2.0:
            sharpe_score = 1.0
        elif candidate_sharpe >= 1.0:
            sharpe_score = 0.7
        elif candidate_sharpe >= 0.5:
            sharpe_score = 0.4
        else:
            sharpe_score = 0.1
        
        quality_score = (icir_score + sharpe_score) / 2
        scores.append(quality_score)
        weights.append(0.2)
        
        # 4. 替换可行性得分 (权重0.1)
        can_replace = evaluation['can_replace']
        feasibility_score = 1.0 if can_replace else 0.3
        scores.append(feasibility_score)
        weights.append(0.1)
        
        # 计算加权平均
        total_score = np.average(scores, weights=weights)
        
        return float(total_score)
    
    def _determine_evaluation_result(
        self,
        factor_id: str,
        score: float,
        evaluation: Dict,
        correlation_results: Dict
    ) -> MarginalContributionResult:
        """确定最终评估结果"""
        thresholds = self.config.get('thresholds', {})
        min_score = thresholds.get('min_score_for_success', 0.7)
        
        improvement = evaluation['improvement']
        can_replace = evaluation['can_replace']
        max_correlation = evaluation['max_correlation']
        max_allowed = thresholds.get('max_correlation', 0.6)
        
        # 决策逻辑
        if score >= min_score and improvement > 0 and max_correlation <= max_allowed:
            evaluation_result = EvaluationResult.SUCCESS
        elif score < 0.3 or improvement < -0.1:
            evaluation_result = EvaluationResult.FAILURE
        elif max_correlation > max_allowed * 1.2:  # 相关性太高
            evaluation_result = EvaluationResult.FAILURE
        else:
            evaluation_result = EvaluationResult.NEUTRAL
        
        # 构建详细结果
        details = {
            'score_breakdown': {
                'total_score': score,
                'min_score_for_success': min_score,
                'improvement': improvement,
                'max_correlation': max_correlation,
                'max_allowed_correlation': max_allowed
            },
            'evaluation_criteria': {
                'score_passed': score >= min_score,
                'improvement_positive': improvement > 0,
                'correlation_acceptable': max_correlation <= max_allowed,
                'can_replace': can_replace
            }
        }
        
        return MarginalContributionResult(
            factor_id=factor_id,
            evaluation=evaluation_result,
            score=score,
            improvement=improvement,
            can_replace=can_replace,
            replaced_factor=evaluation.get('replaced_factor'),
            details=details
        )
    
    def get_evaluation_summary(self, results: Dict[str, MarginalContributionResult]) -> Dict:
        """获取评估摘要"""
        if not results:
            return {}
        
        # 统计结果
        result_counts = {
            'success': 0,
            'failure': 0,
            'neutral': 0,
            'uncertain': 0
        }
        
        scores = []
        improvements = []
        
        for result in results.values():
            result_counts[result.evaluation.value] += 1
            scores.append(result.score)
            improvements.append(result.improvement)
        
        # 找到最佳和最差因子
        if results:
            best_factor = max(results.values(), key=lambda r: r.score)
            worst_factor = min(results.values(), key=lambda r: r.score)
            
            best_improvement = max(results.values(), key=lambda r: r.improvement)
            worst_improvement = min(results.values(), key=lambda r: r.improvement)
        else:
            best_factor = worst_factor = best_improvement = worst_improvement = None
        
        return {
            'total_factors': len(results),
            'result_counts': result_counts,
            'score_stats': {
                'mean': np.mean(scores) if scores else 0.0,
                'std': np.std(scores) if scores else 0.0,
                'min': np.min(scores) if scores else 0.0,
                'max': np.max(scores) if scores else 0.0
            },
            'improvement_stats': {
                'mean': np.mean(improvements) if improvements else 0.0,
                'std': np.std(improvements) if improvements else 0.0,
                'min': np.min(improvements) if improvements else 0.0,
                'max': np.max(improvements) if improvements else 0.0
            },
            'best_factor': {
                'id': best_factor.factor_id if best_factor else None,
                'score': best_factor.score if best_factor else 0.0,
                'improvement': best_factor.improvement if best_factor else 0.0
            },
            'worst_factor': {
                'id': worst_factor.factor_id if worst_factor else None,
                'score': worst_factor.score if worst_factor else 0.0,
                'improvement': worst_factor.improvement if worst_factor else 0.0
            },
            'best_improvement': {
                'id': best_improvement.factor_id if best_improvement else None,
                'improvement': best_improvement.improvement if best_improvement else 0.0,
                'score': best_improvement.score if best_improvement else 0.0
            }
        }
    
    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()
        self.correlation_calculator._cache.clear()


# 测试函数
def test_marginal_contrib_evaluator():
    """测试边际贡献评估器"""
    print("测试边际贡献评估器...")
    
    # 创建测试因子
    np.random.seed(42)
    n_days = 100
    
    # 创建候选因子（好因子）
    candidate_factor = EnhancedFactor(
        factor_id="candidate_001",
        expression="Return(20)",
        topic="momentum"
    )
    
    # 添加表现数据
    dates = [f"2024-01-{i+1:02d}" for i in range(n_days)]
    
    for i, date in enumerate(dates):
        # 好因子：高IC，高收益
        ic = np.random.normal(0.08, 0.02)  # IC均值8%
        ls_return = np.random.normal(0.002, 0.015)  # 日度0.2%收益
        
        candidate_factor.add_daily_performance(
            date=date,
            ic=ic,
            ls_return=ls_return,
            rank_percentile=np.random.uniform(0.1, 0.3)  # 排名前30%
        )
    
    # 创建选中因子
    selected_factors = []
    
    for j in range(3):
        factor = EnhancedFactor(
            factor_id=f"selected_{j:03d}",
            expression=f"Factor_{j}",
            topic="mixed"
        )
        
        for i, date in enumerate(dates):
            # 中等因子
            ic = np.random.normal(0.04 + 0.01 * j, 0.03)
            ls_return = np.random.normal(0.001 + 0.0005 * j, 0.02)
            
            factor.add_daily_performance(
                date=date,
                ic=ic,
                ls_return=ls_return,
                rank_percentile=np.random.uniform(0.3, 0.7)
            )
        
        selected_factors.append(factor)
    
    # 创建评估器
    config = {
        'correlation': {
            'method': 'pearson',
            'min_common_periods': 20
        },
        'portfolio': {
            'method': 'equal_weight',
            'replacement_strategy': 'correlation_based',
            'improvement_threshold': 0.01
        },
        'thresholds': {
            'high_improvement': 0.05,
            'medium_improvement': 0.02,
            'low_improvement': 0.01,
            'min_score_for_success': 0.7,
            'max_correlation': 0.6
        }
    }
    
    evaluator = MarginalContributionEvaluator(config)
    
    # 测试单个因子评估
    print("\n1. 测试单个因子评估:")
    result = evaluator.evaluate_factor(
        candidate_factor, selected_factors, "2024-04-10", lookback_days=60
    )
    
    print(f"   因子ID: {result.factor_id}")
    print(f"   评估结果: {result.evaluation.value}")
    print(f"   综合得分: {result.score:.3f}")
    print(f"   边际改善: {result.improvement:.3f}")
    print(f"   是否可以替换: {result.can_replace}")
    print(f"   替换的因子: {result.replaced_factor}")
    
    # 测试多个因子评估
    print("\n2. 测试多个因子评估:")
    
    # 创建更多候选因子
    candidate_factors = [candidate_factor]
    
    for k in range(2):
        factor = EnhancedFactor(
            factor_id=f"candidate_{k+2:03d}",
            expression=f"Candidate_{k}",
            topic="test"
        )
        
        for i, date in enumerate(dates):
            # 较差因子
            ic = np.random.normal(0.02 - 0.01 * k, 0.04)
            ls_return = np.random.normal(0.0005 - 0.0002 * k, 0.025)
            
            factor.add_daily_performance(
                date=date,
                ic=ic,
                ls_return=ls_return,
                rank_percentile=np.random.uniform(0.5, 0.9)
            )
        
        candidate_factors.append(factor)
    
    results = evaluator.evaluate_multiple_factors(
        candidate_factors, selected_factors, "2024-04-10", lookback_days=60
    )
    
    print(f"   评估了 {len(results)} 个候选因子")
    
    for factor_id, result in results.items():
        print(f"     {factor_id}: {result.evaluation.value}, 得分={result.score:.3f}, "
              f"改善={result.improvement:.3f}")
    
    # 测试评估摘要
    print("\n3. 测试评估摘要:")
    summary = evaluator.get_evaluation_summary(results)
    
    print(f"   总因子数: {summary['total_factors']}")
    print(f"   结果统计: {summary['result_counts']}")
    print(f"   得分统计: 均值={summary['score_stats']['mean']:.3f}, "
          f"范围={summary['score_stats']['min']:.3f}-{summary['score_stats']['max']:.3f}")
    print(f"   改善统计: 均值={summary['improvement_stats']['mean']:.3f}, "
          f"范围={summary['improvement_stats']['min']:.3f}-{summary['improvement_stats']['max']:.3f}")
    
    if summary['best_factor']['id']:
        print(f"   最佳因子: {summary['best_factor']['id']} "
              f"(得分={summary['best_factor']['score']:.3f})")
    
    # 测试缓存
    print("\n4. 测试缓存:")
    result1 = evaluator.evaluate_factor(
        candidate_factor, selected_factors, "2024-04-10", lookback_days=60
    )
    
    # 应该从缓存获取
    result2 = evaluator.evaluate_factor(
        candidate_factor, selected_factors, "2024-04-10", lookback_days=60
    )
    
    print(f"   两次评估结果相同: {result1.score == result2.score}")
    
    # 清除缓存
    evaluator.clear_cache()
    result3 = evaluator.evaluate_factor(
        candidate_factor, selected_factors, "2024-04-10", lookback_days=60
    )
    
    print(f"   清除缓存后重新计算: {result3.score:.3f}")
    
    print("\n测试完成!")


if __name__ == "__main__":
    test_marginal_contrib_evaluator()
