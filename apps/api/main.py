from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings
import asyncpg
from typing import List, Dict, Optional
from datetime import datetime
import json


class Settings(BaseSettings):
    database_url: str
    cors_origins: str = "*"

    class Config:
        env_file = ".env"


settings = Settings()
app = FastAPI(
    title="AI Perp Trader API",
    description="Read-only API for autonomous trading agent dashboard",
    version="1.0.0",
)

# cors
origins = settings.cors_origins.split(",") if settings.cors_origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# database pool
db_pool: Optional[asyncpg.Pool] = None


@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(settings.database_url, min_size=2, max_size=10)


@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()


async def get_current_version_id() -> Optional[int]:
    """Get the currently active version ID"""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT version_id
            FROM version_activity
            WHERE ended_at IS NULL
            ORDER BY started_at DESC
            LIMIT 1
        """)
        return row['version_id'] if row else None


@app.get("/health")
async def health():
    """health check endpoint"""
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.get("/equity-curve")
async def get_equity_curve(limit: int = Query(500, ge=1, le=5000)):
    """get equity curve snapshots for current version only"""
    version_id = await get_current_version_id()

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select ts, equity, cash, unrealized_pl,
                   coalesce(realized, 0) as realized,
                   coalesce(fees, 0) as fees,
                   coalesce(funding, 0) as funding
            from equity_snapshots
            where version_id = $1 or $1 is null
            order by ts desc limit $2
            """,
            version_id, limit,
        )
        return [
            {
                "ts": r["ts"].isoformat(),
                "equity": float(r["equity"]),
                "cash": float(r["cash"]),
                "unrealized_pl": float(r["unrealized_pl"]),
                "realized": float(r["realized"]),
                "fees": float(r["fees"]),
                "funding": float(r["funding"]),
            }
            for r in reversed(rows)
        ]


@app.get("/positions")
async def get_positions():
    """get current open positions"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "select symbol, qty, avg_entry, unrealized_pl, exit_plan, leverage, updated_at from positions"
        )
        result = []
        for r in rows:
            pos = {
                "symbol": r["symbol"],
                "qty": float(r["qty"]),
                "avg_entry": float(r["avg_entry"]),
                "unrealized_pl": float(r["unrealized_pl"]),
                "leverage": float(r["leverage"]) if r["leverage"] is not None else 1.0,
                "updated_at": r["updated_at"].isoformat(),
            }
            # Parse exit_plan from JSON if present
            if r["exit_plan"]:
                import json
                pos["exit_plan"] = json.loads(r["exit_plan"]) if isinstance(r["exit_plan"], str) else r["exit_plan"]
            else:
                pos["exit_plan"] = None
            result.append(pos)
        return result


@app.get("/trades")
async def get_trades(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """get individual trades for current version only"""
    version_id = await get_current_version_id()

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select id, ts, symbol, side, qty, price, fee, client_id
            from trades
            where version_id = $1 or $1 is null
            order by ts desc limit $2 offset $3
            """,
            version_id, limit, offset,
        )
        return [
            {
                "id": r["id"],
                "ts": r["ts"].isoformat(),
                "symbol": r["symbol"],
                "side": r["side"],
                "qty": float(r["qty"]),
                "price": float(r["price"]),
                "fee": float(r["fee"]),
                "client_id": r["client_id"],
            }
            for r in rows
        ]


