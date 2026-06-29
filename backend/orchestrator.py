"""
The first real "tool" in the agent: decide whether an incoming query
can be answered from the SQLite lookup db, or whether it needs a fresh
scrape.

Flow:
    1. Parse the query (rough for now)
    2. check_coverage() against the `locations` table
    3. If partial/insufficient -> run_scraper() (filters results.json by
       query, scrapes + extracts + geocodes new threads, writes a fresh
       discovered_locations.geojson)
    4. Sync that geojson into the db, re-check coverage, return that
    5. Always return a `log` list so your UI can show *why* the agent
       did or didn't scrape.
"""

from pathlib import Path
from typing import List

from backend.models import ParsedQuery, CoverageResult
from backend.coverage import check_coverage
from backend.scraper_interface import run_scraper

# Adjust to your db loader script's actual filename
from retrieval.db_data.geojson_into_db import load_geojson_into_db

GEOJSON_PATH = Path(__file__).resolve().parent.parent / "retrieval" / "data_locations" / "discovered_locations.geojson"


def parse_query(raw_query: str) -> ParsedQuery:
    """
    Stand-in for real query parsing. Swap for an LLM call or proper NER
    once you want the agent to handle messier natural-language input
    (e.g. pulling out region + place_type instead of dumping everything
    into keywords).
    """
    return ParsedQuery(raw_query=raw_query, keywords=raw_query.lower().split())


def handle_query(raw_query: str, geojson_dir=None) -> dict:
    log: List[str] = []

    query = parse_query(raw_query)
    log.append(f"Parsed query: {query}")

    coverage: CoverageResult = check_coverage(query)
    log.append(f"Coverage check: {coverage.verdict} — {coverage.reason}")

    if coverage.verdict == "sufficient":
        return {"locations": coverage.matches, "source": "cache", "log": log}

    log.append("Coverage insufficient/partial — scraping relevant threads...")
    new_locations = run_scraper(query)
    log.append(f"Pipeline added/updated {len(new_locations)} location records.")

    log.append("Syncing fresh geojson into the lookup db...")
    load_geojson_into_db(str(GEOJSON_PATH))

    refreshed: CoverageResult = check_coverage(query)
    log.append(f"Post-scrape coverage: {refreshed.match_count} matches.")

    return {
        "locations": refreshed.matches,
        "source": "cache+scrape" if coverage.matches else "scrape",
        "log": log,
    }


if __name__ == "__main__":
    result = handle_query("abandoned hospital Malmö")
    for line in result["log"]:
        print(line)
    print(f"\n{len(result['locations'])} locations returned from: {result['source']}")
