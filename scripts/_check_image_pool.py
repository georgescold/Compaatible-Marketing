"""Diagnostic ponctuel : combien d'images sont eligibles au matching ?

Compte par compaatible_fit, total et avec public_url renseignee.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db_config import get_conn
from psycopg2.extras import RealDictCursor


def main():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        SELECT
            compaatible_fit,
            COUNT(*) AS total,
            COUNT(public_url) AS with_public_url
        FROM mkt_images
        GROUP BY compaatible_fit
        ORDER BY compaatible_fit
        """
    )
    rows = cur.fetchall()
    print("=== mkt_images : pool par fit ===")
    for r in rows:
        print(dict(r))

    cur.execute("SELECT COUNT(*) AS total FROM mkt_images")
    print("Total mkt_images :", cur.fetchone()["total"])

    cur.execute(
        """
        SELECT COUNT(*) AS eligible_no_url
        FROM mkt_images
        WHERE compaatible_fit IN ('high', 'medium')
          AND public_url IS NULL
        """
    )
    print("Eligibles (high/medium) sans public_url :", cur.fetchone()["eligible_no_url"])

    conn.close()


if __name__ == "__main__":
    main()