@app.get("/completed-trades")
async def get_completed_trades(
    limit: int = Query(50, ge=1, le=500),
):
    """
    Get completed round-trip trades with full P&L details for current version only.
    Each entry represents a fully closed position with entry/exit info.
    """
    version_id = await get_current_version_id()

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select ts, symbol, side, qty, price, fee from trades
            where version_id = $1 or $1 is null
            order by ts
            """,
            version_id
        )

        positions = {}
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
                    "fees": 0.0
                }

            pos = positions[symbol]
            signed_qty = qty if side == "buy" else -qty

            if pos["qty"] == 0:
                # Opening new position
                pos["qty"] = signed_qty
                pos["cost"] = signed_qty * price
                pos["entry_time"] = ts
                pos["fees"] = fee

            elif pos["qty"] * signed_qty > 0:
                # Adding to position
                pos["qty"] += signed_qty
                pos["cost"] += signed_qty * price
                pos["fees"] += fee

            else:
                # Closing position
                close_qty = min(abs(signed_qty), abs(pos["qty"]))
                direction = "long" if pos["qty"] > 0 else "short"
                avg_entry = pos["cost"] / pos["qty"] if pos["qty"] != 0 else 0

                # Calculate P&L
                if pos["qty"] > 0:
                    gross_pnl = close_qty * (price - avg_entry)
                else:
                    gross_pnl = close_qty * (avg_entry - price)

                # Allocate fees
                close_ratio = close_qty / abs(pos["qty"])
                allocated_fees = pos["fees"] * close_ratio + fee * (close_qty / abs(signed_qty))
                net_pnl = gross_pnl - allocated_fees

                # Calculate holding time in seconds
                holding_time_seconds = (ts - pos["entry_time"]).total_seconds() if pos["entry_time"] else 0

                # Format holding time as human readable
                hours = int(holding_time_seconds // 3600)
                minutes = int((holding_time_seconds % 3600) // 60)
                holding_time_display = f"{hours}H {minutes}M" if hours > 0 else f"{minutes}M"

                # Calculate notionals
                entry_notional = close_qty * abs(avg_entry)
                exit_notional = close_qty * price

                completed.append({
                    "symbol": symbol,
                    "direction": direction,
                    "entry_time": pos["entry_time"].isoformat() if pos["entry_time"] else None,
                    "exit_time": ts.isoformat(),
                    "entry_price": abs(avg_entry),
                    "exit_price": price,
                    "qty": close_qty,
                    "entry_notional": entry_notional,
                    "exit_notional": exit_notional,
                    "holding_time_seconds": holding_time_seconds,
                    "holding_time_display": holding_time_display,
                    "gross_pnl": gross_pnl,
                    "fees": allocated_fees,
                    "net_pnl": net_pnl
                })

                # Update position
                pos["qty"] += signed_qty
                if abs(pos["qty"]) < 1e-6:
                    pos["qty"] = 0.0
                    pos["cost"] = 0.0
                    pos["entry_time"] = None
                    pos["fees"] = 0.0
                else:
                    if pos["qty"] * signed_qty > 0:
                        # Reversal
                        remaining_qty = abs(pos["qty"])
                        pos["cost"] = pos["qty"] * price
                        pos["entry_time"] = ts
                        pos["fees"] = fee * (remaining_qty / abs(signed_qty))
                    else:
                        # Partial close
                        pos["cost"] *= (1 - close_ratio)
                        pos["fees"] *= (1 - close_ratio)

        # Return most recent completed trades first
        return list(reversed(completed))[-limit:]


@app.get("/pl")
async def get_pl():
    """get profit/loss summary"""
    async with db_pool.acquire() as conn:
        # get metadata
        pnl_row = await conn.fetchrow("select value from metadata where key = 'pnl_all_time'")
        fees_row = await conn.fetchrow("select value from metadata where key = 'fees_paid_total'")
        dd_row = await conn.fetchrow("select value from metadata where key = 'max_dd'")

        # get current equity and unrealized
        equity_row = await conn.fetchrow(
            "select equity, unrealized_pl from equity_snapshots order by ts desc limit 1"
        )

        pnl_all_time = float(json.loads(pnl_row["value"])) if pnl_row else 0.0
        fees_paid_total = float(json.loads(fees_row["value"])) if fees_row else 0.0
        max_dd = float(json.loads(dd_row["value"])) if dd_row else 0.0
        current_equity = float(equity_row["equity"]) if equity_row else 0.0
        unrealized_pl = float(equity_row["unrealized_pl"]) if equity_row else 0.0

        # Calculate available cash (same logic as worker)
        # Get current positions to calculate used margin
        positions_rows = await conn.fetch(
            "select symbol, qty, avg_entry, leverage from positions"
        )

        # Get current market prices
        prices_rows = await conn.fetch("select symbol, price from market_prices")
        prices = {r["symbol"]: float(r["price"]) for r in prices_rows}

        # Calculate used margin: sum of (notional / leverage) for each position
        used_margin = 0.0
        for pos in positions_rows:
            symbol = pos["symbol"]
            qty = float(pos["qty"])
            avg_entry = float(pos["avg_entry"])
            leverage = float(pos["leverage"]) if pos["leverage"] else 1.0

            # Use current market price if available, otherwise use avg_entry
            current_price = prices.get(symbol, avg_entry)
            notional = abs(qty) * current_price

            if leverage > 0:
                used_margin += notional / leverage

        # Available cash = equity - used_margin
        available_cash = max(0.0, current_equity - used_margin)

        return {
            "pnl_all_time": pnl_all_time,
            "fees_paid_total": fees_paid_total,
            "max_drawdown": max_dd,
            "current_equity": current_equity,
            "unrealized_pl": unrealized_pl,
            "available_cash": available_cash,
        }


@app.get("/chat")
async def get_chat(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """get model chat notes for current version only"""
    version_id = await get_current_version_id()

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select id, ts, content, cycle_id, observation_prompt, action_response
            from model_chat
            where version_id = $1 or $1 is null
            order by ts desc limit $2 offset $3
            """,
            version_id, limit, offset,
        )
        return [
            {
                "id": r["id"],
                "ts": r["ts"].isoformat(),
                "content": r["content"],
                "cycle_id": r["cycle_id"],
                "observation_prompt": r["observation_prompt"],
                "action_response": r["action_response"],
            }
            for r in rows
        ]


