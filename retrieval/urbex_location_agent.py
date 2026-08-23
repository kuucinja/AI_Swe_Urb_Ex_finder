"""
Second-stage UrbEx location agent.

This module builds on the existing Flashback HTML/thread extraction code:

1. Read candidate urbex threads from the `threads` table (urbex = TRUE,
   populated by UrbEx_search.py), or accept explicit URLs.
2. Scrape/parse posts with thread_extraction.py.
3. Classify and score posts for location usefulness.
4. Extract named places/facilities from relevant posts.
5. Geocode candidates, persist them to Postgres, and write JSON + GeoJSON
   map outputs.

The agent checkpoints progress in the `location_agent_visited` table
(via database/repository.py) so it can resume without revisiting the
same thread/post/search twice.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import dataclass, field
from hashlib import sha1
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from retrieval.thread_extraction import BASE, build_url, fetch, get_total_pages, parse_posts

import database.repository as repo
from backend.call_llm import call_llm_json

# Windows consoles/redirected-output default to a codepage (e.g. cp1251)
# that can't encode Swedish characters (ö/ä/å) in scraped text - without
# this, print() crashes mid-run the moment it hits one.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)


PROJECT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_DIR / "data_locations"

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

@dataclass
class QueueItem:
    kind: str
    value: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.value}"


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
        repo.insert_posts(page_posts)
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


def location_clues(text: str) -> str:
    words = re.findall(r"[A-ZÅÄÖa-zåäöéèü-]{4,}", text)
    clue_words = [w for w in words if w.lower() in URBEX_TERMS or w[:1].isupper()]
    return " ".join(clue_words[:10])


def identify_locations(post_text: str) -> list[dict[str, Any]]:
    """Ask the LLM to find every real-world place-related signal in this
    forum post - not just clearly named specific sites, but also vaguer
    or approximate references, each tagged with a confidence score. This
    tool is a helper for a human annotator, not a final filter: even a
    low-confidence clue (a real town used only as a proximity reference,
    with the actual site left unnamed) is worth surfacing, since a human
    can act on it - dig into the thread further, search elsewhere, or
    just notice a clue the model under-weighted. Only truly place-free
    text (pronouns, unrelated chat, generic words) yields nothing.

    Replaces the old regex-based extract_entities(), which had no way to
    tell a real place name from an ordinary capitalized word (Swedish,
    like English, capitalizes the first word of a sentence, and the old
    catch-all pattern matched any of them)."""
    messages = [
        {
            "role": "system",
            "content": """
You are analyzing a post from a Swedish urban-exploration (urbex) forum
(Flashback). Posts are informal, sometimes Swedish, sometimes English, and
often ambiguous.

Your job: identify every real-world place-related signal in this post that
could help a human annotator narrow down where an urbex site is - from a
precisely named building/ruin/factory/bunker/hospital/mine, down to a real
town or area mentioned only as a proximity reference for an unnamed site.
Report what you find, however uncertain, and let your confidence score
carry that uncertainty - do not silently drop something just because it's
vague. The only posts that yield nothing are ones with no place-related
signal at all: pure chat, pronouns, gear talk, or a word that's merely
capitalized because it starts a sentence (never invent a place that isn't
actually referenced in the text).

For each signal found, return:
- "name": a clean, human-readable name built from actual proper
  nouns/place references in the text (never a generic word or pronoun).
- "geocode_query": a search string suitable for a geocoder - the place
  name plus any city/region/municipality mentioned in the post, plus
  "Sweden".
- "reasoning": one short sentence explaining what in the text supports
  this, and why you scored it the confidence you did.
- "confidence": a number from 0.0 to 1.0:
    - 0.8-1.0: a specific named building/ruin/facility - a real pin.
    - 0.4-0.7: a real place used as a fairly tight proximity reference
      for an unnamed site ("an abandoned factory near X").
    - 0.1-0.3: only a broad area/town/region is mentioned, with little
      specificity about the actual site.

