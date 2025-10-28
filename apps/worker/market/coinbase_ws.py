"""
coinbase exchange websocket feed for spot market data (public, no auth)
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import List, Callable
import websockets

logger = logging.getLogger(__name__)


class CoinbaseWebSocket:
    """
    websocket client for coinbase exchange api (public).
    subscribes to best bid/ask (ticker) for spot symbols without authentication.
    """

    def __init__(
        self,
        symbols: List[str],
        on_tick: Callable[[str, float, float, datetime], None],
        ws_url: str = "wss://ws-feed.exchange.coinbase.com",
        prefilled_1m_candles: dict = None,
        prefilled_4h_candles: dict = None,
    ):
        """
        symbols: list of spot symbols (e.g. ["BTC-USD", "ETH-USD"])
        on_tick: callback(symbol, best_bid, best_ask, ts)
        prefilled_1m_candles: optional dict of {symbol: [[candles]]} to pre-populate 1m buffer
        prefilled_4h_candles: optional dict of {symbol: [[candles]]} to pre-populate 4h buffer
        """
        self.symbols = symbols
        self.on_tick = on_tick
        self.ws_url = ws_url
        self.ws = None
        self.running = False
        self.last_tick_time = datetime.utcnow()  # Track last message time

        # ohlcv ring buffer for 1m candles (last 240 candles = 4 hours)
        # Pre-fill with historical data if provided
        if prefilled_1m_candles:
            self.candle_buffer = {sym: prefilled_1m_candles.get(sym, []) for sym in symbols}
        else:
            self.candle_buffer = {sym: [] for sym in symbols}

        # ohlcv ring buffer for 4h candles (last 50 candles)
        # Pre-fill with historical data if provided
        if prefilled_4h_candles:
            self.candle_4h_buffer = {sym: prefilled_4h_candles.get(sym, []) for sym in symbols}
        else:
            self.candle_4h_buffer = {sym: [] for sym in symbols}

    async def connect(self):
        """connect to coinbase websocket and subscribe to ticker channel"""
        try:
            self.ws = await websockets.connect(self.ws_url)
            logger.info(f"connected to coinbase ws: {self.ws_url}")

            # subscribe to ticker channel for all symbols
            # using coinbase exchange api (public, no auth required)
            subscribe_msg = {
                "type": "subscribe",
                "product_ids": self.symbols,
                "channels": ["ticker"],
            }
            await self.ws.send(json.dumps(subscribe_msg))
            logger.info(f"subscribed to ticker: {self.symbols}")

            self.running = True

        except Exception as e:
            logger.error(f"failed to connect to coinbase ws: {e}")
            raise

    async def start(self):
        """start listening to websocket messages with auto-reconnect"""
        retry_delay = 1  # Start with 1 second
        max_retry_delay = 60  # Max 60 seconds between retries

        while self.running:
            try:
                if not self.ws or self.ws.closed:
                    await self.connect()
                    retry_delay = 1  # Reset delay on successful connection

                async for message in self.ws:
                    if not self.running:
                        break

                    try:
                        data = json.loads(message)
                        await self._handle_message(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"failed to parse ws message: {e}")
                    except Exception as e:
                        logger.error(f"error handling message: {e}")

            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"coinbase ws connection closed, reconnecting in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)  # Exponential backoff
            except Exception as e:
                logger.error(f"coinbase ws error: {e}, reconnecting in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry_delay)
            finally:
                if self.ws and not self.ws.closed:
                    try:
                        await self.ws.close()
                    except:
                        pass
                self.ws = None

    async def _handle_message(self, data: dict):
        """handle incoming websocket message"""
        msg_type = data.get("type")

        if msg_type == "ticker":
            # ticker update with best bid/ask
            product_id = data.get("product_id")
            best_bid = float(data.get("best_bid", 0))
            best_ask = float(data.get("best_ask", 0))
            time_str = data.get("time", datetime.utcnow().isoformat())

            try:
                ts = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                if ts.tzinfo is not None:
                    ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                ts = datetime.utcnow()

            if best_bid > 0 and best_ask > 0:
                # Update last tick time
                self.last_tick_time = datetime.utcnow()

                # call the tick callback
                self.on_tick(product_id, best_bid, best_ask, ts)

                # update candle buffers (simplified)
                self._update_candle_buffer(product_id, best_bid, best_ask, ts)
                self._update_4h_candle_buffer(product_id, best_bid, best_ask, ts)

                logger.debug(f"tick: {product_id} bid={best_bid} ask={best_ask}")
            else:
                logger.warning(f"invalid ticker data for {product_id}: bid={best_bid}, ask={best_ask}")

        elif msg_type == "subscriptions":
            logger.info(f"subscription confirmed: {data.get('channels')}")

        elif msg_type == "error":
            logger.error(f"coinbase ws error: {data.get('message')}")

        else:
            logger.debug(f"received message type: {msg_type}")

    def _update_candle_buffer(self, symbol: str, bid: float, ask: float, ts: datetime):
        """
        update 1m candle buffer.
        simplified: just store mid price as ohlc.
        Note: Volume is not tracked in live updates (only from historical data)
        """
        mid = (bid + ask) / 2

        # truncate to 1m
        ts_minute = ts.replace(second=0, microsecond=0)

        buffer = self.candle_buffer.get(symbol, [])

        # check if we need to add a new candle
        if not buffer or buffer[-1][0] != int(ts_minute.timestamp() * 1000):
            # new candle - preserve volume from historical data if this is updating an existing candle
            # otherwise set to 0 (live websocket doesn't provide volume)
            candle = [
                int(ts_minute.timestamp() * 1000),  # timestamp in ms
                mid,  # open
                mid,  # high
                mid,  # low
                mid,  # close
                0.0,  # volume (not tracked in live feed)
            ]
            buffer.append(candle)

            # keep only last 240 candles (4 hours of 1m data)
            if len(buffer) > 240:
                buffer.pop(0)

        else:
            # update current candle (preserve existing volume)
            candle = buffer[-1]
            candle[2] = max(candle[2], mid)  # high
            candle[3] = min(candle[3], mid)  # low
            candle[4] = mid  # close
            # volume (index 5) is preserved from historical data

        self.candle_buffer[symbol] = buffer

    def _update_4h_candle_buffer(self, symbol: str, bid: float, ask: float, ts: datetime):
        """
        update 4h candle buffer.
        simplified: just store mid price as ohlc.
        Note: Volume is preserved from historical data, not tracked in live updates
        """
        mid = (bid + ask) / 2

        # truncate to 4h intervals (0:00, 4:00, 8:00, 12:00, 16:00, 20:00)
        hour_4h = (ts.hour // 4) * 4
        ts_4h = ts.replace(hour=hour_4h, minute=0, second=0, microsecond=0)

        buffer = self.candle_4h_buffer.get(symbol, [])

        # check if we need to add a new candle
        if not buffer or buffer[-1][0] != int(ts_4h.timestamp() * 1000):
            # new candle - volume will be 0 for live candles (only historical has volume)
            candle = [
                int(ts_4h.timestamp() * 1000),  # timestamp in ms
                mid,  # open
                mid,  # high
                mid,  # low
                mid,  # close
                0.0,  # volume (not tracked in live feed, only from historical)
            ]
            buffer.append(candle)

            # keep only last 50 4h candles (~ 8 days)
            if len(buffer) > 50:
                buffer.pop(0)

        else:
            # update current candle (preserve existing volume from historical data)
            candle = buffer[-1]
            candle[2] = max(candle[2], mid)  # high
            candle[3] = min(candle[3], mid)  # low
            candle[4] = mid  # close
            # volume (index 5) is preserved from historical data

        self.candle_4h_buffer[symbol] = buffer

    def get_candles(self, symbol: str) -> List[List[float]]:
        """return last 240 1m candles for symbol"""
        return self.candle_buffer.get(symbol, [])

    def get_4h_candles(self, symbol: str) -> List[List[float]]:
        """return last 50 4h candles for symbol"""
        return self.candle_4h_buffer.get(symbol, [])

    def is_connection_stale(self, max_seconds=120):
        """Check if we haven't received ticks in a while"""
        time_since_last_tick = (datetime.utcnow() - self.last_tick_time).total_seconds()
        if time_since_last_tick > max_seconds:
            logger.warning(f"No ticks received for {time_since_last_tick:.0f}s, connection may be stale")
            return True
        return False

    async def close(self):
        """close websocket connection"""
        self.running = False
        if self.ws:
            await self.ws.close()
            logger.info("coinbase ws closed")

    async def run_forever(self):
        """
        run websocket in a loop with auto-reconnect.
        """
        self.running = True
        while self.running:
            try:
                logger.info(f"connecting to coinbase ws for {self.symbols}...")
                await self.start()
            except Exception as e:
                logger.error(f"coinbase ws error: {e}, reconnecting in 5s...", exc_info=True)
                await asyncio.sleep(5)
