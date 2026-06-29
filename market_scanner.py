from datetime import datetime
from zoneinfo import ZoneInfo

from indicator_engine import IndicatorEngine
from market_feed import MarketFeed


class MarketScanner:
    """
    Autonomous market scanner using IndicatorEngine candles and patterns
    for trading signal generation. Takes raw price ticks, builds candles,
    computes indicators, detects patterns, and scores trading opportunities.
    """

    def __init__(self, config: dict):
        self.config = config
        self.market_data = {}
        self.indicators = IndicatorEngine(
            ema_period=20,
            timeframe_minutes=config.get("scanner_candle_minutes", 5),
        )
        self.market_feed = MarketFeed(stale_seconds=300)
        self.trade_taken_today = False

    def now_et(self):
        return datetime.now(ZoneInfo("America/New_York"))

    def update_market(self, symbol: str, price: float, volume: float = 0.0, 
                      vwap: float | None = None, ema: float | None = None,
                      avg_volume: float | None = None):
        """
        Ingest a price tick: update candles, indicators, and market feed.
        External VWAP/EMA values are optional (IndicatorEngine computes internally).
        """
        # Build/update candles and compute EMA/VWAP from them
        indicator_result = self.indicators.update(symbol, price, volume)

        # Use computed indicators, fallback to externally provided values
        computed_vwap = indicator_result.get("vwap")
        computed_ema = indicator_result.get("ema")
        final_vwap = computed_vwap if computed_vwap is not None else vwap
        final_ema = computed_ema if computed_ema is not None else ema

        # Ingest into market feed (unified data aggregation)
        feed_data = self.market_feed.ingest(
            symbol=symbol,
            price=price,
            vwap=final_vwap,
            ema=final_ema,
            volume=volume,
            avg_volume=avg_volume,
            source="scanner",
        )

        # Store for scoring
        self.market_data[symbol] = {
            **feed_data,
            "indicator_snapshot": indicator_result,
            "candle": indicator_result.get("candle"),
            "pattern": self.indicators.detect_pattern(symbol),
        }

    def score_symbol(self, symbol: str) -> dict:
        """
        Score a symbol using momentum, candle patterns, and technical alignment.
        Patterns (engulfing, runs) are strong BUY/SELL signals.
        """
        data = self.market_data.get(symbol)
        if not data:
            return {
                "symbol": symbol,
                "direction": None,
                "score": 0,
                "price": None,
                "reasons": ["No market data"],
            }

        price = data.get("price", 0)
        vwap = data.get("vwap")
        ema = data.get("ema")
        momentum_pct = data.get("momentum_pct", 0)
        pattern = data.get("pattern", {})
        candle = data.get("candle", {})

        score = 0
        direction = None
        reasons = []
        min_momentum = self.config.get("scanner_min_momentum_pct", 0.15)

        # Pattern-based signals (high confidence)
        pattern_name = pattern.get("pattern")
        if pattern_name == "bullish_engulfing":
            direction = "BUY"
            score += 50
            reasons.append("Bullish engulfing pattern")
        elif pattern_name == "bearish_engulfing":
            direction = "SELL"
            score += 50
            reasons.append("Bearish engulfing pattern")
        elif pattern_name == "bullish_run":
            direction = "BUY"
            score += 35
            reasons.append("Bullish run (3 green candles)")
        elif pattern_name == "bearish_run":
            direction = "SELL"
            score += 35
            reasons.append("Bearish run (3 red candles)")

        # Momentum-based signals (medium confidence)
        if momentum_pct >= min_momentum and not direction:
            direction = "BUY"
            score += 30
            reasons.append(f"Bullish momentum +{momentum_pct:.2f}%")
        elif momentum_pct <= -min_momentum and not direction:
            direction = "SELL"
            score += 30
            reasons.append(f"Bearish momentum {momentum_pct:.2f}%")

        if not direction:
            return {
                "symbol": symbol,
                "direction": None,
                "score": 0,
                "price": price,
                "reasons": ["No clear signal"],
                "indicators": data,
            }

        # Technical confirmations (add to score)
        if direction == "BUY":
            if vwap and price > vwap:
                score += 20
                reasons.append("Price above VWAP")
            if ema and price > ema:
                score += 20
                reasons.append("Price above EMA")
            if candle.get("bullish"):
                score += 10
                reasons.append("Current candle bullish")

        elif direction == "SELL":
            if vwap and price < vwap:
                score += 20
                reasons.append("Price below VWAP")
            if ema and price < ema:
                score += 20
                reasons.append("Price below EMA")
            if candle.get("bearish"):
                score += 10
                reasons.append("Current candle bearish")

        # Volume confirmation
        if data.get("volume", 0) > (data.get("avg_volume", 1) * 1.2):
            score += 15
            reasons.append("Volume confirmation")

        return {
            "symbol": symbol,
            "direction": direction,
            "score": min(score, 100),  # Cap at 100
            "momentum_pct": momentum_pct,
            "price": price,
            "reasons": reasons,
            "pattern": pattern,
            "candle": candle,
            "indicators": {k: v for k, v in data.items() if k not in ["indicator_snapshot", "pattern"]},
        }

    def best_market(self) -> dict | None:
        """Return the highest-scored trading opportunity across all symbols."""
        results = [self.score_symbol(symbol) for symbol in self.market_data]
        results = [r for r in results if r.get("direction")]  # Filter no-signal

        if not results:
            return None

        return max(results, key=lambda x: x["score"])

    def should_trade(self) -> dict:
        """Check if best market opportunity should be traded."""
        if self.trade_taken_today:
            return {
                "approved": False,
                "reason": "One trade per day limit reached",
                "best": None,
            }

        best = self.best_market()
        if not best:
            return {
                "approved": False,
                "reason": "No market opportunities found",
                "best": None,
            }

        min_score = self.config.get("scanner_min_score", 70)
        if best["score"] < min_score:
            return {
                "approved": False,
                "reason": f"Score {best['score']} below threshold {min_score}",
                "best": best,
            }

        self.trade_taken_today = True
        return {
            "approved": True,
            "reason": "All checks passed",
            "best": best,
        }
