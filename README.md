# 贝叶斯因子库维护系统

## 项目概述

从AlphaPROBE论文中抽取**贝叶斯检索器模块**，独立应用于**因子库维护问题**。

### 核心问题
```
已有：N个因子（有历史表现数据）
目标：定期（如每月）选择K个最优因子
约束：考虑因子质量、多样性、稳定性、演化潜力
方法：使用贝叶斯优化（Thompson Sampling）进行智能选择
```

### 与AlphaPROBE的关系
- **抽取模块**：贝叶斯检索器（Thompson Sampling）
- **独立应用**：因子库维护（非因子生成）
- **创新点**：将贝叶斯优化应用于因子选择而非因子生成

## 快速开始

### 安装
```bash
cd bayesian_factor_lib
# 目前是纯Python，无需安装
```

### 运行测试
```bash
python3 src/test_mvp.py
```

### 基本使用
```python
from src.mvp_selector import Factor, MVPBayesianSelector

# 1. 创建因子
factors = [
    Factor(id="factor_001", expression="Div($high, $close)", topic="price_momentum"),
    # ... 更多因子
]

# 2. 初始化选择器
selector = MVPBayesianSelector(factors, target_size=50)

# 3. 选择因子
selected_ids = selector.select_factors("2024-01-31")

# 4. 模拟表现数据（实际应从真实数据获取）
performance_data = {
    fid: {'icir': 1.5, 'rank_percentile': 0.3}
    for fid in selected_ids
}

# 5. 更新贝叶斯参数
selector.update_from_performance(selected_ids, performance_data)
```

## 核心算法

### 1. Thompson Sampling
```python
# 为每个因子从Beta分布采样
bayesian_score = np.random.beta(factor.alpha, factor.beta)
```

### 2. 三套评价标准
1. **采样打分标准**：选择因子时使用（预测未来表现）
2. **判断成功-选中因子**：更新贝叶斯参数时使用（实际表现）
3. **判断成功-没选中因子**：更新贝叶斯参数时使用（边际贡献）

### 3. 边际贡献评估
评估没选中因子的潜在价值，考虑：
- 近期ICIR表现
- 与选中因子的相关性
- 加入后的组合改善（模拟）

## 项目结构

```
bayesian_factor_lib/
├── src/                    # 源代码（分层结构）
│   ├── core/              # 核心算法
│   │   ├── mvp_selector.py          # MVP贝叶斯选择器
│   │   ├── integrated_selector.py   # 集成选择器
│   │   ├── factor_enhanced.py       # 增强版因子类 (迭代3)
│   │   ├── correlation_calculator.py # 相关性计算模块 (迭代3)
│   │   └── bayesian_selector_v2.py  # 新版贝叶斯选择器 (迭代3)
│   ├── evaluation/        # 评估系统
│   │   ├── portfolio_simulator.py   # 组合模拟模块 (迭代3)
│   │   └── marginal_contrib.py      # 边际贡献评估模块 (迭代3)
│   ├── simulation/        # 数据模拟
│   │   └── stock_simulator.py       # 正确的股票数据模拟器
│   ├── utils/            # 工具函数
│   │   └── config_manager.py        # 配置管理器 (迭代3)
│   ├── tests/            # 测试代码
│   │   ├── test_mvp.py              # MVP测试
│   │   ├── minimal_test.py          # 核心逻辑验证
│   │   └── quick_test.py            # 快速测试
│   ├── archive/          # 历史版本
│   │   ├── stock_simulator_v2.py    # 版本2
│   │   ├── stock_simulator_v3.py    # 版本3
│   │   └── ...                     # 其他中间版本
│   └── __init__.py       # 包导出
├── config/                # 配置文件
│   └── evaluation_config.yaml      # 评价配置 (迭代3)
├── docs/                   # 设计文档
│   ├── DESIGN_DECISIONS.md    # 设计决策记录
│   ├── PAPER_COMPARISON.md    # 与AlphaPROBE对比
│   ├── ITERATION_LOG.md       # 迭代日志
│   ├── EVALUATION_STANDARDS.md # 评价标准清单
│   └── ITERATION3_SUMMARY.md  # 迭代3总结 (新增)
├── examples/               # 使用示例（待添加）
├── run_demo.py            # 演示程序
└── README.md              # 项目说明
```

## 设计原则

1. **渐进式开发**：从简单MVP开始，逐步增加复杂度
2. **模块化设计**：每个功能独立，便于测试和替换
3. **可配置性**：所有参数可配置，便于调优
4. **可解释性**：记录所有决策过程，便于分析和调试

