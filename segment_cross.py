"""
Cross-segmentation: play_days × total_spins
Shows player count and bet contribution % per cell.
"""
import duckdb
import pandas as pd
import numpy as np

con = duckdb.connect("D:/IGame/db dash/101003_20251207_20260207(wide).duckdb", read_only=True)

df = con.execute("""
    SELECT
        PlayerID,
        COUNT(DISTINCT Date)  AS play_days,
        SUM(daily_spin_cnt)   AS total_spins,
        SUM(daily_total_bet)  AS total_bet
    FROM MechanismStats
    WHERE GameID = '101003' AND Mode = 'Normal'
    GROUP BY PlayerID
""").fetchdf()
con.close()

total_bet = df["total_bet"].sum()
total_players = len(df)

# --- Bin definitions ---
day_bins   = [0, 1, 3, 7, 14, 999]
day_labels = ["1天", "2-3天", "4-7天", "8-14天", "15天+"]
spin_bins  = [0, 100, 500, 2000, 10000, 9_999_999]
spin_labels = ["1-100", "101-500", "501-2000", "2001-10000", "10000+"]

df["day_seg"]  = pd.cut(df["play_days"],  bins=day_bins,  labels=day_labels,  right=True)
df["spin_seg"] = pd.cut(df["total_spins"], bins=spin_bins, labels=spin_labels, right=True)

# --- Cross table: player count ---
ct_players = pd.crosstab(df["day_seg"], df["spin_seg"], margins=True)
ct_players.index.name = "遊玩天數 \\ Spin數"

# --- Cross table: total bet ---
ct_bet = df.groupby(["day_seg", "spin_seg"], observed=True)["total_bet"].sum().unstack(fill_value=0)
ct_bet["Total"] = ct_bet.sum(axis=1)
ct_bet.loc["Total"] = ct_bet.sum()

# --- Bet contribution % of total ---
ct_bet_pct = (ct_bet / total_bet * 100).round(2)

# --- Player % of total ---
ct_player_pct = (ct_players / total_players * 100).round(2)

print("=== Player count per cell ===")
print(ct_players.to_string())
print()
print("=== Player % of total ===")
print(ct_player_pct.to_string())
print()
print("=== Bet contribution % of total ===")
print(ct_bet_pct.to_string())
print()
print("=== Avg bet per player per cell ===")
ct_avg = (ct_bet.drop(columns="Total", errors="ignore").drop(index="Total", errors="ignore") /
          ct_players.drop(columns="All", errors="ignore").drop(index="All", errors="ignore")
          .replace(0, np.nan)).round(0)
print(ct_avg.to_string())
print()

# Key insight summary
print("=== Key insights ===")
for ds in day_labels:
    for ss in spin_labels:
        try:
            players = ct_players.loc[ds, ss]
            bet_pct = ct_bet_pct.loc[ds, ss]
            p_pct   = ct_player_pct.loc[ds, ss]
            if bet_pct > 1:
                print(f"  [{ds} × {ss}]  {players:>7,} 人 ({p_pct:.1f}%)  →  貢獻 {bet_pct:.1f}% 押注")
        except Exception:
            pass
