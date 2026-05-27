# import required libraries
import sqlite3
import os
import time
from app.config import STATS_DB, DATA_DIR


# function to get connection to the database
def _get_conn():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(STATS_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# function to initialize the database
def init_db():
    conn = _get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bot_id TEXT NOT NULL,
            timestamp REAL NOT NULL,
            latency_ms REAL NOT NULL,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            unanswered INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


# function to record a message
def record_message(bot_id, latency_ms, input_tokens=0, output_tokens=0, unanswered=False):
    conn = _get_conn()
    conn.execute(
        """INSERT INTO chat_stats
           (bot_id, timestamp, latency_ms, input_tokens, output_tokens, unanswered)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (bot_id, time.time(), latency_ms, input_tokens, output_tokens, 1 if unanswered else 0),
    )
    conn.commit()
    conn.close()


# function to get stats for a bot
def get_stats(bot_id):
    conn = _get_conn()
    cursor = conn.execute(
        """SELECT
            COUNT(*) as total,
            COALESCE(AVG(latency_ms), 0) as avg_lat,
            COALESCE(SUM(input_tokens), 0) as inp_tok,
            COALESCE(SUM(output_tokens), 0) as out_tok,
            COALESCE(SUM(unanswered), 0) as unans
        FROM chat_stats
        WHERE bot_id = ?""",
        (bot_id,),
    )
    row = cursor.fetchone()
    conn.close()

    if not row or row[0] == 0:
        return {
            "total_messages": 0,
            "avg_latency_ms": 0.0,
            "estimated_cost_usd": 0.0,
            "unanswered_questions": 0,
        }

    total, avg_lat, inp_tok, out_tok, unans = row

    # estimate cost based on approximate groq pricing
    from app.config import INPUT_COST_PER_M, OUTPUT_COST_PER_M

    cost = (inp_tok / 1_000_000 * INPUT_COST_PER_M) + (
        out_tok / 1_000_000 * OUTPUT_COST_PER_M
    )

    return {
        "total_messages": total,
        "avg_latency_ms": round(avg_lat, 2),
        "estimated_cost_usd": round(cost, 6),
        "unanswered_questions": unans,
    }
