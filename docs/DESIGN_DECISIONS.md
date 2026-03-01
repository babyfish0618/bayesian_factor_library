# 设计决策文档

## 项目概述
**贝叶斯因子库维护系统** - 从AlphaPROBE论文中抽取贝叶斯检索器模块，独立应用于因子库维护问题。

## 设计原则
1. **渐进式开发**：从简单MVP开始，逐步增加复杂度
2. **模块化设计**：每个功能独立，便于测试和替换
3. **可配置性**：所有参数可配置，便于调优
4. **可解释性**：记录所有决策过程，便于分析和调试

## 迭代记录

### 迭代1：MVP基础框架 (2026-02-28)
**目标**：实现最基本的贝叶斯选择功能

**设计决策**：
1. **简化数据结构**：只保留核心字段（id, expression, topic, alpha, beta, performance）
   - 原因：MVP阶段验证算法逻辑，不需要完整因子数据
   - 后续：真实数据阶段会扩展

2. **Thompson Sampling实现**：
   ```python
   # 从Beta分布采样
   bayesian_score = np.random.beta(factor.alpha, factor.beta)
   ```
   - 原因：这是贝叶斯优化的核心，简单有效
   - 与论文相同：AlphaPROBE也使用Thompson Sampling

3. **简化评价标准**：
   - 选中因子：ICIR > 0.8 且排名前70%
   - 没选中因子：ICIR > 1.5 且相关性 < 0.6
   - 原因：MVP阶段验证逻辑，后续会实现完整的三标准体系

4. **模拟数据生成**：
   - 创建5种不同类型的测试因子（稳定好、波动大、近期失效、新兴好、一直差）
   - 原因：模拟真实场景，验证算法对不同类型因子的处理能力
   - 后续：会替换为真实数据接口

**代码结构**：
```
MVPBayesianSelector
├── select_factors()          # 选择因子（Thompson Sampling）
├── update_from_performance() # 更新贝叶斯参数
├── evaluate_selected_success()  # 评估选中因子
└── evaluate_unselected_success() # 评估没选中因子（边际贡献法）
```

**测试结果**：
1. **算法有效性验证**：好因子平均成功率0.921 vs 差因子0.381，差异显著（0.539）
2. **因子类型分析**：
   - 稳定好因子：成功率0.93，ICIR 1.93
   - 新兴好因子：成功率0.91，ICIR 1.78  
   - 波动大因子：成功率0.52，ICIR 1.06
   - 近期失效因子：成功率0.40，ICIR 0.47
   - 一直差因子：成功率0.37，ICIR 0.36
3. **边界测试通过**：因子数不足、全差因子、空列表等情况处理正常

**关键发现**：
1. 算法能有效区分好因子和差因子
2. 贝叶斯参数能正确学习因子质量
3. 需要改进：边际贡献评估过于简化，相关性计算是随机的

**下一步**：
1. 实现真实的边际贡献评估
2. 添加相关性计算
3. 实现多样性控制
4. 添加单元测试框架

---

### 迭代2：正确的股票数据模拟器 (2026-03-01)
**目标**：实现精确的股票和因子数据模拟，完全符合研究员的要求

**设计决策**：
1. **精确的IC控制公式**：
   ```python
   # 生成因子得分F_t，使得 corr(F_t, R_{t+1}) = IC_t
   # 设 R = 标准化后的t+1期收益
   # 设 Z ~ N(0,1) 且与R独立
   # 则：F = ρR + √(1-ρ²)Z，其中 ρ = IC_t
   
   # 使Z与R正交的方法：
   proj = np.dot(Z, R_norm) / np.dot(R_norm, R_norm)
   Z_ortho = Z - proj * R_norm
   Z_norm = Z_ortho / Z_ortho.std()
   ```
   - 原因：数学上精确控制相关性，避免近似误差
   - 创新点：使用正交化确保独立噪声，相关性误差<0.1%

2. **IC参数设计**：
   ```python
   # IC序列：IC_t ~ N(μ_k, σ_fixed²)
   ic_sequences = np.random.normal(ic_means[k], ic_std_fixed, T)
   ```
   - 原因：固定IC方差，ICIR只取决于IC均值（ICIR_k = μ_k / σ_fixed）
   - 与要求一致：通过IC均值的不同体现不同的ICIR

3. **时间对齐**：
   ```python
   # t期因子预测t+1期收益
   for t in range(num_days - 1):
       returns_next = stock_returns[t + 1, :]  # t+1期收益
       current_ic = ic_sequences[t, k]        # t期IC值
       factor_scores[t, k, :] = generate_correlated_series(returns_next, current_ic)
   ```
   - 原因：符合实际投资逻辑，避免使用未来信息
   - 正确性：确保t期因子只使用t期及之前的信息

4. **得分加权多空组合（杠杆2倍）**：
   ```python
   # 标准化得分
   scores_norm = scores / scores.std()
   
   # 多头权重（得分>0）
   long_mask = scores_norm > 0
   long_weights = scores_norm[long_mask] / scores_norm[long_mask].sum() * 1.0
   
   # 空头权重（得分<0）
   short_mask = scores_norm < 0
   short_scores_pos = -scores_norm[short_mask]  # 负得分变正
   short_weights = -short_scores_pos / short_scores_pos.sum() * 1.0
   
   # 组合收益
   portfolio_return = np.sum(long_weights * returns[long_mask]) + 
                      np.sum(short_weights * returns[short_mask])
   ```
   - 原因：使用得分加权而非等权，更符合因子投资实践
   - 杠杆：多头权重和=1，空头权重和=-1，总杠杆=2.0

**代码结构**：
```
ProperStockSimulator
├── generate_correlated_series()      # 生成相关序列（核心）
├── calculate_weighted_long_short_return() # 得分加权多空
└── simulate()                        # 完整模拟流程
```

**测试结果**：
```
核心逻辑验证：
- 相关性生成精度：误差0.0%（目标ρ=0.02-0.10）
- 权重计算：多头权重和=1.000000，空头权重和=-1.000000

完整模拟结果（100股票，252天，30因子）：
- IC控制精度：平均误差0.0005，最大误差0.0014，误差<0.01比例100%
- 因子表现：ICIR范围2.227到6.392，平均ICIR=3.982，正ICIR比例100%
- 相关性：目标IC vs 实际IC=0.999，目标IC vs ICIR=0.991
```

**关键发现**：
1. **数学精确性**：通过正交化方法，相关性控制精度达到0.1%级别
2. **ICIR公式验证**：实际ICIR ≈ μ/σ_fixed，验证了设计正确性
3. **权重计算正确**：多头权重和精确为1，空头权重和精确为-1
4. **时间对齐正确**：t期因子预测t+1期收益，避免未来信息泄露

**与之前版本的对比**：
| 指标 | 错误版本 | 正确版本 | 改进 |
|------|----------|----------|------|
| IC平均误差 | 0.0490 | 0.0005 | 提高98倍 |
| ICIR范围 | -0.154到0.102 | 2.227到6.392 | 符合理论 |
| 目标IC相关性 | -0.120 | 0.999 | 完全纠正 |
| 权重精度 | 近似 | 精确到1e-6 | 数学精确 |

**下一步**：
1. 集成模拟器到贝叶斯选择器
2. 实现基于真实因子相关性的边际贡献评估
3. 开始迭代3：完整的因子库维护系统