Return ONLY strict JSON, no explanation outside the JSON:
{"places": [{"name": string, "geocode_query": string, "reasoning": string, "confidence": number}]}
"""
        },
        {
            "role": "user",
            "content": post_text
        }
    ]

    try:
        data = call_llm_json(messages)
    except Exception as exc:
        print(f"identify_locations failed: {exc}")
        return []

    places = data.get("places")
    if not isinstance(places, list):
        return []

    results: list[dict[str, Any]] = []
    for place in places:
        if not isinstance(place, dict):
            continue
        name = (place.get("name") or "").strip()
        if not name:
            continue
        try:
            confidence = float(place.get("confidence"))
        except (TypeError, ValueError):
            confidence = 0.3
        confidence = max(0.0, min(1.0, confidence))
        results.append({
            "name": name,
            "geocode_query": (place.get("geocode_query") or "").strip() or f"{name}, Sweden",
            "reasoning": (place.get("reasoning") or "").strip() or None,
            "confidence": confidence,
        })
    return results


def _plausible_geocode_match(query: str, candidate: dict[str, Any]) -> bool:
    """Nominatim's top-ranked hit for an ambiguous query (e.g. a hospital
    name that also partially matches an unrelated golf club) can be
    confidently wrong. geocode_query is built as "<name>, <region hint>,
    Sweden" - the name is the ambiguous part being searched for, so check
    the *region hint* actually shows up in the candidate's address rather
    than trusting rank position alone."""
    display_name = (candidate.get("display_name") or "").lower()
    parts = query.split(",")
    hint_words = [
        w.strip().lower() for w in parts[1:]
        if len(w.strip()) > 2 and w.strip().lower() != "sweden"
    ]
    if not hint_words:
        return True  # nothing to check the candidate against
    return any(word in display_name for word in hint_words)


def geocode_candidates(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Raw Nominatim search - returns up to `limit` ranked candidates
    without picking one. Used both by geocode() (auto-picks the first
    plausible one) and the frontend's re-geocode search, where a human
    annotator picks the right candidate themselves."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": limit, "addressdetails": 1}
    headers = {"User-Agent": "IR-agent-location-mapper/0.1"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=20)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        print(f"Geocode search failed for {query}: {exc}")
        return []

    return [
        {
            "lat": float(item["lat"]),
            "lon": float(item["lon"]),
            "display_name": item.get("display_name"),
            "osm_type": item.get("osm_type"),
            "osm_id": item.get("osm_id"),
            "importance": float(item.get("importance", 0.0) or 0.0),
        }
        for item in data
    ]


def geocode(entity: dict[str, Any], country_hint: str = "Sweden") -> dict[str, Any] | None:
    query = entity.get("geocode_query") or f"{entity['name']}, {country_hint}"
    candidates = geocode_candidates(query)
    if not candidates:
        return None

    top = next((c for c in candidates if _plausible_geocode_match(query, c)), candidates[0])
    return {
        "entity": entity["name"],
        "query": query,
        "lat": top["lat"],
        "lon": top["lon"],
        "display_name": top["display_name"],
        "osm_type": top["osm_type"],
        "osm_id": top["osm_id"],
        "geocode_confidence": top["importance"],
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
        "reasoning": metadata.get("reasoning"),
    }


def location_row(item: dict[str, Any]) -> dict[str, Any]:
    """Flatten a discovered-location item into the row shape
    database.repository.insert_location expects."""
    metadata = item.get("metadata", {})
    return {
        "id": item["id"],
        "entity": item.get("entity"),
        "lat": item["lat"],
        "lon": item["lon"],
        "query": item.get("query"),
        "display_name": item.get("display_name"),
        "osm_type": item.get("osm_type"),
        "osm_id": item.get("osm_id"),
        "geocode_confidence": item.get("geocode_confidence"),
        "post_id": metadata.get("post_id"),
        "thread_url": metadata.get("thread_url"),
        "username": metadata.get("username"),
        "time_raw": metadata.get("time_raw"),
        "confidence": metadata.get("confidence"),
        "comment": metadata.get("comment"),
        "evidence": item.get("evidence", []),
        "reasoning": metadata.get("reasoning"),
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
            repo.insert_location(location_row(item))
        return False

    item = {"id": location_id, **location, "metadata": metadata, "evidence": [evidence]}
    discovered.append(item)
    write_outputs(discovered)
    repo.insert_location(location_row(item))
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


def should_expand_search(relevance_score: float, places: list[dict[str, Any]]) -> bool:
    return relevance_score >= 0.75 and bool(places)


def budget_exceeded(start_time: float, processed: int, max_items: int, max_minutes: float | None) -> bool:
    if processed >= max_items:
        return True
    if max_minutes is not None and (time.time() - start_time) / 60 >= max_minutes:
        return True
    return False


def convergence_reached(no_new_locations: int, patience: int = 75) -> bool:
    return no_new_locations >= patience


def load_initial_posts(max_threads: int) -> list[QueueItem]:
    """Seed the queue from urbex-positive threads UrbEx_search.py has
    already classified in Postgres."""
    rows = repo.get_urbex_threads(limit=max_threads)
    return [
        QueueItem(kind="thread", value=normalize_url(row["url"]), metadata=dict(row))
        for row in rows
        if row.get("url")
    ]


def load_discovered_from_db() -> list[dict[str, Any]]:
    """Reconstruct the in-memory discovered-locations list (the shape
    add_to_map/write_outputs expect) from the `locations` table, so a
    resumed run picks up exactly what's already been persisted."""
    discovered = []
    for row in repo.get_locations():
        discovered.append({
            "id": row["id"],
            "entity": row["entity"],
            "lat": row["lat"],
            "lon": row["lon"],
            "query": row["query"],
            "display_name": row["display_name"],
            "osm_type": row["osm_type"],
            "osm_id": row["osm_id"],
            "geocode_confidence": row["geocode_confidence"],
            "metadata": {
                "post_id": row["post_id"],
                "thread_url": row["thread_url"],
                "username": row["username"],
                "time_raw": row["time_raw"],
                "confidence": row["confidence"],
                "comment": row["comment"],
                "reasoning": row["reasoning"],
            },
            "evidence": row["evidence"] or [],
        })
    return discovered


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


