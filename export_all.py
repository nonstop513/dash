"""Full re-export of all analytics tables to D1."""
import sqlite3

conn = sqlite3.connect("analytics.db")
lines = []

TABLES = [
    "games", "domains",
    "dau_daily", "rtp_daily",
    "cohort_matrix", "segment_cross",
    "churn_overview", "churn_exit_type", "churn_last_days",
    "fdr_overview", "fdr_segments",
]

for table in TABLES:
    lines.append(f"DROP TABLE IF EXISTS {table};")
    for row in conn.execute(
        f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'"
    ):
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
    lines.append("")

conn.close()
with open("full_dump.sql", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"Done: {len(lines)} lines")
