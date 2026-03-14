"""
新版贝叶斯选择器 (V2)。

职责:
1. 基于多窗口统计 + Thompson Sampling 进行因子选择。
2. 基于新增观测更新已选因子的后验参数。
3. 对未选因子执行边际贡献评估，并按结果更新后验。
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime
import yaml
import json

# 导入新模块 (使用绝对导入以兼容sys.path)
from core.factor_enhanced import EnhancedFactor
from core.correlation_calculator import CorrelationCalculator
from evaluation.marginal_contrib import MarginalContributionEvaluator, EvaluationResult
from utils.config_manager import ConfigManager, EvaluationConfig


@dataclass
class SelectionResult:
    """选择结果"""
    date: str                              # 选择日期
    selected_factors: List[str]            # 选中的因子ID
    candidate_scores: Dict[str, float]     # 所有候选因子得分
    selection_details: Dict = field(default_factory=dict)  # 选择详情


@dataclass
class UpdateResult:
    """更新结果"""
    date: str                              # 更新日期
    selected_updates: Dict[str, bool]      # 选中因子更新结果 {factor_id: success}
    unselected_updates: Dict[str, bool]    # 没选中因子更新结果
    marginal_details: Dict[str, Dict] = field(default_factory=dict)  # 没选中因子边际评估详情
    update_stats: Dict = field(default_factory=dict)  # 更新统计


class BayesianSelectorV2:
    """新版贝叶斯选择器 (V2)
    
    集成功能：
    1. 多时间窗口多指标因子选择
    2. 真实相关性计算
    3. 边际贡献评估
    4. 配置文件管理
    5. 完整的贝叶斯更新逻辑
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        verbose: bool = True,
    ):
        """
        初始化新版选择器
        
        参数：
            config_path: 配置文件路径
            verbose: 是否输出过程日志
        """
        self.verbose = verbose

        # 加载配置
        self.config_manager = ConfigManager()
        if config_path:
            self.config_manager.load_config(config_path)
        else:
            self.config_manager.load_config()
        
        self.config: EvaluationConfig = self.config_manager.config
        self.annualization_days = float(getattr(self.config, "annualization_days", 250))
        ic_cfg = self.config.time_windows.get("ic_calculation", {})
        self.ic_min_periods_abs = int(ic_cfg.get("min_periods_abs", 5))
        self.ic_min_periods_ratio = float(ic_cfg.get("min_periods_ratio", 0.5))
        
        # 初始化子模块
        self.correlation_calculator = CorrelationCalculator(
            self.config.correlation
        )
        
        marginal_cfg = dict(self.config.marginal_contribution or {})
        # 强制与全局年化天数一致，避免口径漂移
        marginal_cfg["annualization_factor"] = self.annualization_days

        self.marginal_evaluator = MarginalContributionEvaluator({
            'correlation': self.config.correlation,
            'portfolio': marginal_cfg,
            'thresholds': self.config.success_thresholds['unselected'],
            'scoring': marginal_cfg.get('scoring', {}),
        })
        
        # 数据存储
        self.factors: Dict[str, EnhancedFactor] = {}  # 所有因子
        self.selection_history: List[SelectionResult] = []  # 选择历史
        self.update_history: List[UpdateResult] = []  # 更新历史
        self.performance_cache: Dict = {}  # 表现缓存
        
        if self.verbose:
            print(f"新版贝叶斯选择器初始化完成")
            print(f"配置版本: {self.config.version}")
    
    def add_factor(self, factor: EnhancedFactor):
        """添加因子"""
        factor.config = factor.config or {}
        factor.config["annualization_days"] = self.annualization_days
        factor.config["ic_min_periods_abs"] = self.ic_min_periods_abs
        factor.config["ic_min_periods_ratio"] = self.ic_min_periods_ratio
        self.factors[factor.id] = factor
    
    def add_factors(self, factors: List[EnhancedFactor]):
        """批量添加因子"""
        for factor in factors:
            self.add_factor(factor)
    
    def select_factors(self, current_date: str, target_size: Optional[int] = None) -> SelectionResult:
        """
        选择因子 - 多时间窗口多指标版本
        
        参数：
            current_date: 当前日期
            target_size: 目标选择数量 (默认使用配置)
        
        返回：
            选择结果
        """
        if target_size is None:
            target_size = len(self.factors) // 3  # 默认选择1/3
        
        if self.verbose:
            print(f"[{current_date}] 开始选择因子，目标数量: {target_size}")
            print(f"  候选因子数: {len(self.factors)}")
        
        # 1. 计算所有因子的综合得分
        candidate_scores = self._calculate_factor_scores(current_date)
        
        # 2. Thompson Sampling选择
        selected_ids = self._thompson_sampling_selection(candidate_scores, target_size)
        
        # 3. 记录选择历史
        result = SelectionResult(
            date=current_date,
            selected_factors=selected_ids,
            candidate_scores=candidate_scores,
            selection_details={
                'target_size': target_size,
                'total_candidates': len(self.factors),
                'selection_ratio': len(selected_ids) / len(self.factors) if self.factors else 0
            }
        )
        
        self.selection_history.append(result)
        
        if self.verbose:
            print(f"[{current_date}] 选择完成，选中 {len(selected_ids)} 个因子")
            if selected_ids:
                print(f"  前5个选中因子: {selected_ids[:5]}")
        
        return result
    
    def update_from_performance(
        self,
        selected_ids: List[str],
        performance_data: Dict[str, Dict],
        current_date: str
    ) -> UpdateResult:
        """
        根据表现更新贝叶斯参数 - 集成边际贡献评估
        
        参数：
            selected_ids: 选中因子ID列表
            performance_data: 表现数据 {factor_id: {指标: 值}}
            current_date: 当前日期
        """
        if self.verbose:
            print(f"[{current_date}] 开始更新贝叶斯参数")
            print(f"  选中因子数: {len(selected_ids)}")
        
        # 准备选中因子对象
        selected_factors = [self.factors[fid] for fid in selected_ids if fid in self.factors]
        
        # 更新统计
        update_stats = {
            'selected_success': 0,
            'selected_failure': 0,
            'unselected_success': 0,
            'unselected_failure': 0,
            'marginal_evaluations': 0
        }
        
        selected_updates = {}
        unselected_updates = {}
        marginal_details = {}
        
        # 1. 更新选中因子
        for fid in selected_ids:
            if fid not in self.factors:
                continue
            
            factor = self.factors[fid]
            perf = performance_data.get(fid, {})
            
            success = self._evaluate_selected_success(factor, perf, current_date)
            selected_updates[fid] = success
            
            # 更新贝叶斯参数
            update_weight = self.config.bayesian['update_rules']['selected_success' if success else 'selected_failure']
            factor.update_bayesian_params(success, update_weight)
            
            if success:
                update_stats['selected_success'] += 1
            else:
                update_stats['selected_failure'] += 1
            
            # 输出调试信息
            if self.verbose and list(self.factors.keys()).index(fid) < 3:  # 前3个因子
                print(f"    选中因子 {fid}: 成功={success}, "
                      f"新参数: α={factor.alpha:.1f}, β={factor.beta:.1f}")
        
        # 2. 评估和更新没选中因子（边际贡献法）
        unselected_ids = [fid for fid in self.factors.keys() if fid not in selected_ids]
        
        if unselected_ids and selected_factors:
            if self.verbose:
                print(f"  评估 {len(unselected_ids)} 个没选中因子的边际贡献...")
            
            # 批量评估边际贡献
            unselected_factors = [self.factors[fid] for fid in unselected_ids]
            
            # 使用配置驱动的没选中因子评估窗口
            eval_windows = self.config.time_windows.get('evaluation', {})
            unselected_lookback = int(eval_windows.get('unselected_long', 40))

            # 使用边际贡献评估器
            marginal_results = self.marginal_evaluator.evaluate_multiple_factors(
                unselected_factors, selected_factors, current_date, lookback_days=unselected_lookback
            )
            
            update_stats['marginal_evaluations'] = len(marginal_results)
            
            for fid, result in marginal_results.items():
                if fid not in self.factors:
                    continue
                
                factor = self.factors[fid]
                marginal_details[fid] = result.to_dict()
                
                # 根据边际贡献评估结果决定是否更新
                if result.evaluation == EvaluationResult.SUCCESS:
                    # 成功：应该被选中但没选中
                    success = True
                    update_weight = self.config.bayesian['update_rules']['unselected_success']
                    update_stats['unselected_success'] += 1
                elif result.evaluation == EvaluationResult.FAILURE:
                    # 失败：确实不应该被选中
                    success = False
                    update_weight = self.config.bayesian['update_rules']['unselected_failure']
                    update_stats['unselected_failure'] += 1
                else:
                    # 中性或不确定：不更新
                    continue
                
                unselected_updates[fid] = success
                factor.update_bayesian_params(success, update_weight)
        
        # 3. 记录更新历史
        update_result = UpdateResult(
            date=current_date,
            selected_updates=selected_updates,
            unselected_updates=unselected_updates,
            marginal_details=marginal_details,
            update_stats=update_stats
        )
        
        self.update_history.append(update_result)
        
        if self.verbose:
            print(f"[{current_date}] 更新完成")
            print(f"  选中成功: {update_stats['selected_success']}, "
                  f"选中失败: {update_stats['selected_failure']}")
            print(f"  没选中成功: {update_stats['unselected_success']}, "
                  f"没选中失败: {update_stats['unselected_failure']}")
            print(f"  边际贡献评估: {update_stats['marginal_evaluations']} 个因子")
        
        return update_result
    
    def _calculate_factor_scores(self, current_date: str) -> Dict[str, Dict[str, float]]:
        """计算每个候选因子的最终得分与中间拆解项。

        返回字段:
        - final_score: 选择排序使用的最终分数
        - aggregate_score: 多窗口多指标聚合分
        - bayesian_score: Beta(alpha, beta) 的一次采样值
        - success_rate: 历史后验成功率估计
        """
        scores = {}
        blend_cfg = self.config.bayesian.get('selection_blend', {})
        aggregate_w = float(blend_cfg.get('aggregate_score', 0.7))
        bayesian_w = float(blend_cfg.get('bayesian_score', 0.3))
        w_sum = aggregate_w + bayesian_w
        if w_sum <= 0:
            aggregate_w, bayesian_w = 0.7, 0.3
        else:
            aggregate_w, bayesian_w = aggregate_w / w_sum, bayesian_w / w_sum
        
        # A层聚合分改为“全截面分位数标准化”后再聚合，提升跨指标可比性。
        aggregate_scores = self._calculate_cross_sectional_aggregate_scores(current_date)

        for fid, factor in self.factors.items():
            score = float(aggregate_scores.get(fid, 0.0))
            
            # 贝叶斯得分 (Thompson Sampling)
            bayesian_score = np.random.beta(factor.alpha, factor.beta)
            
            # 综合得分 = 聚合打分 + 贝叶斯打分（权重由配置控制）
            final_score = score * aggregate_w + bayesian_score * bayesian_w
            
            scores[fid] = {
                'final_score': final_score,
                'aggregate_score': score,
                'bayesian_score': bayesian_score,
                'success_rate': factor.get_success_rate()
            }
        
        return scores

    @staticmethod
    def _percentile_score_map(raw_map: Dict[str, float]) -> Dict[str, float]:
        """将同一截面的原始值映射到 [0,1] 分位数得分（高值=高分）。"""
        items = [(fid, float(v)) for fid, v in raw_map.items() if v is not None and np.isfinite(v)]
        n = len(items)
        if n == 0:
            return {}
        if n == 1:
            return {items[0][0]: 0.5}

        values = [v for _, v in items]
        out: Dict[str, float] = {}
        for fid, v in items:
            less = sum(1 for x in values if x < v)
            equal = sum(1 for x in values if x == v)
            avg_rank = less + (equal - 1) / 2.0
            out[fid] = avg_rank / (n - 1)
        return out

    def _calculate_cross_sectional_aggregate_scores(self, current_date: str) -> Dict[str, float]:
        """按当前日期横截面分位数标准化后计算 aggregate_score。"""
        window_weights = self.config.get_window_weights()
        indicator_weights = self.config.get_indicator_weights_for_selection()
        windows = list(window_weights.keys())

        # 1) 取每个因子在各窗口的原始统计
        factor_window_stats: Dict[str, Dict[str, Dict[str, float]]] = {}
        for fid, factor in self.factors.items():
            factor_window_stats[fid] = factor.get_multi_window_stats(windows, current_date)

        # 2) 对每个窗口、每个指标做“全截面分位数标准化”
        metric_names = ("icir", "ls_return", "rank", "stability")
        metric_pct_by_window: Dict[int, Dict[str, Dict[str, float]]] = {w: {} for w in windows}
        for window in windows:
            raw_icir: Dict[str, float] = {}
            raw_ls_return: Dict[str, float] = {}
            raw_rank: Dict[str, float] = {}
            raw_stability: Dict[str, float] = {}

            for fid in self.factors.keys():
                ws = factor_window_stats[fid].get(f"window_{window}", {})
                if int(ws.get("data_points", 0)) <= 0:
                    continue
                icir_val = ws.get("icir")
                if icir_val is not None and np.isfinite(icir_val):
                    raw_icir[fid] = float(icir_val)
                ls_val = ws.get("ls_return_mean")
                if ls_val is not None and np.isfinite(ls_val):
                    raw_ls_return[fid] = float(ls_val)
                rank_val = ws.get("avg_rank")
                if rank_val is not None and np.isfinite(rank_val):
                    # 原始 avg_rank 越小越好，这里先转同向分值再做截面分位数。
                    raw_rank[fid] = 1.0 - float(rank_val)
                stability_val = ws.get("ls_return_sharpe")
                if stability_val is not None and np.isfinite(stability_val):
                    raw_stability[fid] = float(stability_val)

            metric_pct_by_window[window]["icir"] = self._percentile_score_map(raw_icir)
            metric_pct_by_window[window]["ls_return"] = self._percentile_score_map(raw_ls_return)
            metric_pct_by_window[window]["rank"] = self._percentile_score_map(raw_rank)
            metric_pct_by_window[window]["stability"] = self._percentile_score_map(raw_stability)

        # 3) 每个因子做窗口内指标聚合 + 窗口间聚合（缺失项均重归一）
        out_scores: Dict[str, float] = {}
        metric_weight_map = {
            "icir": float(indicator_weights.get("icir", 0.0)),
            "ls_return": float(indicator_weights.get("ls_return", 0.0)),
            "rank": float(indicator_weights.get("rank", indicator_weights.get("rank_percentile", 0.0))),
            "stability": float(indicator_weights.get("stability", 0.0)),
        }
        for fid in self.factors.keys():
            total_score = 0.0
            total_w = 0.0
            for window, window_w in window_weights.items():
                metric_pairs: List[Tuple[float, float]] = []
                for metric in metric_names:
                    mw = metric_weight_map[metric]
                    if mw <= 0:
                        continue
                    v = metric_pct_by_window[window].get(metric, {}).get(fid)
                    if v is None or not np.isfinite(v):
                        continue
                    metric_pairs.append((mw, float(v)))
                if not metric_pairs:
                    continue
                mws = sum(w for w, _ in metric_pairs)
                window_score = sum((w / mws) * v for w, v in metric_pairs)
                total_score += float(window_w) * window_score
                total_w += float(window_w)
            out_scores[fid] = (total_score / total_w) if total_w > 1e-8 else 0.0
        return out_scores
    
    def _thompson_sampling_selection(self, candidate_scores: Dict[str, Dict], target_size: int) -> List[str]:
        """Thompson Sampling选择"""
        # 按最终得分排序
        sorted_factors = sorted(
            candidate_scores.items(),
            key=lambda x: x[1]['final_score'],
            reverse=True
        )
        
        # 选择前target_size个
        selected = [fid for fid, _ in sorted_factors[:target_size]]
        
        return selected
    
    def _evaluate_selected_success(self, factor: EnhancedFactor, performance: Dict, current_date: str) -> bool:
        """评估“被选中因子”在本轮是否判定为成功。

        业务规则:
        - 主要依据因子历史表现窗口重新计算 ICIR / Sharpe / WinRate。
        - `performance` 字典当前仅补充 `rank_percentile` 输入。
        - 当有效样本数不足 `required_points=max(min_periods_abs, ceil(window*min_periods_ratio))`
          时直接视为失败，避免小样本误判。
        """
        thresholds = self.config.success_thresholds['selected']
        
        # 获取近期表现
        lookback = self.config.time_windows['evaluation'].get('selected_short', 10)
        recent_perf = factor.get_recent_performance(lookback, current_date)
        
        required_points = factor.get_required_ic_periods(lookback)
        valid_ic_points = sum(1 for p in recent_perf if p.ic is not None)
        if valid_ic_points < required_points:
            return False
        
        # 计算指标
        icir = factor.calculate_icir(recent_perf)
        ls_stats = factor.calculate_ls_return_stats(recent_perf)
        
        # 从performance_data获取额外指标
        rank_percentile = performance.get('rank_percentile', 0.5)
        win_rate = ls_stats['win_rate']
        
        # 检查是否满足所有阈值
        success = (
            icir > thresholds['icir'] and
            ls_stats['sharpe'] > 0 and  # 夏普为正
            rank_percentile < thresholds['rank_percentile'] and
            win_rate > thresholds['win_rate']
        )
        
        return success
    
    def get_factor_stats(self, top_n: int = 10) -> List[Dict]:
        """获取因子统计信息"""
        factors_sorted = sorted(
            self.factors.values(),
            key=lambda f: f.get_success_rate(),
            reverse=True
        )[:top_n]
        
        selected_long = int(self.config.time_windows.get('evaluation', {}).get('selected_long', 20))
        stats = []
        for factor in factors_sorted:
            stats.append({
                'id': factor.id,
                'topic': factor.topic,
                'alpha': factor.alpha,
                'beta': factor.beta,
                'success_rate': factor.get_success_rate(),
                'performance_count': len(factor.performance_history),
                'recent_icir': factor.calculate_icir(factor.get_recent_performance(selected_long)) if factor.performance_history else 0.0
            })
        
        return stats
    
    def get_selection_stats(self) -> Dict:
        """获取选择统计信息"""
        if not self.selection_history:
            return {}
        
        latest = self.selection_history[-1]
        
        return {
            'date': latest.date,
            'num_selected': len(latest.selected_factors),
            'num_candidates': len(self.factors),
            'selection_ratio': len(latest.selected_factors) / len(self.factors) if self.factors else 0,
            'avg_success_rate': np.mean([f.get_success_rate() for f in self.factors.values()]) if self.factors else 0.0
        }
    
    def save_state(self, filepath: str):
        """保存状态到文件"""
        state = {
            'factors': {fid: factor.to_dict() for fid, factor in self.factors.items()},
            'selection_history': [
                {
                    'date': r.date,
                    'selected_factors': r.selected_factors,
                    'selection_details': r.selection_details
                }
                for r in self.selection_history
            ],
            'update_history': [
                {
                    'date': r.date,
                    'update_stats': r.update_stats
                }
                for r in self.update_history
            ],
            'config_summary': self.config_manager.get_config_summary(),
            'timestamp': datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2, default=str)
        
        print(f"状态已保存到: {filepath}")
    
    def load_state(self, filepath: str):
        """从文件加载状态"""
        with open(filepath, 'r') as f:
            state = json.load(f)
        
        # 加载因子
        self.factors.clear()
        for fid, factor_data in state.get('factors', {}).items():
            # 这里简化处理，实际应该重新创建EnhancedFactor对象
            print(f"加载因子: {fid}")
        
        # 加载历史
        self.selection_history = [
            SelectionResult(
                date=r['date'],
                selected_factors=r['selected_factors'],
                selection_details=r.get('selection_details', {})
            )
            for r in state.get('selection_history', [])
        ]
        
        self.update_history = [
            UpdateResult(
                date=r['date'],
                selected_updates={},
                unselected_updates={},
                update_stats=r.get('update_stats', {})
            )
            for r in state.get('update_history', [])
        ]
        
        print(f"状态已从 {filepath} 加载")
        print(f"  加载了 {len(self.factors)} 个因子")
        print(f"  选择历史: {len(self.selection_history)} 条")
        print(f"  更新历史: {len(self.update_history)} 条")
    
    def print_summary(self):
        """打印摘要信息"""
        print("=" * 70)
        print("新版贝叶斯选择器 (V2) 摘要")
        print("=" * 70)
        
        # 配置摘要
        config_summary = self.config_manager.get_config_summary()
        print(f"配置版本: {config_summary.get('version', 'N/A')}")
        
        # 因子统计
        print(f"\n因子统计:")
        print(f"  总因子数: {len(self.factors)}")
        
        if self.factors:
            success_rates = [f.get_success_rate() for f in self.factors.values()]
            print(f"  平均成功率: {np.mean(success_rates):.3f}")
            print(f"  成功率范围: {np.min(success_rates):.3f} - {np.max(success_rates):.3f}")
        
        # 选择历史
        print(f"\n选择历史:")
        if self.selection_history:
            latest = self.selection_history[-1]
            print(f"  最近选择: {latest.date}")
            print(f"  选中因子数: {len(latest.selected_factors)}")
            print(f"  选择比例: {len(latest.selected_factors)/len(self.factors):.1%}")
        else:
            print(f"  无选择历史")
        
        # 更新历史
        print(f"\n更新历史:")
        if self.update_history:
            latest = self.update_history[-1]
            stats = latest.update_stats
            print(f"  最近更新: {latest.date}")
            print(f"  选中成功: {stats.get('selected_success', 0)}")
            print(f"  选中失败: {stats.get('selected_failure', 0)}")
            print(f"  没选中成功: {stats.get('unselected_success', 0)}")
            print(f"  没选中失败: {stats.get('unselected_failure', 0)}")
        else:
            print(f"  无更新历史")
        
        print("\n" + "=" * 70)


