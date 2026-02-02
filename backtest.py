"""
QQE趋势策略回测系统
用于评估不同质量阈值下的策略表现
"""
import baostock as bs
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from qqe_trend_strategy import qqe_trend_strategy
import argparse
import time
import random


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, initial_capital=100000, commission=0.0003, 
                 slippage=0.001, position_size=1.0, stop_loss=0.10):
        """
        初始化回测引擎
        
        Args:
            initial_capital: 初始资金
            commission: 手续费率（双向）
            slippage: 滑点
            position_size: 仓位比例（0-1）
            stop_loss: 止损比例（如 0.10 表示 -10%）
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.position_size = position_size
        self.stop_loss = stop_loss
        
        # 回测结果
        self.trades = []
        self.equity_curve = []
    
    def backtest_stock(self, stock_code, stock_name, stock_data, 
                      strict_mode=True, min_quality=60):
        """
        回测单只股票
        
        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            stock_data: 股票数据
            strict_mode: 是否使用严格模式
            min_quality: 最低质量分数
            
        Returns:
            trades: 交易记录列表
        """
        try:
            # 运行策略
            result = qqe_trend_strategy(stock_data, strict_mode=strict_mode)
            
            # 获取信号
            signal_column = 'buy_signal_strict' if strict_mode else 'buy_signal'
            buy_signals = result[result[signal_column] == True]
            sell_signals = result[result['sell_signal'] == True]
            
            # 质量过滤
            if strict_mode and min_quality > 0:
                buy_signals = buy_signals[buy_signals['signal_quality'] >= min_quality]
            
            # 模拟交易 - 修正后的逻辑：确保同一时间只持有一个仓位
            stock_trades = []
            current_position = None  # 记录当前持仓
            
            # 合并所有日期，按时间顺序处理
            for date in result.index:
                # 如果当前有持仓，检查是否需要平仓
                if current_position is not None:
                    buy_date = current_position['buy_date']
                    buy_cost = current_position['buy_cost']
                    
                    # 获取当前行数据
                    row = result.loc[date]
                    
                    # 计算当前收益率（用最低价检查止损）
                    current_price = row['low']
                    current_return = (current_price - buy_cost) / buy_cost
                    
                    # 检查止损
                    if current_return <= -self.stop_loss:
                        sell_date = date
                        sell_price = current_price
                        exit_reason = 'stop_loss'
                        status = 'closed'
                        
                        # 平仓
                        sell_net = sell_price * (1 - self.slippage - self.commission)
                        profit_pct = (sell_net - buy_cost) / buy_cost * 100
                        holding_days = (sell_date - buy_date).days
                        
                        trade = {
                            'stock_code': stock_code,
                            'stock_name': stock_name,
                            'buy_date': buy_date,
                            'buy_price': current_position['buy_price'],
                            'buy_cost': buy_cost,
                            'sell_date': sell_date,
                            'sell_price': sell_price,
                            'sell_net': sell_net,
                            'profit_pct': profit_pct,
                            'holding_days': holding_days,
                            'signal_quality': current_position['signal_quality'],
                            'exit_reason': exit_reason,
                            'status': status
                        }
                        
                        stock_trades.append(trade)
                        current_position = None  # 清空持仓
                        continue
                    
                    # 检查卖出信号
                    if date in sell_signals.index:
                        sell_date = date
                        sell_price = row['open']
                        exit_reason = 'signal'
                        status = 'closed'
                        
                        # 平仓
                        sell_net = sell_price * (1 - self.slippage - self.commission)
                        profit_pct = (sell_net - buy_cost) / buy_cost * 100
                        holding_days = (sell_date - buy_date).days
                        
                        trade = {
                            'stock_code': stock_code,
                            'stock_name': stock_name,
                            'buy_date': buy_date,
                            'buy_price': current_position['buy_price'],
                            'buy_cost': buy_cost,
                            'sell_date': sell_date,
                            'sell_price': sell_price,
                            'sell_net': sell_net,
                            'profit_pct': profit_pct,
                            'holding_days': holding_days,
                            'signal_quality': current_position['signal_quality'],
                            'exit_reason': exit_reason,
                            'status': status
                        }
                        
                        stock_trades.append(trade)
                        current_position = None  # 清空持仓
                        continue
                
                # 如果当前没有持仓，检查是否有买入信号
                if current_position is None and date in buy_signals.index:
                    buy_price = buy_signals.loc[date]['open']
                    signal_quality = buy_signals.loc[date].get('signal_quality', 0) if strict_mode else 0
                    buy_cost = buy_price * (1 + self.slippage + self.commission)
                    
                    # 建立持仓
                    current_position = {
                        'buy_date': date,
                        'buy_price': buy_price,
                        'buy_cost': buy_cost,
                        'signal_quality': signal_quality
                    }
            
            # 如果最后还有持仓，以最后一天的收盘价平仓
            if current_position is not None:
                buy_date = current_position['buy_date']
                buy_cost = current_position['buy_cost']
                sell_date = result.index[-1]
                sell_price = result.iloc[-1]['close']
                exit_reason = 'open'
                status = 'open'
                
                sell_net = sell_price * (1 - self.slippage - self.commission)
                profit_pct = (sell_net - buy_cost) / buy_cost * 100
                holding_days = (sell_date - buy_date).days
                
                trade = {
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'buy_date': buy_date,
                    'buy_price': current_position['buy_price'],
                    'buy_cost': buy_cost,
                    'sell_date': sell_date,
                    'sell_price': sell_price,
                    'sell_net': sell_net,
                    'profit_pct': profit_pct,
                    'holding_days': holding_days,
                    'signal_quality': current_position['signal_quality'],
                    'exit_reason': exit_reason,
                    'status': status
                }
                
                stock_trades.append(trade)
            
            return stock_trades
            
        except Exception as e:
            return []
    
    def calculate_metrics(self, trades):
        """
        计算回测指标
        
        Args:
            trades: 交易记录列表
            
        Returns:
            metrics: 指标字典
        """
        if len(trades) == 0:
            return None
        
        df = pd.DataFrame(trades)
        
        # 基本统计
        total_trades = len(df)
        closed_trades = df[df['status'] == 'closed']
        
        # 止损统计
        if 'exit_reason' in df.columns:
            stop_loss_trades = df[df['exit_reason'] == 'stop_loss']
            stop_loss_count = len(stop_loss_trades)
            stop_loss_rate = stop_loss_count / total_trades * 100 if total_trades > 0 else 0
            signal_exit_count = len(df[df['exit_reason'] == 'signal'])
        else:
            stop_loss_count = 0
            stop_loss_rate = 0
            signal_exit_count = 0
        
        # 收益统计
        profits = df['profit_pct'].values
        avg_profit = np.mean(profits)
        median_profit = np.median(profits)
        max_profit = np.max(profits)
        min_profit = np.min(profits)
        
        # 胜率统计
        win_trades = df[df['profit_pct'] > 0]
        win_count = len(win_trades)
        loss_count = total_trades - win_count
        win_rate = win_count / total_trades * 100 if total_trades > 0 else 0
        
        # 盈亏比
        avg_win = win_trades['profit_pct'].mean() if len(win_trades) > 0 else 0
        loss_trades = df[df['profit_pct'] <= 0]
        avg_loss = abs(loss_trades['profit_pct'].mean()) if len(loss_trades) > 0 else 0
        profit_factor = avg_win / avg_loss if avg_loss != 0 else 0
        
        # 持有期统计
        avg_holding = df['holding_days'].mean()
        
        # 质量统计
        if 'signal_quality' in df.columns and df['signal_quality'].max() > 0:
            avg_quality = df['signal_quality'].mean()
        else:
            avg_quality = 0
        
        # 累计收益
        cumulative_return = ((1 + df['profit_pct'] / 100).prod() - 1) * 100
        
        # 最大回撤
        cumulative_returns = (1 + df['profit_pct'] / 100).cumprod()
        running_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - running_max) / running_max * 100
        max_drawdown = drawdown.min()
        
        # 夏普比率（简化版，假设无风险利率为0）
        sharpe_ratio = avg_profit / df['profit_pct'].std() if df['profit_pct'].std() > 0 else 0
        
        metrics = {
            'total_trades': total_trades,
            'closed_trades': len(closed_trades),
            'win_count': win_count,
            'loss_count': loss_count,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'median_profit': median_profit,
            'max_profit': max_profit,
            'min_profit': min_profit,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'avg_holding': avg_holding,
            'avg_quality': avg_quality,
            'cumulative_return': cumulative_return,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'stop_loss_count': stop_loss_count,
            'stop_loss_rate': stop_loss_rate,
            'signal_exit_count': signal_exit_count
        }
        
        return metrics


class StockDataLoader:
    """股票数据加载器"""
    
    @staticmethod
    def get_stock_list(board_filter=None, max_stocks=None):
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
                    # 过滤ST和退市股票
                    if 'ST' not in name and '退' not in name:
                        # 板块筛选
                        code_num = full_code.split('.')[-1]
                        
                        is_chinext = code_num.startswith('300') or code_num.startswith('301')
                        is_star = code_num.startswith('688')
                        
                        if board_filter == 'chinext' and not is_chinext:
                            continue
                        elif board_filter == 'star' and not is_star:
                            continue
                        elif board_filter == 'chinext+star' and not (is_chinext or is_star):
                            continue
                        
                        stock_list.append({'code': full_code, 'name': name})
        
        bs.logout()
        
        if max_stocks and max_stocks < len(stock_list):
            stock_list = stock_list[:max_stocks]
        
        return stock_list
    
    @staticmethod
    def get_stock_data(code, days=250):
        """获取股票数据"""
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


def run_backtest(board='chinext+star', max_stocks=100, quality_thresholds=None,
                strict_mode=True, history_days=250, stop_loss=0.10, delay=0.1):
    """
    运行回测
    
    Args:
        board: 板块筛选
        max_stocks: 最大股票数量
        quality_thresholds: 质量阈值列表
        strict_mode: 是否使用严格模式
        history_days: 历史数据天数
        stop_loss: 止损比例（如 0.10 表示 -10%）
        delay: 请求间隔
    """
    print("=" * 100)
    print("QQE趋势策略回测系统")
    print("=" * 100)
    print(f"板块: {board}")
    print(f"股票数量: {max_stocks}")
    print(f"模式: {'严格模式' if strict_mode else '标准模式'}")
    print(f"历史数据: {history_days}天")
    print(f"止损设置: {stop_loss * 100:.0f}%")
    print(f"质量阈值: {quality_thresholds}")
    print("=" * 100)
    
    # 默认质量阈值
    if quality_thresholds is None:
        quality_thresholds = [0, 50, 60, 70, 80] if strict_mode else [0]
    
    # 获取股票列表
    print("\n正在获取股票列表...")
    stock_list = StockDataLoader.get_stock_list(board_filter=board, max_stocks=max_stocks)
    print(f"共获取 {len(stock_list)} 只股票")
    
    # 对每个质量阈值进行回测
    results = {}
    
    for min_quality in quality_thresholds:
        print(f"\n{'=' * 100}")
        print(f"开始回测 - 质量阈值: {min_quality}分")
        print(f"{'=' * 100}")
        
        engine = BacktestEngine(stop_loss=stop_loss)
        all_trades = []
        
        for i, stock in enumerate(stock_list, 1):
            try:
                code = stock['code']
                name = stock['name']
                
                print(f"\r进度: {i}/{len(stock_list)} - {code} {name}  ", end='', flush=True)
                
                # 获取数据
                stock_data = StockDataLoader.get_stock_data(code, days=history_days)
                
                if stock_data is None or len(stock_data) < 60:
                    continue
                
                # 回测
                trades = engine.backtest_stock(code, name, stock_data, 
                                              strict_mode=strict_mode, 
                                              min_quality=min_quality)
                
                all_trades.extend(trades)
                
                time.sleep(delay)
                
            except Exception as e:
                continue
        
        print()
        
        # 计算指标
        if len(all_trades) > 0:
            metrics = engine.calculate_metrics(all_trades)
            results[min_quality] = {
                'metrics': metrics,
                'trades': all_trades
            }
            
            # 显示结果
            print(f"\n{'=' * 100}")
            print(f"回测结果 - 质量阈值: {min_quality}分")
            print(f"{'=' * 100}")
            print(f"总交易次数: {metrics['total_trades']}")
            print(f"已平仓交易: {metrics['closed_trades']}")
            print(f"胜率: {metrics['win_rate']:.2f}%")
            print(f"平均收益: {metrics['avg_profit']:.2f}%")
            print(f"中位数收益: {metrics['median_profit']:.2f}%")
            print(f"最大收益: {metrics['max_profit']:.2f}%")
            print(f"最大亏损: {metrics['min_profit']:.2f}%")
            print(f"平均盈利: {metrics['avg_win']:.2f}%")
            print(f"平均亏损: {metrics['avg_loss']:.2f}%")
            print(f"盈亏比: {metrics['profit_factor']:.2f}")
            print(f"平均持有天数: {metrics['avg_holding']:.1f}")
            print(f"累计收益: {metrics['cumulative_return']:.2f}%")
            print(f"最大回撤: {metrics['max_drawdown']:.2f}%")
            print(f"夏普比率: {metrics['sharpe_ratio']:.2f}")
            if metrics['avg_quality'] > 0:
                print(f"平均信号质量: {metrics['avg_quality']:.1f}分")
            print(f"\n退出方式统计:")
            print(f"  止损退出: {metrics['stop_loss_count']}次 ({metrics['stop_loss_rate']:.1f}%)")
            print(f"  信号退出: {metrics['signal_exit_count']}次 ({metrics['signal_exit_count']/metrics['total_trades']*100:.1f}%)")
            print(f"  持有中: {metrics['total_trades']-metrics['stop_loss_count']-metrics['signal_exit_count']}次")
        else:
            print(f"\n质量阈值 {min_quality}分 没有产生任何交易")
    
    # 对比分析
    print(f"\n\n{'=' * 100}")
    print("不同质量阈值对比分析")
    print(f"{'=' * 100}")
    print(f"{'质量阈值':<10}{'交易次数':<10}{'胜率%':<10}{'平均收益%':<12}{'累计收益%':<12}{'最大回撤%':<12}{'止损率%':<10}{'盈亏比':<10}{'夏普比率':<10}")
    print("-" * 100)
    
    for min_quality in sorted(results.keys()):
        m = results[min_quality]['metrics']
        print(f"{min_quality:<10}{m['total_trades']:<10}{m['win_rate']:<10.2f}{m['avg_profit']:<12.2f}{m['cumulative_return']:<12.2f}{m['max_drawdown']:<12.2f}{m['stop_loss_rate']:<10.2f}{m['profit_factor']:<10.2f}{m['sharpe_ratio']:<10.2f}")
    
    print("=" * 100)
    
    # 保存详细结果
    save_results(results, board, strict_mode)
    
    return results


def save_results(results, board, strict_mode):
    """保存回测结果到CSV文件"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode = "strict" if strict_mode else "standard"
    
    # 保存汇总指标
    summary_data = []
    for min_quality, result in results.items():
        m = result['metrics']
        summary_data.append({
            '质量阈值': min_quality,
            '交易次数': m['total_trades'],
            '已平仓': m['closed_trades'],
            '胜率%': round(m['win_rate'], 2),
            '平均收益%': round(m['avg_profit'], 2),
            '中位数收益%': round(m['median_profit'], 2),
            '最大收益%': round(m['max_profit'], 2),
            '最大亏损%': round(m['min_profit'], 2),
            '平均盈利%': round(m['avg_win'], 2),
            '平均亏损%': round(m['avg_loss'], 2),
            '盈亏比': round(m['profit_factor'], 2),
            '平均持有天数': round(m['avg_holding'], 1),
            '累计收益%': round(m['cumulative_return'], 2),
            '最大回撤%': round(m['max_drawdown'], 2),
            '夏普比率': round(m['sharpe_ratio'], 2),
            '平均质量': round(m['avg_quality'], 1) if m['avg_quality'] > 0 else 0,
            '止损次数': m['stop_loss_count'],
            '止损率%': round(m['stop_loss_rate'], 2),
            '信号退出次数': m['signal_exit_count']
        })
    
    summary_df = pd.DataFrame(summary_data)
    summary_file = f"backtest_summary_{board}_{mode}_{timestamp}.csv"
    summary_df.to_csv(summary_file, index=False, encoding='utf-8-sig')
    print(f"\n汇总结果已保存到: {summary_file}")
    
    # 保存所有交易详情
    for min_quality, result in results.items():
        trades_df = pd.DataFrame(result['trades'])
        if len(trades_df) > 0:
            trades_df['buy_date'] = trades_df['buy_date'].astype(str)
            trades_df['sell_date'] = trades_df['sell_date'].astype(str)
            
            trades_file = f"backtest_trades_{board}_{mode}_q{min_quality}_{timestamp}.csv"
            trades_df.to_csv(trades_file, index=False, encoding='utf-8-sig')
            print(f"质量阈值{min_quality}的交易详情已保存到: {trades_file}")


