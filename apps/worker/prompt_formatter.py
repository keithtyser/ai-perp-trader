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

"""

    # Add market regime context
    if obs.market_regime:
        regime = obs.market_regime
        prompt += f"""🌍 CURRENT MARKET REGIME
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{regime.summary}

Regime Type: {regime.regime_type.replace('_', ' ').title()}
Volatility Level: {regime.volatility_level.title()}
Trend Strength: {regime.trend_strength:.1f}/100
Risk Sentiment: {regime.risk_sentiment.replace('_', ' ').title()}

CONTEXT: This regime analysis summarizes the current market environment across all assets.
Consider this broader context when making your trading decisions. You may choose to adapt your
approach based on these conditions, or you may identify opportunities that contradict the regime.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""

    prompt += """CURRENT MARKET STATE FOR ALL COINS
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

        # 6-hour timeframe context (Note: Coinbase doesn't support 4h, so we use 6h)
        if market.four_hour_context:
            ctx = market.four_hour_context
            prompt += f"""Longer-term context (6-hour timeframe):

20-Period EMA: {round(ctx.ema_20, 3)} vs. 50-Period EMA: {round(ctx.ema_50, 3)}

3-Period ATR: {round(ctx.atr_3, 3)} vs. 14-Period ATR: {round(ctx.atr_14, 3)}

"""
            # Only show volume if it's available (> 0)
            if ctx.avg_volume > 0:
                prompt += f"Current Volume: {round(ctx.current_volume, 3)} vs. Average Volume: {round(ctx.avg_volume, 3)}\n\n"
            if len(ctx.macd) > 0:
                macd_6h_formatted = [round(val, 3) for val in ctx.macd]
                prompt += f"MACD indicators (6-hour): {macd_6h_formatted}\n\n"

            if len(ctx.rsi_14) > 0:
                rsi_14_6h_formatted = [round(val, 3) for val in ctx.rsi_14]
                prompt += f"RSI indicators (14-Period, 6-hour): {rsi_14_6h_formatted}\n\n"

        # Open interest and funding
        prompt += f"""In addition, here is the latest {coin} funding rate for perps (the instrument you are trading):

"""

        # Only show open interest if available (real perp exchanges)
        if market.open_interest is not None:
            if market.open_interest_avg is not None:
                prompt += f"Open Interest: Latest: {round(market.open_interest, 2)}, Average: {round(market.open_interest_avg, 2)}\n\n"
            else:
                prompt += f"Open Interest: Latest: {round(market.open_interest, 2)}\n\n"

        prompt += f"Funding Rate (8h): {market.funding_8h_rate}\n\n"

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
            holding_time_str = f"{pos.holding_time_minutes} minutes" if hasattr(pos, 'holding_time_minutes') and pos.holding_time_minutes is not None else "N/A"

            # Format exit plan if available
            exit_plan_str = ""
            if hasattr(pos, 'exit_plan') and pos.exit_plan:
                exit_plan_str = f"""Current Exit Plan:
  - Profit Target: ${pos.exit_plan.profit_target if pos.exit_plan.profit_target else 'N/A'}
  - Stop Loss: ${pos.exit_plan.stop_loss if pos.exit_plan.stop_loss else 'N/A'}
  - Invalidation Condition: {pos.exit_plan.invalidation_condition}
"""

            prompt += f"""Symbol: {pos.symbol.replace('-USD', '')}
Quantity: {pos.qty}
Entry Price: {pos.avg_entry}
Current Price: {pos.current_price if hasattr(pos, 'current_price') else 'N/A'}
Liquidation Price: {pos.liquidation_price if hasattr(pos, 'liquidation_price') else 'N/A'}
Unrealized P&L: {pos.unrealized_pnl}
Leverage: {pos.leverage if hasattr(pos, 'leverage') else 'N/A'}
Holding Time: {holding_time_str}
{exit_plan_str}
"""
    else:
        prompt += "No open positions.\n\n"

    # Format recent trades
    if obs.recent_trades and len(obs.recent_trades) > 0:
        prompt += """RECENT COMPLETED TRADES

Below are your most recent completed trades for reference and analysis.

"""
        for i, trade in enumerate(obs.recent_trades, 1):
            # Calculate R-multiple (profit relative to risk)
            # Assuming stop was halfway between entry and exit for losses
            price_move = abs(trade.exit_price - trade.entry_price)

            # Determine win/loss
            if trade.direction == "long":
                is_win = trade.exit_price > trade.entry_price
            else:  # short
                is_win = trade.exit_price < trade.entry_price

            result_label = "WIN" if is_win else "LOSS"

            # Calculate return percentage
            if trade.direction == "long":
                return_pct = ((trade.exit_price - trade.entry_price) / trade.entry_price) * 100
            else:  # short
                return_pct = ((trade.entry_price - trade.exit_price) / trade.entry_price) * 100

            # Format holding time
            holding_minutes = trade.holding_time_seconds / 60
            if holding_minutes < 60:
                holding_str = f"{holding_minutes:.1f} minutes"
            else:
                holding_hours = holding_minutes / 60
                holding_str = f"{holding_hours:.1f} hours"

            # Format entry and exit times with date
            try:
                entry_str = trade.entry_time.strftime('%Y-%m-%d %H:%M:%S')
                exit_str = trade.exit_time.strftime('%Y-%m-%d %H:%M:%S')
            except:
                entry_str = str(trade.entry_time)
                exit_str = str(trade.exit_time)

            prompt += f"""Trade #{i}: {trade.symbol.replace('-USD', '')} {trade.direction.upper()}
  Side: {trade.direction}
  Entry: ${trade.entry_price:.2f} at {entry_str}
  Exit: ${trade.exit_price:.2f} at {exit_str}
  Result: {result_label} - {return_pct:+.2f}% (${trade.net_pnl:+.2f} net after fees)
  Holding Time: {holding_str}
"""
            if hasattr(trade, 'entry_reason') and trade.entry_reason:
                prompt += f"  Entry Reason: {trade.entry_reason}\n"
            if hasattr(trade, 'exit_reason') and trade.exit_reason:
                prompt += f"  Exit Reason: {trade.exit_reason}\n"
            prompt += "\n"

    # Add performance metrics
    if obs.scoreboard:
        prompt += f"""PERFORMANCE METRICS & TRADING STATISTICS

Overall Performance:
All-Time P&L: ${obs.scoreboard.pnl_all_time:.2f}
Sharpe Ratio (30d): {obs.scoreboard.sharpe_30d:.3f}
Max Drawdown: {obs.scoreboard.max_dd:.2f}%

"""
        # Add detailed trading statistics if available
        if obs.scoreboard.performance:
            perf = obs.scoreboard.performance
            prompt += f"""Detailed Trading Statistics:
Total Completed Trades: {perf.total_trades}
Win Rate: {perf.win_rate:.1f}% ({perf.winning_trades} wins / {perf.losing_trades} losses)
Average Win: ${perf.avg_win:.2f}
Average Loss: ${perf.avg_loss:.2f}
Profit Factor: {perf.profit_factor:.2f} (avg_win / |avg_loss|)
Largest Win: ${perf.largest_win:.2f}
Largest Loss: ${perf.largest_loss:.2f}
Average Hold Time: {perf.avg_hold_time_minutes:.1f} minutes
Total Volume Traded: ${perf.total_volume:.2f}

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
