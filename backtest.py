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


class PortfolioBacktester:
    """组合回测引擎（资金池模式）"""
    def __init__(self, initial_capital=100000, max_stocks=5, commission=0.0003, slippage=0.001,
                 stop_loss=0.10, take_profit=0.20, strict_mode=True):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.max_stocks = max_stocks
        self.commission = commission
        self.slippage = slippage
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.strict_mode = strict_mode
        
        self.positions = {}  # {code: {cost, shares, buy_date, ...}}
        self.trades = []
        self.equity_curve = []  # [{date, equity, cash, positions_val}]
        self.daily_logs = []

    def run(self, stock_list, history_days=250, min_quality=60):
        """执行组合回测"""
        print(f"\n正在初始化组合回测 (资金: {self.initial_capital}, 最大持仓: {self.max_stocks})...")
        
        # 1. 预加载数据并计算信号
        # 为了按日回测，我们需要将所有股票的数据对齐到同一时间轴
        # 结构: date -> {code: {open, high, low, close, buy_signal, sell_signal, quality}}
        market_data = {} 
        all_dates = set()
        
        print("正在预计算策略信号...")
        valid_stocks = 0
        for i, stock in enumerate(stock_list):
            print(f"\r处理进度: {i+1}/{len(stock_list)}", end='', flush=True)
            try:
                df = StockDataLoader.get_stock_data(stock['code'], days=history_days)
                if df is None or len(df) < 60:
                    continue
                
                # 计算策略
                result = qqe_trend_strategy(df, strict_mode=self.strict_mode)
                
                # 提取关键数据存入内存
                signal_col = 'buy_signal_strict' if self.strict_mode else 'buy_signal'
                
                for date, row in result.iterrows():
                    d_str = date.strftime('%Y-%m-%d')
                    all_dates.add(d_str)
                    
                    if d_str not in market_data:
                        market_data[d_str] = {}
                    
                    market_data[d_str][stock['code']] = {
                        'name': stock['name'],
                        'open': row['open'],
                        'high': row['high'],
                        'low': row['low'],
                        'close': row['close'],
                        'buy_signal': row[signal_col],
                        'sell_signal': row['sell_signal'],
                        'quality': row.get('signal_quality', 0) if self.strict_mode else 0
                    }
                valid_stocks += 1
            except Exception:
                continue
                
        print(f"\n预计算完成，有效股票: {valid_stocks}只，开始按日撮合...")
        
        # 2. 按日时间步进
        sorted_dates = sorted(list(all_dates))
        
        for date_str in sorted_dates:
            daily_market = market_data.get(date_str, {})
            self._process_daily_step(date_str, daily_market, min_quality)
            
        return self.equity_curve, self.trades

    def run_with_cache(self, market_data_cache, min_quality=60):
        """
        使用预缓存的数据执行组合回测
        """
        # 1. 转换数据格式
        market_data = {} 
        all_dates = set()
        
        signal_col = 'buy_signal_strict' if self.strict_mode else 'buy_signal'
        
        total_buy_signals = 0 # 调试统计
        
        for code, item in market_data_cache.items():
            name = item['name']
            result = item['data']
            
            for date, row in result.iterrows():
                d_str = date.strftime('%Y-%m-%d')
                all_dates.add(d_str)
                
                if d_str not in market_data:
                    market_data[d_str] = {}
                
                # 检查是否包含必需列
                has_signal = False
                if signal_col in row:
                    has_signal = bool(row[signal_col])
                
                if has_signal:
                    total_buy_signals += 1
                
                market_data[d_str][code] = {
                    'name': name,
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'buy_signal': has_signal,
                    'sell_signal': bool(row['sell_signal']) if 'sell_signal' in row else False,
                    'quality': row.get('signal_quality', 0) if self.strict_mode else 0
                }
        
        print(f"DEBUG: 数据转换完成，共发现 {total_buy_signals} 个原始买入信号 (严格模式: {self.strict_mode}, 信号列: {signal_col})")
        
        if total_buy_signals == 0:
            print("警告: 没有任何股票产生买入信号，请检查策略逻辑或严格模式设置！")
        
        # 2. 按日时间步进
        sorted_dates = sorted(list(all_dates))
        
        for date_str in sorted_dates:
            daily_market = market_data.get(date_str, {})
            self._process_daily_step(date_str, daily_market, min_quality)
            
        return self.equity_curve, self.trades

    def _process_daily_step(self, date_str, daily_market, min_quality):
        """处理每一天的交易逻辑"""
        # ... (卖出逻辑不变，省略以节省空间) ...
        # --- 1. 更新持仓市值 & 检查卖出 ---
        positions_to_close = [] 
        current_positions_value = 0
        
        for code, pos in self.positions.items():
            if code not in daily_market:
                current_positions_value += pos['shares'] * pos['last_close']
                continue
            data = daily_market[code]
            pos['last_close'] = data['close']
            
            action = None
            sell_price = 0
            reason = ""
            buy_cost = pos['cost_price']
            
            if not pos.get('has_taken_profit') and self.take_profit > 0:
                tp_price = buy_cost * (1 + self.take_profit)
                if data['high'] >= tp_price:
                    exec_price = max(data['open'], tp_price)
                    self._execute_sell(date_str, code, data['name'], exec_price, is_partial=True, reason="止盈50%")
                    pos['has_taken_profit'] = True
                    pos['use_breakeven'] = True
            
            if pos.get('use_breakeven'):
                stop_price = buy_cost * (1.01) 
            else:
                stop_price = buy_cost * (1 - self.stop_loss)
                
            if data['low'] <= stop_price:
                action = "SELL"
                reason = "止损" if not pos.get('use_breakeven') else "保本离场"
                if data['open'] < stop_price:
                    sell_price = data['open']
                else:
                    sell_price = stop_price
            elif data['sell_signal']:
                action = "SELL"
                reason = "卖出信号"
                sell_price = data['close'] 

            if action == "SELL":
                positions_to_close.append((code, sell_price, reason))
            else:
                current_positions_value += pos['shares'] * data['close']
        
        for code, price, reason in positions_to_close:
            if code in self.positions:
                name = self.positions[code]['name']
                self._execute_sell(date_str, code, name, price, is_partial=False, reason=reason)

        # --- 2. 检查买入 ---
        candidates = []
        # DEBUG: 检查当天是否有信号但没被选中
        daily_signals = 0
        filtered_by_quality = 0
        
        if len(self.positions) < self.max_stocks:
            for code, data in daily_market.items():
                if data['buy_signal']:
                    daily_signals += 1
                    if code in self.positions:
                        pass
                    elif data['quality'] >= min_quality:
                        candidates.append({
                            'code': code, 
                            'name': data['name'],
                            'price': data['close'],
                            'quality': data['quality']
                        })
                    else:
                        filtered_by_quality += 1
            
            # DEBUG: 首次买入信号时打印诊断信息
            if daily_signals > 0 and len(self.trades) == 0:
                print(f"\n[调试] {date_str}: 发现 {daily_signals} 个买入信号, 通过质量筛选 {len(candidates)} 个 (最低质量={min_quality}), 被质量过滤 {filtered_by_quality} 个")
                if len(candidates) > 0:
                    print(f"  候选质量范围: {min([c['quality'] for c in candidates]):.1f} - {max([c['quality'] for c in candidates]):.1f}")
            
            # 按质量排序
            candidates.sort(key=lambda x: x['quality'], reverse=True)
            
            # 尝试买入
            first_attempt = len(self.trades) == 0 and len(candidates) > 0
            for item in candidates:
                if len(self.positions) >= self.max_stocks:
                    break
                    
                # 资金分配模型
                target_pos_size = self.initial_capital / self.max_stocks
                available_cash = min(self.cash, target_pos_size)
                
                # 预留手续费
                cost_with_fee = item['price'] * (1 + self.commission)
                
                # DEBUG: 首次尝试买入时打印详细信息
                if first_attempt:
                    print(f"  [首次尝试] {item['code']} 价格={item['price']:.2f}, 可用资金={available_cash:.2f}, 需要最少={cost_with_fee * 100:.2f}")
                    first_attempt = False
                
                # 修复：防止资金不足导致无法买入 (至少买100股)
                if available_cash < cost_with_fee * 100:
                    continue
                    
                max_shares = int(available_cash / cost_with_fee) // 100 * 100
                
                if max_shares >= 100:
                    self._execute_buy(date_str, item['code'], item['name'], item['price'], max_shares, item['quality'])
                else:
                    pass
        
        # --- 3. 记录当日权益 ---
        total_mkt_value = 0
        for pos in self.positions.values():
            total_mkt_value += pos['shares'] * pos['last_close']
            
        total_equity = self.cash + total_mkt_value
        self.equity_curve.append({
            'date': date_str,
            'equity': total_equity,
            'cash': self.cash,
            'market_value': total_mkt_value,
            'position_count': len(self.positions)
        })

    def _execute_buy(self, date, code, name, price, shares, quality):
        cost = shares * price
        fee = max(5, cost * self.commission)
        total_out = cost + fee
        
        self.cash -= total_out
        self.positions[code] = {
            'name': name,
            'shares': shares,
            'cost_price': price,
            'buy_date': date,
            'last_close': price,
            'quality': quality,
            'has_taken_profit': False,
            'use_breakeven': False
        }
        self.trades.append({
            'date': date, 'code': code, 'name': name, 'action': 'BUY',
            'price': price, 'shares': shares, 'amount': -total_out, 'reason': f"Q:{quality:.1f}"
        })

    def _execute_sell(self, date, code, name, price, is_partial, reason):
        pos = self.positions[code]
        
        shares_to_sell = pos['shares']
        if is_partial:
            shares_to_sell = shares_to_sell // 2 // 100 * 100 # 卖一半
            if shares_to_sell == 0: return # 股数太少无法分批，略过
            
        income = shares_to_sell * price
        fee = max(5, income * self.commission) + (income * self.slippage) # 滑点算在卖出
        net_income = income - fee
        
        # 收益计算
        buy_cost = pos['cost_price'] * shares_to_sell
        profit = net_income - buy_cost
        profit_pct = (profit / buy_cost) * 100
        
        self.cash += net_income
        self.trades.append({
            'date': date, 'code': code, 'name': name, 'action': 'SELL',
            'price': price, 'shares': shares_to_sell, 'amount': net_income, 
            'profit': profit, 'profit_pct': profit_pct, 'reason': reason
        })
        
        if is_partial:
            self.positions[code]['shares'] -= shares_to_sell
        else:
            del self.positions[code]

