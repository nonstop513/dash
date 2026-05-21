#!/usr/bin/env python3
"""
Game Analytics REST API — FastAPI + SQLite (local dev).
For production, see workers/index.js (Cloudflare Workers + D1).

Start:
    pip install fastapi uvicorn
    uvicorn api:app --reload --port 8000
"""

import os
import sqlite3
from typing import Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Game Analytics API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "analytics.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/games")
def list_games():
    """Return all available games with date ranges and feature flags."""
    conn = get_db()
    rows = conn.execute("SELECT * FROM games ORDER BY game_id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/domains")
def list_domains(game_id: str = Query(..., description="Game ID, e.g. 101003")):
    """Return all domains that have data for the given game."""
    conn = get_db()
    rows = conn.execute(
        "SELECT domain FROM domains WHERE game_id=? ORDER BY domain", [game_id]
    ).fetchall()
    conn.close()
    return [r["domain"] for r in rows]


@app.get("/api/dau")
def get_dau(
    game_id:   str           = Query(...),
    domain:    Optional[str] = Query(None, description="Domain filter; omit for all domains"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to:   Optional[str] = Query(None, description="YYYY-MM-DD"),
):
    """
    Return daily active users.
    When domain is omitted the result is the total across all domains per date.
    """
    conn = get_db()

    where, params = ["game_id = ?"], [game_id]

    if domain and domain != "ALL":
        where.append("domain = ?")
        params.append(domain)
    if date_from:
        where.append("date >= ?")
        params.append(date_from)
    if date_to:
        where.append("date <= ?")
        params.append(date_to)

    sql = f"""
        SELECT date, domain, SUM(player_count) AS player_count
        FROM dau_daily
        WHERE {" AND ".join(where)}
        GROUP BY date, domain
        ORDER BY date, domain
    """
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/rtp")
def get_rtp(
    game_id:   str           = Query(...),
    domain:    Optional[str] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to:   Optional[str] = Query(None),
):
    """
    Return daily RTP and betting metrics.
    Values are averaged / summed across domains when domain is omitted.
    """
    conn = get_db()

    where, params = ["game_id = ?"], [game_id]

    if domain and domain != "ALL":
        where.append("domain = ?")
        params.append(domain)
    if date_from:
        where.append("date >= ?")
        params.append(date_from)
    if date_to:
        where.append("date <= ?")
        params.append(date_to)

    sql = f"""
        SELECT
            date,
            AVG(avg_rtp)     AS avg_rtp,
            SUM(total_bet)   AS total_bet,
            AVG(avg_bet)     AS avg_bet,
            SUM(total_spins) AS total_spins
        FROM rtp_daily
        WHERE {" AND ".join(where)}
        GROUP BY date
        ORDER BY date
    """
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/cohort")
def get_cohort(
    game_id: str = Query(...),
    max_day: int = Query(30, ge=1, le=69, description="Maximum day index to return"),
):
    """
    Return the cohort retention matrix.
    Each row is (cohort_day, day_index, cohort_size, retention_rate).
    retention_rate = players_on_day_N / players_on_day_0.
    """
    conn = get_db()
    rows = conn.execute(
        """
        SELECT cohort_day, day_index, cohort_size, retention_rate
        FROM cohort_matrix
        WHERE game_id = ? AND day_index <= ?
        ORDER BY cohort_day, day_index
        """,
        [game_id, max_day],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Dev entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
