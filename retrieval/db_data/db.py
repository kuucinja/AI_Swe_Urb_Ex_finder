from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "ir_data.db"

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        entity TEXT,
        lat REAL,
        lon REAL,
        post_id TEXT,
        thread_url TEXT,
        confidence REAL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        post_id TEXT PRIMARY KEY,
        thread_url TEXT,
        username TEXT,
        time_raw TEXT,
        text TEXT
    )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_entity ON locations(entity)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_post_id ON posts(post_id)")

    conn.commit()
    conn.close()