import sqlite3
from datetime import datetime

DB_NAME = "falcon.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at TEXT,
            action TEXT,
            symbol TEXT,
            price REAL,
            strategy TEXT,
            decision TEXT,
            reason TEXT,
            broker TEXT,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_trade(row: dict, execution: dict):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO trades (
            received_at, action, symbol, price, strategy,
            decision, reason, broker, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        row.get("received_at", datetime.utcnow().isoformat()),
        row.get("action"),
        row.get("symbol"),
        row.get("price"),
        row.get("strategy"),
        str(row.get("decision")),
        row.get("reason"),
        execution.get("broker"),
        execution.get("status")
    ))
    conn.commit()
    conn.close()


def get_recent_trades(limit: int = 20):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT received_at, action, symbol, price, strategy, decision, broker, status
        FROM trades
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows
