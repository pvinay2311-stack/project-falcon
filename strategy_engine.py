class StrategyEngine:
    def __init__(self, min_score: int = 70):
        self.min_score = min_score

    def score_signal(self, action: str, symbol: str, price: float | None, risk_status: dict):
        score = 0
        reasons = []

        if risk_status.get("session_allowed"):
            score += 20
            reasons.append("Session allowed")
        else:
            reasons.append("Outside session")

        if action.upper() in ["BUY", "SELL"]:
            score += 20
            reasons.append("Valid direction")

        if symbol in ["ES1!", "NQ1!", "MES1!", "MNQ1!"]:
            score += 20
            reasons.append("Allowed futures symbol")

        if price is not None and price > 0:
            score += 20
            reasons.append("Valid price")

        if not risk_status.get("emergency_stop"):
            score += 20
            reasons.append("Emergency stop off")

        approved = score >= self.min_score

        return {
            "approved": approved,
            "score": score,
            "min_score": self.min_score,
            "reasons": reasons
        }
