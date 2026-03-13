# AI_AI_CONTEXT.md

## 项目目的

本项目实现一个 **Bayesian 因子库维护系统**。

系统从一个已有的因子池中，定期选择最优的 K 个因子。

选择因子时考虑：

- 因子收益质量
- 因子稳定性
- 因子相关性
- 因子对组合的边际贡献

算法思想参考 AlphaPROBE，但目标是 **因子库维护** 而不是信号生成。

---

## 当前开发阶段

当前分支：

iteration3

当前重点：

- 多指标评价
- 多窗口评价
- 边际贡献评估
- 相关性约束
- 组合模拟

---

## 关键代码模块

优先阅读以下文件理解系统：
src/core/bayesian_selector_v2.py

主控制器：

- 管理因子池
- 执行 Bayesian 选择逻辑
- 调用评估模块

src/evaluation/marginal_contrib.py

边际贡献评估：

- 评估未选因子
- 分类 SUCCESS / FAILURE / NEUTRAL / UNCERTAIN

src/evaluation/portfolio_simulator.py

组合模拟：

- 构建组合
- 评估替换因子的收益变化

src/core/correlation_calculator.py

相关性计算：

- 因子相关性
- 替换筛选
- 多样性约束

---

## 测试入口

主要调试入口：
src/tests/test_performance.py

该脚本使用 **模拟数据** 测试因子选择逻辑。

典型执行路径：
test_performance.py
→ bayesian_selector_v2
→ marginal_contrib
→ portfolio_simulator
→ correlation_calculator

---

## 配置文件

主要配置：
config/evaluation_config.yaml

重要参数包括：

- metric weights
- evaluation windows
- improvement thresholds
- replacement strategy

调试时优先检查配置。

---

## 文档说明

详细设计文档在：
docs/

主要文件：  
CODE_ARCHITECTURE.md  
EVALUATION_STANDARDS.md  
PARAMETER_MAPPING.md  
ITERATION3_SUMMARY.md  
FACTOR_LIBRARY_EVAL_PROTOCOL.md  
PAPER_COMPARISON.md
example.md

只有在需要理解设计时再阅读。

---

## 文档同步规则（强制）

若未来发生以下任一变化，必须同步更新文档：

- 程序架构调整（模块职责、调用链、数据流）
- 参数调整（阈值、权重、窗口、更新规则）
- 跟踪输出调整（输出文件、字段、口径）

必须同步更新这些文件：

- docs/CODE_ARCHITECTURE.md
- docs/ITERATION3_SUMMARY.md
- docs/EVALUATION_STANDARDS.md
- docs/PARAMETER_MAPPING.md

此外，若出现以下任一变化，必须同步更新：

- `src/tests/` 新增实验入口 `.py` 文件
- 现有 `src/tests/` 入口脚本的参数、调用方式、默认行为发生变化

必须同步更新文件：

- docs/example.md

---

## 已知历史修改

历史调试和修改记录在：
AI_LOG.md

如果出现异常行为，先查看是否已经记录过。

---

## 调试原则

当分析问题时：

1. 从测试入口开始追踪代码
2. 检查数据生成逻辑
3. 检查配置参数
4. 检查评估阈值
5. 再考虑代码 bug

不要在未确认原因前重构代码。

---

## 给 AI agent 的规则

1. 优先阅读 **AI_CONTEXT.md**
2. 再查看 **AI_LOG.md**
3. 从给定的 `src/tests` 中指定实验文件，或问题中指名的函数开始追踪执行路径
4. 只阅读相关模块，不扫描整个仓库
5. 在修改代码前先解释 root cause
6. 优先提出最小修改方案

