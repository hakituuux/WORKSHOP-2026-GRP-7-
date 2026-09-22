# couche sqlite toute simple
# une connexion par appel -> flask et mqtt peuvent ecrire en meme temps sans se marcher dessus

import sqlite3
import time
from contextlib import closing

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    ts     REAL NOT NULL,   -- timestamp unix
    metric TEXT NOT NULL,   -- soil / temp / humidity / lux / etc
    value  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_readings_metric_ts ON readings (metric, ts);

CREATE TABLE IF NOT EXISTS events (
    ts     REAL NOT NULL,
    kind   TEXT NOT NULL,   -- pump, light, state, status, command...
    detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events (ts);
"""


def _connect() -> sqlite3.Connection:
    # helper interne : ouvre + row_factory pour avoir des dict-like
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    # a lancer au boot : cree tables + mode wal (lectures ok pendant une ecriture)
    with closing(_connect()) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)


def add_reading(metric: str, value: float, ts: float | None = None) -> None:
    # insert une mesure (sol, temp, etc)
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO readings (ts, metric, value) VALUES (?, ?, ?)",
            (ts or time.time(), metric, value),
        )


def add_event(kind: str, detail: str, ts: float | None = None) -> None:
    # insert un event (changement pompe, cmd manuelle...)
    with closing(_connect()) as conn, conn:
        conn.execute(
            "INSERT INTO events (ts, kind, detail) VALUES (?, ?, ?)",
            (ts or time.time(), kind, detail),
        )


def history(metric: str, hours: float, max_points: int = 500) -> list[list[float]]:
    # historique pour les graphiques : on bucket/moyenne pour pas exploser le front
    since = time.time() - hours * 3600
    bucket = max(1.0, hours * 3600 / max_points)  # largeur d'un point en sec
    with closing(_connect()) as conn:
        rows = conn.execute(
            """
            SELECT CAST(ts / :bucket AS INTEGER) * :bucket AS t, AVG(value) AS v
            FROM readings
            WHERE metric = :metric AND ts >= :since
            GROUP BY 1
            ORDER BY 1
            """,
            {"bucket": bucket, "metric": metric, "since": since},
        ).fetchall()
    return [[row["t"], round(row["v"], 2)] for row in rows]


def events(limit: int = 50) -> list[dict]:
    # derniers events, du plus recent au plus vieux
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT ts, kind, detail FROM events ORDER BY ts DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(row) for row in rows]


def all_readings():
    # pour l'export csv : generateur, on charge pas toute la db d'un coup
    with closing(_connect()) as conn:
        yield from conn.execute("SELECT ts, metric, value FROM readings ORDER BY ts")
