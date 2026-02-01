"""
对比标准模式和严格模式的信号数量和质量
"""
import baostock as bs
import pandas as pd
from datetime import datetime, timedelta
from qqe_trend_strategy import qqe_trend_strategy


def get_test_stock_data(code='sz.300750', days=100):
    """获取测试股票数据"""
    lg = bs.login()
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    rs = bs.query_history_k_data_plus(
        code,
        "date,open,high,low,close,volume",
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="3"
    )
    
    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    
    bs.logout()
    
    if len(data_list) == 0:
        return None
    
    df = pd.DataFrame(data_list, columns=rs.fields)
    df = df[df['close'] != '']
    
    if len(df) == 0:
        return None
    
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df.sort_index()
    
    return df


def compare_modes(code='sz.300750'):
    """对比两种模式的信号"""
    print("=" * 80)
    print(f"对比测试 - 股票代码: {code}")
    print("=" * 80)
    
    # 获取数据
    data = get_test_stock_data(code)
    
    if data is None or len(data) < 60:
        print("数据不足，无法测试")
        return
    
    print(f"数据范围: {data.index[0].strftime('%Y-%m-%d')} 至 {data.index[-1].strftime('%Y-%m-%d')}")
    print(f"数据天数: {len(data)} 天")
    print()
    
    # 标准模式
    print("-" * 80)
    print("【标准模式】")
    print("-" * 80)
    result_standard = qqe_trend_strategy(data, strict_mode=False)
    buy_signals_standard = result_standard[result_standard['buy_signal'] == True]
    print(f"买入信号数量: {len(buy_signals_standard)}")
    
    if len(buy_signals_standard) > 0:
        print("\n最近5个买入信号:")
        for i, (date, row) in enumerate(buy_signals_standard.tail(5).iterrows(), 1):
            print(f"  {i}. 日期: {date.strftime('%Y-%m-%d')}, 价格: {row['close']:.2f}")
    
    # 严格模式
    print("\n" + "-" * 80)
    print("【严格模式】")
    print("-" * 80)
    result_strict = qqe_trend_strategy(data, strict_mode=True)
    buy_signals_strict = result_strict[result_strict['buy_signal_strict'] == True]
    print(f"买入信号数量: {len(buy_signals_strict)}")
    
    if len(buy_signals_strict) > 0:
        print("\n最近5个买入信号:")
        for i, (date, row) in enumerate(buy_signals_strict.tail(5).iterrows(), 1):
            quality = row.get('signal_quality', 0)
            print(f"  {i}. 日期: {date.strftime('%Y-%m-%d')}, 价格: {row['close']:.2f}, 质量: {quality:.1f}分")
    
    # 对比统计
    print("\n" + "=" * 80)
    print("【对比总结】")
    print("=" * 80)
    print(f"标准模式信号数量: {len(buy_signals_standard)}")
    print(f"严格模式信号数量: {len(buy_signals_strict)}")
    if len(buy_signals_standard) > 0:
        reduction = (1 - len(buy_signals_strict) / len(buy_signals_standard)) * 100
        print(f"信号减少比例: {reduction:.1f}%")
    
    if len(buy_signals_strict) > 0:
        avg_quality = result_strict[result_strict['buy_signal_strict'] == True]['signal_quality'].mean()
        print(f"严格模式平均质量: {avg_quality:.1f}分")


if __name__ == "__main__":
    # 测试几个股票
    test_codes = [
        'sz.300750',  # 宁德时代
        'sz.300059',  # 东方财富
        'sh.688981',  # 中芯国际
    ]
    
    for code in test_codes:
        try:
            compare_modes(code)
            print("\n\n")
        except Exception as e:
            print(f"测试 {code} 失败: {str(e)}\n\n")
