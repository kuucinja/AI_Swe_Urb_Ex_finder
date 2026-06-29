"""
Thin wrapper around your existing flashback scraper script, so the
orchestrator can call it uniformly without caring about its internals.
"""

from typing import List
from models import ParsedQuery
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from retrieval.crawl_agent import run_agent_crawl


def run_scraper(query: ParsedQuery) -> List[dict]:
    """
    TODO: replace this with a call into your actual scraper, e.g.:

        from flashback_scraper import scrape_threads
        return scrape_threads(
            search_term=query.place_type or query.raw_query,
            region=query.region,
        )

    Should return raw scraped thread/comment data, ready to be handed
    to extract_features() in heuristics_interface.py.
    """
    



    raise NotImplementedError("Wire this up to your flashback scraper script.")
