"""
Coinbase REST API client for fetching historical candle data
"""

import httpx
import logging
from datetime import datetime, timedelta
from typing import List

logger = logging.getLogger(__name__)


async def fetch_historical_candles(
    symbol: str,
    granularity: int,
    num_candles: int,
    base_url: str = "https://api.exchange.coinbase.com"
) -> List[List[float]]:
    """
    Fetch historical candles from Coinbase REST API.

    Args:
        symbol: Trading pair (e.g., "BTC-USD")
        granularity: Candle size in seconds (60=1m, 300=5m, 900=15m, 3600=1h, 14400=4h, 86400=1d)
        num_candles: Number of historical candles to fetch
        base_url: Coinbase API base URL

    Returns:
        List of candles in format: [[timestamp_ms, open, high, low, close, volume], ...]
    """
    try:
        # Calculate time range
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(seconds=granularity * num_candles)

        # Coinbase API expects ISO8601 format
        start_iso = start_time.isoformat()
        end_iso = end_time.isoformat()

        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{base_url}/products/{symbol}/candles"
            params = {
                "start": start_iso,
                "end": end_iso,
                "granularity": granularity,
            }

            logger.info(f"Fetching {num_candles} {granularity}s candles for {symbol}...")

            response = await client.get(url, params=params)
            response.raise_for_status()

            # Coinbase returns: [[timestamp, low, high, open, close, volume], ...]
            # We need: [[timestamp_ms, open, high, low, close, volume], ...]
            raw_candles = response.json()

            # Convert format and sort by timestamp (oldest first)
            candles = []
            for candle in raw_candles:
                timestamp, low, high, open_price, close, volume = candle
                candles.append([
                    int(timestamp * 1000),  # Convert to milliseconds
                    open_price,
                    high,
                    low,
                    close,
                    volume,
                ])

            # Sort by timestamp (oldest first)
            candles.sort(key=lambda x: x[0])

            # Limit to requested number
            candles = candles[-num_candles:] if len(candles) > num_candles else candles

            logger.info(f"Fetched {len(candles)} candles for {symbol} ({granularity}s)")
            return candles

    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch historical candles for {symbol}: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching historical candles for {symbol}: {e}")
        return []


async def prefill_candle_buffers(
    symbols: List[str],
    candle_1m_count: int = 240,  # 4 hours of 1m candles
    candle_6h_count: int = 60,   # ~15 days of 6h candles
) -> tuple[dict, dict]:
    """
    Pre-populate candle buffers with historical data for all symbols.

    Note: Using 6h instead of 4h because Coinbase doesn't support 4h granularity.

    Returns:
        (candles_1m_dict, candles_6h_dict) where each is {symbol: [[candles]]}
    """
    candles_1m = {}
    candles_6h = {}

    for symbol in symbols:
        # Fetch 1-minute candles
        candles_1m[symbol] = await fetch_historical_candles(
            symbol=symbol,
            granularity=60,  # 1 minute
            num_candles=candle_1m_count,
        )

        # Fetch 6-hour candles (Coinbase doesn't support 4h)
        candles_6h[symbol] = await fetch_historical_candles(
            symbol=symbol,
            granularity=21600,  # 6 hours
            num_candles=candle_6h_count,
        )

    return candles_1m, candles_6h
