from database import get_account_state, save_account_state


class PaperAccount:
    def __init__(self, contract_multiplier=50, stop_points=10, target_points=20):
        state = get_account_state()

        self.position = state.get("position", "FLAT")
        self.entry_price = state.get("entry_price")
        self.contracts = state.get("contracts", 0)
        self.realized_pnl = state.get("realized_pnl", 0.0)
        self.stop_price = state.get("stop_price")
        self.target_price = state.get("target_price")

        self.contract_multiplier = contract_multiplier
        self.stop_points = stop_points
        self.target_points = target_points

    def persist(self):
        save_account_state(
            self.position,
            self.entry_price,
            self.contracts,
            self.realized_pnl,
            self.stop_price,
            self.target_price
        )

    def open_position(self, side: str, price: float, contracts: int):
        self.position = side
        self.entry_price = price
        self.contracts = contracts

        if side == "LONG":
            self.stop_price = price - self.stop_points
            self.target_price = price + self.target_points
        else:
            self.stop_price = price + self.stop_points
            self.target_price = price - self.target_points

        self.persist()

        return {
            "status": "opened",
            "position": self.position,
            "entry_price": self.entry_price,
            "contracts": self.contracts,
            "stop_price": self.stop_price,
            "target_price": self.target_price,
            "realized_pnl": self.realized_pnl,
            "pnl": None
        }

    def close_position(self, price: float, reason: str = "manual_close"):
        if self.position == "LONG":
            pnl = (price - self.entry_price) * self.contract_multiplier * self.contracts
            status = "closed_long"
        elif self.position == "SHORT":
            pnl = (self.entry_price - price) * self.contract_multiplier * self.contracts
            status = "closed_short"
        else:
            return {
                "status": "ignored",
                "reason": "No open position",
                "position": self.position,
                "pnl": None
            }

        self.realized_pnl += pnl

        self.position = "FLAT"
        self.entry_price = None
        self.contracts = 0
        self.stop_price = None
        self.target_price = None

        self.persist()

        return {
            "status": status,
            "reason": reason,
            "pnl": pnl,
            "realized_pnl": self.realized_pnl,
            "position": self.position
        }

    def process_order(self, action: str, price: float, contracts: int = 1):
        action = action.upper()

        if self.position == "FLAT":
            if action == "BUY":
                return self.open_position("LONG", price, contracts)
            if action == "SELL":
                return self.open_position("SHORT", price, contracts)
            return {"status": "rejected", "reason": "Invalid action", "pnl": None}

        if self.position == "LONG":
            if action == "SELL":
                return self.close_position(price, reason="manual_sell_close")
            return {
                "status": "ignored",
                "reason": "Already LONG",
                "position": self.position,
                "pnl": None
            }

        if self.position == "SHORT":
            if action == "BUY":
                return self.close_position(price, reason="manual_buy_close")
            return {
                "status": "ignored",
                "reason": "Already SHORT",
                "position": self.position,
                "pnl": None
            }

        return {"status": "rejected", "reason": "Unknown state", "pnl": None}

    def check_stop_target(self, price: float):
        if self.position == "FLAT":
            return {
                "triggered": False,
                "reason": "No open position",
                "position": self.position
            }

        if self.stop_price is None or self.target_price is None:
            return {
                "triggered": False,
                "reason": "Stop/target not set",
                "position": self.position
            }

        if self.position == "LONG":
            if price <= self.stop_price:
                result = self.close_position(price, reason="stop_loss_hit")
                result["triggered"] = True
                result["trigger_type"] = "stop_loss"
                return result

            if price >= self.target_price:
                result = self.close_position(price, reason="target_hit")
                result["triggered"] = True
                result["trigger_type"] = "target"
                return result

        if self.position == "SHORT":
            if price >= self.stop_price:
                result = self.close_position(price, reason="stop_loss_hit")
                result["triggered"] = True
                result["trigger_type"] = "stop_loss"
                return result

            if price <= self.target_price:
                result = self.close_position(price, reason="target_hit")
                result["triggered"] = True
                result["trigger_type"] = "target"
                return result

        return {
            "triggered": False,
            "reason": "No stop or target hit",
            "position": self.position
        }

    def get_status(self):
        return {
            "position": self.position,
            "entry_price": self.entry_price,
            "contracts": self.contracts,
            "realized_pnl": self.realized_pnl,
            "stop_price": self.stop_price,
            "target_price": self.target_price
        }