class BacktestEngine:
    """旧的单股回测引擎 (保留)"""
    # ... (保持原代码不变)
    def __init__(self, initial_capital=100000, commission=0.0003, 
                 slippage=0.001, position_size=1.0, stop_loss=0.10, take_profit=0.20):
        """
        初始化回测引擎
        
        Args:
            initial_capital: 初始资金
            commission: 手续费率（双向）
            slippage: 滑点
            position_size: 仓位比例（0-1）
            stop_loss: 止损比例（如 0.10 表示 -10%）
            take_profit: 动态止盈比例（如 0.20 表示 +20%时卖出一半）
        """
        self.initial_capital = initial_capital
        self.commission = commission
        self.slippage = slippage
        self.position_size = position_size
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        
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
                # 获取当前行数据
                row = result.loc[date]
                
                # 如果当前有持仓，检查是否需要平仓
                if current_position is not None:
                    buy_date = current_position['buy_date']
                    buy_cost = current_position['buy_cost']
                    has_taken_profit = current_position.get('has_taken_profit', False)
                    
                    # --- 1. 检查动态止盈 ---
                    if not has_taken_profit and self.take_profit > 0:
                        tp_price_threshold = buy_cost * (1 + self.take_profit)
                        
                        # 检查最高价是否触及止盈线
                        if row['high'] >= tp_price_threshold:
                            # 确定成交价
                            tp_price = max(row['open'], tp_price_threshold)
                            
                            # 生成一笔"卖出50%"的交易记录
                            sell_net = tp_price * (1 - self.slippage - self.commission)
                            profit_pct = (sell_net - buy_cost) / buy_cost * 100
                            holding_days = (date - buy_date).days
                            
                            tp_trade = {
                                'stock_code': stock_code,
                                'stock_name': stock_name,
                                'buy_date': buy_date,
                                'buy_price': current_position['buy_price'],
                                'buy_cost': buy_cost,
                                'sell_date': date,
                                'sell_price': tp_price,
                                'sell_net': sell_net,
                                'profit_pct': profit_pct,
                                'holding_days': holding_days,
                                'signal_quality': current_position['signal_quality'],
                                'exit_reason': 'take_profit_50%',
                                'status': 'closed'
                            }
                            stock_trades.append(tp_trade)
                            
                            # 更新持仓状态
                            current_position['has_taken_profit'] = True
                            current_position['use_breakeven_stop'] = True
                            
                            # 继续检查是否触发其他信号（简化处理，这里不再继续）
                            continue
                            
                    # --- 2. 检查止损 ---
                    if current_position.get('use_breakeven_stop', False):
                        # 保本止损
                        stop_price_threshold = buy_cost * (1 + self.commission + self.slippage)
                    else:
                        # 普通止损
                        stop_price_threshold = buy_cost * (1 - self.stop_loss)
                    
                    if row['low'] <= stop_price_threshold:
                        sell_date = date
                        exit_reason = 'stop_loss'
                        status = 'closed'
                        
                        # 确定止损执行价格
                        if row['open'] < stop_price_threshold:
                            sell_price = row['open']
                        else:
                            sell_price = stop_price_threshold
                        
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
                    
                    # --- 3. 检查卖出信号 ---
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
                        'signal_quality': signal_quality,
                        'has_taken_profit': False
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
        
        # 累计收益 (改为单利累加，避免夸张的复利误导)
        # 假设每次使用固定金额交易，不进行复利定投
        cumulative_return = df['profit_pct'].sum()
        
        # 最大回撤 (基于资金曲线计算)
        # 假设初始资金为100，每次盈亏叠加
        equity = 100 + df['profit_pct'].cumsum()
        running_max = equity.expanding().max()
        # 防止分母为0或负数（虽然理论上equity应该>0）
        # 这里计算的是相对于最高点的回撤百分比
        drawdown = (equity - running_max) / running_max * 100
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


