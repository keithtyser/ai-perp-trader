"""Technical indicator calculations"""
import numpy as np
from typing import List, Tuple


def calculate_ema(prices: List[float], period: int) -> List[float]:
    """
    Calculate Exponential Moving Average

    Args:
        prices: List of prices (oldest to newest)
        period: EMA period (e.g., 20)

    Returns:
        List of EMA values (same length as prices)
    """
    if len(prices) < period:
        return [prices[-1]] * len(prices) if prices else []

    prices_array = np.array(prices)
    ema = np.zeros_like(prices_array)

    # First EMA value is SMA
    ema[period - 1] = np.mean(prices_array[:period])

    # Calculate multiplier
    multiplier = 2 / (period + 1)

    # Calculate EMA for remaining values
    for i in range(period, len(prices)):
        ema[i] = (prices_array[i] - ema[i-1]) * multiplier + ema[i-1]

    # Fill initial values with first EMA value
    ema[:period-1] = ema[period-1]

    return ema.tolist()


def calculate_macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> List[float]:
    """
    Calculate MACD (Moving Average Convergence Divergence)

    Args:
        prices: List of prices (oldest to newest)
        fast: Fast EMA period (default 12)
        slow: Slow EMA period (default 26)
        signal: Signal line period (default 9)

    Returns:
        List of MACD line values (MACD line - Signal line)
    """
    if len(prices) < slow:
        return [0.0] * len(prices)

    fast_ema = calculate_ema(prices, fast)
    slow_ema = calculate_ema(prices, slow)

    # MACD line = Fast EMA - Slow EMA
    macd_line = [fast_ema[i] - slow_ema[i] for i in range(len(prices))]

    # Signal line = EMA of MACD line
    signal_line = calculate_ema(macd_line, signal)

    # MACD histogram = MACD line - Signal line
    macd_histogram = [macd_line[i] - signal_line[i] for i in range(len(prices))]

    return macd_histogram


def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    """
    Calculate Relative Strength Index

    Args:
        prices: List of prices (oldest to newest)
        period: RSI period (default 14)

    Returns:
        List of RSI values (0-100)
    """
    if len(prices) < period + 1:
        return [50.0] * len(prices)

    prices_array = np.array(prices)

    # Calculate price changes
    deltas = np.diff(prices_array)

    # Separate gains and losses
    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    # Calculate average gains and losses
    rsi_values = [50.0]  # First value is neutral

    # Initial averages
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0:
        rsi_values.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        rsi_values.append(rsi)

    # Calculate RSI for remaining values using smoothed averages
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            rsi_values.append(rsi)

    # Pad beginning with first calculated value
    while len(rsi_values) < len(prices):
        rsi_values.insert(0, rsi_values[0])

    return rsi_values


def calculate_atr(ohlcv: List[List[float]], period: int = 14) -> List[float]:
    """
    Calculate Average True Range

    Args:
        ohlcv: List of OHLCV candles [[timestamp, open, high, low, close, volume], ...]
        period: ATR period (default 14)

    Returns:
        List of ATR values
    """
    if len(ohlcv) < period:
        return [0.0] * len(ohlcv)

    true_ranges = []
    for i in range(len(ohlcv)):
        high = ohlcv[i][2]
        low = ohlcv[i][3]

        if i == 0:
            # First candle: true range is just high - low
            true_ranges.append(high - low)
        else:
            prev_close = ohlcv[i-1][4]
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

    # Calculate ATR using EMA of true ranges
    atr = calculate_ema(true_ranges, period)

    return atr


def get_recent_indicators(prices: List[float], count: int = 10) -> Tuple[List[float], List[float], List[float], List[float]]:
    """
    Get recent technical indicators

    Args:
        prices: List of prices (oldest to newest)
        count: Number of recent values to return

    Returns:
        Tuple of (ema_20, macd, rsi_7, rsi_14) - each containing 'count' most recent values
    """
    if len(prices) < 2:
        return ([], [], [], [])

    ema_20 = calculate_ema(prices, 20)
    macd = calculate_macd(prices, 12, 26, 9)
    rsi_7 = calculate_rsi(prices, 7)
    rsi_14 = calculate_rsi(prices, 14)

    # Return most recent 'count' values
    return (
        ema_20[-count:] if len(ema_20) >= count else ema_20,
        macd[-count:] if len(macd) >= count else macd,
        rsi_7[-count:] if len(rsi_7) >= count else rsi_7,
        rsi_14[-count:] if len(rsi_14) >= count else rsi_14
    )
