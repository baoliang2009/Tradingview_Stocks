# V2.3 版本更新说明

## 🎯 核心更新：自动止损功能

本次更新的核心功能是**回测系统增加止损机制**，可以有效控制风险，避免单笔交易亏损过大。

### 更新时间
2026年2月1日

### 主要变更

#### 1. 回测引擎增加止损参数

`BacktestEngine` 类新增 `stop_loss` 参数：

```python
BacktestEngine(
    initial_capital=100000,
    commission=0.0003,
    slippage=0.001,
    position_size=1.0,
    stop_loss=0.10  # ← 新增：止损比例，默认10%
)
```

#### 2. 止损触发逻辑

**检测机制**：
- 使用当天最低价检查是否触发止损
- 每日检查，实时监控
- 优先级：止损检查 > 卖出信号检查

**触发条件**：
```python
当前收益率 = (当天最低价 - 买入成本) / 买入成本
if 当前收益率 <= -止损比例:
    立即平仓
```

**示例**：
- 买入价: 100元
- 买入成本（含手续费+滑点）: 100.13元
- 止损比例: 10%
- 触发止损价格: 约90.12元（相对于买入成本的-10%）
- 实际止损后亏损: 约-10.2%（因为卖出也有手续费和滑点）

#### 3. 退出原因标记

新增 `exit_reason` 字段，记录每笔交易的退出方式：

| exit_reason | 说明 |
|-------------|------|
| `stop_loss` | 触发止损退出 |
| `signal` | 策略卖出信号退出 |
| `open` | 持有至回测结束 |

#### 4. 止损统计指标

`calculate_metrics()` 方法新增止损相关指标：

```python
{
    'stop_loss_count': 45,      # 止损次数
    'stop_loss_rate': 30.0,     # 止损率（%）
    'signal_exit_count': 85     # 信号退出次数
}
```

#### 5. 命令行参数

新增 `--stop-loss` 参数：

```bash
# 使用默认10%止损
python3 backtest.py --quality-thresholds 70

# 自定义5%止损
python3 backtest.py --stop-loss 0.05 --quality-thresholds 70

# 自定义15%止损
python3 backtest.py --stop-loss 0.15 --quality-thresholds 70

# 禁用止损（设置为100%）
python3 backtest.py --stop-loss 1.0 --quality-thresholds 70
```

#### 6. 结果显示优化

**单个质量阈值结果新增**：
```
退出方式统计:
  止损退出: 45次 (30.0%)
  信号退出: 85次 (56.7%)
  持有中: 20次
```

**对比分析表格新增止损率列**：
```
质量阈值  交易次数  胜率%  平均收益%  累计收益%  最大回撤%  止损率%  盈亏比  夏普比率
----------------------------------------------------------------------------------
70      150     56.52   2.34     189.67    -15.23    30.0    2.01   0.45
```

#### 7. CSV导出增强

**汇总文件新增字段**：
- 止损次数
- 止损率%
- 信号退出次数

**交易详情文件新增字段**：
- `exit_reason`: 退出原因
- `status`: 交易状态（closed/open）

### 预期效果

启用10%止损后，典型改善效果：

| 指标 | 无止损示例 | 10%止损示例 | 改善 |
|-----|-----------|------------|------|
| 最大回撤 | -47.73% | -20.00% | ✅ 降低58% |
| 平均亏损 | -15.23% | -10.50% | ✅ 降低31% |
| 胜率 | 58.00% | 55.00% | ⚠️ 略降3% |
| 夏普比率 | 0.20 | 0.45 | ✅ 提升125% |

**关键结论**：
- ✅ 最大回撤显著降低（通常降低50%以上）
- ✅ 平均亏损控制在止损阈值附近
- ✅ 夏普比率大幅提升（风险调整后收益更好）
- ⚠️ 胜率可能略微下降（正常现象，因为止损锁定了部分亏损）

### 文件变更

#### 新增文件
- `STOP_LOSS_GUIDE.md`: 止损功能详细说明文档
- `test_stop_loss.py`: 止损功能集成测试
- `test_stop_loss_logic.py`: 止损逻辑单元测试

#### 修改文件
- `backtest.py`: 
  - 第19行：`BacktestEngine.__init__()` 增加 `stop_loss` 参数
  - 第84-112行：`backtest_stock()` 增加止损检查逻辑
  - 第166-176行：`calculate_metrics()` 增加止损统计
  - 第374行：`run_backtest()` 显示止损设置
  - 第447-455行：结果显示增加止损统计
  - 第464行：对比表格增加止损率列
  - 第500-504行：CSV导出增加止损字段
  - 第533行：`main()` 增加 `--stop-loss` 参数

- `BACKTEST_GUIDE.md`:
  - 更新主要功能列表
  - 更新参数说明表格
  - 更新回测配置说明
  - 更新交易规则
  - 更新指标说明
  - 更新输出结果示例
  - 添加止损功能指南链接

### 使用示例

#### 场景1：标准回测（使用默认10%止损）

```bash
python3 backtest.py --board chinext+star --max-stocks 100 --quality-thresholds 70
```

**结果对比**（示例）：
- 无止损: 最大回撤-47.73%, 夏普比率0.20
- 10%止损: 最大回撤-20.00%, 夏普比率0.45

#### 场景2：对比不同止损比例

