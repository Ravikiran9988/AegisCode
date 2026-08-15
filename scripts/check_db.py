"""Verify SQLite tables are created on disk."""
import sqlite3
import sys

db_path = "aegiscode.db"

try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]
    conn.close()

    expected = {"projects", "runs", "iterations", "events"}
    found = set(tables)

    print(f"Tables found: {sorted(tables)}")

    missing = expected - found
    if missing:
        print(f"MISSING TABLES: {missing}")
        sys.exit(1)

    print("ALL REQUIRED TABLES PRESENT")
    sys.exit(0)
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
