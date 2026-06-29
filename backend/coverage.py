"""
Coverage check backed by the SQLite lookup database instead of reading
geojson files directly. Given a parsed query, decides whether existing
rows in `locations` already answer it well enough, or whether a fresh
scrape is needed.

Inferred schema (from your INSERT statements - confirm against the
actual CREATE TABLE in db.py and adjust column names if they differ):

    locations(entity, lat, lon, post_id, thread_url, confidence)
    posts(post_id, thread_url, username, time_raw, text)

Known gap: there's no timestamp column yet, so freshness can't be
checked - every match is treated as "age unknown" rather than stale.
Add a `scraped_at` column (default CURRENT_TIMESTAMP) to `locations`
once you want real staleness checks back.
"""

from typing import List

from retrieval.db_data.db import get_conn
from backend.models import ParsedQuery, CoverageResult

MIN_MATCHES_FOR_SUFFICIENT = 3
MIN_CONFIDENCE_FOR_SUFFICIENT = 0.6


def _query_locations(query: ParsedQuery) -> List[dict]:
    conn = get_conn()
    cur = conn.cursor()

    terms = query.keywords or []
    columns = ["entity", "lat", "lon", "post_id", "thread_url", "confidence"]

    if not terms:
        cur.execute(f"SELECT {', '.join(columns)} FROM locations")
    else:
        # OR-match any keyword against the entity name itself or the
        # text of the post it was extracted from.
        clauses = []
        params: List[str] = []
        for term in terms:
            clauses.append("(l.entity LIKE ? OR p.text LIKE ?)")
            like_term = f"%{term}%"
            params.extend([like_term, like_term])

        sql = f"""
            SELECT DISTINCT {', '.join(f'l.{c}' for c in columns)}
            FROM locations l
            LEFT JOIN posts p ON p.post_id = l.post_id
            WHERE {" OR ".join(clauses)}
        """
        cur.execute(sql, params)

    rows = cur.fetchall()
    conn.close()
    return [dict(zip(columns, row)) for row in rows]


def check_coverage(query: ParsedQuery) -> CoverageResult:
    rows = _query_locations(query)

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
