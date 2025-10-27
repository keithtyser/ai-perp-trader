"""Format observation data into human-readable prompt for the LLM"""
from schemas import Observation
from datetime import datetime


def format_observation(obs: Observation) -> str:
    """Format observation into detailed, readable text prompt"""

    # Parse timestamp
    try:
        ts = datetime.fromisoformat(obs.timestamp.replace('Z', '+00:00'))
        time_str = ts.strftime('%Y-%m-%d %H:%M:%S.%f')
    except:
        time_str = obs.timestamp

    # Build header
    prompt = f"""It has been {obs.minutes_since_start} minutes since you started trading. The current time is {time_str} and you've been invoked {obs.invocation_count} times. Below, we are providing you with a variety of state data, price data, and predictive signals so you can discover alpha. Below that is your current account information, value, performance, positions, etc.

ALL OF THE PRICE OR SIGNAL DATA BELOW IS ORDERED: OLDEST → NEWEST

Timeframes note: Unless stated otherwise in a section title, intraday series are provided at 1-minute intervals. If a coin uses a different interval, it is explicitly stated in that coin's section.

CURRENT MARKET STATE FOR ALL COINS
"""

    # Format each market
    for market in obs.markets:
        coin = market.symbol.replace('-USD', '')

        # Extract latest values
        latest_price = market.mid

        # Get technical indicators if available
        if market.technical_indicators:
            ti = market.technical_indicators
            current_ema20 = ti.current_ema_20
            current_macd = ti.current_macd
            current_rsi7 = ti.current_rsi_7
            ema_20_series = ti.ema_20
            macd_series = ti.macd
            rsi_7_series = ti.rsi_7
            rsi_14_series = ti.rsi_14
            indicators_available = True
        else:
            current_ema20 = None
            current_macd = None
            current_rsi7 = None
            ema_20_series = []
            macd_series = []
            rsi_7_series = []
            rsi_14_series = []
            indicators_available = False

        prompt += f"""ALL {coin} DATA
current_price = {latest_price}"""

        if indicators_available:
            prompt += f""", current_ema20 = {current_ema20}, current_macd = {current_macd}, current_rsi (7 period) = {current_rsi7}

"""
        else:
            prompt += f"""
Technical indicators (EMA, MACD, RSI): Not yet available - insufficient candle data (need 30+ candles)

"""

        # Extract price series from OHLCV
        if market.ohlcv_1m and len(market.ohlcv_1m) > 0:
            # Get last 10 candles
            recent_candles = market.ohlcv_1m[-10:] if len(market.ohlcv_1m) >= 10 else market.ohlcv_1m

            # Extract mid prices (using close)
            mid_prices = [round(candle[4], 3) for candle in recent_candles]  # close prices
            prompt += f"Intraday series (1-minute intervals, oldest → latest):\n\n"
            prompt += f"Mid prices: {mid_prices}\n\n"

            # Historical indicator series
            if len(ema_20_series) > 0:
                ema_formatted = [round(val, 3) for val in ema_20_series]
                prompt += f"EMA indicators (20-period): {ema_formatted}\n\n"

            if len(macd_series) > 0:
                macd_formatted = [round(val, 3) for val in macd_series]
                prompt += f"MACD indicators: {macd_formatted}\n\n"

            if len(rsi_7_series) > 0:
                rsi_7_formatted = [round(val, 3) for val in rsi_7_series]
                prompt += f"RSI indicators (7-Period): {rsi_7_formatted}\n\n"

            if len(rsi_14_series) > 0:
                rsi_14_formatted = [round(val, 3) for val in rsi_14_series]
                prompt += f"RSI indicators (14-Period): {rsi_14_formatted}\n\n"

        # 4-hour timeframe context
        if market.four_hour_context:
            ctx = market.four_hour_context
            prompt += f"""Longer-term context (4-hour timeframe):

20-Period EMA: {round(ctx.ema_20, 3)} vs. 50-Period EMA: {round(ctx.ema_50, 3)}

3-Period ATR: {round(ctx.atr_3, 3)} vs. 14-Period ATR: {round(ctx.atr_14, 3)}

Current Volume: {round(ctx.current_volume, 3)} vs. Average Volume: {round(ctx.avg_volume, 3)}

"""
            if len(ctx.macd) > 0:
                macd_4h_formatted = [round(val, 3) for val in ctx.macd]
                prompt += f"MACD indicators (4-hour): {macd_4h_formatted}\n\n"

            if len(ctx.rsi_14) > 0:
                rsi_14_4h_formatted = [round(val, 3) for val in ctx.rsi_14]
                prompt += f"RSI indicators (14-Period, 4-hour): {rsi_14_4h_formatted}\n\n"

        # Open interest and funding
        prompt += f"""In addition, here is the latest {coin} open interest and funding rate for perps (the instrument you are trading):

"""

        if market.open_interest is not None and market.open_interest_avg is not None:
            prompt += f"Open Interest: Latest: {round(market.open_interest, 2)}, Average: {round(market.open_interest_avg, 2)}\n\n"
        elif market.open_interest is not None:
            prompt += f"Open Interest: Latest: {round(market.open_interest, 2)}\n\n"
        else:
            prompt += f"Open Interest: N/A\n\n"

        prompt += f"Funding Rate: {market.funding_8h_rate}\n\n"

        prompt += f"Spread (bps): {market.spread_bps}\n"
        prompt += f"Realized Volatility (15m): {market.realized_vol_15m}\n\n"

    # Format account information
    acc = obs.account

    prompt += """HERE IS YOUR ACCOUNT INFORMATION & PERFORMANCE
"""

    # Calculate return percentage
    return_pct = acc.total_return_pct if hasattr(acc, 'total_return_pct') else 0.0

    prompt += f"""Current Total Return (percent): {return_pct:.2f}%

Available Cash: {acc.cash:.2f}

Current Account Value: {acc.equity:.2f}

Margin Balance: {acc.margin_balance:.2f}

Used Margin: {acc.used_margin:.2f}

Unrealized P&L: {acc.unrealized_pl:.2f}

Total Fees Paid: {acc.fees_paid_total:.2f}

"""

    # Format positions
    if acc.positions and len(acc.positions) > 0:
        prompt += "Current live positions & performance:\n\n"
        for pos in acc.positions:
            prompt += f"""Symbol: {pos.symbol.replace('-USD', '')}
Quantity: {pos.qty}
Entry Price: {pos.avg_entry}
Current Price: {pos.current_price if hasattr(pos, 'current_price') else 'N/A'}
Liquidation Price: {pos.liquidation_price if hasattr(pos, 'liquidation_price') else 'N/A'}
Unrealized P&L: {pos.unrealized_pnl}
Leverage: {pos.leverage if hasattr(pos, 'leverage') else 'N/A'}

"""
    else:
        prompt += "No open positions.\n\n"

    # Add performance metrics
    if obs.scoreboard:
        prompt += f"""Performance Metrics:
All-Time P&L: {obs.scoreboard.pnl_all_time:.2f}
Sharpe Ratio (30d): {obs.scoreboard.sharpe_30d:.3f}
Max Drawdown: {obs.scoreboard.max_dd:.2f}

"""

    # Add limits
    prompt += f"""Trading Limits:
Min Notional: ${obs.limits.min_notional}
Tick Size: {obs.limits.tick_size}
Max Leverage: {obs.limits.max_leverage}x

"""

    # Add any errors
    if obs.last_error:
        prompt += f"Last Error: {obs.last_error}\n\n"

    return prompt
