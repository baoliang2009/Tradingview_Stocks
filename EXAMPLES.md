# 快速使用示例

## 1. 批量监控

### 示例1：默认配置（推荐新手）
```bash
python3 batch_monitor.py --random
```
- 随机选择20只创业板+科创板股票
- 使用严格模式
- 质量阈值60分
- 历史数据120天
- 检查最近2天

### 示例2：提高质量要求
```bash
python3 batch_monitor.py --random --min-quality 70
```
- 只显示质量≥70分的信号
- 信号更少但质量更高

### 示例3：监控更多股票
```bash
python3 batch_monitor.py --random --max-stocks 50
```
- 随机选择50只股票
- 增加发现好股票的概率

### 示例4：只看创业板
```bash
python3 batch_monitor.py --board chinext --random --max-stocks 30
```
- 只监控创业板（300/301开头）
- 随机30只

### 示例5：只看科创板
```bash
python3 batch_monitor.py --board star --random --max-stocks 30
```
- 只监控科创板（688开头）
- 随机30只

### 示例6：使用标准模式（信号更多）
```bash
python3 batch_monitor.py --random --no-strict
```
- 使用标准模式
- 会产生更多信号，但质量可能较低

### 示例7：自定义历史数据天数 🆕
```bash
python3 batch_monitor.py --random --history-days 150
```
- 获取150天的历史数据
- 策略计算更准确

### 示例8：检查最近5天的信号 🆕
```bash
python3 batch_monitor.py --random --check-days 5
```
- 检查最近5天内的买入信号
- 适合周末回测或补扫

### 示例9：组合使用新参数 🆕
```bash
python3 batch_monitor.py --random --max-stocks 100 \
  --history-days 150 --check-days 5 --min-quality 70
```
- 随机100只股票
- 使用150天历史数据
- 检查最近5天
- 质量阈值70分

## 2. 单股票测试

### 示例1：快速查看（推荐）
```bash
python3 batch_monitor.py --stock 300750
```
- 快速查看宁德时代是否有买入信号
- 适合快速验证

### 示例2：详细分析
```bash
python3 single_stock_test.py 300750 --details
```
- 深度分析宁德时代
- 显示所有历史信号、回测数据、技术指标

### 示例2a：查看所有信号记录（新功能）🆕
```bash
python3 single_stock_test.py 300750 --all-signals
```
- 显示所有买入信号记录（表格形式）
- 显示所有卖出信号记录（表格形式）
- 买入-卖出配对分析
- 每笔交易的收益率和持有天数

### 示例2b：完整分析（推荐）🆕
```bash
python3 single_stock_test.py 300750 --all-signals --details
```
- 所有信号记录 + 详细技术指标
- 最完整的分析报告

### 示例3：降低质量要求
```bash
python3 batch_monitor.py --stock 300750 --min-quality 50
```
- 严格模式下没信号时
- 降低质量阈值试试

### 示例4：查看标准模式
```bash
python3 single_stock_test.py 300750 --no-strict
```
- 使用标准模式分析
- 对比两种模式的差异

### 示例5：长期回测
```bash
python3 single_stock_test.py 300750 --days 200 --details
```
- 获取200天历史数据
- 查看长期表现

### 示例5a：完整的长期分析（新功能）🆕
```bash
python3 single_stock_test.py 300750 --days 200 --all-signals --details
```
- 200天历史数据
- 所有信号记录
- 详细技术指标
- 最全面的回测分析

### 示例6：自定义检查天数 🆕
```bash
python3 batch_monitor.py --stock 300750 --check-days 5
```
- 检查最近5天的信号
- 适合补扫模式

### 示例7：组合参数深度分析 🆕
```bash
python3 batch_monitor.py --stock 300750 \
  --history-days 180 --check-days 7 --min-quality 50
```
- 使用180天历史数据
- 检查最近7天
- 降低质量要求到50分

## 3. 对比测试

```bash
python3 compare_modes.py
```
- 自动对比标准模式和严格模式
- 测试宁德时代、东方财富、中芯国际等股票
- 显示信号数量差异和质量分数

