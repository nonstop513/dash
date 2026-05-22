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
import pandas as pd  # noqa: F401  (used in aggregate_segment)

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
        DROP TABLE IF EXISTS fdr_segments;
        DROP TABLE IF EXISTS fdr_overview;
        DROP TABLE IF EXISTS churn_last_days;
        DROP TABLE IF EXISTS churn_exit_type;
        DROP TABLE IF EXISTS churn_overview;
        DROP TABLE IF EXISTS cohort_matrix;
        DROP TABLE IF EXISTS segment_cross;
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

        -- Churn analysis: overall player counts
        CREATE TABLE churn_overview (
            game_id         TEXT PRIMARY KEY,
            total_players   INTEGER,
            churned_players INTEGER,
            active_players  INTEGER,
            churn_rate      REAL,
            churn_cutoff    TEXT
        );

        -- Churn analysis: exit type distribution (last-day WinRatio buckets)
        CREATE TABLE churn_exit_type (
            game_id       TEXT,
            exit_type     TEXT,
            label         TEXT,
            player_count  INTEGER,
            pct           REAL,
            PRIMARY KEY (game_id, exit_type)
        );

        -- Cross-segmentation: play_days × total_spins
        CREATE TABLE segment_cross (
            game_id       TEXT,
            day_seg       TEXT,
            spin_seg      TEXT,
            player_count  INTEGER,
            player_pct    REAL,
            total_bet     REAL,
            bet_pct       REAL,
            avg_bet_per_player REAL,
            PRIMARY KEY (game_id, day_seg, spin_seg)
        );

        -- Churn analysis: avg metrics in last 3 days before churn
        CREATE TABLE churn_last_days (
            game_id          TEXT,
            day_rank         INTEGER,
            n_players        INTEGER,
            avg_win_ratio    REAL,
            avg_exit_balance REAL,
            pct_losing       REAL,
            PRIMARY KEY (game_id, day_rank)
        );

        -- First-day-in-7-window retention: overall summary
        CREATE TABLE fdr_overview (
            game_id        TEXT PRIMARY KEY,
            total_records  INTEGER,
            retained       INTEGER,
            not_retained   INTEGER,
            retention_pct  REAL,
            avg_spin_ret   REAL,
            avg_spin_not   REAL,
            med_spin_ret   REAL,
            med_spin_not   REAL,
            avg_rtp_ret    REAL,
            avg_rtp_not    REAL
        );

        -- First-day-in-7-window retention: per segment breakdown
        CREATE TABLE fdr_segments (
            game_id        TEXT,
            seg_type       TEXT,
            seg_order      INTEGER,
            seg_label      TEXT,
            retained       INTEGER,
            not_retained   INTEGER,
            retention_pct  REAL,
            avg_rtp_ret    REAL,
            avg_rtp_not    REAL,
            PRIMARY KEY (game_id, seg_type, seg_label)
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
# Cross-segmentation: play_days × total_spins (wide DB)
# ---------------------------------------------------------------------------

DAY_BINS  = [0, 1, 3, 7, 14, 9999]
DAY_LABELS = ["1天", "2-3天", "4-7天", "8-14天", "15天+"]
SPIN_BINS  = [0, 100, 500, 2000, 10000, 99_999_999]
SPIN_LABELS = ["1-100", "101-500", "501-2000", "2001-10000", "10000+"]

def aggregate_segment(game_id: str, db_path: str, conn: sqlite3.Connection) -> None:
    log.info(f"[{game_id}] Aggregating cross-segmentation ...")
    t0 = time.time()

    duck = duckdb.connect(db_path, read_only=True)
    df = duck.execute("""
        SELECT
            PlayerID,
            COUNT(DISTINCT Date)  AS play_days,
            SUM(daily_spin_cnt)   AS total_spins,
            SUM(daily_total_bet)  AS total_bet
        FROM MechanismStats
        WHERE GameID = ? AND Mode = 'Normal'
        GROUP BY PlayerID
    """, [game_id]).fetchdf()
    duck.close()

    total_bet     = df["total_bet"].sum()
    total_players = len(df)

    df["day_seg"]  = pd.cut(df["play_days"],   bins=DAY_BINS,  labels=DAY_LABELS,  right=True)
    df["spin_seg"] = pd.cut(df["total_spins"],  bins=SPIN_BINS, labels=SPIN_LABELS, right=True)

    grp = df.groupby(["day_seg", "spin_seg"], observed=True).agg(
        player_count=("PlayerID", "count"),
        total_bet=("total_bet", "sum"),
    ).reset_index()

    grp["player_pct"]        = (grp["player_count"] / total_players * 100).round(2)
    grp["bet_pct"]           = (grp["total_bet"]    / total_bet     * 100).round(2)
    grp["avg_bet_per_player"] = (grp["total_bet"]   / grp["player_count"]).round(0)

    rows = []
    for _, r in grp.iterrows():
        rows.append((
            game_id,
            str(r["day_seg"]),
            str(r["spin_seg"]),
            int(r["player_count"]),
            float(r["player_pct"]),
            float(r["total_bet"]),
            float(r["bet_pct"]),
            float(r["avg_bet_per_player"]),
        ))

    conn.executemany("INSERT OR REPLACE INTO segment_cross VALUES (?,?,?,?,?,?,?,?)", rows)
    conn.commit()
    log.info(f"[{game_id}]   Segment cross rows: {len(rows)}, done in {time.time()-t0:.1f}s")


# ---------------------------------------------------------------------------
# Churn analysis (requires cohort DB with VariableX balance columns)
# ---------------------------------------------------------------------------

def aggregate_churn(game_id: str, db_path: str, conn: sqlite3.Connection) -> None:
    log.info(f"[{game_id}] Aggregating churn analysis ...")
    t0 = time.time()

    duck = duckdb.connect(db_path, read_only=True)
    max_date     = duck.execute("SELECT MAX(Date) FROM VariableX").fetchone()[0]
    cutoff       = (pd.Timestamp(max_date) - pd.Timedelta(days=7)).date()
    cutoff_str   = str(cutoff)

    # --- Overview: churned vs active ---
    ov = duck.execute(f"""
        WITH last_dates AS (
            SELECT PlayerID, MAX(Date) AS last_date
            FROM VariableX GROUP BY PlayerID
        )
        SELECT
            COUNT(*)                                                    AS total,
            SUM(CASE WHEN last_date <  '{cutoff_str}' THEN 1 ELSE 0 END) AS churned,
            SUM(CASE WHEN last_date >= '{cutoff_str}' THEN 1 ELSE 0 END) AS active
        FROM last_dates
    """).fetchone()
    total, churned, active = ov
    conn.execute(
        "INSERT OR REPLACE INTO churn_overview VALUES (?,?,?,?,?,?)",
        [game_id, int(total), int(churned), int(active), churned/total, cutoff_str]
    )
    log.info(f"[{game_id}]   Churned {churned:,} / {total:,} ({churned/total*100:.1f}%)")

    # --- Exit type: WinRatio buckets on last day ---
    ex = duck.execute(f"""
        SELECT
            SUM(CASE WHEN WinRatio <  0.1                         THEN 1 ELSE 0 END) AS busted,
            SUM(CASE WHEN WinRatio >= 0.1 AND WinRatio <  0.5    THEN 1 ELSE 0 END) AS heavy_loss,
            SUM(CASE WHEN WinRatio >= 0.5 AND WinRatio <  1.0    THEN 1 ELSE 0 END) AS light_loss,
            SUM(CASE WHEN WinRatio >= 1.0                         THEN 1 ELSE 0 END) AS profit,
            COUNT(*) AS n
        FROM VariableX vx
        JOIN (
            SELECT PlayerID, MAX(Date) AS last_date
            FROM VariableX WHERE Date < '{cutoff_str}'
            GROUP BY PlayerID
        ) t ON vx.PlayerID = t.PlayerID AND vx.Date = t.last_date
    """).fetchone()
    busted, heavy, light, profit, n = ex
    types = [
        ("busted",     "輸光 (WinRatio < 0.1)",  busted, busted/n*100),
        ("heavy_loss", "重損 (0.1 ~ 0.5)",       heavy,  heavy/n*100),
        ("light_loss", "小輸 (0.5 ~ 1.0)",       light,  light/n*100),
        ("profit",     "贏錢離場 (≥ 1.0)",       profit, profit/n*100),
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO churn_exit_type VALUES (?,?,?,?,?)",
        [(game_id, t[0], t[1], int(t[2]), round(t[3], 2)) for t in types]
    )

    # --- Last 3 days trend ---
    trend = duck.execute(f"""
        WITH ranked AS (
            SELECT PlayerID, Date, WinRatio, LastAfterBalance,
                   RANK() OVER (PARTITION BY PlayerID ORDER BY Date DESC) AS day_rank
            FROM VariableX WHERE Date < '{cutoff_str}'
        )
        SELECT
            day_rank,
            COUNT(*)                                                            AS n_players,
            ROUND(AVG(WinRatio), 4)                                             AS avg_win_ratio,
            ROUND(AVG(LastAfterBalance), 2)                                     AS avg_exit_balance,
            ROUND(SUM(CASE WHEN WinRatio < 1 THEN 1.0 ELSE 0.0 END)
                  / COUNT(*) * 100, 2)                                          AS pct_losing
        FROM ranked WHERE day_rank <= 3
        GROUP BY day_rank ORDER BY day_rank
    """).fetchdf()

    conn.executemany(
        "INSERT OR REPLACE INTO churn_last_days VALUES (?,?,?,?,?,?)",
        [(game_id, int(r.day_rank), int(r.n_players),
          float(r.avg_win_ratio), float(r.avg_exit_balance), float(r.pct_losing))
         for r in trend.itertuples()]
    )

    duck.close()
    conn.commit()
    log.info(f"[{game_id}]   Churn analysis done in {time.time()-t0:.1f}s")


# ---------------------------------------------------------------------------
# First-Day-in-7-Window Retention (wide DB)
# ---------------------------------------------------------------------------

FDR_SPIN_BINS   = [0, 100, 500, 2000, 10_000, 99_999_999]
FDR_SPIN_LABELS = ["1-100", "101-500", "501-2000", "2001-10000", "10000+"]
FDR_RTP_BINS    = [-0.001, 0.5, 0.8, 0.9, 0.95, 1.0, 1.1, 1.25, 9999]
FDR_RTP_LABELS  = ["<50%", "50-80%", "80-90%", "90-95%", "95-100%",
                   "100-110%", "110-125%", ">125%"]

def aggregate_fdr(game_id: str, db_path: str, conn: sqlite3.Connection) -> None:
    log.info(f"[{game_id}] Aggregating first-day-in-7-window retention ...")
    t0 = time.time()

    duck = duckdb.connect(db_path, read_only=True)

    df = duck.execute("""
        WITH base AS (
            SELECT
                PlayerID,
                CAST(Date AS DATE)      AS play_date,
                SUM(daily_spin_cnt)     AS daily_spin_cnt,
                AVG(daily_rtp)          AS daily_rtp,
                SUM(daily_total_bet)    AS daily_total_bet
            FROM MechanismStats
            WHERE GameID = ? AND Mode = 'Normal'
            GROUP BY PlayerID, CAST(Date AS DATE)
        ),
        with_prev AS (
            SELECT *,
                   LAG(play_date) OVER (PARTITION BY PlayerID ORDER BY play_date) AS prev_date
            FROM base
        ),
        first_in_window AS (
            -- prev_date IS NULL (first ever login) OR gap > 6 days
            SELECT * FROM with_prev
            WHERE prev_date IS NULL OR (play_date - prev_date) > 6
        )
        SELECT
            fiw.daily_spin_cnt,
            fiw.daily_rtp,
            fiw.daily_total_bet,
            CASE WHEN EXISTS (
                SELECT 1 FROM base b
                WHERE b.PlayerID  = fiw.PlayerID
                  AND b.play_date = fiw.play_date + 1
            ) THEN 1 ELSE 0 END AS returned_next_day
        FROM first_in_window fiw
    """, [game_id]).fetchdf()

    duck.close()

    # ── Overall overview ─────────────────────────────────────────────────────
    ret = df[df["returned_next_day"] == 1]
    nrt = df[df["returned_next_day"] == 0]
    total = len(df)

    conn.execute(
        "INSERT OR REPLACE INTO fdr_overview VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        [
            game_id,
            int(total),
            int(len(ret)),
            int(len(nrt)),
            round(len(ret) / total * 100, 2),
            round(float(ret["daily_spin_cnt"].mean()), 2),
            round(float(nrt["daily_spin_cnt"].mean()), 2),
            round(float(ret["daily_spin_cnt"].median()), 2),
            round(float(nrt["daily_spin_cnt"].median()), 2),
            round(float(ret["daily_rtp"].mean()), 4),
            round(float(nrt["daily_rtp"].mean()), 4),
        ]
    )
    log.info(f"[{game_id}]   FDR overview: total={total:,}, "
             f"retained={len(ret):,} ({len(ret)/total*100:.1f}%)")

    # ── Spin segmentation ────────────────────────────────────────────────────
    df["spin_seg"] = pd.cut(df["daily_spin_cnt"], bins=FDR_SPIN_BINS,
                            labels=FDR_SPIN_LABELS, right=True)
    spin_grp = (
        df.groupby(["spin_seg", "returned_next_day"], observed=True)
          .agg(count=("daily_spin_cnt", "count"), avg_rtp=("daily_rtp", "mean"))
          .reset_index()
    )
    spin_wide = spin_grp.pivot(index="spin_seg", columns="returned_next_day",
                                values="count").fillna(0)
    spin_rtp  = spin_grp.pivot(index="spin_seg", columns="returned_next_day",
                                values="avg_rtp")

    for order, label in enumerate(FDR_SPIN_LABELS):
        if label not in spin_wide.index:
            continue
        r_cnt = int(spin_wide.loc[label, 1]) if 1 in spin_wide.columns else 0
        n_cnt = int(spin_wide.loc[label, 0]) if 0 in spin_wide.columns else 0
        tot   = r_cnt + n_cnt
        if tot == 0:
            continue
        r_rtp = round(float(spin_rtp.loc[label, 1]), 4) if (1 in spin_rtp.columns and label in spin_rtp.index and not pd.isna(spin_rtp.loc[label, 1])) else None
        n_rtp = round(float(spin_rtp.loc[label, 0]), 4) if (0 in spin_rtp.columns and label in spin_rtp.index and not pd.isna(spin_rtp.loc[label, 0])) else None
        conn.execute(
            "INSERT OR REPLACE INTO fdr_segments VALUES (?,?,?,?,?,?,?,?,?)",
            [game_id, "spin", order, label, r_cnt, n_cnt,
             round(r_cnt / tot * 100, 2), r_rtp, n_rtp]
        )

    # ── RTP segmentation ─────────────────────────────────────────────────────
    df["rtp_seg"] = pd.cut(df["daily_rtp"], bins=FDR_RTP_BINS,
                           labels=FDR_RTP_LABELS, right=True)
    rtp_grp = (
        df.groupby(["rtp_seg", "returned_next_day"], observed=True)
          .agg(count=("daily_spin_cnt", "count"))
          .reset_index()
    )
    rtp_wide = rtp_grp.pivot(index="rtp_seg", columns="returned_next_day",
                              values="count").fillna(0)

    for order, label in enumerate(FDR_RTP_LABELS):
        if label not in rtp_wide.index:
            continue
        r_cnt = int(rtp_wide.loc[label, 1]) if 1 in rtp_wide.columns else 0
        n_cnt = int(rtp_wide.loc[label, 0]) if 0 in rtp_wide.columns else 0
        tot   = r_cnt + n_cnt
        if tot == 0:
            continue
        conn.execute(
            "INSERT OR REPLACE INTO fdr_segments VALUES (?,?,?,?,?,?,?,?,?)",
            [game_id, "rtp", order, label, r_cnt, n_cnt,
             round(r_cnt / tot * 100, 2), None, None]
        )

    conn.commit()
    log.info(f"[{game_id}]   FDR segments done in {time.time()-t0:.1f}s")


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
            aggregate_segment(game_id, sources["wide"], conn)
            aggregate_fdr(game_id, sources["wide"], conn)
        if "cohort" in sources:
            aggregate_cohort(game_id, sources["cohort"], conn)
            aggregate_churn(game_id, sources["cohort"], conn)

    log.info("Aggregation complete — summary:")
    for table in ["games", "domains", "dau_daily", "rtp_daily",
                  "cohort_matrix", "segment_cross",
                  "churn_overview", "churn_exit_type", "churn_last_days",
                  "fdr_overview", "fdr_segments"]:
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        log.info(f"  {table:20s}: {n:,} rows")

    conn.close()


if __name__ == "__main__":
    main()
