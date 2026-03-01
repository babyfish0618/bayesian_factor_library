# 评价标准与参数清单 - MVP版本

## 概述
本文档记录当前MVP版本中所有评价标准、参数设置及相关函数。
用于后续迭代的调整和优化参考。

## 一、核心评价标准体系

### 1.1 三套评价标准（设计理念）
```
1. 采样打分标准 (Scoring for Selection)
   - 用途：选择因子时使用
   - 特点：预测性、多窗口、平衡利用与探索

2. 判断成功-选中因子 (Success Evaluation for Selected Factors)
   - 用途：更新选中因子的贝叶斯参数
   - 特点：实际表现、相对宽松、基于真实结果

3. 判断成功-没选中因子 (Success Evaluation for Unselected Factors)
   - 用途：更新没选中因子的贝叶斯参数
   - 特点：边际贡献、非常严格、基于模拟评估
```

## 二、具体参数设置

### 2.1 配置参数（`_get_default_config()`）

#### 2.1.1 采样打分权重
```python
'scoring_weights': {
    'bayesian': 0.7,      # 贝叶斯部分权重（Thompson Sampling）
    'recent_perf': 0.3,   # 近期表现权重（ICIR）
}
```

#### 2.1.2 成功阈值
```python
'success_thresholds': {
    # 选中因子标准（相对宽松）
    'selected_icir': 0.8,      # ICIR > 0.8
    'selected_rank': 0.7,      # 排名在前70%（rank_percentile < 0.7）
    
    # 没选中因子标准（非常严格）
    'unselected_icir': 1.5,    # ICIR > 1.5（几乎2倍于选中标准）
    'unselected_corr': 0.6,    # 与选中因子平均相关性 < 0.6
}
```

#### 2.1.3 时间窗口
```python
'time_windows': {
    'recent_performance': 3,  # 近期表现回看期数
}
```

## 三、核心函数与算法

### 3.1 因子选择 (`select_factors()`)

#### 算法流程：
1. **贝叶斯得分计算**：
   ```python
   bayesian_score = np.random.beta(factor.alpha, factor.beta)
   ```
   - 函数：`np.random.beta(alpha, beta)`
   - 原理：Thompson Sampling，从后验Beta分布采样
   - 权重：0.7

2. **近期表现得分计算**：
   ```python
   recent_icir = factor.get_recent_icir(lookback=3)
   recent_score = self._normalize_icir_score(recent_icir)
   ```
   - 函数：`factor.get_recent_icir()` → 取最近3期ICIR均值
   - 归一化：`_normalize_icir_score(icir)` → `min(max(icir/3.0, 0.0), 1.0)`
   - 权重：0.3

3. **综合得分**：
   ```python
   total_score = 0.7 * bayesian_score + 0.3 * recent_score
   ```

### 3.2 选中因子成功评估 (`_evaluate_selected_success()`)

#### 评估标准：
```python
success = (
    icir > 0.8 and                # ICIR阈值
    rank_percentile < 0.7         # 排名阈值
)
```

#### 参数说明：
- `icir`: 当期ICIR（从`performance_data`获取）
- `rank_percentile`: 排名百分位（0-1，越小越好）
- 逻辑：**AND**关系，必须同时满足

#### 更新规则：
- 成功：`alpha += 1`
- 失败：`beta += 1`

### 3.3 没选中因子成功评估 (`_evaluate_unselected_success()`)

#### 评估标准（三重过滤）：
1. **ICIR过滤**：
   ```python
   recent_icir = factor.get_recent_icir()  # 最近3期均值
   if recent_icir < 1.5: return False
   ```

2. **相关性过滤**：
   ```python
   avg_correlation = self._estimate_average_correlation(factor, selected_ids)
   if avg_correlation > 0.6: return False
   ```

3. **边际贡献过滤**：
   ```python
   marginal_improvement = self._simulate_marginal_improvement(factor, selected_ids)
   if marginal_improvement <= 0: return False
   ```

