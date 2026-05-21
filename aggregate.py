#!/usr/bin/env python3
"""
Aggregate DuckDB game data into SQLite for the Analytics Dashboard API.
Run this script once (or periodically) to refresh the analytics database.

Usage:
    python aggregate.py
"""

import duckdb
import sqlite3
import os
import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_FILES = {
    "101003": {
        "wide":   os.path.join(BASE_DIR, "101003_20251207_20260207(wide).duckdb"),
        "cohort": os.path.join(BASE_DIR, "101003_20260108_20260318.duckdb"),
    },
    "101007": {
        "wide":   os.path.join(BASE_DIR, "101007_20260107_20260207(wide).duckdb"),
    },
    "102003": {
        "cohort": os.path.join(BASE_DIR, "102003_20260108_20260318.duckdb"),
    },
}

ANALYTICS_DB = os.path.join(BASE_DIR, "analytics.db")


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        DROP TABLE IF EXISTS cohort_matrix;
        DROP TABLE IF EXISTS rtp_daily;
        DROP TABLE IF EXISTS dau_daily;
        DROP TABLE IF EXISTS domains;
        DROP TABLE IF EXISTS games;

        CREATE TABLE games (
            game_id   TEXT PRIMARY KEY,
            date_from TEXT,
            date_to   TEXT,
            has_wide  INTEGER DEFAULT 0,
            has_cohort INTEGER DEFAULT 0
        );

        CREATE TABLE domains (
            game_id TEXT,
            domain  TEXT,
            PRIMARY KEY (game_id, domain)
        );

        -- Daily Active Users per game × domain
        CREATE TABLE dau_daily (
            date         TEXT,
            game_id      TEXT,
            domain       TEXT,
            player_count INTEGER,
            PRIMARY KEY (date, game_id, domain)
        );

        -- Daily RTP and betting metrics per game × domain
        CREATE TABLE rtp_daily (
            date         TEXT,
            game_id      TEXT,
            domain       TEXT,
            avg_rtp      REAL,
            total_bet    REAL,
            avg_bet      REAL,
            total_spins  INTEGER,
            PRIMARY KEY (date, game_id, domain)
        );

        -- Cohort retention matrix: cohort_day × day_index
        CREATE TABLE cohort_matrix (
            game_id        TEXT,
            cohort_day     TEXT,
            day_index      INTEGER,
            cohort_size    INTEGER,
            retention_rate REAL,
            PRIMARY KEY (game_id, cohort_day, day_index)
        );
    """)
    conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def upsert_game(conn: sqlite3.Connection, game_id: str,
                date_from: str, date_to: str,
                has_wide: int = 0, has_cohort: int = 0) -> None:
    row = conn.execute("SELECT date_from, date_to, has_wide, has_cohort FROM games WHERE game_id=?",
                       [game_id]).fetchone()
    if row:
        new_from   = min(row[0], date_from)
        new_to     = max(row[1], date_to)
        new_wide   = max(row[2], has_wide)
        new_cohort = max(row[3], has_cohort)
        conn.execute(
            "UPDATE games SET date_from=?, date_to=?, has_wide=?, has_cohort=? WHERE game_id=?",
            [new_from, new_to, new_wide, new_cohort, game_id]
        )
    else:
        conn.execute("INSERT INTO games VALUES (?,?,?,?,?)",
                     [game_id, date_from, date_to, has_wide, has_cohort])


# ---------------------------------------------------------------------------
# Wide DB: DAU + RTP from MechanismStats
# ---------------------------------------------------------------------------

def aggregate_wide(game_id: str, db_path: str, conn: sqlite3.Connection) -> None:
    log.info(f"[{game_id}] Aggregating wide DB: {os.path.basename(db_path)}")
    t0 = time.time()

    duck = duckdb.connect(db_path, read_only=True)

    # DAU — unique players per day × domain (Normal mode only)
    log.info(f"[{game_id}]   Querying DAU ...")
    dau_df = duck.execute("""
        SELECT
            strftime(Date, '%Y-%m-%d')   AS date,
            Domain                       AS domain,
            COUNT(DISTINCT PlayerID)     AS player_count
        FROM MechanismStats
        WHERE GameID = ? AND Mode = 'Normal'
        GROUP BY Date, Domain
        ORDER BY Date, Domain
    """, [game_id]).fetchdf()

    dau_df["game_id"] = game_id
    conn.executemany(
        "INSERT OR REPLACE INTO dau_daily VALUES (?,?,?,?)",
        dau_df[["date", "game_id", "domain", "player_count"]].values.tolist()
    )
    log.info(f"[{game_id}]   DAU rows: {len(dau_df)}")

    # RTP + Betting — aggregated per day × domain
    log.info(f"[{game_id}]   Querying RTP ...")
    rtp_df = duck.execute("""
        SELECT
            strftime(Date, '%Y-%m-%d') AS date,
            Domain                     AS domain,
            AVG(daily_rtp)             AS avg_rtp,
            SUM(daily_total_bet)       AS total_bet,
            AVG(daily_avg_bet)         AS avg_bet,
            SUM(daily_spin_cnt)        AS total_spins
        FROM MechanismStats
        WHERE GameID = ? AND Mode = 'Normal'
        GROUP BY Date, Domain
        ORDER BY Date, Domain
    """, [game_id]).fetchdf()

    rtp_df["game_id"] = game_id
    conn.executemany(
        "INSERT OR REPLACE INTO rtp_daily VALUES (?,?,?,?,?,?,?)",
        rtp_df[["date", "game_id", "domain", "avg_rtp", "total_bet", "avg_bet", "total_spins"]].values.tolist()
    )
    log.info(f"[{game_id}]   RTP rows: {len(rtp_df)}")

    # Domains
    domains = dau_df["domain"].unique().tolist()
    conn.executemany("INSERT OR IGNORE INTO domains VALUES (?,?)",
                     [(game_id, d) for d in domains])

    date_from = str(dau_df["date"].min())
    date_to   = str(dau_df["date"].max())
    upsert_game(conn, game_id, date_from, date_to, has_wide=1)

    duck.close()
    conn.commit()
    log.info(f"[{game_id}]   Wide done in {time.time()-t0:.1f}s")


# ---------------------------------------------------------------------------
# Cohort DB: Cohort retention matrix + fallback DAU/RTP from VariableX
# ---------------------------------------------------------------------------

def aggregate_cohort(game_id: str, db_path: str, conn: sqlite3.Connection) -> None:
    log.info(f"[{game_id}] Aggregating cohort DB: {os.path.basename(db_path)}")
    t0 = time.time()

    duck = duckdb.connect(db_path, read_only=True)

    # Cohort retention matrix
    log.info(f"[{game_id}]   Querying cohort matrix ...")
    cohort_df = duck.execute("""
        WITH day0 AS (
            SELECT CohortDay, COUNT(DISTINCT PlayerID) AS day0_count
            FROM CohortBase
            WHERE DayIndex = 0
            GROUP BY CohortDay
        )
        SELECT
            CAST(cb.CohortDay AS TEXT)                                        AS cohort_day,
            cb.DayIndex                                                        AS day_index,
            COUNT(DISTINCT cb.PlayerID)                                        AS cohort_size,
            CAST(COUNT(DISTINCT cb.PlayerID) AS DOUBLE) / d0.day0_count       AS retention_rate
        FROM CohortBase cb
        JOIN day0 d0 ON cb.CohortDay = d0.CohortDay
        WHERE cb.DayIndex <= 30
        GROUP BY cb.CohortDay, cb.DayIndex, d0.day0_count
        ORDER BY cb.CohortDay, cb.DayIndex
    """).fetchdf()

    cohort_df["game_id"] = game_id
    conn.executemany(
        "INSERT OR REPLACE INTO cohort_matrix VALUES (?,?,?,?,?)",
        cohort_df[["game_id", "cohort_day", "day_index", "cohort_size", "retention_rate"]].values.tolist()
    )
    log.info(f"[{game_id}]   Cohort matrix rows: {len(cohort_df)}")

    # Domains from VariableX
    domain_df = duck.execute("SELECT DISTINCT Domain FROM VariableX").fetchdf()
    conn.executemany("INSERT OR IGNORE INTO domains VALUES (?,?)",
                     [(game_id, d) for d in domain_df["Domain"].tolist()])

    # Fallback DAU + RTP from VariableX (only if no wide DB data exists)
    has_dau = conn.execute("SELECT 1 FROM dau_daily WHERE game_id=? LIMIT 1", [game_id]).fetchone()
    if not has_dau:
        log.info(f"[{game_id}]   No wide data; computing DAU/RTP from VariableX ...")
        dr_df = duck.execute("""
            SELECT
                CAST(Date AS TEXT)             AS date,
                Domain                         AS domain,
                COUNT(DISTINCT PlayerID)        AS player_count,
                AVG(RTP)                        AS avg_rtp,
                SUM(CAST(SpinCount AS DOUBLE) * AvgBet) AS total_bet,
                AVG(AvgBet)                     AS avg_bet,
                SUM(SpinCount)                  AS total_spins
            FROM VariableX
            GROUP BY Date, Domain
            ORDER BY Date, Domain
        """).fetchdf()

        dr_df["game_id"] = game_id
        conn.executemany(
            "INSERT OR REPLACE INTO dau_daily VALUES (?,?,?,?)",
            dr_df[["date", "game_id", "domain", "player_count"]].values.tolist()
        )
        conn.executemany(
            "INSERT OR REPLACE INTO rtp_daily VALUES (?,?,?,?,?,?,?)",
            dr_df[["date", "game_id", "domain", "avg_rtp", "total_bet", "avg_bet", "total_spins"]].values.tolist()
        )
        log.info(f"[{game_id}]   VariableX DAU/RTP rows: {len(dr_df)}")

    date_from = str(cohort_df["cohort_day"].min())
    date_to   = str(cohort_df["cohort_day"].max())
    upsert_game(conn, game_id, date_from, date_to, has_cohort=1)

    duck.close()
    conn.commit()
    log.info(f"[{game_id}]   Cohort done in {time.time()-t0:.1f}s")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info(f"Creating analytics database: {ANALYTICS_DB}")
    conn = sqlite3.connect(ANALYTICS_DB)
    create_schema(conn)

    for game_id, sources in DB_FILES.items():
        if "wide" in sources:
            aggregate_wide(game_id, sources["wide"], conn)
        if "cohort" in sources:
            aggregate_cohort(game_id, sources["cohort"], conn)

    log.info("Aggregation complete — summary:")
    for table in ["games", "domains", "dau_daily", "rtp_daily", "cohort_matrix"]:
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        log.info(f"  {table:20s}: {n:,} rows")

    conn.close()


if __name__ == "__main__":
    main()
