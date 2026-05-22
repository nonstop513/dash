#!/usr/bin/env python3
"""
直接比較：Wide DB 的「新玩家 Day-1 留存」vs Cohort DB 的「正統 Cohort Day-1 留存」
兩個 DB 有重疊期間（2026-01-08 ~ 2026-02-07），用這段做蘋果對蘋果比較。

假設：Wide DB 只記錄「有 spin 的 session」，而 CohortBase 記錄所有登入。
驗證方式：比較同一天 new-player 數量差異。
"""

import duckdb
import pandas as pd
import os

BASE_DIR    = r"D:\IGame\db dash"
GAME_ID     = "101003"
WIDE_PATH   = os.path.join(BASE_DIR, "101003_20251207_20260207(wide).duckdb")
COHORT_PATH = os.path.join(BASE_DIR, "101003_20260108_20260318.duckdb")

OVERLAP_START = "2026-01-08"
OVERLAP_END   = "2026-02-07"

# ── Wide DB：overlap 期間的「資料集首次出現」玩家 ──────────────────
print("=== Wide DB：overlap 期間的 '新玩家'（首次出現於資料集）===")
wide = duckdb.connect(WIDE_PATH, read_only=True)

wide_new = wide.execute("""
    WITH base AS (
        SELECT PlayerID, CAST(Date AS DATE) AS play_date
        FROM MechanismStats
        WHERE GameID = ? AND Mode = 'Normal'
        GROUP BY PlayerID, CAST(Date AS DATE)
    ),
    first_ever AS (
        SELECT PlayerID, MIN(play_date) AS first_date
        FROM base GROUP BY PlayerID
    )
    SELECT
        fe.first_date AS cohort_day,
        COUNT(DISTINCT fe.PlayerID) AS wide_new_players,
        SUM(CASE WHEN EXISTS (
            SELECT 1 FROM base b2
            WHERE b2.PlayerID = fe.PlayerID
              AND b2.play_date = fe.first_date + 1
        ) THEN 1 ELSE 0 END) AS wide_returned_day1
    FROM first_ever fe
    WHERE fe.first_date BETWEEN ? AND ?
    GROUP BY fe.first_date
    ORDER BY fe.first_date
""", [GAME_ID, OVERLAP_START, OVERLAP_END]).fetchdf()

wide.close()

wide_new["wide_day1_ret"] = (wide_new["wide_returned_day1"] / wide_new["wide_new_players"] * 100).round(1)
print(wide_new.to_string())
print(f"\nWide DB overlap: avg Day-1 retention = {wide_new['wide_day1_ret'].mean():.1f}%")
print(f"  total 'new' players = {wide_new['wide_new_players'].sum():,}")
print()

# ── Cohort DB：同期間 CohortBase 的 Day-1 留存 ────────────────────
print("=== Cohort DB：CohortBase Day-1 留存（正統 Cohort）===")
cohort = duckdb.connect(COHORT_PATH, read_only=True)

# CohortBase 欄位探索
tables = cohort.execute("SHOW TABLES").fetchdf()
print("Tables:", tables["name"].tolist())

# 看 CohortBase 樣本
sample = cohort.execute("SELECT * FROM CohortBase LIMIT 5").fetchdf()
print("CohortBase columns:", sample.columns.tolist())
print(sample.to_string())
print()

cohort_ret = cohort.execute("""
    WITH day0 AS (
        SELECT CohortDay, COUNT(DISTINCT PlayerID) AS day0_count
        FROM CohortBase WHERE DayIndex = 0
        GROUP BY CohortDay
    ),
    day1 AS (
        SELECT CohortDay, COUNT(DISTINCT PlayerID) AS day1_count
        FROM CohortBase WHERE DayIndex = 1
        GROUP BY CohortDay
    )
    SELECT
        CAST(d0.CohortDay AS DATE) AS cohort_day,
        d0.day0_count AS cohort_new_players,
        COALESCE(d1.day1_count, 0) AS cohort_returned_day1,
        ROUND(COALESCE(d1.day1_count, 0) * 100.0 / d0.day0_count, 1) AS cohort_day1_ret
    FROM day0 d0
    LEFT JOIN day1 d1 ON d0.CohortDay = d1.CohortDay
    WHERE CAST(d0.CohortDay AS DATE) BETWEEN ? AND ?
    ORDER BY d0.CohortDay
""", [OVERLAP_START, OVERLAP_END]).fetchdf()

cohort.close()

print(cohort_ret.to_string())
print(f"\nCohort DB overlap: avg Day-1 retention = {cohort_ret['cohort_day1_ret'].mean():.1f}%")
print(f"  total cohort new players = {cohort_ret['cohort_new_players'].sum():,}")
print()

# ── 直接比較：同一天兩邊的人數差異 ────────────────────────────────
print("=== 同期間：Wide DB vs Cohort DB 新玩家數量比較 ===")
wide_new["cohort_day"] = wide_new["cohort_day"].astype(str)
cohort_ret["cohort_day"] = cohort_ret["cohort_day"].astype(str)

merged = pd.merge(
    wide_new[["cohort_day", "wide_new_players", "wide_day1_ret"]],
    cohort_ret[["cohort_day", "cohort_new_players", "cohort_day1_ret"]],
    on="cohort_day", how="outer"
).fillna(0)

merged["ratio"] = (merged["cohort_new_players"] / merged["wide_new_players"]).round(2)
print(merged.to_string())
print()
print("cohort_new / wide_new 比值（應遠大於 1，表示 cohort 包含大量 0-spin 玩家）:")
print(f"  平均比值: {merged['ratio'].mean():.2f}x")
print(f"  Wide avg Day-1 ret:   {merged['wide_day1_ret'].mean():.1f}%")
print(f"  Cohort avg Day-1 ret: {merged['cohort_day1_ret'].mean():.1f}%")
