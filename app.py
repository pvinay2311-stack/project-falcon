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
from position_manager import PositionManager
from paper_account import PaperAccount

app = FastAPI(title="Project Falcon ES/NQ Bot")

risk = RiskManager("config.json")
logger = TradeLogger("trades.csv")
executor = ExecutionRouter(risk.config.get("mode", "paper"))
position = PositionManager()
paper_account = PaperAccount()
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
            "trades": get_recent_trades(),
            "risk_status": risk.get_status(),
            "current_position": position.get_position(),
            "paper_account": paper_account.get_status()
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

    contracts = 1
    decision = risk.check_trade_allowed(contracts=contracts)

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

    save_trade(log_row, execution_result)

    return {
        "status": "accepted",
        "message": "Signal received and routed.",
        "signal": log_row,
        "execution": execution_result,
        "risk_status": risk.get_status(),
        "paper_account": paper_account.get_status()
    }
