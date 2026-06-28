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

    cur.execute("""
        CREATE TABLE IF NOT EXISTS account_state (
            id INTEGER PRIMARY KEY,
            position TEXT,
            entry_price REAL,
            contracts INTEGER,
            realized_pnl REAL
        )
    """)

    cur.execute("""
        INSERT OR IGNORE INTO account_state
        (id, position, entry_price, contracts, realized_pnl)
        VALUES (1, 'FLAT', NULL, 0, 0.0)
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


def get_account_state():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT position, entry_price, contracts, realized_pnl
        FROM account_state
        WHERE id = 1
    """ )
    row = cur.fetchone()
    conn.close()

    return {
        "position": row[0],
        "entry_price": row[1],
        "contracts": row[2],
        "realized_pnl": row[3]
    }


def save_account_state(position, entry_price, contracts, realized_pnl):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        UPDATE account_state
        SET position = ?, entry_price = ?, contracts = ?, realized_pnl = ?
        WHERE id = 1
    """, (position, entry_price, contracts, realized_pnl))
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


def get_today_trades():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    today = datetime.utcnow().date().isoformat()

    cur.execute("""
        SELECT price, status
        FROM trades
        WHERE received_at LIKE ?
    """, (today + "%",))

    rows = cur.fetchall()
    conn.close()
    return rows
