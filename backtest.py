"""
QQE趋势策略回测系统
用于评估不同质量阈值下的策略表现
"""
import baostock as bs
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from qqe_trend_strategy import qqe_trend_strategy
from index_trend_filter import IndexTrendFilter
import argparse
import time
import random


class PortfolioBacktester:
    """组合回测引擎（资金池模式）"""
    def __init__(self, initial_capital=100000, max_stocks=5, commission=0.0003, slippage=0.001,
                 stop_loss=0.10, take_profit=0.20, trailing_stop=0.0, layered_tp=False,
                 pyramid_enabled=False, strict_mode=True, use_index_filter=False, 
                 index_filter_mode='moderate', index_min_strength=60,
                 use_atr_stop=False, atr_multiplier=2.0,
                 use_drawdown_exit=False, drawdown_threshold=0.08, min_profit_for_drawdown=0.05):
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.max_stocks = max_stocks
        self.commission = commission
        self.slippage = slippage
        self.stop_loss = stop_loss  # 固定止损比例（当不使用ATR时）
        self.take_profit = take_profit  # 固定止盈比例（传统模式）
        self.trailing_stop = trailing_stop  # 移动止盈回落比例（旧版本，已废弃）
        self.layered_tp = layered_tp  # 分层止盈
        self.pyramid_enabled = pyramid_enabled  # 金字塔加仓
        self.strict_mode = strict_mode
        
        # 🆕 指数过滤参数
        self.use_index_filter = use_index_filter
        self.use_index_filter = use_index_filter
        self.index_filter_mode = index_filter_mode  # 'simple', 'moderate', 'strict'
        self.index_min_strength = index_min_strength
        self.index_filter = IndexTrendFilter() if use_index_filter else None
        
        # 🆕 ATR动态止损参数
        self.use_atr_stop = use_atr_stop  # 是否使用ATR止损
        self.atr_multiplier = atr_multiplier  # ATR倍数，默认2倍
        
        # 🆕 回撤止盈参数
        self.use_drawdown_exit = use_drawdown_exit  # 是否启用回撤止盈
        self.drawdown_threshold = drawdown_threshold  # 回撤阈值，如8% = 0.08
        self.min_profit_for_drawdown = min_profit_for_drawdown  # 启用回撤止盈的最低盈利，如5% = 0.05
        
        self.positions = {}  # {code: {cost, shares, buy_date, ...}}
        self.trades = []
        self.equity_curve = []  # [{date, equity, cash, positions_val}]
        self.daily_logs = []
        
        # 统计信息
        self.index_filter_stats = {
            'total_signals': 0,
            'filtered_by_index': 0,
            'passed_index_filter': 0
        }

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
                    'quality': row.get('signal_quality', 0) if self.strict_mode else 0,
                    'atr': row.get('atr', 0)  # 🆕 添加ATR数据
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
        
        for code, pos in list(self.positions.items()):  # 🔧 Fix: Convert to list to avoid iteration error
            if code not in daily_market:
                current_positions_value += pos['shares'] * pos['last_close']
                continue
            data = daily_market[code]
            pos['last_close'] = data['close']
            
            action = None
            sell_price = 0
            reason = ""
            buy_cost = pos['cost_price']
            
            # 计算持有天数（用于渐进式止损和最小持仓过滤）
            from datetime import datetime as dt
            try:
                buy_date = dt.strptime(pos['buy_date'], '%Y-%m-%d')
                current_date = dt.strptime(date_str, '%Y-%m-%d')
                hold_days = (current_date - buy_date).days
            except:
                hold_days = 0
            
            # 🆕 分层止盈逻辑 (多级止盈，逐步减仓)
            if self.layered_tp:
                current_profit_pct = (data['close'] - buy_cost) / buy_cost
                if 'tp_levels' not in pos:
                    # 初始化止盈层级: [20%, 40%, 60%, 80%, 100%]
                    pos['tp_levels'] = [0.20, 0.40, 0.60, 0.80, 1.00]
                    pos['tp_sold'] = []  # 记录已卖出的层级
                
                # 检查是否触及新的止盈层级
                for level in pos['tp_levels']:
                    if level not in pos['tp_sold'] and current_profit_pct >= level:
                        # 每层卖出20%原始仓位
                        sell_ratio = 0.20
                        reason = f"分层止盈{int(level*100)}%"
                        self._execute_sell(date_str, code, data['name'], data['close'], 
                                         sell_ratio=sell_ratio, reason=reason)
                        pos['tp_sold'].append(level)
                        
                        # 如果卖完80%，剩余20%使用移动止盈
                        if len(pos['tp_sold']) >= 4:  # 已卖80%
                            pos['use_trailing'] = True
                            if 'max_price' not in pos:
                                pos['max_price'] = data['high']
                
                # 剩余20%使用15%移动止盈
                if pos.get('use_trailing'):
                    pos['max_price'] = max(pos.get('max_price', buy_cost), data['high'])
                    trailing_stop_price = pos['max_price'] * 0.85  # 15%回撤
                    if data['close'] < trailing_stop_price and pos['shares'] > 0:
                        peak_pct = (pos['max_price'] - buy_cost) / buy_cost * 100
                        reason = f"最后20%移动止盈(峰值{peak_pct:.1f}%)"
                        positions_to_close.append((code, data['close'], reason))
                        continue
            
            # 🆕 回撤止盈逻辑（优先级最高，适用于非分层止盈模式）
            elif self.use_drawdown_exit:
                # 跟踪持仓期最高价
                if 'peak_price' not in pos:
                    pos['peak_price'] = buy_cost
                pos['peak_price'] = max(pos['peak_price'], data['high'])
                
                # 计算当前相对入场价的盈利
                current_profit_pct = (data['close'] - buy_cost) / buy_cost
                
                # 只有盈利超过最低阈值后才启用回撤止盈
                if current_profit_pct >= self.min_profit_for_drawdown:
                    # 计算从最高价的回撤幅度
                    drawdown_from_peak = (pos['peak_price'] - data['close']) / pos['peak_price']
                    
                    # 如果回撤超过阈值，触发止盈
                    if drawdown_from_peak >= self.drawdown_threshold:
                        peak_profit_pct = (pos['peak_price'] - buy_cost) / buy_cost * 100
                        current_profit = (data['close'] - buy_cost) / buy_cost * 100
                        drawdown_pct = drawdown_from_peak * 100
                        
                        action = "SELL"
                        reason = f"回撤止盈(峰值+{peak_profit_pct:.1f}%,回撤{drawdown_pct:.1f}%)"
                        sell_price = data['close']
                        positions_to_close.append((code, sell_price, reason))
                        continue  # 跳过后续检查
            
            # 🆕 移动止盈逻辑（替代固定止盈）
            elif self.trailing_stop > 0:
                # 跟踪历史最高价
                if 'max_price' not in pos:
                    pos['max_price'] = buy_cost
                pos['max_price'] = max(pos['max_price'], data['high'])
                
                current_profit_pct = (data['close'] - buy_cost) / buy_cost
                
                # 只有盈利超过初始止盈阈值后才启用移动止盈
                if current_profit_pct > self.take_profit:
                    trailing_stop_price = pos['max_price'] * (1 - self.trailing_stop)
                    
                    # 如果价格从峰值回落超过阈值，触发移动止盈
                    if data['close'] < trailing_stop_price:
                        peak_profit_pct = (pos['max_price'] - buy_cost) / buy_cost * 100
                        current_profit = (data['close'] - buy_cost) / buy_cost * 100
                        action = "SELL"
                        reason = f"移动止盈(峰值{peak_profit_pct:.1f}%)"
                        sell_price = data['close']
                        positions_to_close.append((code, sell_price, reason))
                        continue  # 跳过后续检查
            
            # 🔄 保留固定止盈逻辑（当未启用移动止盈时）
            elif not pos.get('has_taken_profit') and self.take_profit > 0:
                tp_price = buy_cost * (1 + self.take_profit)
                if data['high'] >= tp_price:
                    exec_price = max(data['open'], tp_price)
                    self._execute_sell(date_str, code, data['name'], exec_price, is_partial=True, reason="止盈50%")
                    pos['has_taken_profit'] = True
                    pos['use_breakeven'] = True
            
            if pos.get('use_breakeven'):
                stop_price = buy_cost * (1.01) 
            else:
                # 🆕 ATR动态止损 vs 固定比例止损
                if self.use_atr_stop and 'entry_atr' in pos and pos['entry_atr'] > 0:
                    # ATR动态止损: 止损价 = 入场价 - ATR_multiplier * ATR
                    stop_price = buy_cost - (self.atr_multiplier * pos['entry_atr'])
                else:
                    # 固定比例止损（原逻辑）
                    # 🆕 渐进式止损：根据持有天数调整止损比例
                    if hold_days < 5:
                        stop_loss_pct = min(self.stop_loss * 1.2, 0.12)  # 前5天放宽20%
                    elif hold_days < 15:
                        stop_loss_pct = self.stop_loss  # 5-15天正常
                    else:
                        stop_loss_pct = self.stop_loss * 0.8  # 15天后收紧20%
                    
                    stop_price = buy_cost * (1 - stop_loss_pct)
                
            if data['low'] <= stop_price:
                action = "SELL"
                reason = "止损" if not pos.get('use_breakeven') else "保本离场"
                if data['open'] < stop_price:
                    sell_price = data['open']
                else:
                    sell_price = stop_price
            elif data['sell_signal']:
                # 🆕 最小持仓天数过滤：持仓不足5天忽略卖出信号
                if hold_days >= 5:
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

        # --- 1.5. 金字塔加仓检查 ---
        if self.pyramid_enabled:
            for code, pos in list(self.positions.items()):
                if code not in daily_market:
                    continue
                data = daily_market[code]
                buy_cost = pos['cost_price']
                current_profit_pct = (data['close'] - buy_cost) / buy_cost
                
                # 初始化金字塔状态
                if 'pyramid_levels' not in pos:
                    pos['pyramid_levels'] = []  # 已加仓层级
                
                # 金字塔加仓层级: +5%, +10%
                pyramid_thresholds = [0.05, 0.10]
                
                for threshold in pyramid_thresholds:
                    if threshold not in pos['pyramid_levels'] and current_profit_pct >= threshold:
                        # 加仓20%的原始仓位
                        target_pos_size = self.initial_capital / self.max_stocks
                        add_shares = int(pos['initial_shares'] * 0.20) // 100 * 100
                        cost_with_fee = data['close'] * (1 + self.commission) * add_shares
                        
                        if add_shares >= 100 and self.cash >= cost_with_fee:
                            # 执行加仓
                            cost = add_shares * data['close']
                            fee = max(5, cost * self.commission)
                            total_out = cost + fee
                            
                            self.cash -= total_out
                            pos['shares'] += add_shares
                            pos['pyramid_levels'].append(threshold)
                            
                            # 更新平均成本
                            total_shares = pos['shares']
                            total_cost = (pos['cost_price'] * (pos['shares'] - add_shares)) + (data['close'] * add_shares)
                            pos['cost_price'] = total_cost / total_shares
                            
                            # 记录加仓交易
                            self.trades.append({
                                'date': date_str,
                                'code': code,
                                'name': pos['name'],
                                'action': 'BUY_ADD',
                                'price': data['close'],
                                'shares': add_shares,
                                'cost': cost,
                                'fee': fee,
                                'amount': -total_out,
                                'quality': pos.get('quality', 0),
                                'cash_after': self.cash,
                                'reason': f'金字塔加仓{int(threshold*100)}%'
                            })

        # --- 2. 检查买入 ---
        candidates = []
        # DEBUG: 检查当天是否有信号但没被选中
        daily_signals = 0
        filtered_by_quality = 0
        filtered_by_index = 0
        
        if len(self.positions) < self.max_stocks:
            for code, data in daily_market.items():
                if data['buy_signal']:
                    daily_signals += 1
                    self.index_filter_stats['total_signals'] += 1
                    
                    if code in self.positions:
                        pass
                    elif data['quality'] >= min_quality:
                        # 🆕 指数趋势过滤
                        if self.use_index_filter:
                            allow_entry, index_code, index_strength = self.index_filter.should_allow_entry(
                                code, current_date=date_str, 
                                mode=self.index_filter_mode, 
                                min_strength=self.index_min_strength
                            )
                            
                            if not allow_entry:
                                filtered_by_index += 1
                                self.index_filter_stats['filtered_by_index'] += 1
                                continue
                            else:
                                self.index_filter_stats['passed_index_filter'] += 1
                        
                        candidates.append({
                            'code': code, 
                            'name': data['name'],
                            'price': data['close'],
                            'quality': data['quality'],
                            'atr': data.get('atr', 0)  # 🆕 添加ATR数据
                        })
                    else:
                        filtered_by_quality += 1
            
            # DEBUG: 首次买入信号时打印诊断信息
            if daily_signals > 0 and len(self.trades) == 0:
                index_info = f", 被指数过滤 {filtered_by_index} 个" if self.use_index_filter else ""
                print(f"\n[调试] {date_str}: 发现 {daily_signals} 个买入信号, 通过质量筛选 {len(candidates) + filtered_by_index} 个 (最低质量={min_quality}), 被质量过滤 {filtered_by_quality} 个{index_info}")
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
                
                # 🆕 金字塔模式：初始只买20%，后续加仓
                if self.pyramid_enabled:
                    available_cash = available_cash * 0.20  # 初始只用20%资金
                
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
                    # 🆕 传递ATR数据
                    item_atr = item.get('atr', 0)
                    self._execute_buy(date_str, item['code'], item['name'], item['price'], max_shares, item['quality'], item_atr)
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

    def _execute_buy(self, date, code, name, price, shares, quality, atr=0):
        cost = shares * price
        fee = max(5, cost * self.commission)
        total_out = cost + fee
        
        self.cash -= total_out
        self.positions[code] = {
            'name': name,
            'shares': shares,
            'initial_shares': shares,  # 用于分层止盈计算
            'cost_price': price,
            'buy_date': date,
            'last_close': price,
            'quality': quality,
            'has_taken_profit': False,
            'use_breakeven': False,
            'entry_atr': atr  # 🆕 记录入场时的ATR
        }
        self.trades.append({
            'date': date, 
            'code': code, 
            'name': name, 
            'action': 'BUY',
            'price': price, 
            'shares': shares, 
            'cost': cost,
            'fee': fee,
            'amount': -total_out, 
            'quality': quality,
            'cash_after': self.cash,
            'reason': f"Q:{quality:.1f}"
        })

    def _execute_sell(self, date, code, name, price, is_partial=False, sell_ratio=None, reason=""):
        pos = self.positions[code]
        
        shares_to_sell = pos['shares']
        if sell_ratio is not None:
            # 按比例卖出（用于分层止盈）
            # 注意: sell_ratio 是相对于**原始仓位**的比例
            if 'initial_shares' not in pos:
                pos['initial_shares'] = pos['shares']
            shares_to_sell = int(pos['initial_shares'] * sell_ratio) // 100 * 100
            if shares_to_sell == 0 or shares_to_sell > pos['shares']:
                return  # 无法卖出或超出当前持仓
        elif is_partial:
            shares_to_sell = shares_to_sell // 2 // 100 * 100 # 卖一半
            if shares_to_sell == 0: return # 股数太少无法分批，略过
            
        income = shares_to_sell * price
        fee = max(5, income * self.commission) + (income * self.slippage) # 滑点算在卖出
        net_income = income - fee
        
        # 收益计算
        buy_cost = pos['cost_price'] * shares_to_sell
        profit = net_income - buy_cost
        profit_pct = (profit / buy_cost) * 100
        
        # 持有天数
        from datetime import datetime as dt
        try:
            buy_date = dt.strptime(pos['buy_date'], '%Y-%m-%d')
            sell_date = dt.strptime(date, '%Y-%m-%d')
            hold_days = (sell_date - buy_date).days
        except:
            hold_days = 0
        
        self.cash += net_income
        self.trades.append({
            'date': date, 
            'code': code, 
            'name': name, 
            'action': 'SELL',
            'price': price, 
            'shares': shares_to_sell, 
            'income': income,
            'fee': fee,
            'amount': net_income, 
            'buy_price': pos['cost_price'],
            'buy_date': pos['buy_date'],
            'hold_days': hold_days,
            'profit': profit, 
            'profit_pct': profit_pct,
            'quality': pos.get('quality', 0),
            'cash_after': self.cash,
            'reason': reason
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
                strict_mode=True, history_days=250, stop_loss=0.10, take_profit=0.20, 
                trailing_stop=0.0, layered_tp=False, pyramid_enabled=False, enhanced_entry=False,
                delay=0.1, initial_capital=100000, 
                use_index_filter=False, index_filter_mode='moderate', index_min_strength=60,
                use_atr_stop=False, atr_multiplier=2.0,
                use_drawdown_exit=False, drawdown_threshold=0.08, min_profit_for_drawdown=0.05):
    """
    运行回测 (组合模式)
    
    参数说明:
    - max_stocks: 股票池大小（从市场选取多少只股票）
    - max_positions: 最大持仓数量（同时持有多少只股票）
    - use_index_filter: 是否启用指数趋势过滤
    - index_filter_mode: 指数过滤模式 ('simple', 'moderate', 'strict')
    - index_min_strength: 指数最小趋势强度 (0-100)
    - use_atr_stop: 是否使用ATR动态止损
    - atr_multiplier: ATR止损倍数（默认2.0）
    - use_drawdown_exit: 是否使用回撤止盈
    - drawdown_threshold: 回撤阈值（默认0.08即8%）
    - min_profit_for_drawdown: 启用回撤止盈的最低盈利（默认0.05即5%）
    """
    print("=" * 100)
    print("QQE趋势策略回测系统 (v2.3 回撤止盈版)")
    print("=" * 100)
    print(f"板块: {board}")
    print(f"股票池: {max_stocks}只")
    print(f"最大持仓: {max_positions}只")
    print(f"初始资金: {initial_capital}")
    print(f"模式: {'严格模式' if strict_mode else '标准模式'}{'  | 增强入场' if enhanced_entry else ''}")
    
    # 🆕 显示止损止盈模式
    stop_loss_str = f"ATR动态止损({atr_multiplier}倍ATR)" if use_atr_stop else f"{stop_loss*100:.0f}%止损"
    
    if use_drawdown_exit:
        take_profit_str = f"回撤止盈(峰值回撤{drawdown_threshold*100:.0f}%,需盈利>{min_profit_for_drawdown*100:.0f}%)"
    elif trailing_stop > 0:
        take_profit_str = f"移动止盈(回落{trailing_stop*100:.0f}%)"
    else:
        take_profit_str = f"{take_profit*100:.0f}%止盈"
    
    print(f"止损: {stop_loss_str} | 止盈: {take_profit_str}")
    print(f"分层止盈: {'启用' if layered_tp else '禁用'} | 金字塔加仓: {'启用' if pyramid_enabled else '禁用'}")
    print(f"指数过滤: {'启用' if use_index_filter else '禁用'}" + 
          (f" ({index_filter_mode}模式, 最小强度{index_min_strength})" if use_index_filter else ""))
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
                result = qqe_trend_strategy(df, strict_mode=strict_mode, enhanced_entry=enhanced_entry)
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
            trailing_stop=trailing_stop,
            layered_tp=layered_tp,
            pyramid_enabled=pyramid_enabled,
            strict_mode=strict_mode,
            use_index_filter=use_index_filter,
            index_filter_mode=index_filter_mode,
            index_min_strength=index_min_strength,
            use_atr_stop=use_atr_stop,
            atr_multiplier=atr_multiplier,
            use_drawdown_exit=use_drawdown_exit,  # 🆕 回撤止盈
            drawdown_threshold=drawdown_threshold,  # 🆕 回撤阈值
            min_profit_for_drawdown=min_profit_for_drawdown  # 🆕 最低盈利要求
        )
        
        equity_curve, trades = engine.run_with_cache(market_data_cache, min_quality=q)
        
        # 打印指数过滤统计
        if use_index_filter:
            stats = engine.index_filter_stats
            if stats['total_signals'] > 0:
                filter_rate = (stats['filtered_by_index'] / stats['total_signals']) * 100
                print(f"  指数过滤统计: 总信号 {stats['total_signals']}, 被过滤 {stats['filtered_by_index']} ({filter_rate:.1f}%), 通过 {stats['passed_index_filter']}")
        
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
        
        # 保存权益曲线
        equity_file = f"equity_q{q}_{timestamp}.csv"
        pd.DataFrame(equity_curve).to_csv(equity_file, index=False)
        
        # 保存交易记录
        if trades:
            trades_file = f"trades_q{q}_{timestamp}.csv"
            trades_df = pd.DataFrame(trades)
            
            # 添加额外的分析列
            if 'profit' in trades_df.columns:
                # 计算累计收益
                trades_df['cumulative_profit'] = trades_df['profit'].fillna(0).cumsum()
                
                # 计算胜率（仅统计卖出交易）
                sell_trades = trades_df[trades_df['action'] == 'SELL'].copy()
                if len(sell_trades) > 0:
                    win_trades = len(sell_trades[sell_trades['profit'] > 0])
                    win_rate = (win_trades / len(sell_trades)) * 100
                    avg_profit = sell_trades['profit'].mean()
                    avg_profit_pct = sell_trades['profit_pct'].mean()
                    
                    print(f"  交易统计: 胜率 {win_rate:.1f}%, 平均收益 {avg_profit:.2f} ({avg_profit_pct:.2f}%)")
            
            trades_df.to_csv(trades_file, index=False, encoding='utf-8-sig')
            print(f"  已保存: {equity_file}, {trades_file}")
        
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
    parser.add_argument('--trailing-stop', type=float, default=0.0, help='移动止盈回落比例 (0=禁用, 推荐0.15)')
    parser.add_argument('--layered-tp', action='store_true', help='启用分层止盈(20%,40%,60%,80%,100%)')
    parser.add_argument('--pyramid', action='store_true', help='启用金字塔加仓(初始20%, +5%/+10%各加20%)')
    parser.add_argument('--enhanced-entry', action='store_true', help='启用增强入场(3日QQE+1.5倍量+突破20日高)')
    parser.add_argument('--use-index-filter', action='store_true', help='启用指数趋势过滤（根据板块指数多空）')
    parser.add_argument('--index-filter-mode', type=str, default='moderate', choices=['simple', 'moderate', 'strict'], 
                       help='指数过滤模式: simple(简单均线), moderate(多均线), strict(QQE)')
    parser.add_argument('--index-min-strength', type=int, default=60, help='指数最小趋势强度(0-100)')
    parser.add_argument('--use-atr-stop', action='store_true', help='启用ATR动态止损（替代固定止损比例）')
    parser.add_argument('--atr-multiplier', type=float, default=2.0, help='ATR止损倍数（默认2.0，即入场价-2*ATR）')
    parser.add_argument('--use-drawdown-exit', action='store_true', help='启用回撤止盈（基于持仓期最高价）')
    parser.add_argument('--drawdown-threshold', type=float, default=0.08, help='回撤止盈阈值（默认0.08即8%回撤）')
    parser.add_argument('--min-profit-for-drawdown', type=float, default=0.05, help='启用回撤止盈的最低盈利（默认5%）')
    parser.add_argument('--delay', type=float, default=0.1, help='请求间隔')
    
    args = parser.parse_args()
    
    strict_mode = not args.no_strict
    
    # 智能默认：非严格模式下默认阈值为0，严格模式下保持原默认值
    if args.quality_thresholds == '50,60,70' and not strict_mode:
        quality_thresholds = [0]
    else:
        quality_thresholds = [int(x.strip()) for x in args.quality_thresholds.split(',')]
    
    # 警告：非严格模式下使用高阈值会过滤所有信号
    if not strict_mode and any(q > 0 for q in quality_thresholds):
        print("\n" + "="*80)
        print("⚠️  警告: 您正在使用 --no-strict 模式，但设置了质量阈值 > 0")
        print("="*80)
        print("在非严格模式下，所有信号的质量分数都是 0，")
        print(f"使用阈值 {quality_thresholds} 会过滤掉所有买入信号，导致无交易产生。")
        print("\n建议:")
        print("  1. 去掉 --no-strict 参数，使用严格模式（启用8因子质量评分）")
        print("  2. 或者使用 --quality-thresholds 0 (接受所有信号)")
        print("="*80)
        
        # 给用户5秒时间取消
        import time
        print("\n将在5秒后继续执行... (按Ctrl+C取消)")
        try:
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n\n已取消执行。")
            return
    
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
        trailing_stop=args.trailing_stop,
        layered_tp=args.layered_tp,
        pyramid_enabled=args.pyramid,
        enhanced_entry=args.enhanced_entry,
        delay=args.delay,
        use_index_filter=args.use_index_filter,
        index_filter_mode=args.index_filter_mode,
        index_min_strength=args.index_min_strength,
        use_atr_stop=args.use_atr_stop,
        atr_multiplier=args.atr_multiplier,
        use_drawdown_exit=args.use_drawdown_exit,  # 🆕 回撤止盈
        drawdown_threshold=args.drawdown_threshold,  # 🆕 回撤阈值
        min_profit_for_drawdown=args.min_profit_for_drawdown  # 🆕 最低盈利
    )


if __name__ == "__main__":
    main()
