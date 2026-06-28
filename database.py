import sqlite3
import os
from datetime import datetime

DB_NAME = "falcon.db"
DATABASE_URL = os.getenv("DATABASE_URL")
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError:
        print("Warning: psycopg2 not installed. Falling back to SQLite.")
        USE_POSTGRES = False


def get_db_connection():
    """Get database connection (PostgreSQL or SQLite)
    
    For PostgreSQL:
    - Automatically enables SSL/TLS for Neon
    - Supports standard Neon connection strings
    - Implements connection pooling parameters
    
    For SQLite:
    - Uses local falcon.db file
    """
    if USE_POSTGRES:
        # Neon PostgreSQL with SSL/TLS support
        return psycopg2.connect(
            DATABASE_URL,
            sslmode="require",  # Enforce SSL for Neon
            connect_timeout=10
        )
    else:
        return sqlite3.connect(DB_NAME)


def get_db_cursor(conn):
    """Get cursor from connection"""
    if USE_POSTGRES:
        return conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    else:
        conn.row_factory = sqlite3.Row
        return conn.cursor()


def init_db():
    """Initialize database tables
    
    Creates trades and account_state tables if they don't exist.
    Supports both PostgreSQL (Neon) and SQLite.
    """
    try:
        conn = get_db_connection()
        cur = get_db_cursor(conn)

        if USE_POSTGRES:
            # PostgreSQL schema (Neon compatible)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id SERIAL PRIMARY KEY,
                    received_at TEXT,
                    action TEXT,
                    symbol TEXT,
                    price REAL,
                    strategy TEXT,
                    decision TEXT,
                    reason TEXT,
                    broker TEXT,
                    status TEXT,
                    score INTEGER,
                    pnl REAL,
                    position_after TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS account_state (
                    id INTEGER PRIMARY KEY,
                    position TEXT,
                    entry_price REAL,
                    contracts INTEGER,
                    realized_pnl REAL,
                    stop_price REAL,
                    target_price REAL
                )
            """)

            # Insert default account state if not exists
            cur.execute("""
                INSERT INTO account_state (id, position, entry_price, contracts, realized_pnl, stop_price, target_price)
                VALUES (1, 'FLAT', NULL, 0, 0.0, NULL, NULL)
                ON CONFLICT (id) DO NOTHING
            """)
        else:
            # SQLite schema
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
                    status TEXT,
                    score INTEGER,
                    pnl REAL,
                    position_after TEXT
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS account_state (
                    id INTEGER PRIMARY KEY,
                    position TEXT,
                    entry_price REAL,
                    contracts INTEGER,
                    realized_pnl REAL,
                    stop_price REAL,
                    target_price REAL
                )
            """)

            # Insert default account state if not exists
            cur.execute("""
                INSERT OR IGNORE INTO account_state
                (id, position, entry_price, contracts, realized_pnl, stop_price, target_price)
                VALUES (1, 'FLAT', NULL, 0, 0.0, NULL, NULL)
            """)

        conn.commit()
        conn.close()
        
        if USE_POSTGRES:
            print("✅ PostgreSQL (Neon) database initialized")
        else:
            print("✅ SQLite database initialized")
            
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        raise


def save_trade(row: dict, execution: dict, score: int | None = None, pnl: float | None = None, position_after: str | None = None):
    conn = get_db_connection()
    cur = get_db_cursor(conn)
    
    if USE_POSTGRES:
        cur.execute("""
            INSERT INTO trades (
                received_at, action, symbol, price, strategy,
                decision, reason, broker, status, score, pnl, position_after
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            row.get("received_at", datetime.utcnow().isoformat()),
            row.get("action"),
            row.get("symbol"),
            row.get("price"),
            row.get("strategy"),
            str(row.get("decision")),
            row.get("reason"),
            execution.get("broker"),
            execution.get("status"),
            score,
            pnl,
            position_after
        ))
    else:
        cur.execute("""
            INSERT INTO trades (
                received_at, action, symbol, price, strategy,
                decision, reason, broker, status, score, pnl, position_after
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row.get("received_at", datetime.utcnow().isoformat()),
            row.get("action"),
            row.get("symbol"),
            row.get("price"),
            row.get("strategy"),
            str(row.get("decision")),
            row.get("reason"),
            execution.get("broker"),
            execution.get("status"),
            score,
            pnl,
            position_after
        ))
    conn.commit()
    conn.close()


