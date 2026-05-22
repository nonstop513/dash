"""Export fdr_overview + fdr_segments to SQL dump for D1 import."""
import sqlite3

conn = sqlite3.connect("analytics.db")
lines = []

for table in ("fdr_overview", "fdr_segments"):
    for row in conn.execute(
        f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}' AND sql IS NOT NULL"
    ):
        lines.append(f"DROP TABLE IF EXISTS {table};")
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
with open("fdr_dump.sql", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"Done: {len(lines)} lines")
