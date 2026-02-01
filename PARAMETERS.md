# 参数详细说明

## 所有可用参数

### batch_monitor.py 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--stock` | string | None | 测试单只股票代码（如 300750） |
| `--board` | string | chinext+star | 板块筛选 |
| `--max-stocks` | int | 20 | 最大监控股票数量 |
| `--random` | flag | False | 是否随机采样股票 |
| `--no-strict` | flag | False | 不使用严格模式 |
| `--min-quality` | int | 60 | 最低信号质量分数(0-100) |
| `--history-days` | int | 120 | 获取历史数据天数 |
| `--check-days` | int | 2 | 检查最近几天的买入信号 |
| `--delay` | float | 0.1 | 请求间隔时间(秒) |

### single_stock_test.py 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `code` | string | 必填 | 股票代码（位置参数） |
| `--no-strict` | flag | False | 使用标准模式 |
| `--details` | flag | False | 显示详细技术指标 |
| `--days` | int | 100 | 获取历史数据天数 |

## 参数详细解释

### 1. --stock (股票代码)

测试单只股票，输入股票代码。

**格式**:
- 简写: `300750`（自动识别市场）
- 完整: `sz.300750`

**示例**:
```bash
# 测试宁德时代
python3 batch_monitor.py --stock 300750

# 测试中芯国际
python3 batch_monitor.py --stock 688981
```

### 2. --board (板块筛选)

选择监控的板块范围。

**可选值**:
- `chinext`: 创业板（300/301开头）
- `star`: 科创板（688开头）
- `chinext+star`: 创业板+科创板（默认）
- `all`: 全部A股市场

**示例**:
```bash
# 只监控创业板
python3 batch_monitor.py --board chinext --random

# 只监控科创板
python3 batch_monitor.py --board star --random

# 监控全部A股（耗时较长）
python3 batch_monitor.py --board all --random --max-stocks 50
```

### 3. --max-stocks (股票数量)

限制监控的最大股票数量。

**范围**: 1-10000
**默认值**: 20

**示例**:
```bash
# 监控10只股票（快速测试）
python3 batch_monitor.py --random --max-stocks 10

# 监控100只股票（深度扫描）
python3 batch_monitor.py --random --max-stocks 100
```

**建议**:
- 快速测试: 10-20只
- 日常扫描: 50-100只
- 深度扫描: 200-500只

### 4. --random (随机采样)

是否随机选择股票（推荐使用）。

**示例**:
```bash
# 随机选择20只股票
python3 batch_monitor.py --random

# 不使用随机，选择前20只
python3 batch_monitor.py --max-stocks 20
```

**建议**: 
- 总是使用 `--random` 可以避免只扫描固定的股票
- 每次运行会得到不同的股票样本

### 5. --no-strict (标准模式)

不使用严格模式，会产生更多信号。

**示例**:
```bash
# 使用严格模式（默认）
python3 batch_monitor.py --random

# 使用标准模式
python3 batch_monitor.py --random --no-strict
```

**对比**:
- **严格模式**: 信号少（减少70-80%），质量高，盈利确定性大
- **标准模式**: 信号多，质量参差，适合活跃交易

### 6. --min-quality (质量阈值)

设置最低信号质量分数，范围0-100。

**范围**: 0-100
**默认值**: 60

**示例**:
```bash
# 只要高质量信号（70分以上）
python3 batch_monitor.py --random --min-quality 70

# 降低要求（50分以上）
python3 batch_monitor.py --random --min-quality 50

# 非常严格（80分以上）
python3 batch_monitor.py --random --min-quality 80
```

**建议**:
- 保守型: 75-80分
- 平衡型: 60-70分（默认）
- 积极型: 50-60分

### 7. --history-days (历史数据天数) 🆕

获取多少天的历史K线数据。

**范围**: 60-500天
**默认值**: 120天

**示例**:
```bash
# 获取更多历史数据（适合长期分析）
python3 batch_monitor.py --stock 300750 --history-days 200

# 快速测试（减少数据量）
python3 batch_monitor.py --random --history-days 80

# 批量监控使用更多数据
python3 batch_monitor.py --random --history-days 150
```

**影响**:
- **数据越多**: 策略计算更准确，但获取速度变慢
- **数据越少**: 速度快，但可能不够准确

**建议**:
- 单股详细分析: 150-200天
- 批量快速扫描: 100-120天（默认）
- 最少需要: 60天（策略计算最低要求）

**注意**: 
- 新股可能没有足够的历史数据
- 停牌时间过长的股票数据可能不连续

### 8. --check-days (检查天数) 🆕

检查最近几天内的买入信号。

**范围**: 1-10天
**默认值**: 2天

**示例**:
```bash
# 只看今天的信号
python3 batch_monitor.py --random --check-days 1

# 检查最近5天
python3 batch_monitor.py --random --check-days 5

# 单股测试，检查最近3天
python3 batch_monitor.py --stock 300750 --check-days 3
```