## 4. 常用股票代码

### 创业板热门
- 300750 - 宁德时代
- 300059 - 东方财富  
- 300122 - 智飞生物
- 300760 - 迈瑞医疗
- 300919 - 中伟股份

### 科创板热门
- 688981 - 中芯国际
- 688041 - 海光信息
- 688012 - 中微公司
- 688599 - 天合光能
- 688169 - 石头科技

## 5. 实战工作流程

### 每日选股流程
```bash
# 步骤1：早上/收盘后扫描市场（只看今天的新信号）
python3 batch_monitor.py --board chinext+star --random \
  --max-stocks 100 --min-quality 70 --check-days 1

# 步骤2：发现3只高质量股票，逐个深入分析
python3 single_stock_test.py 300750 --details
python3 single_stock_test.py 688981 --details
python3 single_stock_test.py 300059 --details

# 步骤3：对最感兴趣的股票做多维度分析
python3 single_stock_test.py 300750          # 严格模式
python3 single_stock_test.py 300750 --no-strict  # 标准模式对比
```

### 研究某只股票
```bash
# 步骤1：快速查看是否有信号
python3 batch_monitor.py --stock 300750

# 步骤2：有信号，做详细分析
python3 single_stock_test.py 300750 --details

# 步骤3：查看所有交易记录（新功能）🆕
python3 single_stock_test.py 300750 --all-signals

# 步骤4：查看长期表现
python3 single_stock_test.py 300750 --days 200 --details

# 步骤5：对比不同模式
python3 single_stock_test.py 300750 --all-signals          # 严格模式
python3 single_stock_test.py 300750 --all-signals --no-strict  # 标准模式

# 步骤6：完整的深度分析（推荐）🆕
python3 single_stock_test.py 300750 --days 200 --all-signals --details
```

### 周末回测
```bash
# 测试多只股票的长期表现
python3 single_stock_test.py 300750 --days 200 --details
python3 single_stock_test.py 300059 --days 200 --details
python3 single_stock_test.py 688981 --days 200 --details

# 对比两种模式的效果
python3 compare_modes.py

# 扫描本周的信号
python3 batch_monitor.py --random --max-stocks 200 \
  --check-days 5 --history-days 150
```

### 补扫模式（错过了几天） 🆕
```bash
# 如果周一到周三没有扫描，周四补扫
python3 batch_monitor.py --random --max-stocks 150 \
  --check-days 4 --history-days 120
```

## 6. 参数调优建议

### 如果信号太少
```bash
# 方法1：降低质量阈值
python3 batch_monitor.py --random --min-quality 50

# 方法2：增加检查天数 🆕
python3 batch_monitor.py --random --check-days 5

# 方法3：使用标准模式
python3 batch_monitor.py --random --no-strict

# 方法4：增加股票数量
python3 batch_monitor.py --random --max-stocks 100

# 方法5：组合使用
python3 batch_monitor.py --random --max-stocks 200 \
  --min-quality 50 --check-days 5 --no-strict
```

### 如果信号太多
```bash
# 方法1：提高质量阈值
python3 batch_monitor.py --random --min-quality 80

# 方法2：减少检查天数 🆕
python3 batch_monitor.py --random --check-days 1

# 方法3：确保使用严格模式（默认）
python3 batch_monitor.py --random
```

### 如果数据不足 🆕
```bash
# 方法1：增加历史数据天数
python3 batch_monitor.py --stock 300750 --history-days 200

# 方法2：使用 single_stock_test.py
python3 single_stock_test.py 300750 --days 200
```

### 如果扫描速度太慢 🆕
```bash
# 方法1：减少历史数据天数
python3 batch_monitor.py --random --history-days 80

# 方法2：减少股票数量
python3 batch_monitor.py --random --max-stocks 20

# 方法3：减少请求间隔（谨慎使用）
python3 batch_monitor.py --random --delay 0.05
```

