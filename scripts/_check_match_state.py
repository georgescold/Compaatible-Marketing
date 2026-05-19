"""Diagnostic : combien de tweets sont vraiment liees a une image (image_id NOT NULL)
vs seulement marquees needs_image=true. Et un sample des 3 derniers tweets lies."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from db_config import get_conn
from psycopg2.extras import RealDictCursor

conn = get_conn()
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute(
    """
    SELECT
        COUNT(*) FILTER (WHERE needs_image = TRUE) AS needs_image_total,
        COUNT(*) FILTER (WHERE needs_image = TRUE AND image_id IS NOT NULL) AS linked,
        COUNT(*) FILTER (WHERE needs_image = TRUE AND image_id IS NULL) AS not_linked,
        COUNT(*) FILTER (WHERE needs_image = TRUE AND media_url IS NOT NULL) AS with_media_url
    FROM mkt_tweets
    """
)
print("=== mkt_tweets : etat des liens image ===")
print(dict(cur.fetchone()))

cur.execute(
    """
    SELECT t.id, LEFT(t.content, 60) AS content_preview,
           t.image_id, t.media_url, i.filename, i.public_url
    FROM mkt_tweets t
    LEFT JOIN mkt_images i ON i.id = t.image_id
    WHERE t.image_id IS NOT NULL
    ORDER BY t.id DESC
    LIMIT 3
    """
)
print()
print("=== 3 derniers tweets lies ===")
for r in cur.fetchall():
    print(dict(r))

conn.close()
