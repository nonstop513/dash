import sqlite3

conn = sqlite3.connect("analytics.db")
lines = []

for row in conn.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name='segment_cross' AND sql IS NOT NULL"
):
    lines.append("DROP TABLE IF EXISTS segment_cross;")
    lines.append(row[0] + ";")
    lines.append("")

for row in conn.execute("SELECT * FROM segment_cross"):
    vals = ", ".join(
        "NULL" if v is None
        else str(v) if isinstance(v, (int, float))
        else "'" + str(v).replace("'", "''") + "'"
        for v in row
    )
    lines.append(f"INSERT INTO segment_cross VALUES ({vals});")

conn.close()

with open("segment_dump.sql", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"Done: {len(lines)} lines")