@app.get("/metrics")
async def get_metrics():
    """get performance metrics summary for current version only"""
    version_id = await get_current_version_id()

    async with db_pool.acquire() as conn:
        # get metadata (already version-specific since it's reset per version)
        pnl_row = await conn.fetchrow("select value from metadata where key = 'pnl_all_time'")
        fees_row = await conn.fetchrow("select value from metadata where key = 'fees_paid_total'")
        dd_row = await conn.fetchrow("select value from metadata where key = 'max_dd'")

        # get sim-specific metadata if available
        sim_fees_row = await conn.fetchrow("select value from metadata where key = 'sim_fees'")
        sim_funding_row = await conn.fetchrow("select value from metadata where key = 'sim_funding'")
        sim_realized_row = await conn.fetchrow("select value from metadata where key = 'sim_realized'")

        # get current equity for current version only
        equity_row = await conn.fetchrow(
            """
            select equity, unrealized_pl from equity_snapshots
            where version_id = $1 or $1 is null
            order by ts desc limit 1
            """,
            version_id
        )

        pnl_all_time = float(json.loads(pnl_row["value"])) if pnl_row else 0.0
        fee_pct = float(json.loads(fees_row["value"])) if fees_row else 0.0
        max_dd = float(json.loads(dd_row["value"])) if dd_row else 0.0
        current_equity = float(equity_row["equity"]) if equity_row else 0.0

        # sim metrics
        sim_fees = float(json.loads(sim_fees_row["value"])) if sim_fees_row else 0.0
        funding_net = float(json.loads(sim_funding_row["value"])) if sim_funding_row else 0.0
        sim_realized = float(json.loads(sim_realized_row["value"])) if sim_realized_row else 0.0

        # calculate sharpe (placeholder - would need equity timeseries)
        sharpe_30d = 0.0

        return {
            "pnl_all_time": pnl_all_time,
            "sharpe_30d": sharpe_30d,
            "max_dd": max_dd,
            "fee_pct": fee_pct,
            "funding_net": funding_net,
            "current_equity": current_equity,
            "sim_fees": sim_fees,
            "sim_realized": sim_realized,
        }


@app.get("/market-prices")
async def get_market_prices():
    """get current market prices for all tracked symbols"""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            "select symbol, price, updated_at from market_prices order by symbol"
        )
        return {
            r["symbol"]: {
                "price": float(r["price"]),
                "updated_at": r["updated_at"].isoformat()
            }
            for r in rows
        }


