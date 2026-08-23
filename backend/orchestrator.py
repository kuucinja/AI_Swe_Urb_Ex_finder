"""
The first real "tool" in the agent: decide how to answer an incoming
query about UrbEx locations.

Flow:
    1. Parse the query (rough for now)
    2. check_coverage() against the `locations` table
    3. Gather signals (cached matches, already-scraped-but-unanalyzed
       posts in relevant threads, whether the background crawler is
       already running) and let the LLM choose a strategy: "cache" (just
       show what's already found), "reprocess" (re-analyze
       already-scraped posts relevant to this query right now - cheap,
       no network scrape), or "ensure_crawling" (make sure the perpetual
       background crawler is running - see retrieval/crawler.py - which
       works through the whole forum over time, not scoped to this
       query).
    4. Execute that strategy, re-check coverage, return it - along with
       the crawler's current status, always, regardless of which action
       was taken, so the UI/chat reply can report it.
    5. Always return a `log` list so the UI can show *why* the agent
       did what it did.
"""

from typing import List

import retrieval.crawler as crawler
import backend.dedup as dedup
from backend.models import ParsedQuery, CoverageResult
from backend.coverage import check_coverage
from backend.scraper_interface import run_reprocess, reprocessing_candidates
from backend.call_llm import call_llm, call_llm_json, trim_to_limit, summarize, count_tokens

def parse_query(raw_query: str) -> ParsedQuery:
    """
    Stand-in for real query parsing. Swap for an LLM call or proper NER
    once you want the agent to handle messier natural-language input
    (e.g. pulling out region + place_type instead of dumping everything
    into keywords).
    """
    messages = [
    {
        "role": "system",
        "content": """
You are a STRICT JSON generator.

Return ONLY valid JSON with EXACTLY these keys:

{
  "raw_query": string,
  "keywords": list of strings
}

Rules:
- DO NOT use "text"
- DO NOT use "message"
- DO NOT use "query"
- ONLY use "raw_query" and "keywords"
- Output ONLY JSON (no explanations)
"""
    },
    {
        "role": "user",
        "content": raw_query
    }
]

    data = call_llm_json(messages)

    return ParsedQuery(**data)

    # return ParsedQuery(raw_query=raw_query, keywords=raw_query.lower().split())


def _explicit_action_hint(raw_query: str) -> str | None:
    """Cheap, deterministic check for the user directly asking for a
    specific strategy ("scrape more", "search again", "look deeper").
    decide_strategy()'s LLM call gets the raw query text either way, but
    a soft mention buried in a prompt full of coverage statistics is easy
    for the model to out-weigh with its own sufficiency judgment - which
    is exactly what happened: a user explicitly asking to scrape got
    "cache" back because 12 matches at 0.60 confidence looked sufficient
    by the numbers. This hint is injected as an unambiguous directive
    instead, so an explicit request can't be quietly out-voted."""
    lowered = raw_query.lower()
    crawl_words = ("scrape", "crawl", "fetch new", "new threads", "more web", "web scraping")
    reprocess_words = ("reprocess", "re-analyze", "reanalyze", "re-analyse", "look again", "re-check", "recheck")
    dedup_words = ("duplicate", "duplicates", "dedupe", "dedup", "merge")
    if any(w in lowered for w in crawl_words):
        return "ensure_crawling"
    if any(w in lowered for w in reprocess_words):
        return "reprocess"
    if any(w in lowered for w in dedup_words):
        return "deduplicate"
    return None


