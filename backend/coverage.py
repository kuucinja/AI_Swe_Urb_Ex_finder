"""
Coverage check backed by Postgres (database/repository.py) instead of
the old SQLite lookup database. Given a parsed query, decides whether
existing rows in `locations` already answer it well enough, or whether
a fresh scrape is needed.

Known gap: the `locations` table has no timestamp column yet, so
freshness can't be checked - every match is treated as "age unknown"
rather than stale. Add a `scraped_at` column (default NOW()) once you
want real staleness checks back (see database/schema.sql).
"""

from typing import List

import database.repository as repo
from backend.models import ParsedQuery, CoverageResult

MIN_MATCHES_FOR_SUFFICIENT = 3
MIN_CONFIDENCE_FOR_SUFFICIENT = 0.6


def check_coverage(query: ParsedQuery) -> CoverageResult:
    rows: List[dict] = repo.search_locations_multi(query.keywords or [])

    if not rows:
        return CoverageResult(
            match_count=0,
            matches=[],
            avg_confidence=0.0,
            newest_match_age_days=None,
            verdict="insufficient",
            reason="No existing locations match this query.",
        )

    confidences = [float(r.get("confidence") or 0.0) for r in rows]
    avg_confidence = sum(confidences) / len(confidences)

    if len(rows) >= MIN_MATCHES_FOR_SUFFICIENT and avg_confidence >= MIN_CONFIDENCE_FOR_SUFFICIENT:
        verdict = "sufficient"
        reason = (
            f"{len(rows)} matches, avg confidence {avg_confidence:.2f} "
            f"(freshness unknown - no scraped_at column yet)."
        )
    else:
        verdict = "partial"
        reason = f"{len(rows)} matches found but confidence ({avg_confidence:.2f}) is below threshold."

    return CoverageResult(
        match_count=len(rows),
        matches=rows,
        avg_confidence=avg_confidence,
        newest_match_age_days=None,
        verdict=verdict,
        reason=reason,
    )