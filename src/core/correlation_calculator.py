"""
因子相关性计算模块
基于因子值时间序列计算真实相关性
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Union
import pandas as pd
from scipy import stats
import warnings


class CorrelationCalculator:
    """因子相关性计算器
    
    功能：
    1. 计算因子间的Pearson/Spearman/Kendall相关性
    2. 处理缺失值和不同长度的时间序列
    3. 计算相关性矩阵和显著性检验
    4. 支持滚动窗口相关性计算
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        初始化相关性计算器
        
        参数：
            config: 配置参数，包含：
                - method: 相关性计算方法 ('pearson'/'spearman'/'kendall')
                - min_common_periods: 最小共同期数
                - significance_level: 显著性水平
                - handle_na: 缺失值处理方法 ('drop'/'fill')
        """
        self.config = config or {
            'method': 'pearson',
            'min_common_periods': 20,
            'significance_level': 0.05,
            'handle_na': 'drop'
        }
        
        # 缓存计算结果
        self._cache = {}
    
    def calculate_pairwise(
        self, 
        series1: np.ndarray, 
        series2: np.ndarray,
        dates1: Optional[List[str]] = None,
        dates2: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """
        计算两个时间序列的相关性
        
        参数：
            series1: 第一个时间序列
            series2: 第二个时间序列
            dates1: 第一个序列的日期列表 (可选)
            dates2: 第二个序列的日期列表 (可选)
        
        返回：
            包含相关性系数、p值、有效样本数等的字典
        """
        # 处理缺失值
        series1_clean, series2_clean = self._align_series(
            series1, series2, dates1, dates2
        )
        
        if len(series1_clean) < self.config['min_common_periods']:
            return {
                'correlation': 0.0,
                'p_value': 1.0,
                'n_obs': len(series1_clean),
                'significant': False,
                'method': self.config['method']
            }
        
        # 计算相关性
        method = self.config['method'].lower()
        
        if method == 'pearson':
            corr, p_value = stats.pearsonr(series1_clean, series2_clean)
        elif method == 'spearman':
            corr, p_value = stats.spearmanr(series1_clean, series2_clean)
        elif method == 'kendall':
            corr, p_value = stats.kendalltau(series1_clean, series2_clean)
        else:
            raise ValueError(f"不支持的相关性计算方法: {method}")
        
        # 检查显著性
        significant = p_value < self.config['significance_level']
        
        return {
            'correlation': float(corr),
            'p_value': float(p_value),
            'n_obs': len(series1_clean),
            'significant': significant,
            'method': method
        }
    
    def calculate_correlation_matrix(
        self, 
        factor_scores: Dict[str, np.ndarray],
        factor_dates: Optional[Dict[str, List[str]]] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        计算所有因子的相关性矩阵
        
        参数：
            factor_scores: 因子得分字典 {factor_id: scores_array}
            factor_dates: 因子日期字典 {factor_id: dates_list} (可选)
        
        返回：
            correlation_matrix: 相关性系数矩阵
            p_value_matrix: p值矩阵
        """
        factor_ids = list(factor_scores.keys())
        n_factors = len(factor_ids)
        
        # 初始化矩阵
        corr_matrix = np.eye(n_factors)  # 对角线为1
        pvalue_matrix = np.zeros((n_factors, n_factors))
        
        # 计算所有因子对的相关性
        for i in range(n_factors):
            for j in range(i + 1, n_factors):
                fid_i = factor_ids[i]
                fid_j = factor_ids[j]
                
                # 获取日期（如果提供）
                dates_i = factor_dates.get(fid_i) if factor_dates else None
                dates_j = factor_dates.get(fid_j) if factor_dates else None
                
                # 计算相关性
                result = self.calculate_pairwise(
                    factor_scores[fid_i], 
                    factor_scores[fid_j],
                    dates_i,
                    dates_j
                )
                
                corr_matrix[i, j] = result['correlation']
                corr_matrix[j, i] = result['correlation']
                pvalue_matrix[i, j] = result['p_value']
                pvalue_matrix[j, i] = result['p_value']
        
        # 转换为DataFrame
        corr_df = pd.DataFrame(corr_matrix, index=factor_ids, columns=factor_ids)
        pvalue_df = pd.DataFrame(pvalue_matrix, index=factor_ids, columns=factor_ids)
        
        return corr_df, pvalue_df
    
    def calculate_rolling_correlation(
        self,
        series1: np.ndarray,
        series2: np.ndarray,
        window: int = 20,
        min_periods: Optional[int] = None
    ) -> np.ndarray:
        """
        计算滚动窗口相关性
        
        参数：
            series1: 第一个时间序列
            series2: 第二个时间序列
            window: 滚动窗口大小
            min_periods: 最小计算期数
        
        返回：
            滚动相关性序列
        """
        if min_periods is None:
            min_periods = max(5, window // 4)
        
        # 确保序列长度相同
        if len(series1) != len(series2):
            raise ValueError("两个序列长度必须相同")
        
        n = len(series1)
        rolling_corr = np.full(n, np.nan)
        
        for i in range(window - 1, n):
            start_idx = i - window + 1
            
            # 提取窗口数据
            window1 = series1[start_idx:i+1]
            window2 = series2[start_idx:i+1]
            
            # 处理缺失值
            mask = ~(np.isnan(window1) | np.isnan(window2))
            valid1 = window1[mask]
            valid2 = window2[mask]
            
            if len(valid1) >= min_periods:
                if self.config['method'] == 'pearson':
                    corr = np.corrcoef(valid1, valid2)[0, 1]
                elif self.config['method'] == 'spearman':
                    corr = stats.spearmanr(valid1, valid2)[0]
                else:  # kendall
                    corr = stats.kendalltau(valid1, valid2)[0]
                
                rolling_corr[i] = corr
        
        return rolling_corr
    
    def calculate_average_correlation(
        self,
        target_factor_id: str,
        selected_factor_ids: List[str],
        factor_scores: Dict[str, np.ndarray],
        factor_dates: Optional[Dict[str, List[str]]] = None,
        weights: Optional[List[float]] = None
    ) -> Dict[str, float]:
        """
        计算目标因子与选中因子的平均相关性
        
        参数：
            target_factor_id: 目标因子ID
            selected_factor_ids: 选中因子ID列表
            factor_scores: 因子得分字典
            factor_dates: 因子日期字典 (可选)
            weights: 权重列表 (可选，默认等权)
        
        返回：
            包含平均相关性、加权相关性、最大相关性等的字典
        """
        if target_factor_id not in factor_scores:
            raise ValueError(f"目标因子不存在: {target_factor_id}")
        
        if not selected_factor_ids:
            return {
                'average': 0.0,
                'weighted_average': 0.0,
                'max': 0.0,
                'min': 0.0,
                'count': 0
            }
        
        correlations = []
        valid_selected = []
        
        for fid in selected_factor_ids:
            if fid not in factor_scores:
                warnings.warn(f"选中因子不存在: {fid}")
                continue
            
            # 计算相关性
            dates_target = factor_dates.get(target_factor_id) if factor_dates else None
            dates_selected = factor_dates.get(fid) if factor_dates else None
            
            result = self.calculate_pairwise(
                factor_scores[target_factor_id],
                factor_scores[fid],
                dates_target,
                dates_selected
            )
            
            correlations.append(result['correlation'])
            valid_selected.append(fid)
        
        if not correlations:
            return {
                'average': 0.0,
                'weighted_average': 0.0,
                'max': 0.0,
                'min': 0.0,
                'count': 0
            }
        
        correlations_array = np.array(correlations)
        
        # 计算各种统计量
        avg_corr = np.mean(correlations_array)
        max_corr = np.max(correlations_array)
        min_corr = np.min(correlations_array)
        
        # 加权平均相关性
        if weights is not None and len(weights) == len(correlations):
            weighted_avg = np.average(correlations_array, weights=weights)
        else:
            weighted_avg = avg_corr
        
        return {
            'average': float(avg_corr),
            'weighted_average': float(weighted_avg),
            'max': float(max_corr),
            'min': float(min_corr),
            'count': len(correlations),
            'std': float(np.std(correlations_array))
        }
    
    def _align_series(
        self,
        series1: np.ndarray,
        series2: np.ndarray,
        dates1: Optional[List[str]] = None,
        dates2: Optional[List[str]] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        对齐两个时间序列（处理缺失值和不同日期）
        
        返回：
            对齐后的两个序列
        """
        # 如果没有日期信息，直接处理缺失值
        if dates1 is None or dates2 is None:
            return self._handle_missing_values(series1, series2)
        
        # 如果有日期信息，按日期对齐
        return self._align_by_dates(series1, series2, dates1, dates2)
    
    def _handle_missing_values(
        self,
        series1: np.ndarray,
        series2: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """处理缺失值（无日期信息）"""
        handle_na = self.config.get('handle_na', 'drop')
        
        if handle_na == 'drop':
            # 删除任何序列中有缺失值的对应位置
            mask = ~(np.isnan(series1) | np.isnan(series2))
            return series1[mask], series2[mask]
        elif handle_na == 'fill':
            # 用均值填充缺失值
            series1_filled = series1.copy()
            series2_filled = series2.copy()
            
            series1_filled[np.isnan(series1_filled)] = np.nanmean(series1_filled)
            series2_filled[np.isnan(series2_filled)] = np.nanmean(series2_filled)
            
            return series1_filled, series2_filled
        else:
            raise ValueError(f"不支持的缺失值处理方法: {handle_na}")
    
    def _align_by_dates(
        self,
        series1: np.ndarray,
        series2: np.ndarray,
        dates1: List[str],
        dates2: List[str]
    ) -> Tuple[np.ndarray, np.ndarray]:
        """按日期对齐序列"""
        # 创建日期到索引的映射
        date_to_idx1 = {date: idx for idx, date in enumerate(dates1)}
        date_to_idx2 = {date: idx for idx, date in enumerate(dates2)}
        
        # 找到共同日期
        common_dates = set(dates1) & set(dates2)
        
        if not common_dates:
            return np.array([]), np.array([])
        
        # 提取共同日期的数据
        aligned_series1 = []
        aligned_series2 = []
        
        for date in sorted(common_dates):
            idx1 = date_to_idx1[date]
            idx2 = date_to_idx2[date]
            
            aligned_series1.append(series1[idx1])
            aligned_series2.append(series2[idx2])
        
        return np.array(aligned_series1), np.array(aligned_series2)
    
    def save_correlation_matrix(
        self,
        corr_matrix: pd.DataFrame,
        pvalue_matrix: pd.DataFrame,
        filepath: str
    ):
        """保存相关性矩阵到文件"""
        import json
        
        data = {
            'correlation_matrix': corr_matrix.to_dict(),
            'pvalue_matrix': pvalue_matrix.to_dict(),
            'config': self.config,
            'timestamp': pd.Timestamp.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    @classmethod
    def load_correlation_matrix(cls, filepath: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """从文件加载相关性矩阵"""
        import json
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        corr_matrix = pd.DataFrame(data['correlation_matrix'])
        pvalue_matrix = pd.DataFrame(data['pvalue_matrix'])
        
        return corr_matrix, pvalue_matrix


# 测试函数
def test_correlation_calculator():
    """测试相关性计算器"""
    print("测试相关性计算器...")
    
    # 创建测试数据
    np.random.seed(42)
    n_days = 100
    n_factors = 5
    
    # 生成因子得分
    factor_scores = {}
    factor_dates = {}
    
    dates = [f"2024-01-{i+1:02d}" for i in range(n_days)]
    
    for i in range(n_factors):
        factor_id = f"F{i:03d}"
        
        # 生成相关的时间序列
        base = np.random.randn(n_days)
        noise = np.random.randn(n_days) * 0.3
        
        # 使因子间有一定相关性
        if i > 0:
            # 与第一个因子相关
            correlation = 0.1 * i  # 逐渐增加相关性
            factor_scores[factor_id] = correlation * factor_scores["F000"] + np.sqrt(1 - correlation**2) * noise
        else:
            factor_scores[factor_id] = base
        
        factor_dates[factor_id] = dates
    
    # 创建计算器
    config = {
        'method': 'pearson',
        'min_common_periods': 10,
        'significance_level': 0.05,
        'handle_na': 'drop'
    }
    
    calculator = CorrelationCalculator(config)
    
    # 测试成对相关性
    print("\n1. 测试成对相关性:")
    result = calculator.calculate_pairwise(
        factor_scores["F000"], 
        factor_scores["F001"],
        factor_dates["F000"],
        factor_dates["F001"]
    )
    
    print(f"   F000 vs F001:")
    print(f"     相关性: {result['correlation']:.3f}")
    print(f"     p值: {result['p_value']:.4f}")
    print(f"     显著: {result['significant']}")
    print(f"     样本数: {result['n_obs']}")
    
    # 测试相关性矩阵
    print("\n2. 测试相关性矩阵:")
    corr_matrix, pvalue_matrix = calculator.calculate_correlation_matrix(
        factor_scores, factor_dates
    )
    
    print(f"   矩阵形状: {corr_matrix.shape}")
    print(f"   前3x3相关性矩阵:")
    print(corr_matrix.iloc[:3, :3])
    
    # 测试平均相关性
    print("\n3. 测试平均相关性:")
    avg_corr = calculator.calculate_average_correlation(
        target_factor_id="F000",
        selected_factor_ids=["F001", "F002", "F003"],
        factor_scores=factor_scores,
        factor_dates=factor_dates
    )
    
    print(f"   F000与选中因子的平均相关性:")
    for key, value in avg_corr.items():
        print(f"     {key}: {value:.3f}")
    
    # 测试滚动相关性
    print("\n4. 测试滚动相关性:")
    rolling_corr = calculator.calculate_rolling_correlation(
        factor_scores["F000"],
        factor_scores["F001"],
        window=20
    )
    
    print(f"   滚动相关性形状: {rolling_corr.shape}")
    print(f"   有效值数量: {np.sum(~np.isnan(rolling_corr))}")
    print(f"   最后5个值: {rolling_corr[-5:]}")
    
    # 测试保存和加载
    print("\n5. 测试保存和加载:")
    test_file = "test_correlation_matrix.json"
    calculator.save_correlation_matrix(corr_matrix, pvalue_matrix, test_file)
    
    loaded_corr, loaded_pvalue = CorrelationCalculator.load_correlation_matrix(test_file)
    print(f"   加载成功: {loaded_corr.shape == corr_matrix.shape}")
    
    # 清理测试文件
    import os
    if os.path.exists(test_file):
        os.remove(test_file)
    
    print("\n测试完成!")


if __name__ == "__main__":
    test_correlation_calculator()