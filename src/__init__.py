"""
贝叶斯因子库维护系统
"""

# 导出当前主链路核心类
from .core.bayesian_selector_v2 import BayesianSelectorV2
from .core.factor_enhanced import EnhancedFactor, FactorPerformance
from .simulation.latent_factor_data_simulator import (
    LatentFactorDataSimulator,
    LatentFactorSimulationConfig,
)

__version__ = "1.0.0"
__author__ = "小鱼爬爬量化研究助手"
__description__ = "贝叶斯因子库维护系统 - 从AlphaPROBE抽取的贝叶斯检索器模块"

__all__ = [
    "BayesianSelectorV2",
    "EnhancedFactor",
    "FactorPerformance",
    "LatentFactorDataSimulator",
    "LatentFactorSimulationConfig",
]
