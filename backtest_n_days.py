"""
N天延迟回测系统
发现买入信号后，第buy_delay天买入，持有hold_days天后卖出
支持批量测试不同参数组合的效果
"""
import baostock as bs
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from qqe_trend_strategy import qqe_trend_strategy
import argparse
import json
from typing import List, Dict, Tuple, Optional
import time


class NDayBacktester:
    """
    N天延迟回测引擎
    
    逻辑：
    - 检测到买入信号后，在第buy_delay个交易日买入
    - 买入后持有hold_days个交易日卖出
    - buy_delay和hold_days可分别配置
    """
    
    def __init__(self, 
                 buy_delay: int = 3,
                 hold_days: int = 5,
                 initial_capital: float = 100000,
                 commission: float = 0.0003,
                 slippage: float = 0.001,
                 position_size: float = 1.0,
                 strict_mode: bool = True,
                 min_quality: int = 60):
        """
        初始化回测引擎
        
        Args:
            buy_delay: 买入延迟天数，信号出现后第buy_delay天买入
            hold_days: 持有天数，买入后持有hold_days天卖出
            initial_capital: 初始资金
            commission: 手续费率
            slippage: 滑点
            position_size: 仓位比例(0-1)
            strict_mode: 是否使用严格模式
            min_quality: 最低信号质量
        """
        self.buy_delay = buy_delay
        self.hold_days = hold_days
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.position_size = position_size
        self.strict_mode = strict_mode
        self.min_quality = min_quality
        
        # 回测状态
        self.cash = initial_capital
        self.positions = {}  # {code: {'shares': int, 'cost_price': float, 'buy_date': str, 'planned_sell_date': str, ...}}
        self.pending_orders = []  # [{'code': str, 'name': str, 'signal_date': str, 'planned_buy_date': str, 'quality': float}, ...]
        self.trades = []
        self.equity_curve = []
        
        # 统计
        self.stats = {
            'total_signals': 0,
            'executed_buys': 0,
            'executed_sells': 0,
            'skipped_no_data': 0,
            'skipped_insufficient_funds': 0
        }
    
    def reset(self):
        """重置回测状态"""
        self.cash = self.initial_capital
        self.positions = {}
        self.pending_orders = []
        self.trades = []
        self.equity_curve = []
        self.stats = {
            'total_signals': 0,
            'executed_buys': 0,
            'executed_sells': 0,
            'skipped_no_data': 0,
            'skipped_insufficient_funds': 0
        }
    
    def backtest_stock(self, stock_code: str, stock_name: str, stock_data: pd.DataFrame) -> List[Dict]:
        """
        对单只股票进行回测
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            stock_data: 股票数据DataFrame
            
        Returns:
            交易记录列表
        """
        if stock_data is None or len(stock_data) < (self.buy_delay + self.hold_days) + 10:
            return []
        
        try:
            # 运行策略获取信号
            result = qqe_trend_strategy(stock_data, strict_mode=self.strict_mode)
            signal_col = 'buy_signal_strict' if self.strict_mode else 'buy_signal'
            
            # 获取所有交易日列表
            dates = result.index.tolist()
            date_to_idx = {d: i for i, d in enumerate(dates)}
            
            stock_trades = []
            pending_buy = None  # 待执行的买入订单
            position = None     # 当前持仓
            
            for i, current_date in enumerate(dates):
                current_row = result.loc[current_date]
                
                # 1. 检查是否需要执行卖出（持有N天到期）
                if position is not None:
                    if current_date >= position['planned_sell_date']:
                        # 执行卖出
                        sell_price = current_row['open']  # 以开盘价卖出
                        sell_net = sell_price * (1 - self.slippage - self.commission)
                        
                        buy_cost = position['buy_cost']
                        profit_pct = (sell_net - buy_cost) / buy_cost * 100
                        hold_days = (current_date - position['buy_date']).days
                        
                        trade = {
                            'stock_code': stock_code,
                            'stock_name': stock_name,
                            'signal_date': position['signal_date'],
                            'buy_date': position['buy_date'],
                            'buy_price': position['buy_price'],
                            'buy_cost': buy_cost,
                            'sell_date': current_date,
                            'sell_price': sell_price,
                            'sell_net': sell_net,
                            'profit_pct': profit_pct,
                            'hold_days': hold_days,
                            'signal_quality': position['signal_quality'],
                            'buy_delay': self.buy_delay,
                            'hold_days': self.hold_days,
                            'exit_reason': 'time_exit'
                        }
                        stock_trades.append(trade)
                        position = None
                
                # 2. 检查是否需要执行买入（信号后第N天）
                if pending_buy is not None and current_date >= pending_buy['planned_buy_date']:
                    # 检查是否还有持仓（单股回测一次只持有一仓）
                    if position is None:
                        # 执行买入
                        buy_price = current_row['open']  # 以开盘价买入
                        buy_cost = buy_price * (1 + self.slippage + self.commission)
                        
                        # 计算可买入股数
                        position_value = self.initial_capital * self.position_size
                        shares = int(position_value / buy_cost / 100) * 100
                        
                        if shares >= 100:
                            # 计算计划卖出日期
                            sell_idx = i + self.hold_days
                            if sell_idx < len(dates):
                                planned_sell_date = dates[sell_idx]
                            else:
                                planned_sell_date = dates[-1]
                            
                            position = {
                                'shares': shares,
                                'buy_price': buy_price,
                                'buy_cost': buy_cost,
                                'buy_date': current_date,
                                'planned_sell_date': planned_sell_date,
                                'signal_date': pending_buy['signal_date'],
                                'signal_quality': pending_buy['signal_quality']
                            }
                    
                    pending_buy = None
                
                # 3. 检查是否有新的买入信号
                if position is None and pending_buy is None:
                    has_signal = bool(current_row[signal_col])
                    
                    if has_signal:
                        # 质量过滤
                        quality = current_row.get('signal_quality', 0) if self.strict_mode else 100
                        
                        if quality >= self.min_quality:
                            # 计算计划买入日期（第buy_delay个交易日）
                            buy_idx = i + self.buy_delay
                            if buy_idx < len(dates):
                                planned_buy_date = dates[buy_idx]
                                
                                pending_buy = {
                                    'signal_date': current_date,
                                    'planned_buy_date': planned_buy_date,
                                    'signal_quality': quality
                                }
                                self.stats['total_signals'] += 1
            
            # 如果最后还有持仓，以最后一天的收盘价平仓
            if position is not None:
                last_date = dates[-1]
                last_row = result.loc[last_date]
                
                sell_price = last_row['close']
                sell_net = sell_price * (1 - self.slippage - self.commission)
                
                buy_cost = position['buy_cost']
                profit_pct = (sell_net - buy_cost) / buy_cost * 100
                hold_days = (last_date - position['buy_date']).days
                
                trade = {
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'signal_date': position['signal_date'],
                    'buy_date': position['buy_date'],
                    'buy_price': position['buy_price'],
                    'buy_cost': buy_cost,
                    'sell_date': last_date,
                    'sell_price': sell_price,
                    'sell_net': sell_net,
                    'profit_pct': profit_pct,
                    'hold_days': hold_days,
                    'signal_quality': position['signal_quality'],
                    'buy_delay': self.buy_delay,
                    'hold_days': self.hold_days,
                    'exit_reason': 'open'
                }
                stock_trades.append(trade)
            
            return stock_trades
            
        except Exception as e:
            print(f"回测 {stock_code} 时出错: {e}")
            return []
    
    def calculate_metrics(self, trades: List[Dict]) -> Dict:
        """
        计算回测指标
        
        Args:
            trades: 交易记录列表
            
        Returns:
            指标字典
        """
        if not trades:
            return {
                'total_trades': 0,
                'win_count': 0,
                'loss_count': 0,
                'win_rate': 0,
                'avg_profit': 0,
                'total_return': 0,
                'max_profit': 0,
                'min_profit': 0,
                'avg_hold_days': 0
            }
        
        df = pd.DataFrame(trades)
        
        total_trades = len(df)
        profits = df['profit_pct'].values
        
        # 胜率
        win_count = len(df[df['profit_pct'] > 0])
        loss_count = total_trades - win_count
        win_rate = win_count / total_trades * 100 if total_trades > 0 else 0
        
        # 收益统计
        avg_profit = np.mean(profits)
        total_return = np.sum(profits)
        max_profit = np.max(profits)
        min_profit = np.min(profits)
        
        # 持有天数
        avg_hold_days = df['hold_days'].mean()
        
        # 盈亏比
        win_profits = df[df['profit_pct'] > 0]['profit_pct']
        loss_profits = df[df['profit_pct'] <= 0]['profit_pct']
        avg_win = win_profits.mean() if len(win_profits) > 0 else 0
        avg_loss = abs(loss_profits.mean()) if len(loss_profits) > 0 else 0
        profit_factor = avg_win / avg_loss if avg_loss != 0 else 0
        
        # 最大回撤（简化计算）
        equity_curve = 100 + np.cumsum(profits)
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = (equity_curve - running_max) / running_max * 100
        max_drawdown = np.min(drawdown)
        
        return {
            'total_trades': total_trades,
            'win_count': win_count,
            'loss_count': loss_count,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'total_return': total_return,
            'max_profit': max_profit,
            'min_profit': min_profit,
            'avg_hold_days': avg_hold_days,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown
        }


