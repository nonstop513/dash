#!/usr/bin/env python3
"""
第二輪：算各分段的留存率，並輸出儀表板所需的 JSON 格式摘要
"""
import duckdb, pandas as pd, os, json

BASE_DIR = r"D:\IGame\db dash"
GAME_ID  = "101003"
DB_PATH  = os.path.join(BASE_DIR, "101003_20251207_20260207(wide).duckdb")

SPIN_BINS   = [0, 100, 500, 2000, 10_000, 99_999_999]
SPIN_LABELS = ["1-100", "101-500", "501-2000", "2001-10000", "10000+"]
RTP_BINS    = [-0.001, 0.5, 0.8, 0.9, 0.95, 1.0, 1.1, 1.25, 9999]
RTP_LABELS  = ["<50%", "50-80%", "80-90%", "90-95%", "95-100%", "100-110%", "110-125%", ">125%"]

# ── 重用上次的 CSV 而非重跑 DuckDB（速度快）──────────────────────────────
spin_csv = os.path.join(BASE_DIR, "first_day_spin.csv")
rtp_csv  = os.path.join(BASE_DIR, "first_day_rtp.csv")

if os.path.exists(spin_csv) and os.path.exists(rtp_csv):
    spin_grp = pd.read_csv(spin_csv)
    rtp_grp  = pd.read_csv(rtp_csv)
    print("從 CSV 載入資料")
else:
    print("重新跑 DuckDB…")
    duck = duckdb.connect(DB_PATH, read_only=True)
    df = duck.execute("""
        WITH base AS (
            SELECT PlayerID, CAST(Date AS DATE) AS play_date,
                   SUM(daily_spin_cnt) AS daily_spin_cnt,
                   AVG(daily_rtp)      AS daily_rtp,
                   SUM(daily_total_bet) AS daily_total_bet
            FROM MechanismStats WHERE GameID = ? AND Mode = 'Normal'
            GROUP BY PlayerID, CAST(Date AS DATE)
        ),
        fiw AS (
            SELECT b1.*
            FROM base b1
            WHERE NOT EXISTS (
                SELECT 1 FROM base b2
                WHERE b2.PlayerID = b1.PlayerID
                  AND b2.play_date >= b1.play_date - INTERVAL '6 days'
                  AND b2.play_date <  b1.play_date
            )
        )
        SELECT fiw.*, CASE WHEN EXISTS (
            SELECT 1 FROM base b3
            WHERE b3.PlayerID = fiw.PlayerID
              AND b3.play_date = fiw.play_date + INTERVAL '1 day'
        ) THEN 1 ELSE 0 END AS returned_next_day FROM fiw
    """, [GAME_ID]).fetchdf()
    duck.close()
    df["group"]    = df["returned_next_day"].map({1: "留下(D+1)", 0: "未留下"})
    df["spin_seg"] = pd.cut(df["daily_spin_cnt"], bins=SPIN_BINS, labels=SPIN_LABELS, right=True)
    df["rtp_seg"]  = pd.cut(df["daily_rtp"],      bins=RTP_BINS,  labels=RTP_LABELS,  right=True)
    spin_grp = df.groupby(["spin_seg","group"], observed=True).agg(count=("PlayerID","count"), avg_rtp=("daily_rtp","mean")).reset_index()
    rtp_grp  = df.groupby(["rtp_seg", "group"], observed=True).agg(count=("PlayerID","count")).reset_index()
    spin_grp.to_csv(spin_csv, index=False, encoding="utf-8-sig")
    rtp_grp.to_csv(rtp_csv,  index=False, encoding="utf-8-sig")

# ── 轉數段留存率 ─────────────────────────────────────────────────────────────
spin_wide = spin_grp.pivot(index="spin_seg", columns="group", values="count").fillna(0)
spin_wide.columns.name = None
if "留下(D+1)" not in spin_wide: spin_wide["留下(D+1)"] = 0
if "未留下"    not in spin_wide: spin_wide["未留下"]    = 0
spin_wide["total"]        = spin_wide["留下(D+1)"] + spin_wide["未留下"]
spin_wide["retention_pct"]= (spin_wide["留下(D+1)"] / spin_wide["total"] * 100).round(1)

# RTP within each spin segment
spin_rtp = spin_grp.pivot(index="spin_seg", columns="group", values="avg_rtp")
spin_rtp.columns.name = None

print("=== 轉數段留存率 ===")
print(spin_wide[["未留下","留下(D+1)","total","retention_pct"]].to_string())
print()
print("各轉數段平均 RTP:")
print(spin_rtp.to_string())
print()

# ── RTP 段留存率 ──────────────────────────────────────────────────────────────
rtp_wide = rtp_grp.pivot(index="rtp_seg", columns="group", values="count").fillna(0)
rtp_wide.columns.name = None
if "留下(D+1)" not in rtp_wide: rtp_wide["留下(D+1)"] = 0
if "未留下"    not in rtp_wide: rtp_wide["未留下"]    = 0
rtp_wide["total"]        = rtp_wide["留下(D+1)"] + rtp_wide["未留下"]
rtp_wide["retention_pct"]= (rtp_wide["留下(D+1)"] / rtp_wide["total"] * 100).round(1)

print("=== RTP 段留存率 ===")
print(rtp_wide[["未留下","留下(D+1)","total","retention_pct"]].to_string())
print()

# ── 輸出 JSON 供儀表板使用 ────────────────────────────────────────────────────
result = {
    "spin_retention": [
        {
            "seg":          str(row.Index),
            "retained":     int(row._asdict().get("留下(D+1)", 0)),
            "not_retained": int(row._asdict().get("未留下", 0)),
            "total":        int(row.total),
            "retention_pct": float(row.retention_pct),
            "avg_rtp_ret":   round(float(spin_rtp.loc[row.Index, "留下(D+1)"]), 4) if "留下(D+1)" in spin_rtp.columns and row.Index in spin_rtp.index else None,
            "avg_rtp_not":   round(float(spin_rtp.loc[row.Index, "未留下"]),    4) if "未留下"    in spin_rtp.columns and row.Index in spin_rtp.index else None,
        }
        for row in spin_wide.itertuples()
        if row.total > 0
    ],
    "rtp_retention": [
        {
            "seg":           str(row.Index),
            "retained":      int(row._asdict().get("留下(D+1)", 0)),
            "not_retained":  int(row._asdict().get("未留下", 0)),
            "total":         int(row.total),
            "retention_pct": float(row.retention_pct),
        }
        for row in rtp_wide.itertuples()
        if row.total > 0
    ],
}

out_path = os.path.join(BASE_DIR, "first_day_summary.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(f"JSON 已輸出 → {out_path}")
