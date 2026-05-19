"""Diagnostic ponctuel : pick une URL publique au hasard et fait un HEAD pour
verifier qu'elle est servie correctement par Supabase Storage en public."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from db_config import get_conn
from psycopg2.extras import RealDictCursor
import requests

conn = get_conn()
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute(
    "SELECT filename, public_url FROM mkt_images WHERE public_url IS NOT NULL ORDER BY random() LIMIT 1"
)
row = cur.fetchone()
print("Sample URL:", row["public_url"])
r = requests.head(row["public_url"], timeout=10)
print("HEAD status:", r.status_code)
print("content-type:", r.headers.get("content-type"))
print("content-length:", r.headers.get("content-length"))
conn.close()
