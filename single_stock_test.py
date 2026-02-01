"""
单只股票测试工具
支持详细分析单只股票的买入信号和策略指标
"""
import baostock as bs
import pandas as pd
from datetime import datetime, timedelta
from qqe_trend_strategy import qqe_trend_strategy
import argparse


def get_stock_data(code, days=100):
    """获取股票数据
    
    Args:
        code: 股票代码（如 sz.300750 或 300750）
        days: 获取天数
    """
    # 自动添加市场前缀
    if '.' not in code:
        if code.startswith('6'):
            code = f'sh.{code}'
        else:
            code = f'sz.{code}'
    
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
        return None, None
    
    df = pd.DataFrame(data_list, columns=rs.fields)
    df = df[df['close'] != '']
    
    if len(df) == 0:
        return None, None
    
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df.sort_index()
    
    return code, df


def get_stock_name(code):
    """获取股票名称"""
    lg = bs.login()
    
    # 找到最近的交易日
    trade_date = None
    for days_back in range(10):
        test_date = datetime.now() - timedelta(days=days_back)
        date_str = test_date.strftime("%Y-%m-%d")
        
        rs = bs.query_all_stock(day=date_str)
        
        if rs.error_code == '0':
            count = 0
            while rs.next():
                count += 1
                if count > 0:
                    trade_date = date_str
                    break
            if trade_date:
                break
    
    if not trade_date:
        bs.logout()
        return None
    
    # 查询股票信息
    rs = bs.query_all_stock(day=trade_date)
    
    name = None
    while (rs.error_code == '0') & rs.next():
        row = rs.get_row_data()
        if len(row) >= 3 and row[0] == code:
            name = row[2]
            break
    
    bs.logout()
    return name


