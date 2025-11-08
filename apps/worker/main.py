import asyncio
import logging
from datetime import datetime
import uuid
import numpy as np
from config import settings
from hyperliquid_client import HyperliquidClient
from openrouter_client import OpenRouterClient
from db import Database
from validator import Validator
from executor import Executor
from reconciler import Reconciler
from schemas import (
    Observation, MarketObservation, BookTop, Account, Position,
    Limits, Scoreboard, Action, TechnicalIndicators, FourHourContext,
    CompletedTrade, MarketRegime
)
from adapters import (
    BrokerAdapter, HyperliquidAdapter, PerpSimAdapter, PerpSimConfig,
    Order as AdapterOrder
)
from market import CoinbaseWebSocket
from market.coinbase_rest import prefill_candle_buffers
from indicators import get_recent_indicators, calculate_ema, calculate_macd, calculate_rsi, calculate_atr
from position_manager import PositionManager
from prompt_formatter import format_observation
from regime import RegimeAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class AgentWorker:
    """main agent loop: observe, plan, execute, reconcile"""

    def __init__(self):
        self.db = Database(settings.database_url)

        # create broker adapter based on TRADING_BACKEND env
        self.adapter = self._create_adapter()

        # coinbase ws feed for perpsim (will be initialized in start() with historical data)
        self.coinbase_ws = None
        self.perpsim_symbols = None
        if settings.trading_backend == "perpsim":
            self.perpsim_symbols = settings.sim_symbols.split(",")

        self.llm_client = OpenRouterClient()

        # validator uses adapter limits
        limits = self.adapter.limits()

        # build tick sizes map for all supported symbols (use per-symbol tick sizes)
        tick_sizes = settings.tick_sizes

        self.validator = Validator(
            min_notional=limits.min_notional,
            max_leverage=limits.max_leverage,
            tick_sizes=tick_sizes,
        )

        # executor and reconciler now use adapter directly
        # we'll update these modules later to accept adapters
        # for now, keep backward compatibility
        if settings.trading_backend == "hyperliquid":
            hl_client = HyperliquidClient(
                api_key=settings.hl_api_key,
                api_secret=settings.hl_api_secret,
                account=settings.hl_account,
                base_url=settings.hl_base_url,
            )
            self.executor = Executor(hl_client, self.db, dry_run=settings.dry_run)
            self.reconciler = Reconciler(hl_client, self.db)
        else:
            # perpsim mode - executor and reconciler will use adapter
            self.executor = None  # we'll execute directly via adapter
            self.reconciler = None  # we'll reconcile directly via adapter

        self.last_error = ""
        self.used_client_ids = set()
        self.client_id_aliases = {}
        self.actual_to_original = {}
        self.pending_aliases = {}

        # tracking for observation
        self.start_time = datetime.utcnow()
        self.invocation_count = 0
        self.initial_equity = 10000.0  # will be updated on first observation

        # position manager for translating decisions to orders
        self.position_manager = PositionManager(self.adapter, tick_sizes=tick_sizes)

        # regime analyzer for market condition analysis
        self.regime_analyzer = RegimeAnalyzer()

        logger.info(f"initialized with backend: {settings.trading_backend}")

    def _create_adapter(self) -> BrokerAdapter:
        """factory method to create the correct adapter"""
        if settings.trading_backend == "hyperliquid":
            hl_client = HyperliquidClient(
                api_key=settings.hl_api_key,
                api_secret=settings.hl_api_secret,
                account=settings.hl_account,
                base_url=settings.hl_base_url,
            )
            return HyperliquidAdapter(hl_client, self.db)

        elif settings.trading_backend == "perpsim":
            symbols = settings.sim_symbols.split(",")
            config = PerpSimConfig(
                im=settings.sim_im,
                mm=settings.sim_mm,
                max_leverage=settings.sim_max_leverage,
                slippage_bps=settings.sim_slippage_bps,
                fee_bps=settings.sim_fee_bps,
                liq_penalty_bps=settings.sim_liq_penalty_bps,
                funding_mode=settings.sim_funding_mode,
                symbols=symbols,
                data_source=settings.data_feed,
                min_notional=settings.min_notional,
                tick_size=settings.sim_tick_size,
            )
            return PerpSimAdapter(config, self.db)

        else:
            raise ValueError(f"unknown trading backend: {settings.trading_backend}")




    def _on_market_tick(self, symbol: str, best_bid: float, best_ask: float, ts: datetime):
        """callback for coinbase websocket ticks"""
        if isinstance(self.adapter, PerpSimAdapter):
            self.adapter.on_market_data(symbol, best_bid, best_ask, ts)

    async def _refresh_candles_periodically(self):
        """Background task to refresh 6h candles every 30 minutes to update volume data"""
        while True:
            try:
                await asyncio.sleep(1800)  # 30 minutes
                if self.coinbase_ws:
                    await self.coinbase_ws.refresh_6h_candles()
            except Exception as e:
                logger.error(f"Error refreshing candles: {e}")

    def _normalize_action_client_ids(self, action_dict: dict) -> dict:
        """ensure client ids are unique and cancellations reference active ids"""
        self.pending_aliases = {}
        seen_ids = set()
        actions = action_dict.get("actions", []) or []
        for order in actions:
            original = order.get("client_id") or str(uuid.uuid4())
            actual = original
            while actual in seen_ids or actual in self.used_client_ids:
                actual = f"{original}-{uuid.uuid4().hex[:8]}"
            order["client_id"] = actual
            seen_ids.add(actual)
            self.pending_aliases[actual] = original

        for cancel in action_dict.get("cancellations", []) or []:
            resolved = self._resolve_client_id(cancel.get("client_id"))
            cancel["client_id"] = resolved

        return action_dict

    def _resolve_client_id(self, client_id: str) -> str:
        """map llm-provided id to an active adapter id if needed"""
        if not client_id:
            return client_id
        if client_id in self.actual_to_original or client_id in self.used_client_ids:
            return client_id
        aliases = self.client_id_aliases.get(client_id)
        if aliases:
            return aliases[-1]
        for actual, original in reversed(list(self.pending_aliases.items())):
            if original == client_id:
                return actual
        return client_id

    def _register_client_id(self, actual_id: str):
        """record a client id after a successful placement"""
        original = self.pending_aliases.pop(actual_id, None)
        if original is None:
            original = self.actual_to_original.get(actual_id, actual_id)
        self.actual_to_original[actual_id] = original
        aliases = self.client_id_aliases.setdefault(original, [])
        if actual_id not in aliases:
            aliases.append(actual_id)
        self.used_client_ids.add(actual_id)

    def _release_client_id(self, actual_id: str):
        """remove bookkeeping for a client id after cancel or failure"""
        self.pending_aliases.pop(actual_id, None)
        self.used_client_ids.discard(actual_id)
        original = self.actual_to_original.pop(actual_id, None)
        if original:
            aliases = self.client_id_aliases.get(original)
            if aliases and actual_id in aliases:
                aliases.remove(actual_id)
                if not aliases:
                    self.client_id_aliases.pop(original, None)

    async def start(self):
        """connect to database and start main loop"""
        await self.db.connect()
        logger.info("agent worker started")

        # Register and activate this version
        config_snapshot = {
            "model": settings.openrouter_model,
            "trading_backend": settings.trading_backend,
            "symbols": settings.sim_symbols if settings.trading_backend == "perpsim" else "BTC-PERP,ETH-PERP",
            "max_leverage": settings.max_leverage,
            "cycle_interval": settings.cycle_interval_seconds,
        }

        self.version_id = await self.db.register_version(
            version_tag=settings.agent_version,
            description=settings.version_description,
            config=config_snapshot
        )
        await self.db.start_version_activity(self.version_id)

        logger.info(f"Running as version {settings.agent_version} (id={self.version_id})")

        # pre-fill historical candles and start coinbase ws if using perpsim
        if self.perpsim_symbols:
            logger.info(f"Pre-filling historical candles for {self.perpsim_symbols}...")

            # Fetch historical data (240 1m candles = 4 hours, 60 6h candles = ~15 days)
            # Note: Using 6h candles instead of 4h because Coinbase doesn't support 4h granularity
            candles_1m, candles_6h = await prefill_candle_buffers(
                symbols=self.perpsim_symbols,
                candle_1m_count=240,
                candle_6h_count=60,
            )

            logger.info(f"Historical candles loaded. 1m candles: {[(s, len(c)) for s, c in candles_1m.items()]}")
            logger.info(f"Historical candles loaded. 6h candles: {[(s, len(c)) for s, c in candles_6h.items()]}")

            # Create WebSocket with pre-filled buffers
            self.coinbase_ws = CoinbaseWebSocket(
                symbols=self.perpsim_symbols,
                on_tick=self._on_market_tick,
                ws_url=settings.coinbase_ws_url,
                prefilled_1m_candles=candles_1m,
                prefilled_4h_candles=candles_6h,  # Using 6h candles (Coinbase limitation)
            )

            asyncio.create_task(self.coinbase_ws.run_forever())
            logger.info("coinbase websocket started with historical data")

            # Start background task to refresh 6h candles every 30 minutes for volume data
            asyncio.create_task(self._refresh_candles_periodically())
            logger.info("candle refresh task started (every 30 minutes)")

            # wait for initial market data to arrive
            logger.info("waiting for live market data...")
            await asyncio.sleep(3)
            logger.info("live market data should be available")

        try:
            while True:
                await self.run_cycle()
                await asyncio.sleep(settings.cycle_interval_seconds)
        except KeyboardInterrupt:
            logger.info("shutting down...")
        finally:
            await self.cleanup()

    async def cleanup(self):
        """cleanup resources"""
        if self.coinbase_ws:
            await self.coinbase_ws.close()
        await self.adapter.close()
        await self.llm_client.close()
        await self.db.close()

    async def run_cycle(self):
        """single decision cycle"""
        cycle_id = str(uuid.uuid4())[:8]
        self.invocation_count += 1
        logger.info(f"=== cycle {cycle_id} start (invocation #{self.invocation_count}) ===")

        try:
            # 1. build observation
            obs = await self.build_observation()
            logger.info(f"observation: {obs.model_dump_json()}")

            # Format observation as string for saving
            observation_str = format_observation(obs)

            # 2. call llm
            action_dict = await self.llm_client.get_action(obs)
            logger.info(f"llm action: {action_dict}")

            # 3. detect action format and validate
            notes_for_audience = ""

            if "positions" in action_dict:
                # New position-based format
                position_action, error = self.validator.validate_position_action(action_dict)
                if error:
                    logger.error(f"validation error: {error}")
                    self.last_error = error
                    await self.db.set_metadata("last_error", error)
                    return

                notes_for_audience = position_action.notes_for_audience

                # 4. execute using position manager
                # Build market prices from observation
                market_prices = {m.symbol: m.mid for m in obs.markets}

                # Store exit plans and justifications BEFORE executing trades
                # so they're available when trades are recorded
                for coin, decision in position_action.positions.items():
                    symbol = f"{coin}-USD"
                    exit_plan_dict = decision.exit_plan.model_dump() if decision.exit_plan else None
                    await self.db.set_metadata(f"exit_plan_{symbol}", exit_plan_dict)

                    # Store justification for trade recording
                    # Only store if signal is not "hold" - hold signals don't result in trades
                    # and their justifications would be misleading if used for future trades
                    if decision.signal != "hold":
                        await self.db.set_metadata(f"justification_{symbol}", decision.justification)

                exec_errors = await self.position_manager.execute_position_decisions(
                    position_action.positions,
                    obs.account.positions,
                    obs.account.equity,
                    market_prices
                )

                if exec_errors:
                    self.last_error = "; ".join(exec_errors)
                    await self.db.set_metadata("last_error", self.last_error)
                    logger.error(f"Position execution errors: {self.last_error}")
                else:
                    self.last_error = ""
                    await self.db.set_metadata("last_error", "")

            else:
                # Old action-based format (backward compatibility)
                action_dict = self._normalize_action_client_ids(action_dict)
                action, error = self.validator.validate_action(action_dict)
                if error:
                    logger.error(f"validation error: {error}")
                    self.last_error = error
                    await self.db.set_metadata("last_error", error)
                    return

                notes_for_audience = action.notes_for_audience

                # 4. execute actions via adapter
                if settings.trading_backend == "hyperliquid":
                    # use existing executor
                    exec_errors = await self.executor.execute_action(action)
                    if exec_errors:
                        self.last_error = "; ".join(exec_errors)
                        await self.db.set_metadata("last_error", self.last_error)
                    else:
                        self.last_error = ""
                        await self.db.set_metadata("last_error", "")
                else:
                    # perpsim - execute directly via adapter
                    exec_errors = await self._execute_via_adapter(action)
                    if exec_errors:
                        self.last_error = "; ".join(exec_errors)
                        await self.db.set_metadata("last_error", self.last_error)
                    else:
                        self.last_error = ""
                        await self.db.set_metadata("last_error", "")

            # 5. save chat note with observation and action
            await self.db.insert_chat(
                datetime.utcnow(), notes_for_audience, cycle_id, observation_str, action_dict
            )

            # 6. reconcile positions and equity
            await asyncio.sleep(2)  # wait for fills
            if settings.trading_backend == "hyperliquid":
                await self.reconciler.reconcile()
            else:
                await self.adapter.reconcile()

            # 7. update scoreboard metadata
            await self.update_scoreboard()

            # 8. update version tags for all records
            await self.db.update_current_version_tags()

            # 9. calculate current version performance (every 10 cycles)
            if self.invocation_count % 10 == 0:
                if self.version_id:
                    await self.db.calculate_version_performance(self.version_id)

        except Exception as e:
            logger.error(f"cycle error: {e}", exc_info=True)
            self.last_error = str(e)
            await self.db.set_metadata("last_error", str(e))

        self.pending_aliases.clear()
        logger.info(f"=== cycle {cycle_id} end ===")

    async def _execute_via_adapter(self, action: Action) -> list[str]:
        """execute actions using adapter (for perpsim mode)"""
        errors = []

        # process cancellations
        for cancel in action.cancellations:
            client_id = cancel.client_id
            result = await self.adapter.cancel_order(client_id)
            if result.success:
                self._release_client_id(client_id)
            else:
                errors.append(f"cancel failed: {result.error}")

        # process orders
        for order_action in action.actions:
            if order_action.type != "place_order":
                continue

            client_id = order_action.client_id or str(uuid.uuid4())

            order = AdapterOrder(
                symbol=order_action.symbol,
                side=order_action.side,
                qty=order_action.qty,
                order_type=order_action.order_type,
                limit_price=order_action.limit_price,
                time_in_force=order_action.time_in_force,
                reduce_only=order_action.reduce_only,
                client_id=client_id,
            )

            result = await self.adapter.place_order(order)
            if result.success:
                self._register_client_id(order.client_id)
            else:
                self._release_client_id(order.client_id)
                errors.append(f"order failed: {result.error}")

        return errors

    async def build_observation(self) -> Observation:
        """build observation json from market and account data"""
        # determine symbols based on backend
        if settings.trading_backend == "perpsim":
            symbols = settings.sim_symbols.split(",")
        else:
            symbols = ["BTC-PERP", "ETH-PERP"]

        # fetch market data via adapter
        market_state = await self.adapter.get_market_state(symbols)
        markets = []

        for mkt in market_state.markets:
            logger.debug(f"Building observation for {mkt.symbol}: mark={mkt.mark:.2f}, bid={mkt.best_bid:.2f}, ask={mkt.best_ask:.2f}")
            # get candles from coinbase ws if perpsim, otherwise from hyperliquid
            if self.coinbase_ws:
                ohlcv_1m = self.coinbase_ws.get_candles(mkt.symbol)
            else:
                # fallback: fetch from hyperliquid (if available)
                # this is a simplified approach; in production you'd want a cleaner abstraction
                ohlcv_1m = []

            # realized vol (simplified from candles)
            realized_vol = 0.0
            if len(ohlcv_1m) >= 15:
                try:
                    returns = [np.log(ohlcv_1m[i][4] / ohlcv_1m[i-1][4]) for i in range(-15, 0)]
                    realized_vol = np.std(returns) * np.sqrt(60 * 24 * 365)
                except:
                    realized_vol = 0.0

            # calculate technical indicators from close prices
            tech_indicators = None
            if len(ohlcv_1m) >= 30:  # need sufficient data
                try:
                    close_prices = [candle[4] for candle in ohlcv_1m]  # close is index 4
                    ema_20, macd, rsi_7, rsi_14 = get_recent_indicators(close_prices, count=10)

                    if len(ema_20) > 0:
                        tech_indicators = TechnicalIndicators(
                            ema_20=ema_20,
                            macd=macd,
                            rsi_7=rsi_7,
                            rsi_14=rsi_14,
                            current_ema_20=ema_20[-1],
                            current_macd=macd[-1],
                            current_rsi_7=rsi_7[-1],
                        )
                except Exception as e:
                    logger.warning(f"Failed to calculate indicators for {mkt.symbol}: {e}")

            # calculate 6-hour context indicators (Coinbase doesn't support 4h, so we use 6h)
            four_hour_context = None
            if self.coinbase_ws:
                ohlcv_4h = self.coinbase_ws.get_4h_candles(mkt.symbol)
                if len(ohlcv_4h) >= 50:  # need sufficient data for 50-period EMA
                    try:
                        close_prices_4h = [candle[4] for candle in ohlcv_4h]
                        volumes_4h = [candle[5] for candle in ohlcv_4h]

                        # Calculate EMAs
                        ema_20_4h = calculate_ema(close_prices_4h, 20)
                        ema_50_4h = calculate_ema(close_prices_4h, 50)

                        # Calculate ATRs
                        atr_3_4h = calculate_atr(ohlcv_4h, 3)
                        atr_14_4h = calculate_atr(ohlcv_4h, 14)

                        # Calculate MACD and RSI series (last 10 values)
                        macd_4h = calculate_macd(close_prices_4h, 12, 26, 9)
                        rsi_14_4h = calculate_rsi(close_prices_4h, 14)

                        # Volume stats - filter out zeros from live candles that don't have volume
                        volumes_nonzero = [v for v in volumes_4h if v > 0]
                        current_volume = volumes_4h[-1] if volumes_4h else 0.0
                        avg_volume = np.mean(volumes_nonzero) if volumes_nonzero else 0.0

                        four_hour_context = FourHourContext(
                            ema_20=ema_20_4h[-1] if len(ema_20_4h) > 0 else 0.0,
                            ema_50=ema_50_4h[-1] if len(ema_50_4h) > 0 else 0.0,
                            atr_3=atr_3_4h[-1] if len(atr_3_4h) > 0 else 0.0,
                            atr_14=atr_14_4h[-1] if len(atr_14_4h) > 0 else 0.0,
                            current_volume=current_volume,
                            avg_volume=avg_volume,
                            macd=macd_4h[-10:] if len(macd_4h) >= 10 else macd_4h,
                            rsi_14=rsi_14_4h[-10:] if len(rsi_14_4h) >= 10 else rsi_14_4h,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to calculate 6H indicators for {mkt.symbol}: {e}")

            # Open interest: Only available for real perp exchanges, not Coinbase spot
            # Set to None for Coinbase data to avoid misleading the LLM with zeros
            open_interest_latest = None
            open_interest_avg = None

            markets.append(MarketObservation(
                symbol=mkt.symbol,
                mid=mkt.mark,
                spread_bps=mkt.spread_bps,
                ohlcv_1m=ohlcv_1m,
                realized_vol_15m=realized_vol,
                book_top=BookTop(bid_qty=mkt.bid_qty, ask_qty=mkt.ask_qty),
                funding_8h_rate=mkt.funding_8h_rate,
                open_interest=open_interest_latest,
                open_interest_avg=open_interest_avg,
                technical_indicators=tech_indicators,
                four_hour_context=four_hour_context,
            ))

        # fetch account data via adapter
        account_state = await self.adapter.get_account_state()

        # update initial equity on first observation
        if self.invocation_count == 1:
            self.initial_equity = account_state.equity

        # build market price map for positions
        market_prices = {m.symbol: m.mark for m in market_state.markets}

        positions = []
        for pos in account_state.positions:
            current_price = market_prices.get(pos.symbol, pos.avg_entry)

            # Use stored leverage from position
            leverage = pos.leverage

            # calculate unrealized P&L
            if pos.qty > 0:
                unrealized_pnl = pos.qty * (current_price - pos.avg_entry)
            else:
                unrealized_pnl = pos.qty * (current_price - pos.avg_entry)

            # estimate liquidation price (simplified)
            # for long: liq = entry * (1 - 1/leverage * maintenance_margin_fraction)
            # using 0.05 as maintenance margin
            if pos.qty > 0:
                liquidation_price = pos.avg_entry * (1 - (1 / leverage) * 0.95) if leverage > 0 else 0
            else:
                liquidation_price = pos.avg_entry * (1 + (1 / leverage) * 0.95) if leverage > 0 else 0

            # Calculate holding time
            entry_time = getattr(pos, 'entry_time', None)
            holding_time_minutes = None
            if entry_time:
                holding_time_minutes = int((datetime.utcnow() - entry_time).total_seconds() / 60)

            # Get exit plan from metadata
            exit_plan_dict = await self.db.get_metadata(f"exit_plan_{pos.symbol}")
            exit_plan = None
            if exit_plan_dict:
                try:
                    from schemas import ExitPlan
                    exit_plan = ExitPlan(**exit_plan_dict)
                except Exception as e:
                    logger.warning(f"Failed to parse exit plan for {pos.symbol}: {e}")

            positions.append(Position(
                symbol=pos.symbol,
                qty=pos.qty,
                avg_entry=pos.avg_entry,
                current_price=current_price,
                liquidation_price=max(0, liquidation_price),
                unrealized_pnl=unrealized_pnl,
                leverage=leverage,
                entry_time=entry_time,
                holding_time_minutes=holding_time_minutes,
                exit_plan=exit_plan,
            ))

        # calculate total return percentage
        total_return_pct = 0.0
        if self.initial_equity > 0:
            total_return_pct = ((account_state.equity - self.initial_equity) / self.initial_equity) * 100

        # calculate margin usage
        # used_margin = sum of initial margin for all positions
        # initial margin = notional / leverage (for cross-margin)
        used_margin = 0.0
        for pos in positions:
            notional = abs(pos.qty) * pos.current_price
            # Use the minimum of actual leverage or max leverage for margin calculation
            if pos.leverage and pos.leverage > 0:
                used_margin += notional / pos.leverage

        # available margin = equity - used_margin
        available_margin = max(0, account_state.equity - used_margin)

        account = Account(
            equity=account_state.equity,
            cash=available_margin,  # available margin to open new positions
            margin_balance=account_state.cash,  # total collateral balance
            used_margin=used_margin,  # margin locked in positions
            positions=positions,
            unrealized_pl=account_state.unrealized_pl,
            fees_paid_total=abs(account_state.fees),  # fees are negative in adapter
            total_return_pct=total_return_pct,
        )

        # get limits from adapter
        adapter_limits = self.adapter.limits()
        limits = Limits(
            min_notional=adapter_limits.min_notional,
            tick_size=adapter_limits.tick_size,
            max_leverage=adapter_limits.max_leverage,
        )

        # scoreboard with performance metrics
        pnl_all_time = account_state.realized_pl + account_state.unrealized_pl

        # Calculate comprehensive performance metrics for current version only
        perf_metrics_dict = await self.db.calculate_performance_metrics(version_id=self.version_id)
        sharpe_30d = await self.db.calculate_sharpe_ratio(days=30, version_id=self.version_id)
        max_dd = await self.db.calculate_max_drawdown(version_id=self.version_id)

        # Create PerformanceMetrics object
        from schemas import PerformanceMetrics
        performance = PerformanceMetrics(**perf_metrics_dict)

        scoreboard = Scoreboard(
            pnl_all_time=pnl_all_time,
            sharpe_30d=sharpe_30d,
            max_dd=max_dd,
            performance=performance,
        )

        # calculate minutes since start
        minutes_since_start = int((datetime.utcnow() - self.start_time).total_seconds() / 60)

        # update market prices in database
        await self.db.update_market_prices(market_prices)

        # fetch recent completed trades (last 10) for current version only
        recent_trades_raw = await self.db.get_completed_trades(limit=10, version_id=self.version_id)
        recent_trades = [
            CompletedTrade(
                symbol=trade["symbol"],
                direction=trade["direction"],
                entry_price=trade["entry_price"],
                exit_price=trade["exit_price"],
                qty=trade["qty"],
                net_pnl=trade["net_pnl"],
                holding_time_seconds=trade["holding_time_seconds"],
                entry_time=trade["entry_time"],
                exit_time=trade["exit_time"],
                entry_reason=trade.get("entry_reason"),
                exit_reason=trade.get("exit_reason"),
            )
            for trade in recent_trades_raw
        ]

        # Analyze market regime
        market_regime = self.regime_analyzer.analyze(markets)
        logger.info(f"Market regime: {market_regime.summary}")

        return Observation(
            timestamp=datetime.utcnow().isoformat(),
            minutes_since_start=minutes_since_start,
            invocation_count=self.invocation_count,
            markets=markets,
            account=account,
            limits=limits,
            scoreboard=scoreboard,
            last_error=self.last_error,
            recent_trades=recent_trades if recent_trades else None,
            market_regime=market_regime,
        )

    async def update_scoreboard(self):
        """update scoreboard metrics in metadata"""
        # For perpsim, use the sim_* values which are more accurate
        # For hyperliquid, calculate from trades
        if settings.trading_backend == "perpsim":
            sim_realized_str = await self.db.get_metadata("sim_realized")
            sim_fees_str = await self.db.get_metadata("sim_fees")
            realized_pnl = float(sim_realized_str) if sim_realized_str else 0.0
            fees_paid = float(sim_fees_str) if sim_fees_str else 0.0
        else:
            realized_pnl = await self.db.calculate_realized_pnl()
            fees_paid = await self.db.calculate_fees_paid()

        pnl_all_time = realized_pnl + fees_paid  # fees are already negative
        await self.db.set_metadata("pnl_all_time", pnl_all_time)
        await self.db.set_metadata("fees_paid_total", fees_paid)
        # max_dd calculation requires equity timeseries; placeholder here
        logger.info(f"scoreboard updated: pnl={pnl_all_time}, fees={fees_paid}")


async def main():
    worker = AgentWorker()
    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
