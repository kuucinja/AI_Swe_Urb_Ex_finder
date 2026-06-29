"""
Checks whether existing scraped/processed data already covers a query,
before deciding whether to invoke the scraper.

Wire this up to your actual data sources:
  - the geojson files your heuristics script produces
  - (optionally) raw scraped comments, for a keyword fallback

Tune the thresholds at the top once you see how it behaves on real data.
"""

import json
import glob
import os
from datetime import datetime, timezone
from typing import List

from models import ParsedQuery, CoverageResult


# --- thresholds, tune these as you go ---
MIN_MATCHES_FOR_SUFFICIENT = 3
MIN_CONFIDENCE_FOR_SUFFICIENT = 0.6
STALE_AFTER_DAYS = 180


def load_geojson_features(geojson_dir: str) -> List[dict]:
    """Load all features from every .geojson file in a directory."""
    features = []
    for path in glob.glob(os.path.join(geojson_dir, "*.geojson")):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            features.extend(data.get("features", []))
    return features


def _matches_query(feature: dict, query: ParsedQuery) -> bool:
    """
    Cheap keyword/region filter to start. Swap in real geo (shapely bbox
    check against query.bbox) and/or semantic matching on thread text
    once this is proven out.
    """
    props = feature.get("properties", {})
    haystack = " ".join(
        str(props.get(k, "")) for k in ("title", "description", "region", "tags")
    ).lower()

    if query.region and query.region.lower() not in haystack:
        return False
    if query.place_type and query.place_type.lower() not in haystack:
        return False
    if query.keywords and not any(kw.lower() in haystack for kw in query.keywords):
        return False
    return True


def _feature_confidence(feature: dict) -> float:
    """
    Pull the confidence score your heuristics script assigns, if any.
    Defaults to a conservative 0.3 when missing — given the heuristics
    are described as "mediocre", trust is probably the real bottleneck,
    so it's worth adding a confidence field to your geojson properties
    if you haven't already.
    """
    return float(feature.get("properties", {}).get("confidence", 0.3))


def _feature_age_days(feature: dict) -> int:
    scraped_at = feature.get("properties", {}).get("scraped_at")
    if not scraped_at:
        return STALE_AFTER_DAYS + 1  # unknown age treated as stale
    ts = datetime.fromisoformat(scraped_at.replace("Z", "+00:00"))
    return (datetime.now(timezone.utc) - ts).days


def check_coverage(query: ParsedQuery, geojson_dir: str) -> CoverageResult:
    features = load_geojson_features(geojson_dir)
    matches = [f for f in features if _matches_query(f, query)]

    if not matches:
        return CoverageResult(
            match_count=0,
            matches=[],
            avg_confidence=0.0,
            newest_match_age_days=None,
            verdict="insufficient",
            reason="No existing locations match this query.",
        )

    confidences = [_feature_confidence(f) for f in matches]
    ages = [_feature_age_days(f) for f in matches]
    avg_confidence = sum(confidences) / len(confidences)
    newest_age = min(ages)

    if (
        len(matches) >= MIN_MATCHES_FOR_SUFFICIENT
        and avg_confidence >= MIN_CONFIDENCE_FOR_SUFFICIENT
        and newest_age <= STALE_AFTER_DAYS
    ):
        verdict = "sufficient"
        reason = (
            f"{len(matches)} matches, avg confidence {avg_confidence:.2f}, "
            f"freshest {newest_age}d old."
        )
    else:
        verdict = "partial"
        reason = (
            f"{len(matches)} matches found but confidence ({avg_confidence:.2f}) "
            f"or freshness ({newest_age}d) is below threshold."
        )

    return CoverageResult(
        match_count=len(matches),
        matches=matches,
        avg_confidence=avg_confidence,
        newest_match_age_days=newest_age,
        verdict=verdict,
        reason=reason,
    )
