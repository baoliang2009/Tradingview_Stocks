# QQE策略回测使用指南

## 快速开始

### 最简单的命令（使用所有默认值）
```bash
python3 backtest.py
```
- 板块: 创业板+科创板 (chinext+star)
- 股票池: 100只
- 持仓: 最多5只
- 资金: 10万
- 模式: 严格模式（启用质量评分）
- 阈值: 50, 60, 70

---

## 常用场景

### 1. 测试300,00板块（创业板+主板000开头）
```bash
python3 backtest.py --board "300,00" --max-stocks 50 --budget 300000
```

### 2. 非严格模式（接受所有信号）
```bash
python3 backtest.py --no-strict --budget 300000
```
**注意**: 非严格模式下会自动使用阈值0

### 3. 严格模式 + 自定义阈值
```bash
python3 backtest.py --quality-thresholds 60,70,80 --budget 300000
```

### 4. 增加持仓数量
```bash
python3 backtest.py --max-positions 10 --budget 500000
```

### 5. 调整止损止盈
```bash
python3 backtest.py --stop-loss 0.08 --take-profit 0.25 --budget 300000
```
- 止损8%
- 止盈25%

### 6. 使用移动止盈（推荐用于捕获大涨）
```bash
python3 backtest.py --trailing-stop 0.15 --budget 300000
```
- 价格超过20%盈利后启用移动止盈
- 当价格从峰值回落15%时自动卖出
- **优势**: 捕获50%-100%+的大涨行情

---

## ⚠️ 常见错误

### ❌ 错误：非严格模式 + 高阈值
```bash
# 这个命令会导致0交易！
python3 backtest.py --no-strict --quality-thresholds 60 --budget 300000
```

**原因**: 
- `--no-strict`: 所有质量分数 = 0
- `--quality-thresholds 60`: 只接受质量 ≥ 60的信号
- **结果**: 所有信号被过滤（0 < 60）

**解决方案**:
```bash
# 方案1: 使用严格模式（启用质量评分）
python3 backtest.py --quality-thresholds 60 --budget 300000

# 方案2: 非严格模式使用阈值0
python3 backtest.py --no-strict --quality-thresholds 0 --budget 300000

# 方案3: 非严格模式不指定阈值（自动使用0）
python3 backtest.py --no-strict --budget 300000
```

---

## 参数详解

### 板块选择 (--board)
| 参数 | 说明 | 示例 |
|------|------|------|
| `chinext+star` | 创业板+科创板（默认） | `--board chinext+star` |
| `chinext` | 仅创业板 (300/301开头) | `--board chinext` |
| `star` | 仅科创板 (688开头) | `--board star` |
| `all` | 所有A股 | `--board all` |
| `"300,00"` | 自定义前缀（创业板+主板000） | `--board "300,00"` |

### 股票数量
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--max-stocks` | 100 | 股票池大小（从市场选取多少只） |
| `--max-positions` | 5 | 最大持仓（同时持有多少只） |

**示例**:
```bash
# 从200只股票中选择，最多同时持有10只
python3 backtest.py --max-stocks 200 --max-positions 10
```

### 资金管理
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--budget` | 100000 | 初始资金（元） |
| `--stop-loss` | 0.10 | 止损比例 (10%) |
| `--take-profit` | 0.20 | 固定止盈比例 (20%) |
| `--trailing-stop` | 0.0 | 移动止盈回落比例 (0=禁用) |

**移动止盈说明**:
- 当 `--trailing-stop` > 0 时，替代固定止盈机制
- 价格超过 `--take-profit` 阈值后启用移动止盈
- 价格从峰值回落超过 `--trailing-stop` 时触发卖出
- **示例**: `--take-profit 0.20 --trailing-stop 0.15`
  - 盈利超过20%后启用移动止盈
  - 从峰值回落15%时卖出
  - 若股票涨到+100%，会在约+85%处卖出（而非+20%）

### 策略模式
| 参数 | 默认 | 说明 |
|------|------|------|
| `--no-strict` | 关闭 | 非严格模式（质量分=0） |
| 不加参数 | **严格模式** | 启用8因子质量评分 |

### 质量阈值 (--quality-thresholds)
| 模式 | 默认值 | 说明 |
|------|--------|------|
| 严格模式 | `50,60,70` | 测试3个阈值 |
| 非严格模式 | `0` | 自动设为0（接受所有） |

**手动指定**:
```bash
# 测试单个阈值
python3 backtest.py --quality-thresholds 60

# 测试多个阈值（逗号分隔）
python3 backtest.py --quality-thresholds 40,50,60,70
```

---

## 严格模式 vs 非严格模式

### 严格模式（推荐）
```bash
python3 backtest.py --budget 300000
```

**特点**:
- ✅ 启用8因子质量评分系统
- ✅ 可以按质量过滤信号
- ✅ 避免低质量交易
- ✅ 默认测试3个阈值对比

**8个质量因子**:
1. QQE趋势强度
2. 成交量确认
3. RSI位置
4. 动量强度
5. 波动率
6. 趋势持续性
7. 突破确认
8. 价格位置

### 非严格模式
```bash
python3 backtest.py --no-strict --budget 300000
```

**特点**:
- 所有信号质量 = 0
- 不进行质量筛选
- 接受所有QQE基础信号
- 交易更频繁

**何时使用**:
- 想测试策略的基础表现
- 不想过滤任何信号
- 对比严格模式的差异

---

## 输出文件

每次回测会生成2个文件：

### 1. 权益曲线 (equity_*.csv)
记录每日账户资金变化

### 2. 交易记录 (trades_*.csv)
**包含每笔交易的完整信息**:
- 买入/卖出价格、股数
- 收益金额、收益率
- 持有天数
- 买入质量分数
- 卖出原因
- 累计收益

详见 `BACKTEST_OUTPUT.md`

---

## 完整示例

### 保守策略（高质量 + 少量持仓）
```bash
python3 backtest.py \
  --budget 300000 \
  --max-stocks 50 \
  --max-positions 3 \
  --quality-thresholds 70 \
  --stop-loss 0.08 \
  --take-profit 0.25 \
  --board "300,00"
```

### 激进策略（移动止盈捕获大涨）
```bash
python3 backtest.py \
  --budget 500000 \
  --max-stocks 100 \
  --max-positions 10 \
  --no-strict \
  --stop-loss 0.10 \
  --take-profit 0.20 \
  --trailing-stop 0.15 \
  --board "300,00"
```
- 使用移动止盈让利润奔跑
- 适合捕获50%-100%+的大涨行情
- 回撤15%时止盈

### 对比测试（多个阈值）
```bash
python3 backtest.py \
  --budget 300000 \
  --max-stocks 50 \
  --quality-thresholds 0,30,50,70 \
  --board "300,00"
```
会生成4组对比结果

---

## 帮助信息
```bash
python3 backtest.py --help
```

查看所有可用参数和说明。
