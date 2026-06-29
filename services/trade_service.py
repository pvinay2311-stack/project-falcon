from datetime import datetime
from database import save_trade
from paper_account import PaperAccount
from strategy_engine import StrategyEngine
from trade_manager import TradeManager
from risk_manager import RiskManager
from execution_router import ExecutionRouter


class TradeService:
    def __init__(self, risk: RiskManager, paper_account: PaperAccount, strategy_engine: StrategyEngine, trade_manager: TradeManager, executor: ExecutionRouter):
        self.risk = risk
        self.paper_account = paper_account
        self.strategy_engine = strategy_engine
        self.trade_manager = trade_manager
        self.executor = executor
        self.contracts = 1

    def execute_signal(self, action: str, symbol: str, price: float, strategy: str, time: str | None = None) -> dict:
        """Execute a trading signal through all gates: strategy → trade → risk → paper → executor → save"""
        
        strategy_score = self.strategy_engine.score_signal(
            action=action,
            symbol=symbol,
            price=price,
            risk_status=self.risk.get_status(),
        )

        trade_decision = self.trade_manager.process_signal(
            action=action,
            symbol=symbol,
            price=price,
            strategy_score=strategy_score,
        )

        if not trade_decision["allowed"]:
            log_row = {
                "received_at": datetime.utcnow().isoformat(),
                "action": action,
                "symbol": symbol,
                "price": price,
                "strategy": strategy,
                "tradingview_time": time,
                "decision": False,
                "reason": trade_decision["reason"],
            }

            execution_result = {
                "broker": self.risk.config.get("mode", "paper"),
                "status": "strategy_blocked",
            }

            save_trade(
                log_row,
                execution_result,
                score=strategy_score.get("score"),
                pnl=None,
                position_after=self.paper_account.get_status()["position"],
            )

            return {
                "status": "blocked",
                "reason": trade_decision["reason"],
                "strategy_score": strategy_score,
            }

        current_position = self.paper_account.get_status()["position"]

        invalid_transition = (
            (current_position == "LONG" and action == "BUY")
            or (current_position == "SHORT" and action == "SELL")
        )

        if invalid_transition:
            log_row = {
                "received_at": datetime.utcnow().isoformat(),
                "action": action,
                "symbol": symbol,
                "price": price,
                "strategy": strategy,
                "tradingview_time": time,
                "decision": False,
                "reason": f"Already {current_position}",
            }

            execution_result = {
                "broker": self.risk.config.get("mode", "paper"),
                "status": "position_blocked",
            }

            save_trade(
                log_row,
                execution_result,
                score=strategy_score.get("score"),
                pnl=None,
                position_after=current_position,
            )

            return {
                "status": "blocked",
                "reason": f"Already {current_position}",
                "paper_account": self.paper_account.get_status(),
            }

        decision = self.risk.check_trade_allowed(
            contracts=self.contracts,
            realized_pnl=self.paper_account.get_status()["realized_pnl"],
        )

        log_row = {
            "received_at": datetime.utcnow().isoformat(),
            "action": action,
            "symbol": symbol,
            "price": price,
            "strategy": strategy,
            "tradingview_time": time,
            "decision": decision["allowed"],
            "reason": decision["reason"],
        }

        if not decision["allowed"]:
            execution_result = {
                "broker": self.risk.config.get("mode", "paper"),
                "status": "risk_blocked",
            }

            save_trade(
                log_row,
                execution_result,
                score=strategy_score.get("score"),
                pnl=None,
                position_after=self.paper_account.get_status()["position"],
            )

            return {
                "status": "blocked",
                "reason": decision["reason"],
                "risk_status": self.risk.get_status(),
                "paper_account": self.paper_account.get_status(),
            }

        paper_result = self.paper_account.process_order(
            action=action,
            price=price,
            contracts=self.contracts,
        )

        execution_result = self.executor.execute(
            action=action,
            symbol=symbol,
            price=price,
            contracts=self.contracts,
        )

        execution_result["status"] = "paper_routed"
        execution_result["paper_account"] = paper_result

        save_trade(
            log_row,
            execution_result,
            score=strategy_score.get("score"),
            pnl=paper_result.get("pnl"),
            position_after=paper_result.get("position"),
        )

        return {
            "status": "accepted",
            "message": "Signal received, scored, risk checked, paper processed, routed, and saved.",
            "signal": log_row,
            "strategy_score": strategy_score,
            "execution": execution_result,
            "risk_status": self.risk.get_status(),
            "paper_account": self.paper_account.get_status(),
        }
