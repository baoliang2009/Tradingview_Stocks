import baostock as bs
import pandas as pd
from datetime import datetime
from qqe_trend_strategy import qqe_trend_strategy


def get_stock_data(code, start_date, end_date):
    lg = bs.login()
    
    rs = bs.query_history_k_data_plus(
        code,
        "date,open,high,low,close,volume,amount",
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="3"
    )
    
    data_list = []
    while (rs.error_code == '0') & rs.next():
        data_list.append(rs.get_row_data())
    
    bs.logout()
    
    df = pd.DataFrame(data_list, columns=rs.fields)
    
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df['amount'] = df['amount'].astype(float)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    
    return df


if __name__ == "__main__":
    stock_code = "sz.300454"
    start_date = "2025-01-01"
    end_date = "2026-01-30"
    
    print(f"正在获取股票 {stock_code} 从 {start_date} 到 {end_date} 的K线数据...")
    stock_data = get_stock_data(stock_code, start_date, end_date)
    
    print(f"获取数据成功，共 {len(stock_data)} 条记录")
    print(stock_data.head())
    
    print("\n正在生成QQE + Trend策略信号...")
    result = qqe_trend_strategy(
        stock_data,
        rsi_length_primary=6,
        rsi_smoothing_primary=5,
        qqe_factor_primary=3.0,
        threshold_primary=3.0,
        rsi_length_secondary=6,
        rsi_smoothing_secondary=5,
        qqe_factor_secondary=1.61,
        threshold_secondary=3.0,
        bollinger_length=50,
        bollinger_multiplier=0.35,
        ma_type='EMA',
        ma_period=9
    )
    
    buy_signals = result[result['buy_signal'] == True]
    sell_signals = result[result['sell_signal'] == True]
    
    print(f"\n生成信号完成！")
    print(f"买入信号数量: {len(buy_signals)}")
    print(f"卖出信号数量: {len(sell_signals)}")
    
    if len(buy_signals) > 0:
        print("\n" + "=" * 80)
        print("买入信号详情:")
        print("=" * 80)
        for idx, row in buy_signals.iterrows():
            print(f"日期: {idx.strftime('%Y-%m-%d')}")
            print(f"  开盘: {row['open']:.2f}, 最高: {row['high']:.2f}, 最低: {row['low']:.2f}, 收盘: {row['close']:.2f}")
            print(f"  QQE值: {row['qqe_value']:.4f}, 趋势: {row['trend']:.4f}")
            print()
    
    if len(sell_signals) > 0:
        print("\n" + "=" * 80)
        print("卖出信号详情:")
        print("=" * 80)
        for idx, row in sell_signals.iterrows():
            print(f"日期: {idx.strftime('%Y-%m-%d')}")
            print(f"  开盘: {row['open']:.2f}, 最高: {row['high']:.2f}, 最低: {row['low']:.2f}, 收盘: {row['close']:.2f}")
            print(f"  QQE值: {row['qqe_value']:.4f}, 趋势: {row['trend']:.4f}")
            print()
    
    print("\n" + "=" * 80)
    print("回测分析:")
    print("=" * 80)
    
    position = None
    entry_price = None
    entry_date = None
    trades = []
    
    for idx, row in result.iterrows():
        if row['buy_signal'] and position is None:
            position = 'long'
            entry_price = row['open']
            entry_date = idx
            print(f"[买入] {idx.strftime('%Y-%m-%d')}: 入场价格 {entry_price:.2f}")
        elif row['sell_signal'] and position == 'long':
            exit_price = row['open']
            exit_date = idx
            profit = exit_price - entry_price
            profit_pct = (profit / entry_price) * 100
            trades.append({
                'entry_date': entry_date,
                'exit_date': exit_date,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'profit': profit,
                'profit_pct': profit_pct
            })
            print(f"[卖出] {exit_date.strftime('%Y-%m-%d')}: 出场价格 {exit_price:.2f}, 盈亏 {profit:.2f} ({profit_pct:.2f}%)")
            position = None
            entry_price = None
    
    if position == 'long' and entry_price is not None:
        last_price = result.iloc[-1]['close']
        unrealized_profit = last_price - entry_price
        unrealized_profit_pct = (unrealized_profit / entry_price) * 100
        print(f"[持仓中] 入场 {entry_date.strftime('%Y-%m-%d')}: 入场价格 {entry_price:.2f}, 当前价格 {last_price:.2f}, 未实现盈亏 {unrealized_profit:.2f} ({unrealized_profit_pct:.2f}%)")
    
    print("\n" + "=" * 80)
    print("盈利统计:")
    print("=" * 80)
    
    if len(trades) > 0:
        total_profit = sum(t['profit'] for t in trades)
        total_profit_pct = sum(t['profit_pct'] for t in trades)
        winning_trades = [t for t in trades if t['profit'] > 0]
        losing_trades = [t for t in trades if t['profit'] <= 0]
        
        print(f"总交易次数: {len(trades)}")
        print(f"盈利交易: {len(winning_trades)}")
        print(f"亏损交易: {len(losing_trades)}")
        print(f"胜率: {len(winning_trades)/len(trades)*100:.2f}%")
        print(f"总盈亏: {total_profit:.2f}")
        print(f"平均盈亏: {total_profit/len(trades):.2f}")
        print(f"平均盈亏%: {total_profit_pct/len(trades):.2f}%")
        print(f"最大盈利: {max(t['profit'] for t in trades):.2f}")
        print(f"最大亏损: {min(t['profit'] for t in trades):.2f}")
        
        if len(winning_trades) > 0:
            avg_win = sum(t['profit'] for t in winning_trades) / len(winning_trades)
            avg_win_pct = sum(t['profit_pct'] for t in winning_trades) / len(winning_trades)
            print(f"平均盈利: {avg_win:.2f} ({avg_win_pct:.2f}%)")
        
        if len(losing_trades) > 0:
            avg_loss = sum(t['profit'] for t in losing_trades) / len(losing_trades)
            avg_loss_pct = sum(t['profit_pct'] for t in losing_trades) / len(losing_trades)
            print(f"平均亏损: {avg_loss:.2f} ({avg_loss_pct:.2f}%)")
        
        print(f"盈亏比: {avg_win/abs(avg_loss) if len(losing_trades) > 0 and avg_loss != 0 else 0:.2f}")
    else:
        print("没有完成任何交易")
    
    print("\n最近10天的指标:")
    print(result[['close', 'qqe_value', 'trend', 'long_condition', 'short_condition']].tail(10))
