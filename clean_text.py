import re
import html
from bs4 import BeautifulSoup
from pathlib import Path
import json


def clean_text(raw_html: str, lower: bool = False) -> str:
    """
    Clean Flashback post text from HTML to readable plain text.
    
    Args:
        raw_html (str): raw HTML from post_message
        lower (bool): optionally lowercase output for NLP tasks
    
    Returns:
        str: cleaned text
    """
    if not raw_html:
        return None

    # 1. Parse HTML safely
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text("\n")

    # 2. Decode HTML entities
    text = html.unescape(text)

    # 3. Normalize line breaks
    text = re.sub(r"\r\n|\r", "\n", text)

    # 4. Remove excessive spaces/tabs
    text = re.sub(r"[ \t]+", " ", text)

    # 5. Collapse multiple newlines
    text = re.sub(r"\n\s*\n+", "\n\n", text)

    # 6. Strip whitespace
    text = text.strip()

    # 7. Optional normalization
    if lower:
        text = text.lower()

    return text


def clean_flashback_post(post_element) -> str:
    """
    Direct helper for BeautifulSoup post element.
    """
    if not post_element:
        return None

    msg = post_element.select_one(".post_message")
    if not msg:
        return None

    raw_html = msg.decode_contents()
    return clean_text(raw_html)


def clean_jsonl_posts(input_file: Path) -> list[dict]:
    """
    Clean every post in a thread page JSONL file.
    """
    cleaned_posts = []

    with input_file.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            post = json.loads(line)
            post["text"] = clean_text(post.get("text"))
            cleaned_posts.append(post)

    return cleaned_posts


# -------------------------
# CLI test
# -------------------------
if __name__ == "__main__":
    BASE_DIR = Path("data_urbex")

    for input_file in sorted(BASE_DIR.glob("*.jsonl")):
        print(input_file.name)
        cleaned_posts = clean_jsonl_posts(input_file)

        text_file = input_file.with_name(input_file.stem + "_clean.txt")
        jsonl_file = input_file.with_name(input_file.stem + "_clean.jsonl")

        with text_file.open("w", encoding="utf-8") as f:
            for post in cleaned_posts:
                f.write(f"--- {post.get('post_id')} | {post.get('username')} | {post.get('time_raw')} ---\n")
                f.write((post.get("text") or "") + "\n\n")

        with jsonl_file.open("w", encoding="utf-8") as f:
            for post in cleaned_posts:
                f.write(json.dumps(post, ensure_ascii=False) + "\n")

        print(f"Cleaned posts: {len(cleaned_posts)}")
