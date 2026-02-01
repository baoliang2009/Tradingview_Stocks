# 监控所有股票使用指南

## 方法总览

有多种方式可以监控所有股票或大批量股票，根据需求选择合适的方法。

## 方法1：使用 "all" 参数（推荐）🆕

最简单直接的方式，监控指定板块的所有股票。

### 基本用法

```bash
# 监控所有创业板+科创板股票（不限制数量）
python3 batch_monitor.py --max-stocks all

# 监控所有创业板股票
python3 batch_monitor.py --board chinext --max-stocks all

# 监控所有科创板股票
python3 batch_monitor.py --board star --max-stocks all

# 监控全部A股（包括沪深主板）
python3 batch_monitor.py --board all --max-stocks all
```

### 注意事项

- ⚠️ 不要使用 `--random` 参数（会导致随机采样）
- ⚠️ 全市场扫描耗时较长，建议设置合理的延迟
- ⚠️ 建议从小范围开始测试

## 方法2：指定大数量（按顺序）

不使用 `--random` 参数，按股票代码顺序扫描。

```bash
# 监控前100只（按代码顺序）
python3 batch_monitor.py --max-stocks 100

# 监控前500只
python3 batch_monitor.py --max-stocks 500

# 监控前1000只
python3 batch_monitor.py --max-stocks 1000

# 只监控创业板前200只
python3 batch_monitor.py --board chinext --max-stocks 200
```

**特点**：
- ✅ 按股票代码顺序扫描
- ✅ 可控制扫描数量
- ✅ 每次扫描相同的股票

## 方法3：分批扫描

将股票池分成多批，分别扫描。

### 为什么要分批？

- 避免单次扫描时间过长
- 可以定期执行，及时发现信号
- 降低系统压力
- 避免网络超时

### 分批策略

```bash
# 第一批：创业板
python3 batch_monitor.py --board chinext --max-stocks all --delay 0.2

# 第二批：科创板
python3 batch_monitor.py --board star --max-stocks all --delay 0.2

# 第三批：沪深主板（如需要）
# 注意：主板股票数量很多，建议分时段或使用更大延迟
python3 batch_monitor.py --board all --max-stocks all --delay 0.5
```

## 完整扫描示例

### 示例1：创业板+科创板全扫描（推荐）

```bash
python3 batch_monitor.py --board chinext+star --max-stocks all \
  --min-quality 65 --delay 0.2
```

**说明**:
- 扫描所有创业板和科创板股票
- 质量阈值65分（过滤低质量信号）
- 延迟0.2秒（避免请求过快）
- 预计时间：创业板约1500只 + 科创板约500只 = 2000只 × 0.2秒 ≈ 7分钟

### 示例2：分板块扫描

```bash
# 先扫创业板
python3 batch_monitor.py --board chinext --max-stocks all \
  --min-quality 65 --delay 0.15 > chinext_results.txt

# 再扫科创板
python3 batch_monitor.py --board star --max-stocks all \
  --min-quality 65 --delay 0.15 > star_results.txt
```

### 示例3：全市场扫描（耗时长）

```bash
python3 batch_monitor.py --board all --max-stocks all \
  --min-quality 70 --delay 0.3
```

**说明**:
- 扫描全部A股（约5000只）
- 质量阈值70分（减少信号数量）
- 延迟0.3秒（避免被限流）
- 预计时间：5000只 × 0.3秒 ≈ 25分钟

## 性能优化建议

### 1. 合理设置延迟

```bash
# 小批量（<100只）：0.1秒
python3 batch_monitor.py --max-stocks 100 --delay 0.1

# 中批量（100-500只）：0.15-0.2秒
python3 batch_monitor.py --max-stocks 500 --delay 0.2

# 大批量（500-2000只）：0.2-0.3秒
python3 batch_monitor.py --max-stocks all --delay 0.25

# 全市场（>2000只）：0.3-0.5秒
python3 batch_monitor.py --board all --max-stocks all --delay 0.4
```

### 2. 提高质量阈值

减少输出信号数量，提高扫描速度：

```bash
# 高质量阈值，减少输出
python3 batch_monitor.py --max-stocks all --min-quality 70
```

### 3. 减少历史数据天数

```bash
# 使用较少的历史数据（更快）
python3 batch_monitor.py --max-stocks all --history-days 90
```

### 4. 只检查今天的信号

```bash
# 只看今天的新信号
python3 batch_monitor.py --max-stocks all --check-days 1
```

## 定时任务设置

