class DecisionEngine:
    """
    Combines scanner score + strategy signal into a final trade approval decision.
    Acts as the last gate before execution.
    """

    def __init__(self, min_score: int = 75):
        self.min_score = min_score

    def evaluate(self, scanner_result: dict | None) -> dict:
        """
        Evaluate whether to trade based on the scanner's best market result.

        Args:
            scanner_result: Output of MarketScanner.best_market() — contains
                            symbol, score, direction, momentum_pct, price, reasons.

        Returns:
            {approved, final_score, direction, symbol, price, reason, breakdown}
        """
        if not scanner_result:
            return {
                "approved": False,
                "final_score": 0,
                "reason": "No scanner data available",
                "breakdown": {},
            }

        scanner_score = scanner_result.get("score", 0)
        direction = scanner_result.get("direction")
        symbol = scanner_result.get("symbol")
        price = scanner_result.get("price")
        momentum_pct = scanner_result.get("momentum_pct", 0)
        reasons = scanner_result.get("reasons", [])

        if not direction:
            return {
                "approved": False,
                "final_score": scanner_score,
                "reason": "No directional signal from scanner",
                "breakdown": {"scanner_score": scanner_score},
            }

        # Bonus points on top of base scanner score
        confidence_bonus = 0
        bonus_reasons = []

        # Strong momentum bonus (>0.5%)
        if momentum_pct >= 0.5:
            confidence_bonus += 10
            bonus_reasons.append(f"Strong momentum: +{momentum_pct:.2f}%")

        # All 4 confirmations present
        if len(reasons) >= 4:
            confidence_bonus += 5
            bonus_reasons.append("All confirmations present")

        final_score = min(scanner_score + confidence_bonus, 100)

        if final_score < self.min_score:
            return {
                "approved": False,
                "final_score": final_score,
                "direction": direction,
                "symbol": symbol,
                "price": price,
                "reason": f"Final score {final_score} below threshold {self.min_score}",
                "breakdown": {
                    "scanner_score": scanner_score,
                    "confidence_bonus": confidence_bonus,
                    "final_score": final_score,
                    "min_score": self.min_score,
                    "scanner_reasons": reasons,
                    "bonus_reasons": bonus_reasons,
                },
            }

        return {
            "approved": True,
            "final_score": final_score,
            "direction": direction,
            "symbol": symbol,
            "price": price,
            "reason": "AI decision engine approved",
            "breakdown": {
                "scanner_score": scanner_score,
                "confidence_bonus": confidence_bonus,
                "final_score": final_score,
                "min_score": self.min_score,
                "scanner_reasons": reasons,
                "bonus_reasons": bonus_reasons,
            },
        }
