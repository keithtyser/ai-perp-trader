import asyncpg
from typing import List, Dict, Optional
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class Database:
    """async postgres client for agent state"""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """create connection pool"""
        self.pool = await asyncpg.create_pool(self.database_url, min_size=2, max_size=10)
        logger.info("database pool created")

    async def close(self):
        """close connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("database pool closed")

    async def insert_trade(
        self, symbol: str, side: str, qty: float, price: float, fee: float, client_id: str, ts: datetime
    ):
        """insert a filled trade"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                insert into trades (ts, symbol, side, qty, price, fee, client_id)
                values ($1, $2, $3, $4, $5, $6, $7)
                on conflict (client_id) do nothing
                """,
                ts, symbol, side, qty, price, fee, client_id,
            )

    async def upsert_position(self, symbol: str, qty: float, avg_entry: float, unrealized_pl: float, exit_plan: Optional[Dict] = None, leverage: float = 1.0):
        """update or insert position"""
        async with self.pool.acquire() as conn:
            if qty == 0:
                # close position
                await conn.execute("delete from positions where symbol = $1", symbol)
            else:
                # Check if this is a new position or position direction change
                existing = await conn.fetchrow("select qty, entry_time from positions where symbol = $1", symbol)

                if existing is None:
                    # New position - set entry_time
                    await conn.execute(
                        """
                        insert into positions (symbol, qty, avg_entry, unrealized_pl, exit_plan, leverage, entry_time, updated_at)
                        values ($1, $2, $3, $4, $5, $6, now(), now())
                        """,
                        symbol, qty, avg_entry, unrealized_pl, json.dumps(exit_plan) if exit_plan else None, leverage,
                    )
                elif (existing['qty'] > 0 and qty < 0) or (existing['qty'] < 0 and qty > 0):
                    # Direction change - reset entry_time
                    await conn.execute(
                        """
                        update positions
                        set qty = $2, avg_entry = $3, unrealized_pl = $4, exit_plan = $5, leverage = $6, entry_time = now(), updated_at = now()
                        where symbol = $1
                        """,
                        symbol, qty, avg_entry, unrealized_pl, json.dumps(exit_plan) if exit_plan else None, leverage,
                    )
                else:
                    # Same direction - preserve entry_time
                    await conn.execute(
                        """
                        update positions
                        set qty = $2, avg_entry = $3, unrealized_pl = $4, exit_plan = $5, leverage = $6, updated_at = now()
                        where symbol = $1
                        """,
                        symbol, qty, avg_entry, unrealized_pl, json.dumps(exit_plan) if exit_plan else None, leverage,
                    )

    async def get_positions(self) -> List[Dict]:
        """fetch all open positions"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("select symbol, qty, avg_entry, unrealized_pl, exit_plan, leverage, entry_time from positions")
            result = []
            for r in rows:
                pos = dict(r)
                # Parse exit_plan from JSON string to dict
                if pos.get('exit_plan'):
                    pos['exit_plan'] = json.loads(pos['exit_plan']) if isinstance(pos['exit_plan'], str) else pos['exit_plan']
                result.append(pos)
            return result

    async def insert_equity_snapshot(self, ts: datetime, equity: float, cash: float, unrealized_pl: float):
        """insert equity snapshot"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                insert into equity_snapshots (ts, equity, cash, unrealized_pl)
                values ($1, $2, $3, $4)
                on conflict (ts) do update set equity = $2, cash = $3, unrealized_pl = $4
                """,
                ts, equity, cash, unrealized_pl,
            )

    async def insert_chat(self, ts: datetime, content: str, cycle_id: str):
        """insert model chat note"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                "insert into model_chat (ts, content, cycle_id) values ($1, $2, $3)",
                ts, content, cycle_id,
            )

    async def get_metadata(self, key: str) -> Optional[any]:
        """get metadata value"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("select value from metadata where key = $1", key)
            if row:
                return json.loads(row["value"])
            return None

    async def set_metadata(self, key: str, value: any):
        """set metadata value"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                insert into metadata (key, value, updated_at)
                values ($1, $2, now())
                on conflict (key) do update set value = $2, updated_at = now()
                """,
                key, json.dumps(value),
            )

    async def get_trades(self, limit: int = 100) -> List[Dict]:
        """fetch recent trades"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "select * from trades order by ts desc limit $1", limit
            )
            return [dict(r) for r in rows]

    async def calculate_fees_paid(self) -> float:
        """sum all fees paid"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("select coalesce(sum(fee), 0) as total from trades")
            return float(row["total"])

    async def calculate_realized_pnl(self) -> float:
        """calculate realized pnl from trades (simplified fifo)"""
        # this is a simplified version; real impl would track fifo properly
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("select symbol, side, qty, price from trades order by ts")
            positions = {}
            realized = 0.0
            for r in rows:
                symbol = r["symbol"]
                if symbol not in positions:
                    positions[symbol] = {"qty": 0.0, "cost": 0.0}
                qty = float(r["qty"]) if r["side"] == "buy" else -float(r["qty"])
                price = float(r["price"])
                pos = positions[symbol]
                if pos["qty"] * qty < 0:
                    # closing trade
                    close_qty = min(abs(qty), abs(pos["qty"]))
                    avg_entry = pos["cost"] / pos["qty"] if pos["qty"] != 0 else 0
                    realized += close_qty * (price - avg_entry) * (1 if pos["qty"] > 0 else -1)
                    pos["qty"] += qty
                    pos["cost"] += qty * price
                else:
                    # opening trade
                    pos["qty"] += qty
                    pos["cost"] += qty * price
            return realized

    async def get_completed_trades(self, limit: int = 100) -> List[Dict]:
        """
        Calculate completed trades with full details.
        Returns list of dicts with: symbol, direction, entry_time, exit_time,
        entry_price, exit_price, qty, entry_notional, exit_notional, holding_time_seconds, net_pnl
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "select ts, symbol, side, qty, price, fee from trades order by ts"
            )

            positions = {}  # symbol -> {qty, cost, entry_time, entry_trades, fees}
            completed = []

            for r in rows:
                symbol = r["symbol"]
                side = r["side"]
                qty = float(r["qty"])
                price = float(r["price"])
                fee = float(r["fee"])
                ts = r["ts"]

                if symbol not in positions:
                    positions[symbol] = {
                        "qty": 0.0,
                        "cost": 0.0,
                        "entry_time": None,
                        "entry_trades": [],
                        "fees": 0.0
                    }

                pos = positions[symbol]
                signed_qty = qty if side == "buy" else -qty

                if pos["qty"] == 0:
                    # Opening new position
                    pos["qty"] = signed_qty
                    pos["cost"] = signed_qty * price
                    pos["entry_time"] = ts
                    pos["entry_trades"] = [(price, abs(signed_qty), fee)]
                    pos["fees"] = fee

                elif pos["qty"] * signed_qty > 0:
                    # Adding to position
                    pos["qty"] += signed_qty
                    pos["cost"] += signed_qty * price
                    pos["entry_trades"].append((price, abs(signed_qty), fee))
                    pos["fees"] += fee

                else:
                    # Closing or reversing position
                    close_qty = min(abs(signed_qty), abs(pos["qty"]))
                    direction = "long" if pos["qty"] > 0 else "short"

                    # Calculate average entry price
                    avg_entry = pos["cost"] / pos["qty"] if pos["qty"] != 0 else 0

                    # Calculate P&L for closed portion
                    if pos["qty"] > 0:
                        gross_pnl = close_qty * (price - avg_entry)
                    else:
                        gross_pnl = close_qty * (avg_entry - price)

                    # Pro-rate fees based on close quantity
                    close_ratio = close_qty / abs(pos["qty"])
                    allocated_fees = pos["fees"] * close_ratio + fee * (close_qty / abs(signed_qty))
                    net_pnl = gross_pnl - allocated_fees

                    # Calculate holding time
                    holding_time_seconds = (ts - pos["entry_time"]).total_seconds() if pos["entry_time"] else 0

                    # Calculate notionals
                    entry_notional = close_qty * abs(avg_entry)
                    exit_notional = close_qty * price

                    # Record completed trade
                    completed.append({
                        "symbol": symbol,
                        "direction": direction,
                        "entry_time": pos["entry_time"],
                        "exit_time": ts,
                        "entry_price": abs(avg_entry),
                        "exit_price": price,
                        "qty": close_qty,
                        "entry_notional": entry_notional,
                        "exit_notional": exit_notional,
                        "holding_time_seconds": holding_time_seconds,
                        "net_pnl": net_pnl
                    })

                    # Update position
                    pos["qty"] += signed_qty
                    if abs(pos["qty"]) < 1e-6:
                        # Position fully closed
                        pos["qty"] = 0.0
                        pos["cost"] = 0.0
                        pos["entry_time"] = None
                        pos["entry_trades"] = []
                        pos["fees"] = 0.0
                    else:
                        # Reduce cost proportionally or handle reversal
                        if pos["qty"] * signed_qty > 0:
                            # Reversal - new position in opposite direction
                            remaining_qty = abs(pos["qty"])
                            pos["cost"] = pos["qty"] * price
                            pos["entry_time"] = ts
                            pos["entry_trades"] = [(price, remaining_qty, fee * (remaining_qty / abs(signed_qty)))]
                            pos["fees"] = fee * (remaining_qty / abs(signed_qty))
                        else:
                            # Partial close
                            pos["cost"] *= (1 - close_ratio)
                            pos["fees"] *= (1 - close_ratio)

            # Return most recent completed trades first
            return list(reversed(completed))[-limit:]

    async def update_market_prices(self, prices: Dict[str, float]):
        """Update market prices for all symbols"""
        async with self.pool.acquire() as conn:
            for symbol, price in prices.items():
                await conn.execute(
                    """
                    insert into market_prices (symbol, price, updated_at)
                    values ($1, $2, now())
                    on conflict (symbol) do update set price = $2, updated_at = now()
                    """,
                    symbol, price,
                )
