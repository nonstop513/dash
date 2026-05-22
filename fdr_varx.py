#!/usr/bin/env python3
"""
首日留存分析 v2 — 使用 VariableX.LoginCount_D7
-------------------------------------------------
條件: LoginCount_D7 = 1（過去 7 天只有這天登入）
隔日回來: 直接看資料集內隔天是否出現（不依賴 Stay 欄位）
邊界處理: 資料最後一天沒有「隔天」，排除在留存率計算之外
對比: 也順便驗證 Stay 欄位的準確度
"""

import duckdb
import pandas as pd
import os

BASE_DIR    = r"D:\IGame\db dash"
COHORT_PATH = os.path.join(BASE_DIR, "101003_20260108_20260318.duckdb")

SPIN_BINS   = [0, 100, 500, 2000, 10_000, 99_999_999]
SPIN_LABELS = ["1-100", "101-500", "501-2000", "2001-10000", "10000+"]
RTP_BINS    = [-0.001, 0.5, 0.8, 0.9, 0.95, 1.0, 1.1, 1.25, 9999]
RTP_LABELS  = ["<50%", "50-80%", "80-90%", "90-95%", "95-100%", "100-110%", "110-125%", ">125%"]

duck = duckdb.connect(COHORT_PATH, read_only=True)

# 資料集的最後一天（最後一天沒有「隔天」，不算在留存分母）
max_date = duck.execute("SELECT MAX(CAST(Date AS DATE)) FROM VariableX").fetchone()[0]
print(f"資料集最後一天: {max_date}（此日不計入分母）\n")

print("建立分析資料集（LoginCount_D7=1）…")
df = duck.execute("""
    WITH d7_players AS (
        -- LoginCount_D7=1：過去7天只有這天登入
        SELECT
            PlayerID,
            CAST(Date AS DATE)  AS play_date,
            SpinCount,
            RTP,
            WinRatio,
            AvgBet,
            Stay                -- 備用對比欄位
        FROM VariableX
        WHERE LoginCount_D7 = 1
    ),
    max_date AS (
        SELECT MAX(CAST(Date AS DATE)) AS d FROM VariableX
    )
    SELECT
        d7.*,
        -- 實際計算隔日是否出現（排除最後一天）
        CASE
            WHEN d7.play_date = (SELECT d FROM max_date) THEN NULL  -- 最後一天不知道
            WHEN EXISTS (
                SELECT 1 FROM VariableX v2
                WHERE v2.PlayerID = d7.PlayerID
                  AND CAST(v2.Date AS DATE) = d7.play_date + 1
            ) THEN 1
            ELSE 0
        END AS returned_next_day
    FROM d7_players d7
""").fetchdf()

duck.close()

# 分出「可計算」和「邊界日」
computable = df[df["returned_next_day"].notna()].copy()
boundary   = df[df["returned_next_day"].isna()]

total_all  = len(df)
total_comp = len(computable)
ret        = int(computable["returned_next_day"].sum())
not_ret    = total_comp - ret

print(f"LoginCount_D7=1 總筆數:    {total_all:,}")
print(f"  可計算（非最後一天）:     {total_comp:,}")
print(f"  最後一天（邊界，排除）:   {len(boundary):,}")
print(f"\n隔日有回來: {ret:,}  ({ret/total_comp*100:.1f}%)")
print(f"隔日沒回來: {not_ret:,}  ({not_ret/total_comp*100:.1f}%)\n")

# ── Stay 準確度驗證 ─────────────────────────────────────────────────
print("=== Stay 欄位準確度（vs 實際計算）===")
stay_check = (
    computable.groupby(["Stay", "returned_next_day"])
              .size()
              .reset_index(name="n")
)
stay_total = stay_check.groupby("Stay")["n"].transform("sum")
stay_check["pct"] = (stay_check["n"] / stay_total * 100).round(1)
print(stay_check.to_string())
print()

# ── 基本指標 ───────────────────────────────────────────────────────
computable["group"] = computable["returned_next_day"].map({1: "留下(D+1)", 0: "未留下"})

summary = (
    computable.groupby("group")
              .agg(
                  count      = ("PlayerID",  "count"),
                  avg_spin   = ("SpinCount", "mean"),
                  med_spin   = ("SpinCount", "median"),
                  avg_rtp    = ("RTP",       "mean"),
                  med_rtp    = ("RTP",       "median"),
                  avg_bet    = ("AvgBet",    "mean"),
              )
              .round(4)
)
print("=== 平均指標比較 ===")
print(summary.to_string())
print()

