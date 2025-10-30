"""
abstract broker adapter interface
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class MarketInfo:
    """market data for a single symbol"""

    symbol: str
    best_bid: float
    best_ask: float
    mark: float  # mid or mark price
    spread_bps: float  # spread in basis points
    funding_8h_rate: float  # annualized funding rate (8h window)
    volume_24h: float
    bid_qty: float  # size at best bid
    ask_qty: float  # size at best ask


@dataclass
class PositionInfo:
    """open position"""

    symbol: str
    qty: float  # signed: positive=long, negative=short
    avg_entry: float
    unrealized_pl: float
    notional: float  # abs(qty) * mark
    leverage: float = 1.0  # leverage used when opening this position
    entry_time: Optional[datetime] = None  # when the position was opened


@dataclass
class MarketState:
    """aggregated market data for multiple symbols"""

    markets: list[MarketInfo]
    timestamp: str  # iso8601


@dataclass
class AccountState:
    """account balances and positions"""

    equity: float
    cash: float
    realized_pl: float  # cumulative realized pnl
    unrealized_pl: float  # sum of all open position unrealized
    fees: float  # cumulative fees paid (negative value)
    funding_net: float  # cumulative funding (positive=received, negative=paid)
    positions: list[PositionInfo]
    timestamp: str  # iso8601


@dataclass
class Limits:
    """trading limits and constraints"""

    min_notional: float
    tick_size: float
    max_leverage: float
    initial_margin: float  # im ratio
    maintenance_margin: float  # mm ratio


@dataclass
class Order:
    """order to be placed"""

    symbol: str
    side: str  # "buy" or "sell"
    qty: float
    order_type: str  # "market" or "limit"
    limit_price: Optional[float] = None
    time_in_force: str = "gtc"
    reduce_only: bool = False
    client_id: str = ""
    leverage: float = 1.0  # leverage to use for this order


@dataclass
class PlacedOrder:
    """result of placing an order"""

    success: bool
    client_id: str
    exchange_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class CancelResult:
    """result of canceling an order"""

    success: bool
    client_id: str
    error: Optional[str] = None


class BrokerAdapter(ABC):
    """
    abstract interface for trading backends.
    implementations: hyperliquid (live), perpsim (paper)
    """

    @abstractmethod
    async def get_market_state(self, symbols: list[str]) -> MarketState:
        """
        fetch current market data for given symbols.
        includes best bid/ask, mark, spread, funding, volume.
        """
        pass

    @abstractmethod
    async def get_account_state(self) -> AccountState:
        """
        fetch current account state: equity, cash, positions, pnl, fees, funding.
        """
        pass

    @abstractmethod
    async def place_order(self, order: Order) -> PlacedOrder:
        """
        place a market or limit order.
        returns placed order result with success/error.
        """
        pass

    @abstractmethod
    async def cancel_order(self, client_id: str) -> CancelResult:
        """
        cancel an open order by client_id.
        """
        pass

    @abstractmethod
    async def reconcile(self) -> None:
        """
        pull fills from exchange/simulator, update positions and equity.
        called after each agent cycle to sync state.
        """
        pass

    @abstractmethod
    def limits(self) -> Limits:
        """
        return trading limits: min_notional, tick_size, max_leverage, im, mm.
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """
        cleanup resources (websockets, connections, etc).
        """
        pass
