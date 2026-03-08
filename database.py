"""
SQLite database setup and helper functions.

Why SQLite?
- Built into Python (no install needed, no separate server)
- Data persists across app restarts (unlike in-memory lists)
- Uses standard SQL (same queries work on MySQL/PostgreSQL)
- Perfect for single-server apps; for multi-server, you'd swap to PostgreSQL
"""

import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "transvalidate.db")


def get_connection():
    """Create a new database connection. SQLite needs one per thread."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # So we get dict-like rows instead of tuples
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent read performance
    return conn


def init_db():
    """Create tables if they don't exist. Safe to call multiple times."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            receiver TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            valid INTEGER NOT NULL,
            flags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS blacklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity TEXT NOT NULL UNIQUE,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_transactions_sender
            ON transactions(sender);

        CREATE INDEX IF NOT EXISTS idx_transactions_created
            ON transactions(created_at);
    """)
    conn.commit()
    conn.close()


def save_transaction(sender, receiver, amount, currency, valid, flags):
    """Insert a transaction record into the database."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO transactions (sender, receiver, amount, currency, valid, flags) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (sender, receiver, amount, currency, int(valid), ",".join(flags))
    )
    conn.commit()
    conn.close()


def get_recent_transactions(limit=50):
    """Fetch the most recent transactions."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM transactions ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def count_recent_by_sender(sender, minutes=10):
    """
    Count how many transactions a sender made in the last N minutes.
    This is the core of velocity checking — too many in a short window = suspicious.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM transactions "
        "WHERE sender = ? AND created_at >= datetime('now', ?)",
        (sender, f"-{minutes} minutes")
    ).fetchone()
    conn.close()
    return row["cnt"]


def get_sender_daily_total(sender, currency):
    """
    Sum of all APPROVED transaction amounts by this sender today (in given currency).
    Used for daily cumulative limit enforcement.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(amount), 0) as total FROM transactions "
        "WHERE sender = ? AND currency = ? AND valid = 1 "
        "AND date(created_at) = date('now')",
        (sender, currency)
    ).fetchone()
    conn.close()
    return row["total"]


def find_duplicate(sender, receiver, amount, currency, seconds=60):
    """
    Check if the exact same transaction was submitted recently.
    Catches accidental double-clicks or replay attacks.
    """
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM transactions "
        "WHERE sender = ? AND receiver = ? AND amount = ? AND currency = ? "
        "AND created_at >= datetime('now', ?)",
        (sender, receiver, amount, currency, f"-{seconds} seconds")
    ).fetchone()
    conn.close()
    return row["cnt"] > 0


def is_blacklisted(entity):
    """Check if a sender or receiver is on the blacklist."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM blacklist WHERE entity = ?",
        (entity,)
    ).fetchone()
    conn.close()
    return row["cnt"] > 0


def add_to_blacklist(entity, reason=""):
    """Add an entity (sender/receiver name) to the blacklist."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO blacklist (entity, reason) VALUES (?, ?)",
            (entity, reason)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # Already exists
    finally:
        conn.close()


def remove_from_blacklist(entity):
    """Remove an entity from the blacklist."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM blacklist WHERE entity = ?", (entity,))
    conn.commit()
    removed = cursor.rowcount > 0
    conn.close()
    return removed


def get_blacklist():
    """Get all blacklisted entities."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM blacklist ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_stats():
    """Dashboard stats — total, approved, rejected, approval rate."""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) as cnt FROM transactions").fetchone()["cnt"]
    approved = conn.execute(
        "SELECT COUNT(*) as cnt FROM transactions WHERE valid = 1"
    ).fetchone()["cnt"]
    rejected = total - approved

    top_senders = conn.execute(
        "SELECT sender, COUNT(*) as cnt FROM transactions "
        "GROUP BY sender ORDER BY cnt DESC LIMIT 5"
    ).fetchall()

    conn.close()

    return {
        "total_transactions": total,
        "approved": approved,
        "rejected": rejected,
        "approval_rate": round((approved / total * 100), 1) if total > 0 else 0,
        "top_senders": [dict(r) for r in top_senders]
    }
