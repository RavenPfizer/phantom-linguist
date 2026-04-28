"""
PHANTOM-LINGUIST: Logger Module
SQLite-based logging for reframe operations.
Tracks usage patterns for data-driven config evolution.
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Any, Optional

# Default DB path, overridable via LINGUIST_HOME env var
_DEFAULT_DB_DIR = os.environ.get("LINGUIST_HOME", os.path.dirname(os.path.dirname(__file__)))
DB_PATH = os.path.join(_DEFAULT_DB_DIR, "data", "linguist.db")


def _get_connection() -> sqlite3.Connection:
    """Get SQLite connection, creating tables if needed."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reframe_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            raw_prompt TEXT NOT NULL,
            reframed_prompt TEXT NOT NULL,
            strategy_used TEXT NOT NULL,
            target_model TEXT,
            detected_keywords TEXT,
            specificity_score REAL,
            technical_anchors TEXT,
            result TEXT DEFAULT 'pending',
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS refusal_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            reframe_log_id INTEGER,
            model TEXT NOT NULL,
            refusal_text TEXT,
            trigger_keywords TEXT,
            strategy_failed TEXT,
            FOREIGN KEY (reframe_log_id) REFERENCES reframe_log(id)
        )
    """)
    conn.commit()
    return conn


def log_reframe(
    raw_prompt: str,
    reframed_prompt: str,
    strategy_used: str,
    target_model: str = "unknown",
    detected_keywords: Optional[list] = None,
    specificity_score: float = 0.0,
    technical_anchors: Optional[list] = None,
) -> int:
    """Log a reframe operation. Returns the log entry ID."""
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO reframe_log 
               (timestamp, raw_prompt, reframed_prompt, strategy_used, 
                target_model, detected_keywords, specificity_score, technical_anchors)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                raw_prompt,
                reframed_prompt,
                strategy_used,
                target_model,
                json.dumps(detected_keywords or []),
                specificity_score,
                json.dumps(technical_anchors or []),
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def log_refusal(
    reframe_log_id: int,
    model: str,
    refusal_text: str = "",
    trigger_keywords: Optional[list] = None,
    strategy_failed: str = "",
) -> int:
    """Log a refusal from target AI. Links back to reframe_log entry."""
    conn = _get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO refusal_log
               (timestamp, reframe_log_id, model, refusal_text, 
                trigger_keywords, strategy_failed)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                datetime.now(timezone.utc).isoformat(),
                reframe_log_id,
                model,
                refusal_text,
                json.dumps(trigger_keywords or []),
                strategy_failed,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def update_result(log_id: int, result: str, notes: str = "") -> None:
    """Update the result status of a reframe log entry.
    
    Results: 'success', 'refused', 'partial', 'pending'
    """
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE reframe_log SET result = ?, notes = ? WHERE id = ?",
            (result, notes, log_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_stats() -> dict[str, Any]:
    """Get summary statistics from the reframe log."""
    conn = _get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM reframe_log").fetchone()[0]
        by_result = dict(
            conn.execute(
                "SELECT result, COUNT(*) FROM reframe_log GROUP BY result"
            ).fetchall()
        )
        by_strategy = dict(
            conn.execute(
                "SELECT strategy_used, COUNT(*) FROM reframe_log GROUP BY strategy_used"
            ).fetchall()
        )
        avg_spec = conn.execute(
            "SELECT AVG(specificity_score) FROM reframe_log"
        ).fetchone()[0]
        refusals = conn.execute("SELECT COUNT(*) FROM refusal_log").fetchone()[0]
        
        return {
            "total_reframes": total,
            "by_result": by_result,
            "by_strategy": by_strategy,
            "avg_specificity": round(avg_spec, 3) if avg_spec else 0.0,
            "total_refusals": refusals,
        }
    finally:
        conn.close()
