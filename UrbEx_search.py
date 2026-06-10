import requests
from agent import run_agent
import time
import requests
from bs4 import BeautifulSoup
import re
import json
import os


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
        input(f"Page info not found in HTML: {url} \n press to continue...")
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
    return run_agent(prompt).strip().upper() == "YES"

def save_json(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)



def load_json(filename, default):
    path = os.path.join(DATA_DIR, filename)

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default
    

def save_results(results, filename="urbex_results.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

def agent(start_url):
    # results = []

    # LEVEL 1: get themes
    html = fetch(start_url)
    # input(html)
    themes = extract_forum_themes(html)
    # input(f'{themes} \n themes found, press to continue...')
    priority_theme = "https://www.flashback.org/f492-urban-exploration-60610"

    if priority_theme in themes:
        themes.remove(priority_theme)
        themes.insert(0, priority_theme)


    for theme in themes:
        if theme  not in completed_themes:
            if theme not in seen_themes:
                seen_themes.append(theme)
                save_json("seen_themes.json", seen_themes)
        else:
            print(f"Theme already completed, skipping: {theme}")
            continue
        # LEVEL 2: paginate theme
        max_pages = get_max_page(fetch(theme), theme)
        pages = build_pages(theme, max_pages)
        print(f"Theme: {theme} | Max pages: {max_pages}")
        # input(f'{pages} \n pages found, press to continue...')
        for page in pages:
            if page not in completed_pages:
                if page not in seen_pages:
                    seen_pages.append(page)
                    save_json("seen_pages.json", list(seen_pages))
            else:
                print(f"Page already completed, skipping: {page}")
                continue
            page_html = fetch(page)
            # LEVEL 3: threads
            threads = extract_threads(page_html)
            # input(f'{threads} \n threads found, press to continue...')
            for title, url in threads:
                if url not in completed_threads:
                    if url not in seen_threads:
                        seen_threads.append(url)
                        save_json("seen_threads.json", list(seen_threads))
                else:
                    print(f"Thread already completed, skipping: {title} - {url}")
                    continue
                all_links.append({
                "title": title,
                "url": url,
                "theme": theme,
                "page": page
            })

                save_json("all_links.json", all_links)
                # AI decision
                decision = is_urbex(title)
                if decision:
                    print(f'URBEX THREAD FOUND: {title} - {url} \n press to continue...')
                    results.append({
                        "title": title,
                        "url": url,
                        "theme": theme,
                        "urbex": True
                    })
                else:
                    results.append({
                    "title": title,
                    "url": url,
                    "theme": theme,
                    "urbex": False
                })
                save_json("results.json", results)
                print(f"Checked thread: {title} - {url} | Urbex: {'YES' if decision else 'NO'}")

                completed_threads.append(url)
                save_json("completed_threads.json", completed_threads)
            completed_pages.append(page)
            save_json("completed_pages.json", completed_pages)
        completed_themes.append(theme)
        save_json("completed_themes.json", completed_themes)


    return results

if __name__ == "__main__":

    DATA_DIR = "data"

    os.makedirs(DATA_DIR, exist_ok=True)    

    completed_themes = load_json("completed_themes.json", [])
    completed_pages = load_json("completed_pages.json", [])
    completed_threads = load_json("completed_threads.json", [])
    seen_themes = load_json("seen_themes.json", [])
    seen_pages = load_json("seen_pages.json", [])
    seen_threads = load_json("seen_threads.json", [])
    results = load_json("results.json", [])
    all_links = load_json("all_links.json", [])
    BASE_URL = "https://www.flashback.org"
    results = agent(BASE_URL)

    print("\nUrbEx-related posts found:")
    for r in results:
        print(r["title"], "-", r["url"])