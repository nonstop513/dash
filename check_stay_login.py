import duckdb, os

duck = duckdb.connect(r"D:\IGame\db dash\101003_20260108_20260318.duckdb", read_only=True)

print("=== LoginCount_D7 值分布 ===")
d7 = duck.execute("""
    SELECT LoginCount_D7, COUNT(*) AS n
    FROM VariableX
    GROUP BY LoginCount_D7
    ORDER BY LoginCount_D7
    LIMIT 20
""").fetchdf()
print(d7.to_string())
print()

print("=== Stay 值分布 ===")
stay = duck.execute("""
    SELECT Stay, COUNT(*) AS n
    FROM VariableX
    GROUP BY Stay
    ORDER BY Stay
""").fetchdf()
print(stay.to_string())
print()

print("=== LoginCount_D7=1 × Stay（剛好對應我們的 FDR 條件）===")
cross = duck.execute("""
    SELECT LoginCount_D7, Stay, COUNT(*) AS n
    FROM VariableX
    WHERE LoginCount_D7 <= 3
    GROUP BY LoginCount_D7, Stay
    ORDER BY LoginCount_D7, Stay
""").fetchdf()
total = cross["n"].sum()
cross["pct"] = (cross["n"] / total * 100).round(1)
print(cross.to_string())
print()

print("=== Stay 的意義驗證：LoginCount_D7=1 且 Stay=1 的玩家，隔天有沒有出現在 VariableX？===")
sample = duck.execute("""
    WITH today AS (
        SELECT PlayerID, Date, Stay
        FROM VariableX
        WHERE LoginCount_D7 = 1 AND Stay = 1
        LIMIT 5
    )
    SELECT t.PlayerID, t.Date AS today_date, t.Stay,
           v.Date AS next_date
    FROM today t
    LEFT JOIN VariableX v
        ON v.PlayerID = t.PlayerID
        AND CAST(v.Date AS DATE) = CAST(t.Date AS DATE) + 1
    ORDER BY t.PlayerID
""").fetchdf()
print(sample.to_string())
print()

print("=== Stay=0 的玩家，隔天有沒有出現？===")
sample0 = duck.execute("""
    WITH today AS (
        SELECT PlayerID, Date, Stay
        FROM VariableX
        WHERE LoginCount_D7 = 1 AND Stay = 0
        LIMIT 5
    )
    SELECT t.PlayerID, t.Date AS today_date, t.Stay,
           v.Date AS next_date
    FROM today t
    LEFT JOIN VariableX v
        ON v.PlayerID = t.PlayerID
        AND CAST(v.Date AS DATE) = CAST(t.Date AS DATE) + 1
    ORDER BY t.PlayerID
""").fetchdf()
print(sample0.to_string())
print()

# Wide DB 的 Retention 表
print("=== Wide DB：Retention 表結構與範例 ===")
wide = duckdb.connect(r"D:\IGame\db dash\101003_20251207_20260207(wide).duckdb", read_only=True)
ret_sample = wide.execute("""
    SELECT * FROM Retention
    WHERE D1 IS NOT NULL OR D7 IS NOT NULL
    LIMIT 10
""").fetchdf()
print(ret_sample.to_string())
wide.close()
duck.close()