def decide_strategy(query: ParsedQuery, coverage: CoverageResult, signals: dict) -> dict:
    """LLM call: given cached-match count/confidence, the count of
    relevant threads with already-scraped-but-unanalyzed posts, and
    whether the background crawler is already running, choose one of
    'cache' | 'reprocess' | 'ensure_crawling' | 'deduplicate' and explain
    why."""
    explicit_action = _explicit_action_hint(query.raw_query)

    messages = [
        {
            "role": "system",
            "content": """
You are the decision step of an urban-exploration (urbex) location-finding
agent. For a user's query, choose exactly ONE strategy:

- "cache": return the locations already identified and stored. Use this
  when there are already good matches, or when none of the other options
  have anything to offer right now.
- "reprocess": re-analyze posts that were already scraped from relevant
  forum threads but haven't been checked for locations yet. Fast,
  immediate, free of network scraping, and scoped to this query - prefer
  it over "ensure_crawling" whenever it has signal.
- "ensure_crawling": make sure the perpetual background crawler is
  running. It is NOT scoped to this query - it works through the entire
  forum continuously, in the background, for as long as the backend runs,
  and never blocks this response. Choose this when the cache and
  reprocess options don't have enough to offer and there's more of the
  forum left to explore in general.
- "deduplicate": check the cached matches for this query for duplicate
  entries (the same real place saved multiple times under slightly
  different names) and merge the confident ones. Choose this when the
  user explicitly asks about duplicates/merging, or when the cached
  matches you're seeing clearly look like repeats of the same place.

If the user's message contains an EXPLICIT DIRECTIVE naming one of these
actions (e.g. "scrape more", "crawl", "search again", "reprocess",
"merge duplicates"), you MUST honor it and choose that action - a human
explicitly asking for something overrides your own sufficiency judgment
about the cache, even if the numbers look fine.

Return ONLY strict JSON:
{"action": "cache"|"reprocess"|"ensure_crawling"|"deduplicate", "reasoning": string}
"""
        },
        {
            "role": "user",
            "content": (
                f"Query: {query.raw_query}\n"
                f"Keywords: {query.keywords}\n"
                + (
                    f"EXPLICIT DIRECTIVE DETECTED: the user is directly asking for '{explicit_action}'. Honor it.\n"
                    if explicit_action else ""
                )
                + f"Already-cached matches: {coverage.match_count} "
                f"(avg confidence {coverage.avg_confidence:.2f}, verdict: {coverage.verdict})\n"
                f"Relevant threads with unanalyzed posts (reprocess candidates): {signals['unanalyzed']}\n"
                f"Background crawler currently running: {signals['crawler_running']}\n"
            )
        }
    ]

    try:
        result = call_llm_json(messages)
        action = result.get("action")
        if action not in {"cache", "reprocess", "ensure_crawling", "deduplicate"}:
            raise ValueError(f"invalid action: {action!r}")
        return {"action": action, "reasoning": result.get("reasoning") or "(no reasoning given)"}
    except Exception as exc:
        # Defensive fallback for an external-service failure (bad/missing
        # JSON) - not a second decision mechanism, just keeps the agent
        # functional if the LLM call fails. Still honors an explicit
        # directive.
        if explicit_action in {"ensure_crawling", "deduplicate"}:
            fallback = explicit_action
        elif explicit_action == "reprocess" and signals["unanalyzed"] > 0:
            fallback = "reprocess"
        elif signals["unanalyzed"] > 0:
            fallback = "reprocess"
        else:
            fallback = "cache"
        return {"action": fallback, "reasoning": f"LLM decision failed ({exc}); defaulted to {fallback}."}


def handle_query(raw_query: str) -> dict:
    log: List[str] = []

    query = parse_query(raw_query)
    log.append(f"Parsed query: {query}")

    coverage: CoverageResult = check_coverage(query)
    log.append(f"Coverage check: {coverage.verdict} — {coverage.reason}")

    crawler_status_before = crawler.get_status()
    signals = {
        "unanalyzed": len(reprocessing_candidates(query)),
        "crawler_running": crawler_status_before["running"],
    }
    decision = decide_strategy(query, coverage, signals)
    log.append(f"Agent decision: {decision['action']} — {decision['reasoning']}")

    if decision["action"] == "reprocess":
        new_locations = run_reprocess(query)
        log.append(f"Reprocessed already-scraped posts, added/updated {len(new_locations)} location records.")
        coverage = check_coverage(query)
        log.append(f"Post-reprocess coverage: {coverage.match_count} matches.")
    elif decision["action"] == "ensure_crawling":
        if crawler_status_before["running"]:
            log.append("Crawler already running in the background.")
        else:
            crawler.start_crawler()
            log.append("Started the background crawler - it works through the whole forum over time.")
    elif decision["action"] == "deduplicate":
        merge_summaries = dedup.deduplicate_locations(coverage.matches)
        if merge_summaries:
            for merge in merge_summaries:
                merged_names = ", ".join(f"'{name}'" for name in merge["merged_entities"])
                log.append(
                    f"Merged {merge['merged_count']} duplicate(s) into '{merge['canonical_entity']}': {merged_names}"
                )
            coverage = check_coverage(query)
            log.append(f"Post-merge coverage: {coverage.match_count} matches.")
        else:
            log.append("Checked for duplicates among the cached matches - none confident enough to merge automatically.")

    crawler_status = crawler.get_status()
    log.append(
        f"Crawler status: {'running' if crawler_status['running'] else 'idle'} "
        f"({crawler_status['threads_scraped']}/{crawler_status['threads_known']} urbex threads scraped so far)."
    )

    return {
        "locations": coverage.matches,
        "source": f"cache+{decision['action']}" if coverage.matches and decision["action"] != "cache" else decision["action"],
        "log": log,
        "crawler": crawler_status,
    }


if __name__ == "__main__":
    result = handle_query("abandoned hospital Malmö")
    for line in result["log"]:
        print(line)
    print(f"\n{len(result['locations'])} locations returned from: {result['source']}")
