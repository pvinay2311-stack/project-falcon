class PositionManager:
    def __init__(self):
        self.position = "FLAT"

    def process(self, action: str):
        action = action.upper()

        if action == "BUY":
            if self.position == "LONG":
                return {
                    "allowed": False,
                    "reason": "Already LONG",
                    "position_after": self.position
                }

            self.position = "LONG"
            return {
                "allowed": True,
                "reason": "Opened LONG",
                "position_after": self.position
            }

        if action == "SELL":
            if self.position == "SHORT":
                return {
                    "allowed": False,
                    "reason": "Already SHORT",
                    "position_after": self.position
                }

            self.position = "SHORT"
            return {
                "allowed": True,
                "reason": "Opened SHORT",
                "position_after": self.position
            }

        return {
            "allowed": False,
            "reason": "Unknown action",
            "position_after": self.position
        }

    def get_position(self):
        return self.position
