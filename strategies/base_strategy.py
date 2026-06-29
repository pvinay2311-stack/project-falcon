class BaseStrategy:
    name = "Base Strategy"

    def evaluate(self, market: dict):
        return {
            "approved": False,
            "direction": "HOLD",
            "confidence": 0,
            "strategy": self.name,
            "reason": "Base strategy does nothing",
        }