# 测试函数
def test_bayesian_selector_v2():
    """测试新版贝叶斯选择器"""
    print("测试新版贝叶斯选择器 (V2)...")
    
    # 创建选择器
    selector = BayesianSelectorV2()
    
    # 创建测试因子
    np.random.seed(42)
    n_factors = 20
    n_days = 100
    
    dates = [f"2024-01-{i+1:02d}" for i in range(n_days)]
    
    print(f"创建 {n_factors} 个测试因子...")
    
    for i in range(n_factors):
        factor_id = f"F{i:03d}"
        
        # 创建因子
        factor = EnhancedFactor(
            factor_id=factor_id,
            expression=f"Test_Expression_{i}",
            topic="test"
        )
        
        # 添加表现数据
        for j, date in enumerate(dates):
            # 模拟不同质量的因子
            if i < 5:
                # 好因子
                ic = np.random.normal(0.08, 0.02)
                ls_return = np.random.normal(0.002, 0.015)
                rank = np.random.uniform(0.1, 0.3)
            elif i < 15:
                # 中等因子
                ic = np.random.normal(0.04, 0.03)
                ls_return = np.random.normal(0.001, 0.02)
                rank = np.random.uniform(0.3, 0.7)
            else:
                # 差因子
                ic = np.random.normal(0.01, 0.04)
                ls_return = np.random.normal(0.0002, 0.025)
                rank = np.random.uniform(0.7, 0.9)
            
            factor.add_daily_performance(
                date=date,
                ic=ic,
                ls_return=ls_return,
                rank_percentile=rank
            )
        
        # 设置不同的贝叶斯参数
        if i < 5:
            factor.alpha = 8.0  # 成功次数多
            factor.beta = 2.0   # 失败次数少
        elif i < 15:
            factor.alpha = 5.0
            factor.beta = 5.0
        else:
            factor.alpha = 2.0  # 成功次数少
            factor.beta = 8.0   # 失败次数多
        
        selector.add_factor(factor)
    
    print(f"添加了 {len(selector.factors)} 个因子")
    
    # 测试选择因子
    print("\n1. 测试选择因子:")
    selection_result = selector.select_factors("2024-04-10", target_size=5)
    
    print(f"   选择日期: {selection_result.date}")
    print(f"   选中因子数: {len(selection_result.selected_factors)}")
    print(f"   选中因子: {selection_result.selected_factors}")
    
    # 显示前几个因子的得分
    print(f"\n   前5个因子得分:")
    for i, (fid, scores) in enumerate(list(selection_result.candidate_scores.items())[:5]):
        print(f"     {fid}: 综合得分={scores['final_score']:.3f}, "
              f"贝叶斯得分={scores['bayesian_score']:.3f}, "
              f"成功率={scores['success_rate']:.3f}")
    
    # 测试更新贝叶斯参数
    print("\n2. 测试更新贝叶斯参数:")
    
    # 模拟表现数据
    performance_data = {}
    for fid in selection_result.selected_factors:
        # 模拟表现：好因子表现好，差因子表现差
        if fid in ["F000", "F001", "F002", "F003", "F004"]:
            performance_data[fid] = {
                'rank_percentile': np.random.uniform(0.1, 0.3),
                'icir': np.random.uniform(1.5, 2.5)
            }
        else:
            performance_data[fid] = {
                'rank_percentile': np.random.uniform(0.6, 0.9),
                'icir': np.random.uniform(0.2, 0.8)
            }
    
    update_result = selector.update_from_performance(
        selection_result.selected_factors,
        performance_data,
        "2024-04-10"
    )
    
    print(f"   更新日期: {update_result.date}")
    print(f"   更新统计: {update_result.update_stats}")
    
    # 测试获取统计信息
    print("\n3. 测试获取统计信息:")
    
    # 因子统计
    factor_stats = selector.get_factor_stats(top_n=5)
    print(f"   前5个因子统计:")
    for stat in factor_stats:
        print(f"     {stat['id']}: α={stat['alpha']:.1f}, β={stat['beta']:.1f}, "
              f"成功率={stat['success_rate']:.3f}, ICIR={stat['recent_icir']:.3f}")
    
    # 选择统计
    selection_stats = selector.get_selection_stats()
    print(f"\n   选择统计:")
    print(f"     最近选择日期: {selection_stats.get('date', 'N/A')}")
    print(f"     选中因子数: {selection_stats.get('num_selected', 0)}")
    print(f"     选择比例: {selection_stats.get('selection_ratio', 0):.1%}")
    print(f"     平均成功率: {selection_stats.get('avg_success_rate', 0):.3f}")
    
    # 测试保存和加载状态
    print("\n4. 测试保存和加载状态:")
    test_state_file = "test_selector_state.json"
    
    selector.save_state(test_state_file)
    print(f"   状态已保存到: {test_state_file}")
    
    # 创建新的选择器并加载状态
    selector2 = BayesianSelectorV2()
    selector2.load_state(test_state_file)
    print(f"   状态已加载，选择历史: {len(selector2.selection_history)} 条")
    
    # 清理测试文件
    import os
    if os.path.exists(test_state_file):
        os.remove(test_state_file)
    
    # 打印完整摘要
    print("\n5. 完整摘要:")
    selector.print_summary()
    
    print("\n测试完成!")


if __name__ == "__main__":
    test_bayesian_selector_v2()
