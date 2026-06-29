from datetime import datetime
from zoneinfo import ZoneInfo

from candle_engine import CandleEngine


class IndicatorEngine:
    """
    Computes technical indicators (EMA, VWAP, momentum) from OHLCV candles
    built by CandleEngine. Uses candle close prices for EMA and candle 
    price×volume for VWAP, giving smoother, noise-reduced signals.
    """

    def __init__(self, ema_period: int = 20, timeframe_minutes: int = 5):
        self.ema_period = ema_period
        self.candles = CandleEngine(timeframe_minutes=timeframe_minutes)
        self._ema_state: dict[str, float | None] = {}
        self._vwap_state: dict[str, dict] = {}

    def update(self, symbol: str, price: float, volume: float = 0.0) -> dict:
        """
        Ingest a price tick, update candles, and recompute indicators.

        Returns computed indicators using candle data.
        """
        result = self.candles.update(symbol, price, volume)

        # If a candle completed, update EMA and VWAP from it
        if result["completed"]:
            completed = result["completed"]
            self._update_ema(symbol, completed["close"])
            self._update_vwap(symbol, completed["close"], completed["volume"])

        # Use current candle close for live EMA/VWAP estimate
        current = result["current"]
        live_ema = self._calc_live_ema(symbol, current["close"])
        live_vwap = self._calc_live_vwap(symbol, current["close"], current["volume"])

        # Momentum from completed candle history
        completed_candles = self.candles.completed_candles(symbol)
        momentum_pct = self._calc_momentum(symbol, price, completed_candles)

        return {
            "symbol": symbol,
            "price": price,
            "ema": round(live_ema, 4) if live_ema is not None else None,
            "vwap": round(live_vwap, 4) if live_vwap is not None else None,
            "momentum_pct": round(momentum_pct, 4),
            "candle": current,
            "candle_completed": result["completed"] is not None,
        }

    def get(self, symbol: str) -> dict:
        """Return latest computed indicators without ingesting a new tick."""
        current = self.candles.current_candle(symbol)
        if not current:
            return {}

        price = current["close"]
        live_ema = self._calc_live_ema(symbol, price)
        live_vwap = self._calc_live_vwap(symbol, price, current["volume"])
        completed_candles = self.candles.completed_candles(symbol)
        momentum_pct = self._calc_momentum(symbol, price, completed_candles)

        return {
            "symbol": symbol,
            "price": price,
            "ema": round(live_ema, 4) if live_ema is not None else None,
            "vwap": round(live_vwap, 4) if live_vwap is not None else None,
            "momentum_pct": round(momentum_pct, 4),
            "candle": current,
        }

    def detect_pattern(self, symbol: str) -> dict:
        """Delegate pattern detection to the underlying CandleEngine."""
        return self.candles.detect_pattern(symbol)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _update_ema(self, symbol: str, close: float):
        """Apply EMA smoothing using a completed candle's close price."""
        k = 2.0 / (self.ema_period + 1)
        prev = self._ema_state.get(symbol)
        if prev is None:
            self._ema_state[symbol] = close
        else:
            self._ema_state[symbol] = close * k + prev * (1 - k)

    def _calc_live_ema(self, symbol: str, current_close: float) -> float | None:
        """Blend the stored EMA with the current candle's close (not persisted)."""
        stored = self._ema_state.get(symbol)
        if stored is None:
            return current_close
        k = 2.0 / (self.ema_period + 1)
        return current_close * k + stored * (1 - k)

    def _update_vwap(self, symbol: str, close: float, volume: float):
        """Accumulate price×volume for VWAP from completed candles."""
        today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
        state = self._vwap_state.get(symbol)

        if state is None or state.get("date") != today:
            self._vwap_state[symbol] = {
                "date": today,
                "cum_pv": 0.0,
                "cum_vol": 0.0,
            }
            state = self._vwap_state[symbol]

        if volume > 0:
            state["cum_pv"] += close * volume
            state["cum_vol"] += volume

    def _calc_live_vwap(self, symbol: str, close: float, volume: float) -> float | None:
        """Compute VWAP including the current incomplete candle's contribution."""
        today = datetime.now(ZoneInfo("America/New_York")).date().isoformat()
        state = self._vwap_state.get(symbol)

        if state is None or state.get("date") != today:
            return close  # No history yet — seed with current price

        cum_pv = state["cum_pv"] + (close * volume if volume > 0 else 0)
        cum_vol = state["cum_vol"] + (volume if volume > 0 else 0)

        if cum_vol > 0:
            return cum_pv / cum_vol
        return close

    def _calc_momentum(self, symbol: str, current_price: float, completed: list) -> float:
        """% change from the oldest completed candle's open to current price."""
        if not completed:
            return 0.0
        oldest_close = completed[-1]["close"]  # list is newest-first
        if oldest_close == 0:
            return 0.0
        return ((current_price - oldest_close) / oldest_close) * 100