import os

class StockDataLoader:
    """股票数据加载器"""
    CACHE_DIR = "data_cache"
    
    @staticmethod
    def _get_cache_path(code):
        if not os.path.exists(StockDataLoader.CACHE_DIR):
            os.makedirs(StockDataLoader.CACHE_DIR)
        today = datetime.now().strftime("%Y%m%d")
        return os.path.join(StockDataLoader.CACHE_DIR, f"{code}_{today}.csv")

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
                    # 过滤ST、退市、指数、债券
                    if 'ST' not in name and '退' not in name and '指数' not in name and '债' not in name:
                        # 板块筛选
                        exchange = full_code.split('.')[0]  # sh or sz
                        code_num = full_code.split('.')[-1]
                        
                        # 确保是6位股票代码
                        if len(code_num) != 6:
                            continue
                        
                        # 过滤上海交易所的指数 (sh.000xxx, sh.999xxx等)
                        if exchange == 'sh' and (code_num.startswith('000') or code_num.startswith('999')):
                            continue
                        
                        is_chinext = code_num.startswith('300') or code_num.startswith('301')
                        is_star = code_num.startswith('688')
                        
                        if board_filter == 'chinext':
                            if not is_chinext: continue
                        elif board_filter == 'star':
                            if not is_star: continue
                        elif board_filter == 'chinext+star':
                            if not (is_chinext or is_star): continue
                        elif board_filter == 'all':
                            # 只接受主板股票 (60, 00, 30, 68开头)
                            if not (code_num.startswith('60') or code_num.startswith('00') or 
                                   code_num.startswith('30') or code_num.startswith('68')):
                                continue
                        else:
                            # 支持自定义前缀，如 "300,00"
                            prefixes = board_filter.split(',')
                            if not any(code_num.startswith(p.strip()) for p in prefixes):
                                continue
                        
                        stock_list.append({'code': full_code, 'name': name})
        
        bs.logout()
        
        if max_stocks and max_stocks < len(stock_list):
            stock_list = stock_list[:max_stocks]
        
        return stock_list
    
    @staticmethod
    def get_stock_data(code, days=250):
        """获取股票数据 (带缓存)"""
        cache_path = StockDataLoader._get_cache_path(code)
        
        # 1. 尝试从缓存读取
        if os.path.exists(cache_path):
            try:
                df = pd.read_csv(cache_path, index_col='date', parse_dates=['date'])
                return df
            except Exception:
                pass # 读取失败则重新下载
        
        # 2. 从服务器下载
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
        
        # 3. 写入缓存
        try:
            df.to_csv(cache_path)
        except Exception as e:
            print(f"写入缓存失败: {e}")
            
        return df


