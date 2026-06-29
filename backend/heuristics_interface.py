"""
Wrapper around your existing heuristics script that turns raw scraped
comments/threads into geojson features.
"""

from typing import List
from models import ParsedQuery


def extract_features(raw_threads: List[dict], query: ParsedQuery) -> List[dict]:
    """
    TODO: replace this with a call into your actual heuristics script, e.g.:

        from geo_heuristics import extract_locations
        return extract_locations(raw_threads)

    Should return a list of geojson Feature dicts. If your heuristics
    don't currently attach a "confidence" property per feature, adding
    one (even a rough 0-1 estimate) makes check_coverage() far more
    useful, since right now everything without one defaults to 0.3.
    """
    raise NotImplementedError("Wire this up to your heuristics script.")
