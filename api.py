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


@app.get("/api/segment")
def get_segment(game_id: str = Query(...)):
    """
    Return cross-segmentation matrix: play_days × total_spins.
    Each cell contains player_count, player_pct, bet_pct, avg_bet_per_player.
    Only available for games with wide data (has_wide=1).
    """
    conn = get_db()
    rows = conn.execute(
        """SELECT day_seg, spin_seg, player_count, player_pct,
                  total_bet, bet_pct, avg_bet_per_player
           FROM segment_cross WHERE game_id=?
           ORDER BY day_seg, spin_seg""",
        [game_id]
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/churn")
def get_churn(game_id: str = Query(...)):
    """
    Return full churn analysis for a game:
    overview, exit_type distribution, and last-3-days trend.
    Only available for games with cohort data (has_cohort=1).
    """
    conn = get_db()
    overview = conn.execute(
        "SELECT * FROM churn_overview WHERE game_id=?", [game_id]
    ).fetchone()
    exit_types = conn.execute(
        "SELECT exit_type, label, player_count, pct FROM churn_exit_type WHERE game_id=? ORDER BY pct DESC",
        [game_id]
    ).fetchall()
    last_days = conn.execute(
        "SELECT day_rank, n_players, avg_win_ratio, avg_exit_balance, pct_losing FROM churn_last_days WHERE game_id=? ORDER BY day_rank",
        [game_id]
    ).fetchall()
    conn.close()

    if not overview:
        return {"overview": None, "exit_types": [], "last_days": []}
    return {
        "overview":   dict(overview),
        "exit_types": [dict(r) for r in exit_types],
        "last_days":  [dict(r) for r in last_days],
    }


@app.get("/api/first_day")
def get_first_day(game_id: str = Query(...)):
    """
    Return first-day-in-7-window retention analysis.
    overview: overall summary; spin_segments / rtp_segments: per-bucket breakdown.
    Only available for games with wide data (has_wide=1).
    """
    conn = get_db()
    overview = conn.execute(
        "SELECT * FROM fdr_overview WHERE game_id=?", [game_id]
    ).fetchone()
    spin_segs = conn.execute(
        """SELECT seg_label, retained, not_retained, retention_pct, avg_rtp_ret, avg_rtp_not
           FROM fdr_segments WHERE game_id=? AND seg_type='spin'
           ORDER BY seg_order""",
        [game_id]
    ).fetchall()
    rtp_segs = conn.execute(
        """SELECT seg_label, retained, not_retained, retention_pct
           FROM fdr_segments WHERE game_id=? AND seg_type='rtp'
           ORDER BY seg_order""",
        [game_id]
    ).fetchall()
    conn.close()

    return {
        "overview":       dict(overview) if overview else None,
        "spin_segments":  [dict(r) for r in spin_segs],
        "rtp_segments":   [dict(r) for r in rtp_segs],
    }


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
