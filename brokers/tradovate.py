from datetime import datetime


class TradovateClient:
    """Placeholder for future Tradovate API integration.

    Do not add live credentials here.
    We will connect this only after:
    1. Strategy is validated
    2. Paper trading is stable
    3. Tradovate API access is enabled
    """

    def place_order(self, symbol: str, action: str, quantity: int):
        raise NotImplementedError("Tradovate execution is not enabled yet.")


class PaperBroker:
    def place_order(self, action: str, symbol: str, price: float | None, contracts: int = 1):
        return {
            "status": "paper_filled",
            "broker": "paper",
            "action": action,
            "symbol": symbol,
            "price": price,
            "contracts": contracts,
            "filled_at": datetime.utcnow().isoformat()
        }
