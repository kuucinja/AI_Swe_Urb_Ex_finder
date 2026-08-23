import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))

from database.repository import parse_theme_id, parse_thread_id, parse_page_number

import os
import json
import psycopg2
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import re

load_dotenv()

DATA_DIR =  Path(__file__).resolve().parents[1] / "data"

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def load_set(name):
    path = Path(DATA_DIR) / name
    print(f"Loading JSON from {path}")
    if not path.exists():
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(json.load(f))

def load_list(name):
    path = Path(DATA_DIR) / name
    if not path.exists():
        return []

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_theme_id(url):
    m = re.search(r"/f(\d+)", url)
    return f"f{m.group(1)}" if m else None


def parse_thread_id(url):
    m = re.search(r"/t(\d+)", url)
    return f"t{m.group(1)}" if m else None


# -------------------------
# THEMES
# -------------------------
def migrate_themes():
    # theme_id = parse_theme_id(url)
    conn = get_conn()
    cur = conn.cursor()

    seen = load_set("seen_themes.json")
    completed = load_set("completed_themes.json")

    all_themes = seen | completed

    print("SEEN THEMES:", len(seen))
    print("COMPLETED THEMES:", len(completed))
    print("ALL THEMES:", len(all_themes))
    print(list(all_themes)[:5])

    for url in all_themes:
        theme_id = parse_theme_id(url)

        cur.execute("""
            INSERT INTO themes (theme_id, url, seen, completed, created_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (theme_id) DO UPDATE SET
                seen = EXCLUDED.seen,
                completed = EXCLUDED.completed;
        """, (
            theme_id,
            url,
            url in seen,
            url in completed
        ))


    conn.commit()
    conn.close()
    print(f"[themes] migrated {len(all_themes)}")


# -------------------------
# PAGES
# -------------------------
def migrate_pages():
    # thread_id = parse_thread_id(url)
    # page_number = parse_page_number(url)
    conn = get_conn()
    cur = conn.cursor()

    seen = load_set("seen_pages.json")
    completed = load_set("completed_pages.json")

    all_pages = seen | completed

    for url in all_pages:
        thread_id = parse_thread_id(url)
        page_number = parse_page_number(url)

        cur.execute("""
            INSERT INTO thread_pages (
                thread_id, page_number, url,
                seen, completed, created_at
            )
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT DO NOTHING;
        """, (
            thread_id,
            page_number,
            url,
            url in seen,
            url in completed
        ))

    conn.commit()
    conn.close()
    print(f"[pages] migrated {len(all_pages)}")


# -------------------------
# THREADS
# -------------------------
def migrate_threads():
    # thread_id = parse_thread_id(url)
    # page_number = parse_page_number(url)
    # theme_id = parse_theme_id(url)
    conn = get_conn()
    cur = conn.cursor()

    seen = load_set("seen_threads.json")
    completed = load_set("completed_threads.json")
    results = load_list("results.json")

    all_threads = seen | completed

    # map url -> result object
    result_map = {r["url"]: r for r in results}

    for url in all_threads:
        thread_id = parse_thread_id(url)
        theme_url = result_map.get(url, {}).get("theme")
        theme_id = parse_theme_id(theme_url) if theme_url else None

        if theme_id == "f492":
            urbex = True
        else:
            urbex = result_map.get(url, {}).get("urbex", False)

        cur.execute("""
            INSERT INTO threads (
                thread_id,
                theme_id,
                title,
                url,
                urbex,
                result,
                seen,
                completed,
                checked_at,
                created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (thread_id)
            DO UPDATE SET
                seen = EXCLUDED.seen,
                completed = EXCLUDED.completed,
                urbex = EXCLUDED.urbex,
                result = EXCLUDED.result;
        """, (
            thread_id,
            theme_id,
            result_map.get(url, {}).get("title"),
            url,
            result_map.get(url, {}).get("urbex", False),
            json.dumps(result_map.get(url, {})),
            url in seen,
            url in completed,
            datetime.utcnow()
        ))

    conn.commit()
    conn.close()
    print(f"[threads] migrated {len(all_threads)}")


# -------------------------
# RUN
# -------------------------
if __name__ == "__main__":
    migrate_themes()
    migrate_pages()
    migrate_threads()