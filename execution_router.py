from paper_broker import PaperBroker


class ExecutionRouter:
    def __init__(self, mode: str = "paper"):
        self.mode = mode
        self.paper = PaperBroker()

    def execute(self, action: str, symbol: str, price: float | None, contracts: int = 1):
        if self.mode == "paper":
            return self.paper.place_order(action, symbol, price, contracts)

        if self.mode == "manual":
            return {
                "status": "manual_review",
                "broker": "manual",
                "message": "Signal logged for manual execution only.",
                "action": action,
                "symbol": symbol,
                "price": price,
                "contracts": contracts
            }

        return {
            "status": "not_supported",
            "broker": self.mode,
            "message": f"Execution mode '{self.mode}' is not connected yet."
        }
