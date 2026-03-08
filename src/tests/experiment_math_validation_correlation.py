"""
最小化测试 - 相关性生成核心逻辑验证

测试目标：
验证使用正交化方法生成具有指定相关性的序列

测试参数：
- 样本数量: 1000个（大量样本提高统计精度）
- 测试相关性: [0.02, 0.04, 0.06, 0.08, 0.10]

测试维度：
1. 相关性精度: 目标相关性 vs 实际相关性
2. 误差分析: 绝对误差和相对误差
3. 稳定性: 不同随机种子下的表现
4. 线性范围: 不同相关性水平下的表现

核心算法：
1. 生成基准序列Y（模拟未来收益）
2. 生成随机噪声Z
3. 使Z与Y正交（Gram-Schmidt简化）
4. 组合: X = ρ * Y + √(1-ρ²) * Z
5. 验证: corr(X, Y) ≈ ρ

数学原理：
- corr(ρY + √(1-ρ²)Z, Y) = ρ * corr(Y,Y) + √(1-ρ²) * corr(Z,Y)
- 由于Z与Y正交，corr(Z,Y) = 0
- 因此 corr(X,Y) = ρ

预期结果：
- 所有测试的相关性误差 < 1%
- 误差不随目标相关性增加而显著增加

作者: 小鱼爬爬
日期: 2026-02-28
"""

import numpy as np

def test_correlation_generation():
    """测试生成具有指定相关性的序列"""
    print("测试相关性生成...")
    
    np.random.seed(42)
    N = 1000  # 大量样本提高统计精度
    
    # 生成基准序列（模拟未来收益）
    Y = np.random.randn(N)
    
    # 测试不同的目标相关性
    test_rhos = [0.02, 0.04, 0.06, 0.08, 0.10]
    
    print(f"{'目标ρ':<8} {'实际ρ':<8} {'误差':<8} {'误差%':<8}")
    print("-" * 40)
    
    for rho_target in test_rhos:
        # 生成独立噪声
        Z = np.random.randn(N)
        
        # 使Z与Y正交
        # 计算Z在Y上的投影
        if np.dot(Y, Y) > 1e-8:
            proj = np.dot(Z, Y) / np.dot(Y, Y)
            Z_ortho = Z - proj * Y
        else:
            Z_ortho = Z
        
        # 标准化正交噪声
        Z_std = Z_ortho.std()
        if Z_std < 1e-8:
            Z_norm = np.zeros_like(Z_ortho)
        else:
            Z_norm = Z_ortho / Z_std
        
        # 生成X，使得 corr(X, Y) = rho_target
        X = rho_target * Y + np.sqrt(1 - rho_target**2) * Z_norm
        
        # 计算实际相关性
        rho_actual = np.corrcoef(X, Y)[0, 1]
        error = abs(rho_actual - rho_target)
        error_pct = error / abs(rho_target)
        
        print(f"{rho_target:<8.3f} {rho_actual:<8.3f} {error:<8.3f} {error_pct:<8.1%}")

def test_ic_sequence():
    """测试IC序列生成"""
    print("\n\n测试IC序列生成...")
    
    np.random.seed(42)
    T = 1000  # 1000个时间点
    
    # 生成IC序列：IC_t ~ N(μ, σ²)
    mu = 0.05  # IC均值
    sigma = 0.01  # IC标准差固定
    
    ic_series = np.random.normal(mu, sigma, T)
    
    print(f"IC统计:")
    print(f"  理论均值: {mu:.4f}, 实际均值: {ic_series.mean():.4f}")
    print(f"  理论标准差: {sigma:.4f}, 实际标准差: {ic_series.std():.4f}")
    print(f"  IC范围: {ic_series.min():.4f} 到 {ic_series.max():.4f}")
    
    # 计算ICIR
    icir = ic_series.mean() / ic_series.std()
    print(f"  ICIR: {icir:.3f}")
    print(f"  理论ICIR (μ/σ): {mu/sigma:.3f}")

