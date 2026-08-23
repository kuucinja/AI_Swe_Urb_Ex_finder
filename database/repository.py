"""
repository.py

The ONLY module that communicates directly with PostgreSQL/PostGIS.
All other modules (scraper, orchestrator, agent, API) should call
functions from here instead of writing SQL.
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
import re
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}


# ---------------------------------------------------
# Connection
# ---------------------------------------------------

def get_conn():
    return psycopg2.connect(
        **DB_CONFIG,
        cursor_factory=RealDictCursor
    )

#---------------------------------------------------
# Helper functions
#---------------------------------------------------

def _fetch_one(query, params):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    row = cur.fetchone()
    conn.close()
    return row

def _execute(query, params):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params)
    conn.commit()
    conn.close()

def now():
    return datetime.utcnow()

# -----------------------------
# Crawl State
# -----------------------------
# ok, so the PostgreSQL structure is:
# themes:
# [theme_id,url,seen,completed, created_at]
# threads:
# [thread_id,theme_id,title,url,urbex,result,seen,completed, checked_at,created_at]
# thread_pages:
# [id,thread_id,page_number,url,seen,completed,created_at]

#####THEME QUERIES
def parse_theme_id(url: str) -> str | None:
    match = re.search(r"/f(\d+)", url)
    return f"f{match.group(1)}" if match else None

def has_seen_theme(theme_url):
    theme_id = parse_theme_id(theme_url)
    if not theme_id:
        return False

    row = _fetch_one(
        "SELECT seen FROM themes WHERE theme_id = %s",
        (theme_id,)
    )

    return bool(row["seen"]) if row else False

def mark_theme_seen(theme_url):
    theme_id = parse_theme_id(theme_url)
    if not theme_id:
        return

    _execute("""
        INSERT INTO themes (theme_id, url, seen)
        VALUES (%s, %s, TRUE)
        ON CONFLICT (theme_id)
        DO UPDATE SET seen = TRUE;
    """, (theme_id, theme_url))

def has_completed_theme(theme_url):
    theme_id = parse_theme_id(theme_url)
    if not theme_id:
        return False

    row = _fetch_one(
        "SELECT completed FROM themes WHERE theme_id = %s",
        (theme_id,)
    )

    return bool(row["completed"]) if row else False

def mark_theme_completed(theme_url):
    theme_id = parse_theme_id(theme_url)
    if not theme_id:
        return

    _execute("""
        INSERT INTO themes (theme_id, url, completed)
        VALUES (%s, %s, TRUE)
        ON CONFLICT (theme_id)
        DO UPDATE SET completed = TRUE;
    """, (theme_id, theme_url))

###THREAD QUERIES

def parse_thread_id(url: str) -> str | None:
    match = re.search(r"/t(\d+)", url)
    return f"t{match.group(1)}" if match else None

def has_seen_thread(thread_url):
    thread_id = parse_thread_id(thread_url)

    if not thread_id:
        return False

    row = _fetch_one(
        """
        SELECT seen 
        FROM threads
        WHERE thread_id = %s
        """,
        (thread_id,)
    )

    return bool(row["seen"]) if row else False

def mark_thread_seen(thread_url):
    thread_id = parse_thread_id(thread_url)
    if not thread_id:
        return

    _execute("""
        INSERT INTO threads (thread_id, url, seen)
        VALUES (%s, %s, TRUE)
        ON CONFLICT (thread_id)
        DO UPDATE SET seen = TRUE;
    """, (thread_id, thread_url))

def has_completed_thread(thread_url):
    thread_id = parse_thread_id(thread_url)
    if not thread_id:
        return False

    row = _fetch_one(
        "SELECT completed FROM threads WHERE thread_id = %s",
        (thread_id,)
    )

    return bool(row["completed"]) if row else False

def mark_thread_completed(thread_url):
    thread_id = parse_thread_id(thread_url)
    if not thread_id:
        return

    _execute("""
        UPDATE threads
        SET completed = TRUE
        WHERE thread_id = %s
    """, (thread_id,))

def set_thread_created_at(thread_id: str):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE threads
        SET created_at = %s
        WHERE thread_id = %s
    """, (now(), thread_id))

    conn.commit()
    conn.close()

