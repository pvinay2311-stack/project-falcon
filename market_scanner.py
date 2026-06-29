from datetime import datetime
from zoneinfo import ZoneInfo


class MarketScanner:
    """Automated market analysis and trading signal generation."""

    def __init__(self, config: dict):
        self.config = config
        self.market_data = {}
        self.trade_taken_today = False
        
    def now_et(self):
        """Get current time in Eastern timezone."""
        return datetime.now(ZoneInfo("America/New_York"))
    
    def in_scan_window(self) -> bool:
        """Check if within scan window (08:00-09:30 ET)."""
        now = self.now_et()
        start_time = self.config.get("scanner_start", "08:00")
        end_time = self.config.get("scanner_end", "09:30")
        
        start_hour, start_min = map(int, start_time.split(":"))
        end_hour, end_min = map(int, end_time.split(":"))
        
        start_dt = now.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
        end_dt = now.replace(hour=end_hour, minute=end_min, second=0, microsecond=0)
        
        return start_dt <= now <= end_dt
    
    def can_execute_after_scan(self) -> bool:
        """Check if past execution time (09:30 ET)."""
        now = self.now_et()
        execute_time = self.config.get("scanner_execute_after", "09:30")
        exec_hour, exec_min = map(int, execute_time.split(":"))
        
        exec_dt = now.replace(hour=exec_hour, minute=exec_min, second=0, microsecond=0)
        return now >= exec_dt
    
    def update_market(self, symbol: str, price: float, vwap: float | None = None, 
                     ema: float | None = None, volume: float | None = None, 
                     avg_volume: float | None = None):
        """Update market data for symbol."""
        if symbol not in self.market_data:
            self.market_data[symbol] = {}
        
        self.market_data[symbol].update({
            "price": price,
            "vwap": vwap,
            "ema": ema,
            "volume": volume,
            "avg_volume": avg_volume,
            "updated_at": self.now_et().isoformat(),
        })
    
    def score_symbol(self, symbol: str) -> dict:
        """Calculate signal score (0-100) with momentum and technical confirmation."""
        if symbol not in self.market_data:
            return {"approved": False, "reason": f"No market data for {symbol}"}
        
        data = self.market_data[symbol]
        price = data.get("price", 0)
        vwap = data.get("vwap")
        ema = data.get("ema")
        volume = data.get("volume", 0)
        avg_volume = data.get("avg_volume", 1)
        
        score = 0
        direction = None
        reasons = []
        momentum_pct = 0
        
        # Calculate momentum (simplified - would use price history in production)
        min_momentum = self.config.get("scanner_min_momentum_pct", 0.15) / 100
        
        # Bullish momentum detection
        if price > 0 and vwap and price > vwap:
            momentum_pct = ((price - vwap) / vwap) * 100
            if momentum_pct >= self.config.get("scanner_min_momentum_pct", 0.15):
                score += 35
                direction = "BUY"
                reasons.append(f"Bullish momentum: +{momentum_pct:.2f}%")
        
        # Bearish momentum detection
        if price > 0 and vwap and price < vwap:
            momentum_pct = ((vwap - price) / vwap) * 100
            if momentum_pct >= self.config.get("scanner_min_momentum_pct", 0.15):
                score += 35
                direction = "SELL"
                reasons.append(f"Bearish momentum: -{momentum_pct:.2f}%")
        
        # VWAP confirmation for BUY
        if direction == "BUY" and vwap and price >= vwap:
            score += 20
            reasons.append("VWAP confirmation")
        
        # VWAP confirmation for SELL
        if direction == "SELL" and vwap and price <= vwap:
            score += 20
            reasons.append("VWAP confirmation")
        
        # EMA confirmation for BUY
        if direction == "BUY" and ema and price >= ema:
            score += 20
            reasons.append("EMA confirmation")
        
        # EMA confirmation for SELL
        if direction == "SELL" and ema and price <= ema:
            score += 20
            reasons.append("EMA confirmation")
        
        # Volume confirmation
        if volume and avg_volume and volume > (1.2 * avg_volume):
            score += 25
            reasons.append("Volume confirmation")
        
        return {
            "symbol": symbol,
            "score": score,
            "direction": direction,
            "momentum_pct": momentum_pct,
            "price": price,
            "reasons": reasons,
        }
    
    def best_market(self) -> dict | None:
        """Find highest-scored trading opportunity."""
        best_score = 0
        best_symbol = None
        best_result = None
        
        for symbol in self.market_data:
            result = self.score_symbol(symbol)
            if result.get("score", 0) > best_score and result.get("direction"):
                best_score = result["score"]
                best_symbol = symbol
                best_result = result
        
        return best_result
    
    def should_trade(self) -> dict:
        """Determine if trade should execute based on score and timing."""
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
        
        if best["score"] < self.config.get("scanner_min_score", 70):
            return {
                "approved": False,
                "reason": f"Score {best['score']} below threshold {self.config.get('scanner_min_score', 70)}",
                "best": best,
            }
        
        if not self.can_execute_after_scan():
            return {
                "approved": False,
                "reason": f"Outside execution window (need to be after {self.config.get('scanner_execute_after', '09:30')} ET)",
                "best": best,
            }
        
        self.trade_taken_today = True
        return {
            "approved": True,
            "reason": "All checks passed",
            "best": best,
        }
