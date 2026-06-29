from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


class MarketFeed:
    """
    Aggregates and normalizes market data from various sources (TradingView, 
    IndicatorEngine, real-time feeds). Provides a unified interface for 
    the scanner to consume clean, deduplicated market data.
    """

    def __init__(self, stale_seconds: int = 300):
        """
        Args:
            stale_seconds: Age threshold after which a tick is considered stale
                          and excluded from analysis (default 5 minutes).
        """
        self.stale_seconds = stale_seconds
        self._feeds: dict[str, dict] = {}

    def ingest(
        self,
        symbol: str,
        price: float,
        vwap: float | None = None,
        ema: float | None = None,
        volume: float | None = None,
        avg_volume: float | None = None,
        source: str = "webhook",
    ) -> dict:
        """
        Ingest a market data tick from any source and update aggregate state.

        Args:
            symbol: Trading symbol (e.g., "ES1!")
            price: Current bid/ask or last price
            vwap: Volume-weighted average price
            ema: Exponential moving average
            volume: Current bar/tick volume
            avg_volume: Average volume
            source: Data source label ("webhook", "indicator_engine", "realtime", etc.)

        Returns:
            Normalized tick with all available fields and metadata.
        """
        if symbol not in self._feeds:
            self._feeds[symbol] = {
                "price": price,
                "vwap": vwap,
                "ema": ema,
                "volume": volume,
                "avg_volume": avg_volume,
                "source": source,
                "received_at": datetime.now(ZoneInfo("America/New_York")),
                "tick_count": 0,
            }
        else:
            feed = self._feeds[symbol]
            feed["price"] = price
            if vwap is not None:
                feed["vwap"] = vwap
            if ema is not None:
                feed["ema"] = ema
            if volume is not None:
                feed["volume"] = volume
            if avg_volume is not None:
                feed["avg_volume"] = avg_volume
            feed["source"] = source
            feed["received_at"] = datetime.now(ZoneInfo("America/New_York"))

        self._feeds[symbol]["tick_count"] += 1
        return self.get(symbol)

    def get(self, symbol: str) -> dict | None:
        """Return latest normalized data for a symbol, or None if stale."""
        feed = self._feeds.get(symbol)
        if not feed:
            return None

        age = (datetime.now(ZoneInfo("America/New_York")) - feed["received_at"]).total_seconds()
        if age > self.stale_seconds:
            return None  # Stale data

        return {
            "symbol": symbol,
            "price": feed["price"],
            "vwap": feed["vwap"],
            "ema": feed["ema"],
            "volume": feed["volume"],
            "avg_volume": feed["avg_volume"],
            "source": feed["source"],
            "received_at": feed["received_at"].isoformat(),
            "age_seconds": round(age, 2),
            "tick_count": feed["tick_count"],
        }

    def get_all_active(self) -> dict[str, dict]:
        """Return all non-stale market data across all symbols."""
        active = {}
        for symbol in self._feeds:
            data = self.get(symbol)
            if data:
                active[symbol] = data
        return active

    def clear_symbol(self, symbol: str) -> None:
        """Clear all data for a symbol (useful for daily resets)."""
        if symbol in self._feeds:
            del self._feeds[symbol]

    def clear_all(self) -> None:
        """Clear all tracked symbols."""
        self._feeds.clear()

    def stats(self) -> dict:
        """Return feed statistics."""
        active = self.get_all_active()
        total = len(self._feeds)
        return {
            "total_symbols": total,
            "active_symbols": len(active),
            "stale_symbols": total - len(active),
            "stale_threshold_seconds": self.stale_seconds,
        }
