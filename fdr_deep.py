#!/usr/bin/env python3
"""
為什麼 Cohort Day-1 留存 ~20-30%，而 FDR D+1 留存卻有 58%？
---------------------------------------------------------------
假設：FDR 的 "first_in_window" 混入了大量回歸玩家（gap > 6 天但不是第一次登入），
      回歸玩家的次日留存遠高於真正的新玩家，拉高了整體數字。
"""

import duckdb
import pandas as pd
import os

BASE_DIR = r"D:\IGame\db dash"
GAME_ID  = "101003"
DB_PATH  = os.path.join(BASE_DIR, "101003_20251207_20260207(wide).duckdb")

duck = duckdb.connect(DB_PATH, read_only=True)

print("查詢中（約 2~3 秒）…\n")

df = duck.execute("""
    WITH base AS (
        SELECT
            PlayerID,
            CAST(Date AS DATE)      AS play_date,
            SUM(daily_spin_cnt)     AS daily_spin_cnt,
            AVG(daily_rtp)          AS daily_rtp
        FROM MechanismStats
        WHERE GameID = ? AND Mode = 'Normal'
        GROUP BY PlayerID, CAST(Date AS DATE)
    ),
    -- 每位玩家的第一次登入日
    first_ever AS (
        SELECT PlayerID, MIN(play_date) AS first_ever_date
        FROM base
        GROUP BY PlayerID
    ),
    -- 前一筆紀錄（用 LAG 找 gap）
    with_prev AS (
        SELECT b.*,
               LAG(play_date) OVER (PARTITION BY PlayerID ORDER BY play_date) AS prev_date
        FROM base b
    ),
    -- first_in_window：過去 6 天沒登入
    fiw AS (
        SELECT wp.*
        FROM with_prev wp
        WHERE prev_date IS NULL OR (play_date - prev_date) > 6
    )
    SELECT
        fiw.PlayerID,
        fiw.play_date,
        fiw.daily_spin_cnt,
        fiw.daily_rtp,
        -- 新玩家 or 回歸玩家
        CASE WHEN fe.first_ever_date = fiw.play_date THEN 'new' ELSE 'returning' END AS player_type,
        -- gap 天數（new 沒有前次 → NULL）
        (fiw.play_date - fiw.prev_date) AS gap_days,
        -- 隔日是否回來
        CASE WHEN EXISTS (
            SELECT 1 FROM base b2
            WHERE b2.PlayerID = fiw.PlayerID
              AND b2.play_date = fiw.play_date + 1
        ) THEN 1 ELSE 0 END AS returned_next_day
    FROM fiw
    JOIN first_ever fe ON fe.PlayerID = fiw.PlayerID
""", [GAME_ID]).fetchdf()

duck.close()

total = len(df)
print(f"符合條件總筆數: {total:,}")
print()

# ── 新玩家 vs 回歸玩家 組成比例 ─────────────────────────────────────
comp = df["player_type"].value_counts()
print("=== 組成 ===")
for ptype, cnt in comp.items():
    print(f"  {ptype:10s}: {cnt:>8,}  ({cnt/total*100:.1f}%)")
print()

# ── 各類型的 D+1 留存率 ──────────────────────────────────────────────
print("=== D+1 留存率（核心問題）===")
ret_by_type = (
    df.groupby("player_type")["returned_next_day"]
      .agg(["count", "sum", "mean"])
      .rename(columns={"count": "total", "sum": "retained", "mean": "retention_rate"})
)
ret_by_type["retention_rate"] = (ret_by_type["retention_rate"] * 100).round(2)
print(ret_by_type.to_string())
print()

# ── 回歸玩家：gap 分布 ───────────────────────────────────────────────
ret_df = df[df["player_type"] == "returning"].copy()
gap_bins   = [6, 13, 20, 30, 60, 9999]
gap_labels = ["7-13天", "14-20天", "21-30天", "31-60天", "60天+"]
ret_df["gap_seg"] = pd.cut(ret_df["gap_days"], bins=gap_bins, labels=gap_labels, right=True)

print("=== 回歸玩家：gap 天數 × D+1 留存率 ===")
gap_grp = (
    ret_df.groupby("gap_seg", observed=True)["returned_next_day"]
          .agg(["count", "sum", "mean"])
          .rename(columns={"count": "total", "sum": "retained", "mean": "retention_rate"})
)
gap_grp["retention_rate"] = (gap_grp["retention_rate"] * 100).round(2)
print(gap_grp.to_string())
print()

# ── 新玩家的 Cohort 模擬：以登入日為 cohort，看 Day+1 留存 ──────────
new_df = df[df["player_type"] == "new"].copy()
print("=== 新玩家（等同 Cohort Day-0）D+1 留存率 ===")
overall_new_ret = new_df["returned_next_day"].mean() * 100
print(f"  整體: {len(new_df):,} 人  留存率: {overall_new_ret:.1f}%")
print()

# 按登入日期看波動（模擬 Cohort 熱力圖第一行）
daily = (
    new_df.groupby("play_date")["returned_next_day"]
          .agg(["count", "mean"])
          .rename(columns={"count": "cohort_size", "mean": "day1_retention"})
)
daily["day1_retention"] = (daily["day1_retention"] * 100).round(1)
print("新玩家每日 cohort（節錄前 20 天）:")
print(daily.head(20).to_string())
print()
print(f"新玩家 Day-1 留存率範圍: {daily['day1_retention'].min():.1f}% ~ {daily['day1_retention'].max():.1f}%")
print(f"新玩家 Day-1 留存率中位: {daily['day1_retention'].median():.1f}%")
