# 回测输出文件说明

## 文件命名规则

回测完成后会在当前目录生成以下文件：

- `equity_q{质量阈值}_{时间戳}.csv` - 权益曲线数据
- `trades_q{质量阈值}_{时间戳}.csv` - 交易记录明细

示例：
- `equity_q0_20260203_090757.csv`
- `trades_q0_20260203_090757.csv`

---

## 1. 权益曲线文件 (equity_*.csv)

记录每日账户权益变化。

### 字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| date | 日期 | 2025-08-15 |
| equity | 总权益 | 100000.00 |
| cash | 现金余额 | 50000.00 |
| market_value | 持仓市值 | 50000.00 |
| position_count | 持仓数量 | 3 |

---

## 2. 交易记录文件 (trades_*.csv)

记录每笔买入和卖出交易的详细信息。

### 买入交易字段

| 字段 | 说明 | 示例 |
|------|------|------|
| date | 交易日期 | 2025-08-15 |
| code | 股票代码 | sz.000006 |
| name | 股票名称 | 深振业A |
| action | 操作类型 | BUY |
| price | 买入价格 | 7.33 |
| shares | 买入股数 | 2700 |
| cost | 交易成本 | 19791.00 |
| fee | 手续费 | 5.94 |
| amount | 总支出（负数） | -19796.94 |
| quality | 信号质量分 | 69.2 |
| cash_after | 交易后现金 | 80203.06 |
| reason | 买入原因 | Q:69.2 |

### 卖出交易字段

| 字段 | 说明 | 示例 |
|------|------|------|
| date | 卖出日期 | 2025-09-03 |
| code | 股票代码 | sz.000014 |
| name | 股票名称 | 沙河股份 |
| action | 操作类型 | SELL |
| price | 卖出价格 | 13.66 |
| shares | 卖出股数 | 1300 |
| income | 卖出收入 | 17760.60 |
| fee | 手续费+滑点 | 23.09 |
| amount | 净收入 | 17737.51 |
| buy_price | 买入成本价 | 15.18 |
| buy_date | 买入日期 | 2025-08-15 |
| hold_days | 持有天数 | 19 |
| profit | 收益金额 | -1996.49 |
| profit_pct | 收益率 | -10.12% |
| quality | 买入时质量分 | 0 |
| cash_after | 交易后现金 | 18097.57 |
| reason | 卖出原因 | 止损 / 止盈50% / 卖出信号 / 保本离场 |
| cumulative_profit | 累计收益 | -2951.10 |

---

## 使用示例

### Python 分析

```python
import pandas as pd

# 读取交易记录
trades = pd.read_csv('trades_q0_20260203_090757.csv')

# 筛选卖出交易
sell_trades = trades[trades['action'] == 'SELL']

# 计算胜率
win_rate = (sell_trades['profit'] > 0).sum() / len(sell_trades) * 100
print(f"胜率: {win_rate:.1f}%")

# 平均收益率
avg_return = sell_trades['profit_pct'].mean()
print(f"平均收益率: {avg_return:.2f}%")

# 最大单笔盈利
max_profit = sell_trades['profit'].max()
print(f"最大单笔盈利: {max_profit:.2f}")

# 最大单笔亏损
max_loss = sell_trades['profit'].min()
print(f"最大单笔亏损: {max_loss:.2f}")

# 平均持有天数
avg_hold = sell_trades['hold_days'].mean()
print(f"平均持有天数: {avg_hold:.1f}天")
```

### Excel 分析

1. 直接用Excel打开CSV文件
2. 使用数据透视表分析：
   - 按股票代码统计盈亏
   - 按月份统计交易频率
   - 按卖出原因统计（止损/止盈/信号）
3. 绘制收益曲线图（cumulative_profit列）

---

## 交易原因说明

| 原因 | 说明 | 策略逻辑 |
|------|------|----------|
| Q:XX.X | 买入信号（质量分） | 满足QQE策略条件 |
| 止损 | 触发止损 | 跌破成本价*(1-止损比例) |
| 止盈50% | 部分止盈 | 涨幅达到止盈目标，卖出50% |
| 保本离场 | 保本止损 | 止盈后回落到成本价+1% |
| 卖出信号 | 策略卖出信号 | QQE策略产生卖出信号 |

---

## 注意事项

1. **编码问题**: 文件使用UTF-8-BOM编码，Excel可正常打开中文
2. **金额单位**: 所有金额单位为人民币（元）
3. **百分比**: profit_pct等字段为百分比数值（如-10.12表示-10.12%）
4. **日期格式**: YYYY-MM-DD格式
5. **缓存**: equity和trades文件会随着回测增多而累积，可定期清理
