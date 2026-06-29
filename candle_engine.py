from datetime import datetime, timezone
from zoneinfo import ZoneInfo


class Candle:
    """Represents a single OHLCV candle."""

    def __init__(self, open_price: float, timestamp: datetime):
        self.open = open_price
        self.high = open_price
        self.low = open_price
        self.close = open_price
        self.volume = 0.0
        self.timestamp = timestamp
        self.tick_count = 0

    def update(self, price: float, volume: float = 0.0):
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += volume
        self.tick_count += 1

    def is_bullish(self) -> bool:
        return self.close > self.open

    def is_bearish(self) -> bool:
        return self.close < self.open

    def body_pct(self) -> float:
        """Body size as % of open price."""
        return abs(self.close - self.open) / self.open * 100 if self.open else 0.0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "tick_count": self.tick_count,
            "bullish": self.is_bullish(),
            "body_pct": round(self.body_pct(), 4),
        }


class CandleEngine:
    """
    Builds OHLCV candles from raw price ticks at configurable timeframes.
    Supports pattern detection on completed candles.
    """

    VALID_TIMEFRAMES = {1, 2, 3, 5, 10, 15, 30, 60}  # minutes

    def __init__(self, timeframe_minutes: int = 5, history_limit: int = 50):
        """
        Args:
            timeframe_minutes: Candle duration in minutes (default 5).
            history_limit: Max completed candles to retain per symbol.
        """
        if timeframe_minutes not in self.VALID_TIMEFRAMES:
            raise ValueError(f"timeframe_minutes must be one of {self.VALID_TIMEFRAMES}")

        self.timeframe_minutes = timeframe_minutes
        self.history_limit = history_limit
        self._current: dict[str, Candle] = {}
        self._completed: dict[str, list[Candle]] = {}

    def _candle_timestamp(self, dt: datetime) -> datetime:
        """Round a datetime down to the current candle boundary."""
        minutes = (dt.minute // self.timeframe_minutes) * self.timeframe_minutes
        return dt.replace(minute=minutes, second=0, microsecond=0)

    def update(self, symbol: str, price: float, volume: float = 0.0) -> dict:
        """
        Ingest a tick and update or open a candle for the symbol.

        Returns dict with current candle and completed candle info (if any).
        """
        now = datetime.now(ZoneInfo("America/New_York"))
        boundary = self._candle_timestamp(now)

        result = {"symbol": symbol, "current": None, "completed": None}

        if symbol not in self._current:
            # First tick — open the first candle
            self._current[symbol] = Candle(price, boundary)
        elif self._current[symbol].timestamp < boundary:
            # New candle period — close current, open new
            finished = self._current[symbol]
            if symbol not in self._completed:
                self._completed[symbol] = []
            self._completed[symbol].append(finished)
            if len(self._completed[symbol]) > self.history_limit:
                self._completed[symbol].pop(0)
            result["completed"] = finished.to_dict()
            self._current[symbol] = Candle(price, boundary)

        self._current[symbol].update(price, volume)
        result["current"] = self._current[symbol].to_dict()
        return result

    def current_candle(self, symbol: str) -> dict | None:
        """Return the live (incomplete) candle for a symbol."""
        c = self._current.get(symbol)
        return c.to_dict() if c else None

    def completed_candles(self, symbol: str, limit: int | None = None) -> list[dict]:
        """Return completed candles for a symbol, newest first."""
        candles = self._completed.get(symbol, [])
        result = [c.to_dict() for c in reversed(candles)]
        return result[:limit] if limit else result

    def last_completed(self, symbol: str) -> dict | None:
        """Return the most recently completed candle."""
        candles = self._completed.get(symbol, [])
        return candles[-1].to_dict() if candles else None

    def detect_pattern(self, symbol: str) -> dict:
        """
        Detect simple candle patterns from the last 3 completed candles.

        Patterns detected: engulfing, consecutive_run, doji.
        """
        candles = self._completed.get(symbol, [])
        if len(candles) < 2:
            return {"pattern": None, "reason": "Not enough candles"}

        last = candles[-1]
        prev = candles[-2]

        # Bullish engulfing
        if (prev.is_bearish() and last.is_bullish()
                and last.open <= prev.close and last.close >= prev.open):
            return {"pattern": "bullish_engulfing", "direction": "BUY",
                    "candle": last.to_dict()}

        # Bearish engulfing
        if (prev.is_bullish() and last.is_bearish()
                and last.open >= prev.close and last.close <= prev.open):
            return {"pattern": "bearish_engulfing", "direction": "SELL",
                    "candle": last.to_dict()}

        # Consecutive bullish run (last 3 green)
        if len(candles) >= 3:
            last3 = candles[-3:]
            if all(c.is_bullish() for c in last3):
                return {"pattern": "bullish_run", "direction": "BUY",
                        "candle": last.to_dict()}
            if all(c.is_bearish() for c in last3):
                return {"pattern": "bearish_run", "direction": "SELL",
                        "candle": last.to_dict()}

        # Doji (body < 0.05% of open)
        if last.body_pct() < 0.05:
            return {"pattern": "doji", "direction": None,
                    "candle": last.to_dict()}

        return {"pattern": None, "reason": "No pattern detected"}
