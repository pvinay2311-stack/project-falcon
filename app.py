from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime
from dotenv import load_dotenv

from risk_manager import RiskManager
from execution_router import ExecutionRouter
from database import init_db, save_trade, get_recent_trades, get_db_status, test_connection
from paper_account import PaperAccount
from strategy_engine import StrategyEngine
from trade_manager import TradeManager
from statistics_engine import calculate_stats

load_dotenv()

app = FastAPI(title="Project Falcon ES/NQ Bot - v2")

risk = RiskManager("config.json")
init_db()

executor = ExecutionRouter(risk.config.get("mode", "paper"))

paper_account = PaperAccount(
    contract_multiplier=risk.config.get("contract_multiplier", 50),
    stop_points=risk.config.get("default_stop_points", 10),
    target_points=risk.config.get("default_target_points", 20)
)

strategy_engine = StrategyEngine(min_score=risk.config.get("strategy_min_score", 70))
trade_manager = TradeManager()

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class TradingViewAlert(BaseModel):
    action: str
    symbol: str
    price: float | None = None
    strategy: str | None = None
    time: str | None = None
    secret: str | None = None


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    trades = get_recent_trades()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "mode": risk.config.get("mode", "paper"),
            "trades": trades,
            "risk_status": risk.get_status(),
            "paper_account": paper_account.get_status(),
            "strategy_status": trade_manager.get_status(),
            "stats": calculate_stats(trades)
        },
    )


@app.get("/health")
def health():
    db_success, db_message = test_connection()
    return {
        "status": "ok",
        "mode": risk.config.get("mode", "paper"),
        "database": get_db_status(),
        "database_connection": db_message if db_success else f"❌ {db_message}",
        "risk_status": risk.get_status(),
        "paper_account": paper_account.get_status()
    }


@app.post("/webhook")
def webhook(alert: TradingViewAlert):
    print("STEP 0 - TradingView Alert:", alert.model_dump())

    action = alert.action.upper()

    expected_secret = risk.config.get("webhook_secret") or risk.config.get("secret")
    if alert.secret != expected_secret:
        print("BLOCKED - Invalid secret")
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    if action not in ["BUY", "SELL"]:
        print("BLOCKED - Invalid action")
        raise HTTPException(status_code=400, detail="Invalid action. Use BUY or SELL.")

    if not risk.symbol_allowed(alert.symbol):
        print("BLOCKED - Symbol not allowed")
        raise HTTPException(status_code=400, detail=f"Symbol not allowed: {alert.symbol}")

    if alert.price is None or alert.price <= 0:
        print("BLOCKED - Invalid price")
        raise HTTPException(status_code=400, detail="Valid price is required.")

    contracts = 1

    print("STEP 1 - Strategy scoring")
    strategy_score = strategy_engine.score_signal(
        action=action,
        symbol=alert.symbol,
        price=alert.price,
        risk_status=risk.get_status()
    )

    print("STEP 2 - Trade manager")
    trade_decision = trade_manager.process_signal(
        action=action,
        symbol=alert.symbol,
        price=alert.price,
        strategy_score=strategy_score
    )

    if not trade_decision["allowed"]:
        print("BLOCKED - Strategy rejected")

        log_row = {
            "received_at": datetime.utcnow().isoformat(),
            "action": action,
            "symbol": alert.symbol,
            "price": alert.price,
            "strategy": alert.strategy,
            "tradingview_time": alert.time,
            "decision": False,
            "reason": trade_decision["reason"]
        }

        execution_result = {
            "broker": risk.config.get("mode", "paper"),
            "status": "strategy_blocked"
        }

        save_trade(
            log_row,
            execution_result,
            score=strategy_score.get("score"),
            pnl=None,
            position_after=paper_account.get_status()["position"]
        )

        return {
            "status": "blocked",
            "reason": trade_decision["reason"],
            "strategy_score": strategy_score
        }

    print("STEP 3 - Paper account position check")
    paper_result = paper_account.process_order(
        action=action,
        price=alert.price,
        contracts=contracts
    )

    # Check if position change was valid
    if paper_result.get("status") == "ignored":
        print("BLOCKED - Invalid position transition:", paper_result.get("reason"))

        log_row = {
            "received_at": datetime.utcnow().isoformat(),
            "action": action,
            "symbol": alert.symbol,
            "price": alert.price,
            "strategy": alert.strategy,
            "tradingview_time": alert.time,
            "decision": False,
            "reason": paper_result.get("reason", "Invalid position transition")
        }

        execution_result = {
            "broker": risk.config.get("mode", "paper"),
            "status": "position_blocked"
        }

        save_trade(
            log_row,
            execution_result,
            score=strategy_score.get("score"),
            pnl=None,
            position_after=paper_account.get_status()["position"]
        )

        return {
            "status": "blocked",
            "reason": paper_result.get("reason", "Invalid position transition"),
            "paper_account": paper_account.get_status()
        }

    print("STEP 4 - Risk check (only if position valid)")
    decision = risk.check_trade_allowed(
        contracts=contracts,
        realized_pnl=paper_account.get_status()["realized_pnl"]
    )

    log_row = {
        "received_at": datetime.utcnow().isoformat(),
        "action": action,
        "symbol": alert.symbol,
        "price": alert.price,
        "strategy": alert.strategy,
        "tradingview_time": alert.time,
        "decision": decision["allowed"],
        "reason": decision["reason"]
    }

    if not decision["allowed"]:
        print("BLOCKED - Risk rejected:", decision["reason"])

        execution_result = {
            "broker": risk.config.get("mode", "paper"),
            "status": "risk_blocked"
        }

        save_trade(
            log_row,
            execution_result,
            score=strategy_score.get("score"),
            pnl=None,
            position_after=paper_account.get_status()["position"]
        )

        return {
            "status": "blocked",
            "reason": decision["reason"],
            "risk_status": risk.get_status(),
            "paper_account": paper_account.get_status()
        }

    print("STEP 5 - Execution router")
    execution_result = executor.execute(
        action=action,
        symbol=alert.symbol,
        price=alert.price,
        contracts=contracts
    )

    execution_result["paper_account"] = paper_result

    print("STEP 6 - Save trade")
    save_trade(
        log_row,
        execution_result,
        score=strategy_score.get("score"),
        pnl=paper_result.get("pnl"),
        position_after=paper_result.get("position")
    )

    print("STEP 7 - Completed")

    return {
        "status": "accepted",
        "message": "Signal received, scored, risk checked, paper processed, routed, and saved.",
        "signal": log_row,
        "strategy_score": strategy_score,
        "execution": execution_result,
        "risk_status": risk.get_status(),
        "paper_account": paper_account.get_status()
    }