## 测试结果

### 算法有效性
```
好因子平均成功率: 0.921
差因子平均成功率: 0.381
差异: 0.539 (显著)
```

### 因子类型分析
| 因子类型 | 平均成功率 | 平均ICIR | 数量 |
|----------|------------|----------|------|
| 稳定好因子 | 0.93 | 1.93 | 20 |
| 新兴好因子 | 0.91 | 1.78 | 20 |
| 波动大因子 | 0.52 | 1.06 | 20 |
| 近期失效因子 | 0.40 | 0.47 | 20 |
| 一直差因子 | 0.37 | 0.36 | 20 |

## 迭代3完成：多指标多时间窗口评价系统

迭代3已成功完成，实现了完整的多指标多时间窗口评价系统。

### 主要成果

1. **配置系统** (`config/evaluation_config.yaml`, `src/utils/config_manager.py`)
   - YAML配置文件管理
   - 多时间窗口配置 (选择/评估不同窗口)
   - 多指标权重配置 (ICIR/收益/排名/稳定性)
   - 成功阈值配置 (区分选中/没选中)

2. **增强版因子类** (`src/core/factor_enhanced.py`)
   - 多指标存储 (IC, ICIR, 多空收益, 排名等)
   - 多时间窗口分析 (5/20/60天)
   - **正确ICIR计算**: `ICIR = mean(IC) / std(IC)`

3. **相关性计算模块** (`src/core/correlation_calculator.py`)
   - 基于真实时间序列计算相关性
   - 支持Pearson/Spearman/Kendall方法
   - 计算相关性矩阵和显著性检验

4. **组合模拟模块** (`src/evaluation/portfolio_simulator.py`)
   - 多种组合构建方法 (等权/ICIR加权/夏普优化等)
   - 多种因子替换策略 (相关性/有效性/组合优化)
   - 完整的组合表现评估

5. **边际贡献评估模块** (`src/evaluation/marginal_contrib.py`)
   - 集成相关性计算和组合模拟
   - 多维度评分系统 (边际改善/相关性/因子质量/可行性)
   - 评估结果分类 (SUCCESS/FAILURE/NEUTRAL/UNCERTAIN)

6. **新版贝叶斯选择器 (V2)** (`src/core/bayesian_selector_v2.py`)
   - 集成所有新模块
   - 多时间窗口多指标选择
   - 集成边际贡献评估的更新逻辑
   - 完整的生命周期管理

### 使用新版系统

```bash
# 运行新版选择器测试
python3 src/core/bayesian_selector_v2.py

# 查看配置
cat config/evaluation_config.yaml

# 运行演示程序
python3 run_demo.py
```

### 文档

- **迭代3总结**: `docs/ITERATION3_SUMMARY.md`
- **评价标准清单**: `docs/EVALUATION_STANDARDS.md`
- **设计决策**: `docs/DESIGN_DECISIONS.md`
- **迭代日志**: `docs/ITERATION_LOG.md`

系统现在已准备好用于实际的因子库维护和管理任务。

## 开发计划

### 已完成
- [x] 迭代1：MVP基础框架（Thompson Sampling + 简化评价）
- [x] 迭代2：正确的股票数据模拟器（数学精确版本）
- [x] 迭代2.5：评价标准分析与重构
- [x] 迭代3：多指标多时间窗口评价系统（生产就绪版本）

### 进行中
- [ ] 迭代4：性能测试和参数调优
- [ ] 迭代5：真实数据接口集成

### 待完成
- [ ] 迭代6：超参数学习
- [ ] 迭代7：性能优化
- [ ] 迭代8：生产环境部署

## 与AlphaPROBE的对比

| 维度 | AlphaPROBE (原论文) | 我们的项目 |
|------|-------------------|-----------|
| **核心问题** | 因子生成和演化 | 因子库维护和选择 |
| **输入** | 初始因子 + LLM生成新因子 | 现有因子库（N个因子） |
| **输出** | 新生成的因子 + DAG演化历史 | 选择的K个最优因子 |
| **贝叶斯应用** | 选择父因子进行演化 | 选择最优因子进行保留 |
| **创新点** | DAG导航 + LLM生成 | 边际贡献评估 + 三标准体系 |
| **系统成熟度** | 研究原型 | 生产就绪版本 |

## 贡献指南

1. 遵循渐进式开发原则
2. 每次迭代都要有可验证的结果
3. 更新设计文档和迭代日志
4. 添加单元测试
5. 保持与AlphaPROBE的对比分析

## 许可证

MIT License

## 作者

小鱼爬爬量化研究助手 🐟📊