### 使用 cron 定时执行

#### 每日盘后扫描（推荐）

```bash
# 编辑 crontab
crontab -e

# 添加任务：每个交易日 15:30 执行
30 15 * * 1-5 cd /path/to/codex-stocks && python3 batch_monitor.py --board chinext+star --max-stocks all --min-quality 70 --delay 0.2 > /path/to/logs/daily_scan_$(date +\%Y\%m\%d).log 2>&1
```

#### 分批扫描

```bash
# 15:30 扫描创业板
30 15 * * 1-5 cd /path/to/codex-stocks && python3 batch_monitor.py --board chinext --max-stocks all --delay 0.2 > /path/to/logs/chinext_$(date +\%Y\%m\%d).log 2>&1

# 16:00 扫描科创板
00 16 * * 1-5 cd /path/to/codex-stocks && python3 batch_monitor.py --board star --max-stocks all --delay 0.2 > /path/to/logs/star_$(date +\%Y\%m\%d).log 2>&1
```

## 实战建议

### 新手建议

```bash
# 从小范围开始
python3 batch_monitor.py --max-stocks 50 --delay 0.1

# 逐步增加
python3 batch_monitor.py --max-stocks 100 --delay 0.15

# 最后全扫描
python3 batch_monitor.py --max-stocks all --delay 0.2
```

### 日常监控建议

```bash
# 每日盘后：创业板+科创板全扫描
python3 batch_monitor.py --board chinext+star --max-stocks all \
  --min-quality 70 --check-days 1 --delay 0.2
```

### 周末回测建议

```bash
# 周末：查看本周所有信号
python3 batch_monitor.py --board chinext+star --max-stocks all \
  --min-quality 65 --check-days 5 --delay 0.2
```

## 常见问题

### Q1: 扫描所有股票要多久？

A: 取决于股票数量和延迟设置：
- 创业板（~1500只）× 0.2秒 ≈ 5分钟
- 科创板（~500只）× 0.2秒 ≈ 2分钟
- 创业板+科创板 ≈ 7分钟
- 全A股（~5000只）× 0.3秒 ≈ 25分钟

### Q2: 会不会被限流？

A: 建议：
- 设置合理延迟（0.2秒以上）
- 避免并发运行多个脚本
- 大批量扫描使用 0.3-0.5秒延迟

### Q3: 如何保存扫描结果？

A: 使用输出重定向：
```bash
python3 batch_monitor.py --max-stocks all > results.txt 2>&1
```

### Q4: 如何只看股票代码列表？

A: 使用 grep 过滤：
```bash
python3 batch_monitor.py --max-stocks all 2>&1 | grep "发现买入信号"
```

### Q5: --random 和不使用 --random 的区别？

A: 
- **不使用 --random**：按股票代码顺序扫描，每次结果一致
- **使用 --random**：随机采样，每次扫描不同的股票

### Q6: 监控所有股票应该用哪种模式？

A: 建议：
- **严格模式**（默认）：信号少但质量高
- **质量阈值70+**：进一步减少信号
- **检查今日信号**：--check-days 1

## 推荐配置

### 配置1：日常快速扫描

```bash
python3 batch_monitor.py --board chinext+star --max-stocks all \
  --min-quality 70 --check-days 1 --history-days 100 --delay 0.2
```

**特点**：快速、高质量、只看今日新信号

### 配置2：周末深度扫描

```bash
python3 batch_monitor.py --board chinext+star --max-stocks all \
  --min-quality 65 --check-days 5 --history-days 150 --delay 0.25
```

**特点**：深度分析、查看本周信号、更多历史数据

### 配置3：全市场扫描

```bash
python3 batch_monitor.py --board all --max-stocks all \
  --min-quality 75 --check-days 1 --history-days 120 --delay 0.4
```

**特点**：覆盖全市场、高质量要求、避免限流

## 总结

监控所有股票的最佳实践：

1. ✅ **使用 `--max-stocks all`**：不限制数量
2. ✅ **不使用 `--random`**：按顺序扫描
3. ✅ **设置合理延迟**：0.2-0.3秒
4. ✅ **提高质量阈值**：70分以上
5. ✅ **分批执行**：创业板、科创板分开
6. ✅ **定时任务**：每日盘后自动执行
7. ✅ **保存结果**：输出重定向到文件

开始使用：
```bash
# 推荐命令
python3 batch_monitor.py --board chinext+star --max-stocks all \
  --min-quality 70 --delay 0.2
```
