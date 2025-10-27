from typing import Dict, Optional
from schemas import Action, PlaceOrder, PositionAction, PositionDecision
from pydantic import ValidationError
import logging

logger = logging.getLogger(__name__)


class Validator:
    """validates llm actions against platform constraints"""

    def __init__(self, min_notional: float, max_leverage: float, tick_sizes: Dict[str, float]):
        self.min_notional = min_notional
        self.max_leverage = max_leverage
        self.tick_sizes = tick_sizes

    def validate_action(self, action_dict: Dict) -> tuple[Optional[Action], Optional[str]]:
        """validate action json and return error if any"""
        try:
            action = Action(**action_dict)
        except ValidationError as e:
            return None, f"schema validation failed: {e}"

        # check each order and ensure unique client ids within this request
        seen_client_ids = set()
        for order in action.actions:
            err = self._validate_order(order)
            if err:
                return None, err
            if order.client_id in seen_client_ids:
                return None, f"duplicate client_id in request: {order.client_id}"
            seen_client_ids.add(order.client_id)

        return action, None

    def _validate_order(self, order: PlaceOrder) -> Optional[str]:
        """validate a single order"""
        # limit price required for limit orders
        if order.order_type == "limit" and order.limit_price is None:
            return f"limit_price required for limit order {order.client_id}"

        # check tick size
        tick_size = self.tick_sizes.get(order.symbol, 0.1)
        if order.limit_price is not None:
            if not self._is_valid_tick(order.limit_price, tick_size):
                return f"limit_price {order.limit_price} does not match tick_size {tick_size}"

        # check min notional (estimate with limit price or assume current mid)
        notional = order.qty * (order.limit_price or 1.0)
        if notional < self.min_notional:
            return f"notional {notional} below min {self.min_notional}"

        # leverage check would require knowing current equity and positions
        # we skip it here; executor can enforce

        return None

    def _is_valid_tick(self, price: float, tick_size: float) -> bool:
        """check if price is a valid multiple of tick size"""
        remainder = price % tick_size
        return remainder < 1e-6 or (tick_size - remainder) < 1e-6

    def validate_position_action(self, action_dict: Dict) -> tuple[Optional[PositionAction], Optional[str]]:
        """validate position-based action format"""
        try:
            action = PositionAction(**action_dict)
        except ValidationError as e:
            return None, f"schema validation failed: {e}"

        # validate each position decision
        for coin, decision in action.positions.items():
            # validate coin matches
            if decision.coin != coin:
                return None, f"coin mismatch: key={coin}, decision.coin={decision.coin}"

            # validate leverage
            if decision.leverage > self.max_leverage:
                return None, f"{coin}: leverage {decision.leverage} exceeds max {self.max_leverage}"

            # validate tick size for exit plan prices (skip if None, which is allowed for close signals)
            symbol_with_suffix = f"{coin}-USD" if "USD" in list(self.tick_sizes.keys())[0] else f"{coin}-PERP"
            tick_size = self.tick_sizes.get(symbol_with_suffix, 0.5)

            if decision.exit_plan.profit_target is not None and not self._is_valid_tick(decision.exit_plan.profit_target, tick_size):
                return None, f"{coin}: profit_target {decision.exit_plan.profit_target} invalid for tick {tick_size}"

            if decision.exit_plan.stop_loss is not None and not self._is_valid_tick(decision.exit_plan.stop_loss, tick_size):
                return None, f"{coin}: stop_loss {decision.exit_plan.stop_loss} invalid for tick {tick_size}"

            # validate quantity makes sense
            if decision.signal in ["buy", "sell"] and decision.quantity <= 0:
                return None, f"{coin}: signal {decision.signal} requires quantity > 0"

            # validate confidence
            if decision.confidence < 0 or decision.confidence > 1:
                return None, f"{coin}: confidence {decision.confidence} must be 0-1"

        return action, None