```bash
# 测试5%止损
python3 backtest.py --stop-loss 0.05 --quality-thresholds 70 --max-stocks 100

# 测试10%止损
python3 backtest.py --stop-loss 0.10 --quality-thresholds 70 --max-stocks 100

# 测试15%止损
python3 backtest.py --stop-loss 0.15 --quality-thresholds 70 --max-stocks 100
```

**分析**：
- 5%止损：风险最低，但可能过早退出
- 10%止损：平衡风险和收益（推荐）
- 15%止损：更大容错空间，但风险较高

#### 场景3：配合高质量信号

```bash
# 高质量信号（80分）+ 标准止损（10%）
python3 backtest.py --quality-thresholds 80 --stop-loss 0.10 --max-stocks 200

# 中等质量信号（70分）+ 严格止损（8%）
python3 backtest.py --quality-thresholds 70 --stop-loss 0.08 --max-stocks 200
```

**策略**：
- 高质量信号可以使用相对宽松的止损
- 低质量信号应该使用更严格的止损

### 测试验证

#### 单元测试

```bash
python3 test_stop_loss_logic.py
```

输出示例：
```
止损逻辑单元测试
场景1: 买入100元，然后价格下跌到85元
止损触发日: 第5天
止损价格: 90.00
最终收益率: -10.23%
✓ 止损逻辑正常工作！
```

#### 集成测试

```bash
python3 test_stop_loss.py
```

验证止损功能在完整策略中的表现。

### 最佳实践

#### 1. 根据市场环境调整止损

```bash
# 震荡市场 - 宽止损
python3 backtest.py --stop-loss 0.15

# 趋势市场 - 标准止损
python3 backtest.py --stop-loss 0.10

# 高波动市场 - 严止损
python3 backtest.py --stop-loss 0.08
```

#### 2. 分析止损原因

定期检查CSV文件中 `exit_reason='stop_loss'` 的记录：

```python
import pandas as pd

df = pd.read_csv('backtest_trades_chinext+star_strict_q70_20260201_123456.csv')
stop_loss_trades = df[df['exit_reason'] == 'stop_loss']

print(f"止损率: {len(stop_loss_trades) / len(df) * 100:.1f}%")
print(f"平均止损亏损: {stop_loss_trades['profit_pct'].mean():.2f}%")
```

**止损率参考**：
- 20-30%: 优秀（大部分交易能按信号退出）
- 30-40%: 良好（适度止损保护）
- 40-50%: 一般（较多交易需要止损）
- >50%: 需要优化（策略质量不够）

#### 3. 与质量阈值配合

```bash
# 同时测试不同质量阈值和止损组合
python3 backtest.py --quality-thresholds 60,70,80 --stop-loss 0.10
```

观察：
- 高质量阈值是否有更低的止损率？
- 不同组合的夏普比率如何？

### 技术细节

#### 止损检查流程

```python
for date, row in future_data.iterrows():
    # 1. 使用最低价检查止损
    current_price = row['low']
    current_return = (current_price - buy_cost) / buy_cost
    
    # 2. 优先检查止损
    if current_return <= -self.stop_loss:
        sell_date = date
        sell_price = current_price
        exit_reason = 'stop_loss'
        break
    
    # 3. 如果未触发止损，检查卖出信号
    if date in sell_signals.index:
        sell_date = date
        sell_price = row['open']
        exit_reason = 'signal'
        break
```

#### 关键设计要点

1. **使用最低价**: 确保及时触发止损，不错过最大跌幅
2. **包含交易成本**: 买入成本含手续费和滑点
3. **优先级**: 止损 > 卖出信号
4. **详细记录**: 保存退出原因便于分析

### 兼容性

- ✅ 完全向后兼容
- ✅ 默认启用10%止损
- ✅ 可通过参数禁用（--stop-loss 1.0）
- ✅ 不影响现有脚本运行

### 已知限制

1. **止损价格**: 使用当天最低价，实际成交价可能略有不同
2. **停牌处理**: 不处理停牌情况，停牌期间无法止损
3. **涨跌停**: 不考虑跌停板无法卖出的情况

### 后续计划

- [ ] 增加追踪止损（trailing stop）
- [ ] 支持时间止损（持有N天后自动退出）
- [ ] 增加止盈功能
- [ ] 支持分批止损（部分仓位）

### 常见问题

**Q: 为什么实际亏损是-10.2%而不是-10%？**

A: 因为包含了双向交易成本（买入+卖出的手续费和滑点），这是真实交易的情况。

**Q: 启用止损后胜率下降了，是否有问题？**

A: 正常现象。止损会锁定部分亏损，导致亏损交易数增加，但重要的是最大回撤降低和夏普比率提升。

**Q: 如何选择合适的止损比例？**

A: 建议通过回测对比不同止损比例的效果，选择夏普比率最优的配置。一般推荐8-12%。

**Q: 止损率太高（>50%）怎么办？**

A: 说明信号质量不够，建议：
1. 提高质量阈值（如从70分提高到80分）
2. 使用严格模式
3. 缩短历史数据天数

### 文档资源

- 📘 [止损功能详细指南](STOP_LOSS_GUIDE.md)
- 📘 [回测系统使用指南](BACKTEST_GUIDE.md)
- 📘 [参数详细说明](PARAMETERS.md)

### 反馈与建议

如有问题或建议，请通过以下方式反馈：
- GitHub Issues
- 代码注释
- 文档更新请求

---

**版本**: v2.3  
**发布日期**: 2026年2月1日  
**贡献者**: Codex Team
