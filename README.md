# Project Falcon – ES/NQ Trading Bot

This is a starter framework for building an ES/NQ futures trading bot.

Phase 1 is strategy research only:
- No live orders
- No Tradovate API yet
- Receives TradingView webhook alerts
- Logs signals to CSV
- Applies simple risk checks

## Setup

1. Install Python 3.11+
2. Open this folder in VS Code
3. Run:

```bash
pip install -r requirements.txt
python app.py
```

The webhook server will run at:

```text
http://127.0.0.1:8000/webhook
```

Later we will expose it safely using ngrok or a cloud server.

## TradingView Alert JSON

Use this alert message:

```json
{
  "action": "BUY",
  "symbol": "{{ticker}}",
  "price": "{{close}}",
  "strategy": "ES_NQ_V5",
  "time": "{{time}}"
}
```

For sell alerts, change BUY to SELL.