# ── 轉數分群留存率 ──────────────────────────────────────────────────
computable["spin_seg"] = pd.cut(
    computable["SpinCount"], bins=SPIN_BINS, labels=SPIN_LABELS, right=True
)
spin_wide = (
    computable.groupby(["spin_seg", "returned_next_day"], observed=True)
              .agg(count=("SpinCount","count"), avg_rtp=("RTP","mean"))
              .reset_index()
              .pivot(index="spin_seg", columns="returned_next_day", values=["count","avg_rtp"])
)
spin_wide.columns = ["_".join(str(c) for c in col) for col in spin_wide.columns]
spin_wide = spin_wide.fillna(0)
spin_wide["total"]         = spin_wide.get("count_0", 0) + spin_wide.get("count_1", 0)
spin_wide["retention_pct"] = (spin_wide.get("count_1", 0) / spin_wide["total"] * 100).round(1)

print("=== 轉數分群留存率 ===")
print(spin_wide[["count_0","count_1","total","retention_pct",
                  "avg_rtp_0","avg_rtp_1"]].rename(
    columns={"count_0":"未留下","count_1":"留下","avg_rtp_0":"avg_rtp_未留","avg_rtp_1":"avg_rtp_留"}
).to_string())
print()

# ── RTP 分布留存率 ──────────────────────────────────────────────────
computable["rtp_seg"] = pd.cut(
    computable["RTP"], bins=RTP_BINS, labels=RTP_LABELS, right=True
)
rtp_wide = (
    computable.groupby(["rtp_seg", "returned_next_day"], observed=True)
              .agg(count=("SpinCount","count"))
              .reset_index()
              .pivot(index="rtp_seg", columns="returned_next_day", values="count")
              .fillna(0)
)
rtp_wide["total"]         = rtp_wide.get(0, 0) + rtp_wide.get(1, 0)
rtp_wide["retention_pct"] = (rtp_wide.get(1, 0) / rtp_wide["total"] * 100).round(1)

print("=== RTP 分布留存率 ===")
print(rtp_wide.rename(columns={0:"未留下",1:"留下"}).to_string())
print()

# ── 輸出 CSV 供儀表板使用 ─────────────────────────────────────────
spin_out = []
for order, label in enumerate(SPIN_LABELS):
    if label not in spin_wide.index: continue
    row = spin_wide.loc[label]
    spin_out.append({
        "seg_label":     label,
        "seg_order":     order,
        "retained":      int(row.get("count_1", 0)),
        "not_retained":  int(row.get("count_0", 0)),
        "total":         int(row["total"]),
        "retention_pct": float(row["retention_pct"]),
        "avg_rtp_ret":   round(float(row.get("avg_rtp_1", 0)), 4),
        "avg_rtp_not":   round(float(row.get("avg_rtp_0", 0)), 4),
    })

rtp_out = []
for order, label in enumerate(RTP_LABELS):
    if label not in rtp_wide.index: continue
    row = rtp_wide.loc[label]
    rtp_out.append({
        "seg_label":     label,
        "seg_order":     order,
        "retained":      int(row.get(1, 0)),
        "not_retained":  int(row.get(0, 0)),
        "total":         int(row["total"]),
        "retention_pct": float(row["retention_pct"]),
    })

overview = {
    "total_records":  total_comp,
    "retained":       ret,
    "not_retained":   not_ret,
    "retention_pct":  round(ret / total_comp * 100, 2),
    "avg_spin_ret":   round(float(computable[computable["returned_next_day"]==1]["SpinCount"].mean()), 2),
    "avg_spin_not":   round(float(computable[computable["returned_next_day"]==0]["SpinCount"].mean()), 2),
    "med_spin_ret":   round(float(computable[computable["returned_next_day"]==1]["SpinCount"].median()), 2),
    "med_spin_not":   round(float(computable[computable["returned_next_day"]==0]["SpinCount"].median()), 2),
    "avg_rtp_ret":    round(float(computable[computable["returned_next_day"]==1]["RTP"].mean()), 4),
    "avg_rtp_not":    round(float(computable[computable["returned_next_day"]==0]["RTP"].mean()), 4),
}
print(f"Overview: {overview}")

import json
out = {"overview": overview, "spin_segments": spin_out, "rtp_segments": rtp_out}
with open(os.path.join(BASE_DIR, "fdr_varx_summary.json"), "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print("\n已輸出 fdr_varx_summary.json")
