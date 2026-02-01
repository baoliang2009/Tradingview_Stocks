# 快速参考卡片

## 常用命令速查

### 批量监控
```bash
# 默认配置
python3 batch_monitor.py --random

# 高质量扫描
python3 batch_monitor.py --random --min-quality 70 --history-days 150

# 快速测试
python3 batch_monitor.py --random --max-stocks 20 --history-days 80

# 周末回测
python3 batch_monitor.py --random --check-days 5 --history-days 200
```

### 单股票测试
```bash
# 快速查看
python3 batch_monitor.py --stock 300750

# 详细分析
python3 single_stock_test.py 300750 --details

# 长期回测
python3 batch_monitor.py --stock 300750 --history-days 200 --check-days 10
```

## 参数速查表

| 参数 | 默认 | 说明 | 示例 |
|------|------|------|------|
| `--stock` | - | 单股票代码 | `--stock 300750` |
| `--board` | chinext+star | 板块筛选 | `--board chinext` |
| `--max-stocks` | 20 | 股票数量 | `--max-stocks 100` |
| `--random` | False | 随机采样 | `--random` |
| `--no-strict` | False | 标准模式 | `--no-strict` |
| `--min-quality` | 60 | 质量阈值 | `--min-quality 70` |
| `--history-days` | 120 | 历史天数 | `--history-days 150` |
| `--check-days` | 2 | 检查天数 | `--check-days 5` |
| `--delay` | 0.1 | 间隔秒数 | `--delay 0.2` |

## 板块代码

- `chinext` - 创业板 (300/301)
- `star` - 科创板 (688)
- `chinext+star` - 创业板+科创板
- `all` - 全部A股

## 质量评级

- 80+ 分：⭐⭐⭐⭐⭐ 优秀
- 70-80分：⭐⭐⭐⭐ 良好
- 60-70分：⭐⭐⭐ 一般
- <60分：⭐⭐ 较差

## 推荐配置

### 保守型
```bash
--min-quality 75 --history-days 150 --check-days 2
```

### 平衡型
```bash
--min-quality 65 --history-days 120 --check-days 2
```

### 积极型
```bash
--min-quality 55 --history-days 100 --check-days 3 --no-strict
```

## 时间周期

### 每日盘后
```bash
--check-days 1 --history-days 120
```

### 每周监控
```bash
--check-days 5 --history-days 150
```

### 补扫模式
```bash
--check-days 7 --history-days 150
```

## 常见股票代码

### 创业板
- 300750 宁德时代
- 300059 东方财富
- 300760 迈瑞医疗

### 科创板
- 688981 中芯国际
- 688041 海光信息
- 688012 中微公司

## 快速故障排除

| 问题 | 解决方案 |
|------|---------|
| 信号太少 | `--min-quality 50 --check-days 5` |
| 信号太多 | `--min-quality 75 --check-days 1` |
| 速度太慢 | `--history-days 80 --max-stocks 20` |
| 数据不足 | `--history-days 200` |

## 文档链接

- 📖 [README.md](README.md) - 完整文档
- 📝 [PARAMETERS.md](PARAMETERS.md) - 参数详解
- 💡 [EXAMPLES.md](EXAMPLES.md) - 使用示例
- 🚀 [UPDATE_V2.1.md](UPDATE_V2.1.md) - 更新说明