class StockDataLoader:
    """股票数据加载器"""
    CACHE_DIR = "data_cache"
    
    @staticmethod
    def _get_cache_path(code: str) -> str:
        """获取缓存文件路径"""
        import os
        if not os.path.exists(StockDataLoader.CACHE_DIR):
            os.makedirs(StockDataLoader.CACHE_DIR)
        today = datetime.now().strftime("%Y%m%d")
        return os.path.join(StockDataLoader.CACHE_DIR, f"{code}_{today}.csv")
    
    @staticmethod
    def get_stock_list(board_filter: Optional[str] = None, max_stocks: Optional[int] = None) -> List[Dict]:
        """获取股票列表"""
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
                    # 过滤ST、退市、指数、债券
                    if 'ST' not in name and '退' not in name and '指数' not in name and '债' not in name:
                        exchange = full_code.split('.')[0]
                        code_num = full_code.split('.')[-1]
                        
                        # 确保是6位股票代码
                        if len(code_num) != 6:
                            continue
                        
                        # 过滤上海交易所的指数
                        if exchange == 'sh' and (code_num.startswith('000') or code_num.startswith('999')):
                            continue
                        
                        is_chinext = code_num.startswith('300') or code_num.startswith('301')
                        is_star = code_num.startswith('688')
                        
                        # 板块筛选
                        if board_filter == 'chinext':
                            if not is_chinext:
                                continue
                        elif board_filter == 'star':
                            if not is_star:
                                continue
                        elif board_filter == 'chinext+star':
                            if not (is_chinext or is_star):
                                continue
                        elif board_filter == 'all':
                            if not (code_num.startswith('60') or code_num.startswith('00') or 
                                   code_num.startswith('30') or code_num.startswith('68')):
                                continue
                        elif board_filter and board_filter != 'all':
                            prefixes = board_filter.split(',')
                            if not any(code_num.startswith(p.strip()) for p in prefixes):
                                continue
                        
                        stock_list.append({'code': full_code, 'name': name})
        
        bs.logout()
        
        if max_stocks and max_stocks < len(stock_list):
            stock_list = stock_list[:max_stocks]
        
        return stock_list
    
    @staticmethod
    def get_stock_data(code: str, days: int = 250) -> Optional[pd.DataFrame]:
        """获取股票数据（带缓存）"""
        cache_path = StockDataLoader._get_cache_path(code)
        
        # 尝试从缓存读取
        import os
        if os.path.exists(cache_path):
            try:
                df = pd.read_csv(cache_path, index_col='date', parse_dates=['date'])
                return df
            except Exception:
                pass
        
        # 从服务器下载
        lg = bs.login()
        
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days * 1.5)).strftime("%Y-%m-%d")
        
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
        
        # 写入缓存
        try:
            df.to_csv(cache_path)
        except Exception:
            pass
        
        return df


