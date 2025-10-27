"""
hyperliquid adapter implementation
"""

import logging
from datetime import datetime
from typing import List

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


class HyperliquidAdapter(BrokerAdapter):
    """
    adapter for live hyperliquid testnet trading.
    wraps existing hyperliquid_client.py logic.
    """

    def __init__(self, hl_client, db):
        """
        hl_client: HyperliquidClient instance
        db: Database instance
        """
        self.hl_client = hl_client
        self.db = db

    async def get_market_state(self, symbols: List[str]) -> MarketState:
        """fetch market data for all symbols"""
        markets = []
        for symbol in symbols:
            try:
                # get l2 book for best bid/ask
                book = await self.hl_client.get_l2_book(symbol)
                levels = book.get("levels", [[], []])
                bids = levels[0] if len(levels) > 0 else []
                asks = levels[1] if len(levels) > 1 else []

                best_bid = float(bids[0]["px"]) if bids else 0.0
                best_ask = float(asks[0]["px"]) if asks else 0.0
                bid_qty = float(bids[0]["sz"]) if bids else 0.0
                ask_qty = float(asks[0]["sz"]) if asks else 0.0

                mark = (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else 0.0
                spread_bps = (
                    ((best_ask - best_bid) / mark * 10000) if mark > 0 else 0.0
                )

                # get funding rate
                funding_rate = await self.hl_client.get_funding_rate(symbol)

                markets.append(
                    MarketInfo(
                        symbol=symbol,
                        best_bid=best_bid,
                        best_ask=best_ask,
                        mark=mark,
                        spread_bps=spread_bps,
                        funding_8h_rate=funding_rate,
                        volume_24h=0.0,  # hyperliquid doesn't provide this directly
                        bid_qty=bid_qty,
                        ask_qty=ask_qty,
                    )
                )
            except Exception as e:
                logger.error(f"failed to fetch market data for {symbol}: {e}")

        return MarketState(markets=markets, timestamp=datetime.utcnow().isoformat())

    async def get_account_state(self) -> AccountState:
        """fetch account state from hyperliquid"""
        try:
            state = await self.hl_client.get_account_state()
            margin = state.get("marginSummary", {})
            positions_data = state.get("assetPositions", [])

            equity = float(margin.get("accountValue", 0))
            cash = float(margin.get("totalMarginUsed", 0))
            unrealized_pl = float(margin.get("totalNtlPos", 0))

            # calculate realized pnl from db
            realized_pl = await self.db.calculate_realized_pnl()
            fees = -abs(await self.db.calculate_fees_paid())  # negative value

            # hyperliquid doesn't track funding separately; set to 0
            funding_net = 0.0

            # parse positions
            positions = []
            for pos_data in positions_data:
                pos = pos_data.get("position", {})
                symbol = pos.get("coin", "")
                qty = float(pos.get("szi", 0))
                avg_entry = float(pos.get("entryPx", 0))
                upnl = float(pos.get("unrealizedPnl", 0))
                mark_price = float(pos.get("positionValue", 0)) / abs(qty) if qty != 0 else 0
                notional = abs(qty) * mark_price

                positions.append(
                    PositionInfo(
                        symbol=symbol,
                        qty=qty,
                        avg_entry=avg_entry,
                        unrealized_pl=upnl,
                        notional=notional,
                    )
                )

            return AccountState(
                equity=equity,
                cash=cash,
                realized_pl=realized_pl,
                unrealized_pl=unrealized_pl,
                fees=fees,
                funding_net=funding_net,
                positions=positions,
                timestamp=datetime.utcnow().isoformat(),
            )
        except Exception as e:
            logger.error(f"failed to get account state: {e}")
            return AccountState(
                equity=0,
                cash=0,
                realized_pl=0,
                unrealized_pl=0,
                fees=0,
                funding_net=0,
                positions=[],
                timestamp=datetime.utcnow().isoformat(),
            )

    async def place_order(self, order: Order) -> PlacedOrder:
        """place order on hyperliquid"""
        try:
            result = await self.hl_client.place_order(
                symbol=order.symbol,
                side=order.side,
                qty=order.qty,
                order_type=order.order_type,
                limit_price=order.limit_price,
                reduce_only=order.reduce_only,
                time_in_force=order.time_in_force,
                client_id=order.client_id,
            )

            # hyperliquid returns {"status": "ok", "response": {"data": {...}}}
            success = result.get("status") == "ok"
            error = None if success else str(result)

            return PlacedOrder(
                success=success,
                client_id=order.client_id,
                exchange_id=None,  # hyperliquid uses client_id
                error=error,
            )
        except Exception as e:
            logger.error(f"failed to place order: {e}")
            return PlacedOrder(
                success=False,
                client_id=order.client_id,
                error=str(e),
            )

    async def cancel_order(self, client_id: str) -> CancelResult:
        """cancel order on hyperliquid"""
        try:
            result = await self.hl_client.cancel_order(client_id)
            success = result.get("status") == "ok"
            error = None if success else str(result)

            return CancelResult(
                success=success,
                client_id=client_id,
                error=error,
            )
        except Exception as e:
            logger.error(f"failed to cancel order: {e}")
            return CancelResult(
                success=False,
                client_id=client_id,
                error=str(e),
            )

    async def reconcile(self) -> None:
        """sync account state to database"""
        try:
            state = await self.hl_client.get_account_state()

            # update positions
            positions = state.get("assetPositions", [])
            for pos_data in positions:
                pos = pos_data["position"]
                symbol = pos["coin"]
                qty = float(pos["szi"])
                avg_entry = float(pos["entryPx"])
                unrealized_pl = float(pos["unrealizedPnl"])
                # Retrieve exit plan from metadata
                exit_plan = await self.db.get_metadata(f"exit_plan_{symbol}")
                await self.db.upsert_position(symbol, qty, avg_entry, unrealized_pl, exit_plan)

            # update equity snapshot
            margin = state.get("marginSummary", {})
            equity = float(margin.get("accountValue", 0))
            cash = float(margin.get("totalMarginUsed", 0))
            unrealized_pl = float(margin.get("totalNtlPos", 0))

            ts = datetime.utcnow().replace(second=0, microsecond=0)
            await self.db.insert_equity_snapshot(ts, equity, cash, unrealized_pl)

            logger.info(f"reconciled: equity={equity:.2f}")
        except Exception as e:
            logger.error(f"reconcile failed: {e}")

    def limits(self) -> Limits:
        """return hyperliquid trading limits"""
        return Limits(
            min_notional=5.0,  # $5 minimum
            tick_size=0.5,  # varies by symbol; simplified
            max_leverage=5.0,  # testnet default
            initial_margin=0.2,  # 20% im for 5x leverage
            maintenance_margin=0.1,  # 10% mm
        )

    async def close(self) -> None:
        """cleanup resources"""
        await self.hl_client.close()
        logger.info("hyperliquid adapter closed")
