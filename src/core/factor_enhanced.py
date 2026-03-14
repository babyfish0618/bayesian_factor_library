"""
增强版因子数据结构
支持多指标、多时间窗口、ICIR正确计算
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
import yaml
import json


@dataclass
class FactorPerformance:
    """因子表现数据 - 按日期存储"""
    date: str                    # 日期 YYYY-MM-DD
    ic: Optional[float] = None   # 信息系数 (Information Coefficient)
    icir: Optional[float] = None # IC信息比率 (IC Information Ratio)
    ls_return: Optional[float] = None  # 多空收益
    rank_percentile: Optional[float] = None  # 排名百分位 (0-1, 越小越好)
    win_rate: Optional[float] = None   # 胜率
    sharpe: Optional[float] = None     # 夏普比率
    max_drawdown: Optional[float] = None  # 最大回撤
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'date': self.date,
            'ic': self.ic,
            'icir': self.icir,
            'ls_return': self.ls_return,
            'rank_percentile': self.rank_percentile,
            'win_rate': self.win_rate,
            'sharpe': self.sharpe,
            'max_drawdown': self.max_drawdown
        }


class EnhancedFactor:
    """增强版因子类
    
    支持：
    1. 多指标存储 (IC, ICIR, 多空收益, 排名等)
    2. 多时间窗口分析
    3. 正确的ICIR计算 (IC均值/标准差)
    4. 时间序列存储和查询
    """
    
    def __init__(self, factor_id: str, expression: str, topic: str, 
                 config: Optional[Dict] = None):
        """
        初始化增强版因子
        
        参数：
            factor_id: 因子ID
            expression: 因子表达式
            topic: 主题分类
            config: 配置参数
        """
        self.id = factor_id
        self.expression = expression
        self.topic = topic
        
        # 贝叶斯参数
        self.alpha = 1.0  # 先验成功次数
        self.beta = 1.0   # 先验失败次数
        
        # 表现数据 (按日期排序)
        self.performance_history: List[FactorPerformance] = []
        
        # 配置
        self.config = config or {}
        
        # 缓存计算结果
        self._cache = {}

    def _annualization_days(self) -> float:
        """年化天数（统一从配置读取）"""
        return float(self.config.get("annualization_days", 250))

    def _ic_min_periods_abs(self) -> int:
        """IC/ICIR最小样本绝对下限。"""
        return max(1, int(self.config.get("ic_min_periods_abs", 5)))

    def _ic_min_periods_ratio(self) -> float:
        """IC/ICIR最小样本比例下限（相对当前窗口长度）。"""
        return float(self.config.get("ic_min_periods_ratio", 0.5))

    def get_required_ic_periods(self, window_size: int) -> int:
        """计算给定窗口长度下的 IC/ICIR 最小有效样本门槛。"""
        window_n = max(1, int(window_size))
        ratio = self._ic_min_periods_ratio()
        ratio = min(max(ratio, 0.0), 1.0)
        ratio_floor = int(np.ceil(window_n * ratio))
        return max(self._ic_min_periods_abs(), ratio_floor)
    
    def add_daily_performance(self, date: str, **kwargs):
        """添加日度表现数据"""
        perf = FactorPerformance(date=date, **kwargs)
        self.performance_history.append(perf)
        
        # 按日期排序
        self.performance_history.sort(key=lambda x: x.date)
        
        # 清除缓存
        self._cache.clear()
    
    def add_batch_performance(self, performances: List[FactorPerformance]):
        """批量添加表现数据"""
        self.performance_history.extend(performances)
        self.performance_history.sort(key=lambda x: x.date)
        self._cache.clear()
    
    def get_performance_in_range(self, start_date: str, end_date: str) -> List[FactorPerformance]:
        """获取指定日期范围内的表现数据"""
        return [
            p for p in self.performance_history
            if start_date <= p.date <= end_date
        ]
    
    def get_recent_performance(self, lookback_days: int, end_date: Optional[str] = None) -> List[FactorPerformance]:
        """获取截至 `end_date` 的最近 N 条表现记录。

        说明:
        - 这里按“记录条数”回看，而非自然日历天数。
        - 若 `end_date` 为空，默认使用当前历史中的最后日期。
        """
        if not self.performance_history:
            return []
        
        # 确定结束日期
        if end_date is None:
            end_date = self.performance_history[-1].date
        
        # 找到结束日期的索引
        end_idx = -1
        for i, perf in enumerate(self.performance_history):
            if perf.date <= end_date:
                end_idx = i
            else:
                break
        
        if end_idx < 0:
            return []
        
        # 向前取lookback_days个
        start_idx = max(0, end_idx - lookback_days + 1)
        return self.performance_history[start_idx:end_idx+1]
    
    def calculate_icir(self, performances: List[FactorPerformance], window_size: Optional[int] = None) -> float:
        """计算 ICIR = mean(IC) / std(IC)。

        返回约定:
        - 有效样本不足时返回 `np.nan`（表示“不可计算”而非“中性”）。
        - 标准差近似为 0 时返回 `0.0`（表示“有样本但无波动信息”）。
        """
        if not performances:
            return np.nan
        
        # 提取有效IC值
        ic_values = [p.ic for p in performances if p.ic is not None]
        
        required = self.get_required_ic_periods(window_size or len(performances))
        if len(ic_values) < required:
            return np.nan
        
        ic_mean = np.mean(ic_values)
        ic_std = np.std(ic_values)
        
        if ic_std < 1e-8:
            return 0.0
        
        return float(ic_mean / ic_std)
    
    def calculate_ls_return_stats(self, performances: List[FactorPerformance]) -> Dict:
        """计算多空收益统计"""
        if not performances:
            return {
                'mean': 0.0,
                'std': 0.0,
                'sharpe': 0.0,
                'win_rate': 0.0,
                'cumulative': 0.0
            }
        
        # 提取多空收益
        returns = [p.ls_return for p in performances if p.ls_return is not None]
        
        if not returns:
            return {
                'mean': 0.0,
                'std': 0.0,
                'sharpe': 0.0,
                'win_rate': 0.0,
                'cumulative': 0.0
            }
        
        returns_array = np.array(returns)
        
        # 基本统计
        mean_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        
        # 夏普比率 (假设无风险利率为0)
        sharpe = mean_return / (std_return + 1e-8) * np.sqrt(self._annualization_days())  # 年化
        
        # 胜率
        win_rate = np.sum(returns_array > 0) / len(returns_array)
        
        # 累计收益
        cumulative = np.prod(1 + returns_array) - 1
        
        return {
            'mean': mean_return,
            'std': std_return,
            'sharpe': sharpe,
            'win_rate': win_rate,
            'cumulative': cumulative
        }
    
    def get_multi_window_stats(self, windows: List[int], end_date: Optional[str] = None) -> Dict:
        """获取多时间窗口统计"""
        cache_key = f"multi_window_{'_'.join(map(str, windows))}_{end_date}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        stats = {}
        
        for window in windows:
            # 获取近期表现
            recent_perf = self.get_recent_performance(window, end_date)
            
            if not recent_perf:
                stats[f'window_{window}'] = {
                    'icir': np.nan,
                    'ls_return_mean': 0.0,
                    'ls_return_sharpe': 0.0,
                    'avg_rank': 1.0,
                    'win_rate': 0.0,
                    'data_points': 0,
                    'required_ic_points': self.get_required_ic_periods(window),
                    'effective_ic_points': 0,
                }
                continue
            
            # 计算ICIR
            icir = self.calculate_icir(recent_perf, window_size=window)
            ic_values = [p.ic for p in recent_perf if p.ic is not None]
            
            # 计算多空收益统计
            ls_stats = self.calculate_ls_return_stats(recent_perf)
            
            # 计算平均排名
            ranks = [p.rank_percentile for p in recent_perf if p.rank_percentile is not None]
            avg_rank = np.mean(ranks) if ranks else 1.0
            
            stats[f'window_{window}'] = {
                'icir': icir,
                'ls_return_mean': ls_stats['mean'],
                'ls_return_sharpe': ls_stats['sharpe'],
                'avg_rank': avg_rank,
                'win_rate': ls_stats['win_rate'],
                'data_points': len(recent_perf),
                'required_ic_points': self.get_required_ic_periods(window),
                'effective_ic_points': len(ic_values),
            }
        
        # 缓存结果
        self._cache[cache_key] = stats
        return stats
    
    def get_aggregate_score(self, window_weights: Dict[int, float], 
                           indicator_weights: Dict[str, float],
                           end_date: Optional[str] = None) -> float:
        """计算综合得分
        
        参数：
            window_weights: 时间窗口权重 {5: 0.3, 20: 0.4, 60: 0.3}
            indicator_weights: 指标权重 {'icir': 0.4, 'ls_return': 0.3, 'rank': 0.2, 'stability': 0.1}
            end_date: 结束日期

        评分方向约定:
        - icir / ls_return / stability 越大越好
        - rank_percentile 越小越好（内部会做反向处理）
        """
        # 获取多窗口统计
        windows = list(window_weights.keys())
        stats = self.get_multi_window_stats(windows, end_date)
        
        total_score = 0.0
        total_weight = 0.0
        
        for window, window_weight in window_weights.items():
            window_stats = stats.get(f'window_{window}')
            if not window_stats or window_stats['data_points'] <= 0:
                continue

            # 指标缺失时按有效指标重归一化权重，避免 NaN 污染最终分。
            metric_values = {
                'icir': self._normalize_icir(window_stats['icir']),
                'ls_return': self._normalize_ls_return(window_stats['ls_return_mean']),
                'rank': 1.0 - window_stats['avg_rank'],  # 排名越前得分越高
                'stability': self._normalize_sharpe(window_stats['ls_return_sharpe']),
            }
            metric_weights = {
                'icir': float(indicator_weights.get('icir', 0.0)),
                'ls_return': float(indicator_weights.get('ls_return', 0.0)),
                'rank': float(indicator_weights.get('rank', indicator_weights.get('rank_percentile', 0.0))),
                'stability': float(indicator_weights.get('stability', 0.0)),
            }
            valid_pairs = [
                (metric_weights[name], metric_values[name])
                for name in ("icir", "ls_return", "rank", "stability")
                if np.isfinite(metric_values[name]) and metric_weights[name] > 0
            ]
            if not valid_pairs:
                continue

            metric_weight_sum = sum(w for w, _ in valid_pairs)
            window_score = sum((w / metric_weight_sum) * v for w, v in valid_pairs)

            total_score += window_weight * window_score
            total_weight += window_weight
        
        if total_weight < 1e-8:
            return 0.0
        
        return total_score / total_weight
    
    def _normalize_icir(self, icir: float) -> float:
        """归一化ICIR得分"""
        if icir is None or not np.isfinite(icir):
            return np.nan
        # 使用sigmoid函数
        # ICIR=0 → 0.5, ICIR=3 → 0.95
        return 1.0 / (1.0 + np.exp(-icir))
    
    def _normalize_ls_return(self, ls_return: float) -> float:
        """归一化多空收益"""
        if ls_return is None or not np.isfinite(ls_return):
            return np.nan
        # 日度收益，年化约 日收益*annualization_days
        annualized = ls_return * self._annualization_days()
        return min(max(annualized / 0.5, 0.0), 1.0)  # 年化50%得1.0
    
    def _normalize_sharpe(self, sharpe: float) -> float:
        """归一化夏普比率"""
        if sharpe is None or not np.isfinite(sharpe):
            return np.nan
        return min(max(sharpe / 3.0, 0.0), 1.0)  # 夏普3.0得1.0
    
    def get_success_rate(self) -> float:
        """计算历史成功率 (α/(α+β))"""
        if self.alpha + self.beta < 1e-8:
            return 0.5
        return self.alpha / (self.alpha + self.beta)
    
    def update_bayesian_params(self, success: bool, weight: float = 1.0):
        """更新贝叶斯参数"""
        if success:
            self.alpha += weight
        else:
            self.beta += weight
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'id': self.id,
            'expression': self.expression,
            'topic': self.topic,
            'alpha': self.alpha,
            'beta': self.beta,
            'success_rate': self.get_success_rate(),
            'performance_count': len(self.performance_history),
            'recent_icir': self.calculate_icir(self.get_recent_performance(20)) if self.performance_history else 0.0
        }
    
    def save_to_file(self, filepath: str):
        """保存到文件"""
        data = {
            'factor_info': {
                'id': self.id,
                'expression': self.expression,
                'topic': self.topic,
                'alpha': self.alpha,
                'beta': self.beta
            },
            'performance_history': [
                perf.to_dict() for perf in self.performance_history
            ]
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load_from_file(cls, filepath: str, config: Optional[Dict] = None):
        """从文件加载"""
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        factor_info = data['factor_info']
        factor = cls(
            factor_id=factor_info['id'],
            expression=factor_info['expression'],
            topic=factor_info['topic'],
            config=config
        )
        
        factor.alpha = factor_info.get('alpha', 1.0)
        factor.beta = factor_info.get('beta', 1.0)
        
        # 加载表现数据
        for perf_data in data.get('performance_history', []):
            perf = FactorPerformance(**perf_data)
            factor.performance_history.append(perf)
        
        factor.performance_history.sort(key=lambda x: x.date)
        
        return factor


# 测试函数
def test_enhanced_factor():
    """测试增强版因子类"""
    print("测试增强版因子类...")
    
    # 创建因子
    factor = EnhancedFactor(
        factor_id="momentum_001",
        expression="Return(20)",
        topic="momentum"
    )
    
    # 添加模拟数据
    np.random.seed(42)
    dates = [f"2024-01-{i+1:02d}" for i in range(100)]
    
    for i, date in enumerate(dates):
        # 模拟IC (均值0.05，波动0.02)
        ic = np.random.normal(0.05, 0.02)
        
        # 模拟多空收益 (均值0.001，波动0.01)
        ls_return = np.random.normal(0.001, 0.01)
        
        # 模拟排名 (0-1均匀分布)
        rank = np.random.uniform(0, 1)
        
        factor.add_daily_performance(
            date=date,
            ic=ic,
            ls_return=ls_return,
            rank_percentile=rank
        )
    
    # 测试多窗口统计
    print("\n1. 多窗口统计:")
    windows = [5, 20, 60]
    stats = factor.get_multi_window_stats(windows)
    
    for window in windows:
        window_stats = stats[f'window_{window}']
        print(f"  窗口{window}天: ICIR={window_stats['icir']:.3f}, "
              f"多空收益={window_stats['ls_return_mean']:.4f}, "
              f"夏普={window_stats['ls_return_sharpe']:.3f}")
    
    # 测试综合得分
    print("\n2. 综合得分:")
    window_weights = {5: 0.3, 20: 0.4, 60: 0.3}
    indicator_weights = {'icir': 0.4, 'ls_return': 0.3, 'rank': 0.2, 'stability': 0.1}
    
    score = factor.get_aggregate_score(window_weights, indicator_weights)
    print(f"  综合得分: {score:.3f}")
    
    # 测试ICIR计算
    print("\n3. ICIR计算验证:")
    recent_20 = factor.get_recent_performance(20)
    icir = factor.calculate_icir(recent_20)
    print(f"  最近20天ICIR: {icir:.3f}")
    
    # 提取IC值验证
    ic_values = [p.ic for p in recent_20 if p.ic is not None]
    if ic_values:
        ic_mean = np.mean(ic_values)
        ic_std = np.std(ic_values)
        print(f"  IC均值: {ic_mean:.4f}, IC标准差: {ic_std:.4f}")
        print(f"  验证: ICIR = {ic_mean}/{ic_std} = {ic_mean/ic_std:.3f}")
    
    print("\n测试完成!")


if __name__ == "__main__":
    test_enhanced_factor()
