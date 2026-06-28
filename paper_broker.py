from datetime import datetime


class PaperBroker:
    def place_order(self, action: str, symbol: str, price: float | None, contracts: int = 1):
        return {
            "status": "paper_routed",
            "broker": "paper",
            "action": action,
            "symbol": symbol,
            "price": price,
            "contracts": contracts,
            "routed_at": datetime.utcnow().isoformat()
        }