@app.get("/performance-stats")
async def get_performance_stats():
    """
    Get comprehensive trading performance statistics for current version only.
    Includes win rate, profit factor, sharpe ratio, and more.
    """
    version_id = await get_current_version_id()

    async with db_pool.acquire() as conn:
        # Get all completed trades for current version to calculate metrics
        rows = await conn.fetch(
            """
            select ts, symbol, side, qty, price, fee from trades
            where version_id = $1 or $1 is null
            order by ts
            """,
            version_id
        )

        positions = {}
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
                    "fees": 0.0
                }

            pos = positions[symbol]
            signed_qty = qty if side == "buy" else -qty

            if pos["qty"] == 0:
                pos["qty"] = signed_qty
                pos["cost"] = signed_qty * price
                pos["entry_time"] = ts
                pos["fees"] = fee
            elif pos["qty"] * signed_qty > 0:
                pos["qty"] += signed_qty
                pos["cost"] += signed_qty * price
                pos["fees"] += fee
            else:
                # Closing trade
                close_qty = min(abs(signed_qty), abs(pos["qty"]))
                avg_entry = pos["cost"] / pos["qty"] if pos["qty"] != 0 else 0

                if pos["qty"] > 0:
                    gross_pnl = close_qty * (price - avg_entry)
                else:
                    gross_pnl = close_qty * (avg_entry - price)

                close_ratio = close_qty / abs(pos["qty"])
                allocated_fees = pos["fees"] * close_ratio + fee * (close_qty / abs(signed_qty))
                net_pnl = gross_pnl - allocated_fees

                holding_time_seconds = (ts - pos["entry_time"]).total_seconds() if pos["entry_time"] else 0
                entry_notional = close_qty * abs(avg_entry)

                completed.append({
                    "net_pnl": net_pnl,
                    "holding_time_seconds": holding_time_seconds,
                    "entry_notional": entry_notional
                })

                pos["qty"] += signed_qty
                if abs(pos["qty"]) < 1e-6:
                    pos["qty"] = 0.0
                    pos["cost"] = 0.0
                    pos["entry_time"] = None
                    pos["fees"] = 0.0
                else:
                    if pos["qty"] * signed_qty > 0:
                        remaining_qty = abs(pos["qty"])
                        pos["cost"] = pos["qty"] * price
                        pos["entry_time"] = ts
                        pos["fees"] = fee * (remaining_qty / abs(signed_qty))
                    else:
                        pos["cost"] *= (1 - close_ratio)
                        pos["fees"] *= (1 - close_ratio)

        # Calculate performance metrics
        if not completed:
            return {
                "win_rate": 0.0,
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "profit_factor": 0.0,
                "largest_win": 0.0,
                "largest_loss": 0.0,
                "avg_hold_time_minutes": 0.0,
                "total_volume": 0.0,
                "sharpe_30d": 0.0,
                "max_dd": 0.0,
            }

        winning_trades = [t for t in completed if t["net_pnl"] > 0]
        losing_trades = [t for t in completed if t["net_pnl"] < 0]

        total_trades = len(completed)
        num_wins = len(winning_trades)
        num_losses = len(losing_trades)

        win_rate = (num_wins / total_trades * 100) if total_trades > 0 else 0.0
        avg_win = sum(t["net_pnl"] for t in winning_trades) / num_wins if num_wins > 0 else 0.0
        avg_loss = sum(t["net_pnl"] for t in losing_trades) / num_losses if num_losses > 0 else 0.0
        profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else 0.0
        largest_win = max((t["net_pnl"] for t in winning_trades), default=0.0)
        largest_loss = min((t["net_pnl"] for t in losing_trades), default=0.0)
        avg_hold_time_minutes = sum(t["holding_time_seconds"] for t in completed) / len(completed) / 60.0
        total_volume = sum(t["entry_notional"] for t in completed)

        # Get Sharpe and max DD from equity curve for current version
        equity_rows = await conn.fetch(
            """
            select ts, equity from equity_snapshots
            where (version_id = $1 or $1 is null) and ts >= now() - interval '30 days'
            order by ts
            """,
            version_id
        )

        sharpe_30d = 0.0
        if len(equity_rows) >= 2:
            equities = [float(r["equity"]) for r in equity_rows]
            returns = []
            for i in range(1, len(equities)):
                if equities[i-1] != 0:
                    ret = (equities[i] - equities[i-1]) / equities[i-1]
                    returns.append(ret)

            if returns:
                import math
                mean_return = sum(returns) / len(returns)
                variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
                std_return = math.sqrt(variance)
                if std_return != 0:
                    sharpe_30d = (mean_return / std_return) * math.sqrt(1440 * 365)

        # Calculate max drawdown for current version
        all_equity_rows = await conn.fetch(
            """
            select equity from equity_snapshots
            where version_id = $1 or $1 is null
            order by ts
            """,
            version_id
        )
        max_dd = 0.0
        if len(all_equity_rows) >= 2:
            equities = [float(r["equity"]) for r in all_equity_rows]
            peak = equities[0]
            for equity in equities:
                if equity > peak:
                    peak = equity
                drawdown = (peak - equity) / peak * 100 if peak > 0 else 0.0
                max_dd = max(max_dd, drawdown)

        return {
            "win_rate": round(win_rate, 2),
            "total_trades": total_trades,
            "winning_trades": num_wins,
            "losing_trades": num_losses,
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "profit_factor": round(profit_factor, 2),
            "largest_win": round(largest_win, 2),
            "largest_loss": round(largest_loss, 2),
            "avg_hold_time_minutes": round(avg_hold_time_minutes, 1),
            "total_volume": round(total_volume, 2),
            "sharpe_30d": round(sharpe_30d, 3),
            "max_dd": round(max_dd, 2),
        }


