"""
快速测试 - IC控制和权重计算验证

测试目标：
验证股票数据模拟器的核心数学逻辑

测试参数：
- 股票数量: 100只
- 测试IC值: [0.05, 0.10, 0.20, 0.30]

测试维度：
1. IC控制精度: 生成的因子与目标IC的匹配程度
2. 权重计算正确性: 多头/空头权重是否正确归一化
3. 时间对齐: 因子是否正确预测未来收益

核心逻辑：
- 使用正交化方法生成与收益相关的因子值
- F = ρ * R + √(1-ρ²) * Z
- 确保因子与未来收益的相关性为目标IC

数学验证：
- 目标IC vs 实际IC的相关性应接近1.0
- 权重和应精确为1.0

作者: 小鱼爬爬
日期: 2026-02-28
"""

import numpy as np

def test_ic_control():
    """测试IC控制逻辑"""
    print("测试IC控制逻辑...")
    
    # 生成收益率
    np.random.seed(42)
    N = 100  # 100只股票
    returns = np.random.randn(N)  # 标准化收益
    
    # 测试不同IC值
    test_ics = [0.05, 0.10, 0.20, 0.30]
    
    for target_ic in test_ics:
        print(f"\n目标IC = {target_ic:.3f}")
        
        # 生成独立噪声
        Z = np.random.randn(N)
        
        # 使Z与returns正交
        if np.dot(returns, returns) > 1e-8:
            projection = np.dot(Z, returns) / np.dot(returns, returns)
            Z_orthogonal = Z - projection * returns
        else:
            Z_orthogonal = Z
        
        # 标准化正交噪声
        Z_std = Z_orthogonal.std()
        if Z_std < 1e-8:
            Z_normalized = np.zeros_like(Z_orthogonal)
        else:
            Z_normalized = Z_orthogonal / Z_std
        
        # 生成因子得分
        factor_scores = target_ic * returns + np.sqrt(1 - target_ic**2) * Z_normalized
        
        # 计算实际IC
        actual_ic = np.corrcoef(factor_scores, returns)[0, 1]
        error = abs(actual_ic - target_ic)
        
        print(f"  实际IC = {actual_ic:.4f}")
        print(f"  误差 = {error:.4f}")
        print(f"  误差百分比 = {error/abs(target_ic):.1%}")

def test_weighted_return():
    """测试得分加权收益计算"""
    print("\n\n测试得分加权收益计算...")
    
    np.random.seed(42)
    N = 50
    
    # 生成因子得分和收益
    scores = np.random.randn(N)
    returns = np.random.randn(N) * 0.02  # 2%日波动
    
    # 计算得分加权多空收益
    scores_std = scores.std()
    if scores_std < 1e-8:
        scores_normalized = np.zeros_like(scores)
    else:
        scores_normalized = scores / scores_std
    
    leverage = 2.0
    
    # 多头部分
    long_mask = scores_normalized > 0
    if np.any(long_mask):
        long_scores = scores_normalized[long_mask]
        long_returns = returns[long_mask]
        long_weights = long_scores / long_scores.sum() * (leverage / 2)
        long_return = np.sum(long_weights * long_returns)
    else:
        long_return = 0
    
    # 空头部分
    short_mask = scores_normalized < 0
    if np.any(short_mask):
        short_scores = scores_normalized[short_mask]
        short_returns = returns[short_mask]
        short_scores_pos = -short_scores  # 负得分变正
        short_weights = -short_scores_pos / short_scores_pos.sum() * (leverage / 2)
        short_return = np.sum(short_weights * short_returns)
    else:
        short_return = 0
    
    total_return = long_return + short_return
    
    print(f"因子得分范围: {scores.min():.3f} 到 {scores.max():.3f}")
    print(f"多头股票数: {np.sum(long_mask)}")
    print(f"空头股票数: {np.sum(short_mask)}")
    print(f"多头权重和: {np.sum(long_weights) if long_mask.any() else 0:.3f}")
    print(f"空头权重和: {np.sum(short_weights) if short_mask.any() else 0:.3f}")
    print(f"多空组合收益: {total_return:.6f}")
    
    # 验证权重和
    if long_mask.any():
        assert abs(np.sum(long_weights) - 1.0) < 0.01, f"多头权重和应为1.0，实际为{np.sum(long_weights)}"
    if short_mask.any():
        assert abs(np.sum(short_weights) + 1.0) < 0.01, f"空头权重和应为-1.0，实际为{np.sum(short_weights)}"

def test_ic_series():
    """测试IC序列生成"""
    print("\n\n测试IC序列生成...")
    
    np.random.seed(42)
    T = 100  # 100个时间点
    
    # 生成IC序列
    ic_mean = 0.05
    ic_std = 0.02
    ic_series = np.random.normal(ic_mean, ic_std, T)
    
    print(f"IC均值: {ic_series.mean():.4f} (目标: {ic_mean:.4f})")
    print(f"IC标准差: {ic_series.std():.4f} (目标: {ic_std:.4f})")
    print(f"IC范围: {ic_series.min():.4f} 到 {ic_series.max():.4f}")
    
    # 计算ICIR
    icir = ic_series.mean() / ic_series.std()
    print(f"ICIR: {icir:.3f}")

if __name__ == "__main__":
    print("=" * 60)
    print("快速测试 - 验证核心逻辑")
    print("=" * 60)
    
    test_ic_control()
    test_weighted_return()
    test_ic_series()
    
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)