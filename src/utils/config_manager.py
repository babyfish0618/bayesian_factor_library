"""
配置管理器
从YAML/JSON文件读取配置，支持热更新和验证
"""

import yaml
import json
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EvaluationConfig:
    """评价配置数据类"""
    
    # 时间窗口配置
    time_windows: Dict[str, Any] = field(default_factory=lambda: {
        'selection': {'short_term': 5, 'medium_term': 20, 'long_term': 60},
        'evaluation': {
            'selected_short': 10, 'selected_long': 20,
            'unselected_short': 20, 'unselected_long': 40
        },
        'ic_calculation': {'min_periods': 10, 'rolling_window': 20}
    })
    
    # 指标权重
    indicator_weights: Dict[str, Any] = field(default_factory=lambda: {
        'selection': {
            'icir': 0.4, 'ls_return': 0.3, 
            'rank_percentile': 0.2, 'stability': 0.1
        },
        'evaluation': {
            'selected': {'icir': 0.5, 'ls_return': 0.3, 'rank_percentile': 0.2},
            'unselected': {
                'icir': 0.6, 'ls_return': 0.2, 
                'rank_percentile': 0.1, 'marginal_contrib': 0.1
            }
        }
    })
    
    # 成功阈值
    success_thresholds: Dict[str, Any] = field(default_factory=lambda: {
        'selected': {
            'icir': 0.8, 'ls_return_annual': 0.05,
            'rank_percentile': 0.7, 'win_rate': 0.55
        },
        'unselected': {
            'icir': 1.5, 'ls_return_annual': 0.10,
            'rank_percentile': 0.5, 'win_rate': 0.60,
            'max_correlation': 0.6
        }
    })
    
    # 贝叶斯参数
    bayesian: Dict[str, Any] = field(default_factory=lambda: {
        'prior_alpha': 1.0, 'prior_beta': 1.0,
        'update_rules': {
            'selected_success': 1.0, 'selected_failure': 1.0,
            'unselected_success': 0.5, 'unselected_failure': 0.0
        }
    })
    
    # 相关性计算
    correlation: Dict[str, Any] = field(default_factory=lambda: {
        'method': 'pearson', 'min_common_periods': 20,
        'significance_level': 0.05
    })
    
    # 边际贡献
    marginal_contribution: Dict[str, Any] = field(default_factory=lambda: {
        'simulation_method': 'portfolio_optimization',
        'portfolio_methods': ['equal_weight', 'icir_weighted', 'sharpe_optimized'],
        'replacement_strategy': 'correlation_based',
        'improvement_threshold': 0.01
    })
    
    # 归一化配置
    normalization: Dict[str, Any] = field(default_factory=lambda: {
        'icir': {'method': 'sigmoid', 'scale_factor': 3.0, 'shift': 0.0},
        'ls_return': {'method': 'linear', 'max_value': 0.50, 'min_value': -0.20},
        'rank_percentile': {'method': 'inverse'}
    })
    
    # 调试配置
    debug: Dict[str, Any] = field(default_factory=lambda: {
        'log_level': 'INFO', 'save_intermediate': True,
        'plot_figures': False, 'performance_tracking': True
    })
    
    # 元数据
    version: str = "1.0.0"
    description: str = "贝叶斯因子选择器评价配置"
    last_updated: str = "2026-03-01"
    
    def validate(self) -> bool:
        """验证配置有效性"""
        try:
            # 验证时间窗口
            for key, value in self.time_windows['selection'].items():
                if not isinstance(value, int) or value <= 0:
                    raise ValueError(f"时间窗口 {key} 必须为正整数")
            
            # 验证权重和为1
            for category, weights in self.indicator_weights.items():
                if isinstance(weights, dict):
                    # 处理嵌套字典结构（如evaluation包含selected/unselected）
                    if category == 'evaluation':
                        for sub_category, sub_weights in weights.items():
                            if isinstance(sub_weights, dict):
                                total = sum(w for w in sub_weights.values() if isinstance(w, (int, float)))
                                if abs(total - 1.0) > 0.01:
                                    raise ValueError(f"{category}.{sub_category} 权重和必须为1.0，当前为{total}")
                    else:
                        total = sum(w for w in weights.values() if isinstance(w, (int, float)))
                        if abs(total - 1.0) > 0.01:
                            raise ValueError(f"{category} 权重和必须为1.0，当前为{total}")
            
            # 验证阈值合理性
            if self.success_thresholds['selected']['icir'] >= self.success_thresholds['unselected']['icir']:
                raise ValueError("没选中因子ICIR阈值必须大于选中因子阈值")
            
            if self.success_thresholds['selected']['ls_return_annual'] >= self.success_thresholds['unselected']['ls_return_annual']:
                raise ValueError("没选中因子收益阈值必须大于选中因子阈值")
            
            return True
            
        except Exception as e:
            print(f"配置验证失败: {e}")
            return False
    
    def get_window_weights(self) -> Dict[int, float]:
        """获取时间窗口权重"""
        selection_windows = self.time_windows['selection']
        windows = list(selection_windows.values())
        
        # 默认权重：短期0.3，中期0.4，长期0.3
        if len(windows) == 3:
            return {windows[0]: 0.3, windows[1]: 0.4, windows[2]: 0.3}
        else:
            # 等权
            weight = 1.0 / len(windows)
            return {w: weight for w in windows}
    
    def get_indicator_weights_for_selection(self) -> Dict[str, float]:
        """获取选择因子时的指标权重"""
        return self.indicator_weights.get('selection', {})
    
    def get_evaluation_window(self, factor_type: str = 'selected') -> Dict[str, int]:
        """获取评估窗口"""
        eval_windows = self.time_windows['evaluation']
        
        if factor_type == 'selected':
            return {
                'short': eval_windows.get('selected_short', 10),
                'long': eval_windows.get('selected_long', 20)
            }
        else:  # unselected
            return {
                'short': eval_windows.get('unselected_short', 20),
                'long': eval_windows.get('unselected_long', 40)
            }


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        # 默认配置文件路径
        self.default_config_path = self.config_dir / "evaluation_config.yaml"
        self.user_config_path = self.config_dir / "user_config.yaml"
        
        # 当前配置
        self.config: Optional[EvaluationConfig] = None
        
        # 加载配置
        self.load_config()
    
    def load_config(self, config_path: Optional[str] = None) -> bool:
        """加载配置"""
        try:
            if config_path:
                filepath = Path(config_path)
            elif self.user_config_path.exists():
                filepath = self.user_config_path
            else:
                filepath = self.default_config_path
                
            if not filepath.exists():
                print(f"配置文件不存在: {filepath}")
                print("使用默认配置...")
                self.config = EvaluationConfig()
                return True
            
            # 读取YAML文件
            with open(filepath, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            # 创建配置对象
            self.config = EvaluationConfig()
            
            # 更新配置
            for key, value in config_data.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
            
            # 验证配置
            if not self.config.validate():
                print("配置验证失败，使用默认配置")
                self.config = EvaluationConfig()
                return False
            
            print(f"配置加载成功: {filepath}")
            print(f"版本: {self.config.version}")
            return True
            
        except Exception as e:
            print(f"加载配置失败: {e}")
            self.config = EvaluationConfig()
            return False
    
    def save_config(self, config_path: Optional[str] = None) -> bool:
        """保存配置"""
        if self.config is None:
            print("没有配置可保存")
            return False
        
        try:
            filepath = Path(config_path) if config_path else self.user_config_path
            
            # 转换为字典
            config_dict = {
                'time_windows': self.config.time_windows,
                'indicator_weights': self.config.indicator_weights,
                'success_thresholds': self.config.success_thresholds,
                'bayesian': self.config.bayesian,
                'correlation': self.config.correlation,
                'marginal_contribution': self.config.marginal_contribution,
                'normalization': self.config.normalization,
                'debug': self.config.debug,
                'version': self.config.version,
                'description': self.config.description,
                'last_updated': self.config.last_updated
            }
            
            # 保存为YAML
            with open(filepath, 'w', encoding='utf-8') as f:
                yaml.dump(config_dict, f, default_flow_style=False, allow_unicode=True)
            
            print(f"配置保存成功: {filepath}")
            return True
            
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def create_default_config(self) -> bool:
        """创建默认配置文件"""
        self.config = EvaluationConfig()
        return self.save_config(self.default_config_path)
    
    def update_config(self, updates: Dict[str, Any]) -> bool:
        """更新配置"""
        if self.config is None:
            print("配置未加载")
            return False
        
        try:
            for key, value in updates.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)
                else:
                    print(f"警告: 未知配置项 {key}")
            
            # 验证更新后的配置
            if not self.config.validate():
                print("更新后配置验证失败")
                return False
            
            print("配置更新成功")
            return True
            
        except Exception as e:
            print(f"更新配置失败: {e}")
            return False
    
    def get_config_summary(self) -> Dict[str, Any]:
        """获取配置摘要"""
        if self.config is None:
            return {}
        
        return {
            'version': self.config.version,
            'time_windows': {
                'selection': self.config.time_windows.get('selection', {}),
                'evaluation': self.config.time_windows.get('evaluation', {})
            },
            'indicator_weights': {
                'selection': self.config.indicator_weights.get('selection', {}),
                'evaluation_selected': self.config.indicator_weights.get('evaluation', {}).get('selected', {}),
                'evaluation_unselected': self.config.indicator_weights.get('evaluation', {}).get('unselected', {})
            },
            'success_thresholds': {
                'selected_icir': self.config.success_thresholds.get('selected', {}).get('icir', 0.8),
                'unselected_icir': self.config.success_thresholds.get('unselected', {}).get('icir', 1.5),
                'selected_ls_return': self.config.success_thresholds.get('selected', {}).get('ls_return_annual', 0.05),
                'unselected_ls_return': self.config.success_thresholds.get('unselected', {}).get('ls_return_annual', 0.10)
            }
        }
    
    def print_summary(self):
        """打印配置摘要"""
        summary = self.get_config_summary()
        
        print("=" * 60)
        print("配置摘要")
        print("=" * 60)
        print(f"版本: {summary.get('version', 'N/A')}")
        
        print("\n时间窗口:")
        time_windows = summary.get('time_windows', {})
        print(f"  选择窗口: {time_windows.get('selection', {})}")
        print(f"  评估窗口: {time_windows.get('evaluation', {})}")
        
        print("\n指标权重:")
        weights = summary.get('indicator_weights', {})
        print(f"  选择权重: {weights.get('selection', {})}")
        print(f"  评估-选中权重: {weights.get('evaluation_selected', {})}")
        print(f"  评估-没选中权重: {weights.get('evaluation_unselected', {})}")
        
        print("\n成功阈值:")
        thresholds = summary.get('success_thresholds', {})
        print(f"  选中ICIR: >{thresholds.get('selected_icir', 0.8)}")
        print(f"  没选中ICIR: >{thresholds.get('unselected_icir', 1.5)}")
        print(f"  选中年化收益: >{thresholds.get('selected_ls_return', 0.05):.1%}")
        print(f"  没选中年化收益: >{thresholds.get('unselected_ls_return', 0.10):.1%}")
        
        print("\n" + "=" * 60)


# 测试函数
def test_config_manager():
    """测试配置管理器"""
    print("测试配置管理器...")
    
    # 创建配置管理器
    config_dir = "test_config"
    manager = ConfigManager(config_dir)
    
    # 打印摘要
    manager.print_summary()
    
    # 测试更新配置
    print("\n测试更新配置...")
    updates = {
        'success_thresholds': {
            'selected': {'icir': 0.9, 'ls_return_annual': 0.06},
            'unselected': {'icir': 1.6, 'ls_return_annual': 0.12}
        }
    }
    
    if manager.update_config(updates):
        print("配置更新成功")
        manager.print_summary()
    
    # 测试保存和加载
    print("\n测试保存和加载...")
    test_config_path = "test_config/test_config.yaml"
    if manager.save_config(test_config_path):
        print(f"配置保存到: {test_config_path}")
    
    # 重新加载
    manager2 = ConfigManager(config_dir)
    if manager2.load_config(test_config_path):
        print("配置重新加载成功")
        manager2.print_summary()
    
    # 清理测试文件
    import shutil
    if os.path.exists(config_dir):
        shutil.rmtree(config_dir)
    
    print("\n测试完成!")


if __name__ == "__main__":
    test_config_manager()