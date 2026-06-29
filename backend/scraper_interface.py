"""
Wraps the real pipeline (location_agent.py) so the orchestrator can call
it uniformly.

This replaces what used to be two separate stubs (run_scraper +
extract_features) with one, because in location_agent.py scraping,
relevance scoring, entity extraction, and geocoding are all fused
together inside run_location_agent() - there's no clean seam to split
them at without restructuring that script.

The one piece location_agent.py doesn't have: turning a free-text query
into a set of thread URLs to scrape. It only consumes threads that are
already in results.json (flagged urbex=True by some earlier search
script) or passed explicitly via --thread-url. So this wrapper's job is
to filter results.json down to rows relevant to the query, then hand
those URLs to run_location_agent.
"""

from pathlib import Path
from typing import List

from backend.models import ParsedQuery

# Adjust this import to match the actual filename of your script
# (the one with run_location_agent / QueueItem / etc in it).
from retrieval.urbex_location_agent import (
    QueueItem,
    normalize_url,
    run_location_agent,
    load_json,
    DEFAULT_RESULTS_FILE,
)


def _candidate_thread_urls(
    query: ParsedQuery,
    results_file: Path = DEFAULT_RESULTS_FILE,
    max_threads: int = 25,
) -> List[str]:
    """
    Filter the curated results.json down to threads that look relevant
    to THIS query, instead of blindly taking the first N urbex-flagged
    rows (which is all load_initial_posts does today).

    NOTE: title/snippet/text below are a guess at your results.json
    schema based on what's referenced elsewhere in location_agent.py -
    confirm/correct the field names against an actual row.
    """
    rows = load_json(results_file, [])
    terms = [t.lower() for t in (query.keywords or [])]

    matches: List[str] = []
    for row in rows:
        if not (row.get("urbex") and row.get("url")):
            continue
        haystack = " ".join(str(row.get(k, "")) for k in ("title", "snippet", "text")).lower()
        if not terms or any(term in haystack for term in terms):
            matches.append(row["url"])
        if len(matches) >= max_threads:
            break
    return matches


def run_scraper(query: ParsedQuery, results_file: Path = DEFAULT_RESULTS_FILE) -> List[dict]:
    """
    Find threads relevant to `query`, then scrape + score + extract +
    geocode them via the real pipeline. The pipeline writes its results
    to disk itself (discovered_locations.json/.geojson/.csv) as a side
    effect - the orchestrator re-reads that file afterward rather than
    trying to use this return value directly, since run_location_agent
    returns flat location dicts, not GeoJSON Feature dicts.
    """
    urls = _candidate_thread_urls(query, results_file)
    if not urls:
        return []

    items = [QueueItem(kind="thread", value=normalize_url(u)) for u in urls]
    return run_location_agent(items, threshold=0.45, max_items=100)