def get_recent_trades(limit: int = 20):
    conn = get_db_connection()
    cur = get_db_cursor(conn)
    
    if USE_POSTGRES:
        cur.execute("""
            SELECT received_at, action, symbol, price, strategy, decision, broker, status, score, pnl, position_after
            FROM trades
            ORDER BY id DESC
            LIMIT %s
        """, (limit,))
    else:
        cur.execute("""
            SELECT received_at, action, symbol, price, strategy, decision, broker, status, score, pnl, position_after
            FROM trades
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
    
    rows = cur.fetchall()
    conn.close()
    return rows


def get_today_trades():
    conn = get_db_connection()
    cur = get_db_cursor(conn)
    today = datetime.utcnow().date().isoformat()

    if USE_POSTGRES:
        cur.execute("""
            SELECT price, status, score, pnl
            FROM trades
            WHERE received_at LIKE %s
        """, (today + "%",))
    else:
        cur.execute("""
            SELECT price, status, score, pnl
            FROM trades
            WHERE received_at LIKE ?
        """, (today + "%",))

    rows = cur.fetchall()
    conn.close()
    return rows


def get_account_state():
    conn = get_db_connection()
    cur = get_db_cursor(conn)
    
    if USE_POSTGRES:
        cur.execute("""
            SELECT position, entry_price, contracts, realized_pnl, stop_price, target_price
            FROM account_state
            WHERE id = %s
        """, (1,))
    else:
        cur.execute("""
            SELECT position, entry_price, contracts, realized_pnl, stop_price, target_price
            FROM account_state
            WHERE id = ?
        """, (1,))
    
    row = cur.fetchone()
    conn.close()
    return {
        "position": row[0],
        "entry_price": row[1],
        "contracts": row[2],
        "realized_pnl": row[3],
        "stop_price": row[4],
        "target_price": row[5]
    }


def save_account_state(position, entry_price, contracts, realized_pnl, stop_price=None, target_price=None):
    conn = get_db_connection()
    cur = get_db_cursor(conn)
    
    if USE_POSTGRES:
        cur.execute("""
            UPDATE account_state
            SET position = %s, entry_price = %s, contracts = %s, realized_pnl = %s, stop_price = %s, target_price = %s
            WHERE id = %s
        """, (position, entry_price, contracts, realized_pnl, stop_price, target_price, 1))
    else:
        cur.execute("""
            UPDATE account_state
            SET position = ?, entry_price = ?, contracts = ?, realized_pnl = ?, stop_price = ?, target_price = ?
            WHERE id = ?
        """, (position, entry_price, contracts, realized_pnl, stop_price, target_price, 1))
    
    conn.commit()
    conn.close()


def test_connection():
    """Test database connectivity
    
    Useful for debugging Neon PostgreSQL connections.
    Returns tuple: (success: bool, message: str)
    """
    try:
        conn = get_db_connection()
        cur = get_db_cursor(conn)
        
        if USE_POSTGRES:
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
            conn.close()
            return True, f"✅ PostgreSQL connected: {version[:50]}..."
        else:
            cur.execute("SELECT sqlite_version()")
            version = cur.fetchone()[0]
            conn.close()
            return True, f"✅ SQLite connected: {version}"
    except Exception as e:
        return False, f"❌ Database connection failed: {str(e)}"


def get_db_status():
    """Get database status and configuration
    
    Returns dict with backend type and connection details.
    """
    return {
        "backend": "PostgreSQL (Neon)" if USE_POSTGRES else "SQLite",
        "database_url": "***configured***" if USE_POSTGRES else DB_NAME,
        "use_postgres": USE_POSTGRES,
        "ssl_enabled": USE_POSTGRES
    }
