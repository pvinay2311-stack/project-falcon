from datetime import datetime, date
from zoneinfo import ZoneInfo


class IndicatorEngine:
    """
    Computes technical indicators (EMA, VWAP, momentum) from raw price/volume ticks.
    Allows the scanner to work without relying on external indicator values.
    """

    def __init__(self, ema_period: int = 20):
        self.ema_period = ema_period
        self._symbols: dict[str, dict] = {}

    def _symbol(self, symbol: str) -> dict:
        if symbol not in self._symbols:
            self._symbols[symbol] = {
                "prices": [],
                "ema": None,
                "vwap_cumulative_pv": 0.0,
                "vwap_cumulative_vol": 0.0,
                "vwap": None,
                "vwap_date": None,
            }
        return self._symbols[symbol]

    def update(self, symbol: str, price: float, volume: float = 0.0) -> dict:
        """
        Ingest a new price tick and recompute EMA, VWAP, and momentum.

        Returns computed indicators for this tick.
        """
        s = self._symbol(symbol)

        # Track price history (keep last 200 ticks)
        s["prices"].append(price)
        if len(s["prices"]) > 200:
            s["prices"].pop(0)

        # EMA
        s["ema"] = self._calc_ema(s["prices"], self.ema_period)

        # VWAP — reset each calendar day (ET)
        today = datetime.now(ZoneInfo("America/New_York")).date()
        if s["vwap_date"] != today:
            s["vwap_cumulative_pv"] = 0.0
            s["vwap_cumulative_vol"] = 0.0
            s["vwap_date"] = today

        if volume > 0:
            s["vwap_cumulative_pv"] += price * volume
            s["vwap_cumulative_vol"] += volume
            s["vwap"] = s["vwap_cumulative_pv"] / s["vwap_cumulative_vol"]
        elif s["vwap"] is None:
            s["vwap"] = price  # seed with first price if no volume provided

        # Momentum: % change from oldest tracked price
        first_price = s["prices"][0]
        momentum_pct = ((price - first_price) / first_price) * 100 if first_price else 0.0

        return {
            "symbol": symbol,
            "price": price,
            "ema": round(s["ema"], 4) if s["ema"] is not None else None,
            "vwap": round(s["vwap"], 4) if s["vwap"] is not None else None,
            "momentum_pct": round(momentum_pct, 4),
            "ticks": len(s["prices"]),
        }

    def get(self, symbol: str) -> dict:
        """Return latest computed indicators for a symbol without updating."""
        s = self._symbols.get(symbol)
        if not s or not s["prices"]:
            return {}
        price = s["prices"][-1]
        first_price = s["prices"][0]
        momentum_pct = ((price - first_price) / first_price) * 100 if first_price else 0.0
        return {
            "symbol": symbol,
            "price": price,
            "ema": round(s["ema"], 4) if s["ema"] is not None else None,
            "vwap": round(s["vwap"], 4) if s["vwap"] is not None else None,
            "momentum_pct": round(momentum_pct, 4),
            "ticks": len(s["prices"]),
        }

    def _calc_ema(self, prices: list[float], period: int) -> float | None:
        """Compute EMA using standard smoothing factor k = 2 / (period + 1)."""
        if len(prices) < 2:
            return prices[0] if prices else None

        k = 2.0 / (period + 1)

        if len(prices) <= period:
            # Not enough data for a full EMA — use SMA as seed
            ema = sum(prices) / len(prices)
        else:
            # Seed with SMA of first `period` prices, then apply EMA
            ema = sum(prices[:period]) / period
            for price in prices[period:]:
                ema = price * k + ema * (1 - k)

        return ema
