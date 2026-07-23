#!/usr/bin/env python3
"""
ralp_scrape.py — Fetch every post from readalittlepoetry.com via the WordPress REST API.

Phase 1: dump raw posts to JSON. No parsing. We look at what came back, then write
the parser in Phase 2.

Usage:
    python3 ralp_scrape.py

Requirements:
    pip3 install requests

Output:
    ralp_raw.json — list of all posts with title, date, link, content, categories, etc.
    ralp_scrape.log — progress and any errors
"""

import json
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests library not installed.")
    print("Fix: run this in Terminal, then re-run the script:")
    print("    pip3 install requests")
    sys.exit(1)


# ---- config ----
BASE_URL = "https://readalittlepoetry.com/wp-json/wp/v2/posts"
FALLBACK_URL = "https://public-api.wordpress.com/wp/v2/sites/readalittlepoetry.com/posts"
PER_PAGE = 100  # WordPress REST API max
DELAY_SECONDS = 1.0  # polite rate limit
OUTPUT_FILE = "ralp_raw.json"
LOG_FILE = "ralp_scrape.log"
USER_AGENT = "parataxis-research-scraper/1.0 (personal poetry archive project)"


def log(msg):
    """Print and also append to log file."""
    print(msg)
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")


def try_endpoint(url):
    """Hit the endpoint with per_page=1 to see if it works and get total post count."""
    try:
        r = requests.get(
            url,
            params={"per_page": 1},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        if r.status_code == 200:
            total = r.headers.get("X-WP-Total", "unknown")
            total_pages = r.headers.get("X-WP-TotalPages", "unknown")
            return True, int(total) if total != "unknown" else None, int(total_pages) if total_pages != "unknown" else None
        else:
            log(f"  endpoint returned status {r.status_code}")
            return False, None, None
    except Exception as e:
        log(f"  endpoint error: {e}")
        return False, None, None


def fetch_page(url, page):
    """Fetch one page of posts. Returns list of posts or None on error."""
    try:
        r = requests.get(
            url,
            params={"per_page": PER_PAGE, "page": page},
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 400:
            # WordPress returns 400 when you paginate past the last page
            return []
        else:
            log(f"  page {page} returned status {r.status_code}")
            return None
    except Exception as e:
        log(f"  page {page} error: {e}")
        return None


def main():
    # clear log
    Path(LOG_FILE).write_text("")

    log("=" * 60)
    log("RALP scraper — Phase 1 (raw fetch, no parsing)")
    log("=" * 60)

    # try primary endpoint first
    log(f"\nTrying primary endpoint: {BASE_URL}")
    ok, total, total_pages = try_endpoint(BASE_URL)
    endpoint = BASE_URL

    if not ok:
        log(f"\nPrimary failed. Trying fallback: {FALLBACK_URL}")
        ok, total, total_pages = try_endpoint(FALLBACK_URL)
        endpoint = FALLBACK_URL

    if not ok:
        log("\nBoth endpoints failed. The WordPress REST API may be disabled on this site.")
        log("Next step: try scraping the HTML directly with BeautifulSoup. Tell Claude.")
        sys.exit(1)

    log(f"\nEndpoint works: {endpoint}")
    log(f"Total posts: {total}")
    log(f"Total pages at per_page={PER_PAGE}: {total_pages}")

    if total and total > 0:
        est_seconds = total_pages * DELAY_SECONDS if total_pages else 0
        log(f"Estimated runtime: ~{est_seconds:.0f} seconds ({est_seconds/60:.1f} min)")

    log("\nStarting fetch...\n")

    all_posts = []
    page = 1
    consecutive_empty = 0

    while True:
        log(f"Fetching page {page}...")
        posts = fetch_page(endpoint, page)

        if posts is None:
            log(f"  page {page} failed. Retrying once after 5 sec...")
            time.sleep(5)
            posts = fetch_page(endpoint, page)
            if posts is None:
                log(f"  page {page} failed twice. Stopping. Saving what we have.")
                break

        if not posts:
            consecutive_empty += 1
            log(f"  page {page} is empty.")
            if consecutive_empty >= 2:
                log("  two empty pages in a row — we're done.")
                break
        else:
            consecutive_empty = 0
            all_posts.extend(posts)
            log(f"  got {len(posts)} posts. Total so far: {len(all_posts)}")

        page += 1
        time.sleep(DELAY_SECONDS)

        # sanity limit
        if page > 500:
            log("  hit page 500 — stopping as a safety limit.")
            break

    log(f"\nDone. Total posts fetched: {len(all_posts)}")
    log(f"Saving to {OUTPUT_FILE}...")

    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_posts, f, indent=2, ensure_ascii=False)

    file_size_mb = Path(OUTPUT_FILE).stat().st_size / 1024 / 1024
    log(f"Saved. File size: {file_size_mb:.1f} MB")
    log(f"\nNext step: open {OUTPUT_FILE} in a text editor, look at 5-10 posts,")
    log("then tell Claude what fields to pull for Phase 2 parsing.")


if __name__ == "__main__":
    main()
