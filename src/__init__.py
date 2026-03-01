"""
贝叶斯因子库维护系统
"""

# 导出核心类
from .core.mvp_selector import Factor, MVPBayesianSelector
from .core.integrated_selector import IntegratedBayesianSelector
from .simulation.stock_simulator import ProperStockSimulator

__version__ = "1.0.0"
__author__ = "小鱼爬爬量化研究助手"
__description__ = "贝叶斯因子库维护系统 - 从AlphaPROBE抽取的贝叶斯检索器模块"

# 简化导入
StockSimulator = ProperStockSimulator  # 别名

__all__ = [
    "Factor",
    "MVPBayesianSelector", 
    "IntegratedBayesianSelector",
    "ProperStockSimulator",
    "StockSimulator"
]