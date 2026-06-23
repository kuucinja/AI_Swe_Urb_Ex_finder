import requests
from bs4 import BeautifulSoup
import time


BASE = "https://www.flashback.org"


# -------------------------
# Fetch HTML
# -------------------------
def fetch(url):
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.text


# -------------------------
# Step 1: get iframe sources
# -------------------------
def get_iframes(html):
    soup = BeautifulSoup(html, "html.parser")
    print(soup.prettify())
    iframes = []
    for iframe in soup.select("iframe"):
        src = iframe.get("src")
        if not src:
            continue

        if src.startswith("/"):
            src = BASE + src

        iframes.append(src)
    print(f"Found {len(iframes)} iframes")
    return iframes


# -------------------------
# Step 2: detect thread iframe
# -------------------------
def is_thread_html(html):
    return (
        "div.post" in html
        or ".post_message" in html
        or "post_message" in html
    )


def find_thread_iframe(iframe_urls):
    for url in iframe_urls:
        try:
            html = fetch(url)

            if is_thread_html(html):
                print("[✓] Thread iframe found:", url)
                return url, html

        except Exception as e:
            print("[!] Failed iframe:", url, e)

    return None, None


# -------------------------
# Step 3: parse posts
# -------------------------
def parse_posts(html):
    soup = BeautifulSoup(html, "html.parser")

    posts = []

    for post in soup.select("div.post"):
        username = None
        time_text = None
        text = None

        u = post.select_one(".username")
        if u:
            username = u.get_text(strip=True)

        t = post.select_one("span.date")
        if t:
            time_text = t.get_text(strip=True)

        m = post.select_one(".post_message")
        if m:
            text = m.get_text("\n", strip=True)

        posts.append({
            "username": username,
            "time": time_text,
            "text": text
        })

    return posts


# -------------------------
# Main workflow
# -------------------------
def scrape_thread(url):
    print("[*] Fetching shell page...")
    html = fetch(url)

    print("[*] Extracting iframes...")
    iframe_urls = get_iframes(html)

    print(f"[*] Found {len(iframe_urls)} iframes")

    print("[*] Searching for thread iframe...")
    iframe_url, iframe_html = find_thread_iframe(iframe_urls)

    if not iframe_html:
        print("[-] No thread iframe found")
        return []

    print("[*] Parsing posts...")
    posts = parse_posts(iframe_html)

    return posts


# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    url = "https://www.flashback.org/t279814"

    posts = scrape_thread(url)

    print("\nTotal posts:", len(posts))

    for p in posts[:3]:
        print("\n---")
        print(p)