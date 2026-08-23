-- schema.sql
--
-- Full schema for the "urbex" PostgreSQL/PostGIS database.
-- This is a snapshot of the live schema (introspected from the running
-- database on 2026-07-27) — it is the single source of truth for
-- reproducing the database from scratch, e.g.:
--
--   createdb urbex
--   psql -d urbex -f database/schema.sql
--
-- All application code must go through database/repository.py rather
-- than issuing DDL/DML directly.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------
-- Crawl state: themes -> threads -> thread_pages
-- ---------------------------------------------------

CREATE TABLE IF NOT EXISTS themes (
    theme_id    TEXT PRIMARY KEY,
    url         TEXT NOT NULL UNIQUE,
    seen        BOOLEAN DEFAULT FALSE,
    completed   BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS threads (
    thread_id   TEXT PRIMARY KEY,
    theme_id    TEXT REFERENCES themes(theme_id) ON DELETE CASCADE,
    title       TEXT,
    url         TEXT NOT NULL UNIQUE,
    urbex       BOOLEAN,
    result      JSONB,
    seen        BOOLEAN DEFAULT FALSE,
    completed   BOOLEAN DEFAULT FALSE,
    checked_at  TIMESTAMP,
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS thread_pages (
    id            SERIAL PRIMARY KEY,
    thread_id     TEXT REFERENCES threads(thread_id) ON DELETE CASCADE,
    page_number   INTEGER,
    url           TEXT NOT NULL UNIQUE,
    seen          BOOLEAN DEFAULT FALSE,
    completed     BOOLEAN DEFAULT FALSE,
    created_at    TIMESTAMP DEFAULT NOW()
);

-- ---------------------------------------------------
-- Scraped content
-- ---------------------------------------------------

CREATE TABLE IF NOT EXISTS posts (
    post_id     TEXT PRIMARY KEY,
    thread_url  TEXT,
    username    TEXT,
    time_raw    TEXT,
    text        TEXT
);

CREATE TABLE IF NOT EXISTS locations (
    id                   TEXT PRIMARY KEY,
    entity               TEXT,
    geom                 GEOGRAPHY(Point, 4326),
    query                TEXT,
    display_name         TEXT,
    osm_type             TEXT,
    osm_id               TEXT,
    geocode_confidence   DOUBLE PRECISION,
    post_id              TEXT,
    thread_url           TEXT,
    username             TEXT,
    time_raw             TEXT,
    confidence           DOUBLE PRECISION,
    comment              TEXT,
    evidence             JSONB,
    reasoning            TEXT,
    verified             BOOLEAN DEFAULT FALSE
);

-- ---------------------------------------------------
-- Location agent resume/checkpoint state
--
-- Replaces retrieval/data/location_agent_state.json. `key` mirrors the
-- in-memory QueueItem.key scheme used by urbex_location_agent.py
-- ("thread:<url>", "post:<text>", "web_search:<query>") so an
-- interrupted run can resume without reprocessing the same item.
-- Discovered locations themselves live in `locations` (see above),
-- not here.
-- ---------------------------------------------------

CREATE TABLE IF NOT EXISTS location_agent_visited (
    key         TEXT PRIMARY KEY,
    kind        TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- ---------------------------------------------------
-- Indexes
-- ---------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_posts_thread_url ON posts(thread_url);
CREATE INDEX IF NOT EXISTS idx_locations_post_id ON locations(post_id);
CREATE INDEX IF NOT EXISTS idx_locations_geom ON locations USING GIST (geom);