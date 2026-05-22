#!/usr/bin/env python3
"""
First-Day-in-7-Window Retention Analysis
-----------------------------------------
找出「過去7天內只有這一天登入」的玩家-日期紀錄，
分成「隔日回來 (D+1)」和「沒回來」兩群，
比較當日 RTP 與轉數分布。
"""

import duckdb
import pandas as pd
import os

BASE_DIR   = r"D:\IGame\db dash"
GAME_ID    = "101003"
DB_PATH    = os.path.join(BASE_DIR, "101003_20251207_20260207(wide).duckdb")

SPIN_BINS   = [0, 100, 500, 2000, 10_000, 99_999_999]
SPIN_LABELS = ["1-100", "101-500", "501-2000", "2001-10000", "10000+"]

# RTP 段位（>1 表示當日贏錢）
RTP_BINS   = [-0.001, 0.5, 0.8, 0.9, 0.95, 1.0, 1.1, 1.25, 9999]
RTP_LABELS = ["<50%", "50-80%", "80-90%", "90-95%", "95-100%", "100-110%", "110-125%", ">125%"]

# ---------------------------------------------------------------------------
duck = duckdb.connect(DB_PATH, read_only=True)

print("Building first-day-in-7-window dataset …")
df = duck.execute("""
    WITH base AS (
        -- 每個 (PlayerID, date) 的當日指標，Normal mode only
        SELECT
            PlayerID,
            CAST(Date AS DATE)     AS play_date,
            SUM(daily_spin_cnt)    AS daily_spin_cnt,
            AVG(daily_rtp)         AS daily_rtp,
            SUM(daily_total_bet)   AS daily_total_bet
        FROM MechanismStats
        WHERE GameID = ? AND Mode = 'Normal'
        GROUP BY PlayerID, CAST(Date AS DATE)
    ),
    first_in_window AS (
        -- 保留「在 play_date 之前 6 天內無任何出現」的紀錄
        SELECT b1.*
        FROM base b1
        WHERE NOT EXISTS (
            SELECT 1 FROM base b2
            WHERE b2.PlayerID  = b1.PlayerID
              AND b2.play_date >= b1.play_date - INTERVAL '6 days'
              AND b2.play_date <  b1.play_date
        )
    )
    SELECT
        fiw.PlayerID,
        fiw.play_date,
        fiw.daily_spin_cnt,
        fiw.daily_rtp,
        fiw.daily_total_bet,
        CASE WHEN EXISTS (
            SELECT 1 FROM base b3
            WHERE b3.PlayerID = fiw.PlayerID
              AND b3.play_date = fiw.play_date + INTERVAL '1 day'
        ) THEN 1 ELSE 0 END AS returned_next_day
    FROM first_in_window fiw
""", [GAME_ID]).fetchdf()

duck.close()

# ---------------------------------------------------------------------------
# 基本統計
# ---------------------------------------------------------------------------
total = len(df)
ret   = df["returned_next_day"].sum()
print(f"\n遊戲: {GAME_ID}")
print(f"符合條件總筆數: {total:,}")
print(f"  隔日有回來: {ret:,}  ({ret/total*100:.1f}%)")
print(f"  隔日沒回來: {total-ret:,}  ({(total-ret)/total*100:.1f}%)\n")

df["group"] = df["returned_next_day"].map({1: "留下(D+1)", 0: "未留下"})

# ---------------------------------------------------------------------------
# 平均指標比較
# ---------------------------------------------------------------------------
summary = (
    df.groupby("group")
      .agg(
          player_days   = ("PlayerID",       "count"),
          unique_players= ("PlayerID",       "nunique"),
          avg_spin      = ("daily_spin_cnt", "mean"),
          med_spin      = ("daily_spin_cnt", "median"),
          avg_rtp       = ("daily_rtp",      "mean"),
          med_rtp       = ("daily_rtp",      "median"),
          total_bet     = ("daily_total_bet","sum"),
      )
      .round(4)
)
print("=== 平均指標 ===")
print(summary.to_string())
print()

# ---------------------------------------------------------------------------
# 轉數分群
# ---------------------------------------------------------------------------
df["spin_seg"] = pd.cut(df["daily_spin_cnt"], bins=SPIN_BINS, labels=SPIN_LABELS, right=True)

spin_grp = (
    df.groupby(["spin_seg", "group"], observed=True)
      .agg(count=("PlayerID", "count"), avg_rtp=("daily_rtp", "mean"))
      .reset_index()
)

# 每個 spin_seg 加上各群百分比
totals = spin_grp.groupby("spin_seg", observed=True)["count"].transform("sum")
spin_grp["pct_within_seg"] = (spin_grp["count"] / totals * 100).round(1)

# 每個 group 加上在該群內佔比
group_totals = spin_grp.groupby("group", observed=True)["count"].transform("sum")
spin_grp["pct_within_group"] = (spin_grp["count"] / group_totals * 100).round(1)

print("=== 轉數分群 ×  留存 ===")
pivot_count = spin_grp.pivot(index="spin_seg", columns="group", values="count").fillna(0).astype(int)
pivot_pct   = spin_grp.pivot(index="spin_seg", columns="group", values="pct_within_group").round(1)
pivot_rtp   = spin_grp.pivot(index="spin_seg", columns="group", values="avg_rtp").round(4)

print("人次數:")
print(pivot_count.to_string())
print("\n各群組內佔比 (%):")
print(pivot_pct.to_string())
print("\n各段位平均 RTP:")
print(pivot_rtp.to_string())
print()

# ---------------------------------------------------------------------------
# RTP 分布
# ---------------------------------------------------------------------------
df["rtp_seg"] = pd.cut(df["daily_rtp"], bins=RTP_BINS, labels=RTP_LABELS, right=True)

rtp_grp = (
    df.groupby(["rtp_seg", "group"], observed=True)
      .agg(count=("PlayerID", "count"))
      .reset_index()
)
group_totals2 = rtp_grp.groupby("group", observed=True)["count"].transform("sum")
rtp_grp["pct"] = (rtp_grp["count"] / group_totals2 * 100).round(1)

print("=== RTP 分布 ===")
pivot_rtp_dist = rtp_grp.pivot(index="rtp_seg", columns="group", values="count").fillna(0).astype(int)
pivot_rtp_pct  = rtp_grp.pivot(index="rtp_seg", columns="group", values="pct").round(1)
print("人次數:")
print(pivot_rtp_dist.to_string())
print("\n各群組內佔比 (%):")
print(pivot_rtp_pct.to_string())
print()

# ---------------------------------------------------------------------------
# 輸出 CSV 供後續使用
# ---------------------------------------------------------------------------
spin_grp.to_csv(os.path.join(BASE_DIR, "first_day_spin.csv"), index=False, encoding="utf-8-sig")
rtp_grp.to_csv(os.path.join(BASE_DIR, "first_day_rtp.csv"),  index=False, encoding="utf-8-sig")
print("已輸出 first_day_spin.csv / first_day_rtp.csv")
