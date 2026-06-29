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
from candle_engine import CandleEngine
from indicator_engine import IndicatorEngine
from timeframe_engine import TimeframeEngine
from services.trade_service import TradeService

load_dotenv()

app = FastAPI(title="Project Falcon ES/NQ Bot - v3")

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
candle_engine = CandleEngine()
indicator_engine = IndicatorEngine()
timeframe_engine = TimeframeEngine()
trade_service = TradeService(
    risk=risk,
    paper_account=paper_account,
    strategy_engine=strategy_engine,
    trade_manager=trade_manager,
    executor=executor,
)

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
    volume: float | None = None
    time: str | None = None


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    trades = get_recent_trades()
    best_market = scanner.best_market()
    decision = decision_engine.evaluate(best_market)

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
            "scanner": best_market,
            "decision": decision,
        },
    )


@app.get("/health")
def health():
    db_success, db_message = test_connection()
    best_market = scanner.best_market()
    decision = decision_engine.evaluate(best_market)

    return {
        "status": "ok",
        "mode": risk.config.get("mode", "paper"),
        "database": get_db_status(),
        "database_connection": db_message if db_success else f"❌ {db_message}",
        "risk_status": risk.get_status(),
        "paper_account": paper_account.get_status(),
        "scanner": {
            "enabled": risk.config.get("scanner_enabled", False),
            "best_market": best_market,
            "decision": decision,
            "market_data": scanner.market_data,
        },
        "candles": candle_engine.snapshot(),
        "timeframes": timeframe_engine.snapshot(),
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

    return trade_service.execute_signal(
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

    candle_engine.update_tick(
        symbol=update.symbol,
        price=update.price,
        volume=update.volume,
    )

    timeframe_engine.update_tick(
        symbol=update.symbol,
        price=update.price,
        volume=update.volume,
    )

    candles = candle_engine.get_candles(update.symbol)
    indicator_snapshot = indicator_engine.snapshot(update.symbol, candles)

    scanner.update_market(indicator_snapshot)

    best = scanner.best_market()
    ai_decision = decision_engine.evaluate(best)

    if not ai_decision.get("approved"):
        return {
            "status": "scanning",
            "message": ai_decision.get("reason"),
            "best_market": best,
            "decision": ai_decision,
            "indicator_snapshot": indicator_snapshot,
            "candles": candle_engine.snapshot(),
            "timeframes": timeframe_engine.snapshot(),
        }

    result = trade_service.execute_signal(
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
        "indicator_snapshot": indicator_snapshot,
        "timeframes": timeframe_engine.snapshot(),
        "trade_result": result,
    }