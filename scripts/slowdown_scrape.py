#!/usr/bin/env python3
"""
slowdown_scrape.py — Fetch every episode from slowdownshow.org.

Phase 1: dump raw episode pages to JSON. No parsing yet.

Strategy: episodes are numbered sequentially (1, 2, 3, ...) with URLs like
/episode/YYYY/MM/DD/{number}-{title-slug}-by-{poet-slug}

We don't know the exact slug for each episode, but the site has an episode
index page that lists them all. We scrape the index to get every episode URL,
then fetch each episode page and save its raw HTML.

Usage:
    pip3 install --break-system-packages requests beautifulsoup4
    python3 slowdown_scrape.py

Output:
    slowdown_raw.json  — list of {url, html, fetched_at}
    slowdown_scrape.log
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


BASE = "https://www.slowdownshow.org"
INDEX_PATH = "/episodes"  # try this first
DELAY = 1.0
OUTPUT_FILE = "slowdown_raw.json"
LOG_FILE = "slowdown_scrape.log"
UA = "parataxis-research/1.0 (personal poetry archive)"


def log(msg):
    print(msg)
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")


def get(url):
    """Fetch a URL, return response text or None."""
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        if r.status_code == 200:
            return r.text
        log(f"  {url} → {r.status_code}")
        return None
    except Exception as e:
        log(f"  {url} → error: {e}")
        return None


def find_episode_urls_from_page(html):
    """Extract /episode/... links from any page's HTML."""
    if not html:
        return set()
    soup = BeautifulSoup(html, "html.parser")
    urls = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # normalize
        if href.startswith("/episode/"):
            urls.add(BASE + href)
        elif href.startswith(BASE + "/episode/"):
            urls.add(href)
        elif href.startswith("https://www.slowdownshow.org/episode/"):
            urls.add(href)
    return urls


def crawl_for_episode_urls():
    """
    Walk the site to collect every episode URL.
    Try index pages, archive pages, and paginated variants.
    """
    all_urls = set()
    visited = set()

    # seed URLs to try
    seeds = [
        f"{BASE}/",
        f"{BASE}/episodes",
        f"{BASE}/archive",
    ]

    # also try year-based archive URLs (2018 through current year)
    current_year = datetime.now().year
    for y in range(2018, current_year + 1):
        seeds.append(f"{BASE}/{y}")

    to_visit = list(seeds)

    while to_visit:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)

        log(f"  crawling: {url}")
        html = get(url)
        time.sleep(DELAY)

        if not html:
            continue

        found = find_episode_urls_from_page(html)
        new_ones = found - all_urls
        if new_ones:
            log(f"    +{len(new_ones)} episode urls (running total: {len(all_urls) + len(new_ones)})")
        all_urls.update(found)

        # look for pagination links on this page
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not href:
                continue
            # only follow same-site links
            full = href if href.startswith("http") else BASE + (href if href.startswith("/") else "/" + href)
            if not full.startswith(BASE):
                continue
            # follow pagination and archive patterns
            if re.search(r"(page|offset|year|month|archive)", href, re.I) and full not in visited:
                to_visit.append(full)

        # safety cap
        if len(visited) > 200:
            log("  hit crawl cap of 200 pages; stopping seed crawl")
            break

    return all_urls


def crawl_by_episode_number(max_check=1700):
    """
    Fallback: episodes are numbered. We know the URL contains the number.
    We can't guess the slug, but Google-indexed episodes often follow the
    same date-slug pattern. This is a fallback only.

    Better approach: use the sitemap.
    """
    return set()


def try_sitemap():
    """Squarespace and similar sites often expose a sitemap."""
    sitemap_urls = [
        f"{BASE}/sitemap.xml",
        f"{BASE}/sitemap-episodes.xml",
    ]
    all_urls = set()
    for sm_url in sitemap_urls:
        log(f"  trying sitemap: {sm_url}")
        text = get(sm_url)
        time.sleep(DELAY)
        if not text:
            continue
        # extract all <loc> URLs that look like episode pages
        found = re.findall(r"<loc>([^<]+/episode/[^<]+)</loc>", text)
        for u in found:
            all_urls.add(u.strip())
        log(f"    sitemap yielded {len(found)} episode URLs")
    return all_urls


def main():
    Path(LOG_FILE).write_text("")
    log("=" * 60)
    log("Slowdown scraper — Phase 1 (raw fetch)")
    log("=" * 60)

    # Step 1: collect all episode URLs.
    log("\nStep 1: collecting episode URLs\n")

    log("Trying sitemap first (fastest if it exists)...")
    all_urls = try_sitemap()

    if len(all_urls) < 100:
        log(f"\nSitemap gave only {len(all_urls)} URLs. Crawling site for more...")
        crawled = crawl_for_episode_urls()
        all_urls.update(crawled)

    log(f"\nTotal unique episode URLs found: {len(all_urls)}")

    if not all_urls:
        log("\nNo episode URLs found. The site structure may have changed.")
        log("Paste this log to Claude for troubleshooting.")
        sys.exit(1)

    # Step 2: fetch each episode page.
    log(f"\nStep 2: fetching {len(all_urls)} episode pages\n")

    urls_list = sorted(all_urls)
    episodes = []
    now = datetime.utcnow().isoformat()

    for i, url in enumerate(urls_list, 1):
        if i % 25 == 0 or i == 1:
            log(f"  [{i}/{len(urls_list)}] {url}")
        html = get(url)
        if html:
            episodes.append({
                "url": url,
                "html": html,
                "fetched_at": now,
            })
        time.sleep(DELAY)

        # incremental save every 100 to prevent total loss on crash
        if i % 100 == 0:
            with open(OUTPUT_FILE, "w") as f:
                json.dump(episodes, f, ensure_ascii=False)
            log(f"    (incremental save: {len(episodes)} episodes so far)")

    # final save
    log(f"\nSaving {len(episodes)} episodes to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(episodes, f, indent=2, ensure_ascii=False)

    size_mb = Path(OUTPUT_FILE).stat().st_size / 1024 / 1024
    log(f"Saved. File size: {size_mb:.1f} MB")
    log(f"\nDone. Come back to Claude when this finishes.")


if __name__ == "__main__":
    main()
