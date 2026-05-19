"""Inspecte la DB Supabase marketing : liste les schémas, tables et colonnes existants.

Ne MODIFIE rien. Lecture seule. Sert à comprendre l'état actuel (notamment les tables
des blogs Compaatible déjà présentes) avant d'ajouter table `images`, `tweets`, etc.
"""
from db_config import get_conn


def main() -> None:
    conn = get_conn()
    cur = conn.cursor()

    print("=" * 80)
    print("SCHÉMAS")
    print("=" * 80)
    cur.execute(
        """
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
          AND schema_name NOT LIKE 'pg_%'
        ORDER BY schema_name;
        """
    )
    schemas = [r[0] for r in cur.fetchall()]
    for s in schemas:
        print(f"  - {s}")

    print()
    print("=" * 80)
    print("TABLES (schéma public)")
    print("=" * 80)
    cur.execute(
        """
        SELECT
            t.table_name,
            (SELECT n_live_tup FROM pg_stat_user_tables WHERE relname = t.table_name) AS row_count
        FROM information_schema.tables t
        WHERE t.table_schema = 'public'
          AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_name;
        """
    )
    tables = cur.fetchall()
    if not tables:
        print("  (aucune table dans public)")
    for name, count in tables:
        print(f"  - {name:<40s} ~{count if count is not None else '?'} rows")

    print()
    print("=" * 80)
    print("COLONNES PAR TABLE (schéma public)")
    print("=" * 80)
    for name, _ in tables:
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position;
            """,
            (name,),
        )
        cols = cur.fetchall()
        print(f"\n[{name}]")
        for col_name, dtype, nullable in cols:
            null_str = "NULL" if nullable == "YES" else "NOT NULL"
            print(f"  {col_name:<35s} {dtype:<20s} {null_str}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
