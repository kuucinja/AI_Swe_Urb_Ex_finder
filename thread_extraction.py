import requests
from bs4 import BeautifulSoup
import time
from os import path, makedirs
import json

BASE = "https://www.flashback.org"


def fetch(url):
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.text


def parse_posts(html):
    soup = BeautifulSoup(html, "html.parser")

    posts = []

    for post in soup.select("div.post"):
        post_id = post.get("id")
        #print("Parsing post:", post_id)

        # username
        user = post.select_one(".post-user-username")
        #print("User element:", user)
        username = user.get_text(strip=True) if user else None

        # time (inside post-heading)
        time_el = post.select_one(".post-heading")
        post_time = None
        if time_el:
            post_time = time_el.get_text(" ", strip=True)

        # message
        msg = post.select_one(".post_message")
        # print("Message element:", msg)
        text = msg.get_text("\n", strip=True) if msg else None
        # print("Extracted text:", text[:100] if text else None)
        posts.append({
            "post_id": post_id,
            "username": username,
            "time_raw": post_time,
            "text": text
        })
        # print(posts[-1])
    return posts


def build_url(thread_id, page):
    if page == 1:
        return f"{BASE}/t{thread_id}"
    return f"{BASE}/t{thread_id}p{page}"


def get_total_pages(html):
    soup = BeautifulSoup(html, "html.parser")
    el = soup.select_one("span.input-page-jump")
    if el and el.has_attr("data-total-pages"):
        return int(el["data-total-pages"])
    return 1


def scrape(thread_id):
    url = build_url(thread_id, 1)
    html = fetch(url)
    time.sleep(2)  # be nice to the server and avoid hitting rate limits
    total_pages = get_total_pages(html)
    print("Pages:", total_pages)
    print("thread url:", url)

    all_posts = []

    for page in range(1, total_pages + 1):
        url = build_url(thread_id, page)
        print("Scraping:", url)

        if path.exists(path.join(BASE_DIR, f"thread{thread_id}_page{page}.jsonl")):
            print(f"File already exists for page {page}, skipping save.")
            continue

        html = fetch(url)
        posts = parse_posts(html)



        with open(path.join(BASE_DIR, f"thread{thread_id}_page{page}.jsonl"), "w", encoding="utf-8") as f:
            for post in posts:
                f.write(json.dumps(post, ensure_ascii=False) + "\n")
        all_posts.extend(posts)
        if page < 10:
            print("page under 10, sleeping for 3 seconds to avoid rate limits...")
            sleep_time = 3
        if page >= 10:
            print("page over 10, sleeping for 0.25 times the page count seconds to avoid rate limits...")
            sleep_time = 0.25 * (page - 1)  # increase sleep time with each page
        if page >=200:
            print("page over 200, sleeping for 0.025 x page count seconds to avoid rate limits...")
            sleep_time = 0.025 * (page - 1) # add extra sleep after 200 pages
        print(f"Sleeping for {sleep_time} seconds to avoid rate limits... {page}/{total_pages}")
        time.sleep(sleep_time)


    return all_posts


if __name__ == "__main__":

    BASE_DIR = "data_urbex"
    INPUT_DATA = "data"
    makedirs(BASE_DIR, exist_ok=True)
    with open(path.join(INPUT_DATA, "results.json"), "r", encoding="utf-8") as f:
        results = json.load(f)
    
    for r in results:
        if "f492" in r["theme"].lower() or "urban" in r["theme"].lower():
            url = r["url"]
            thread_id = url.split("/t")[-1].split("p")[0]
            print(f"Processing thread: {thread_id} | URL: {url}")
            data = scrape(thread_id)

            print("Total posts:", len(data))
            print(data[:2])

            with open(path.join(BASE_DIR, "posts.json"), "w") as f:
                json.dump(data, f)