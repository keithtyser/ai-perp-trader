from typing import List
from schemas import Action, PlaceOrder
from hyperliquid_client import HyperliquidClient
from db import Database
import logging

logger = logging.getLogger(__name__)


class Executor:
    """executes validated actions on hyperliquid testnet"""

    def __init__(self, hl_client: HyperliquidClient, db: Database, dry_run: bool = False):
        self.hl_client = hl_client
        self.db = db
        self.dry_run = dry_run

    async def execute_action(self, action: Action) -> List[str]:
        """execute all orders and cancellations; return list of errors"""
        errors = []

        # process cancellations
        for cancel in action.cancellations:
            try:
                if self.dry_run:
                    logger.info(f"[dry-run] would cancel order {cancel.client_id}")
                else:
                    result = await self.hl_client.cancel_order(cancel.client_id)
                    logger.info(f"cancelled order {cancel.client_id}: {result}")
            except Exception as e:
                err = f"cancel failed for {cancel.client_id}: {e}"
                logger.error(err)
                errors.append(err)

        # process orders
        for order in action.actions:
            try:
                if self.dry_run:
                    logger.info(f"[dry-run] would place {order.side} {order.qty} {order.symbol} @ {order.limit_price}")
                else:
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
                    logger.info(f"placed order {order.client_id}: {result}")
            except Exception as e:
                err = f"order failed for {order.client_id}: {e}"
                logger.error(err)
                errors.append(err)

        return errors