def process_content_item(
    content_item: QueueItem,
    threshold: float,
    discovered_locations: list[dict[str, Any]],
) -> tuple[bool, int, list[QueueItem]]:
    """classify -> score -> identify_locations (LLM) -> geocode -> add_to_map
    for one post-level QueueItem. Shared by both run_location_agent (fresh
    scraping) and reprocess_posts (re-analyzing already-scraped posts).

    Returns (was_processed, locations_found, follow_up_queue_items).
    was_processed is False when the item was skipped before doing any real
    work (not urbex-related, or below the relevance threshold) - callers
    use it to decide whether this item should count against a budget."""
    content = content_item.value
    if not classify_urbex(content):
        return False, 0, []

    relevance_score = score_relevance(content)
    if relevance_score < threshold:
        return False, 0, []

    places = identify_locations(content)

    found_this_item = 0
    for place in places:
        location = geocode(place)
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
                "confidence": place.get("confidence", relevance_score),
                "comment": comment_excerpt(content),
                "reasoning": place.get("reasoning"),
            },
            discovered_locations,
        )
        if added:
            found_this_item += 1

    follow_up: list[QueueItem] = []
    if places and should_expand_search(relevance_score, places):
        if contains_links(content):
            follow_up.extend(get_next_posts(content))
    elif not places:
        query = location_clues(content)
        if query:
            follow_up.append(QueueItem(kind="web_search", value=query))

    return True, found_this_item, follow_up


def run_location_agent(
    initial_posts: list[QueueItem],
    threshold: float = DEFAULT_THRESHOLD,
    max_items: int | None = DEFAULT_MAX_ITEMS,
    max_minutes: float | None = None,
    max_pages_per_thread: int | None = 2,
    should_stop: Callable[[], bool] | None = None,
) -> list[dict[str, Any]]:
    """max_items=None means no budget cap (process the whole queue) - used
    by the perpetual crawler, which wants a full pass each cycle rather
    than a small per-call budget. should_stop is polled once per
    processed item so a long pass can be interrupted mid-way rather than
    only between whole calls."""
    visited = repo.get_visited_keys()
    discovered_locations = load_discovered_from_db()

    work_queue = list(reversed(initial_posts))
    processed = 0
    no_new_locations = 0
    start_time = time.time()

    while work_queue:
        if should_stop is not None and should_stop():
            return discovered_locations

        item = work_queue.pop()
        if item.key in visited:
            continue
        visited.add(item.key)
        repo.mark_visited(item.key, item.kind)

        content_items = load_content(item, max_pages_per_thread=max_pages_per_thread)

        for content_item in content_items:
            if should_stop is not None and should_stop():
                return discovered_locations

            if content_item.key in visited:
                continue
            visited.add(content_item.key)
            repo.mark_visited(content_item.key, content_item.kind)

            was_processed, found_this_item, actions = process_content_item(
                content_item, threshold, discovered_locations
            )
            work_queue.extend(actions)

            if not was_processed:
                continue

            no_new_locations = 0 if found_this_item else no_new_locations + 1
            processed += 1

            if convergence_reached(no_new_locations):
                return discovered_locations
            if max_items is not None and budget_exceeded(start_time, processed, max_items, max_minutes):
                return discovered_locations

    return discovered_locations


def reprocess_posts(
    thread_urls: list[str],
    threshold: float = DEFAULT_THRESHOLD,
    should_stop: Callable[[], bool] | None = None,
) -> list[dict[str, Any]]:
    """Re-analyze posts already sitting in Postgres for the given threads
    with the current (LLM) identifier, without re-scraping flashback.org.
    This is the 'go through already-scraped threads again' path - it
    never enqueues follow-up link/web-search actions, since those would
    imply new network scraping."""
    visited = repo.get_visited_keys()
    discovered_locations = load_discovered_from_db()

    for thread_url in thread_urls:
        for post in repo.get_posts_for_thread(thread_url):
            if should_stop is not None and should_stop():
                return discovered_locations

            content_item = QueueItem(
                kind="post",
                value=post.get("text") or "",
                metadata={**post, "source": thread_url},
            )
            if not content_item.value or content_item.key in visited:
                continue
            visited.add(content_item.key)
            repo.mark_visited(content_item.key, "post")

            process_content_item(content_item, threshold, discovered_locations)

    return discovered_locations


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Find, validate, and map potential UrbEx locations from forum data.")
    parser.add_argument("--thread-url", action="append", default=[], help="Seed a specific Flashback thread URL.")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--max-items", type=int, default=DEFAULT_MAX_ITEMS)
    parser.add_argument("--max-threads", type=int, default=DEFAULT_MAX_THREADS)
    parser.add_argument("--max-minutes", type=float, default=None)
    parser.add_argument("--max-pages-per-thread", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUT_DIR.mkdir(exist_ok=True)

    initial_posts = [QueueItem(kind="thread", value=normalize_url(url)) for url in args.thread_url]
    if not initial_posts:
        initial_posts = load_initial_posts(args.max_threads)

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
