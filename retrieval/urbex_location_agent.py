"""
Second-stage UrbEx location agent.

This module builds on the existing Flashback HTML/thread extraction code:

1. Read candidate urbex threads from data/results.json, or accept explicit URLs.
2. Scrape/parse posts with thread_extraction.py.
3. Classify and score posts for location usefulness.
4. Extract named places/facilities from relevant posts.
5. Geocode candidates and write JSON + GeoJSON map outputs.

The agent stores checkpoints in data/location_agent_state.json so it can resume
without revisiting every thread.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from dataclasses import dataclass, field
from hashlib import sha1
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from retrieval.thread_extraction import BASE, build_url, fetch, get_total_pages, parse_posts


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_DIR = PROJECT_DIR / "data_locations"
STATE_FILE = DATA_DIR / "location_agent_state.json"

DEFAULT_RESULTS_FILE = DATA_DIR / "results.json"
DEFAULT_THRESHOLD = 0.45
DEFAULT_MAX_ITEMS = 300
DEFAULT_MAX_THREADS = 25
REQUEST_DELAY_SECONDS = 1.0

URBEX_TERMS = {
    "abandoned",
    "övergiven",
    "övergivet",
    "nedlagd",
    "ruin",
    "ruiner",
    "urbex",
    "urban exploration",
    "fabrik",
    "factory",
    "militär",
    "bunker",
    "sjukhus",
    "hospital",
    "skola",
    "school",
    "gruva",
    "mine",
    "tunnel",
    "industri",
    "bruk",
    "pappersbruk",
    "kraftverk",
}

LOCATION_HINT_TERMS = {
    "i ",
    "vid ",
    "nära",
    "utanför",
    "kommun",
    "län",
    "vägen",
    "gatan",
    "station",
    "fabrik",
    "bruk",
    "militäranläggning",
    "sjukhus",
}

STOP_ENTITIES = {
    "Citat",
    "Ursprungligen",
    "Postat",
    "Hej",
    "Tänkte",
    "Mina",
    "Som",
    "Berätta",
    "Finns",
    "Lista",
    "Fabriksbyggnaden",
    "Västernorrlänningar",
    "Flashback",
    "Urban Exploration",
}


@dataclass
class QueueItem:
    kind: str
    value: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.value}"


def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_url(url: str) -> str:
    return urljoin(BASE, url)


def thread_id_from_url(url: str) -> str | None:
    match = re.search(r"/t(\d+)", url)
    return match.group(1) if match else None


def scrape_thread(url: str, max_pages: int | None = None) -> list[dict[str, Any]]:
    """Scrape a Flashback thread URL using the existing post parser."""
    thread_id = thread_id_from_url(url)
    if not thread_id:
        return []

    first_html = fetch(build_url(thread_id, 1))
    total_pages = get_total_pages(first_html)
    if max_pages is not None:
        total_pages = min(total_pages, max_pages)

    posts: list[dict[str, Any]] = []
    for page in range(1, total_pages + 1):
        page_url = build_url(thread_id, page)
        html = first_html if page == 1 else fetch(page_url)
        page_posts = parse_posts(html)
        for post in page_posts:
            post["source_url"] = page_url
            post["thread_url"] = normalize_url(url)
        posts.extend(page_posts)
        time.sleep(REQUEST_DELAY_SECONDS)
    return posts


def get_next_posts(source: str) -> list[QueueItem]:
    """Extract linked Flashback threads from post/thread HTML or plain text."""
    links = re.findall(r"https?://(?:www\.)?flashback\.org/t\d+(?:p\d+)?", source)
    links.extend(urljoin(BASE, href) for href in re.findall(r'href=["\'](/t\d+(?:p\d+)?)["\']', source))

    items = []
    for link in sorted(set(links)):
        items.append(QueueItem(kind="thread", value=normalize_url(link)))
    return items


def classify_urbex(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in URBEX_TERMS)


def score_relevance(item: str | dict[str, Any]) -> float:
    text = item if isinstance(item, str) else item.get("text", "")
    lowered = text.lower()

    score = 0.0
    score += min(sum(1 for term in URBEX_TERMS if term in lowered) * 0.12, 0.48)   ## score for urbex terms = nr of terms * 0.12, capped at 0.48
    score += min(sum(1 for term in LOCATION_HINT_TERMS if term in lowered) * 0.08, 0.32) ## score for location hint terms = nr of terms * 0.08, capped at 0.32

    capitalized = re.findall(r"\b[A-ZÅÄÖ][a-zåäöéèü-]{2,}(?:\s+[A-ZÅÄÖ][a-zåäöéèü-]{2,}){0,3}\b", text)
    score += min(len(capitalized) * 0.04, 0.2) ## score for capitalized candidates = nr of candidates * 0.04, capped at 0.2 - more than 5 capitalized candidates is unlikely to add value

    if "?" in text and len(text) < 140:
        score -= 0.1
    if len(text) > 180:
        score += 0.08

    return max(0.0, min(1.0, round(score, 3)))


def contains_links(text: str) -> bool:
    return "flashback.org/t" in text or "/t" in text


def missing_context(text: str) -> bool:
    has_place = bool(extract_entities(text))
    return classify_urbex(text) and not has_place


def contains_location_mentions(text: str) -> bool:
    return bool(extract_entities(text))


def location_clues(text: str) -> str:
    words = re.findall(r"[A-ZÅÄÖa-zåäöéèü-]{4,}", text)
    clue_words = [w for w in words if w.lower() in URBEX_TERMS or w[:1].isupper()]
    return " ".join(clue_words[:10])


def extract_entities(text: str) -> list[dict[str, Any]]:
    """Heuristic Swedish-place/facility extraction.

    This intentionally stays conservative. LLM-based extraction can be added on
    top later, but this gives the agent a deterministic, resumable core.
    """
    candidates: list[str] = []

    patterns = [
        r"\b(?:i|vid|nära|utanför|kring)\s+([A-ZÅÄÖ][A-Za-zÅÄÖåäöéèü-]{2,}(?:\s+[A-ZÅÄÖ][A-Za-zÅÄÖåäöéèü-]{2,}){0,3})",
        r"\b([A-ZÅÄÖ][A-Za-zÅÄÖåäöéèü-]{2,}(?:s)?\s+(?:fabrik|bruk|pappersbruk|militäranläggning|sjukhus|skola|station|kraftverk|gruva|bunker))\b",
        r"\b([A-ZÅÄÖ][a-zåäöéèü-]{2,}(?:\s+[A-ZÅÄÖ][a-zåäöéèü-]{2,}){0,2})\b",
    ]

    for pattern in patterns:
        candidates.extend(match.group(1).strip(" .,:;!?()[]") for match in re.finditer(pattern, text))

    entities: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in STOP_ENTITIES or len(candidate) < 3:
            continue
        if candidate.lower() in {term.lower() for term in URBEX_TERMS}:
            continue
        key = candidate.casefold()
        if key in seen:
            continue
        seen.add(key)
        entities.append({"name": candidate, "type": "place_or_facility"})
    return entities


def is_geocodable(entity: dict[str, Any]) -> bool:
    name = entity.get("name", "").strip()
    return len(name) >= 3 and not re.search(r"^\d+$", name)


def geocode(entity: dict[str, Any], country_hint: str = "Sweden") -> dict[str, Any] | None:
    query = f"{entity['name']}, {country_hint}"
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 1, "addressdetails": 1}
    headers = {"User-Agent": "IR-agent-location-mapper/0.1"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        print(f"Geocode failed for {query}: {exc}")
        return None

    if not data:
        return None

    top = data[0]
    return {
        "entity": entity["name"],
        "query": query,
        "lat": float(top["lat"]),
        "lon": float(top["lon"]),
        "display_name": top.get("display_name"),
        "osm_type": top.get("osm_type"),
        "osm_id": top.get("osm_id"),
        "geocode_confidence": float(top.get("importance", 0.0) or 0.0),
    }


def search_web(query: str) -> list[dict[str, str]]:
    """Lightweight context search using DuckDuckGo HTML results."""
    if not query:
        return []
    url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {"User-Agent": "IR-agent-location-mapper/0.1"}
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    results = []
    for result in soup.select(".result")[:5]:
        title = result.select_one(".result__title")
        link = result.select_one(".result__a")
        snippet = result.select_one(".result__snippet")
        if title and link:
            results.append(
                {
                    "title": title.get_text(" ", strip=True),
                    "url": link.get("href", ""),
                    "snippet": snippet.get_text(" ", strip=True) if snippet else "",
                }
            )
    return results


def comment_excerpt(text: str, max_chars: int = 450) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def evidence_from_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": metadata.get("source"),
        "thread_url": metadata.get("thread_url"),
        "post_id": metadata.get("post_id"),
        "username": metadata.get("username"),
        "time_raw": metadata.get("time_raw"),
        "confidence": metadata.get("confidence"),
        "comment": metadata.get("comment"),
    }


def add_to_map(location: dict[str, Any], metadata: dict[str, Any], discovered: list[dict[str, Any]]) -> bool:
    location_id = sha1(f"{location['entity']}:{location['lat']}:{location['lon']}".encode("utf-8")).hexdigest()[:12]
    evidence = evidence_from_metadata(metadata)

    for item in discovered:
        if item.get("id") != location_id:
            continue

        item.setdefault("evidence", [])
        evidence_key = (evidence.get("post_id"), evidence.get("source"), evidence.get("comment"))
        known_keys = {
            (entry.get("post_id"), entry.get("source"), entry.get("comment"))
            for entry in item["evidence"]
        }
        if evidence_key not in known_keys:
            item["evidence"].append(evidence)
            item["metadata"] = metadata
            write_outputs(discovered)
        return False

    discovered.append({"id": location_id, **location, "metadata": metadata, "evidence": [evidence]})
    write_outputs(discovered)
    return True


def write_outputs(discovered: list[dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    save_json(OUTPUT_DIR / "discovered_locations.json", discovered)

    features = []
    for item in discovered:
        metadata = item.get("metadata", {})
        properties = {k: v for k, v in item.items() if k not in {"lat", "lon", "metadata"}}
        properties["source"] = metadata.get("source")
        properties["thread_url"] = metadata.get("thread_url")
        properties["post_id"] = metadata.get("post_id")
        properties["username"] = metadata.get("username")
        properties["time_raw"] = metadata.get("time_raw")
        properties["confidence"] = metadata.get("confidence")
        properties["comment"] = metadata.get("comment")
        properties["evidence"] = item.get("evidence", [])
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [item["lon"], item["lat"]]},
                "properties": properties,
            }
        )
    save_json(OUTPUT_DIR / "discovered_locations.geojson", {"type": "FeatureCollection", "features": features})
    with (OUTPUT_DIR / "discovered_locations.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "entity", "lat", "lon", "display_name", "source", "confidence"])
        writer.writeheader()
        for item in discovered:
            writer.writerow(
                {
                    "id": item["id"],
                    "entity": item["entity"],
                    "lat": item["lat"],
                    "lon": item["lon"],
                    "display_name": item.get("display_name"),
                    "source": item.get("metadata", {}).get("source"),
                    "confidence": item.get("metadata", {}).get("confidence"),
                }
            )


def should_expand_search(relevance_score: float, entities: list[dict[str, Any]]) -> bool:
    return relevance_score >= 0.75 and bool(entities)


def budget_exceeded(start_time: float, processed: int, max_items: int, max_minutes: float | None) -> bool:
    if processed >= max_items:
        return True
    if max_minutes is not None and (time.time() - start_time) / 60 >= max_minutes:
        return True
    return False


def convergence_reached(no_new_locations: int, patience: int = 75) -> bool:
    return no_new_locations >= patience


def load_initial_posts(results_file: Path, max_threads: int) -> list[QueueItem]:
    results = load_json(results_file, [])
    items: list[QueueItem] = []
    for row in results:
        if row.get("urbex") and row.get("url"):
            items.append(QueueItem(kind="thread", value=normalize_url(row["url"]), metadata=row))
        if len(items) >= max_threads:
            break
    return items


def load_content(item: QueueItem, max_pages_per_thread: int | None) -> list[QueueItem]:
    if item.kind == "thread":
        posts = scrape_thread(item.value, max_pages=max_pages_per_thread)
        return [
            QueueItem(
                kind="post",
                value=post.get("text") or "",
                metadata={**item.metadata, **post, "source": post.get("source_url") or item.value},
            )
            for post in posts
            if post.get("text")
        ]
    if item.kind == "post":
        return [item]
    if item.kind == "web_search":
        return [
            QueueItem(kind="post", value=f"{r['title']}\n{r['snippet']}", metadata={"source": r["url"]})
            for r in search_web(item.value)
        ]
    return []


def run_location_agent(
    initial_posts: list[QueueItem],
    threshold: float = DEFAULT_THRESHOLD,
    max_items: int = DEFAULT_MAX_ITEMS,
    max_minutes: float | None = None,
    max_pages_per_thread: int | None = 2,
) -> list[dict[str, Any]]:
    state = load_json(STATE_FILE, {"visited": [], "discovered_locations": []})
    visited = set(state.get("visited", []))
    discovered_locations = state.get("discovered_locations", [])

    work_queue = list(reversed(initial_posts))
    processed = 0
    no_new_locations = 0
    start_time = time.time()

    while work_queue:
        item = work_queue.pop()
        if item.key in visited:
            continue
        visited.add(item.key)

        content_items = load_content(item, max_pages_per_thread=max_pages_per_thread)

        for content_item in content_items:
            if content_item.key in visited:
                continue
            visited.add(content_item.key)

            content = content_item.value
            if not classify_urbex(content):
                continue

            relevance_score = score_relevance(content)
            if relevance_score < threshold:
                continue

            actions: list[QueueItem] = []
            if contains_links(content):
                actions.extend(get_next_posts(content))
            if missing_context(content):
                query = location_clues(content)
                if query:
                    actions.append(QueueItem(kind="web_search", value=query))

            entities = extract_entities(content) if contains_location_mentions(content) else []
            found_this_item = 0

            for entity in entities:
                if not is_geocodable(entity):
                    continue
                location = geocode(entity)
                time.sleep(REQUEST_DELAY_SECONDS)
                if not location:
                    continue

                added = add_to_map(
                    location,
                    {
                        "source": content_item.metadata.get("source") or content_item.metadata.get("thread_url"),
                        "thread_url": content_item.metadata.get("thread_url"),
                        "post_id": content_item.metadata.get("post_id"),
                        "username": content_item.metadata.get("username"),
                        "time_raw": content_item.metadata.get("time_raw"),
                        "confidence": relevance_score,
                        "comment": comment_excerpt(content),
                    },
                    discovered_locations,
                )
                if added:
                    found_this_item += 1

            no_new_locations = 0 if found_this_item else no_new_locations + 1

            if should_expand_search(relevance_score, entities):
                work_queue.extend(actions)

            processed += 1
            save_json(
                STATE_FILE,
                {
                    "visited": sorted(visited),
                    "discovered_locations": discovered_locations,
                    "processed": processed,
                    "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                },
            )

            if budget_exceeded(start_time, processed, max_items, max_minutes) or convergence_reached(no_new_locations):
                return discovered_locations

    return discovered_locations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find, validate, and map potential UrbEx locations from forum data.")
    parser.add_argument("--results-file", type=Path, default=DEFAULT_RESULTS_FILE)
    parser.add_argument("--thread-url", action="append", default=[], help="Seed a specific Flashback thread URL.")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--max-items", type=int, default=DEFAULT_MAX_ITEMS)
    parser.add_argument("--max-threads", type=int, default=DEFAULT_MAX_THREADS)
    parser.add_argument("--max-minutes", type=float, default=None)
    parser.add_argument("--max-pages-per-thread", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    DATA_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)

    initial_posts = [QueueItem(kind="thread", value=normalize_url(url)) for url in args.thread_url]
    if not initial_posts:
        initial_posts = load_initial_posts(args.results_file, args.max_threads)

    if not initial_posts:
        raise SystemExit("No initial urbex threads found. Run UrbEx_search.py first or pass --thread-url.")

    discovered = run_location_agent(
        initial_posts=initial_posts,
        threshold=args.threshold,
        max_items=args.max_items,
        max_minutes=args.max_minutes,
        max_pages_per_thread=args.max_pages_per_thread,
    )
    print(f"Discovered locations: {len(discovered)}")
    print(f"Wrote outputs to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
