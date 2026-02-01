import pandas as pd
import numpy as np
from typing import Tuple, Optional


class QQETrendStrategy:
    def __init__(
        self,
        rsi_length_primary: int = 6,
        rsi_smoothing_primary: int = 5,
        qqe_factor_primary: float = 3.0,
        threshold_primary: float = 3.0,
        rsi_length_secondary: int = 6,
        rsi_smoothing_secondary: int = 5,
        qqe_factor_secondary: float = 1.61,
        threshold_secondary: float = 3.0,
        bollinger_length: int = 50,
        bollinger_multiplier: float = 0.35,
        ma_type: str = 'EMA',
        ma_period: int = 9,
        alma_offset: float = 0.85,
        alma_sigma: int = 6
    ):
        self.rsi_length_primary = rsi_length_primary
        self.rsi_smoothing_primary = rsi_smoothing_primary
        self.qqe_factor_primary = qqe_factor_primary
        self.threshold_primary = threshold_primary
        self.rsi_length_secondary = rsi_length_secondary
        self.rsi_smoothing_secondary = rsi_smoothing_secondary
        self.qqe_factor_secondary = qqe_factor_secondary
        self.threshold_secondary = threshold_secondary
        self.bollinger_length = bollinger_length
        self.bollinger_multiplier = bollinger_multiplier
        self.ma_type = ma_type
        self.ma_period = ma_period
        self.alma_offset = alma_offset
        self.alma_sigma = alma_sigma

    def _calculate_rsi(self, series: pd.Series, period: int) -> pd.Series:
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def _calculate_ema(self, series: pd.Series, period: int) -> pd.Series:
        return series.ewm(span=period, adjust=False).mean()

    def _calculate_sma(self, series: pd.Series, period: int) -> pd.Series:
        return series.rolling(window=period).mean()

    def _calculate_wma(self, series: pd.Series, period: int) -> pd.Series:
        weights = np.arange(1, period + 1)
        return series.rolling(window=period).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True
        )

    def _calculate_hma(self, series: pd.Series, period: int) -> pd.Series:
        half_period = period // 2
        sqrt_period = int(np.sqrt(period))
        wma_half = self._calculate_wma(series, half_period)
        wma_full = self._calculate_wma(series, period)
        hma = self._calculate_wma(2 * wma_half - wma_full, sqrt_period)
        return hma

    def _calculate_swma(self, series: pd.Series) -> pd.Series:
        weights = np.array([1, 2, 2, 2, 1]) / 8.0
        swma = series.rolling(window=5).apply(
            lambda x: np.dot(x, weights), raw=True
        )
        return swma

    def _calculate_vwma(self, series: pd.Series, volume: pd.Series, period: int) -> pd.Series:
        pv = series * volume
        return pv.rolling(window=period).sum() / volume.rolling(window=period).sum()

    def _calculate_alma(self, series: pd.Series, period: int, offset: float, sigma: int) -> pd.Series:
        m = offset * (period - 1)
        s = period / sigma
        weights = np.exp(-((np.arange(period) - m) ** 2) / (2 * s * s))
        weights = weights / weights.sum()
        return series.rolling(window=period).apply(
            lambda x: np.dot(x, weights), raw=True
        )

    def _calculate_zlema(self, series: pd.Series, period: int) -> pd.Series:
        lag = (period - 1) // 2
        zlema_series = series + series - series.shift(lag)
        return self._calculate_ema(zlema_series, period)

    def calculate_qqe(
        self,
        data: pd.DataFrame,
        rsi_length: int,
        smoothing_factor: int,
        qqe_factor: float,
        source: str = 'close'
    ) -> Tuple[pd.Series, pd.Series]:
        source_series = data[source]
        wilders_length = rsi_length * 2 - 1
        
        rsi = self._calculate_rsi(source_series, rsi_length)
        smoothed_rsi = self._calculate_ema(rsi, smoothing_factor)
        
        atr_rsi = np.abs(smoothed_rsi.shift(1) - smoothed_rsi)
        smoothed_atr_rsi = self._calculate_ema(atr_rsi, wilders_length)
        dynamic_atr_rsi = smoothed_atr_rsi * qqe_factor
        
        long_band = pd.Series(0.0, index=data.index)
        short_band = pd.Series(0.0, index=data.index)
        trend_direction = pd.Series(0, index=data.index)
        
        atr_delta = dynamic_atr_rsi
        new_short_band = smoothed_rsi + atr_delta
        new_long_band = smoothed_rsi - atr_delta
        
        for i in range(1, len(data)):
            if i > 0:
                prev_smoothed_rsi = smoothed_rsi.iloc[i - 1]
                prev_long_band = long_band.iloc[i - 1]
                prev_short_band = short_band.iloc[i - 1]
                prev_trend_direction = trend_direction.iloc[i - 1] if i > 0 else 0
                
                if prev_smoothed_rsi > prev_long_band and smoothed_rsi.iloc[i] > prev_long_band:
                    long_band.iloc[i] = max(prev_long_band, new_long_band.iloc[i])
                else:
                    long_band.iloc[i] = new_long_band.iloc[i]
                
                if prev_smoothed_rsi < prev_short_band and smoothed_rsi.iloc[i] < prev_short_band:
                    short_band.iloc[i] = min(prev_short_band, new_short_band.iloc[i])
                else:
                    short_band.iloc[i] = new_short_band.iloc[i]
                
                long_band_cross = (prev_long_band > smoothed_rsi.iloc[i - 1]) and (long_band.iloc[i] < smoothed_rsi.iloc[i])
                
                if (prev_smoothed_rsi <= prev_short_band and smoothed_rsi.iloc[i] > short_band.iloc[i - 1]) or \
                   (prev_smoothed_rsi >= prev_short_band and smoothed_rsi.iloc[i] < short_band.iloc[i - 1]):
                    trend_direction.iloc[i] = 1
                elif long_band_cross:
                    trend_direction.iloc[i] = -1
                else:
                    trend_direction.iloc[i] = prev_trend_direction
        
        qqe_trend_line = pd.Series(np.where(trend_direction == 1, long_band, short_band), index=data.index)
        
        return qqe_trend_line, smoothed_rsi

    def _calculate_heikin_ashi(self, data: pd.DataFrame) -> pd.DataFrame:
        ha_df = data.copy()
        ha_open = pd.Series(0.0, index=data.index)
        ha_close = (data['open'] + data['high'] + data['low'] + data['close']) / 4
        
        ha_open.iloc[0] = (data['open'].iloc[0] + data['close'].iloc[0]) / 2
        
        for i in range(1, len(data)):
            ha_open.iloc[i] = (ha_open.iloc[i - 1] + ha_close.iloc[i - 1]) / 2
        
        ha_high = pd.concat([data[['open', 'high', 'low', 'close']].max(axis=1), ha_open], axis=1).max(axis=1)
        ha_low = pd.concat([data[['open', 'high', 'low', 'close']].min(axis=1), ha_open], axis=1).min(axis=1)
        
        ha_df['open'] = ha_open
        ha_df['high'] = ha_high
        ha_df['low'] = ha_low
        ha_df['close'] = ha_close
        
        return ha_df

    def _calculate_trend_ma(self, series: pd.Series, volume: Optional[pd.Series] = None) -> pd.Series:
        ma_type = self.ma_type
        ma_period = self.ma_period
        
        if ma_type == 'ALMA':
            return self._calculate_alma(series, ma_period, self.alma_offset, self.alma_sigma)
        elif ma_type == 'HMA':
            return self._calculate_hma(series, ma_period)
        elif ma_type == 'SMA':
            return self._calculate_sma(series, ma_period)
        elif ma_type == 'SWMA':
            return self._calculate_swma(series)
        elif ma_type == 'VWMA':
            if volume is None:
                raise ValueError("Volume series required for VWMA")
            return self._calculate_vwma(series, volume, ma_period)
        elif ma_type == 'WMA':
            return self._calculate_wma(series, ma_period)
        elif ma_type == 'ZLEMA':
            return self._calculate_zlema(series, ma_period)
        else:
            return self._calculate_ema(series, ma_period)

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        result = data.copy()
        
        primary_qqe_trend_line, primary_rsi = self.calculate_qqe(
            data,
            self.rsi_length_primary,
            self.rsi_smoothing_primary,
            self.qqe_factor_primary
        )
        
        secondary_qqe_trend_line, secondary_rsi = self.calculate_qqe(
            data,
            self.rsi_length_secondary,
            self.rsi_smoothing_secondary,
            self.qqe_factor_secondary
        )
        
        bollinger_basis = self._calculate_sma(primary_qqe_trend_line - 50, self.bollinger_length)
        bollinger_deviation = self.bollinger_multiplier * (primary_qqe_trend_line - 50).rolling(window=self.bollinger_length).std()
        bollinger_upper = bollinger_basis + bollinger_deviation
        bollinger_lower = bollinger_basis - bollinger_deviation
        
        ha_data = self._calculate_heikin_ashi(data)
        
        volume = data['volume'] if 'volume' in data.columns else pd.Series(1, index=data.index)
        
        ha_open_ma = self._calculate_trend_ma(ha_data['open'], volume)
        ha_close_ma = self._calculate_trend_ma(ha_data['close'], volume)
        ha_high_ma = self._calculate_trend_ma(ha_data['high'], volume)
        ha_low_ma = self._calculate_trend_ma(ha_data['low'], volume)
        
        trend = 100 * (ha_close_ma - ha_open_ma) / (ha_high_ma - ha_low_ma)
        
        qqe_value = secondary_rsi - 50
        
        qqe_blue = (qqe_value > self.threshold_secondary) & ((primary_rsi - 50) > bollinger_upper)
        qqe_red = (qqe_value < -self.threshold_secondary) & ((primary_rsi - 50) < bollinger_lower)
        
        trend_green = trend > 0
        trend_red = trend < 0
        
        price_above_green = (data['close'] > ha_close_ma) & trend_green
        price_below_red = (data['close'] < ha_close_ma) & trend_red
        
        qqe_long_ok = (qqe_value > 0) & qqe_blue
        qqe_short_ok = (qqe_value < 0) & qqe_red
        
        long_condition = price_above_green & qqe_long_ok
        short_condition = price_below_red & qqe_short_ok
        
        result['primary_qqe_trend_line'] = primary_qqe_trend_line
        result['primary_rsi'] = primary_rsi
        result['secondary_qqe_trend_line'] = secondary_qqe_trend_line
        result['secondary_rsi'] = secondary_rsi
        result['qqe_value'] = qqe_value
        result['trend'] = trend
        result['ha_close_ma'] = ha_close_ma
        result['bollinger_upper'] = bollinger_upper
        result['bollinger_lower'] = bollinger_lower
        result['qqe_blue'] = qqe_blue
        result['qqe_red'] = qqe_red
        result['trend_green'] = trend_green
        result['trend_red'] = trend_red
        result['long_condition'] = long_condition
        result['short_condition'] = short_condition
        
        result['buy_signal'] = long_condition & ~(long_condition.shift(1).fillna(False).astype(bool))
        result['sell_signal'] = short_condition & ~(short_condition.shift(1).fillna(False).astype(bool))
        
        return result

    def generate_signals_strict(self, data: pd.DataFrame) -> pd.DataFrame:
        """生成交易信号 - 严格模式（更高质量，更少信号）
        
        额外的过滤条件：
        1. 趋势强度过滤：只在强趋势中买入
        2. 成交量确认：买入时需要成交量放大
        3. 价格动能：价格需要有明显上升动能
        4. 连续确认：需要多日条件持续满足
        5. 风险控制：避免高位买入
        """
        result = self.generate_signals(data)
        
        # 1. 趋势强度过滤 - 趋势值需要足够强
        trend_strength_threshold = 10  # 趋势强度阈值
        strong_trend = result['trend'] > trend_strength_threshold
        
        # 2. 成交量确认 - 买入时成交量应大于均量
        if 'volume' in data.columns:
            volume_ma = data['volume'].rolling(window=20).mean()
            volume_ratio = data['volume'] / volume_ma
            volume_surge = volume_ratio > 1.2  # 成交量放大20%以上
        else:
            volume_surge = pd.Series(True, index=data.index)
        
        # 3. 价格动能 - 收盘价需要连续上涨
        price_momentum = (data['close'] > data['close'].shift(1)) & \
                        (data['close'].shift(1) > data['close'].shift(2))
        
        # 4. RSI不能过高 - 避免追高
        rsi_not_overbought = result['secondary_rsi'] < 70
        
        # 5. 价格相对位置 - 不在高位买入
        high_20 = data['high'].rolling(window=20).max()
        low_20 = data['low'].rolling(window=20).min()
        price_position = (data['close'] - low_20) / (high_20 - low_20)
        not_at_high = price_position < 0.8  # 不在20日高低点的80%位置以上
        
        # 6. QQE双重确认 - primary和secondary QQE都处于上升趋势
        primary_rising = result['primary_rsi'] > result['primary_rsi'].shift(1)
        secondary_rising = result['secondary_rsi'] > result['secondary_rsi'].shift(1)
        qqe_double_confirm = primary_rising & secondary_rising
        
        # 7. 趋势持续性 - 趋势需要连续2天以上为正
        trend_sustained = strong_trend & strong_trend.shift(1).fillna(False)
        
        # 8. 价格突破确认 - 价格突破均线且有一定幅度
        price_breakout = (data['close'] > result['ha_close_ma']) & \
                        ((data['close'] - result['ha_close_ma']) / result['ha_close_ma'] > 0.02)  # 突破2%以上
        
        # 组合所有严格条件
        strict_long_condition = (
            result['long_condition'] &  # 原始买入条件
            strong_trend &              # 强趋势
            volume_surge &              # 成交量放大
            price_momentum &            # 价格动能
            rsi_not_overbought &        # RSI未超买
            not_at_high &               # 不在高位
            qqe_double_confirm &        # QQE双重确认
            trend_sustained &           # 趋势持续
            price_breakout              # 价格突破
        )
        
        # 生成严格买入信号
        result['buy_signal_strict'] = strict_long_condition & ~(strict_long_condition.shift(1).fillna(False).astype(bool))
        
        # 添加信号质量评分 (0-100)
        signal_quality = pd.Series(0.0, index=data.index)
        signal_quality += result['trend'].clip(0, 20) * 2  # 趋势强度 (0-40分)
        signal_quality += volume_ratio.clip(0, 3) * 10  # 成交量 (0-30分)
        signal_quality += (100 - result['secondary_rsi'].clip(50, 100)) * 0.3  # RSI位置 (0-15分)
        signal_quality += (1 - price_position.clip(0, 1)) * 15  # 价格位置 (0-15分)
        
        result['signal_quality'] = signal_quality.clip(0, 100)
        
        return result


