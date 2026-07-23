#!/usr/bin/env python3
"""
versedaily_scrape.py — Fetch every poem page from versedaily.org

Phase 1: dump raw poem pages to JSON. No parsing yet.

Strategy:
1. Fetch the master archive index at versedaily.org/archives.shtml
2. Extract every poem URL (pattern: /YYYY/{slug}.shtml)
3. Fetch each poem page and save its raw HTML

Usage:
    pip3 install --break-system-packages requests beautifulsoup4
    python3 versedaily_scrape.py

Output:
    versedaily_raw.json  — list of {url, html, fetched_at}
    versedaily_scrape.log
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: missing library.")
    print("Fix: pip3 install --break-system-packages requests beautifulsoup4")
    sys.exit(1)


ARCHIVE_URL = "http://www.versedaily.org/archives.shtml"
BASE = "http://www.versedaily.org"
DELAY = 1.0
OUTPUT_FILE = "versedaily_raw.json"
LOG_FILE = "versedaily_scrape.log"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


def log(msg):
    print(msg)
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")


SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def get(url):
    try:
        r = SESSION.get(url, timeout=30)
        if r.status_code == 200:
            return r.text
        if r.status_code == 404:
            return None
        log(f"  {url} -> {r.status_code}")
        return None
    except Exception as e:
        log(f"  {url} -> error: {e}")
        return None


def extract_poem_urls(html):
    """
    Parse the archive index and extract every poem URL.

    Poem URLs follow the pattern /YYYY/{slug}.shtml where YYYY is a 4-digit year.
    We also filter out the archive page itself and the "about" pages.
    """
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()

        # match /YYYY/*.shtml or YYYY/*.shtml patterns
        if re.match(r"^/?(19|20)\d{2}/[^/]+\.shtml$", href):
            # normalize to absolute URL
            if href.startswith("/"):
                full = BASE + href
            else:
                full = BASE + "/" + href

            # skip "about" pages (author bio pages, not poems)
            if "/about" in full.lower():
                continue

            if full not in seen:
                seen.add(full)
                urls.append(full)

    return urls


def main():
    Path(LOG_FILE).write_text("")
    log("=" * 60)
    log("Verse Daily scraper -- Phase 1 (raw fetch)")
    log("=" * 60)

    # Step 1: fetch the archive index
    log(f"\nStep 1: fetching archive index at {ARCHIVE_URL}\n")
    archive_html = get(ARCHIVE_URL)
    time.sleep(DELAY)

    if not archive_html:
        log("Archive page failed to load. Check your internet connection and the URL.")
        sys.exit(1)

    log(f"  archive fetched ({len(archive_html):,} bytes)")

    # save the archive HTML too, in case we want to re-parse later
    with open("versedaily_archive.html", "w") as f:
        f.write(archive_html)
    log(f"  archive HTML saved to versedaily_archive.html")

    # Step 2: extract poem URLs
    log(f"\nStep 2: extracting poem URLs from archive\n")
    poem_urls = extract_poem_urls(archive_html)
    log(f"  found {len(poem_urls)} unique poem URLs")

    if not poem_urls:
        log("\nNo poem URLs found. The archive HTML structure may have changed.")
        log("Check versedaily_archive.html to see what came back.")
        sys.exit(1)

    # print first few for sanity
    log(f"  sample URLs:")
    for u in poem_urls[:3]:
        log(f"    {u}")

    # Step 3: fetch each poem page
    log(f"\nStep 3: fetching {len(poem_urls)} poem pages\n")

    poems = []
    now = datetime.utcnow().isoformat()

    for i, url in enumerate(sorted(poem_urls), 1):
        if i % 50 == 0 or i == 1:
            log(f"  [{i}/{len(poem_urls)}] {url}")
        html = get(url)
        if html:
            poems.append({
                "url": url,
                "html": html,
                "fetched_at": now,
            })
        time.sleep(DELAY)

        # incremental save every 100 to prevent total loss on crash
        if i % 100 == 0:
            with open(OUTPUT_FILE, "w") as f:
                json.dump(poems, f, ensure_ascii=False)
            log(f"    (incremental save: {len(poems)} poems so far)")

    # final save
    log(f"\nSaving {len(poems)} poems to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(poems, f, indent=2, ensure_ascii=False)

    size_mb = Path(OUTPUT_FILE).stat().st_size / 1024 / 1024
    log(f"Saved. File size: {size_mb:.1f} MB")
    log(f"\nDone. Come back to Claude when this finishes.")


if __name__ == "__main__":
    main()