#### 模拟函数说明：
- `_estimate_average_correlation()`: **随机模拟**（MVP简化）
  - 范围：0.2-0.8
  - 固定随机种子：`hash(factor.id) % 1000`
  
- `_simulate_marginal_improvement()`: **启发式模拟**
  ```python
  marginal_improvement = recent_icir * (1 - avg_corr) * 0.1
  ```

#### 更新规则：
- 成功：`alpha += 1`（只增加α，不轻易惩罚）
- 失败：**不更新**（保持原参数）

### 3.4 归一化函数 (`_normalize_icir_score()`)

#### 算法：
```python
def _normalize_icir_score(self, icir: float) -> float:
    return min(max(icir / 3.0, 0.0), 1.0)
```

#### 设计决策：
- 线性归一化：ICIR=3.0时得1.0
- 截断处理：确保结果在[0,1]区间
- 后续可优化：sigmoid函数、对数变换等

## 四、默认值与假设

### 4.1 贝叶斯先验
```python
alpha = 1.0  # 初始成功次数
beta = 1.0   # 初始失败次数
```
- 等价于：`Beta(1,1)` = `Uniform(0,1)`
- 无信息先验，完全由数据驱动

### 4.2 近期表现默认值
```python
def get_recent_icir(self, lookback: int = 3) -> float:
    if not self.performance:
        return 1.0  # 默认值
```
- 无历史数据时：返回1.0（中性假设）

### 4.3 性能数据默认值
```python
performance_data.get(fid, {})
icir = perf.get('icir', 0)           # 默认0
rank = perf.get('rank_percentile', 1.0)  # 默认1.0（最差）
```

## 五、与AlphaPROBE的对比

### 5.1 相同点
1. **Thompson Sampling核心**：都使用`Beta(α,β)`分布采样
2. **贝叶斯更新框架**：基于成功/失败更新α,β参数
3. **多标准评价**：考虑多个维度（ICIR、排名等）

### 5.2 不同点（我们的创新）
| 维度 | AlphaPROBE | 我们的实现 |
|------|-----------|-----------|
| **没选中因子评估** | 未明确提及 | 专门设计边际贡献法 |
| **评价标准区分** | 可能统一标准 | 明确三套不同标准 |
| **相关性考虑** | DAG结构考虑 | 简单相关性阈值 |
| **边际贡献模拟** | 未明确提及 | 启发式模拟实现 |

### 5.3 参数差异
- **ICIR阈值**：我们区分选中(0.8)和没选中(1.5)
- **排名阈值**：我们使用0.7（前70%）
- **相关性阈值**：我们设定0.6（没选中因子）

## 六、待优化问题

### 6.1 硬编码参数
- 所有阈值和权重都是硬编码
- 缺乏自适应学习机制

### 6.2 简化模拟
- 相关性估计：随机模拟，非真实计算
- 边际贡献：启发式公式，非真实组合模拟

### 6.3 时间窗口固定
- 近期表现：固定3期
- 缺乏多时间尺度融合

### 6.4 归一化函数简单
- 线性归一化可能不合理
- 未考虑ICIR分布特性

## 七、迭代建议

### 7.1 短期优化（迭代3）
1. **实现真实相关性计算**
2. **改进边际贡献模拟**
3. **参数可配置化**

### 7.2 中期优化
1. **自适应阈值学习**
2. **多时间窗口融合**
3. **非线性归一化函数**

### 7.3 长期优化
1. **集成真实数据接口**
2. **考虑因子交互效应**
3. **实现多样性控制**

## 八、测试验证

### 8.1 当前测试结果
```
好因子平均成功率: 0.921
差因子平均成功率: 0.381
差异: 0.539 (显著)
```

### 8.2 参数敏感性
需要测试：
1. 权重比例(0.7/0.3)的影响
2. ICIR阈值(0.8/1.5)的影响
3. 相关性阈值(0.6)的影响

---

**文档版本**: 1.0  
**更新日期**: 2026-03-01  
**对应代码版本**: MVP版本 (commit: 012710f)  
**下一步**: 迭代3 - 边际贡献评估系统实现