import json
from datetime import date


class RiskManager:
    def __init__(self, config_path: str):
        with open(config_path, "r") as f:
            self.config = json.load(f)

        self.current_day = date.today()
        self.trades_today = 0
        self.daily_pnl = 0.0

    def reset_if_new_day(self):
        today = date.today()
        if today != self.current_day:
            self.current_day = today
            self.trades_today = 0
            self.daily_pnl = 0.0

    def symbol_allowed(self, symbol: str) -> bool:
        return symbol in self.config.get("symbols_allowed", [])

    def check_trade_allowed(self, contracts: int = 1):
        self.reset_if_new_day()

        if self.config.get("emergency_stop", False):
            return {"allowed": False, "reason": "Emergency stop active"}

        max_contracts = self.config.get("max_contracts", 1)
        if contracts > max_contracts:
            return {
                "allowed": False,
                "reason": f"Max contracts per trade exceeded ({contracts}/{max_contracts})"
            }

        if self.trades_today >= self.config.get("max_trades_per_day", 2):
            return {"allowed": False, "reason": "Max trades per day reached"}

        if self.daily_pnl <= -abs(self.config.get("max_daily_loss", 500)):
            return {"allowed": False, "reason": "Max daily loss reached"}

        if self.daily_pnl >= self.config.get("max_daily_profit", 1000):
            return {"allowed": False, "reason": "Max daily profit reached"}

        self.trades_today += 1
        return {"allowed": True, "reason": "Risk check passed"}
