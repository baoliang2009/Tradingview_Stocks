import baostock as bs
import pandas as pd
from datetime import datetime, timedelta
from qqe_trend_strategy import qqe_trend_strategy
import time
import random
import sys


def get_stock_list(board_filter=None):
    """获取A股股票列表
    
    Args:
        board_filter: 板块筛选 'chinext' (创业板) 或 'star' (科创板) 或 None (全部)
    """
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
        return []
    
    # 重新查询股票列表
    rs = bs.query_all_stock(day=trade_date)
    
    stock_list = []
    while (rs.error_code == '0') & rs.next():
        row = rs.get_row_data()
        if len(row) >= 3:
            full_code = row[0]
            status = row[1]
            name = row[2]
            
            if status == '1':
                stock_code = full_code
                
                # 过滤ST和退市股票
                if 'ST' not in name and '退' not in name:
                    # 板块筛选
                    code_num = stock_code.split('.')[-1]
                    
                    # 创业板: 300开头, 301开头
                    is_chinext = code_num.startswith('300') or code_num.startswith('301')
                    # 科创板: 688开头
                    is_star = code_num.startswith('688')
                    
                    if board_filter == 'chinext' and not is_chinext:
                        continue
                    elif board_filter == 'star' and not is_star:
                        continue
                    elif board_filter == 'chinext+star' and not (is_chinext or is_star):
                        continue
                    
                    stock_list.append({'code': stock_code, 'name': name})
    
    bs.logout()
    
    return stock_list


def get_recent_stock_data(code, days=120):
    """获取股票最近N天的K线数据
    
    Args:
        code: 股票代码
        days: 获取天数，默认120天以确保有足够的数据计算指标
    """
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
    
    # 过滤掉空值
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


def check_buy_signal(stock_data, check_days=2, strict_mode=True, min_quality=60):
    """检查最近N天内是否有买入信号
    
    Args:
        stock_data: 股票数据DataFrame
        check_days: 检查最近几天，默认2天
        strict_mode: 是否使用严格模式，默认True
        min_quality: 最低信号质量分数(0-100)，默认60
        
    Returns:
        buy_date, buy_price, current_price, signal_quality
    """
    if stock_data is None or len(stock_data) < 60:
        return None, None, None, None
    
    try:
        result = qqe_trend_strategy(stock_data, strict_mode=strict_mode)
        
        # 使用严格模式的买入信号
        signal_column = 'buy_signal_strict' if strict_mode else 'buy_signal'
        
        # 检查最近N天的买入信号
        recent_data = result.tail(check_days)
        
        buy_signals = recent_data[recent_data[signal_column] == True]
        
        if len(buy_signals) > 0:
            latest_buy = buy_signals.iloc[-1]
            buy_date = latest_buy.name
            buy_price = latest_buy['open']
            current_price = result.iloc[-1]['close']
            signal_quality = latest_buy.get('signal_quality', 0)
            
            # 质量过滤
            if signal_quality < min_quality:
                return None, None, None, None
            
            return buy_date, buy_price, current_price, signal_quality
        
        return None, None, None, None
    except Exception as e:
        # 策略计算失败，返回None
        return None, None, None, None


