"""
Explore total play days × total spins distribution per player
to find meaningful segmentation cut points.
"""
import duckdb
import pandas as pd
import numpy as np

# Use wide DB for 101003 (complete daily_spin_cnt + daily_total_bet)
con = duckdb.connect("D:/IGame/db dash/101003_20251207_20260207(wide).duckdb", read_only=True)

df = con.execute("""
    SELECT
        PlayerID,
        COUNT(DISTINCT Date)        AS play_days,
        SUM(daily_spin_cnt)         AS total_spins,
        SUM(daily_total_bet)        AS total_bet
    FROM MechanismStats
    WHERE GameID = '101003' AND Mode = 'Normal'
    GROUP BY PlayerID
""").fetchdf()
con.close()

print(f"Total players: {len(df):,}")
print(f"Total bet in dataset: {df['total_bet'].sum():,.0f}\n")

print("=== play_days distribution ===")
print(df['play_days'].describe(percentiles=[.1,.25,.5,.75,.9,.95,.99]))
print()
print("Value counts (top 15):")
print(df['play_days'].value_counts().sort_index().head(15))
print()

print("=== total_spins distribution ===")
print(df['total_spins'].describe(percentiles=[.1,.25,.5,.75,.9,.95,.99]))
print()

# Percentile cut points for spins
for p in [25, 50, 75, 90, 95, 99]:
    print(f"  P{p:2d}: {df['total_spins'].quantile(p/100):>12,.0f} spins")
