"""Exécute une migration SQL. Idempotent (les migrations utilisent IF NOT EXISTS / IF EXISTS).

Usage : python run_migration.py 001_rename_and_create_mkt.sql
"""
import sys
from pathlib import Path
from db_config import get_conn


def run_migration(filename: str) -> None:
    sql_path = Path(__file__).parent / "migrations" / filename
    if not sql_path.exists():
        print(f"ERROR: migration not found: {sql_path}")
        sys.exit(1)

    sql = sql_path.read_text(encoding="utf-8")
    print(f"Running migration: {filename} ({sql_path.stat().st_size} bytes)")

    conn = get_conn(autocommit=True)
    cur = conn.cursor()
    try:
        cur.execute(sql)
        # Récupérer les NOTICE émis par RAISE NOTICE
        for notice in conn.notices:
            print(f"  PG: {notice.strip()}")
        print(f"Migration {filename} OK.")
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(2)
    finally:
        cur.close()
        conn.close()


def list_mkt_tables() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT t.table_name,
               (SELECT n_live_tup FROM pg_stat_user_tables WHERE relname = t.table_name) AS row_count
        FROM information_schema.tables t
        WHERE t.table_schema='public' AND t.table_name LIKE 'mkt_%'
        ORDER BY t.table_name;
        """
    )
    print("\nTables mkt_* après migration :")
    for name, count in cur.fetchall():
        print(f"  - {name:<35s} ~{count if count is not None else '?'} rows")
    cur.close()
    conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python run_migration.py <migration_file.sql>")
        print("Available migrations:")
        for f in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
            print(f"  - {f.name}")
        sys.exit(1)

    run_migration(sys.argv[1])
    list_mkt_tables()