def batch_monitor_stocks(board_filter=None, max_stocks=None, random_sample=False, 
                        strict_mode=True, min_quality=60, history_days=120, 
                        check_days=2, delay=0.1):
    """批量监控股票池
    
    Args:
        board_filter: 板块筛选 'chinext' (创业板) 或 'star' (科创板) 或 'chinext+star' (创业板+科创板) 或 None (全部)
        max_stocks: 最大监控股票数量
        random_sample: 是否随机采样
        strict_mode: 是否使用严格模式（更少但质量更高的信号）
        min_quality: 最低信号质量分数(0-100)
        history_days: 获取历史数据天数
        check_days: 检查最近几天的买入信号
        delay: 请求间隔时间(秒)
    """
    print("=" * 80)
    print("开始批量监控A股股票池...")
    print("=" * 80)
    
    # 获取股票列表
    stock_list = get_stock_list(board_filter=board_filter)
    
    if len(stock_list) == 0:
        print("未找到符合条件的股票")
        return []
    
    # 随机采样
    if random_sample and max_stocks and max_stocks < len(stock_list):
        stock_list = random.sample(stock_list, max_stocks)
    elif max_stocks and max_stocks < len(stock_list):
        stock_list = stock_list[:max_stocks]
    # 如果 max_stocks 为 None，则使用全部股票列表
    
    board_name = {
        'chinext': '创业板',
        'star': '科创板',
        'chinext+star': '创业板+科创板',
        None: 'A股全市场'
    }.get(board_filter, 'A股全市场')
    
    mode_name = "严格模式" if strict_mode else "标准模式"
    
    print(f"板块范围: {board_name}")
    print(f"筛选模式: {mode_name}")
    print(f"质量阈值: {min_quality}分")
    print(f"股票池总数: {len(stock_list)}")
    print(f"历史数据: {history_days}天")
    print(f"检查范围: 最近{check_days}天内的买入信号")
    print("=" * 80)
    
    buy_signals_found = []
    error_count = 0
    
    for i, stock in enumerate(stock_list, 1):
        try:
            code = stock['code']
            name = stock['name']
            
            print(f"\r进度: {i}/{len(stock_list)} - {code} {name}  ", end='', flush=True)
            
            # 获取历史数据
            stock_data = get_recent_stock_data(code, days=history_days)
            
            if stock_data is None or len(stock_data) < 60:
                continue
            
            buy_date, buy_price, current_price, signal_quality = check_buy_signal(
                stock_data, check_days=check_days, strict_mode=strict_mode, min_quality=min_quality
            )
            
            if buy_date is not None:
                profit = current_price - buy_price
                profit_pct = (profit / buy_price) * 100
                
                buy_signals_found.append({
                    'code': code,
                    'name': name,
                    'buy_date': buy_date,
                    'buy_price': buy_price,
                    'current_price': current_price,
                    'profit': profit,
                    'profit_pct': profit_pct,
                    'quality': signal_quality
                })
                
                # 实时显示发现的股票
                print(f"\n>>> 发现买入信号: {code} {name} - 买入日期: {buy_date.strftime('%Y-%m-%d')} - 质量: {signal_quality:.1f}分")
            
            time.sleep(delay)
            
        except Exception as e:
            error_count += 1
            if error_count <= 5:  # 只显示前5个错误
                print(f"\n错误: {code} {name} - {str(e)}")
            continue
    
    print("\n" + "=" * 80)
    print(f"监控完成! 找到 {len(buy_signals_found)} 只股票出现买入信号")
    print("=" * 80)
    
    if len(buy_signals_found) > 0:
        # 按信号质量排序
        buy_signals_found = sorted(buy_signals_found, key=lambda x: x['quality'], reverse=True)
        
        print("\n买入信号详情 (按质量排序):")
        print("-" * 90)
        print(f"{'代码':<10}{'名称':<12}{'买入日期':<12}{'买入价':<8}{'当前价':<8}{'盈亏':<8}{'盈亏%':<8}{'质量':<8}")
        print("-" * 90)
        
        for signal in buy_signals_found:
            profit_str = f"+{signal['profit']:.2f}" if signal['profit'] >= 0 else f"{signal['profit']:.2f}"
            profit_pct_str = f"+{signal['profit_pct']:.2f}%" if signal['profit_pct'] >= 0 else f"{signal['profit_pct']:.2f}%"
            quality_str = f"{signal['quality']:.1f}"
            print(f"{signal['code']:<10}{signal['name']:<12}{signal['buy_date'].strftime('%Y-%m-%d'):<12}{signal['buy_price']:<8.2f}{signal['current_price']:<8.2f}{profit_str:<8}{profit_pct_str:<8}{quality_str:<8}")
        
        print("-" * 90)
        print(f"\n汇总:")
        print(f"  买入信号数量: {len(buy_signals_found)}")
        
        if len(buy_signals_found) > 0:
            avg_quality = sum(s['quality'] for s in buy_signals_found) / len(buy_signals_found)
            print(f"  平均质量: {avg_quality:.1f}分")
            
            total_profit = sum(s['profit'] for s in buy_signals_found)
            total_profit_pct = sum(s['profit_pct'] for s in buy_signals_found) / len(buy_signals_found)
            print(f"  平均盈亏: {total_profit/len(buy_signals_found):.2f} ({total_profit_pct:.2f}%)")
            
            profit_count = sum(1 for s in buy_signals_found if s['profit'] > 0)
            loss_count = sum(1 for s in buy_signals_found if s['profit'] <= 0)
            print(f"  盈利: {profit_count}, 亏损: {loss_count}")
            if len(buy_signals_found) > 0:
                print(f"  胜率: {profit_count/len(buy_signals_found)*100:.2f}%")
        
        # 输出股票代码列表
        print("\n发现的股票代码列表 (按质量从高到低):")
        print("-" * 90)
        stock_codes = [s['code'] for s in buy_signals_found]
        for i in range(0, len(stock_codes), 5):
            print("  " + "  ".join(stock_codes[i:i+5]))
        print("-" * 90)
        
        # 输出Top 5 高质量信号
        if len(buy_signals_found) >= 5:
            print("\nTop 5 高质量信号:")
            print("-" * 90)
            for i, signal in enumerate(buy_signals_found[:5], 1):
                print(f"{i}. {signal['code']} {signal['name']} - 质量: {signal['quality']:.1f}分")
            print("-" * 90)
    else:
        print("当前没有股票出现买入信号")
        print("\n提示: 可以尝试降低质量阈值 (--min-quality) 或使用标准模式 (--no-strict)")
    
    return buy_signals_found


