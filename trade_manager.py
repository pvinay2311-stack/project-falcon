class TradeManager:
    def __init__(self):
        self.last_signal = None

    def process_signal(self, action, symbol, price, strategy_score):
        self.last_signal = {
            "action": action,
            "symbol": symbol,
            "price": price,
            "score": strategy_score.get("score"),
            "approved": strategy_score.get("approved")
        }

        if not strategy_score.get("approved"):
            return {
                "allowed": False,
                "reason": "Strategy score too low",
                "last_signal": self.last_signal
            }

        return {
            "allowed": True,
            "reason": "Strategy approved",
            "last_signal": self.last_signal
        }

    def get_status(self):
        return {
            "last_signal": self.last_signal
        }
