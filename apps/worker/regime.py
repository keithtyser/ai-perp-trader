"""Market regime analyzer to determine current market conditions"""
import logging
from typing import List, Dict, Tuple
from schemas import MarketObservation, MarketRegime
import numpy as np

logger = logging.getLogger(__name__)


class RegimeAnalyzer:
    """Analyzes market data to determine current regime"""

    def analyze(self, markets: List[MarketObservation]) -> MarketRegime:
        """
        Analyze market observations to determine current regime

        Args:
            markets: List of MarketObservation for all traded assets

        Returns:
            MarketRegime with current market conditions
        """
        if not markets:
            return self._default_regime()

        # Calculate individual metrics
        trend_strength = self._calculate_trend_strength(markets)
        volatility_level = self._calculate_volatility_level(markets)
        risk_sentiment = self._calculate_risk_sentiment(markets)
        regime_type = self._determine_regime_type(markets, trend_strength)

        # Generate human-readable summary
        summary = self._generate_summary(regime_type, volatility_level, risk_sentiment, markets)

        return MarketRegime(
            regime_type=regime_type,
            volatility_level=volatility_level,
            trend_strength=trend_strength,
            risk_sentiment=risk_sentiment,
            summary=summary
        )

    def _calculate_trend_strength(self, markets: List[MarketObservation]) -> float:
        """
        Calculate overall trend strength across markets (0-100)
        Based on:
        - Price vs EMA positions
        - MACD values
        - Consistency across assets
        """
        trend_scores = []

        for market in markets:
            if not market.technical_indicators:
                continue

            ti = market.technical_indicators
            current_price = market.mid

            # Score 1: Price vs EMA-20
            if ti.current_ema_20 > 0:
                price_vs_ema = ((current_price - ti.current_ema_20) / ti.current_ema_20) * 100
                ema_score = min(abs(price_vs_ema) * 10, 50)  # Cap at 50
            else:
                ema_score = 0

            # Score 2: MACD magnitude
            macd_score = min(abs(ti.current_macd) * 20, 30)  # Cap at 30

            # Score 3: RSI deviation from 50 (trending markets have RSI away from 50)
            rsi_deviation = abs(ti.current_rsi_7 - 50)
            rsi_score = min(rsi_deviation / 2, 20)  # Cap at 20

            total_score = ema_score + macd_score + rsi_score
            trend_scores.append(total_score)

        if not trend_scores:
            return 0.0

        # Return average trend strength
        avg_strength = np.mean(trend_scores)
        return min(avg_strength, 100.0)

    def _calculate_volatility_level(self, markets: List[MarketObservation]) -> str:
        """
        Determine volatility level: low, moderate, high, extreme
        Based on:
        - Realized volatility (15m)
        - ATR values
        - Recent price ranges
        """
        volatility_scores = []

        for market in markets:
            # Use realized volatility
            vol_score = market.realized_vol_15m if market.realized_vol_15m else 0

            # Also consider 4H ATR if available
            if market.four_hour_context:
                ctx = market.four_hour_context
                # Normalize ATR by price
                if market.mid > 0:
                    atr_pct = (ctx.atr_14 / market.mid) * 100
                    vol_score = max(vol_score, atr_pct)

            volatility_scores.append(vol_score)

        if not volatility_scores:
            return "moderate"

        avg_vol = np.mean(volatility_scores)

        # Classify volatility
        if avg_vol < 0.5:
            return "low"
        elif avg_vol < 1.5:
            return "moderate"
        elif avg_vol < 3.0:
            return "high"
        else:
            return "extreme"

    def _calculate_risk_sentiment(self, markets: List[MarketObservation]) -> str:
        """
        Determine risk sentiment: risk_on, neutral, risk_off
        Based on:
        - Correlation of price movements
        - Overall directional bias
        - Volatility patterns
        """
        if not markets or len(markets) < 2:
            return "neutral"

        # Analyze recent price action (last 5 candles)
        price_changes = []
        for market in markets:
            if market.ohlcv_1m and len(market.ohlcv_1m) >= 5:
                recent_candles = market.ohlcv_1m[-5:]
                start_price = recent_candles[0][4]  # close of first candle
                end_price = recent_candles[-1][4]  # close of last candle
                if start_price > 0:
                    pct_change = ((end_price - start_price) / start_price) * 100
                    price_changes.append(pct_change)

        if not price_changes:
            return "neutral"

        # Calculate metrics
        avg_change = np.mean(price_changes)
        positive_count = sum(1 for x in price_changes if x > 0)
        negative_count = sum(1 for x in price_changes if x < 0)
        total_count = len(price_changes)

        # Determine sentiment
        # Risk-on: Most assets moving up together
        if positive_count >= total_count * 0.7 and avg_change > 0.3:
            return "risk_on"
        # Risk-off: Most assets moving down together
        elif negative_count >= total_count * 0.7 and avg_change < -0.3:
            return "risk_off"
        else:
            return "neutral"

    def _determine_regime_type(self, markets: List[MarketObservation], trend_strength: float) -> str:
        """
        Determine regime type based on trend analysis
        Returns: trending_up, trending_down, ranging, volatile_choppy
        """
        if trend_strength < 30:
            return "ranging"

        # Analyze directional bias
        up_count = 0
        down_count = 0

        for market in markets:
            if not market.technical_indicators:
                continue

            ti = market.technical_indicators
            current_price = market.mid

            # Price above EMA = up bias
            if current_price > ti.current_ema_20:
                up_count += 1
            else:
                down_count += 1

            # MACD confirmation
            if ti.current_macd > 0:
                up_count += 0.5
            else:
                down_count += 0.5

        total_votes = up_count + down_count
        if total_votes == 0:
            return "ranging"

        up_ratio = up_count / total_votes

        # Determine trend direction
        if up_ratio > 0.65 and trend_strength > 50:
            return "trending_up"
        elif up_ratio < 0.35 and trend_strength > 50:
            return "trending_down"
        elif trend_strength > 60:
            # High trend strength but mixed direction = choppy
            return "volatile_choppy"
        else:
            return "ranging"

    def _generate_summary(
        self,
        regime_type: str,
        volatility_level: str,
        risk_sentiment: str,
        markets: List[MarketObservation]
    ) -> str:
        """Generate human-readable summary of market regime"""

        # Map regime types to descriptions
        regime_descriptions = {
            "trending_up": "Trending Higher",
            "trending_down": "Trending Lower",
            "ranging": "Range-bound",
            "volatile_choppy": "Choppy/Volatile"
        }

        regime_desc = regime_descriptions.get(regime_type, regime_type)

        # Build summary components
        parts = [f"{volatility_level.title()} Volatility", regime_desc]

        # Add risk sentiment if notable
        if risk_sentiment == "risk_on":
            parts.append("Risk On")
        elif risk_sentiment == "risk_off":
            parts.append("Risk Off")

        # Add correlation insight
        correlation_insight = self._get_correlation_insight(markets)
        if correlation_insight:
            parts.append(correlation_insight)

        return " - ".join(parts)

    def _get_correlation_insight(self, markets: List[MarketObservation]) -> str:
        """Determine if assets are moving together or diverging"""
        if len(markets) < 2:
            return ""

        # Check if major assets have similar trends
        major_trends = []
        for market in markets:
            symbol = market.symbol.replace('-USD', '')
            # Focus on majors: BTC, ETH, SOL
            if symbol not in ['BTC', 'ETH', 'SOL']:
                continue

            if market.technical_indicators:
                ti = market.technical_indicators
                if market.mid > ti.current_ema_20:
                    major_trends.append(1)
                else:
                    major_trends.append(-1)

        if not major_trends:
            return ""

        # Calculate agreement
        if len(major_trends) >= 2:
            avg_trend = np.mean(major_trends)
            if abs(avg_trend) > 0.6:  # Strong agreement
                return "Majors Moving Together"
            else:
                return "Majors Diverging"

        return ""

    def _default_regime(self) -> MarketRegime:
        """Return default regime when no data available"""
        return MarketRegime(
            regime_type="ranging",
            volatility_level="moderate",
            trend_strength=0.0,
            risk_sentiment="neutral",
            summary="Insufficient data for regime analysis"
        )
