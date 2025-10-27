from hyperliquid_client import HyperliquidClient
from db import Database
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Reconciler:
    """reconciles positions and equity from exchange state"""

    def __init__(self, hl_client: HyperliquidClient, db: Database):
        self.hl_client = hl_client
        self.db = db

    async def reconcile(self):
        """fetch account state and update database"""
        try:
            state = await self.hl_client.get_account_state()
            await self._update_positions(state)
            await self._update_equity(state)
        except Exception as e:
            logger.error(f"reconcile failed: {e}")

    async def _update_positions(self, state: dict):
        """update positions table from account state"""
        positions = state.get("assetPositions", [])
        for pos in positions:
            symbol = pos["position"]["coin"]
            size = float(pos["position"]["szi"])
            entry_px = float(pos["position"]["entryPx"])
            unrealized_pl = float(pos["position"]["unrealizedPnl"])
            # Retrieve exit plan from metadata
            exit_plan = await self.db.get_metadata(f"exit_plan_{symbol}")
            await self.db.upsert_position(symbol, size, entry_px, unrealized_pl, exit_plan)
            logger.info(f"reconciled position {symbol}: {size} @ {entry_px}")

    async def _update_equity(self, state: dict):
        """insert equity snapshot"""
        margin_summary = state.get("marginSummary", {})
        equity = float(margin_summary.get("accountValue", 0))
        cash = float(margin_summary.get("totalMarginUsed", 0))
        unrealized_pl = float(margin_summary.get("totalNtlPos", 0))

        ts = datetime.utcnow().replace(second=0, microsecond=0)
        await self.db.insert_equity_snapshot(ts, equity, cash, unrealized_pl)
        logger.info(f"equity snapshot: {equity}")

    async def sync_fills(self):
        """fetch recent fills and write to trades table"""
        # hyperliquid provides a fills endpoint; simplified here
        # in production you would subscribe to fills via websocket
        try:
            # placeholder: real impl would fetch fills and insert trades
            logger.info("sync_fills placeholder")
        except Exception as e:
            logger.error(f"sync_fills failed: {e}")