def qqe_trend_strategy(
    data: pd.DataFrame,
    rsi_length_primary: int = 6,
    rsi_smoothing_primary: int = 5,
    qqe_factor_primary: float = 3.0,
    threshold_primary: float = 3.0,
    rsi_length_secondary: int = 6,
    rsi_smoothing_secondary: int = 5,
    qqe_factor_secondary: float = 1.61,
    threshold_secondary: float = 3.0,
    bollinger_length: int = 50,
    bollinger_multiplier: float = 0.35,
    ma_type: str = 'EMA',
    ma_period: int = 9,
    alma_offset: float = 0.85,
    alma_sigma: int = 6,
    strict_mode: bool = False
) -> pd.DataFrame:
    """
    Generate trading signals based on QQE + Trend Strategy.
    
    Parameters:
    -----------
    data : pd.DataFrame
        DataFrame with columns: open, high, low, close, volume
    rsi_length_primary : int, default 6
        RSI Length for primary QQE
    rsi_smoothing_primary : int, default 5
        RSI Smoothing for primary QQE
    qqe_factor_primary : float, default 3.0
        QQE Factor for primary QQE
    threshold_primary : float, default 3.0
        Threshold for primary QQE
    rsi_length_secondary : int, default 6
        RSI Length for secondary QQE
    rsi_smoothing_secondary : int, default 5
        RSI Smoothing for secondary QQE
    qqe_factor_secondary : float, default 1.61
        QQE Factor for secondary QQE
    threshold_secondary : float, default 3.0
        Threshold for secondary QQE
    bollinger_length : int, default 50
        Length for Bollinger Bands
    bollinger_multiplier : float, default 0.35
        Multiplier for Bollinger Bands
    ma_type : str, default 'EMA'
        MA Type for trend calculation ('ALMA','HMA','SMA','SWMA','VWMA','WMA','ZLEMA','EMA')
    ma_period : int, default 9
        MA Period for trend calculation
    alma_offset : float, default 0.85
        ALMA Shift for ALMA
    alma_sigma : int, default 6
        ALMA Deviation for ALMA
    strict_mode : bool, default False
        Use strict filtering mode for higher quality signals
    
    Returns:
    --------
    pd.DataFrame
        DataFrame with original data plus signals and indicators
    """
    strategy = QQETrendStrategy(
        rsi_length_primary=rsi_length_primary,
        rsi_smoothing_primary=rsi_smoothing_primary,
        qqe_factor_primary=qqe_factor_primary,
        threshold_primary=threshold_primary,
        rsi_length_secondary=rsi_length_secondary,
        rsi_smoothing_secondary=rsi_smoothing_secondary,
        qqe_factor_secondary=qqe_factor_secondary,
        threshold_secondary=threshold_secondary,
        bollinger_length=bollinger_length,
        bollinger_multiplier=bollinger_multiplier,
        ma_type=ma_type,
        ma_period=ma_period,
        alma_offset=alma_offset,
        alma_sigma=alma_sigma
    )
    
    if strict_mode:
        return strategy.generate_signals_strict(data)
    else:
        return strategy.generate_signals(data)
