from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime
from risk_manager import RiskManager
from logger import TradeLogger
from execution_router import ExecutionRouter
from database import save_trade, get_recent_trades

app = FastAPI(title="Project Falcon ES/NQ Bot")

risk = RiskManager("config.json")
logger = TradeLogger("trades.csv")
executor = ExecutionRouter(risk.config.get("mode", "paper"))
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory="templates")


class TradingViewAlert(BaseModel):
    action: str
    symbol: str
    price: float | None = None
    strategy: str | None = None
    time: str | None = None


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "mode": risk.config.get("mode", "paper"),
            "trades": get_recent_trades()
        },
    )


@app.post("/webhook")
def webhook(alert: TradingViewAlert):
    print("TradingView Alert:", alert.model_dump())
    action = alert.action.upper()

    if action not in ["BUY", "SELL"]:
        raise HTTPException(status_code=400, detail="Invalid action. Use BUY or SELL.")

    if not risk.symbol_allowed(alert.symbol):
        raise HTTPException(status_code=400, detail=f"Symbol not allowed: {alert.symbol}")

    decision = risk.check_trade_allowed()

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
        return {"status": "blocked", "reason": decision["reason"]}

    execution_result = executor.execute(
        action=action,
        symbol=alert.symbol,
        price=alert.price,
        contracts=1
    )

    save_trade(log_row, execution_result)

    return {
        "status": "accepted",
        "message": "Signal received and routed.",
        "signal": log_row,
        "execution": execution_result
    }
