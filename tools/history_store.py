import sqlite3
from datetime import date
from pathlib import Path

DB_PATH = Path("data/history.db")


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS player_snapshots (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                player_name         TEXT    NOT NULL,
                snapshot_date       TEXT    NOT NULL,
                market_value_eur    REAL,
                contract_expires    TEXT,
                days_until_expiry   INTEGER,
                UNIQUE(player_name, snapshot_date)
            )
        """)


def save_snapshot(
    player_name: str,
    market_value_eur: float | None,
    contract_expires: str | None,
    days_until_expiry: int | None,
    snapshot_date: str | None = None,
) -> None:
    if snapshot_date is None:
        snapshot_date = date.today().isoformat()
    with _conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO player_snapshots
                (player_name, snapshot_date, market_value_eur, contract_expires, days_until_expiry)
            VALUES (?, ?, ?, ?, ?)
            """,
            (player_name, snapshot_date, market_value_eur, contract_expires, days_until_expiry),
        )


def get_snapshots(player_name: str) -> list[dict]:
    """Return all weekly snapshots for a player, oldest first."""
    with _conn() as conn:
        rows = conn.execute(
            """
            SELECT snapshot_date, market_value_eur, contract_expires, days_until_expiry
            FROM player_snapshots
            WHERE player_name = ?
            ORDER BY snapshot_date ASC
            """,
            (player_name,),
        ).fetchall()
    return [dict(r) for r in rows]


# Initialize DB table on module import so the schema is always ready.
init_db()
