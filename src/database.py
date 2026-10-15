import sqlite3
import json
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
from src.config import Config

def get_connection() -> sqlite3.Connection:
    Config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alerted_at INTEGER NOT NULL,
                token_address TEXT NOT NULL,
                pair_address TEXT,
                chain_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                price_usd_at_alert REAL NOT NULL,
                market_cap_at_alert REAL,
                liquidity_usd_at_alert REAL,
                volume_24h_at_alert REAL,
                momentum_score REAL NOT NULL,
                price_change_1h REAL,
                price_change_6h REAL,
                price_change_24h REAL,
                buyer_ratio_1h REAL,
                volume_accel_1h REAL,
                metrics_json TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_token ON alerts(token_address)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts(alerted_at)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS performance_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                evaluated_at INTEGER NOT NULL,
                hours_since_alert REAL NOT NULL,
                current_price_usd REAL NOT NULL,
                price_change_pct REAL NOT NULL,
                max_price_usd REAL,
                max_gain_pct REAL,
                FOREIGN KEY (alert_id) REFERENCES alerts(id)
            )
        """)
    conn.close()

def record_alert(token_data: Dict[str, Any]) -> int:
    conn = get_connection()
    now_ts = int(time.time())
    with conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO alerts (
                alerted_at, token_address, pair_address, chain_id,
                symbol, name, price_usd_at_alert, market_cap_at_alert,
                liquidity_usd_at_alert, volume_24h_at_alert, momentum_score,
                price_change_1h, price_change_6h, price_change_24h,
                buyer_ratio_1h, volume_accel_1h, metrics_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now_ts,
            token_data["token_address"],
            token_data.get("pair_address"),
            token_data["chain_id"],
            token_data["symbol"],
            token_data.get("name"),
            token_data["price_usd"],
            token_data.get("market_cap"),
            token_data.get("liquidity_usd"),
            token_data.get("volume_24h"),
            token_data["momentum_score"],
            token_data.get("price_change_1h"),
            token_data.get("price_change_6h"),
            token_data.get("price_change_24h"),
            token_data.get("buyer_ratio_1h"),
            token_data.get("volume_accel_1h"),
            json.dumps(token_data)
        ))
        inserted_id = cur.lastrowid
    conn.close()
    return inserted_id

def get_last_alert(token_address: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM alerts 
        WHERE token_address = ? 
        ORDER BY alerted_at DESC 
        LIMIT 1
    """, (token_address,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_alerts(limit: int = 100) -> List[Dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM alerts 
        ORDER BY alerted_at DESC 
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def record_evaluation(alert_id: int, hours_since: float, current_price: float, change_pct: float, max_price: float, max_gain: float):
    conn = get_connection()
    now_ts = int(time.time())
    with conn:
        conn.execute("""
            INSERT INTO performance_evaluations (
                alert_id, evaluated_at, hours_since_alert,
                current_price_usd, price_change_pct, max_price_usd, max_gain_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (alert_id, now_ts, hours_since, current_price, change_pct, max_price, max_gain))
    conn.close()
