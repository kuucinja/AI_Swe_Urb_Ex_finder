import os
import json
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


def load_geojson_into_db(geojson_path: str):
    conn = get_conn()
    cur = conn.cursor()

    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    features = data.get("features", [])

    inserted = 0
    skipped = 0

    for feature in features:
        try:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})

            coords = geom.get("coordinates")
            if not coords or len(coords) < 2:
                skipped += 1
                continue

            entity = props.get("entity")
            post_id = props.get("post_id")

            if not entity or not post_id:
                skipped += 1
                continue

            lon, lat = coords[0], coords[1]

            cur.execute("""
                INSERT INTO locations (
                    id, entity, geom,
                    query, display_name, osm_type, osm_id,
                    geocode_confidence, post_id, thread_url,
                    username, time_raw, confidence, comment, evidence
                )
                VALUES (
                    %s, %s,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                ON CONFLICT (id) DO UPDATE SET
                    entity = EXCLUDED.entity,
                    geom = EXCLUDED.geom,
                    confidence = EXCLUDED.confidence;
            """, (
                props.get("id"),
                entity,
                lon, lat,
                props.get("query"),
                props.get("display_name"),
                props.get("osm_type"),
                props.get("osm_id"),
                props.get("geocode_confidence"),
                post_id,
                props.get("thread_url") or props.get("source"),
                props.get("username"),
                props.get("time_raw"),
                props.get("confidence", 0.0),
                props.get("comment"),
                json.dumps(props.get("evidence", []))
            ))

            inserted += 1

        except Exception as e:
            print("Skipping feature:", e)
            skipped += 1

    conn.commit()
    conn.close()

    print(f"[PostGIS GeoJSON] inserted={inserted}, skipped={skipped}")


def load_posts_into_db(jsonl_path: Path):
    conn = get_conn()
    cur = conn.cursor()

    thread_url = jsonl_path.stem

    inserted = 0
    skipped = 0

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            try:
                post = json.loads(line)

                if not post.get("post_id"):
                    skipped += 1
                    continue

                cur.execute("""
                    INSERT INTO posts (
                        post_id, thread_url, username, time_raw, text
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (post_id) DO NOTHING;
                """, (
                    post.get("post_id"),
                    thread_url,
                    post.get("username"),
                    post.get("time_raw"),
                    post.get("text"),
                ))

                inserted += 1

            except Exception as e:
                print("Skipping post:", e)
                skipped += 1

    conn.commit()
    conn.close()

    print(f"[Posts→PostGIS DB] file={jsonl_path.name} inserted={inserted} skipped={skipped}")


if __name__ == "__main__":
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

    load_geojson_into_db(
        f"{PROJECT_ROOT}/data_locations/discovered_locations.geojson"
    )

    directory = Path(f"{PROJECT_ROOT}/data_urbex")

    for file_path in directory.glob("*.jsonl"):
        print(file_path)
        load_posts_into_db(file_path)