def run_backtest(board='chinext+star', max_stocks=100, max_positions=5, quality_thresholds=None,
                strict_mode=True, history_days=250, stop_loss=0.10, take_profit=0.20, delay=0.1,
                initial_capital=100000):
    """
    运行回测 (组合模式)
    
    参数说明:
    - max_stocks: 股票池大小（从市场选取多少只股票）
    - max_positions: 最大持仓数量（同时持有多少只股票）
    """
    print("=" * 100)
    print("QQE趋势策略回测系统 (v2.0 资金池回测版)")
    print("=" * 100)
    print(f"板块: {board}")
    print(f"股票池: {max_stocks}只")
    print(f"最大持仓: {max_positions}只")
    print(f"初始资金: {initial_capital}")
    print(f"模式: {'严格模式' if strict_mode else '标准模式'}")
    print(f"止损: {stop_loss*100:.0f}% | 止盈: {take_profit*100:.0f}%")
    print(f"评测阈值: {quality_thresholds}")
    print("=" * 100)
    
    # 默认质量阈值
    if quality_thresholds is None:
        quality_thresholds = [60]
    
    # 获取股票列表
    print("\n[1/3] 获取股票列表...")
    stock_list = StockDataLoader.get_stock_list(board_filter=board, max_stocks=max_stocks)
    print(f"共获取 {len(stock_list)} 只股票")
    
    # 预加载数据 (只需加载一次)
    print("\n[2/3] 预加载市场数据...")
    market_data_cache = {}
    valid_stocks = 0
    for i, stock in enumerate(stock_list):
        print(f"\r下载进度: {i+1}/{len(stock_list)}", end='', flush=True)
        try:
            df = StockDataLoader.get_stock_data(stock['code'], days=history_days)
            if df is not None and len(df) >= 60:
                # 预计算策略
                result = qqe_trend_strategy(df, strict_mode=strict_mode)
                market_data_cache[stock['code']] = {
                    'name': stock['name'],
                    'data': result
                }
                valid_stocks += 1
        except Exception:
            continue
            
    print(f"\n有效股票数据: {valid_stocks}只")

    # 对每个质量阈值运行组合回测
    print(f"\n[3/3] 开始多组参数回测...")
    
    results = []
    
    for q in quality_thresholds:
        print(f"\n>>> 正在回测: 最小质量分 {q} ...")
        
        engine = PortfolioBacktester(
            initial_capital=initial_capital,
            max_stocks=max_positions,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strict_mode=strict_mode
        )
        
        # 为了避免修改 PortfolioBacktester 太多，我们这里动态注入预加载的数据
        # 或者我们稍微修改 PortfolioBacktester 的 run 方法接收 cache
        # 这里为了简单，我们还是让 PortfolioBacktester 自己去处理，
        # 但既然我们已经写了 PortfolioBacktester.run 会重新下载，这会很慢。
        # 让我重构 PortfolioBacktester.run 支持传入已处理的数据。
        
        # 临时方案：这里直接修改 PortfolioBacktester 的 run 方法会更好，
        # 但为了不来回改文件，我将在这里手动组装数据传给 engine 的 _process_daily_step
        # 或者是修改 PortfolioBacktester.run 接受 preloaded_data
        
        # 鉴于代码结构，最好的办法是修改 PortfolioBacktester 让它支持传入 data_cache
        # 我会在下面紧接着修改 PortfolioBacktester
        equity_curve, trades = engine.run_with_cache(market_data_cache, min_quality=q)
        
        if not equity_curve:
            print("  无交易产生。")
            continue
            
        final_equity = equity_curve[-1]['equity']
        total_return = (final_equity - initial_capital) / initial_capital * 100
        
        # 计算最大回撤
        eq_series = pd.Series([x['equity'] for x in equity_curve])
        running_max = eq_series.expanding().max()
        drawdowns = (eq_series - running_max) / running_max * 100
        max_dd = drawdowns.min()
        
        results.append({
            'threshold': q,
            'return': total_return,
            'max_dd': max_dd,
            'final_equity': final_equity,
            'trades': len(trades)
        })
        
        print(f"  最终权益: {final_equity:,.0f} (收益率 {total_return:.2f}%)")
        print(f"  最大回撤: {max_dd:.2f}%")
        
        # 保存详情
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pd.DataFrame(equity_curve).to_csv(f"equity_q{q}_{timestamp}.csv", index=False)
        
    # 汇总对比
    print("\n" + "="*60)
    print("最终回测对比 (资金池模式)")
    print("="*60)
    print(f"{'阈值':<10} | {'总收益率':<15} | {'最大回撤':<15} | {'交易数':<10}")
    print("-" * 60)
    for res in results:
        print(f"{res['threshold']:<10} | {res['return']:<14.2f}% | {res['max_dd']:<14.2f}% | {res['trades']:<10}")
    print("="*60)

