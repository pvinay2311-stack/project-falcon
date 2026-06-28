class PaperAccount:
    def __init__(self):
        self.position = "FLAT"
        self.entry_price = None
        self.contracts = 0
        self.realized_pnl = 0.0

    def process_order(self, action: str, price: float, contracts: int = 1):
        action = action.upper()

        if self.position == "FLAT":
            if action == "BUY":
                self.position = "LONG"
            elif action == "SELL":
                self.position = "SHORT"
            else:
                return {"status": "rejected", "reason": "Invalid action"}

            self.entry_price = price
            self.contracts = contracts

            return {
                "status": "opened",
                "position": self.position,
                "entry_price": self.entry_price,
                "realized_pnl": self.realized_pnl
            }

        if self.position == "LONG" and action == "SELL":
            pnl = (price - self.entry_price) * 50 * self.contracts
            self.realized_pnl += pnl
            self.position = "FLAT"
            self.entry_price = None
            self.contracts = 0

            return {"status": "closed_long", "pnl": pnl, "realized_pnl": self.realized_pnl, "position": self.position}

        if self.position == "SHORT" and action == "BUY":
            pnl = (self.entry_price - price) * 50 * self.contracts
            self.realized_pnl += pnl
            self.position = "FLAT"
            self.entry_price = None
            self.contracts = 0

            return {"status": "closed_short", "pnl": pnl, "realized_pnl": self.realized_pnl, "position": self.position}

        return {
            "status": "ignored",
            "reason": f"Already in {self.position}",
            "position": self.position,
            "realized_pnl": self.realized_pnl
        }

    def get_status(self):
        return {
            "position": self.position,
            "entry_price": self.entry_price,
            "contracts": self.contracts,
            "realized_pnl": self.realized_pnl
        }