def get_stock_data_single(code, days=120):
    """获取单只股票数据
    
    Args:
        code: 股票代码（如 sz.300750 或 300750）
        days: 获取天数，默认120天
    
    Returns:
        full_code, name, data
    """
    # 自动添加市场前缀
    if '.' not in code:
        if code.startswith('6'):
            code = f'sh.{code}'
        else:
            code = f'sz.{code}'
    
    lg = bs.login()
    
    # 获取股票名称
    name = None
    for days_back in range(10):
        test_date = datetime.now() - timedelta(days=days_back)
        date_str = test_date.strftime("%Y-%m-%d")
        
        rs = bs.query_all_stock(day=date_str)
        
        if rs.error_code == '0':
            while rs.next():
                row = rs.get_row_data()
                if len(row) >= 3 and row[0] == code:
                    name = row[2]
                    break
            if name:
                break
    
    # 获取K线数据
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
        return code, name, None
    
    df = pd.DataFrame(data_list, columns=rs.fields)
    df = df[df['close'] != '']
    
    if len(df) == 0:
        return code, name, None
    
    df['open'] = df['open'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['volume'] = df['volume'].astype(float)
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df.sort_index()
    
    return code, name, df


def test_single_stock_simple(code, strict_mode=True, min_quality=60, history_days=120, check_days=2):
    """简单测试单只股票
    
    Args:
        code: 股票代码
        strict_mode: 是否使用严格模式
        min_quality: 最低信号质量分数
        history_days: 获取历史数据天数
        check_days: 检查最近几天的买入信号
    """
    print("=" * 80)
    print("单只股票测试")
    print("=" * 80)
    
    full_code, name, data = get_stock_data_single(code, days=history_days)
    
    if data is None or len(data) < 60:
        print(f"错误: 股票 {code} 数据不足（需要至少60个交易日）")
        return
    
    print(f"股票代码: {full_code}")
    if name:
        print(f"股票名称: {name}")
    print(f"数据范围: {data.index[0].strftime('%Y-%m-%d')} 至 {data.index[-1].strftime('%Y-%m-%d')}")
    print(f"数据天数: {len(data)} 天")
    print(f"历史数据: {history_days}天")
    print(f"分析模式: {'严格模式' if strict_mode else '标准模式'}")
    print(f"质量阈值: {min_quality}分")
    print(f"检查范围: 最近{check_days}天")
    print("=" * 80)
    
    # 检查买入信号
    buy_date, buy_price, current_price, signal_quality = check_buy_signal(
        data, check_days=check_days, strict_mode=strict_mode, min_quality=min_quality
    )
    
    if buy_date is not None:
        profit = current_price - buy_price
        profit_pct = (profit / buy_price) * 100
        
        print("\n✅ 发现买入信号！")
        print("-" * 80)
        print(f"信号日期: {buy_date.strftime('%Y-%m-%d')}")
        print(f"买入价格: {buy_price:.2f}")
        print(f"当前价格: {current_price:.2f}")
        print(f"盈亏: {profit:+.2f} ({profit_pct:+.2f}%)")
        
        if strict_mode:
            print(f"信号质量: {signal_quality:.1f}分")
            
            if signal_quality >= 80:
                print("质量评价: ⭐⭐⭐⭐⭐ 优秀")
            elif signal_quality >= 70:
                print("质量评价: ⭐⭐⭐⭐ 良好")
            elif signal_quality >= 60:
                print("质量评价: ⭐⭐⭐ 一般")
            else:
                print("质量评价: ⭐⭐ 较差")
        print("-" * 80)
    else:
        print(f"\n❌ 最近{check_days}天内没有符合条件的买入信号")
        print("-" * 80)
        print("提示:")
        print("  - 可以尝试降低质量阈值 (--min-quality)")
        print("  - 或增加检查天数 (--check-days)")
        print("  - 或使用标准模式 (--no-strict)")
        print("  - 或使用 single_stock_test.py 查看详细分析")
        print("-" * 80)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='批量监控A股股票买入信号')
    parser.add_argument('--stock', type=str, default=None,
                        help='测试单只股票（输入股票代码，如 300750）')
    parser.add_argument('--board', type=str, default='chinext+star', 
                        choices=['chinext', 'star', 'chinext+star', 'all'],
                        help='板块筛选: chinext(创业板), star(科创板), chinext+star(创业板+科创板), all(全部A股)')
    parser.add_argument('--max-stocks', type=str, default='20', 
                        help='最大监控股票数量，默认20只用于测试，使用 "all" 监控全部股票')
    parser.add_argument('--random', action='store_true', 
                        help='是否随机采样股票')
    parser.add_argument('--no-strict', action='store_true',
                        help='不使用严格模式（会产生更多但质量较低的信号）')
    parser.add_argument('--min-quality', type=int, default=60,
                        help='最低信号质量分数(0-100)，默认60分')
    parser.add_argument('--history-days', type=int, default=120,
                        help='获取历史数据天数，默认120天')
    parser.add_argument('--check-days', type=int, default=2,
                        help='检查最近几天的买入信号，默认2天')
    parser.add_argument('--delay', type=float, default=0.1,
                        help='请求间隔时间(秒)，避免频繁请求，默认0.1秒')
    
    args = parser.parse_args()
    
    strict_mode = not args.no_strict
    
    # 处理 max_stocks 参数
    if args.max_stocks.lower() == 'all':
        max_stocks = None  # None 表示不限制数量
    else:
        max_stocks = int(args.max_stocks)
    
    # 单只股票测试模式
    if args.stock:
        test_single_stock_simple(
            args.stock, 
            strict_mode=strict_mode, 
            min_quality=args.min_quality,
            history_days=args.history_days,
            check_days=args.check_days
        )
    else:
        # 批量监控模式
        board_filter = None if args.board == 'all' else args.board
        
        batch_monitor_stocks(
            board_filter=board_filter,
            max_stocks=max_stocks,
            random_sample=args.random,
            strict_mode=strict_mode,
            min_quality=args.min_quality,
            history_days=args.history_days,
            check_days=args.check_days,
            delay=args.delay
        )

