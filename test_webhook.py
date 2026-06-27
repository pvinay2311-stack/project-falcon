import requests

payload = {
    "action": "BUY",
    "symbol": "ES1!",
    "price": 7400.25,
    "strategy": "ES_NQ_TEST",
    "time": "2026-06-27T09:45:00"
}

r = requests.post("http://127.0.0.1:8000/webhook", json=payload)
print(r.status_code)
print(r.json())