**使用场景**:
- `check-days=1`: 只看今天新出现的信号
- `check-days=2`: 今天和昨天的信号（默认，推荐）
- `check-days=3-5`: 本周的信号
- `check-days=5-10`: 错过了几天，想补扫

**建议**:
- 日常监控: 2天（默认）
- 每周监控: 5-7天
- 补扫模式: 根据间隔天数设置

### 9. --delay (请求间隔)

每次请求之间的延迟时间，避免请求过于频繁。

**范围**: 0.05-5.0秒
**默认值**: 0.1秒

**示例**:
```bash
# 更快的扫描（可能被限流）
python3 batch_monitor.py --random --delay 0.05

# 更保守的间隔
python3 batch_monitor.py --random --delay 0.5

# 大量扫描时使用
python3 batch_monitor.py --random --max-stocks 500 --delay 0.2
```

**建议**:
- 小批量(<50只): 0.1秒（默认）
- 中批量(50-200只): 0.2秒
- 大批量(>200只): 0.3-0.5秒

## 参数组合示例

### 场景1: 快速日常扫描
```bash
python3 batch_monitor.py --random --max-stocks 50 --check-days 2
```

### 场景2: 高质量深度扫描
```bash
python3 batch_monitor.py --random --max-stocks 100 --min-quality 70 --history-days 150
```

### 场景3: 周末回测
```bash
python3 batch_monitor.py --random --max-stocks 200 --check-days 5 --history-days 200
```

### 场景4: 保守选股
```bash
python3 batch_monitor.py --random --max-stocks 100 --min-quality 75 --history-days 150
```

### 场景5: 积极选股
```bash
python3 batch_monitor.py --random --max-stocks 100 --min-quality 50 --no-strict --check-days 3
```

### 场景6: 单股深度分析
```bash
python3 batch_monitor.py --stock 300750 --history-days 200 --check-days 5 --min-quality 50
```

### 场景7: 全市场扫描
```bash
python3 batch_monitor.py --board all --random --max-stocks 500 --delay 0.3 --history-days 120
```

### 场景8: 创业板专项
```bash
python3 batch_monitor.py --board chinext --random --max-stocks 80 --min-quality 65
```

## 参数调优指南

### 如果信号太少

**方法1**: 降低质量阈值
```bash
python3 batch_monitor.py --random --min-quality 50
```

**方法2**: 增加检查天数
```bash
python3 batch_monitor.py --random --check-days 5
```

**方法3**: 使用标准模式
```bash
python3 batch_monitor.py --random --no-strict
```

**方法4**: 增加股票数量
```bash
python3 batch_monitor.py --random --max-stocks 100
```

**方法5**: 组合使用
```bash
python3 batch_monitor.py --random --max-stocks 200 --min-quality 50 --check-days 5 --no-strict
```

### 如果信号太多

**方法1**: 提高质量阈值
```bash
python3 batch_monitor.py --random --min-quality 75
```

**方法2**: 减少检查天数
```bash
python3 batch_monitor.py --random --check-days 1
```

**方法3**: 确保使用严格模式
```bash
python3 batch_monitor.py --random
```

### 如果扫描速度太慢

**方法1**: 减少历史数据天数
```bash
python3 batch_monitor.py --random --history-days 80
```

**方法2**: 减少股票数量
```bash
python3 batch_monitor.py --random --max-stocks 20
```

**方法3**: 减少请求间隔（谨慎使用）
```bash
python3 batch_monitor.py --random --delay 0.05
```

### 如果数据不足

**方法1**: 增加历史数据天数
```bash
python3 batch_monitor.py --stock 300750 --history-days 200
```

**方法2**: 使用 single_stock_test.py
```bash
python3 single_stock_test.py 300750 --days 200
```

## 不同投资风格的推荐配置

### 保守型投资者
```bash
python3 batch_monitor.py --random \
  --max-stocks 100 \
  --min-quality 75 \
  --history-days 150 \
  --check-days 2
```

### 平衡型投资者
```bash
python3 batch_monitor.py --random \
  --max-stocks 80 \
  --min-quality 65 \
  --history-days 120 \
  --check-days 2
```

### 积极型投资者
```bash
python3 batch_monitor.py --random \
  --max-stocks 100 \
  --min-quality 55 \
  --history-days 100 \
  --check-days 3 \
  --no-strict
```

### 专业投资者
```bash
python3 batch_monitor.py --board all --random \
  --max-stocks 300 \
  --min-quality 70 \
  --history-days 200 \
  --check-days 1 \
  --delay 0.2
```

## 时间周期建议

### 每日盘后（15:30-16:00）
```bash
python3 batch_monitor.py --random \
  --max-stocks 100 \
  --min-quality 65 \
  --check-days 1
```

### 每周监控（周末）
```bash
python3 batch_monitor.py --random \
  --max-stocks 200 \
  --min-quality 65 \
  --check-days 5 \
  --history-days 150
```

### 补扫模式（错过几天）
```bash
python3 batch_monitor.py --random \
  --max-stocks 150 \
  --check-days 7
```
