"""
Duplicate-location detection and merging.

Runs on-demand, scoped to whatever locations are already relevant to the
current query (e.g. coverage.matches) - not a global database sweep.
Only merges when BOTH signals agree: near-identical coordinates AND
similar names. Coordinate closeness alone isn't safe (two genuinely
different, badly-geocoded places can land on the same fallback point;
see the "Klotterhuset" Uppsala-centroid case), and name closeness alone
isn't safe either (same name, wildly different real coordinates usually
means a bad geocode, not a duplicate - that's a data-quality problem for
retrieval/cleanup_locations.py, not this).

Thresholds were calibrated against a real cluster: four independently
scraped "Kymlinge station" mentions that all geocoded to the exact same
point (0m apart, name similarity 0.60-1.00), versus other same-named
entries that were geocoded hundreds of km apart (bad geocodes, not
duplicates).
"""

from __future__ import annotations

import json
import math
from difflib import SequenceMatcher
from typing import Any

import database.repository as repo

DISTANCE_THRESHOLD_METERS = 150
NAME_SIMILARITY_THRESHOLD = 0.5


def _distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, (a or "").lower(), (b or "").lower()).ratio()


def find_duplicate_clusters(locations: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group `locations` into clusters that are very likely the same real
    place. Union-find over pairs passing both thresholds; singletons
    (no match) are dropped."""
    n = len(locations)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i in range(n):
        for j in range(i + 1, n):
            a, b = locations[i], locations[j]
            if a.get("lat") is None or b.get("lat") is None:
                continue
            if _distance_meters(a["lat"], a["lon"], b["lat"], b["lon"]) > DISTANCE_THRESHOLD_METERS:
                continue
            if _name_similarity(a.get("entity"), b.get("entity")) < NAME_SIMILARITY_THRESHOLD:
                continue
            union(i, j)

    groups: dict[int, list[dict[str, Any]]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(locations[i])

    return [group for group in groups.values() if len(group) > 1]


def merge_cluster(cluster: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge a confirmed-duplicate cluster into one canonical row.
    Prefers an already-verified row as canonical (a human confirmed it -
    never delete that in favor of an unverified one); otherwise the
    highest-confidence row. Evidence from every row is unioned into the
    canonical row (deduped the same way add_to_map does), and the other
    rows are deleted."""
    verified_rows = [r for r in cluster if r.get("verified")]
    canonical = verified_rows[0] if verified_rows else max(cluster, key=lambda r: r.get("confidence") or 0)
    others = [r for r in cluster if r["id"] != canonical["id"]]

    merged_evidence = list(canonical.get("evidence") or [])
    known_keys = {
        (entry.get("post_id"), entry.get("source"), entry.get("comment"))
        for entry in merged_evidence
    }
    for row in others:
        for entry in (row.get("evidence") or []):
            key = (entry.get("post_id"), entry.get("source"), entry.get("comment"))
            if key not in known_keys:
                merged_evidence.append(entry)
                known_keys.add(key)

    best_confidence = max((r.get("confidence") or 0) for r in cluster)

    repo.update_location(
        canonical["id"],
        confidence=best_confidence,
        evidence=json.dumps(merged_evidence),
    )
    for row in others:
        repo.delete_location(row["id"])

    return {
        "canonical_id": canonical["id"],
        "canonical_entity": canonical["entity"],
        "merged_entities": [r["entity"] for r in others],
        "merged_count": len(others),
    }


def deduplicate_locations(locations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find and auto-merge high-confidence duplicate clusters among
    `locations`. Returns one summary dict per merge performed, for the
    caller to report back to the user - merges are never silent."""
    return [merge_cluster(cluster) for cluster in find_duplicate_clusters(locations)]