def test_weighted_portfolio():
    """测试得分加权组合"""
    print("\n\n测试得分加权组合...")
    
    np.random.seed(42)
    N = 100
    
    # 生成因子得分
    scores = np.random.randn(N)
    
    # 生成收益（与得分有一定相关性）
    returns = 0.1 * scores + np.random.randn(N) * 0.9
    
    # 计算得分加权权重
    # 多头：得分>0的部分
    long_mask = scores > 0
    if np.any(long_mask):
        long_scores = scores[long_mask]
        long_returns = returns[long_mask]
        
        # 权重正比于得分，和为1
        long_weights = long_scores / long_scores.sum()
        long_return = np.sum(long_weights * long_returns)
        
        print(f"多头部分:")
        print(f"  股票数: {np.sum(long_mask)}")
        print(f"  权重和: {np.sum(long_weights):.3f} (应为1.0)")
        print(f"  加权收益: {long_return:.6f}")
    
    # 空头：得分<0的部分
    short_mask = scores < 0
    if np.any(short_mask):
        short_scores = scores[short_mask]
        short_returns = returns[short_mask]
        
        # 对于空头，得分越负，做空权重越大
        # 所以用 -short_scores（负得分变正）
        short_scores_pos = -short_scores
        
        # 权重和为 -1
        short_weights = -short_scores_pos / short_scores_pos.sum()
        short_return = np.sum(short_weights * short_returns)
        
        print(f"\n空头部分:")
        print(f"  股票数: {np.sum(short_mask)}")
        print(f"  权重和: {np.sum(short_weights):.3f} (应为-1.0)")
        print(f"  加权收益: {short_return:.6f}")
    
    # 总收益
    total_return = long_return + short_return
    print(f"\n多空组合总收益: {total_return:.6f}")
    
    # 验证杠杆
    # 多头权重和 = 1，空头权重和 = -1，总杠杆 = 2
    total_leverage = abs(np.sum(long_weights)) + abs(np.sum(short_weights))
    print(f"总杠杆: {total_leverage:.1f} (应为2.0)")

def test_full_pipeline():
    """测试完整流程"""
    print("\n\n测试完整流程...")
    
    np.random.seed(42)
    
    # 参数
    N = 100  # 股票数
    T = 100  # 时间点数
    K = 10   # 因子数
    
    # 生成股票收益率
    returns = np.random.randn(T, N) * 0.02
    
    # 生成因子IC参数
    ic_means = np.random.uniform(0.02, 0.06, K)
    ic_std_fixed = 0.01
    
    # 生成IC序列
    ic_sequences = np.zeros((T, K))
    for k in range(K):
        ic_sequences[:, k] = np.random.normal(ic_means[k], ic_std_fixed, T)
    
    # 生成因子得分
    factor_scores = np.zeros((T, K, N))
    
    # 第一天随机
    factor_scores[0, :, :] = np.random.randn(K, N)
    
    # 后续天数
    for t in range(T - 1):
        returns_next = returns[t + 1, :]
        
        for k in range(K):
            current_ic = ic_sequences[t, k]
            
            # 标准化未来收益
            R = returns_next.copy()
            R_mean = R.mean()
            R_std = R.std()
            if R_std < 1e-8:
                R_norm = np.zeros_like(R)
            else:
                R_norm = (R - R_mean) / R_std
            
            # 生成独立噪声并正交化
            Z = np.random.randn(N)
            if np.dot(R_norm, R_norm) > 1e-8:
                proj = np.dot(Z, R_norm) / np.dot(R_norm, R_norm)
                Z_ortho = Z - proj * R_norm
            else:
                Z_ortho = Z
            
            Z_std = Z_ortho.std()
            if Z_std < 1e-8:
                Z_norm = np.zeros_like(Z_ortho)
            else:
                Z_norm = Z_ortho / Z_std
            
            # 生成因子得分
            rho = np.clip(current_ic, -0.99, 0.99)
            factor_scores[t, k, :] = rho * R_norm + np.sqrt(1 - rho**2) * Z_norm
    
    # 评估
    print(f"生成完成:")
    print(f"  股票收益率形状: {returns.shape}")
    print(f"  因子得分形状: {factor_scores.shape}")
    print(f"  IC序列形状: {ic_sequences.shape}")
    
    # 检查一个因子的IC控制
    k_test = 0
    actual_ics = []
    for t in range(T - 1):
        scores = factor_scores[t, k_test, :]
        future_returns = returns[t + 1, :]
        ic = np.corrcoef(scores, future_returns)[0, 1]
        if not np.isnan(ic):
            actual_ics.append(ic)
    
    if actual_ics:
        actual_mean = np.mean(actual_ics)
        target_mean = ic_means[k_test]
        error = abs(actual_mean - target_mean)
        
        print(f"\n因子0的IC控制:")
        print(f"  目标IC均值: {target_mean:.4f}")
        print(f"  实际IC均值: {actual_mean:.4f}")
        print(f"  误差: {error:.4f}")
        print(f"  误差百分比: {error/abs(target_mean):.1%}")

if __name__ == "__main__":
    print("=" * 60)
    print("最小化测试 - 验证核心逻辑")
    print("=" * 60)
    
    test_correlation_generation()
    test_ic_sequence()
    test_weighted_portfolio()
    test_full_pipeline()
    
    print("\n" + "=" * 60)
    print("所有测试完成!")
    print("=" * 60)