def main():
    parser = argparse.ArgumentParser(description='QQE趋势策略回测系统')
    parser.add_argument('--board', type=str, default='chinext+star', help='板块筛选')
    parser.add_argument('--max-stocks', type=int, default=100, help='股票池大小（选取多少只股票）')
    parser.add_argument('--max-positions', type=int, default=5, help='最大持仓数量（同时持有多少只）')
    parser.add_argument('--budget', type=float, default=100000, help='初始资金')
    parser.add_argument('--quality-thresholds', type=str, default='50,60,70', help='质量阈值列表')
    parser.add_argument('--no-strict', action='store_true', help='使用标准模式')
    parser.add_argument('--history-days', type=int, default=250, help='历史数据天数')
    parser.add_argument('--stop-loss', type=float, default=0.10, help='止损比例')
    parser.add_argument('--take-profit', type=float, default=0.20, help='动态止盈比例')
    parser.add_argument('--delay', type=float, default=0.1, help='请求间隔')
    
    args = parser.parse_args()
    
    strict_mode = not args.no_strict
    
    # 智能默认：非严格模式下默认阈值为0，严格模式下保持原默认值
    if args.quality_thresholds == '50,60,70' and not strict_mode:
        quality_thresholds = [0]
    else:
        quality_thresholds = [int(x.strip()) for x in args.quality_thresholds.split(',')]
    
    run_backtest(
        board=args.board,
        max_stocks=args.max_stocks,
        max_positions=args.max_positions,
        initial_capital=args.budget,
        quality_thresholds=quality_thresholds,
        strict_mode=strict_mode,
        history_days=args.history_days,
        stop_loss=args.stop_loss,
        take_profit=args.take_profit,
        delay=args.delay
    )


if __name__ == "__main__":
    main()
