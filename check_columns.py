import duckdb, os

BASE_DIR = r"D:\IGame\db dash"

dbs = {
    "Wide (MechanismStats)": os.path.join(BASE_DIR, "101003_20251207_20260207(wide).duckdb"),
    "Cohort (VariableX)":    os.path.join(BASE_DIR, "101003_20260108_20260318.duckdb"),
}

for label, path in dbs.items():
    duck = duckdb.connect(path, read_only=True)
    print(f"=== {label} ===")
    tables = duck.execute("SHOW TABLES").fetchdf()
    for tbl in tables["name"]:
        cols = duck.execute(f"DESCRIBE {tbl}").fetchdf()
        print(f"  Table: {tbl}")
        for _, row in cols.iterrows():
            print(f"    {row['column_name']:40s} {row['column_type']}")
        # 顯示一筆範例
        sample = duck.execute(f"SELECT * FROM {tbl} LIMIT 1").fetchdf()
        print(f"  Sample row:")
        for col, val in sample.iloc[0].items():
            print(f"    {col:40s} = {val}")
        print()
    duck.close()
    print()
