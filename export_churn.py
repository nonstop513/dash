import sqlite3

conn = sqlite3.connect("analytics.db")
lines = []

# Schema for churn tables
for row in conn.execute(
    "SELECT sql FROM sqlite_master WHERE type='table' AND name LIKE 'churn%' AND sql IS NOT NULL"
):
    lines.append("DROP TABLE IF EXISTS " + row[0].split("CREATE TABLE ")[1].split(" (")[0] + ";")
    lines.append(row[0] + ";")
    lines.append("")

# Data
for table in ["churn_overview", "churn_exit_type", "churn_last_days"]:
    rows = conn.execute(f"SELECT * FROM {table}").fetchall()
    for row in rows:
        vals = ", ".join(
            "NULL" if v is None
            else str(v) if isinstance(v, (int, float))
            else "'" + str(v).replace("'", "''") + "'"
            for v in row
        )
        lines.append(f"INSERT INTO {table} VALUES ({vals});")
    lines.append("")

conn.close()

with open("churn_dump.sql", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Done: {len(lines)} lines written to churn_dump.sql")