### 如果信号太多
```bash
# 方法1：提高质量阈值
python3 batch_monitor.py --random --min-quality 80

# 方法2：确保使用严格模式（默认）
python3 batch_monitor.py --random

# 方法3：只看Top信号
python3 batch_monitor.py --random --max-stocks 200 --min-quality 75
# 然后只关注输出的Top 5高质量信号
```

### 针对不同风格

**保守型投资者**（追求确定性）
```bash
python3 batch_monitor.py --random --max-stocks 100 --min-quality 75
```

**平衡型投资者**（质量和数量平衡）
```bash
python3 batch_monitor.py --random --max-stocks 50 --min-quality 65
```

**积极型投资者**（更多机会）
```bash
python3 batch_monitor.py --random --max-stocks 100 --min-quality 55 --no-strict
```

## 7. 输出解读

### 批量监控输出
```
>>> 发现买入信号: sz.300750 宁德时代 - 买入日期: 2026-01-30 - 质量: 75.3分
```
- 实时显示发现的信号
- 75.3分是高质量信号（70-80分为"良好"）

### 信号详情表格
```
代码        名称          买入日期      买入价    当前价    盈亏      盈亏%     质量    
sz.300750  宁德时代      2026-01-30  328.50  335.20  +6.70   +2.04%  75.3
```
- 按质量从高到低排序
- 绿色+号表示盈利
- 质量分数用于优先级排序

### Top 5列表
```
1. sz.300750 宁德时代 - 质量: 75.3分
```
- 自动筛选出质量最高的5只股票
- 重点关注这些高质量信号

### 质量评级
- ⭐⭐⭐⭐⭐ 优秀 (80+分)：强烈推荐
- ⭐⭐⭐⭐ 良好 (70-80分)：值得关注
- ⭐⭐⭐ 一般 (60-70分)：谨慎对待
- ⭐⭐ 较差 (<60分)：建议观望

## 8. 故障排查

### 错误：command not found: python
```bash
# 使用python3而不是python
python3 batch_monitor.py --random
```

### 错误：数据不足
```bash
# 增加历史数据天数
python3 single_stock_test.py 300750 --days 200
```

### 没有找到信号
```bash
# 1. 降低质量阈值
python3 batch_monitor.py --random --min-quality 50

# 2. 使用标准模式
python3 batch_monitor.py --random --no-strict

# 3. 增加扫描数量
python3 batch_monitor.py --random --max-stocks 100
```

### 请求过于频繁
```bash
# 增加请求间隔
python3 batch_monitor.py --random --delay 0.5
```

## 9. 高级用法

### 测试多只指定股票（Shell脚本）
```bash
#!/bin/bash
# test_my_stocks.sh

stocks=(300750 688981 300059 600519 000858)

for stock in "${stocks[@]}"
do
    echo "==================== 测试 $stock ===================="
    python3 batch_monitor.py --stock $stock
    echo ""
done
```

### 每日定时扫描（Cron任务）
```bash
# 编辑crontab
crontab -e

# 添加每天15:30执行
30 15 * * 1-5 cd /path/to/codex-stocks && python3 batch_monitor.py --random --max-stocks 100 > daily_scan.log 2>&1
```

### 导出结果到文件
```bash
# 将结果保存到文件
python3 batch_monitor.py --random > scan_results.txt 2>&1

# 只保存股票代码
python3 batch_monitor.py --random 2>&1 | grep "发现买入信号" > signals.txt
```

## 10. 小贴士

💡 **最佳实践**
- 使用严格模式，专注高质量信号
- Top 5信号优先研究
- 单股分析时使用 `--details` 了解历史表现
- 对比标准模式和严格模式的差异

💡 **避免误区**
- 不要追求信号数量，质量更重要
- 历史表现不代表未来收益
- 再好的信号也要设置止损
- 不要全仓单只股票

💡 **效率提升**
- 批量扫描 → 单股分析 → 深入研究
- 保存高质量股票代码，定期跟踪
- 使用Shell脚本批量测试关注的股票
- 周末做长期回测研究
