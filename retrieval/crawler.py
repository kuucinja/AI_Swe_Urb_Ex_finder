"""
Perpetual background crawler.

Runs for the life of the backend process rather than being scoped to any
single query - a chat query just makes sure this is running (see
backend/orchestrator.py's "ensure_crawling" action) and never blocks on
it. Cycles through three stages, forever:

    1. Discovery - UrbEx_search.agent() (idempotent/resumable via its own
       has_seen_*/has_completed_* checks, so calling it repeatedly just
       continues where it left off and picks up newly-created threads).
    2. Scrape not-yet-scraped urbex-positive threads.
    3. Reprocess already-scraped-but-unanalyzed posts.

When a full cycle finds nothing left to do, sleeps before checking again
instead of busy-looping.

Module-level singleton: only one crawl thread is ever running, guarded
by _lock. Not persisted across backend restarts (in-process only).
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

import database.repository as repo
from retrieval.UrbEx_search import agent as run_discovery
from retrieval.urbex_location_agent import (
    QueueItem,
    normalize_url,
    run_location_agent,
    reprocess_posts,
)

BASE_URL = "https://www.flashback.org"
IDLE_SLEEP_SECONDS = 300

_lock = threading.RLock()
_state: dict[str, Any] = {
    "thread": None,
    "running": False,
    "should_stop": False,
    "started_at": None,
    "current_activity": None,
}


def _should_stop() -> bool:
    with _lock:
        return _state["should_stop"]


def _set_activity(activity: str | None) -> None:
    with _lock:
        _state["current_activity"] = activity


def _crawl_loop() -> None:
    while not _should_stop():
        _set_activity("discovering threads")
        try:
            run_discovery(BASE_URL, should_stop=_should_stop)
        except Exception as exc:
            print(f"crawler: discovery pass failed: {exc}")

        if _should_stop():
            break

        urbex_threads = repo.get_urbex_threads()
        thread_urls = [t["url"] for t in urbex_threads]

        _set_activity("scraping unscraped threads")
        unscraped = [u for u in thread_urls if not repo.get_posts_for_thread(u)]
        if unscraped:
            items = [QueueItem(kind="thread", value=normalize_url(u)) for u in unscraped]
            try:
                run_location_agent(items, max_items=None, should_stop=_should_stop)
            except Exception as exc:
                print(f"crawler: scrape pass failed: {exc}")

        if _should_stop():
            break

        _set_activity("reprocessing unanalyzed posts")
        try:
            reprocess_posts(thread_urls, should_stop=_should_stop)
        except Exception as exc:
            print(f"crawler: reprocess pass failed: {exc}")

        if _should_stop():
            break

        _set_activity("idle (caught up, waiting to re-check)")
        for _ in range(IDLE_SLEEP_SECONDS):
            if _should_stop():
                break
            time.sleep(1)

    with _lock:
        _state["running"] = False
        _state["current_activity"] = None


def start_crawler() -> dict:
    """Idempotent - a no-op (just returns current status) if already running."""
    with _lock:
        if _state["running"]:
            return get_status()
        _state["running"] = True
        _state["should_stop"] = False
        _state["started_at"] = datetime.now(timezone.utc).isoformat()
        _state["current_activity"] = "starting"
        thread = threading.Thread(target=_crawl_loop, daemon=True)
        _state["thread"] = thread
        thread.start()
    return get_status()


def stop_crawler() -> dict:
    """Signals the loop to stop; it exits at its next checkpoint (between
    posts, not just between whole cycles) rather than immediately."""
    with _lock:
        if _state["running"]:
            _state["should_stop"] = True
    return get_status()


def get_status() -> dict:
    with _lock:
        running = _state["running"]
        current_activity = _state["current_activity"]
        started_at = _state["started_at"]

    progress = repo.get_scrape_progress()
    return {
        "running": running,
        "current_activity": current_activity,
        "started_at": started_at,
        "threads_known": progress["threads_known"],
        "threads_scraped": progress["threads_scraped"],
    }
