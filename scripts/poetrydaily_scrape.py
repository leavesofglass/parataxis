#!/usr/bin/env python3
"""
poetrydaily_scrape.py — Fetch every poem from poems.com (Poetry Daily).

v2: goes directly to the 4 known daily_poem sitemap URLs, skips discovery.

The site has 4 poem sitemaps (visible in the sitemap index):
  poems.com/daily_poem-sitemap.xml
  poems.com/daily_poem-sitemap2.xml
  poems.com/daily_poem-sitemap3.xml
  poems.com/daily_poem-sitemap4.xml

Each contains hundreds of <loc>...poem/{slug}/</loc> entries. Total ~4000 poems.

Usage:
    pip3 install --break-system-packages requests
    python3 poetrydaily_scrape.py

Output:
    poetrydaily_raw.json
    poetrydaily_urls.json
    poetrydaily_scrape.log
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: requests not installed.")
    print("Fix: pip3 install --break-system-packages requests")
    sys.exit(1)


BASE = "https://poems.com"
DELAY = 1.5
OUTPUT_FILE = "poetrydaily_raw.json"
URLS_FILE = "poetrydaily_urls.json"
LOG_FILE = "poetrydaily_scrape.log"

SITEMAP_URLS = [
    f"{BASE}/daily_poem-sitemap.xml",
    f"{BASE}/daily_poem-sitemap2.xml",
    f"{BASE}/daily_poem-sitemap3.xml",
    f"{BASE}/daily_poem-sitemap4.xml",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


def log(msg):
    print(msg)
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")


SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def get(url, timeout=30):
    try:
        r = SESSION.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.text
        log(f"  {url} -> HTTP {r.status_code}")
        return None
    except Exception as e:
        log(f"  {url} -> error: {e}")
        return None


def collect_urls_from_sitemap(url):
    """Extract every /poem/{slug}/ URL from a sitemap."""
    log(f"\nFetching sitemap: {url}")
    text = get(url)
    time.sleep(DELAY)
    if not text:
        return set()
    urls = set(re.findall(r"<loc>([^<]+/poem/[^<]+)</loc>", text))
    log(f"  extracted {len(urls)} poem URLs")
    return urls


def main():
    Path(LOG_FILE).write_text("")
    log("=" * 60)
    log("Poetry Daily scraper -- Phase 1 (raw fetch)")
    log("=" * 60)

    # Step 1: collect URLs from all 4 poem sitemaps
    if Path(URLS_FILE).exists():
        log(f"\nLoading URL list from {URLS_FILE}...")
        with open(URLS_FILE) as f:
            all_urls = set(json.load(f))
        log(f"  {len(all_urls)} URLs loaded from previous run")
    else:
        all_urls = set()
        for sm_url in SITEMAP_URLS:
            all_urls.update(collect_urls_from_sitemap(sm_url))

        if not all_urls:
            log("\nNo URLs found from any sitemap. Site structure may have changed.")
            sys.exit(1)

        # save URL list
        with open(URLS_FILE, "w") as f:
            json.dump(sorted(all_urls), f, indent=2)
        log(f"\nURL list saved to {URLS_FILE}")

    log(f"\nTotal unique poem URLs: {len(all_urls)}")

    # Step 2: load any existing raw output for resume
    already_fetched = set()
    existing_poems = []
    if Path(OUTPUT_FILE).exists():
        try:
            with open(OUTPUT_FILE) as f:
                existing_poems = json.load(f)
            for poem in existing_poems:
                already_fetched.add(poem["url"])
            log(f"Resuming: {len(existing_poems)} poems already fetched")
        except Exception as e:
            log(f"Could not load existing output: {e}")

    remaining = sorted(all_urls - already_fetched)
    if not remaining:
        log("\nAll URLs already fetched. Nothing to do.")
        sys.exit(0)

    log(f"\nRemaining to fetch: {len(remaining)}")
    est_min = (len(remaining) * DELAY) / 60
    log(f"Estimated runtime: ~{est_min:.0f} minutes")
    log("Starting fetch...\n")

    poems = existing_poems
    now = datetime.now(timezone.utc).isoformat()

    for i, url in enumerate(remaining, 1):
        if i % 50 == 0 or i == 1:
            log(f"  [{i}/{len(remaining)}] {url}")
        html = get(url)
        if html:
            poems.append({
                "url": url,
                "html": html,
                "fetched_at": now,
            })
        time.sleep(DELAY)

        # incremental save every 100
        if i % 100 == 0:
            with open(OUTPUT_FILE, "w") as f:
                json.dump(poems, f, ensure_ascii=False)
            log(f"    (incremental save: {len(poems)} total on disk)")

    # final save
    log(f"\nSaving {len(poems)} poems to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(poems, f, indent=2, ensure_ascii=False)

    size_mb = Path(OUTPUT_FILE).stat().st_size / 1024 / 1024
    log(f"Saved. File size: {size_mb:.1f} MB")
    log(f"\nDone. Total poems fetched: {len(poems)}")


if __name__ == "__main__":
    main()
