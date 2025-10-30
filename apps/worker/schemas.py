from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field
from datetime import datetime


# observation sent to llm
class BookTop(BaseModel):
    bid_qty: float
    ask_qty: float


class TechnicalIndicators(BaseModel):
    """Technical indicators for a market"""
    ema_20: List[float]  # 20-period EMA series
    macd: List[float]  # MACD series
    rsi_7: List[float]  # 7-period RSI series
    rsi_14: List[float]  # 14-period RSI series
    current_ema_20: float
    current_macd: float
    current_rsi_7: float


class FourHourContext(BaseModel):
    """4-hour timeframe context data"""
    ema_20: float  # 20-period EMA on 4H
    ema_50: float  # 50-period EMA on 4H
    atr_3: float  # 3-period ATR on 4H
    atr_14: float  # 14-period ATR on 4H
    current_volume: float  # Latest 4H candle volume
    avg_volume: float  # Average 4H volume
    macd: List[float]  # MACD series on 4H (last 10 values)
    rsi_14: List[float]  # RSI(14) series on 4H (last 10 values)


class MarketObservation(BaseModel):
    symbol: str
    mid: float
    spread_bps: float
    ohlcv_1m: List[List[float]]  # [[ts, o, h, l, c, v], ...]
    realized_vol_15m: float
    book_top: BookTop
    funding_8h_rate: float
    open_interest: Optional[float] = None
    open_interest_avg: Optional[float] = None  # Average open interest
    technical_indicators: Optional[TechnicalIndicators] = None
    four_hour_context: Optional[FourHourContext] = None


class Position(BaseModel):
    symbol: str
    qty: float
    avg_entry: float
    current_price: Optional[float] = None
    liquidation_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    leverage: Optional[float] = None
    entry_time: Optional[datetime] = None
    holding_time_minutes: Optional[int] = None
    exit_plan: Optional['ExitPlan'] = None


class Account(BaseModel):
    equity: float
    cash: float  # available margin that can be used to open new positions
    margin_balance: float  # total collateral backing all positions (cross-margin)
    used_margin: float  # margin locked in current open positions
    positions: List[Position]
    unrealized_pl: float
    fees_paid_total: float
    total_return_pct: Optional[float] = None  # percentage return since start


class Limits(BaseModel):
    min_notional: float
    tick_size: float
    max_leverage: float


class PerformanceMetrics(BaseModel):
    """Detailed trading performance statistics"""
    win_rate: float  # % of profitable trades
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float  # average profit on winning trades
    avg_loss: float  # average loss on losing trades (negative number)
    profit_factor: float  # |avg_win / avg_loss|
    largest_win: float
    largest_loss: float  # negative number
    avg_hold_time_minutes: float
    total_volume: float


class Scoreboard(BaseModel):
    pnl_all_time: float
    sharpe_30d: float
    max_dd: float
    performance: Optional[PerformanceMetrics] = None


class Observation(BaseModel):
    timestamp: str
    minutes_since_start: Optional[int] = 0
    invocation_count: Optional[int] = 0
    markets: List[MarketObservation]
    account: Account
    limits: Limits
    scoreboard: Scoreboard
    last_error: str


# action returned by llm
class PlaceOrder(BaseModel):
    type: Literal["place_order"]
    symbol: str
    side: Literal["buy", "sell"]
    qty: float = Field(gt=0)
    order_type: Literal["limit", "market"]
    limit_price: Optional[float] = None
    time_in_force: Literal["gtc", "ioc"] = "gtc"
    reduce_only: bool = False
    client_id: str


class Cancellation(BaseModel):
    client_id: str


class Action(BaseModel):
    actions: List[PlaceOrder]
    cancellations: List[Cancellation]
    notes_for_audience: str = Field(max_length=220)


# new position-based action format
class ExitPlan(BaseModel):
    """Exit plan for a position"""
    profit_target: Optional[float] = None
    stop_loss: Optional[float] = None
    invalidation_condition: str


class PositionDecision(BaseModel):
    """Position decision for a specific coin"""
    coin: str  # symbol like "BTC", "ETH"
    signal: Literal["buy", "sell", "hold", "close"]
    quantity: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)
    leverage: float = Field(ge=1, le=50)
    risk_usd: float = Field(ge=0)
    exit_plan: ExitPlan
    justification: str = Field(max_length=500)


class PositionAction(BaseModel):
    """Position-based action format"""
    positions: Dict[str, PositionDecision]  # keyed by coin symbol
    notes_for_audience: str = Field(max_length=1000)


# internal trade record
class Trade(BaseModel):
    symbol: str
    side: str
    qty: float
    price: float
    fee: float
    client_id: str
    ts: datetime
