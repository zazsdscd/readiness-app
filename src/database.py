"""Persistance des check-ins dans une base SQLite locale.

Un check-in par jour (la date est cle primaire). Une nouvelle saisie
le meme jour met a jour la precedente plutot que de creer un doublon.
"""

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "readiness.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS checkins (
    date           TEXT PRIMARY KEY,   -- 'YYYY-MM-DD'
    sleep_quality  INTEGER,
    energy         INTEGER,
    freshness      INTEGER,
    mood           INTEGER,
    motivation     INTEGER,
    sleep_hours    REAL,
    note           TEXT,
    created_at     TEXT DEFAULT (datetime('now'))
);
"""


def get_conn(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(_SCHEMA)
    return conn


def upsert_checkin(record: dict, db_path: Path = DB_PATH) -> None:
    """Insere ou met a jour le check-in du jour."""
    cols = ["date", "sleep_quality", "energy", "freshness", "mood",
            "motivation", "sleep_hours", "note"]
    values = [record.get(c) for c in cols]
    placeholders = ", ".join(["?"] * len(cols))
    update_clause = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "date")
    sql = (
        f"INSERT INTO checkins ({', '.join(cols)}) VALUES ({placeholders}) "
        f"ON CONFLICT(date) DO UPDATE SET {update_clause}"
    )
    with get_conn(db_path) as conn:
        conn.execute(sql, values)
        conn.commit()


def fetch_all(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Retourne tous les check-ins, tries par date croissante."""
    with get_conn(db_path) as conn:
        df = pd.read_sql_query(
            "SELECT * FROM checkins ORDER BY date ASC", conn
        )
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def bulk_insert(df: pd.DataFrame, db_path: Path = DB_PATH) -> None:
    """Charge un DataFrame complet (utilise pour les donnees demo)."""
    out = df.copy()
    if "date" in out and not pd.api.types.is_string_dtype(out["date"]):
        out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    with get_conn(db_path) as conn:
        for _, row in out.iterrows():
            upsert_checkin(row.to_dict(), db_path)


def reset_db(db_path: Path = DB_PATH) -> None:
    with get_conn(db_path) as conn:
        conn.execute("DELETE FROM checkins")
        conn.commit()
