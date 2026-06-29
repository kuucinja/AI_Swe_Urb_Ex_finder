##
##TURNS THE FOUND LOCATION GEOJSON AND THE THREAD INFO INTO AN EASILY QUERYABLE SQLITE DATABASE.
##

import json
from db import get_conn, init_db

import sys
from pathlib import Path


init_db()

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

            if not props or not geom:
                skipped += 1
                continue

            coords = geom.get("coordinates")
            if not coords or len(coords) < 2:
                skipped += 1
                continue

            entity = props.get("entity")
            post_id = props.get("post_id")
            thread_url = props.get("source")
            confidence = props.get("confidence", 0.0)

            if not entity or not post_id:
                skipped += 1
                continue

            lon, lat = coords[0], coords[1]

            cur.execute("""
                INSERT OR REPLACE INTO locations
                (entity, lat, lon, post_id, thread_url, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (entity, lat, lon, post_id, thread_url, confidence))

            inserted += 1

        except Exception as e:
            print("Skipping feature due to error:", e)
            skipped += 1

    conn.commit()
    conn.close()

    print(f"[GeoJSON→DB] inserted={inserted}, skipped={skipped}")


def load_posts_into_db(jsonl_path: Path):
    conn = get_conn()
    cur = conn.cursor()

    # use filename as thread identifier
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
                    INSERT OR REPLACE INTO posts
                    (post_id, thread_url, username, time_raw, text)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    post.get("post_id"),
                    thread_url,
                    post.get("username"),
                    post.get("time_raw"),
                    post.get("text")
                ))

                inserted += 1

            except Exception as e:
                print("Skipping post due to error:", e)
                skipped += 1

    conn.commit()
    conn.close()

    print(f"[Posts→DB] file={jsonl_path.name} inserted={inserted} skipped={skipped}")


if __name__ == "__main__":
        

    PROJECT_ROOT = Path(__file__).resolve().parent.parent


    load_geojson_into_db(f"{PROJECT_ROOT}/data_locations/discovered_locations.geojson")


    directory = Path(f"{PROJECT_ROOT}/data_urbex")

    for file_path in directory.glob("*.jsonl"):
        print(file_path)
        load_posts_into_db(file_path)
