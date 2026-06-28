from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime
from risk_manager import RiskManager
from logger import TradeLogger
from execution_router import ExecutionRouter
from database import init_db, save_trade, get_recent_trades
from position_manager import PositionManager
from paper_account import PaperAccount
from strategy_engine import StrategyEngine
from trade_manager import TradeManager
from statistics_engine import calculate_stats

app = FastAPI(title="Project Falcon ES/NQ Bot")

risk = RiskManager("config.json")
logger = TradeLogger("trades.csv")
init_db()

executor = ExecutionRouter(risk.config.get("mode", "paper"))
position = PositionManager()

try:
    paper_account = PaperAccount(
        contract_multiplier=risk.config.get("contract_multiplier", 50),
        stop_points=risk.config.get("default_stop_points", 10),
        target_points=risk.config.get("default_target_points", 20)
    )
except Exception as e:
    print(f"Warning: Could not initialize PaperAccount: {e}")
    paper_account = None

strategy_engine = StrategyEngine(min_score=risk.config.get("strategy_min_score", 70))
trade_manager = TradeManager()
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory="templates")


class TradingViewAlert(BaseModel):
    action: str
    symbol: str
    price: float | None = None
    strategy: str | None = None
    time: str | None = None
    secret: str | None = None




@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "mode": risk.config.get("mode", "paper"),
            "trades": get_recent_trades(),
            "risk_status": risk.get_status(),
            "paper_account": paper_account.get_status(),
            "strategy_status": trade_manager.get_status(),
            "stats": calculate_stats(get_recent_trades())
        },
    )


@app.post("/webhook")
def webhook(alert: TradingViewAlert):
    print("TradingView Alert:", alert.model_dump())
    action = alert.action.upper()

    expected_secret = risk.config.get("webhook_secret") or risk.config.get("secret")
    if alert.secret != expected_secret:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    if action not in ["BUY", "SELL"]:
        raise HTTPException(status_code=400, detail="Invalid action. Use BUY or SELL.")

    if not risk.symbol_allowed(alert.symbol):
        raise HTTPException(status_code=400, detail=f"Symbol not allowed: {alert.symbol}")

    strategy_score = strategy_engine.score_signal(
        action=action,
        symbol=alert.symbol,
        price=alert.price,
        risk_status=risk.get_status()
    )

    trade_decision = trade_manager.process_signal(
        action=action,
        symbol=alert.symbol,
        price=alert.price,
        strategy_score=strategy_score
    )

    if not trade_decision["allowed"]:
        return {
            "status": "blocked",
            "reason": trade_decision["reason"],
            "strategy_score": strategy_score,
            "strategy_status": trade_manager.get_status(),
            "stats": calculate_stats(get_recent_trades())
        }

    contracts = 1
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

    logger.log(log_row)

    if not decision["allowed"]:
        return {
            "status": "blocked",
            "reason": decision["reason"],
            "risk_status": risk.get_status(),
            "paper_account": paper_account.get_status()
        }

    position_decision = position.process(action)
    if not position_decision["allowed"]:
        return {
            "status": "ignored",
            "reason": position_decision["reason"],
            "position": position_decision["position_after"],
            "risk_status": risk.get_status(),
            "paper_account": paper_account.get_status()
        }

    paper_result = paper_account.process_order(
        action=action,
        price=alert.price,
        contracts=contracts
    )

    execution_result = executor.execute(
        action=action,
        symbol=alert.symbol,
        price=alert.price,
        contracts=contracts
    )

    execution_result["paper_account"] = paper_result

    save_trade(
        log_row,
        execution_result,
        score=strategy_score.get("score"),
        pnl=paper_result.get("pnl"),
        position_after=paper_result.get("position")
    )

    return {
        "status": "accepted",
        "message": "Signal received and routed.",
        "signal": log_row,
        "execution": execution_result,
        "risk_status": risk.get_status(),
        "paper_account": paper_account.get_status()
    }
