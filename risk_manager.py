import json
from datetime import date, datetime
from zoneinfo import ZoneInfo


class RiskManager:
    def __init__(self, config_path: str):
        with open(config_path, "r") as f:
            self.config = json.load(f)

        self.current_day = date.today()
        self.trades_today = 0

    def reset_if_new_day(self):
        today = date.today()
        if today != self.current_day:
            self.current_day = today
            self.trades_today = 0

    def symbol_allowed(self, symbol: str) -> bool:
        return symbol in self.config.get("symbols_allowed", [])

    def session_allowed(self) -> bool:
        if not self.config.get("trading_session_enabled", False):
            return True

        tz = ZoneInfo(self.config.get("session_timezone", "America/New_York"))
        now = datetime.now(tz).time()

        start = datetime.strptime(self.config.get("session_start", "09:45"), "%H:%M").time()
        end = datetime.strptime(self.config.get("session_end", "11:30"), "%H:%M").time()

        return start <= now <= end

    def get_status(self):
        return {
            "emergency_stop": self.config.get("emergency_stop", False),
            "trading_session_enabled": self.config.get("trading_session_enabled", False),
            "session_allowed": self.session_allowed(),
            "trades_today": self.trades_today,
            "max_trades_per_day": self.config.get("max_trades_per_day", 3),
            "mode": self.config.get("mode", "paper")
        }

    def check_trade_allowed(self, contracts: int = 1):
        self.reset_if_new_day()

        if self.config.get("emergency_stop", False):
            return {"allowed": False, "reason": "Emergency stop is ON"}

        if not self.session_allowed():
            return {"allowed": False, "reason": "Outside allowed trading session"}

        if contracts > self.config.get("max_contracts", 1):
            return {"allowed": False, "reason": "Contracts exceed max allowed"}

        if self.trades_today >= self.config.get("max_trades_per_day", 3):
            return {"allowed": False, "reason": "Max trades per day reached"}

        self.trades_today += 1
        return {"allowed": True, "reason": "Risk check passed"}