def mark_thread_checked(thread_id: str):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE threads
        SET checked_at = %s
        WHERE thread_id = %s
    """, (now(), thread_id))

    conn.commit()
    conn.close()

def set_thread_urbex(thread_id: str, value: bool):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE threads
        SET urbex = %s
        WHERE thread_id = %s
    """, (value, thread_id))

    conn.commit()
    conn.close()

def set_thread_page_created_at(thread_id: str, page_number: int):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE thread_pages
        SET created_at = %s
        WHERE thread_id = %s AND page_number = %s
    """, (now(), thread_id, page_number))

    conn.commit()
    conn.close()

def get_thread(thread_id: str):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM threads WHERE thread_id = %s
    """, (thread_id,))

    row = cur.fetchone()
    conn.close()
    return row

def upsert_thread(thread_id, theme_id, title, url):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO threads (thread_id, theme_id, title, url)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (thread_id)
        DO UPDATE SET
            theme_id = EXCLUDED.theme_id,
            title = EXCLUDED.title,
            url = EXCLUDED.url
    """, (thread_id, theme_id, title, url))

    conn.commit()
    conn.close()

def set_thread_result(thread_id: str, result: dict):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        UPDATE threads
        SET result = %s,
            checked_at = %s
        WHERE thread_id = %s
    """, (
        json.dumps(result),
        now(),
        thread_id
    ))

    conn.commit()
    conn.close()

def get_urbex_threads(limit=None):
    """Threads classified urbex-positive by UrbEx_search.py.

    Feeds the second-stage location agent, replacing the old
    data/results.json hand-off.
    """
    conn = get_conn()
    cur = conn.cursor()
    query = """
        SELECT thread_id, theme_id, title, url, urbex, result, created_at
        FROM threads
        WHERE urbex = TRUE
        ORDER BY created_at
    """
    if limit:
        query += " LIMIT %s"
        cur.execute(query, (limit,))
    else:
        cur.execute(query)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_scrape_progress():
    """{"threads_known": N, "threads_scraped": M} - known = urbex-positive
    threads discovered so far (grows as the crawler's discovery pass
    runs), scraped = how many of those have at least one post fetched.
    Used for the crawler status/progress UI."""
    row = _fetch_one(
        """
        SELECT
            COUNT(*) AS threads_known,
            COUNT(*) FILTER (
                WHERE EXISTS (SELECT 1 FROM posts p WHERE p.thread_url = threads.url)
            ) AS threads_scraped
        FROM threads
        WHERE urbex = TRUE
        """,
        ()
    )
    return {
        "threads_known": row["threads_known"] if row else 0,
        "threads_scraped": row["threads_scraped"] if row else 0,
    }

###PAGE QUERIES

def parse_page_number(url: str) -> int:
    match = re.search(r"p(\d+)", url)
    return int(match.group(1)) if match else 1



def has_seen_page(page_url):
    row = _fetch_one(
        "SELECT seen FROM thread_pages WHERE url = %s",
        (page_url,)
    )

    return bool(row["seen"]) if row else False

def mark_page_seen(page_url):
    thread_id = parse_thread_id(page_url)
    page_number = parse_page_number(page_url)

    _execute("""
        INSERT INTO thread_pages (thread_id, page_number, url, seen)
        VALUES (%s, %s, %s, TRUE)
        ON CONFLICT (url)
        DO UPDATE SET seen = TRUE;
    """, (thread_id, page_number, page_url))

def has_completed_page(page_url):
    row = _fetch_one(
        "SELECT completed FROM thread_pages WHERE url = %s",
        (page_url,)
    )

    return bool(row["completed"]) if row else False

def mark_page_completed(page_url):
    _execute("""
        UPDATE thread_pages
        SET completed = TRUE
        WHERE url = %s
    """, (page_url,))



# ---------------------------------------------------
# Location Queries
# ---------------------------------------------------

_LOCATION_COLUMNS = """
    id, entity, ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lon,
    query, display_name, osm_type, osm_id, geocode_confidence,
    post_id, thread_url, username, time_raw, confidence, comment, evidence,
    reasoning, verified
"""


def get_location(location_id):
    """Return one location by its id."""
    return _fetch_one(
        f"SELECT {_LOCATION_COLUMNS} FROM locations WHERE id = %s",
        (location_id,)
    )


