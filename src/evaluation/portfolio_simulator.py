"""
组合模拟模块
用于模拟因子组合的表现，评估边际贡献
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Union
import pandas as pd
from dataclasses import dataclass, field
from enum import Enum


class PortfolioMethod(Enum):
    """组合构建方法"""
    EQUAL_WEIGHT = "equal_weight"          # 等权组合
    ICIR_WEIGHTED = "icir_weighted"        # ICIR加权
    SHARPE_OPTIMIZED = "sharpe_optimized"  # 夏普优化
    RISK_PARITY = "risk_parity"            # 风险平价
    MIN_VARIANCE = "min_variance"          # 最小方差


class ReplacementStrategy(Enum):
    """因子替换策略"""
    CORRELATION_BASED = "correlation_based"      # 基于相关性替换
    EFFECTIVENESS_BASED = "effectiveness_based"  # 基于有效性替换
    PORTFOLIO_OPTIMIZATION = "portfolio_optimization"  # 组合优化替换


@dataclass
class PortfolioResult:
    """组合模拟结果"""
    weights: Dict[str, float]               # 因子权重
    returns: np.ndarray                     # 组合收益序列
    total_return: float                     # 总收益
    annual_return: float                    # 年化收益
    volatility: float                       # 波动率
    sharpe: float                           # 夏普比率
    max_drawdown: float                     # 最大回撤
    win_rate: float                         # 胜率
    turnover: Optional[float] = None        # 换手率
    factor_count: int = 0                   # 因子数量
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'weights': self.weights,
            'total_return': self.total_return,
            'annual_return': self.annual_return,
            'volatility': self.volatility,
            'sharpe': self.sharpe,
            'max_drawdown': self.max_drawdown,
            'win_rate': self.win_rate,
            'turnover': self.turnover,
            'factor_count': self.factor_count
        }


class PortfolioSimulator:
    """组合模拟器
    
    功能：
    1. 构建不同权重的因子组合
    2. 模拟组合表现
    3. 评估因子边际贡献
    4. 支持因子替换策略
    """

    _DEFAULT_CONFIG = {
        'portfolio_method': 'equal_weight',
        'replacement_strategy': 'correlation_based',
        'improvement_threshold': 0.01,
        'annualization_factor': 250,  # 年化因子（默认与主流程统一）
        'risk_free_rate': 0.02,       # 无风险利率
        'max_weight': 0.3,            # 最大单因子权重
        'min_weight': 0.01            # 最小单因子权重
    }

    def __init__(self, config: Optional[Dict] = None):
        """
        初始化组合模拟器
        
        参数：
            config: 配置参数（缺失的键将使用默认值）
        """
        self.config = {**self._DEFAULT_CONFIG, **(config or {})}
    
    def build_portfolio(
        self,
        factor_ids: List[str],
        factor_returns: Dict[str, np.ndarray],
        factor_icirs: Optional[Dict[str, float]] = None,
        factor_correlations: Optional[pd.DataFrame] = None,
        method: Union[str, PortfolioMethod] = PortfolioMethod.EQUAL_WEIGHT
    ) -> PortfolioResult:
        """
        构建因子组合
        
        参数：
            factor_ids: 因子ID列表
            factor_returns: 因子收益字典 {factor_id: returns_array}
            factor_icirs: 因子ICIR字典 {factor_id: icir} (用于加权)
            factor_correlations: 因子相关性矩阵 (用于优化)
            method: 组合构建方法
        
        返回：
            组合结果
        """
        if isinstance(method, str):
            method = PortfolioMethod(method)
        
        # 检查数据
        self._validate_inputs(factor_ids, factor_returns, factor_icirs, factor_correlations)
        
        # 对齐收益序列
        aligned_returns, common_dates = self._align_returns(factor_ids, factor_returns)
        
        # 计算权重
        if method == PortfolioMethod.EQUAL_WEIGHT:
            weights = self._calculate_equal_weights(factor_ids)
        elif method == PortfolioMethod.ICIR_WEIGHTED:
            weights = self._calculate_icir_weights(factor_ids, factor_icirs)
        elif method == PortfolioMethod.SHARPE_OPTIMIZED:
            weights = self._calculate_sharpe_optimized_weights(
                factor_ids, aligned_returns, factor_correlations
            )
        elif method == PortfolioMethod.RISK_PARITY:
            weights = self._calculate_risk_parity_weights(
                factor_ids, aligned_returns, factor_correlations
            )
        elif method == PortfolioMethod.MIN_VARIANCE:
            weights = self._calculate_min_variance_weights(
                factor_ids, aligned_returns, factor_correlations
            )
        else:
            raise ValueError(f"不支持的组合方法: {method}")
        
        # 计算组合收益
        portfolio_returns = self._calculate_portfolio_returns(aligned_returns, weights)
        
        # 计算表现指标
        result = self._calculate_performance_metrics(
            portfolio_returns, weights, factor_ids
        )
        
        return result
    
    def evaluate_marginal_contribution(
        self,
        candidate_factor_id: str,
        selected_factor_ids: List[str],
        factor_returns: Dict[str, np.ndarray],
        factor_icirs: Dict[str, float],
        factor_correlations: pd.DataFrame,
        portfolio_method: str = "equal_weight",
        replacement_strategy: str = "correlation_based"
    ) -> Dict[str, float]:
        """
        评估候选因子的边际贡献
        
        参数：
            candidate_factor_id: 候选因子ID
            selected_factor_ids: 已选中因子ID列表
            factor_returns: 因子收益字典
            factor_icirs: 因子ICIR字典
            factor_correlations: 因子相关性矩阵
            portfolio_method: 组合构建方法
            replacement_strategy: 替换策略
        
        返回：
            边际贡献评估结果
        """
        # 1. 构建基准组合（只有选中因子）
        if not selected_factor_ids:
            # 如果没有选中因子，边际贡献就是单独表现
            candidate_returns = factor_returns.get(candidate_factor_id)
            if candidate_returns is None or len(candidate_returns) == 0:
                return {'marginal_improvement': 0.0, 'can_replace': False}
            
            candidate_perf = self._calculate_single_factor_performance(candidate_returns)
            return {
                'marginal_improvement': candidate_perf['sharpe'],
                'can_replace': True,
                'replaced_factor': None,
                'improvement_details': {'sharpe': candidate_perf['sharpe']}
            }
        
        # 构建基准组合
        try:
            baseline_result = self.build_portfolio(
                selected_factor_ids,
                factor_returns,
                factor_icirs,
                factor_correlations,
                portfolio_method
            )
        except Exception as e:
            print(f"构建基准组合失败: {e}")
            return {'marginal_improvement': 0.0, 'can_replace': False}
        
        # 2. 根据替换策略决定如何加入候选因子
        if replacement_strategy == "correlation_based":
            # 基于相关性替换：替换与候选因子最相关的选中因子
            replacement_result = self._evaluate_correlation_replacement(
                candidate_factor_id, selected_factor_ids,
                baseline_result, factor_returns, factor_icirs,
                factor_correlations, portfolio_method
            )
        elif replacement_strategy == "effectiveness_based":
            # 基于有效性替换：替换表现最差的选中因子
            replacement_result = self._evaluate_effectiveness_replacement(
                candidate_factor_id, selected_factor_ids,
                baseline_result, factor_returns, factor_icirs,
                factor_correlations, portfolio_method
            )
        elif replacement_strategy == "portfolio_optimization":
            # 组合优化：直接优化包含候选因子的组合
            replacement_result = self._evaluate_portfolio_optimization(
                candidate_factor_id, selected_factor_ids,
                factor_returns, factor_icirs,
                factor_correlations, portfolio_method
            )
        else:
            raise ValueError(f"不支持的替换策略: {replacement_strategy}")
        
        # 3. 计算边际改善
        marginal_improvement = self._calculate_marginal_improvement(
            baseline_result, replacement_result
        )
        
        return {
            'marginal_improvement': marginal_improvement,
            'can_replace': marginal_improvement > self.config['improvement_threshold'],
            'replaced_factor': replacement_result.get('replaced_factor'),
            'improvement_details': replacement_result.get('improvement_details', {}),
            'baseline_sharpe': baseline_result.sharpe,
            'new_sharpe': replacement_result.get('new_sharpe', baseline_result.sharpe)
        }
    
    def _validate_inputs(self, factor_ids, factor_returns, factor_icirs, factor_correlations):
        """验证输入数据"""
        if not factor_ids:
            raise ValueError("因子ID列表不能为空")
        
        for fid in factor_ids:
            if fid not in factor_returns:
                raise ValueError(f"因子 {fid} 的收益数据不存在")
        
        if factor_icirs is not None:
            for fid in factor_ids:
                if fid not in factor_icirs:
                    raise ValueError(f"因子 {fid} 的ICIR数据不存在")
    
    def _align_returns(self, factor_ids, factor_returns):
        """对齐收益序列"""
        # 找到所有因子都有数据的日期
        all_dates = []
        returns_by_date = {}
        
        # 这里简化处理，实际应该按日期对齐
        # 假设所有因子收益序列长度相同
        min_length = min(len(factor_returns[fid]) for fid in factor_ids)
        
        aligned_returns = {}
        for fid in factor_ids:
            aligned_returns[fid] = factor_returns[fid][:min_length]
        
        return aligned_returns, list(range(min_length))
    
    def _calculate_equal_weights(self, factor_ids):
        """计算等权权重"""
        n_factors = len(factor_ids)
        weight = 1.0 / n_factors
        return {fid: weight for fid in factor_ids}
    
    def _calculate_icir_weights(self, factor_ids, factor_icirs):
        """计算ICIR加权权重"""
        if factor_icirs is None:
            return self._calculate_equal_weights(factor_ids)
        
        # 提取ICIR值
        icir_values = [max(factor_icirs.get(fid, 0), 0) for fid in factor_ids]
        
        # 避免除零
        total_icir = sum(icir_values)
        if total_icir < 1e-8:
            return self._calculate_equal_weights(factor_ids)
        
        # 计算权重
        weights = {}
        for fid, icir in zip(factor_ids, icir_values):
            weights[fid] = icir / total_icir
        
        return weights
    
    def _calculate_sharpe_optimized_weights(self, factor_ids, aligned_returns, factor_correlations):
        """计算夏普优化权重（简化版）"""
        # 这里实现简化的均值-方差优化
        # 实际应该使用更复杂的优化算法
        
        n_factors = len(factor_ids)
        
        # 计算预期收益（用历史均值）
        expected_returns = np.zeros(n_factors)
        for i, fid in enumerate(factor_ids):
            returns = aligned_returns[fid]
            expected_returns[i] = np.mean(returns) * self.config['annualization_factor']
        
        # 计算协方差矩阵
        if factor_correlations is not None and len(factor_ids) == factor_correlations.shape[0]:
            # 使用提供的相关性矩阵
            corr_matrix = factor_correlations.values
            # 还需要波动率数据，这里简化
            volatilities = np.ones(n_factors) * 0.15  # 假设15%波动率
            cov_matrix = np.outer(volatilities, volatilities) * corr_matrix
        else:
            # 从收益序列计算协方差
            returns_matrix = np.column_stack([aligned_returns[fid] for fid in factor_ids])
            cov_matrix = np.cov(returns_matrix, rowvar=False) * self.config['annualization_factor']
        
        # 简化的优化：最大化夏普比率
        # 实际应该使用二次规划
        try:
            # 使用均值-方差优化（马科维茨）
            inv_cov = np.linalg.inv(cov_matrix + np.eye(n_factors) * 1e-6)  # 正则化
            ones = np.ones(n_factors)
            
            # 计算最优权重
            w = inv_cov @ expected_returns
            w = w / np.sum(np.abs(w))  # 归一化
            
            # 转换为字典
            weights = {fid: float(w[i]) for i, fid in enumerate(factor_ids)}
            
            # 应用权重限制
            weights = self._apply_weight_constraints(weights)
            
            return weights
            
        except Exception as e:
            print(f"夏普优化失败，使用等权: {e}")
            return self._calculate_equal_weights(factor_ids)
    
    def _calculate_risk_parity_weights(self, factor_ids, aligned_returns, factor_correlations):
        """计算风险平价权重（简化版）"""
        # 这里实现简化的风险平价
        n_factors = len(factor_ids)
        
        # 计算波动率
        volatilities = np.zeros(n_factors)
        for i, fid in enumerate(factor_ids):
            returns = aligned_returns[fid]
            volatilities[i] = np.std(returns) * np.sqrt(self.config['annualization_factor'])
        
        # 风险平价：权重与波动率成反比
        inv_vol = 1.0 / (volatilities + 1e-8)
        total_inv_vol = np.sum(inv_vol)
        
        weights = {}
        for i, fid in enumerate(factor_ids):
            weights[fid] = inv_vol[i] / total_inv_vol
        
        return weights
    
    def _calculate_min_variance_weights(self, factor_ids, aligned_returns, factor_correlations):
        """计算最小方差权重（简化版）"""
        n_factors = len(factor_ids)
        
        # 计算协方差矩阵
        returns_matrix = np.column_stack([aligned_returns[fid] for fid in factor_ids])
        cov_matrix = np.cov(returns_matrix, rowvar=False)
        
        try:
            # 最小方差组合：权重与协方差矩阵的逆相关
            inv_cov = np.linalg.inv(cov_matrix + np.eye(n_factors) * 1e-6)
            ones = np.ones(n_factors)
            
            w = inv_cov @ ones
            w = w / np.sum(w)
            
            weights = {fid: float(w[i]) for i, fid in enumerate(factor_ids)}
            weights = self._apply_weight_constraints(weights)
            
            return weights
            
        except Exception as e:
            print(f"最小方差优化失败，使用等权: {e}")
            return self._calculate_equal_weights(factor_ids)
    
    def _apply_weight_constraints(self, weights):
        """应用权重约束"""
        max_weight = self.config.get('max_weight', 0.3)
        min_weight = self.config.get('min_weight', 0.01)
        
        constrained_weights = {}
        
        for fid, weight in weights.items():
            # 限制权重范围
            constrained_weight = max(min(weight, max_weight), min_weight)
            constrained_weights[fid] = constrained_weight
        
        # 重新归一化
        total_weight = sum(constrained_weights.values())
        if total_weight > 1e-8:
            for fid in constrained_weights:
                constrained_weights[fid] /= total_weight
        
        return constrained_weights
    
    def _calculate_portfolio_returns(self, aligned_returns, weights):
        """计算组合收益"""
        n_periods = len(next(iter(aligned_returns.values())))
        portfolio_returns = np.zeros(n_periods)
        
        for fid, weight in weights.items():
            if fid in aligned_returns:
                portfolio_returns += weight * aligned_returns[fid]
        
        return portfolio_returns
    
    def _calculate_performance_metrics(self, portfolio_returns, weights, factor_ids):
        """计算表现指标"""
        n_periods = len(portfolio_returns)
        
        if n_periods == 0:
            return PortfolioResult(
                weights=weights,
                returns=np.array([]),
                total_return=0.0,
                annual_return=0.0,
                volatility=0.0,
                sharpe=0.0,
                max_drawdown=0.0,
                win_rate=0.0,
                factor_count=len(factor_ids)
            )
        
        # 总收益
        total_return = np.prod(1 + portfolio_returns) - 1
        
        # 年化收益
        annual_return = (1 + total_return) ** (self.config['annualization_factor'] / n_periods) - 1
        
        # 波动率
        volatility = np.std(portfolio_returns) * np.sqrt(self.config['annualization_factor'])
        
        # 夏普比率
        risk_free_rate = self.config.get('risk_free_rate', 0.02)
        excess_return = annual_return - risk_free_rate
        sharpe = excess_return / (volatility + 1e-8)
        
        # 最大回撤
        cumulative = np.cumprod(1 + portfolio_returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdown)
        
        # 胜率
        win_rate = np.sum(portfolio_returns > 0) / n_periods
        
        return PortfolioResult(
            weights=weights,
            returns=portfolio_returns,
            total_return=float(total_return),
            annual_return=float(annual_return),
            volatility=float(volatility),
            sharpe=float(sharpe),
            max_drawdown=float(max_drawdown),
            win_rate=float(win_rate),
            factor_count=len(factor_ids)
        )
    
    def _calculate_single_factor_performance(self, returns):
        """计算单因子表现"""
        n_periods = len(returns)
        
        if n_periods == 0:
            return {
                'total_return': 0.0,
                'annual_return': 0.0,
                'volatility': 0.0,
                'sharpe': 0.0,
                'max_drawdown': 0.0,
                'win_rate': 0.0
            }
        
        total_return = np.prod(1 + returns) - 1
        annual_return = (1 + total_return) ** (self.config['annualization_factor'] / n_periods) - 1
        volatility = np.std(returns) * np.sqrt(self.config['annualization_factor'])
        
        risk_free_rate = self.config.get('risk_free_rate', 0.02)
        excess_return = annual_return - risk_free_rate
        sharpe = excess_return / (volatility + 1e-8)
        
        cumulative = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = np.min(drawdown)
        
        win_rate = np.sum(returns > 0) / n_periods
        
        return {
            'total_return': float(total_return),
            'annual_return': float(annual_return),
            'volatility': float(volatility),
            'sharpe': float(sharpe),
            'max_drawdown': float(max_drawdown),
            'win_rate': float(win_rate)
        }
    
    def _evaluate_correlation_replacement(self, candidate_id, selected_ids,
                                         baseline_result, factor_returns,
                                         factor_icirs, factor_correlations,
                                         portfolio_method):
        """基于相关性的替换评估"""
        # 找到与候选因子最相关的选中因子
        if candidate_id not in factor_correlations.index:
            return {'new_sharpe': baseline_result.sharpe, 'replaced_factor': None}
        
        candidate_correlations = factor_correlations.loc[candidate_id]
        
        max_correlation = -1
        most_correlated = None
        
        for fid in selected_ids:
            if fid in candidate_correlations:
                corr = abs(candidate_correlations[fid])
                if corr > max_correlation:
                    max_correlation = corr
                    most_correlated = fid
        
        if most_correlated is None:
            return {'new_sharpe': baseline_result.sharpe, 'replaced_factor': None}
        
        # 替换最相关的因子
        new_selected = [fid for fid in selected_ids if fid != most_correlated]
        new_selected.append(candidate_id)
        
        try:
            new_result = self.build_portfolio(
                new_selected, factor_returns, factor_icirs,
                factor_correlations, portfolio_method
            )
            
            return {
                'new_sharpe': new_result.sharpe,
                'replaced_factor': most_correlated,
                'improvement_details': {
                    'replaced_factor': most_correlated,
                    'correlation_with_replaced': max_correlation,
                    'new_portfolio_size': len(new_selected)
                }
            }
            
        except Exception as e:
            print(f"相关性替换评估失败: {e}")
            return {'new_sharpe': baseline_result.sharpe, 'replaced_factor': None}
    
    def _evaluate_effectiveness_replacement(self, candidate_id, selected_ids,
                                           baseline_result, factor_returns,
                                           factor_icirs, factor_correlations,
                                           portfolio_method):
        """基于有效性的替换评估"""
        # 找到表现最差的选中因子
        worst_performance = float('inf')
        worst_factor = None
        
        for fid in selected_ids:
            if fid in factor_icirs:
                icir = factor_icirs[fid]
                if icir < worst_performance:
                    worst_performance = icir
                    worst_factor = fid
        
        if worst_factor is None:
            return {'new_sharpe': baseline_result.sharpe, 'replaced_factor': None}
        
        # 替换表现最差的因子
        new_selected = [fid for fid in selected_ids if fid != worst_factor]
        new_selected.append(candidate_id)
        
        try:
            new_result = self.build_portfolio(
                new_selected, factor_returns, factor_icirs,
                factor_correlations, portfolio_method
            )
            
            return {
                'new_sharpe': new_result.sharpe,
                'replaced_factor': worst_factor,
                'improvement_details': {
                    'replaced_factor': worst_factor,
                    'replaced_icir': worst_performance,
                    'candidate_icir': factor_icirs.get(candidate_id, 0),
                    'new_portfolio_size': len(new_selected)
                }
            }
            
        except Exception as e:
            print(f"有效性替换评估失败: {e}")
            return {'new_sharpe': baseline_result.sharpe, 'replaced_factor': None}
    
    def _evaluate_portfolio_optimization(self, candidate_id, selected_ids,
                                        factor_returns, factor_icirs,
                                        factor_correlations, portfolio_method):
        """基于组合优化的替换评估"""
        # 构建包含候选因子的新组合
        new_selected = selected_ids.copy()
        new_selected.append(candidate_id)
        
        try:
            new_result = self.build_portfolio(
                new_selected, factor_returns, factor_icirs,
                factor_correlations, portfolio_method
            )
            
            return {
                'new_sharpe': new_result.sharpe,
                'replaced_factor': None,  # 没有替换，只是添加
                'improvement_details': {
                    'action': 'add',
                    'new_portfolio_size': len(new_selected),
                    'candidate_weight': new_result.weights.get(candidate_id, 0)
                }
            }
            
        except Exception as e:
            print(f"组合优化评估失败: {e}")
            return {'new_sharpe': 0.0, 'replaced_factor': None}
    
    def _calculate_marginal_improvement(self, baseline_result, replacement_result):
        """计算边际改善"""
        baseline_sharpe = baseline_result.sharpe
        new_sharpe = replacement_result.get('new_sharpe', baseline_sharpe)
        
        return new_sharpe - baseline_sharpe


# 测试函数
def test_portfolio_simulator():
    """测试组合模拟器"""
    print("测试组合模拟器...")
    
    # 创建测试数据
    np.random.seed(42)
    n_days = 100
    n_factors = 5
    
    # 生成因子收益
    factor_returns = {}
    factor_icirs = {}
    
    for i in range(n_factors):
        factor_id = f"F{i:03d}"
        
        # 生成收益序列
        base_return = 0.001  # 日度0.1%
        volatility = 0.02    # 日度2%
        
        # 使不同因子有不同表现
        if i == 0:
            # 好因子：高收益低波动
            returns = np.random.normal(base_return * 1.5, volatility * 0.8, n_days)
            icir = 2.0
        elif i == 1:
            # 中等因子
            returns = np.random.normal(base_return, volatility, n_days)
            icir = 1.0
        else:
            # 差因子：低收益高波动
            returns = np.random.normal(base_return * 0.5, volatility * 1.2, n_days)
            icir = 0.5
        
        factor_returns[factor_id] = returns
        factor_icirs[factor_id] = icir
    
    # 生成相关性矩阵
    factor_ids = list(factor_returns.keys())
    corr_matrix = pd.DataFrame(
        np.eye(n_factors) * 0.3 + 0.7,  # 对角线1，其他0.3
        index=factor_ids,
        columns=factor_ids
    )
    
    # 创建模拟器
    config = {
        'portfolio_method': 'equal_weight',
        'replacement_strategy': 'correlation_based',
        'improvement_threshold': 0.01,
        'annualization_factor': 252,
        'risk_free_rate': 0.02
    }
    
    simulator = PortfolioSimulator(config)
    
    # 测试组合构建
    print("\n1. 测试组合构建:")
    selected_ids = ["F000", "F001", "F002"]
    
    result = simulator.build_portfolio(
        selected_ids, factor_returns, factor_icirs, corr_matrix, "equal_weight"
    )
    
    print(f"   组合包含 {result.factor_count} 个因子")
    print(f"   年化收益: {result.annual_return:.2%}")
    print(f"   波动率: {result.volatility:.2%}")
    print(f"   夏普比率: {result.sharpe:.3f}")
    print(f"   最大回撤: {result.max_drawdown:.2%}")
    print(f"   权重: {result.weights}")
    
    # 测试ICIR加权组合
    print("\n2. 测试ICIR加权组合:")
    result_icir = simulator.build_portfolio(
        selected_ids, factor_returns, factor_icirs, corr_matrix, "icir_weighted"
    )
    
    print(f"   年化收益: {result_icir.annual_return:.2%}")
    print(f"   夏普比率: {result_icir.sharpe:.3f}")
    print(f"   权重: {result_icir.weights}")
    
    # 测试边际贡献评估
    print("\n3. 测试边际贡献评估:")
    candidate_id = "F003"
    selected_ids = ["F000", "F001", "F002"]
    
    marginal_result = simulator.evaluate_marginal_contribution(
        candidate_id, selected_ids, factor_returns,
        factor_icirs, corr_matrix, "equal_weight", "correlation_based"
    )
    
    print(f"   候选因子: {candidate_id}")
    print(f"   边际改善: {marginal_result['marginal_improvement']:.3f}")
    print(f"   是否可以替换: {marginal_result['can_replace']}")
    print(f"   替换的因子: {marginal_result.get('replaced_factor')}")
    print(f"   基准夏普: {marginal_result.get('baseline_sharpe', 0):.3f}")
    print(f"   新夏普: {marginal_result.get('new_sharpe', 0):.3f}")
    
    # 测试不同替换策略
    print("\n4. 测试不同替换策略:")
    strategies = ["correlation_based", "effectiveness_based", "portfolio_optimization"]
    
    for strategy in strategies:
        result = simulator.evaluate_marginal_contribution(
            candidate_id, selected_ids, factor_returns,
            factor_icirs, corr_matrix, "equal_weight", strategy
        )
        
        print(f"   策略 {strategy}: 改善={result['marginal_improvement']:.3f}, "
              f"可替换={result['can_replace']}")
    
    print("\n测试完成!")


if __name__ == "__main__":
    test_portfolio_simulator()