def run_n_day_backtest(buy_delay: int = 3,
                       hold_days: int = 5,
                       board: str = 'chinext+star',
                       max_stocks: int = 100,
                       strict_mode: bool = True,
                       min_quality: int = 60,
                       history_days: int = 250,
                       initial_capital: float = 100000) -> Dict:
    """
    运行N天延迟回测
    
    Args:
        buy_delay: 买入延迟天数，信号出现后第buy_delay天买入
        hold_days: 持有天数，买入后持有hold_days天卖出
        board: 板块筛选
        max_stocks: 最大股票数量
        strict_mode: 严格模式
        min_quality: 最低信号质量
        history_days: 历史数据天数
        initial_capital: 初始资金
        
    Returns:
        回测结果字典
    """
    print(f"\n{'='*80}")
    print(f"N天延迟回测 - 买入延迟{buy_delay}天, 持有{hold_days}天")
    print(f"{'='*80}")
    print(f"板块: {board}")
    print(f"股票池: {max_stocks}只")
    print(f"模式: {'严格模式' if strict_mode else '标准模式'}")
    print(f"最低质量: {min_quality}")
    print(f"历史数据: {history_days}天")
    
    # 获取股票列表
    print("\n[1/3] 获取股票列表...")
    stock_list = StockDataLoader.get_stock_list(board_filter=board, max_stocks=max_stocks)
    print(f"共获取 {len(stock_list)} 只股票")
    
    # 创建回测引擎
    backtester = NDayBacktester(
        buy_delay=buy_delay,
        hold_days=hold_days,
        initial_capital=initial_capital,
        strict_mode=strict_mode,
        min_quality=min_quality
    )
    
    # 逐个股票回测
    print("\n[2/3] 执行回测...")
    all_trades = []
    
    for i, stock in enumerate(stock_list):
        if (i + 1) % 10 == 0 or i == 0:
            print(f"\r进度: {i+1}/{len(stock_list)}", end='', flush=True)
        
        try:
            # 获取股票数据
            df = StockDataLoader.get_stock_data(stock['code'], days=history_days)
            
            if df is not None and len(df) >= (buy_delay + hold_days) + 10:
                # 执行回测
                trades = backtester.backtest_stock(stock['code'], stock['name'], df)
                all_trades.extend(trades)
        except Exception as e:
            continue
    
    print(f"\n\n[3/3] 计算指标...")
    
    # 计算指标
    metrics = backtester.calculate_metrics(all_trades)
    
    # 打印结果
    print(f"\n{'='*80}")
    print(f"回测结果 (买入延迟{buy_delay}天, 持有{hold_days}天)")
    print(f"{'='*80}")
    print(f"总交易次数: {metrics['total_trades']}")
    print(f"盈利次数: {metrics['win_count']}")
    print(f"亏损次数: {metrics['loss_count']}")
    print(f"胜率: {metrics['win_rate']:.2f}%")
    print(f"平均收益: {metrics['avg_profit']:.2f}%")
    print(f"总收益: {metrics['total_return']:.2f}%")
    print(f"最大单笔盈利: {metrics['max_profit']:.2f}%")
    print(f"最大单笔亏损: {metrics['min_profit']:.2f}%")
    print(f"平均持有天数: {metrics['avg_hold_days']:.1f}天")
    print(f"盈亏比: {metrics['profit_factor']:.2f}")
    print(f"最大回撤: {metrics['max_drawdown']:.2f}%")
    print(f"{'='*80}\n")
    
    return {
        'buy_delay': buy_delay,
        'hold_days': hold_days,
        'metrics': metrics,
        'trades': all_trades,
        'stock_count': len(stock_list)
    }


