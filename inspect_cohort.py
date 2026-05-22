import duckdb

cohort = duckdb.connect("101003_20260108_20260318.duckdb", read_only=True)

# CohortBase 結構 - 單一玩家追蹤
print("=== 同一玩家的所有 CohortBase 紀錄（PlayerID 1845797）===")
p = cohort.execute("SELECT * FROM CohortBase WHERE PlayerID=1845797 ORDER BY CohortDay").fetchdf()
print(p.to_string())
print()

# 另一個玩家，找一個只有少量紀錄的
print("=== 一位「只有幾筆」的玩家 ===")
small = cohort.execute("""
    SELECT PlayerID, COUNT(*) AS n
    FROM CohortBase
    GROUP BY PlayerID
    HAVING n BETWEEN 2 AND 5
    LIMIT 5
""").fetchdf()
for pid in small["PlayerID"]:
    rows = cohort.execute(f"SELECT * FROM CohortBase WHERE PlayerID={pid} ORDER BY CohortDay").fetchdf()
    print(f"PlayerID {pid}:")
    print(rows.to_string())
    print()

# DayIndex 分布
print("=== DayIndex 值分布（前 30 個）===")
di = cohort.execute("SELECT DayIndex, COUNT(*) AS n FROM CohortBase GROUP BY DayIndex ORDER BY DayIndex LIMIT 30").fetchdf()
print(di.to_string())
print()

# 2026-01-08 的 cohort 比較
print("=== 2026-01-08：CohortBase DayIndex=0 vs VariableX DAU ===")
c0 = cohort.execute("SELECT COUNT(*) AS n FROM CohortBase WHERE DayIndex=0 AND CAST(CohortDay AS DATE)=DATE '2026-01-08'").fetchone()[0]
dau = cohort.execute("SELECT COUNT(*) AS n FROM (SELECT PlayerID FROM VariableX WHERE CAST(Date AS DATE)=DATE '2026-01-08' GROUP BY PlayerID) t").fetchone()[0]
print(f"  CohortBase DayIndex=0 on 2026-01-08: {c0:,}")
print(f"  VariableX DAU on 2026-01-08:         {dau:,}")
print()

# DayIndex=0 是「全部當天活躍」還是「只有新玩家」？
print("=== 假設驗證：CohortBase DayIndex=0 每天人數 vs VariableX DAU ===")
coh_daily = cohort.execute("""
    SELECT CAST(CohortDay AS DATE) AS d, COUNT(*) AS coh_n
    FROM CohortBase WHERE DayIndex=0
    GROUP BY CAST(CohortDay AS DATE)
    ORDER BY d LIMIT 15
""").fetchdf()
var_daily = cohort.execute("""
    SELECT CAST(Date AS DATE) AS d, COUNT(*) AS var_n
    FROM (SELECT PlayerID, Date FROM VariableX GROUP BY PlayerID, Date)
    GROUP BY CAST(Date AS DATE)
    ORDER BY d LIMIT 15
""").fetchdf()
import pandas as pd
merged = coh_daily.merge(var_daily, on="d", how="outer")
print(merged.to_string())

cohort.close()
