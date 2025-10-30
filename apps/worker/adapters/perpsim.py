"""
perpsim adapter - paper trading simulator for perpetual futures
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from .base import (
    BrokerAdapter,
    MarketState,
    AccountState,
    Order,
    PlacedOrder,
    CancelResult,
    Limits,
    MarketInfo,
    PositionInfo,
)

logger = logging.getLogger(__name__)


@dataclass
class PerpSimConfig:
    """configuration for paper trading simulator"""

    im: float = 0.05  # initial margin (5%)
    mm: float = 0.03  # maintenance margin (3%)
    max_leverage: float = 20.0
    slippage_bps: float = 1.0  # slippage in basis points
    fee_bps: float = 2.0  # taker fee in basis points
    liq_penalty_bps: float = 5.0  # liquidation penalty
    funding_mode: str = "A"  # A=0%, B=heuristic, C=external
    symbols: List[str] = field(default_factory=lambda: ["BTC-USD"])
    data_source: str = "coinbase"
    min_notional: float = 5.0
    tick_size: float = 0.5


@dataclass
class SimPosition:
    """internal position state for simulator"""

    symbol: str
    qty: float = 0.0  # signed: positive=long, negative=short
    avg_entry: float = 0.0
    realized_pl: float = 0.0
    last_funding_ts: Optional[datetime] = None
    leverage: float = 1.0  # leverage used when opening this position
    entry_time: Optional[datetime] = None  # when the position was opened


@dataclass
class SimOrder:
    """resting limit order in simulator"""

    client_id: str
    symbol: str
    side: str
    qty: float
    limit_price: float
    reduce_only: bool
    timestamp: datetime


class PerpSimAdapter(BrokerAdapter):
    """
    paper trading simulator for perpetual futures.
    simulates margin, leverage, funding, liquidation.
    """

    def __init__(self, config: PerpSimConfig, db):
        self.config = config
        self.db = db

        # state
        self.cash: float = 10000.0  # starting capital
        self.positions: Dict[str, SimPosition] = {}
        self.open_orders: Dict[str, SimOrder] = {}  # client_id -> order
        self.cumulative_fees: float = 0.0
        self.cumulative_funding: float = 0.0

        # market data cache
        self.market_cache: Dict[str, MarketInfo] = {}

        # ema for funding mode B
        self.ema24: Dict[str, float] = {}

        logger.info(f"perpsim initialized: im={config.im}, mm={config.mm}, "
                    f"max_lev={config.max_leverage}, mode={config.funding_mode}")

    async def get_market_state(self, symbols: List[str]) -> MarketState:
        """return cached market data (updated by external feed)"""
        markets = [self.market_cache[s] for s in symbols if s in self.market_cache]
        return MarketState(markets=markets, timestamp=datetime.utcnow().isoformat())

    async def get_account_state(self) -> AccountState:
        """calculate current account state"""
        unrealized_total = 0.0
        positions = []

        for sym, pos in self.positions.items():
            if pos.qty == 0:
                continue

            market = self.market_cache.get(sym)
            if not market:
                continue

            mark = market.mark
            notional = abs(pos.qty) * mark

            # unrealized pnl
            if pos.qty > 0:
                unrealized = pos.qty * (mark - pos.avg_entry)
            else:
                unrealized = abs(pos.qty) * (pos.avg_entry - mark)

            unrealized_total += unrealized

            positions.append(
                PositionInfo(
                    symbol=sym,
                    qty=pos.qty,
                    avg_entry=pos.avg_entry,
                    unrealized_pl=unrealized,
                    notional=notional,
                    leverage=pos.leverage,
                    entry_time=pos.entry_time,
                )
            )

        # total realized pnl across all positions (for reporting only)
        realized_total = sum(p.realized_pl for p in self.positions.values())

        # equity = cash + unrealized + funding
        # (realized P&L is already included in self.cash)
        equity = self.cash + unrealized_total + self.cumulative_funding

        return AccountState(
            equity=equity,
            cash=self.cash,
            realized_pl=realized_total,
            unrealized_pl=unrealized_total,
            fees=self.cumulative_fees,  # negative
            funding_net=self.cumulative_funding,
            positions=positions,
            timestamp=datetime.utcnow().isoformat(),
        )

    async def place_order(self, order: Order) -> PlacedOrder:
        """
        place market or limit order.
        market orders fill immediately against best bid/ask with slippage.
        limit orders rest until crossed.
        """
        try:
            market = self.market_cache.get(order.symbol)
            if not market:
                return PlacedOrder(
                    success=False,
                    client_id=order.client_id,
                    error=f"no market data for {order.symbol}",
                )

            if order.order_type == "market":
                # fill immediately
                fill_price = self._calculate_fill_price(
                    order.side, market.best_bid, market.best_ask
                )
                await self._execute_fill(order, fill_price)
                return PlacedOrder(success=True, client_id=order.client_id)

            else:
                # limit order - add to open orders
                if order.limit_price is None:
                    return PlacedOrder(
                        success=False,
                        client_id=order.client_id,
                        error="limit price required for limit orders",
                    )

                self.open_orders[order.client_id] = SimOrder(
                    client_id=order.client_id,
                    symbol=order.symbol,
                    side=order.side,
                    qty=order.qty,
                    limit_price=order.limit_price,
                    reduce_only=order.reduce_only,
                    timestamp=datetime.utcnow(),
                )
                logger.info(f"limit order placed: {order.client_id} {order.side} "
                           f"{order.qty} @ {order.limit_price}")
                return PlacedOrder(success=True, client_id=order.client_id)

        except Exception as e:
            logger.error(f"place_order failed: {e}")
            return PlacedOrder(success=False, client_id=order.client_id, error=str(e))

    async def cancel_order(self, client_id: str) -> CancelResult:
        """cancel a resting limit order"""
        if client_id in self.open_orders:
            del self.open_orders[client_id]
            logger.info(f"order canceled: {client_id}")
            return CancelResult(success=True, client_id=client_id)
        else:
            return CancelResult(
                success=False, client_id=client_id, error="order not found"
            )

    async def reconcile(self) -> None:
        """
        reconcile simulator state to database.
        called after each agent cycle.
        """
        try:
            # update positions in db
            for sym, pos in self.positions.items():
                if pos.qty != 0:
                    market = self.market_cache.get(sym)
                    mark = market.mark if market else pos.avg_entry
                    unrealized = (
                        pos.qty * (mark - pos.avg_entry)
                        if pos.qty > 0
                        else abs(pos.qty) * (pos.avg_entry - mark)
                    )
                    # Retrieve exit plan from metadata
                    exit_plan = await self.db.get_metadata(f"exit_plan_{sym}")
                    await self.db.upsert_position(sym, pos.qty, pos.avg_entry, unrealized, exit_plan, pos.leverage)
                else:
                    await self.db.upsert_position(sym, 0, 0, 0, None, 1.0)

            # insert equity snapshot
            account = await self.get_account_state()

            # Calculate available cash (equity - used_margin) - same as worker sends to agent
            used_margin = 0.0
            for pos in account.positions:
                if pos.leverage and pos.leverage > 0:
                    used_margin += pos.notional / pos.leverage

            available_cash = max(0.0, account.equity - used_margin)

            ts = datetime.utcnow().replace(second=0, microsecond=0)
            await self.db.insert_equity_snapshot(
                ts, account.equity, available_cash, account.unrealized_pl
            )

            # update metadata
            await self.db.set_metadata("sim_fees", self.cumulative_fees)
            await self.db.set_metadata("sim_funding", self.cumulative_funding)
            await self.db.set_metadata("sim_realized", account.realized_pl)

            logger.info(f"reconciled: equity={account.equity:.2f}, "
                       f"realized={account.realized_pl:.2f}, "
                       f"fees={self.cumulative_fees:.2f}, "
                       f"funding={self.cumulative_funding:.2f}")

        except Exception as e:
            logger.error(f"reconcile failed: {e}")

    def limits(self) -> Limits:
        """return simulator trading limits"""
        return Limits(
            min_notional=self.config.min_notional,
            tick_size=self.config.tick_size,
            max_leverage=self.config.max_leverage,
            initial_margin=self.config.im,
            maintenance_margin=self.config.mm,
        )

    async def close(self) -> None:
        """cleanup resources"""
        logger.info("perpsim closed")

    # ========== internal simulation logic ==========

    def on_market_data(self, symbol: str, best_bid: float, best_ask: float, ts: datetime):
        """
        update market data and trigger fills, funding accrual, liquidation checks.
        called by external data feed on each tick.
        """
        if ts.tzinfo is not None:
            ts = ts.astimezone(timezone.utc).replace(tzinfo=None)

        mark = (best_bid + best_ask) / 2
        spread_bps = ((best_ask - best_bid) / mark * 10000) if mark > 0 else 0

        # calculate funding rate based on mode
        funding_rate = self._calculate_funding_rate(symbol, mark)

        # For simulated trading, provide reasonable bid/ask quantities
        # Use a heuristic: ~0.5% of typical position size (e.g., for BTC at $95k, ~10 BTC = $950k notional)
        # This gives roughly $4,750 worth at each level, or about 0.05 BTC
        typical_qty = 1000.0 / mark if mark > 0 else 1.0  # $1000 worth of the asset

        self.market_cache[symbol] = MarketInfo(
            symbol=symbol,
            best_bid=best_bid,
            best_ask=best_ask,
            mark=mark,
            spread_bps=spread_bps,
            funding_8h_rate=funding_rate,
            volume_24h=0.0,  # Not tracked in simulation
            bid_qty=typical_qty,  # Simulated liquidity
            ask_qty=typical_qty,  # Simulated liquidity
        )

        logger.debug(f"market data cached: {symbol} mark={mark:.2f} bid={best_bid:.2f} ask={best_ask:.2f}")

        # try to fill resting limit orders
        self._try_fill_limits(symbol, best_bid, best_ask, ts)

        # accrue funding
        self._accrue_funding(symbol, funding_rate, ts)

        # check for liquidation
        self._check_liquidation(symbol, mark, ts)

        # update ema for funding mode B
        self._update_ema(symbol, mark)

    def _calculate_fill_price(self, side: str, best_bid: float, best_ask: float) -> float:
        """calculate fill price with slippage"""
        slippage_factor = self.config.slippage_bps / 10000.0
        if side.lower() == "buy":
            return best_ask * (1 + slippage_factor)
        else:
            return best_bid * (1 - slippage_factor)

    async def _execute_fill(self, order: Order, fill_price: float):
        """
        execute a fill: update position, calculate pnl, charge fees.
        """
        symbol = order.symbol
        qty_signed = order.qty if order.side.lower() == "buy" else -order.qty

        # get or create position
        if symbol not in self.positions:
            self.positions[symbol] = SimPosition(
                symbol=symbol, last_funding_ts=datetime.utcnow()
            )

        pos = self.positions[symbol]
        old_qty = pos.qty
        new_qty = old_qty + qty_signed

        # calculate fee
        notional = abs(order.qty) * fill_price
        fee = notional * (self.config.fee_bps / 10000.0)
        self.cumulative_fees -= fee  # fees are negative

        # update position
        if old_qty == 0:
            # opening new position
            pos.qty = new_qty
            pos.avg_entry = fill_price
            pos.leverage = order.leverage  # store leverage from order
            pos.entry_time = datetime.utcnow()  # track when position was opened
            realized_pnl = 0.0

        elif old_qty * qty_signed > 0:
            # adding to position - update leverage to weighted average
            total_cost = old_qty * pos.avg_entry + qty_signed * fill_price
            pos.qty = new_qty
            pos.avg_entry = total_cost / new_qty if new_qty != 0 else 0
            # Keep existing leverage when adding to position
            realized_pnl = 0.0

        else:
            # closing or reversing position
            close_qty = min(abs(qty_signed), abs(old_qty))

            # realized pnl on closed portion
            if old_qty > 0:
                realized_pnl = close_qty * (fill_price - pos.avg_entry)
            else:
                realized_pnl = close_qty * (pos.avg_entry - fill_price)

            pos.realized_pl += realized_pnl

            # update position
            pos.qty = new_qty
            if new_qty != 0 and abs(new_qty) < abs(old_qty):
                # partial close, keep avg_entry and leverage
                pass
            elif new_qty * old_qty < 0:
                # reversed position
                pos.avg_entry = fill_price
                pos.leverage = order.leverage  # use new leverage for reversed position
                pos.entry_time = datetime.utcnow()  # reset entry time for new direction

        # update cash: subtract fee and add realized P&L
        self.cash -= fee
        self.cash += realized_pnl

        # record trade in db
        await self.db.insert_trade(
            symbol=symbol,
            side=order.side,
            qty=order.qty,
            price=fill_price,
            fee=fee,
            client_id=order.client_id,
            ts=datetime.utcnow(),
        )

        logger.info(
            f"filled: {order.side} {order.qty} {symbol} @ {fill_price:.2f}, "
            f"fee={fee:.2f}, realized_pnl={realized_pnl:.2f}, "
            f"pos_qty={pos.qty}, avg_entry={pos.avg_entry:.2f}"
        )

    def _try_fill_limits(self, symbol: str, best_bid: float, best_ask: float, ts: datetime):
        """check if any limit orders can be filled"""
        filled = []
        for client_id, order in self.open_orders.items():
            if order.symbol != symbol:
                continue

            # check if order is crossed
            if order.side.lower() == "buy" and order.limit_price >= best_ask:
                # buy limit crossed
                fill_price = order.limit_price  # limit fill price
                order_obj = Order(
                    symbol=order.symbol,
                    side=order.side,
                    qty=order.qty,
                    order_type="limit",
                    limit_price=order.limit_price,
                    client_id=order.client_id,
                )
                # execute fill (sync version for internal use)
                import asyncio
                asyncio.create_task(self._execute_fill(order_obj, fill_price))
                filled.append(client_id)

            elif order.side.lower() == "sell" and order.limit_price <= best_bid:
                # sell limit crossed
                fill_price = order.limit_price
                order_obj = Order(
                    symbol=order.symbol,
                    side=order.side,
                    qty=order.qty,
                    order_type="limit",
                    limit_price=order.limit_price,
                    client_id=order.client_id,
                )
                import asyncio
                asyncio.create_task(self._execute_fill(order_obj, fill_price))
                filled.append(client_id)

        # remove filled orders
        for cid in filled:
            del self.open_orders[cid]

    def _accrue_funding(self, symbol: str, funding_8h_rate: float, ts: datetime):
        """
        accrue funding payment for open positions.
        called every minute; rate is per 8h, so we divide by 8*60.
        """
        if ts.tzinfo is not None:
            ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        if pos.qty == 0:
            return

        # calculate time delta since last funding accrual
        last_ts = pos.last_funding_ts
        if last_ts is not None and last_ts.tzinfo is not None:
            last_ts = last_ts.astimezone(timezone.utc).replace(tzinfo=None)
            pos.last_funding_ts = last_ts

        if pos.last_funding_ts is None:
            pos.last_funding_ts = ts
            return

        delta_minutes = (ts - pos.last_funding_ts).total_seconds() / 60
        if delta_minutes < 1:
            return

        # funding accrual: rate_per_minute = rate_8h / (8 * 60)
        market = self.market_cache.get(symbol)
        if not market:
            return

        mark = market.mark
        notional = abs(pos.qty) * mark
        rate_per_minute = funding_8h_rate / (8 * 60)

        # funding payment: negative if long and funding positive (paying)
        # positive if short and funding positive (receiving)
        funding_payment = -pos.qty * notional * rate_per_minute / abs(pos.qty) if pos.qty != 0 else 0

        self.cumulative_funding += funding_payment
        pos.last_funding_ts = ts

        if abs(funding_payment) > 0.01:
            logger.info(
                f"funding accrued: {symbol} qty={pos.qty:.4f} "
                f"rate={funding_8h_rate:.6f} payment={funding_payment:.4f}"
            )

    def _check_liquidation(self, symbol: str, mark: float, ts: datetime):
        """
        check if position should be liquidated.
        liquidate if equity < mm * notional.
        """
        if symbol not in self.positions:
            return

        pos = self.positions[symbol]
        if pos.qty == 0:
            return

        # calculate equity (realized P&L already in self.cash)
        unrealized = (
            pos.qty * (mark - pos.avg_entry)
            if pos.qty > 0
            else abs(pos.qty) * (pos.avg_entry - mark)
        )
        equity = self.cash + unrealized + self.cumulative_funding

        # calculate notional
        notional = abs(pos.qty) * mark

        # check maintenance margin
        required_margin = self.config.mm * notional

        if equity < required_margin:
            # liquidate position
            logger.warning(
                f"LIQUIDATION: {symbol} equity={equity:.2f} < "
                f"required={required_margin:.2f}, closing position"
            )

            # close position at mark with liquidation penalty
            liq_penalty_factor = self.config.liq_penalty_bps / 10000.0
            liq_price = mark * (1 - liq_penalty_factor) if pos.qty > 0 else mark * (1 + liq_penalty_factor)

            # execute liquidation
            side = "sell" if pos.qty > 0 else "buy"
            liq_order = Order(
                symbol=symbol,
                side=side,
                qty=abs(pos.qty),
                order_type="market",
                client_id=f"liq-{uuid.uuid4()}",
            )

            import asyncio
            asyncio.create_task(self._execute_fill(liq_order, liq_price))

            # charge liquidation fee
            liq_fee = notional * liq_penalty_factor
            self.cumulative_fees -= liq_fee

            # log to chat
            asyncio.create_task(
                self.db.insert_chat(
                    ts=ts,
                    content=f"⚠️ LIQUIDATED: {symbol} position {pos.qty:.4f} @ {liq_price:.2f}, "
                           f"equity={equity:.2f}, liq_fee={liq_fee:.2f}",
                    cycle_id=f"liq-{ts.isoformat()}",
                )
            )

    def _calculate_funding_rate(self, symbol: str, mark: float) -> float:
        """
        calculate funding rate based on configured mode.
        mode A: 0%
        mode B: heuristic based on trend (ema24)
        mode C: external feed (stub)
        """
        if self.config.funding_mode == "A":
            return 0.0

        elif self.config.funding_mode == "B":
            # simple heuristic: if mark > ema24, positive funding (longs pay shorts)
            ema = self.ema24.get(symbol, mark)
            if mark > ema:
                return 0.0001  # +0.01% per 8h
            else:
                return -0.0001  # -0.01% per 8h

        elif self.config.funding_mode == "C":
            # stub for external funding feed
            return 0.0

        return 0.0

    def _update_ema(self, symbol: str, mark: float):
        """update exponential moving average for funding mode B"""
        if symbol not in self.ema24:
            self.ema24[symbol] = mark
        else:
            # ema with alpha = 2/(24+1) for 24-period ema
            alpha = 2 / 25
            self.ema24[symbol] = alpha * mark + (1 - alpha) * self.ema24[symbol]
