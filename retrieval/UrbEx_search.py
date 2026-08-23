import sys
import requests
from retrieval.crawl_agent import run_agent_crawl
import time
from bs4 import BeautifulSoup
import re
import database.repository as repo

# Windows consoles/redirected-output default to a codepage (e.g. cp1251)
# that can't encode Swedish characters (ö/ä/å) in scraped text - without
# this, print() crashes mid-run the moment it hits one.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", line_buffering=True)


def fetch(url):
    return requests.get(url, headers={"User-Agent": "UniAgent"}).text



def extract_titles(html):
    soup = BeautifulSoup(html, "html.parser")

    titles = []
    for a in soup.find_all("a"):
        t = a.get_text(strip=True)
        href = a.get("href")

        if t and href:
            titles.append((t, href))

    return titles




def extract_forum_themes(html):
    soup = BeautifulSoup(html, "html.parser")

    themes = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]

        # match f<number>
        if re.search(r"/f\d+", href):
            themes.add("https://www.flashback.org" + href)

    return list(themes)

def get_max_page(html, url):
    soup = BeautifulSoup(html, "html.parser")

    page_info = soup.find(
        "span",
        attrs={"data-total-pages": True}
    )

    if not page_info:
        print(f"Page info not found in HTML: {url}")
        return 1

    text = page_info.get_text(strip=True)

    match = re.search(r"av\s+(\d+)", text)

    return int(match.group(1)) if match else 1

def build_pages(theme_url, max_pages):
    match = re.match(r"(https://www\.flashback\.org/f\d+)(.*)", theme_url)

    if not match:
        return [theme_url]

    base = match.group(1)
    suffix = match.group(2)

    pages = [theme_url]

    for i in range(2, max_pages + 1):
        pages.append(f"{base}p{i}{suffix}")

    return pages


def extract_threads(html):
    soup = BeautifulSoup(html, "html.parser")

    threads = []

    for a in soup.find_all("a", href=True, id=True):
        href = a["href"]
        title = a.get_text(strip=True)

        if href.startswith("/t"):  # thread link
            threads.append((title, "https://www.flashback.org" + href))

    return threads

def is_urbex(title):
    prompt = f"""
Is this related to urban exploration (urbex), abandoned places, ruins, or exploring restricted buildings?

Answer ONLY YES or NO.

Title: {title}
"""
    return run_agent_crawl(prompt).strip().upper() == "YES"

def agent(start_url, should_stop=None):
    """should_stop: optional zero-arg callable checked between threads
    (the finest-grained unit of work here, since each one costs an LLM
    call) as well as between pages and themes, so a caller like the
    perpetual crawler can interrupt a long discovery pass promptly
    instead of only between whole themes."""
    results = []

    # LEVEL 1: get themes
    html = fetch(start_url)
    themes = extract_forum_themes(html)
    priority_theme = "https://www.flashback.org/f492lp"

    if priority_theme in themes:
        print(f"Prioritizing theme: {priority_theme}")
        themes.remove(priority_theme)
        themes.insert(0, priority_theme)
    else:
        print(f"Priority theme not found: {priority_theme}")

    for theme in themes:
        if should_stop is not None and should_stop():
            return results

        if repo.has_completed_theme(theme):
            print(f"Theme already completed, skipping: {theme}")
            continue

        if not repo.has_seen_theme(theme):
            repo.mark_theme_seen(theme)

        # LEVEL 2: paginate theme
        max_pages = get_max_page(fetch(theme), theme)
        pages = build_pages(theme, max_pages)
        print(f"Theme: {theme} | Max pages: {max_pages}")
        for page in pages:
            if should_stop is not None and should_stop():
                return results

            if repo.has_completed_page(page):
                print(f"Page already completed, skipping: {page}")
                continue
            if not repo.has_seen_page(page):
                repo.mark_page_seen(page)

            page_html = fetch(page)
            # LEVEL 3: threads
            threads = extract_threads(page_html)
            for title, url in threads:
                if should_stop is not None and should_stop():
                    return results

                if repo.has_completed_thread(url):
                    print(f"Thread already completed, skipping: {title} - {url}")
                    continue
                if not repo.has_seen_thread(url):
                    repo.mark_thread_seen(url)

                repo.upsert_thread(repo.parse_thread_id(url), repo.parse_theme_id(theme), title, url)

                # AI decision
                decision = is_urbex(title)
                result = {"title": title, "url": url, "theme": theme, "urbex": decision}
                results.append(result)

                repo.set_thread_urbex(repo.parse_thread_id(url), decision)
                repo.set_thread_result(repo.parse_thread_id(url), result)

                print(f"Checked thread: {title} - {url} | Urbex: {'YES' if decision else 'NO'}")

                repo.mark_thread_completed(url)
            repo.mark_page_completed(page)
        repo.mark_theme_completed(theme)

    return results

if __name__ == "__main__":
    BASE_URL = "https://www.flashback.org"
    results = agent(BASE_URL)

    print("\nUrbEx-related posts found:")
    for r in results:
        print(r["title"], "-", r["url"])
