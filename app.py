from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime
from dotenv import load_dotenv

from risk_manager import RiskManager
from execution_router import ExecutionRouter
from database import (
    init_db,
    save_trade,
    get_recent_trades,
    get_db_status,
    test_connection,
)
from paper_account import PaperAccount
from strategy_engine import StrategyEngine
from trade_manager import TradeManager
from statistics_engine import calculate_stats
from market_scanner import MarketScanner
from decision_engine import DecisionEngine

load_dotenv()

app = FastAPI(title="Project Falcon ES/NQ Bot - v2")

risk = RiskManager("config.json")
init_db()

executor = ExecutionRouter(risk.config.get("mode", "paper"))

paper_account = PaperAccount(
    contract_multiplier=risk.config.get("contract_multiplier", 50),
    stop_points=risk.config.get("default_stop_points", 10),
    target_points=risk.config.get("default_target_points", 20),
)

strategy_engine = StrategyEngine(min_score=risk.config.get("strategy_min_score", 70))
trade_manager = TradeManager()
scanner = MarketScanner(risk.config)
decision_engine = DecisionEngine(min_score=risk.config.get("decision_min_score", 75))

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


class TradingViewAlert(BaseModel):
    action: str
    symbol: str
    price: float | None = None
    strategy: str | None = None
    time: str | None = None
    secret: str | None = None


class ScannerUpdate(BaseModel):
    secret: str | None = None
    symbol: str
    price: float
    vwap: float | None = None
    ema: float | None = None
    volume: float | None = None
    avg_volume: float | None = None
    time: str | None = None


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
            "stats": calculate_stats(trades),
            "scanner": scanner.best_market(),
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
        "paper_account": paper_account.get_status(),
        "scanner": {
            "enabled": risk.config.get("scanner_enabled", False),
            "best_market": scanner.best_market(),
            "market_data": scanner.market_data,
        },
    }


def execute_falcon_signal(action: str, symbol: str, price: float, strategy: str, time: str | None = None):
    contracts = 1

    strategy_score = strategy_engine.score_signal(
        action=action,
        symbol=symbol,
        price=price,
        risk_status=risk.get_status(),
    )

    trade_decision = trade_manager.process_signal(
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
            "broker": risk.config.get("mode", "paper"),
            "status": "strategy_blocked",
        }

        save_trade(
            log_row,
            execution_result,
            score=strategy_score.get("score"),
            pnl=None,
            position_after=paper_account.get_status()["position"],
        )

        return {
            "status": "blocked",
            "reason": trade_decision["reason"],
            "strategy_score": strategy_score,
        }

    current_position = paper_account.get_status()["position"]

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
            "broker": risk.config.get("mode", "paper"),
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
            "paper_account": paper_account.get_status(),
        }

    decision = risk.check_trade_allowed(
        contracts=contracts,
        realized_pnl=paper_account.get_status()["realized_pnl"],
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
            "broker": risk.config.get("mode", "paper"),
            "status": "risk_blocked",
        }

        save_trade(
            log_row,
            execution_result,
            score=strategy_score.get("score"),
            pnl=None,
            position_after=paper_account.get_status()["position"],
        )

        return {
            "status": "blocked",
            "reason": decision["reason"],
            "risk_status": risk.get_status(),
            "paper_account": paper_account.get_status(),
        }

    paper_result = paper_account.process_order(
        action=action,
        price=price,
        contracts=contracts,
    )

    execution_result = executor.execute(
        action=action,
        symbol=symbol,
        price=price,
        contracts=contracts,
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
        "risk_status": risk.get_status(),
        "paper_account": paper_account.get_status(),
    }


@app.post("/webhook")
def webhook(alert: TradingViewAlert):
    expected_secret = risk.config.get("webhook_secret") or risk.config.get("secret")

    if alert.secret != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    action = alert.action.upper()

    if action not in ["BUY", "SELL"]:
        raise HTTPException(status_code=400, detail="Invalid action. Use BUY or SELL.")

    if not risk.symbol_allowed(alert.symbol):
        raise HTTPException(status_code=400, detail=f"Symbol not allowed: {alert.symbol}")

    if alert.price is None or alert.price <= 0:
        raise HTTPException(status_code=400, detail="Valid price is required.")

    return execute_falcon_signal(
        action=action,
        symbol=alert.symbol,
        price=alert.price,
        strategy=alert.strategy or "TradingView",
        time=alert.time,
    )


@app.post("/scanner")
def scanner_update(update: ScannerUpdate):
    expected_secret = risk.config.get("webhook_secret") or risk.config.get("secret")

    if update.secret != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    if not risk.symbol_allowed(update.symbol):
        raise HTTPException(status_code=400, detail=f"Symbol not allowed: {update.symbol}")

    if not risk.config.get("scanner_enabled", False):
        return {
            "status": "disabled",
            "message": "Scanner is disabled in config.",
        }

    scanner.update_market(
        symbol=update.symbol,
        price=update.price,
        vwap=update.vwap,
        ema=update.ema,
        volume=update.volume,
        avg_volume=update.avg_volume,
    )

    best = scanner.best_market()
    ai_decision = decision_engine.evaluate(best)

    if not ai_decision.get("approved"):
        return {
            "status": "scanning",
            "message": ai_decision.get("reason"),
            "best_market": best,
            "decision": ai_decision,
            "scanner_data": scanner.market_data,
        }

    result = execute_falcon_signal(
        action=ai_decision["direction"],
        symbol=best["symbol"],
        price=best["price"],
        strategy="AI Decision Engine",
        time=update.time,
    )

    return {
        "status": "ai_trade_sent",
        "best_market": best,
        "decision": ai_decision,
        "trade_result": result,
    }