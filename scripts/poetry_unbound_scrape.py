#!/usr/bin/env python3
"""
poetry_unbound_scrape.py — Fetch every episode from onbeing.org/series/poetry-unbound/

Phase 1: dump raw episode pages to JSON. No parsing yet.

v2: adds browser-like headers to get past bot detection.

Usage:
    pip3 install --break-system-packages requests beautifulsoup4
    python3 poetry_unbound_scrape.py

Output:
    poetry_unbound_raw.json
    poetry_unbound_scrape.log
"""

import json
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


SERIES_URL = "https://onbeing.org/series/poetry-unbound/"
BASE = "https://onbeing.org"
DELAY = 1.0
OUTPUT_FILE = "poetry_unbound_raw.json"
LOG_FILE = "poetry_unbound_scrape.log"

# Full browser-like headers. Some sites fingerprint on the presence/order of these.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
}


def log(msg):
    print(msg)
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")


# Use a session so cookies persist across requests (some CDNs set challenge cookies)
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def get(url, referer=None):
    try:
        headers = {}
        if referer:
            headers["Referer"] = referer
        r = SESSION.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            return r.text
        if r.status_code == 404:
            return None
        log(f"  {url} -> {r.status_code}")
        return None
    except Exception as e:
        log(f"  {url} -> error: {e}")
        return None


def find_program_urls(html):
    if not html:
        return set()
    soup = BeautifulSoup(html, "html.parser")
    urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/programs/"):
            urls.add(BASE + href.rstrip("/") + "/")
        elif href.startswith(BASE + "/programs/"):
            urls.add(href.rstrip("/") + "/")
    return urls


def warm_up_session():
    """Hit the homepage first to establish cookies before doing anything else."""
    log("  warming up session (fetching homepage)...")
    html = get(f"{BASE}/")
    time.sleep(DELAY)
    if html:
        log("  session established")
        return True
    log("  homepage also blocked. May need Playwright approach.")
    return False


def try_sitemap():
    sitemap_candidates = [
        f"{BASE}/sitemap.xml",
        f"{BASE}/sitemap_index.xml",
        f"{BASE}/wp-sitemap.xml",
    ]
    all_urls = set()
    poetry_related_sitemaps = []

    for sm_url in sitemap_candidates:
        text = get(sm_url, referer=f"{BASE}/")
        time.sleep(DELAY)
        if not text:
            continue
        log(f"  found sitemap: {sm_url}")
        import re
        sub = re.findall(r"<loc>([^<]+\.xml)</loc>", text)
        for s in sub:
            if any(k in s.lower() for k in ("program", "post", "poetry")):
                poetry_related_sitemaps.append(s.strip())
        direct = re.findall(r"<loc>([^<]+/programs/[^<]+)</loc>", text)
        for u in direct:
            all_urls.add(u.strip().rstrip("/") + "/")

    for sm in poetry_related_sitemaps:
        log(f"  fetching sub-sitemap: {sm}")
        text = get(sm, referer=f"{BASE}/")
        time.sleep(DELAY)
        if not text:
            continue
        import re
        direct = re.findall(r"<loc>([^<]+/programs/[^<]+)</loc>", text)
        for u in direct:
            all_urls.add(u.strip().rstrip("/") + "/")
        log(f"    +{len(direct)} program URLs")

    return all_urls


def paginate_series_index():
    all_urls = set()
    page = 1
    consecutive_empty = 0
    prev_url = f"{BASE}/"

    while True:
        if page == 1:
            url = SERIES_URL
        else:
            url = f"{SERIES_URL}page/{page}/"

        log(f"  fetching series page {page}: {url}")
        html = get(url, referer=prev_url)
        time.sleep(DELAY)
        prev_url = url

        if not html:
            log(f"    page {page} returned nothing -- end of pagination")
            break

        found = find_program_urls(html)
        new_ones = found - all_urls

        if not new_ones:
            consecutive_empty += 1
            log(f"    page {page}: no new URLs")
            if consecutive_empty >= 2:
                log("    two empty pages -- stopping")
                break
        else:
            consecutive_empty = 0
            all_urls.update(found)
            log(f"    +{len(new_ones)} new episode URLs (total: {len(all_urls)})")

        page += 1

        if page > 50:
            log("    hit page cap of 50 -- stopping")
            break

    return all_urls


def main():
    Path(LOG_FILE).write_text("")
    log("=" * 60)
    log("Poetry Unbound scraper -- Phase 1 (raw fetch) v2")
    log("=" * 60)

    log("\nStep 0: warming up session\n")
    if not warm_up_session():
        log("\nSite blocking basic requests. Would need Playwright to bypass.")
        log("Come back to Claude and we'll switch approaches.")
        sys.exit(1)

    log("\nStep 1: collecting episode URLs\n")

    log("Trying sitemap first...")
    all_urls = try_sitemap()

    if len(all_urls) < 100:
        log(f"\nSitemap gave {len(all_urls)}. Also paginating series index...")
        paginated = paginate_series_index()
        all_urls.update(paginated)

    log(f"\nTotal unique /programs/ URLs found: {len(all_urls)}")

    if not all_urls:
        log("\nNo URLs found. Site structure may have changed.")
        sys.exit(1)

    log(f"\nStep 2: fetching {len(all_urls)} pages\n")

    urls_list = sorted(all_urls)
    episodes = []
    now = datetime.utcnow().isoformat()
    prev_url = SERIES_URL

    for i, url in enumerate(urls_list, 1):
        if i % 25 == 0 or i == 1:
            log(f"  [{i}/{len(urls_list)}] {url}")
        html = get(url, referer=prev_url)
        if html:
            episodes.append({
                "url": url,
                "html": html,
                "fetched_at": now,
            })
        prev_url = url
        time.sleep(DELAY)

        if i % 100 == 0:
            with open(OUTPUT_FILE, "w") as f:
                json.dump(episodes, f, ensure_ascii=False)
            log(f"    (incremental save: {len(episodes)} episodes)")

    log(f"\nSaving {len(episodes)} episodes to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(episodes, f, indent=2, ensure_ascii=False)

    size_mb = Path(OUTPUT_FILE).stat().st_size / 1024 / 1024
    log(f"Saved. File size: {size_mb:.1f} MB")
    log(f"\nDone. Come back to Claude when this finishes.")


if __name__ == "__main__":
    main()