def test_single_stock(code, strict_mode=True, show_details=False, show_all_signals=False):
    """测试单只股票
    
    Args:
        code: 股票代码
        strict_mode: 是否使用严格模式
        show_details: 是否显示详细指标
        show_all_signals: 是否显示所有买入卖出信号记录
    """
    print("=" * 80)
    print("单只股票测试")
    print("=" * 80)
    
    # 获取数据
    full_code, data = get_stock_data(code)
    
    if data is None or len(data) < 60:
        print(f"错误: 股票 {code} 数据不足（需要至少60个交易日）")
        return
    
    # 获取股票名称
    name = get_stock_name(full_code)
    if name:
        print(f"股票代码: {full_code}")
        print(f"股票名称: {name}")
    else:
        print(f"股票代码: {full_code}")
    
    print(f"数据范围: {data.index[0].strftime('%Y-%m-%d')} 至 {data.index[-1].strftime('%Y-%m-%d')}")
    print(f"数据天数: {len(data)} 天")
    print(f"分析模式: {'严格模式' if strict_mode else '标准模式'}")
    print("=" * 80)
    
    # 运行策略
    result = qqe_trend_strategy(data, strict_mode=strict_mode)
    
    # 分析信号
    signal_column = 'buy_signal_strict' if strict_mode else 'buy_signal'
    buy_signals = result[result[signal_column] == True]
    sell_signals = result[result['sell_signal'] == True]
    
    print(f"\n买入信号数量: {len(buy_signals)}")
    print(f"卖出信号数量: {len(sell_signals)}")
    
    # 显示所有买入信号记录
    if show_all_signals and len(buy_signals) > 0:
        print("\n" + "=" * 90)
        print("所有买入信号记录:")
        print("=" * 90)
        print(f"{'序号':<4}{'日期':<12}{'开盘价':<8}{'收盘价':<8}{'涨幅%':<8}{'趋势':<8}{'RSI':<8}", end='')
        if strict_mode:
            print(f"{'质量':<8}", end='')
        print()
        print("-" * 90)
        
        for i, (date, row) in enumerate(buy_signals.iterrows(), 1):
            quality = row.get('signal_quality', 0) if strict_mode else 0
            trend = row.get('trend', 0)
            rsi = row.get('secondary_rsi', 0)
            day_change = ((row['close'] - row['open']) / row['open'] * 100)
            
            print(f"{i:<4}{date.strftime('%Y-%m-%d'):<12}{row['open']:<8.2f}{row['close']:<8.2f}{day_change:<8.2f}{trend:<8.2f}{rsi:<8.2f}", end='')
            if strict_mode:
                print(f"{quality:<8.1f}", end='')
            print()
        
        print("=" * 90)
    
    # 显示所有卖出信号记录
    if show_all_signals and len(sell_signals) > 0:
        print("\n" + "=" * 90)
        print("所有卖出信号记录:")
        print("=" * 90)
        print(f"{'序号':<4}{'日期':<12}{'开盘价':<8}{'收盘价':<8}{'跌幅%':<8}{'趋势':<8}{'RSI':<8}")
        print("-" * 90)
        
        for i, (date, row) in enumerate(sell_signals.iterrows(), 1):
            trend = row.get('trend', 0)
            rsi = row.get('secondary_rsi', 0)
            day_change = ((row['close'] - row['open']) / row['open'] * 100)
            
            print(f"{i:<4}{date.strftime('%Y-%m-%d'):<12}{row['open']:<8.2f}{row['close']:<8.2f}{day_change:<8.2f}{trend:<8.2f}{rsi:<8.2f}")
        
        print("=" * 90)
    
    # 配对分析买入卖出信号
    if show_all_signals and len(buy_signals) > 0:
        print("\n" + "=" * 100)
        print("买入-卖出配对分析:")
        print("=" * 100)
        print(f"{'交易':<4}{'买入日期':<12}{'买入价':<8}{'卖出日期':<12}{'卖出价':<8}{'收益率%':<10}{'持有天数':<8}{'状态':<8}")
        print("-" * 100)
        
        for i in range(len(buy_signals)):
            buy_date = buy_signals.index[i]
            buy_price = buy_signals.iloc[i]['open']
            
            # 找到下一个卖出信号或持有到最后
            future_sells = sell_signals[sell_signals.index > buy_date]
            
            if len(future_sells) > 0:
                sell_date = future_sells.index[0]
                sell_price = result.loc[sell_date, 'open']
                status = "已卖出"
            else:
                sell_date = result.index[-1]
                sell_price = result.iloc[-1]['close']
                status = "持有中"
            
            profit_pct = (sell_price - buy_price) / buy_price * 100
            holding_days = (sell_date - buy_date).days
            
            profit_str = f"{profit_pct:+.2f}"
            
            print(f"{i+1:<4}{buy_date.strftime('%Y-%m-%d'):<12}{buy_price:<8.2f}{sell_date.strftime('%Y-%m-%d'):<12}{sell_price:<8.2f}{profit_str:<10}{holding_days:<8}{status:<8}")
        
        print("=" * 100)
    
    # 最近的买入信号（不显示所有信号时才显示这个）
    if not show_all_signals and len(buy_signals) > 0:
        print("\n" + "-" * 80)
        print("最近5个买入信号:")
        print("-" * 80)
        
        for i, (date, row) in enumerate(buy_signals.tail(5).iterrows(), 1):
            quality = row.get('signal_quality', 0) if strict_mode else 0
            trend = row.get('trend', 0)
            rsi = row.get('secondary_rsi', 0)
            
            print(f"\n{i}. 日期: {date.strftime('%Y-%m-%d')}")
            print(f"   开盘价: {row['open']:.2f}")
            print(f"   收盘价: {row['close']:.2f}")
            print(f"   涨幅: {((row['close'] - row['open']) / row['open'] * 100):.2f}%")
            
            if strict_mode:
                print(f"   信号质量: {quality:.1f}分")
            print(f"   趋势强度: {trend:.2f}")
            print(f"   RSI: {rsi:.2f}")
    
    # 最近2天的买入信号
    recent_signals = result.tail(2)
    recent_buy = recent_signals[recent_signals[signal_column] == True]
    
    if len(recent_buy) > 0:
        print("\n" + "=" * 80)
        print("⚠️  最近2天内有买入信号！")
        print("=" * 80)
        
        for date, row in recent_buy.iterrows():
            quality = row.get('signal_quality', 0) if strict_mode else 0
            current_price = result.iloc[-1]['close']
            buy_price = row['open']
            profit = current_price - buy_price
            profit_pct = (profit / buy_price) * 100
            
            print(f"\n信号日期: {date.strftime('%Y-%m-%d')}")
            print(f"买入价格: {buy_price:.2f}")
            print(f"当前价格: {current_price:.2f}")
            print(f"盈亏: {profit:+.2f} ({profit_pct:+.2f}%)")
            
            if strict_mode:
                print(f"信号质量: {quality:.1f}分")
                
                # 质量评价
                if quality >= 80:
                    print("质量评价: ⭐⭐⭐⭐⭐ 优秀")
                elif quality >= 70:
                    print("质量评价: ⭐⭐⭐⭐ 良好")
                elif quality >= 60:
                    print("质量评价: ⭐⭐⭐ 一般")
                else:
                    print("质量评价: ⭐⭐ 较差")
    else:
        print("\n" + "=" * 80)
        print("最近2天内没有买入信号")
        print("=" * 80)
    
    # 当前状态分析
    latest = result.iloc[-1]
    print("\n" + "-" * 80)
    print("当前状态分析:")
    print("-" * 80)
    print(f"最新收盘价: {latest['close']:.2f}")
    print(f"趋势值: {latest['trend']:.2f} ({'上升趋势' if latest['trend'] > 0 else '下降趋势'})")
    print(f"Primary RSI: {latest['primary_rsi']:.2f}")
    print(f"Secondary RSI: {latest['secondary_rsi']:.2f}")
    print(f"QQE值: {latest['qqe_value']:.2f}")
    
    if strict_mode:
        print(f"当前信号质量: {latest.get('signal_quality', 0):.1f}分")
    
    # 趋势判断
    if latest['long_condition']:
        print("\n状态: ✅ 多头趋势中")
    elif latest['short_condition']:
        print("\n状态: ❌ 空头趋势中")
    else:
        print("\n状态: ➖ 震荡或观望")
    
    # 显示详细指标
    if show_details:
        print("\n" + "=" * 80)
        print("详细技术指标 (最近5天):")
        print("=" * 80)
        
        detail_cols = ['close', 'trend', 'primary_rsi', 'secondary_rsi', 'qqe_value']
        if strict_mode:
            detail_cols.append('signal_quality')
        
        detail_df = result[detail_cols].tail(5)
        detail_df.index = detail_df.index.strftime('%Y-%m-%d')
        
        print("\n" + detail_df.to_string())
    
    # 回测统计
    if len(buy_signals) > 0:
        print("\n" + "=" * 80)
        print("历史信号统计:")
        print("=" * 80)
        
        profits = []
        for i in range(len(buy_signals)):
            buy_date = buy_signals.index[i]
            buy_price = buy_signals.iloc[i]['open']
            
            # 找到下一个卖出信号或持有到最后
            future_sells = sell_signals[sell_signals.index > buy_date]
            
            if len(future_sells) > 0:
                sell_date = future_sells.index[0]
                sell_price = result.loc[sell_date, 'open']
            else:
                sell_price = result.iloc[-1]['close']
            
            profit_pct = (sell_price - buy_price) / buy_price * 100
            profits.append(profit_pct)
        
        if len(profits) > 0:
            print(f"总交易次数: {len(profits)}")
            print(f"平均收益率: {sum(profits)/len(profits):.2f}%")
            print(f"最大收益: {max(profits):.2f}%")
            print(f"最大亏损: {min(profits):.2f}%")
            
            win_count = sum(1 for p in profits if p > 0)
            print(f"盈利次数: {win_count}")
            print(f"亏损次数: {len(profits) - win_count}")
            print(f"胜率: {win_count/len(profits)*100:.2f}%")


def main():
    parser = argparse.ArgumentParser(description='测试单只股票的QQE趋势策略')
    parser.add_argument('code', type=str, help='股票代码（如 300750 或 sz.300750）')
    parser.add_argument('--no-strict', action='store_true',
                        help='使用标准模式（默认使用严格模式）')
    parser.add_argument('--details', action='store_true',
                        help='显示详细技术指标')
    parser.add_argument('--all-signals', action='store_true',
                        help='显示所有买入卖出信号记录')
    parser.add_argument('--days', type=int, default=100,
                        help='获取历史数据天数（默认100天）')
    
    args = parser.parse_args()
    
    strict_mode = not args.no_strict
    
    test_single_stock(args.code, strict_mode=strict_mode, 
                     show_details=args.details, 
                     show_all_signals=args.all_signals)


if __name__ == "__main__":
    main()
