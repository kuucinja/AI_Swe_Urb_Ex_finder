from dataclasses import dataclass, field
from typing import Optional, List, Tuple


@dataclass
class ParsedQuery:
    raw_query: str
    region: Optional[str] = None          # e.g. "Malmö", "Stockholm"
    place_type: Optional[str] = None      # e.g. "hospital", "factory", "bunker"
    keywords: List[str] = field(default_factory=list)
    bbox: Optional[Tuple[float, float, float, float]] = None  # (min_lon, min_lat, max_lon, max_lat)


@dataclass
class CoverageResult:
    match_count: int
    matches: List[dict]           # raw geojson feature dicts
    avg_confidence: float         # 0.0 - 1.0, derived from your heuristics scoring
    newest_match_age_days: Optional[int]
    verdict: str                  # "sufficient" | "partial" | "insufficient"
    reason: str