@app.get("/leaderboard")
async def get_leaderboard(min_hours: float = Query(0, ge=0)):
    """
    Get version leaderboard showing performance of all agent versions.

    Args:
        min_hours: Minimum duration in hours to include (default: 0, show all)

    Returns:
        List of versions sorted by performance
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            select
                v.version_tag,
                v.description,
                v.deployed_at,
                v.retired_at,
                case when v.retired_at is null then true else false end as is_active,
                p.duration_days,
                p.total_cycles,
                p.total_return_pct,
                p.daily_return_pct,
                p.sharpe_ratio,
                p.max_drawdown_pct,
                p.total_trades,
                p.trades_per_day,
                p.win_rate,
                p.profit_factor,
                p.avg_hold_time_minutes,
                p.realized_pnl,
                p.total_fees,
                p.pnl_per_day,
                p.starting_equity,
                p.ending_equity
            from agent_versions v
            left join version_performance p on v.id = p.version_id
            where p.duration_days >= $1 / 24.0 or p.duration_days is null
            order by p.sharpe_ratio desc nulls last, p.total_return_pct desc nulls last
            """,
            min_hours
        )

        return [
            {
                "version_tag": r["version_tag"],
                "description": r["description"],
                "deployed_at": r["deployed_at"].isoformat() if r["deployed_at"] else None,
                "retired_at": r["retired_at"].isoformat() if r["retired_at"] else None,
                "is_active": r["is_active"],
                "duration_days": round(float(r["duration_days"]), 2) if r["duration_days"] else 0.0,
                "total_cycles": r["total_cycles"] or 0,
                "total_return_pct": round(float(r["total_return_pct"]), 2) if r["total_return_pct"] is not None else 0.0,
                "daily_return_pct": round(float(r["daily_return_pct"]), 2) if r["daily_return_pct"] is not None else 0.0,
                "sharpe_ratio": round(float(r["sharpe_ratio"]), 2) if r["sharpe_ratio"] is not None else 0.0,
                "max_drawdown_pct": round(float(r["max_drawdown_pct"]), 2) if r["max_drawdown_pct"] is not None else 0.0,
                "total_trades": r["total_trades"] or 0,
                "trades_per_day": round(float(r["trades_per_day"]), 1) if r["trades_per_day"] is not None else 0.0,
                "win_rate": round(float(r["win_rate"]), 1) if r["win_rate"] is not None else 0.0,
                "profit_factor": round(float(r["profit_factor"]), 2) if r["profit_factor"] is not None else 0.0,
                "avg_hold_time_minutes": round(float(r["avg_hold_time_minutes"]), 1) if r["avg_hold_time_minutes"] is not None else 0.0,
                "realized_pnl": round(float(r["realized_pnl"]), 2) if r["realized_pnl"] is not None else 0.0,
                "total_fees": round(float(r["total_fees"]), 2) if r["total_fees"] is not None else 0.0,
                "pnl_per_day": round(float(r["pnl_per_day"]), 2) if r["pnl_per_day"] is not None else 0.0,
                "starting_equity": round(float(r["starting_equity"]), 2) if r["starting_equity"] is not None else 0.0,
                "ending_equity": round(float(r["ending_equity"]), 2) if r["ending_equity"] is not None else 0.0,
            }
            for r in rows
        ]


@app.get("/current-version")
async def get_current_version():
    """Get the currently active agent version"""
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            select v.version_tag, v.description, v.deployed_at, va.started_at
            from version_activity va
            join agent_versions v on va.version_id = v.id
            where va.ended_at is null
            order by va.started_at desc
            limit 1
            """
        )

        if not row:
            return None

        return {
            "version_tag": row["version_tag"],
            "description": row["description"],
            "deployed_at": row["deployed_at"].isoformat(),
            "started_at": row["started_at"].isoformat(),
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
