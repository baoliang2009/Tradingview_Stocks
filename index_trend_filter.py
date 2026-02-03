"""
指数趋势过滤器
用于判断大盘/板块指数是否处于多头趋势，以过滤个股交易信号
"""
import baostock as bs
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from qqe_trend_strategy import qqe_trend_strategy


class IndexTrendFilter:
    """指数趋势过滤器"""
    
    # 板块代码映射
    INDEX_MAP = {
        'chinext': 'sz.399006',      # 创业板指
        'star': 'sh.000688',          # 科创50
        'chinext+star': 'sz.399006',  # 创业板+科创 -> 使用创业板指
        'sz.300': 'sz.399006',        # 300开头 -> 创业板指
        'sz.301': 'sz.399006',        # 301开头 -> 创业板指
        'sh.688': 'sh.000688',        # 688开头 -> 科创50
        'sh.60': 'sh.000001',         # 60开头 -> 上证指数
        'sz.00': 'sz.399001',         # 00开头 -> 深证成指
    }
    
    def __init__(self, cache_dir="index_cache"):
        """初始化指数过滤器"""
        self.cache_dir = cache_dir
        self.index_data_cache = {}  # {index_code: dataframe}
        
    def _get_index_code(self, stock_code):
        """
        根据股票代码返回对应的指数代码
        
        Args:
            stock_code: 股票代码，如 'sz.300750'
            
        Returns:
            指数代码，如 'sz.399006'
        """
        # 提取交易所和前缀
        if '.' not in stock_code:
            return 'sz.399001'  # 默认深证成指
            
        exchange, code_num = stock_code.split('.')
        
        # 创业板
        if code_num.startswith('300') or code_num.startswith('301'):
            return 'sz.399006'  # 创业板指
        
        # 科创板
        elif code_num.startswith('688'):
            return 'sh.000688'  # 科创50
        
        # 上证主板
        elif code_num.startswith('60'):
            return 'sh.000001'  # 上证指数
        
        # 深证主板
        elif code_num.startswith('00'):
            return 'sz.399001'  # 深证成指
        
        # 默认
        else:
            return 'sz.399001'
    
    def get_index_data(self, index_code, days=250):
        """
        获取指数数据
        
        Args:
            index_code: 指数代码，如 'sz.399006'
            days: 历史天数
            
        Returns:
            DataFrame: 指数数据
        """
        # 检查缓存
        if index_code in self.index_data_cache:
            return self.index_data_cache[index_code]
        
        # 下载数据
        lg = bs.login()
        
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        rs = bs.query_history_k_data_plus(
            index_code,
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
        
        # 缓存
        self.index_data_cache[index_code] = df
        
        return df
    
    def is_bullish_trend(self, index_code, current_date=None, mode='strict'):
        """
        判断指数是否处于多头趋势
        
        Args:
            index_code: 指数代码
            current_date: 判断日期（None表示最新）
            mode: 判断模式
                - 'simple': 简单模式（价格在均线上方）
                - 'moderate': 中等模式（多均线金叉 + 趋势向上）
                - 'strict': 严格模式（QQE信号 + 趋势强度）
                
        Returns:
            bool: True表示多头，False表示空头/震荡
        """
        df = self.get_index_data(index_code)
        if df is None or len(df) < 60:
            return False
        
        # 如果指定日期，截取到该日期
        if current_date:
            if isinstance(current_date, str):
                current_date = pd.to_datetime(current_date)
            df = df[df.index <= current_date]
            
        if len(df) < 60:
            return False
        
        # 获取最新数据
        latest = df.iloc[-1]
        close = latest['close']
        
        if mode == 'simple':
            # 简单模式：价格在20日和60日均线上方
            ma20 = df['close'].rolling(20).mean().iloc[-1]
            ma60 = df['close'].rolling(60).mean().iloc[-1]
            
            return close > ma20 and close > ma60 and ma20 > ma60
        
        elif mode == 'moderate':
            # 中等模式：多均线金叉 + 趋势向上
            ma5 = df['close'].rolling(5).mean().iloc[-1]
            ma10 = df['close'].rolling(10).mean().iloc[-1]
            ma20 = df['close'].rolling(20).mean().iloc[-1]
            ma60 = df['close'].rolling(60).mean().iloc[-1]
            
            # 均线多头排列
            multi_align = close > ma5 > ma10 > ma20
            
            # 趋势向上（20日均线斜率为正）
            ma20_prev5 = df['close'].rolling(20).mean().iloc[-6]
            ma20_rising = ma20 > ma20_prev5
            
            # 价格强度（不在低位震荡）
            price_60_high = df['close'].rolling(60).max().iloc[-1]
            price_60_low = df['close'].rolling(60).min().iloc[-1]
            price_position = (close - price_60_low) / (price_60_high - price_60_low)
            not_at_bottom = price_position > 0.3  # 不在60日区间的底部30%
            
            return multi_align and ma20_rising and not_at_bottom
        
        elif mode == 'strict':
            # 严格模式：使用QQE策略判断
            try:
                result = qqe_trend_strategy(df, strict_mode=True)
                
                # 获取最新信号
                latest_signal = result.iloc[-1]
                
                # 1. QQE多头条件
                qqe_bullish = latest_signal.get('long_condition', False)
                
                # 2. 趋势强度
                trend = latest_signal.get('trend', 0)
                strong_trend = trend > 10
                
                # 3. 价格在趋势MA上方
                price_above_ma = latest_signal['close'] > latest_signal.get('ha_close_ma', latest_signal['close'])
                
                # 4. RSI不过热
                secondary_rsi = latest_signal.get('secondary_rsi', 50)
                rsi_ok = 30 < secondary_rsi < 80
                
                # 5. 连续性检查（最近5天至少3天多头）
                recent_5 = result.iloc[-5:]
                bullish_days = recent_5['long_condition'].sum()
                sustained = bullish_days >= 3
                
                return qqe_bullish and strong_trend and price_above_ma and rsi_ok and sustained
                
            except Exception as e:
                print(f"警告: QQE判断失败 ({e})，降级为中等模式")
                return self.is_bullish_trend(index_code, current_date, mode='moderate')
        
        return False
    
    def get_trend_strength(self, index_code, current_date=None):
        """
        获取指数趋势强度评分 (0-100)
        
        Args:
            index_code: 指数代码
            current_date: 判断日期
            
        Returns:
            float: 趋势强度评分，0表示强空头，50表示震荡，100表示强多头
        """
        df = self.get_index_data(index_code)
        if df is None or len(df) < 60:
            return 50  # 数据不足，返回中性
        
        # 如果指定日期，截取到该日期
        if current_date:
            if isinstance(current_date, str):
                current_date = pd.to_datetime(current_date)
            df = df[df.index <= current_date]
        
        if len(df) < 60:
            return 50
        
        close = df['close'].iloc[-1]
        
        # 多个维度评分
        score = 0
        
        # 1. 均线位置 (0-25分)
        ma20 = df['close'].rolling(20).mean().iloc[-1]
        ma60 = df['close'].rolling(60).mean().iloc[-1]
        if close > ma20:
            score += 10
        if close > ma60:
            score += 10
        if ma20 > ma60:
            score += 5
        
        # 2. 价格相对位置 (0-25分)
        high_60 = df['high'].rolling(60).max().iloc[-1]
        low_60 = df['low'].rolling(60).min().iloc[-1]
        price_position = (close - low_60) / (high_60 - low_60) if (high_60 - low_60) > 0 else 0.5
        score += price_position * 25
        
        # 3. 趋势方向 (0-25分)
        ma20_5ago = df['close'].rolling(20).mean().iloc[-6] if len(df) >= 6 else ma20
        trend_direction = (ma20 - ma20_5ago) / ma20_5ago if ma20_5ago > 0 else 0
        score += max(0, min(25, trend_direction * 500))  # 归一化到0-25
        
        # 4. 动能 (0-25分)
        close_5ago = df['close'].iloc[-6] if len(df) >= 6 else close
        momentum = (close - close_5ago) / close_5ago if close_5ago > 0 else 0
        score += max(0, min(25, momentum * 250))  # 归一化到0-25
        
        return max(0, min(100, score))
    
    def should_allow_entry(self, stock_code, current_date=None, mode='moderate', min_strength=60):
        """
        判断是否允许该股票开仓（基于对应指数趋势）
        
        Args:
            stock_code: 股票代码
            current_date: 判断日期
            mode: 判断模式 ('simple', 'moderate', 'strict')
            min_strength: 最小趋势强度（0-100）
            
        Returns:
            tuple: (是否允许, 指数代码, 趋势强度)
        """
        # 获取对应指数
        index_code = self._get_index_code(stock_code)
        
        # 判断趋势
        is_bullish = self.is_bullish_trend(index_code, current_date, mode)
        
        # 获取强度
        strength = self.get_trend_strength(index_code, current_date)
        
        # 综合判断
        allow = is_bullish and strength >= min_strength
        
        return allow, index_code, strength


def test_index_filter():
    """测试指数过滤器"""
    print("=" * 80)
    print("指数趋势过滤器测试")
    print("=" * 80)
    
    filter = IndexTrendFilter()
    
    # 测试主要指数
    test_indices = [
        ('sz.399006', '创业板指'),
        ('sh.000688', '科创50'),
        ('sh.000001', '上证指数'),
        ('sz.399001', '深证成指'),
    ]
    
    print("\n当前指数趋势状态:")
    print("-" * 80)
    print(f"{'指数':<15} | {'简单模式':<10} | {'中等模式':<10} | {'严格模式':<10} | {'趋势强度':<10}")
    print("-" * 80)
    
    for code, name in test_indices:
        simple = filter.is_bullish_trend(code, mode='simple')
        moderate = filter.is_bullish_trend(code, mode='moderate')
        strict = filter.is_bullish_trend(code, mode='strict')
        strength = filter.get_trend_strength(code)
        
        print(f"{name:<15} | {'✓' if simple else '✗':<10} | {'✓' if moderate else '✗':<10} | "
              f"{'✓' if strict else '✗':<10} | {strength:<10.1f}")
    
    print("-" * 80)
    
    # 测试股票过滤
    print("\n股票开仓过滤测试:")
    print("-" * 80)
    
    test_stocks = [
        ('sz.300750', '宁德时代'),
        ('sh.688981', '中芯国际'),
        ('sh.600519', '贵州茅台'),
        ('sz.000001', '平安银行'),
    ]
    
    for code, name in test_stocks:
        allow, index_code, strength = filter.should_allow_entry(code, mode='moderate', min_strength=60)
        print(f"{name:<10} ({code:<12}) -> 指数: {index_code:<12} | "
              f"允许开仓: {'✓' if allow else '✗':<5} | 强度: {strength:.1f}")
    
    print("=" * 80)


if __name__ == '__main__':
    test_index_filter()
