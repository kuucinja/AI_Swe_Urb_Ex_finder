"""
Wraps the real pipeline (urbex_location_agent.py) so the orchestrator can
call it uniformly.

Per-query thread *scraping* no longer lives here - that's the perpetual
background crawler's job now (see retrieval/crawler.py), which isn't
scoped to any single query. What's left is the query-scoped, immediate
*reprocess* path: filtering already-scraped threads down to ones
relevant to a query, then re-analyzing whichever of their posts haven't
been checked for locations yet.
"""

from typing import List

import database.repository as repo
from backend.models import ParsedQuery
from retrieval.urbex_location_agent import reprocess_posts


def candidate_threads(query: ParsedQuery, max_threads: int = 25) -> List[dict]:
    """Urbex-positive threads that look relevant to THIS query (title
    match), instead of blindly taking the first N (which is all
    load_initial_posts does today)."""
    terms = [t.lower() for t in (query.keywords or [])]

    matches: List[dict] = []
    for row in repo.get_urbex_threads():
        title = (row.get("title") or "").lower()
        if not terms or any(term in title for term in terms):
            matches.append(row)
        if len(matches) >= max_threads:
            break
    return matches


def reprocessing_candidates(query: ParsedQuery, max_threads: int = 25) -> List[str]:
    """Candidate thread URLs that have posts scraped, but at least one of
    those posts hasn't been run through the location agent yet - the
    cheap reprocess-without-scraping path."""
    visited = repo.get_visited_keys()
    urls: List[str] = []
    for row in candidate_threads(query, max_threads):
        posts = repo.get_posts_for_thread(row["url"])
        if not posts:
            continue
        if any(f"post:{post['text']}" not in visited for post in posts if post.get("text")):
            urls.append(row["url"])
    return urls


def run_reprocess(query: ParsedQuery) -> List[dict]:
    """
    Re-analyze posts already scraped for threads relevant to `query`,
    without hitting flashback.org again.
    """
    urls = reprocessing_candidates(query)
    if not urls:
        return []

    return reprocess_posts(urls, threshold=0.45)