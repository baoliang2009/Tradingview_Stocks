# v2.1 更新说明

## 🎉 新功能

### 1. 自定义历史数据天数 (`--history-days`)

现在可以自定义获取多少天的历史K线数据，以满足不同分析需求。

**默认值**: 120天（从之前的100天增加）

**用法**:
```bash
# 获取更多历史数据（适合长期分析）
python3 batch_monitor.py --random --history-days 200

# 快速测试（减少数据量）
python3 batch_monitor.py --random --history-days 80

# 单股详细分析
python3 batch_monitor.py --stock 300750 --history-days 180
```

**使用场景**:
- **80-100天**: 快速测试，速度优先
- **120-150天**: 日常扫描，平衡准确性和速度（推荐）
- **150-200天**: 深度分析，准确性优先
- **200天+**: 长期回测研究

**影响**:
- ✅ 数据越多，策略计算越准确
- ✅ 可以看到更多历史信号
- ⚠️ 数据越多，获取速度越慢

### 2. 自定义检查天数 (`--check-days`)

现在可以自定义检查最近几天内的买入信号，而不是固定的2天。

**默认值**: 2天

**用法**:
```bash
# 只看今天的新信号
python3 batch_monitor.py --random --check-days 1

# 检查最近5天（周末回测）
python3 batch_monitor.py --random --check-days 5

# 补扫模式（错过了一周）
python3 batch_monitor.py --random --check-days 7

# 单股测试最近3天
python3 batch_monitor.py --stock 300750 --check-days 3
```

**使用场景**:
- **1天**: 每日盘后，只看当天新信号
- **2天**: 日常监控（推荐）
- **3-5天**: 周中补扫或周末回测
- **5-10天**: 长时间未监控，补扫模式

**优势**:
- ✅ 灵活调整监控范围
- ✅ 避免错过重要信号
- ✅ 适应不同监控频率

## 📊 参数对比

### 之前的版本
- 历史数据：固定100天
- 检查范围：固定最近2天

### 现在的版本
- 历史数据：可自定义（默认120天）
- 检查范围：可自定义（默认2天）

## 🚀 实用示例

### 示例1：每日快速扫描
```bash
python3 batch_monitor.py --random --max-stocks 100 \
  --check-days 1 --history-days 120
```
- 只看今天的新信号
- 使用标准120天历史数据

### 示例2：周末深度回测
```bash
python3 batch_monitor.py --random --max-stocks 200 \
  --check-days 5 --history-days 200 --min-quality 70
```
- 检查本周5天的信号
- 使用200天历史数据
- 高质量要求

### 示例3：补扫模式
```bash
python3 batch_monitor.py --random --max-stocks 150 \
  --check-days 7 --history-days 150
```
- 补扫最近一周
- 使用充足的历史数据

### 示例4：单股深度分析
```bash
python3 batch_monitor.py --stock 300750 \
  --history-days 200 --check-days 10 --min-quality 50
```
- 200天历史数据
- 检查最近10天
- 降低质量要求

## 📈 性能优化

### 速度优先配置
```bash
python3 batch_monitor.py --random \
  --history-days 80 --max-stocks 30 --delay 0.1
```

### 准确性优先配置
```bash
python3 batch_monitor.py --random \
  --history-days 200 --max-stocks 100 --delay 0.2
```

### 平衡配置（推荐）
```bash
python3 batch_monitor.py --random \
  --history-days 120 --max-stocks 80 --delay 0.15
```

## 🎯 使用建议

### 不同时间周期的建议配置

**每日盘后（15:30-16:00）**
```bash
python3 batch_monitor.py --random \
  --max-stocks 100 \
  --history-days 120 \
  --check-days 1 \
  --min-quality 65
```

**每周监控（周末）**
```bash
python3 batch_monitor.py --random \
  --max-stocks 200 \
  --history-days 150 \
  --check-days 5 \
  --min-quality 65
```

**每月回测**
```bash
python3 batch_monitor.py --random \
  --max-stocks 300 \
  --history-days 200 \
  --check-days 20 \
  --min-quality 70
```

## 📝 完整参数列表

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--stock` | string | None | 测试单只股票 |
| `--board` | string | chinext+star | 板块筛选 |
| `--max-stocks` | int | 20 | 最大股票数量 |
| `--random` | flag | False | 随机采样 |
| `--no-strict` | flag | False | 使用标准模式 |
| `--min-quality` | int | 60 | 最低质量分数 |
| `--history-days` | int | 120 | 历史数据天数 🆕 |
| `--check-days` | int | 2 | 检查天数 🆕 |
| `--delay` | float | 0.1 | 请求间隔 |

## 🔧 迁移指南

### 从 v2.0 升级到 v2.1

**无需修改现有命令**！新参数都有默认值，向后完全兼容。

**旧命令**:
```bash
python3 batch_monitor.py --random
```
继续可用，等同于：
```bash
python3 batch_monitor.py --random --history-days 120 --check-days 2
```

**可选升级**：根据需要添加新参数
```bash
# 增加历史数据
python3 batch_monitor.py --random --history-days 150

# 检查更多天数
python3 batch_monitor.py --random --check-days 5
```

## 📚 文档更新

新增和更新的文档：
- ✅ **PARAMETERS.md** - 新增详细参数说明文档
- ✅ **README.md** - 更新参数表格和示例
- ✅ **EXAMPLES.md** - 新增新参数的使用示例
- ✅ **UPDATE_V2.1.md** - 本更新说明文档

## 🐛 Bug修复

- 修复了数据不足时的错误处理
- 优化了默认历史数据天数（100→120天）
- 改进了参数命名的一致性

## 💡 下一步计划

- [ ] 支持自定义策略参数
- [ ] 添加导出功能（CSV/Excel）
- [ ] 支持盘中实时监控
- [ ] 添加邮件/微信提醒
- [ ] 优化大批量扫描性能

## ❓ 常见问题

**Q: 为什么默认历史天数从100天增加到120天？**

A: 经过测试，120天的数据可以提供更稳定和准确的策略计算结果，同时对性能影响很小。

**Q: check-days 最大可以设置多少？**

A: 建议不超过20天。设置太大可能会包含很多过期的信号。

**Q: history-days 和 check-days 的区别是什么？**

A: 
- `history-days`: 获取多少天的K线数据用于策略计算
- `check-days`: 在计算结果中，检查最近几天的买入信号

例如：`--history-days 120 --check-days 2` 表示用120天数据计算策略，但只关注最近2天的买入信号。

**Q: 新参数会影响性能吗？**

A: 
- `history-days` 增加会稍微降低速度（需要获取更多数据）
- `check-days` 不影响性能，只改变结果筛选范围

## 🎊 致谢

感谢用户反馈和建议，帮助我们不断改进系统！