def get_locations():
    """Return every location."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(f"SELECT {_LOCATION_COLUMNS} FROM locations")
    rows = cur.fetchall()
    conn.close()
    return rows


def search_locations(text):
    """Search locations by entity/display name."""
    conn = get_conn()
    cur = conn.cursor()
    like_term = f"%{text}%"
    cur.execute(
        f"""
        SELECT {_LOCATION_COLUMNS} FROM locations
        WHERE entity ILIKE %s OR display_name ILIKE %s
        """,
        (like_term, like_term)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def search_locations_multi(terms: list):
    """OR-match any of `terms` against entity/display_name - the actual
    identified place name and its geocoded address. Deliberately does NOT
    match against `comment` (the raw forum post excerpt): a post can
    mention a region in passing ("I used to live near X, but this is in
    Y") without the location actually being there, which pulled unrelated
    locations into region-based searches. Empty `terms` returns every
    location.

    Combines exact substring matching (ILIKE) with trigram similarity
    (pg_trgm's % operator, database/schema.sql) so a typo like "kymlige"
    still finds "Kymlinge" instead of silently returning nothing. Used by
    backend/coverage.py."""
    if not terms:
        return get_locations()

    conn = get_conn()
    cur = conn.cursor()
    clauses = []
    params = []
    for term in terms:
        clauses.append("(entity ILIKE %s OR display_name ILIKE %s OR entity %% %s OR display_name %% %s)")
        like_term = f"%{term}%"
        params.extend([like_term, like_term, term, term])

    cur.execute(
        f"SELECT {_LOCATION_COLUMNS} FROM locations WHERE {' OR '.join(clauses)}",
        params
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def search_bbox(min_lon, min_lat, max_lon, max_lat):
    """Spatial search inside a bounding box."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT {_LOCATION_COLUMNS} FROM locations
        WHERE geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)
        """,
        (min_lon, min_lat, max_lon, max_lat)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def search_radius(lat, lon, radius_meters):
    """Spatial search around a point."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT {_LOCATION_COLUMNS},
            ST_Distance(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) AS distance_m
        FROM locations
        WHERE ST_DWithin(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)
        ORDER BY distance_m
        """,
        (lon, lat, lon, lat, radius_meters)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def insert_location(location: dict):
    """Insert or update a single location (upsert by id)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO locations (
            id, entity, geom, query, display_name, osm_type, osm_id,
            geocode_confidence, post_id, thread_url, username, time_raw,
            confidence, comment, evidence, reasoning
        )
        VALUES (
            %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        ON CONFLICT (id) DO UPDATE SET
            entity = CASE WHEN locations.verified THEN locations.entity ELSE EXCLUDED.entity END,
            geom = EXCLUDED.geom,
            query = EXCLUDED.query,
            display_name = EXCLUDED.display_name,
            osm_type = EXCLUDED.osm_type,
            osm_id = EXCLUDED.osm_id,
            geocode_confidence = EXCLUDED.geocode_confidence,
            post_id = EXCLUDED.post_id,
            thread_url = EXCLUDED.thread_url,
            username = EXCLUDED.username,
            time_raw = EXCLUDED.time_raw,
            confidence = EXCLUDED.confidence,
            comment = EXCLUDED.comment,
            evidence = EXCLUDED.evidence,
            reasoning = CASE WHEN locations.verified THEN locations.reasoning ELSE EXCLUDED.reasoning END
        """,
        (
            location["id"], location.get("entity"),
            location["lon"], location["lat"],
            location.get("query"), location.get("display_name"),
            location.get("osm_type"), location.get("osm_id"),
            location.get("geocode_confidence"), location.get("post_id"),
            location.get("thread_url"), location.get("username"),
            location.get("time_raw"), location.get("confidence"),
            location.get("comment"), json.dumps(location.get("evidence") or []),
            location.get("reasoning")
        )
    )
    conn.commit()
    conn.close()


def insert_locations(locations):
    """Bulk insert/update locations."""
    for location in locations:
        insert_location(location)


def update_location(location_id, **fields):
    """Update selected columns for a location."""
    if not fields:
        return
    conn = get_conn()
    cur = conn.cursor()
    set_clause = ", ".join(f"{column} = %s" for column in fields)
    values = list(fields.values()) + [location_id]
    cur.execute(f"UPDATE locations SET {set_clause} WHERE id = %s", values)
    conn.commit()
    conn.close()


def delete_location(location_id):
    """Delete a location."""
    _execute("DELETE FROM locations WHERE id = %s", (location_id,))


def update_location_geocode(location_id, lat, lon, display_name=None, osm_type=None, osm_id=None):
    """Update a location's position/address after a human annotator picks
    a geocode candidate for it. `geom` needs the ST_MakePoint conversion,
    so it can't go through the generic update_location(**fields) setter.
    Sets verified=True and confidence=1.0 - a human explicitly confirmed
    this exact pin, which is as certain as this data gets."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE locations
        SET geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
            display_name = %s,
            osm_type = %s,
            osm_id = %s,
            verified = TRUE,
            confidence = 1.0
        WHERE id = %s
        """,
        (lon, lat, display_name, osm_type, osm_id, location_id)
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------
# Post Queries
# ---------------------------------------------------

def get_post(post_id):
    """Return one forum post."""
    return _fetch_one("SELECT * FROM posts WHERE post_id = %s", (post_id,))


def get_posts():
    """Return all posts."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM posts")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_posts_for_thread(thread_url):
    """Return every post in one thread."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM posts WHERE thread_url = %s", (thread_url,))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_posts_for_location(location_id):
    """Return posts associated with a location."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT p.* FROM posts p
        JOIN locations l ON l.post_id = p.post_id
        WHERE l.id = %s
        """,
        (location_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def insert_post(post: dict):
    """Insert one scraped post (upsert by post_id)."""
    _execute(
        """
        INSERT INTO posts (post_id, thread_url, username, time_raw, text)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (post_id) DO UPDATE SET
            thread_url = EXCLUDED.thread_url,
            username = EXCLUDED.username,
            time_raw = EXCLUDED.time_raw,
            text = EXCLUDED.text
        """,
        (
            post.get("post_id"), post.get("thread_url"),
            post.get("username"), post.get("time_raw"), post.get("text")
        )
    )


def insert_posts(posts):
    """Bulk insert scraped posts."""
    for post in posts:
        if post.get("post_id"):
            insert_post(post)


# ---------------------------------------------------
# Coverage / Agent Queries
# ---------------------------------------------------

def coverage_check(parsed_query):
    """
    Return locations already matching the parsed query.
    Used by the orchestrator before deciding to scrape.

    NOTE: not implemented yet - depends on backend.models.ParsedQuery,
    which backend/orchestrator.py and backend/coverage.py still need to
    be rewired onto this repository layer for (currently they read the
    old SQLite db / local geojson files instead).
    """
    pass


def get_recent_locations(limit=100):
    """
    Newest scraped locations.

    NOTE: not implemented - the `locations` table has no timestamp
    column, so "recent" can't be determined yet. Add a `scraped_at
    TIMESTAMP DEFAULT NOW()` column (see database/schema.sql) before
    implementing this.
    """
    pass


def get_locations_by_confidence(min_confidence):
    """Locations above a confidence threshold."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        f"SELECT {_LOCATION_COLUMNS} FROM locations WHERE confidence >= %s",
        (min_confidence,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows


# ---------------------------------------------------
# Location Agent Resume State
#
# Replaces retrieval/data/location_agent_state.json's `visited` set.
# Discovered locations themselves are read back via get_locations().
# ---------------------------------------------------

def has_visited(key: str) -> bool:
    return _fetch_one("SELECT 1 FROM location_agent_visited WHERE key = %s", (key,)) is not None


def mark_visited(key: str, kind: str = None):
    _execute(
        """
        INSERT INTO location_agent_visited (key, kind)
        VALUES (%s, %s)
        ON CONFLICT (key) DO NOTHING
        """,
        (key, kind)
    )


def get_visited_keys() -> set:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT key FROM location_agent_visited")
    rows = cur.fetchall()
    conn.close()
    return {row["key"] for row in rows}


# ---------------------------------------------------
# Maintenance
# ---------------------------------------------------

def location_exists(location_id):
    return _fetch_one("SELECT 1 FROM locations WHERE id = %s", (location_id,)) is not None


def post_exists(post_id):
    return _fetch_one("SELECT 1 FROM posts WHERE post_id = %s", (post_id,)) is not None


def vacuum():
    """Database maintenance if needed."""
    pass

