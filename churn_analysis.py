import duckdb
import pandas as pd
import numpy as np

con = duckdb.connect('D:/IGame/db dash/101003_20260108_20260318.duckdb', read_only=True)

# Max date
max_date = con.execute('SELECT MAX(Date) FROM VariableX').fetchone()[0]
churn_cutoff = pd.Timestamp(max_date) - pd.Timedelta(days=7)
print(f"Data max date  : {max_date}")
print(f"Churn cutoff   : {churn_cutoff.date()}  (last_date < this = churned)")

# --- 1. Classify players ---
player_last = con.execute('''
    SELECT PlayerID, MAX(Date) as last_date, COUNT(DISTINCT Date) as total_days
    FROM VariableX GROUP BY PlayerID
''').fetchdf()

player_last['is_churned'] = player_last['last_date'] < churn_cutoff
n_churned = player_last['is_churned'].sum()
n_active  = (~player_last['is_churned']).sum()
print(f"\nChurned (>7d absent) : {n_churned:,}")
print(f"Active               : {n_active:,}")
print(f"Churn rate           : {n_churned/(n_churned+n_active)*100:.1f}%")

# --- 2. Last-day data for churned players ---
last_day = con.execute(f'''
    SELECT vx.PlayerID,
           vx.FirstBeforeBalance,
           vx.LastAfterBalance,
           vx.WinRatio,
           vx.SpinCount,
           vx.AvgBet,
           vx.RTP,
           vx.FreeGameCount,
           vx.BonusGameCount
    FROM VariableX vx
    JOIN (
        SELECT PlayerID, MAX(Date) as last_date
        FROM VariableX
        WHERE Date < '{churn_cutoff.date()}'
        GROUP BY PlayerID
    ) t ON vx.PlayerID = t.PlayerID AND vx.Date = t.last_date
''').fetchdf()

print(f"\n=== Churned players last-day balance (n={len(last_day):,}) ===")
print(f"Entry balance  median : {last_day['FirstBeforeBalance'].median():.1f}")
print(f"Entry balance  mean   : {last_day['FirstBeforeBalance'].mean():.1f}")
print(f"Exit  balance  median : {last_day['LastAfterBalance'].median():.1f}")
print(f"Exit  balance  mean   : {last_day['LastAfterBalance'].mean():.1f}")

print(f"\n=== WinRatio distribution on last day ===")
print(f"  < 0.1   lost 90%+   : {(last_day['WinRatio'] <  0.1).mean()*100:.1f}%")
print(f"  0.1~0.5 lost 50-90% : {((last_day['WinRatio'] >= 0.1) & (last_day['WinRatio'] < 0.5)).mean()*100:.1f}%")
print(f"  0.5~1.0 small loss  : {((last_day['WinRatio'] >= 0.5) & (last_day['WinRatio'] < 1.0)).mean()*100:.1f}%")
print(f"  >= 1.0  even/profit : {(last_day['WinRatio'] >= 1.0).mean()*100:.1f}%")

print(f"\n=== 'Busted' check ===")
print(f"  LastAfterBalance == 0 : {(last_day['LastAfterBalance'] == 0).mean()*100:.1f}%")
print(f"  LastAfterBalance <  1 : {(last_day['LastAfterBalance'] <  1).mean()*100:.1f}%")
print(f"  LastAfterBalance < 10 : {(last_day['LastAfterBalance'] < 10).mean()*100:.1f}%")

# --- 3. Compare with active players last-day ---
active_last = con.execute(f'''
    SELECT vx.PlayerID,
           vx.FirstBeforeBalance,
           vx.LastAfterBalance,
           vx.WinRatio,
           vx.RTP
    FROM VariableX vx
    JOIN (
        SELECT PlayerID, MAX(Date) as last_date
        FROM VariableX
        WHERE Date >= '{churn_cutoff.date()}'
        GROUP BY PlayerID
    ) t ON vx.PlayerID = t.PlayerID AND vx.Date = t.last_date
''').fetchdf()

print(f"\n=== Active players last-day balance (n={len(active_last):,}) ===")
print(f"Entry balance  median : {active_last['FirstBeforeBalance'].median():.1f}")
print(f"Exit  balance  median : {active_last['LastAfterBalance'].median():.1f}")
print(f"WinRatio       median : {active_last['WinRatio'].median():.3f}")
print(f"  >= 1.0 (profit)     : {(active_last['WinRatio'] >= 1.0).mean()*100:.1f}%")

# --- 4. Last 3 days trend for churned players ---
print(f"\n=== Churned players: avg WinRatio trend in last 3 days ===")
trend = con.execute(f'''
    WITH ranked AS (
        SELECT vx.PlayerID, vx.Date, vx.WinRatio, vx.LastAfterBalance,
               RANK() OVER (PARTITION BY vx.PlayerID ORDER BY vx.Date DESC) as day_rank
        FROM VariableX vx
        WHERE vx.Date < '{churn_cutoff.date()}'
    )
    SELECT day_rank,
           COUNT(*) as n,
           AVG(WinRatio) as avg_win_ratio,
           AVG(LastAfterBalance) as avg_exit_balance,
           SUM(CASE WHEN WinRatio < 1 THEN 1 ELSE 0 END)*100.0/COUNT(*) as pct_losing
    FROM ranked
    WHERE day_rank <= 3
    GROUP BY day_rank ORDER BY day_rank
''').fetchdf()
print(trend.to_string(index=False))

con.close()