def main():
    parser = argparse.ArgumentParser(description='QQE趋势策略回测系统')
    parser.add_argument('--board', type=str, default='chinext+star',
                        choices=['chinext', 'star', 'chinext+star', 'all'],
                        help='板块筛选')
    parser.add_argument('--max-stocks', type=int, default=100,
                        help='最大股票数量')
    parser.add_argument('--quality-thresholds', type=str, default='0,50,60,70,80',
                        help='质量阈值列表，逗号分隔，如: 0,50,60,70,80')
    parser.add_argument('--no-strict', action='store_true',
                        help='使用标准模式（默认使用严格模式）')
    parser.add_argument('--history-days', type=int, default=250,
                        help='历史数据天数')
    parser.add_argument('--stop-loss', type=float, default=0.10,
                        help='止损比例，如 0.10 表示 -10%%，默认0.10')
    parser.add_argument('--delay', type=float, default=0.1,
                        help='请求间隔时间(秒)')
    
    args = parser.parse_args()
    
    # 解析质量阈值
    quality_thresholds = [int(x.strip()) for x in args.quality_thresholds.split(',')]
    
    strict_mode = not args.no_strict
    
    # 运行回测
    run_backtest(
        board=args.board,
        max_stocks=args.max_stocks,
        quality_thresholds=quality_thresholds,
        strict_mode=strict_mode,
        history_days=args.history_days,
        stop_loss=args.stop_loss,
        delay=args.delay
    )


if __name__ == "__main__":
    main()
