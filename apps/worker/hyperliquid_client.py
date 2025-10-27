import httpx
import json
import time
import hashlib
import hmac
from typing import Dict, List, Optional, Any
from eth_account import Account
from eth_account.messages import encode_defunct
import asyncio
import websockets


class HyperliquidClient:
    """minimal hyperliquid testnet client with rest and websocket helpers"""

    def __init__(self, api_key: str, api_secret: str, account: str, base_url: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.account = account
        self.base_url = base_url.rstrip('/')
        self.http_client = httpx.AsyncClient(timeout=30.0)

    def _sign_request(self, endpoint: str, payload: Dict) -> Dict[str, str]:
        """generate signature for authenticated requests"""
        timestamp = str(int(time.time() * 1000))
        message = f"{timestamp}{endpoint}{json.dumps(payload, separators=(',', ':'))}"
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return {
            "X-API-KEY": self.api_key,
            "X-TIMESTAMP": timestamp,
            "X-SIGNATURE": signature,
        }

    async def get_account_state(self) -> Dict:
        """fetch account equity, positions, and balances"""
        endpoint = "/info"
        payload = {"type": "clearinghouseState", "user": self.account}
        resp = await self.http_client.post(
            f"{self.base_url}{endpoint}",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_market_info(self, symbol: str) -> Dict:
        """fetch market metadata including tick size and min notional"""
        endpoint = "/info"
        payload = {"type": "meta"}
        resp = await self.http_client.post(
            f"{self.base_url}{endpoint}",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        # find symbol in universe
        for asset in data.get("universe", []):
            if asset["name"] == symbol:
                return asset
        return {}

    async def get_l2_book(self, symbol: str) -> Dict:
        """fetch level 2 order book"""
        endpoint = "/info"
        payload = {"type": "l2Book", "coin": symbol}
        resp = await self.http_client.post(
            f"{self.base_url}{endpoint}",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_funding_rate(self, symbol: str) -> float:
        """fetch current funding rate"""
        endpoint = "/info"
        payload = {"type": "metaAndAssetCtxs"}
        resp = await self.http_client.post(
            f"{self.base_url}{endpoint}",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        # extract funding from asset contexts
        for ctx in data.get("assetContexts", []):
            if ctx.get("coin") == symbol:
                return float(ctx.get("funding", "0"))
        return 0.0

    async def get_candles(self, symbol: str, interval: str, lookback: int) -> List[List[float]]:
        """fetch ohlcv candles; interval in minutes"""
        endpoint = "/info"
        payload = {
            "type": "candleSnapshot",
            "req": {
                "coin": symbol,
                "interval": f"{interval}m",
                "startTime": int((time.time() - lookback * int(interval) * 60) * 1000),
                "endTime": int(time.time() * 1000),
            }
        }
        resp = await self.http_client.post(
            f"{self.base_url}{endpoint}",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        # parse candles: [ts, open, high, low, close, volume]
        candles = []
        for c in data:
            candles.append([
                c["t"],
                float(c["o"]),
                float(c["h"]),
                float(c["l"]),
                float(c["c"]),
                float(c.get("v", 0)),
            ])
        return candles

    async def place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        order_type: str,
        limit_price: Optional[float] = None,
        reduce_only: bool = False,
        time_in_force: str = "gtc",
        client_id: Optional[str] = None,
    ) -> Dict:
        """place an order on hyperliquid testnet"""
        endpoint = "/exchange"
        is_buy = side.lower() == "buy"
        payload = {
            "type": "order",
            "orders": [{
                "a": self.account,
                "b": is_buy,
                "p": str(limit_price) if limit_price else "0",
                "s": str(qty),
                "r": reduce_only,
                "t": {"limit": {"tif": time_in_force.upper()}},
                "c": client_id or "",
            }],
            "grouping": "na",
        }
        if order_type == "market":
            payload["orders"][0]["t"] = {"market": {}}

        headers = self._sign_request(endpoint, payload)
        resp = await self.http_client.post(
            f"{self.base_url}{endpoint}",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()

    async def cancel_order(self, client_id: str) -> Dict:
        """cancel order by client id"""
        endpoint = "/exchange"
        payload = {
            "type": "cancel",
            "cancels": [{
                "a": self.account,
                "o": client_id,
            }]
        }
        headers = self._sign_request(endpoint, payload)
        resp = await self.http_client.post(
            f"{self.base_url}{endpoint}",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self.http_client.aclose()
