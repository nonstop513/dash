#!/usr/bin/env python3
"""
確認 58% vs 22% 的根本原因
"""
import duckdb, pandas as pd, os

BASE_DIR    = r"D:\IGame\db dash"
WIDE_PATH   = os.path.join(BASE_DIR, "101003_20251207_20260207(wide).duckdb")
COHORT_PATH = os.path.join(BASE_DIR, "101003_20260108_20260318.duckdb")

wide   = duckdb.connect(WIDE_PATH,   read_only=True)
cohort = duckdb.connect(COHORT_PATH, read_only=True)

DATE = "2026-01-08"

print(f"=== {DATE} 的各指標對比 ===\n")

# ── 1. 兩個 DB 同一天的 DAU ─────────────────────────────────────────
wide_dau = wide.execute(f"""
    SELECT COUNT(*) AS n FROM (
        SELECT PlayerID FROM MechanismStats
        WHERE GameID='101003' AND Mode='Normal'
          AND CAST(Date AS DATE) = DATE '{DATE}'
        GROUP BY PlayerID
    ) t
""").fetchone()[0]

cohort_dau = cohort.execute(f"""
    SELECT COUNT(*) AS n FROM (
        SELECT PlayerID FROM VariableX
        WHERE CAST(Date AS DATE) = DATE '{DATE}'
        GROUP BY PlayerID
    ) t
""").fetchone()[0]

print(f"  Wide DB (MechanismStats) DAU on {DATE}: {wide_dau:,}")
print(f"  Cohort DB (VariableX)    DAU on {DATE}: {cohort_dau:,}")
print(f"  比值 (VariableX / Wide):  {cohort_dau/wide_dau:.2f}x")
print()

# ── 2. Cohort Day-1 retention（所有當天活躍玩家的次日留存）─────────────
cohort_d1 = cohort.execute(f"""
    WITH d0 AS (
        SELECT PlayerID FROM VariableX
        WHERE CAST(Date AS DATE) = DATE '{DATE}'
        GROUP BY PlayerID
    ),
    d1 AS (
        SELECT PlayerID FROM VariableX
        WHERE CAST(Date AS DATE) = DATE '{DATE}' + 1
        GROUP BY PlayerID
    )
    SELECT COUNT(d1.PlayerID) AS returned
    FROM d0 LEFT JOIN d1 USING (PlayerID)
""").fetchone()[0]

print(f"  Cohort: {cohort_dau:,} 個當天活躍玩家 → {cohort_d1:,} 人隔日回來")
print(f"  Cohort Day-1 留存率: {cohort_d1/cohort_dau*100:.1f}%  ← 用全體活躍玩家")
print()

# ── 3. Wide DB 同一天 ALL 活躍玩家的次日留存（非 FDR 定義，是直接的 DAU）
wide_d1 = wide.execute(f"""
    WITH d0 AS (
        SELECT PlayerID FROM MechanismStats
        WHERE GameID='101003' AND Mode='Normal'
          AND CAST(Date AS DATE) = DATE '{DATE}'
        GROUP BY PlayerID
    ),
    d1 AS (
        SELECT PlayerID FROM MechanismStats
        WHERE GameID='101003' AND Mode='Normal'
          AND CAST(Date AS DATE) = DATE '{DATE}' + 1
        GROUP BY PlayerID
    )
    SELECT COUNT(d1.PlayerID) AS returned
    FROM d0 LEFT JOIN d1 USING (PlayerID)
""").fetchone()[0]

print(f"  Wide: {wide_dau:,} 個當天活躍玩家 → {wide_d1:,} 人隔日回來")
print(f"  Wide Day-1 留存率: {wide_d1/wide_dau*100:.1f}%  ← 也用全體活躍（Wide 版）")
print()

# ── 4. FDR 在同一天的留存（「7天沒來」子集）─────────────────────────
wide_fdr_d0 = wide.execute(f"""
    WITH base AS (
        SELECT PlayerID, CAST(Date AS DATE) AS play_date
        FROM MechanismStats WHERE GameID='101003' AND Mode='Normal'
        GROUP BY PlayerID, CAST(Date AS DATE)
    ),
    with_prev AS (
        SELECT *, LAG(play_date) OVER (PARTITION BY PlayerID ORDER BY play_date) AS prev_date
        FROM base
    )
    SELECT COUNT(*) AS n
    FROM with_prev
    WHERE play_date = DATE '{DATE}'
      AND (prev_date IS NULL OR (play_date - prev_date) > 6)
""").fetchone()[0]

wide_fdr_d1 = wide.execute(f"""
    WITH base AS (
        SELECT PlayerID, CAST(Date AS DATE) AS play_date
        FROM MechanismStats WHERE GameID='101003' AND Mode='Normal'
        GROUP BY PlayerID, CAST(Date AS DATE)
    ),
    with_prev AS (
        SELECT *, LAG(play_date) OVER (PARTITION BY PlayerID ORDER BY play_date) AS prev_date
        FROM base
    ),
    fdr AS (
        SELECT PlayerID, play_date FROM with_prev
        WHERE play_date = DATE '{DATE}'
          AND (prev_date IS NULL OR (play_date - prev_date) > 6)
    )
    SELECT COUNT(*) AS returned
    FROM fdr f
    WHERE EXISTS (
        SELECT 1 FROM base b WHERE b.PlayerID=f.PlayerID AND b.play_date = f.play_date + 1
    )
""").fetchone()[0]

print(f"  FDR（7天未登入的子集）on {DATE}: {wide_fdr_d0:,} 人")
print(f"  其中隔日回來: {wide_fdr_d1:,} 人")
print(f"  FDR D+1 留存率: {wide_fdr_d1/wide_fdr_d0*100:.1f}%")
print()

# ── 5. 結論計算 ──────────────────────────────────────────────────────
print("=== 解構 ===")
print(f"  Wide 全體: {wide_dau:,} 人，其中 FDR（7天未來）: {wide_fdr_d0:,} 人")
print(f"  FDR 佔比: {wide_fdr_d0/wide_dau*100:.1f}%")
non_fdr = wide_dau - wide_fdr_d0
non_fdr_ret = wide_d1 - wide_fdr_d1
print(f"  非 FDR（昨天就有來）: {non_fdr:,} 人，隔日回來: {non_fdr_ret:,}，留存率: {non_fdr_ret/non_fdr*100:.1f}%")
print()
print(f"  Cohort 活躍玩家比 Wide 多: {cohort_dau-wide_dau:,} 人（{(cohort_dau-wide_dau)/cohort_dau*100:.1f}%）")
print(f"  → 這些是登入但「沒有 spin」的玩家，幾乎全部不會隔日回來")

wide.close()
cohort.close()
