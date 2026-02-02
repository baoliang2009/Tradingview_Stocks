import pandas as pd
import numpy as np
import baostock as bs
import os
import json
import argparse
from datetime import datetime, timedelta
from qqe_trend_strategy import qqe_trend_strategy
from backtest import StockDataLoader

class PortfolioManager:
    """实盘持仓管理器"""
    def __init__(self, portfolio_file='portfolio.json', total_budget=100000, max_positions=5):
        self.portfolio_file = portfolio_file
        self.total_budget = total_budget
        self.max_positions = max_positions
        self.positions = {}
        self.cash = total_budget
        self.history = []
        self.load_portfolio()

    def load_portfolio(self):
        """加载持仓信息"""
        if os.path.exists(self.portfolio_file):
            try:
                with open(self.portfolio_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.positions = data.get('positions', {})
                    self.cash = data.get('cash', self.total_budget)
                    self.history = data.get('history', [])
                    # 重新计算可用资金（可选：根据配置重置预算）
                    # self.cash = self.total_budget - self.get_market_value(...)
            except Exception as e:
                print(f"加载持仓文件失败: {e}，将初始化为空仓。")
        else:
            print("未找到持仓文件，初始化新账户。")

    def save_portfolio(self):
        """保存持仓信息"""
        data = {
            'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_budget': self.total_budget,
            'cash': self.cash,
            'positions': self.positions,
            'history': self.history
        }
        with open(self.portfolio_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        print(f"持仓状态已保存至 {self.portfolio_file}")

    def execute_buy(self, code, name, price, date, signal_quality):
        """执行买入逻辑（更新账本）"""
        # 1. 计算目标仓位金额
        target_per_stock = self.total_budget / self.max_positions
        
        # 2. 计算可买股数 (向下取整到100股)
        # 考虑预留手续费，这里简单按1%预留
        available_amount = min(self.cash, target_per_stock)
        max_shares = int((available_amount * 0.99) / price)
        buy_shares = (max_shares // 100) * 100
        
        if buy_shares < 100:
            return None, "资金不足以买入1手"
            
        # 3. 计算实际花费
        # 佣金万3，最低5元
        commission = max(5, buy_shares * price * 0.0003) 
        # 过户费等其他杂费忽略或简化
        total_cost = (buy_shares * price) + commission
        
        if total_cost > self.cash:
            return None, f"资金不足 (需 {total_cost:.2f}, 剩 {self.cash:.2f})"
            
        # 4. 更新状态
        self.cash -= total_cost
        self.positions[code] = {
            'name': name,
            'buy_date': date,
            'buy_price': price,
            'shares': buy_shares,
            'cost_basis': total_cost, # 包含费用的总成本
            'signal_quality': signal_quality
        }
        
        record = f"买入 {name}({code}): {buy_shares}股 @ {price:.2f}, 花费 {total_cost:.2f}"
        self.history.append({'date': date, 'action': 'BUY', 'details': record})
        return buy_shares, record

    def execute_sell(self, code, price, date, reason):
        """执行卖出逻辑（更新账本）"""
        if code not in self.positions:
            return None, "未持有该股票"
            
        pos = self.positions[code]
        shares = pos['shares']
        
        # 计算卖出所得
        # 印花税0.05% (简易计算，实际可能不同) + 佣金
        market_value = shares * price
        tax = market_value * 0.0005
        commission = max(5, market_value * 0.0003)
        net_income = market_value - tax - commission
        
        # 计算收益
        profit = net_income - pos['cost_basis']
        profit_pct = (profit / pos['cost_basis']) * 100
        
        # 更新状态
        self.cash += net_income
        del self.positions[code]
        
        record = f"卖出 {pos['name']}({code}): {shares}股 @ {price:.2f}, 净得 {net_income:.2f}, 收益 {profit_pct:.2f}% ({reason})"
        self.history.append({'date': date, 'action': 'SELL', 'details': record})
        return net_income, record

class TradeAssistant:
    def __init__(self, budget, max_stocks, stop_loss=0.10, strict_mode=True):
        self.portfolio = PortfolioManager(total_budget=budget, max_positions=max_stocks)
        self.stop_loss = stop_loss
        self.strict_mode = strict_mode
        self.max_stocks = max_stocks
        
    def analyze_market(self, board='chinext+star', max_scan=100):
        """全市场扫描分析"""
        print(f"\n{'='*60}")
        print(f"实盘交易助手 - 市场扫描中...")
        print(f"总预算: {self.portfolio.total_budget} | 当前现金: {self.portfolio.cash:.2f}")
        print(f"持仓数: {len(self.portfolio.positions)}/{self.max_stocks}")
        print(f"{'='*60}")
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 1. 检查当前持仓 (卖出信号/止损)
        self._check_sell_signals(today)
        
        # 2. 如果还有仓位空缺，扫描买入机会
        if len(self.portfolio.positions) < self.max_stocks:
            self._scan_buy_opportunities(board, today, max_scan)
        else:
            print("\n仓位已满，暂不扫描买入机会。")
            
        # 3. 保存状态
        # 注意：这里我们只是“建议”，用户确认执行后再调用 save_portfolio 是更安全的方式
        # 但为了简化，本工具假设用户会跟随操作，或者用户可以在操作后手动修改json
        # 更好的方式是提供 --execute 参数来确认写入
        
    def _check_sell_signals(self, today):
        """检查持仓股票的卖出信号"""
        print("\n[1/2] 检查持仓卖出信号/止损...")
        
        if not self.portfolio.positions:
            print("  当前无持仓。")
            return

        actions = []
        
        for code, pos in list(self.portfolio.positions.items()):
            # 获取该股票最新数据
            # 注意：实盘时需要足够的数据计算指标，所以要拉取历史数据
            df = StockDataLoader.get_stock_data(code, days=100) # 只要最近100天够计算了
            
            if df is None or len(df) < 50:
                print(f"  警告: 无法获取 {pos['name']} 的足够数据，跳过检查。")
                continue
                
            # 运行策略
            result = qqe_trend_strategy(df, strict_mode=self.strict_mode)
            
            if result.empty:
                continue
                
            last_row = result.iloc[-1]
            last_date = result.index[-1].strftime('%Y-%m-%d')
            current_price = last_row['close']
            
            # 计算当前收益（基于最新收盘价）
            # 注意：pos['cost_basis'] 是总成本，pos['shares'] 是股数
            avg_cost = pos['cost_basis'] / pos['shares']
            unrealized_pnl_pct = (current_price - avg_cost) / avg_cost * 100
            
            # 检查止损
            # 止损价逻辑：基于成本价下跌 stop_loss
            stop_price = avg_cost * (1 - self.stop_loss)
            
            print(f"  {pos['name']}: 现价 {current_price:.2f} (成本 {avg_cost:.2f}), 浮动 {unrealized_pnl_pct:.2f}%")
            
            action = None
            reason = None
            
            # 1. 检查止损 (检查最低价是否触及)
            if last_row['low'] <= stop_price:
                action = 'SELL'
                reason = f"触发止损 (最低价 {last_row['low']:.2f} <= 止损线 {stop_price:.2f})"
                # 预估卖出价
                sell_price = min(last_row['open'], stop_price) if last_row['open'] < stop_price else stop_price
            
            # 2. 检查策略卖出信号
            elif last_row['sell_signal']:
                action = 'SELL'
                reason = "策略卖出信号"
                sell_price = current_price
            
            if action == 'SELL':
                print(f"  >>> 建议卖出 {pos['name']}! 原因: {reason}")
                print(f"      建议挂单价格: {sell_price:.2f}")
                actions.append((code, sell_price, reason))
            else:
                print(f"      继续持有 (止损线: {stop_price:.2f})")
                
        return actions

    def _scan_buy_opportunities(self, board, today, max_scan=100):
        """扫描市场寻找买入机会"""
        print(f"\n[2/2] 扫描潜在买入机会 (限制 {max_scan} 只)...")
        
        # 获取股票列表
        stock_list = StockDataLoader.get_stock_list(board_filter=board, max_stocks=max_scan)
        # 这里为了演示速度限制了数量，实盘可以去掉限制或调大
        # 注意：全市场扫描非常慢，建议实盘时只扫描自选股池
        
        candidates = []
        
        for i, stock in enumerate(stock_list):
            code = stock['code']
            if code in self.portfolio.positions:
                continue
                
            print(f"\r进度: {i+1}/{len(stock_list)}", end='', flush=True)
            
            try:
                # 获取数据
                df = StockDataLoader.get_stock_data(code, days=100)
                if df is None or len(df) < 60:
                    continue
                    
                # 运行策略
                result = qqe_trend_strategy(df, strict_mode=self.strict_mode)
                
                if result.empty:
                    continue
                    
                # 检查最新一天是否有买入信号
                # 实盘注意：如果是收盘后跑，看最后一行。如果是盘中跑，最后一行的信号可能还在变动。
                # 假设是收盘后跑，决策明天买入。
                # 策略逻辑是：信号出现当天收盘确认，第二天开盘买入。
                # 所以我们要找的是：最后一天出现了 Buy Signal。
                
                last_row = result.iloc[-1]
                signal_col = 'buy_signal_strict' if self.strict_mode else 'buy_signal'
                
                if last_row[signal_col]:
                    quality = last_row.get('signal_quality', 0) if self.strict_mode else 0
                    candidates.append({
                        'code': code,
                        'name': stock['name'],
                        'price': last_row['close'], # 参考价格
                        'quality': quality,
                        'date': result.index[-1]
                    })
            except Exception:
                continue
                
        print("\n扫描完成。")
        
        if not candidates:
            print("今日无符合条件的买入目标。")
            return
            
        # 按质量排序
        candidates.sort(key=lambda x: x['quality'], reverse=True)
        
        # 计算可用槽位
        open_slots = self.max_stocks - len(self.portfolio.positions)
        print(f"\n>>> 发现 {len(candidates)} 个买入目标，当前可用槽位 {open_slots} 个:")
        
        for idx, item in enumerate(candidates[:open_slots + 2]): # 多显示几个备选
            is_target = idx < open_slots
            prefix = "[建议买入]" if is_target else "[备选]"
            
            # 试算买入数量
            target_per_stock = self.portfolio.total_budget / self.max_stocks
            can_buy_shares = int((min(self.portfolio.cash, target_per_stock) * 0.99) / item['price']) // 100 * 100
            
            cost = can_buy_shares * item['price']
            
            print(f"{prefix} {item['name']} ({item['code']})")
            print(f"    质量分: {item['quality']:.1f}")
            print(f"    参考价: {item['price']:.2f}")
            if is_target and can_buy_shares >= 100:
                print(f"    建议仓位: {can_buy_shares} 股 (约 {cost:.0f} 元)")
            elif is_target:
                print(f"    资金不足以买入1手 ({target_per_stock:.0f}元)")
            print("-" * 30)

    def execute_commands(self, commands):
        """
        手动输入命令更新持仓状态
        格式:
        buy code price shares
        sell code price
        """
        if not commands:
            return
            
        for cmd in commands:
            parts = cmd.strip().split()
            if not parts:
                continue
            
            op = parts[0].lower()
            today = datetime.now().strftime('%Y-%m-%d')
            
            if op == 'buy' and len(parts) >= 4:
                # buy sh.688000 50.5 100
                code, price, shares = parts[1], float(parts[2]), int(parts[3])
                # 这里名字暂时随便填，因为只是更新账本
                self.portfolio.cash -= (shares * price * 1.0003) # 简单扣费
                self.portfolio.positions[code] = {
                    'name': code, # 简化
                    'buy_date': today,
                    'buy_price': price,
                    'shares': shares,
                    'cost_basis': shares * price * 1.0003,
                    'signal_quality': 0
                }
                print(f"已手动记录买入: {code}")
                
            elif op == 'sell' and len(parts) >= 3:
                # sell sh.688000 55.0
                code, price = parts[1], float(parts[2])
                if code in self.portfolio.positions:
                    pos = self.portfolio.positions[code]
                    income = pos['shares'] * price * (1 - 0.001) # 简单扣费
                    self.portfolio.cash += income
                    del self.portfolio.positions[code]
                    print(f"已手动记录卖出: {code}")
        
        self.portfolio.save_portfolio()

def main():
    parser = argparse.ArgumentParser(description='QQE策略实盘助手')
    parser.add_argument('--budget', type=float, default=100000, help='总预算')
    parser.add_argument('--max-stocks', type=int, default=5, help='最大持仓数量')
    parser.add_argument('--no-strict', action='store_true', help='关闭严格模式')
    parser.add_argument('--board', type=str, default='chinext+star', help='扫描板块')
    parser.add_argument('--action', type=str, choices=['scan', 'update'], default='scan', 
                       help='操作: scan=扫描信号, update=手动更新持仓')
    parser.add_argument('--max-scan', type=int, default=100, help='扫描最大股票数量 (默认100)')
    # 添加用于update的参数
    parser.add_argument('--cmd', type=str, nargs='+', help='更新命令 e.g. "buy sh.688001 50 200"')
    
    args = parser.parse_args()
    
    assistant = TradeAssistant(
        budget=args.budget,
        max_stocks=args.max_stocks,
        strict_mode=not args.no_strict
    )
    
    if args.action == 'scan':
        assistant.analyze_market(board=args.board, max_scan=args.max_scan)
        print("\n提示: 如果您根据建议进行了交易，请使用 --action update 更新持仓状态。")
        print("例如: python3 trade_assistant.py --action update --cmd \"buy sh.688052 185.6 200\"")
        
    elif args.action == 'update':
        if args.cmd:
            assistant.execute_commands(args.cmd)
        else:
            print("请提供更新命令，例如: --cmd \"buy sh.688052 185.6 200\"")

if __name__ == "__main__":
    main()
