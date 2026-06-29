"""
The first real "tool" in the agent: decide whether an incoming query
can be answered from existing data, or whether it needs a fresh scrape.

Flow:
    1. Parse the query (rough for now)
    2. check_coverage() against existing geojson
    3. If partial/insufficient -> scrape -> run heuristics -> merge
    4. Return the final feature set + a decision log, so your UI can
       show *why* the agent did or didn't scrape.
"""

from typing import List
from models import ParsedQuery, CoverageResult
from coverage import check_coverage
from scraper_interface import run_scraper
from heuristics_interface import extract_features
# from central_agent import call_llm, memory, trim_to_limit

def parse_query(raw_query: str) -> ParsedQuery:
    """
    Stand-in for real query parsing. Swap for an LLM call or proper NER
    once you want the agent to handle messier natural-language input
    (e.g. pulling out region + place_type instead of dumping everything
    into keywords).
    """
    return ParsedQuery(raw_query=raw_query, keywords=raw_query.lower().split())


def handle_query(raw_query: str, geojson_dir: str) -> dict:
    log: List[str] = []

    query = parse_query(raw_query)
    log.append(f"Parsed query: {query}")

    coverage: CoverageResult = check_coverage(query, geojson_dir)
    log.append(f"Coverage check: {coverage.verdict} — {coverage.reason}")

    if coverage.verdict == "sufficient":
        return {"features": coverage.matches, "source": "cache", "log": log}

    log.append("Coverage insufficient/partial — triggering scraper...")
    raw_threads = run_scraper(query)
    log.append(f"Scraped {len(raw_threads)} threads.")

    new_features = extract_features(raw_threads, query)
    log.append(f"Heuristics produced {len(new_features)} candidate features.")

    merged = coverage.matches + new_features

    return {
        "features": merged,
        "source": "cache+scrape" if coverage.matches else "scrape",
        "log": log,
    }


if __name__ == "__main__":
    result = handle_query("abandoned hospital Malmö", geojson_dir="./data/geojson")
    for line in result["log"]:
        print(line)
    print(f"\n{len(result['features'])} features returned from: {result['source']}")
