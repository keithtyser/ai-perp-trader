"""Position manager to translate PositionDecisions into orders"""
import logging
import uuid
from typing import List, Dict, Optional
from datetime import datetime
from schemas import PositionDecision, Position
from adapters import Order as AdapterOrder, BrokerAdapter, PlacedOrder, CancelResult

logger = logging.getLogger(__name__)

# Minimum holding period in minutes before allowing position closure
MIN_HOLDING_PERIOD_MINUTES = 5


class PositionManager:
    """Manages positions and translates high-level decisions into orders"""

    def __init__(self, adapter: BrokerAdapter, tick_sizes: Dict[str, float]):
        self.adapter = adapter
        self.tick_sizes = tick_sizes

    def _round_to_tick(self, price: float, symbol: str) -> float:
        """Round price to nearest tick size for the given symbol"""
        tick_size = self.tick_sizes.get(symbol, 0.5)  # default to 0.5 if not found
        return round(price / tick_size) * tick_size

    async def execute_position_decisions(
        self,
        decisions: Dict[str, PositionDecision],
        current_positions: List[Position],
        current_equity: float,
        market_prices: Dict[str, float],
    ) -> List[str]:
        """
        Execute position decisions by generating and placing orders

        Args:
            decisions: Dict of coin -> PositionDecision
            current_positions: List of current Position objects
            current_equity: Current account equity
            market_prices: Dict of symbol -> current price

        Returns:
            List of error messages (empty if all successful)
        """
        errors = []

        # Build map of current positions
        current_pos_map = {pos.symbol: pos for pos in current_positions}

        # Calculate current used margin
        used_margin = 0.0
        for pos in current_positions:
            notional = abs(pos.qty) * market_prices.get(pos.symbol, pos.avg_entry)
            if pos.leverage and pos.leverage > 0:
                used_margin += notional / pos.leverage

        available_margin = max(0, current_equity - used_margin)

        for coin, decision in decisions.items():
            # Determine symbol format (BTC-USD vs BTC-PERP)
            symbol = f"{coin}-USD"  # Adjust based on your exchange

            # Get current position
            current_pos = current_pos_map.get(symbol)
            current_qty = current_pos.qty if current_pos else 0.0

            try:
                # Handle different signals
                if decision.signal == "close":
                    # Close entire position
                    if current_qty != 0:
                        # Log warning for early exits (informational only, don't block)
                        if current_pos and hasattr(current_pos, 'entry_time') and current_pos.entry_time:
                            holding_time_minutes = (datetime.utcnow() - current_pos.entry_time).total_seconds() / 60
                            if holding_time_minutes < MIN_HOLDING_PERIOD_MINUTES:
                                logger.warning(
                                    f"{coin}: Early exit after only {holding_time_minutes:.1f} minutes. "
                                    f"This may incur unnecessary fees (~4bps round-trip). "
                                    f"Entry: ${current_pos.avg_entry:.2f}, Current: ${market_prices.get(symbol, 0):.2f}"
                                )

                        await self._close_position(symbol, current_qty, errors)

                elif decision.signal == "hold":
                    # Keep position as is - agent has full autonomy to manage it
                    # No automatic stop-loss or take-profit orders
                    pass

                elif decision.signal in ["buy", "sell"]:
                    # Get current market price
                    current_price = market_prices.get(symbol)
                    if not current_price:
                        errors.append(f"{coin}: Cannot calculate quantity without current price")
                        logger.error(f"{coin}: Cannot calculate quantity without current price")
                        continue

                    # Calculate margin freed up if we close the current position
                    freed_margin = 0.0
                    if current_qty != 0 and current_pos and current_pos.leverage:
                        current_notional = abs(current_qty) * current_price
                        freed_margin = current_notional / current_pos.leverage

                    # Calculate available margin including freed margin
                    effective_available = available_margin + freed_margin

                    # Check if we have any margin to work with (unless closing existing position)
                    if current_qty == 0 and effective_available < 1.0:
                        # Trying to open new position with no margin
                        error_msg = (
                            f"{coin}: Insufficient margin to open position. "
                            f"Requested {decision.leverage}x leverage "
                            f"(${current_equity * decision.leverage:.2f} notional), "
                            f"but only ${effective_available:.2f} margin available"
                        )
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        continue

                    # Calculate target notional based on agent's requested leverage
                    # But constrain it to available margin
                    requested_notional = current_equity * decision.leverage
                    max_notional = effective_available * decision.leverage

                    # Use the minimum of what they requested vs what's actually available
                    target_notional = min(requested_notional, max_notional)

                    if target_notional < effective_available:
                        # Not enough margin even for 1x
                        error_msg = (
                            f"{coin}: Insufficient margin. Requested {decision.leverage}x "
                            f"(${requested_notional:.0f}), available margin: ${effective_available:.2f}"
                        )
                        errors.append(error_msg)
                        logger.warning(error_msg)
                        continue

                    target_quantity = target_notional / current_price

                    # Apply sign based on direction
                    target_qty = target_quantity if decision.signal == "buy" else -target_quantity
                    delta_qty = target_qty - current_qty

                    if abs(delta_qty) > 1e-6:
                        # Need to adjust position
                        side = "buy" if delta_qty > 0 else "sell"
                        qty = abs(delta_qty)

                        # Use MARKET orders for entries to ensure immediate fill at current price
                        order = AdapterOrder(
                            symbol=symbol,
                            side=side,
                            qty=qty,
                            order_type="market",
                            limit_price=None,
                            time_in_force="ioc",
                            reduce_only=False,
                            client_id=str(uuid.uuid4()),
                            leverage=decision.leverage,
                        )

                        result = await self.adapter.place_order(order)
                        if not result.success:
                            errors.append(f"{coin}: Failed to place {side} order: {result.error}")
                            continue

                        # Update available margin after placing order
                        new_margin_required = target_notional / decision.leverage
                        available_margin = available_margin + freed_margin - new_margin_required

                        logger.info(
                            f"{coin}: Placed {side} market order for {qty} "
                            f"(notional: ${target_notional:.0f}, margin: ${new_margin_required:.0f})"
                        )

                    # Agent has full autonomy - no automatic exit orders

            except Exception as e:
                errors.append(f"{coin}: Exception while executing: {str(e)}")
                logger.error(f"{coin}: Exception while executing decision", exc_info=True)

        return errors

    async def _close_position(self, symbol: str, current_qty: float, errors: List[str]):
        """Close an entire position"""
        side = "sell" if current_qty > 0 else "buy"
        qty = abs(current_qty)

        order = AdapterOrder(
            symbol=symbol,
            side=side,
            qty=qty,
            order_type="market",
            limit_price=None,
            time_in_force="ioc",
            reduce_only=True,
            client_id=str(uuid.uuid4()),
        )

        result = await self.adapter.place_order(order)
        if not result.success:
            errors.append(f"{symbol}: Failed to close position: {result.error}")
        else:
            logger.info(f"{symbol}: Closed position of {current_qty}")