def compare_n_days(buy_delay_list: List[int] = [1, 3, 5],
                   hold_days_list: List[int] = [5, 10, 15],
                   board: str = 'chinext+star',
                   max_stocks: int = 100,
                   strict_mode: bool = True,
                   min_quality: int = 60,
                   history_days: int = 250) -> pd.DataFrame:
    """
    对比不同参数组合的回测效果（网格搜索）
    
    Args:
        buy_delay_list: 买入延迟天数列表
        hold_days_list: 持有天数列表
        board: 板块筛选
        max_stocks: 最大股票数量
        strict_mode: 严格模式
        min_quality: 最低信号质量
        history_days: 历史数据天数
        
    Returns:
        对比结果DataFrame
    """
    print(f"\n{'='*80}")
    print("参数组合对比回测（网格搜索）")
    print(f"{'='*80}")
    print(f"买入延迟天数: {buy_delay_list}")
    print(f"持有天数: {hold_days_list}")
    print(f"总组合数: {len(buy_delay_list) * len(hold_days_list)}")
    print(f"股票池: {max_stocks}只")
    print(f"{'='*80}\n")
    
    results = []
    total_combinations = len(buy_delay_list) * len(hold_days_list)
    current = 0
    
    for buy_delay in buy_delay_list:
        for hold_days in hold_days_list:
            current += 1
            print(f"\n[{current}/{total_combinations}] 测试组合: 买入延迟{buy_delay}天, 持有{hold_days}天")
            
            result = run_n_day_backtest(
                buy_delay=buy_delay,
                hold_days=hold_days,
                board=board,
                max_stocks=max_stocks,
                strict_mode=strict_mode,
                min_quality=min_quality,
                history_days=history_days
            )
            
            metrics = result['metrics']
            results.append({
                '买入延迟': buy_delay,
                '持有天数': hold_days,
                '交易次数': metrics['total_trades'],
                '胜率(%)': round(metrics['win_rate'], 2),
                '平均收益(%)': round(metrics['avg_profit'], 2),
                '总收益(%)': round(metrics['total_return'], 2),
                '最大盈利(%)': round(metrics['max_profit'], 2),
                '最大亏损(%)': round(metrics['min_profit'], 2),
                '盈亏比': round(metrics['profit_factor'], 2),
                '最大回撤(%)': round(metrics['max_drawdown'], 2),
                '平均持有(天)': round(metrics['avg_hold_days'], 1)
            })
    
    # 创建对比表格
    df_comparison = pd.DataFrame(results)
    
    print("\n" + "="*80)
    print("参数组合对比结果")
    print("="*80)
    print(df_comparison.to_string(index=False))
    print("="*80)
    
    # 找出最佳组合
    best_by_return = df_comparison.loc[df_comparison['总收益(%)'].idxmax()]
    best_by_winrate = df_comparison.loc[df_comparison['胜率(%)'].idxmax()]
    best_by_factor = df_comparison.loc[df_comparison['盈亏比'].idxmax()]
    
    print("\n最佳表现:")
    print(f"  最高总收益: 买入延迟{int(best_by_return['买入延迟'])}天, 持有{int(best_by_return['持有天数'])}天 ({best_by_return['总收益(%)']}%)")
    print(f"  最高胜率: 买入延迟{int(best_by_winrate['买入延迟'])}天, 持有{int(best_by_winrate['持有天数'])}天 ({best_by_winrate['胜率(%)']}%)")
    print(f"  最佳盈亏比: 买入延迟{int(best_by_factor['买入延迟'])}天, 持有{int(best_by_factor['持有天数'])}天 ({best_by_factor['盈亏比']})")
    
    return df_comparison


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='N天延迟回测系统')
    parser.add_argument('--buy-delay', type=int, default=3, help='买入延迟天数，信号出现后第N天买入（默认3）')
    parser.add_argument('--hold-days', type=int, default=5, help='持有天数，买入后持有N天卖出（默认5）')
    parser.add_argument('--buy-delay-list', type=int, nargs='+', help='买入延迟天数列表（用于对比模式）')
    parser.add_argument('--hold-days-list', type=int, nargs='+', help='持有天数列表（用于对比模式）')
    parser.add_argument('--board', type=str, default='chinext+star', help='板块筛选')
    parser.add_argument('--max-stocks', type=int, default=100, help='最大股票数量')
    parser.add_argument('--strict', action='store_true', help='使用严格模式')
    parser.add_argument('--min-quality', type=int, default=60, help='最低信号质量')
    parser.add_argument('--history-days', type=int, default=250, help='历史数据天数')
    parser.add_argument('--compare', action='store_true', help='对比模式（网格搜索测试多个参数组合）')
    parser.add_argument('--output', type=str, help='输出结果到JSON文件')
    
    args = parser.parse_args()
    
    if args.compare or args.buy_delay_list or args.hold_days_list:
        # 对比模式（网格搜索）
        buy_delay_list = args.buy_delay_list if args.buy_delay_list else [1, 3, 5]
        hold_days_list = args.hold_days_list if args.hold_days_list else [5, 10, 15]
        results_df = compare_n_days(
            buy_delay_list=buy_delay_list,
            hold_days_list=hold_days_list,
            board=args.board,
            max_stocks=args.max_stocks,
            strict_mode=args.strict,
            min_quality=args.min_quality,
            history_days=args.history_days
        )
        
        if args.output:
            results_df.to_json(args.output, orient='records', force_ascii=False, indent=2)
            print(f"\n结果已保存到: {args.output}")
    else:
        # 单参数组合模式
        result = run_n_day_backtest(
            buy_delay=args.buy_delay,
            hold_days=args.hold_days,
            board=args.board,
            max_stocks=args.max_stocks,
            strict_mode=args.strict,
            min_quality=args.min_quality,
            history_days=args.history_days
        )
        
        if args.output:
            # 保存详细结果
            output_data = {
                'config': {
                    'buy_delay': args.buy_delay,
                    'hold_days': args.hold_days,
                    'board': args.board,
                    'max_stocks': args.max_stocks,
                    'strict_mode': args.strict,
                    'min_quality': args.min_quality
                },
                'metrics': result['metrics'],
                'trades_count': len(result['trades'])
            }
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"\n结果已保存到: {args.output}")


if __name__ == '__main__':
    main()
