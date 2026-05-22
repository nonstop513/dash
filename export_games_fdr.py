"""Export games + fdr tables to D1 SQL dump."""
import sqlite3

conn = sqlite3.connect("analytics.db")
lines = []

# games 表（含新的 has_fdr 欄位）
lines.append("DROP TABLE IF EXISTS games;")
for row in conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='games'"):
    lines.append(row[0] + ";")
lines.append("")
for row in conn.execute("SELECT * FROM games"):
    vals = ", ".join(
        "NULL" if v is None
        else str(v) if isinstance(v, (int, float))
        else "'" + str(v).replace("'", "''") + "'"
        for v in row
    )
    lines.append(f"INSERT INTO games VALUES ({vals});")
lines.append("")

# FDR tables
for table in ("fdr_overview", "fdr_segments"):
    lines.append(f"DROP TABLE IF EXISTS {table};")
    for row in conn.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'"):
        lines.append(row[0] + ";")
    lines.append("")
    for row in conn.execute(f"SELECT * FROM {table}"):
        vals = ", ".join(
            "NULL" if v is None
            else str(v) if isinstance(v, (int, float))
            else "'" + str(v).replace("'", "''") + "'"
            for v in row
        )
        lines.append(f"INSERT INTO {table} VALUES ({vals});")

conn.close()
with open("games_fdr_dump.sql", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"Done: {len(lines)} lines")
