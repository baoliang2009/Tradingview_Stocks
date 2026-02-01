"""
测试止损功能
快速验证止损逻辑是否正确工作
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from backtest import BacktestEngine
from qqe_trend_strategy import qqe_trend_strategy

# 创建模拟数据
def create_test_data():
    """创建一个会触发止损的测试数据"""
    dates = pd.date_range(start='2024-01-01', periods=150, freq='D')
    
    # 创建一个先上涨后下跌的价格序列
    prices_close = []
    prices_high = []
    prices_low = []
    prices_open = []
    base_price = 10.0
    
    # 前50天缓慢上涨 (创建上涨趋势，触发买入信号)
    for i in range(50):
        base_price += 0.15  # 每天上涨1.5%
        daily_open = base_price
        daily_high = base_price * 1.02
        daily_low = base_price * 0.99
        daily_close = base_price * 1.01
        
        prices_open.append(daily_open)
        prices_high.append(daily_high)
        prices_low.append(daily_low)
        prices_close.append(daily_close)
    
    # 第51-60天继续小幅上涨（买入信号可能在这里触发）
    for i in range(10):
        base_price += 0.05
        daily_open = base_price
        daily_high = base_price * 1.01
        daily_low = base_price * 0.99
        daily_close = base_price
        
        prices_open.append(daily_open)
        prices_high.append(daily_high)
        prices_low.append(daily_low)
        prices_close.append(daily_close)
    
    # 第61-75天快速下跌超过15% (确保触发10%止损)
    peak_price = base_price
    for i in range(15):
        base_price -= peak_price * 0.012  # 每天下跌1.2%相对于峰值
        daily_open = base_price + 0.05
        daily_close = base_price
        daily_high = max(daily_open, daily_close) * 1.005
        daily_low = min(daily_open, daily_close) * 0.995
        
        prices_open.append(daily_open)
        prices_high.append(daily_high)
        prices_low.append(daily_low)
        prices_close.append(daily_close)
    
    # 剩余时间缓慢波动
    for i in range(75):
        base_price += np.random.randn() * 0.02
        daily_open = base_price
        daily_high = base_price * 1.01
        daily_low = base_price * 0.99
        daily_close = base_price * (1 + np.random.randn() * 0.005)
        
        prices_open.append(daily_open)
        prices_high.append(daily_high)
        prices_low.append(daily_low)
        prices_close.append(daily_close)
    
    # 创建OHLCV数据
    data = pd.DataFrame({
        'date': dates,
        'open': prices_open,
        'high': prices_high,
        'low': prices_low,
        'close': prices_close,
        'volume': [1000000 * (1 + np.random.random()) for _ in range(150)]
    })
    data = data.set_index('date')
    
    return data

def test_stop_loss():
    """测试止损功能"""
    print("=" * 80)
    print("止损功能测试")
    print("=" * 80)
    
    # 创建测试数据
    print("\n创建测试数据...")
    test_data = create_test_data()
    print(f"数据长度: {len(test_data)}天")
    print(f"价格范围: {test_data['close'].min():.2f} - {test_data['close'].max():.2f}")
    
    # 不使用止损
    print("\n\n测试1: 不使用止损 (stop_loss=1.0, 即-100%)")
    print("-" * 80)
    engine_no_stop = BacktestEngine(stop_loss=1.0)  # 设置为100%，实际上不会触发
    trades_no_stop = engine_no_stop.backtest_stock(
        'TEST.SZ', '测试股票', test_data, strict_mode=False, min_quality=0
    )
    
    if trades_no_stop:
        for i, trade in enumerate(trades_no_stop, 1):
            print(f"\n交易{i}:")
            print(f"  买入日期: {trade['buy_date']}")
            print(f"  买入价格: {trade['buy_price']:.2f}")
            print(f"  卖出日期: {trade['sell_date']}")
            print(f"  卖出价格: {trade['sell_price']:.2f}")
            print(f"  收益率: {trade['profit_pct']:.2f}%")
            print(f"  退出原因: {trade['exit_reason']}")
            print(f"  持有天数: {trade['holding_days']}")
    else:
        print("未产生交易")
    
    # 使用10%止损
    print("\n\n测试2: 使用10%止损 (stop_loss=0.10)")
    print("-" * 80)
    engine_with_stop = BacktestEngine(stop_loss=0.10)
    trades_with_stop = engine_with_stop.backtest_stock(
        'TEST.SZ', '测试股票', test_data, strict_mode=False, min_quality=0
    )
    
    if trades_with_stop:
        for i, trade in enumerate(trades_with_stop, 1):
            print(f"\n交易{i}:")
            print(f"  买入日期: {trade['buy_date']}")
            print(f"  买入价格: {trade['buy_price']:.2f}")
            print(f"  卖出日期: {trade['sell_date']}")
            print(f"  卖出价格: {trade['sell_price']:.2f}")
            print(f"  收益率: {trade['profit_pct']:.2f}%")
            print(f"  退出原因: {trade['exit_reason']}")
            print(f"  持有天数: {trade['holding_days']}")
            
            if trade['exit_reason'] == 'stop_loss':
                print(f"  ✓ 成功触发止损！")
    else:
        print("未产生交易")
    
    # 对比结果
    print("\n\n" + "=" * 80)
    print("对比分析")
    print("=" * 80)
    
    if trades_no_stop and trades_with_stop:
        metrics_no_stop = engine_no_stop.calculate_metrics(trades_no_stop)
        metrics_with_stop = engine_with_stop.calculate_metrics(trades_with_stop)
        
        print(f"\n{'指标':<20}{'无止损':<20}{'10%止损':<20}{'改善':<20}")
        print("-" * 80)
        print(f"{'交易次数':<20}{metrics_no_stop['total_trades']:<20}{metrics_with_stop['total_trades']:<20}{'-':<20}")
        print(f"{'平均收益%':<20}{metrics_no_stop['avg_profit']:<20.2f}{metrics_with_stop['avg_profit']:<20.2f}{metrics_with_stop['avg_profit']-metrics_no_stop['avg_profit']:<20.2f}")
        print(f"{'最大回撤%':<20}{metrics_no_stop['max_drawdown']:<20.2f}{metrics_with_stop['max_drawdown']:<20.2f}{metrics_with_stop['max_drawdown']-metrics_no_stop['max_drawdown']:<20.2f}")
        print(f"{'平均亏损%':<20}{metrics_no_stop['avg_loss']:<20.2f}{metrics_with_stop['avg_loss']:<20.2f}{metrics_with_stop['avg_loss']-metrics_no_stop['avg_loss']:<20.2f}")
        print(f"{'止损次数':<20}{metrics_no_stop['stop_loss_count']:<20}{metrics_with_stop['stop_loss_count']:<20}{'-':<20}")
        print(f"{'止损率%':<20}{metrics_no_stop['stop_loss_rate']:<20.2f}{metrics_with_stop['stop_loss_rate']:<20.2f}{'-':<20}")
        
        print("\n结论:")
        if metrics_with_stop['stop_loss_count'] > 0:
            print(f"✓ 止损功能正常工作！触发了 {metrics_with_stop['stop_loss_count']} 次止损")
            if metrics_with_stop['avg_loss'] > metrics_no_stop['avg_loss']:
                print(f"✓ 平均亏损从 {metrics_no_stop['avg_loss']:.2f}% 降低到 {metrics_with_stop['avg_loss']:.2f}%")
            if metrics_with_stop['max_drawdown'] > metrics_no_stop['max_drawdown']:
                print(f"✓ 最大回撤从 {metrics_no_stop['max_drawdown']:.2f}% 降低到 {metrics_with_stop['max_drawdown']:.2f}%")
        else:
            print("⚠ 止损未被触发，可能需要调整测试数据")

if __name__ == "__main__":
    test_stop_loss()
