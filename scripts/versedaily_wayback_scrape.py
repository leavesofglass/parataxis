#!/usr/bin/env python3
"""
versedaily_wayback_scrape.py — Fetch every archived Verse Daily poem via the
Wayback Machine, since the live site is dead.

Strategy:
1. Query Wayback's CDX API for every archived versedaily.org URL matching
   the poem pattern (/YYYY/*.shtml).
2. For each URL, fetch the latest available snapshot from Wayback.
3. Save raw HTML to JSON, same format as the other scrapers.

Wayback rate limits scrapers, so we go slower: 3 seconds between requests.
Runtime for ~5,000 poems: ~4-5 hours. Runs unattended.

Usage:
    pip3 install --break-system-packages requests
    python3 versedaily_wayback_scrape.py

Output:
    versedaily_wayback_raw.json — list of {url, wayback_url, timestamp, html, fetched_at}
    versedaily_wayback_scrape.log
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: missing library.")
    print("Fix: pip3 install --break-system-packages requests")
    sys.exit(1)


# CDX API query — asks Wayback for every URL it has archived matching a pattern.
# match_type=prefix means "everything starting with this prefix"
# We ask for original URL, timestamp, statuscode, and use collapse to dedupe.
CDX_URL = "http://web.archive.org/cdx/search/cdx"
WAYBACK_BASE = "http://web.archive.org/web"

DELAY = 3.0  # Wayback rate limits — be polite
OUTPUT_FILE = "versedaily_wayback_raw.json"
URLS_FILE = "versedaily_wayback_urls.json"
LOG_FILE = "versedaily_wayback_scrape.log"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def log(msg):
    print(msg)
    with open(LOG_FILE, "a") as f:
        f.write(msg + "\n")


SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def get(url, timeout=60):
    try:
        r = SESSION.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.text
        if r.status_code == 404:
            return None
        log(f"  {url} -> HTTP {r.status_code}")
        return None
    except Exception as e:
        log(f"  {url} -> error: {e}")
        return None


def query_cdx_for_urls():
    """
    Query Wayback CDX for every archived versedaily.org poem URL.

    We fetch results in chunks by year to avoid one giant response that could
    time out. Each poem lives at /YYYY/{slug}.shtml, so we can query per year
    to reduce load and get manageable results.

    Returns a dict: {original_url: latest_timestamp}
    """
    log("\nQuerying Wayback CDX API for archived Verse Daily URLs...")
    log("(This may take a minute or two)\n")

    all_urls = {}
    current_year = datetime.now().year

    # Verse Daily started around 2002, but let's start at 2000 to be safe
    for year in range(2000, current_year + 1):
        url_pattern = f"versedaily.org/{year}/*"
        params = {
            "url": url_pattern,
            "output": "json",
            "fl": "original,timestamp,statuscode",
            "filter": "statuscode:200",
            "filter": "mimetype:text/html",
            "collapse": "urlkey",  # dedupe by URL
        }

        log(f"  querying year {year}...")
        try:
            r = SESSION.get(CDX_URL, params=params, timeout=120)
            if r.status_code != 200:
                log(f"    year {year} returned HTTP {r.status_code}, skipping")
                time.sleep(DELAY)
                continue

            data = r.json()
            if not data or len(data) < 2:
                log(f"    year {year}: no results")
                time.sleep(DELAY)
                continue

            # First row is header: ["original", "timestamp", "statuscode"]
            header = data[0]
            rows = data[1:]

            year_count = 0
            for row in rows:
                original = row[0]
                timestamp = row[1]

                # only .shtml poem pages, not the archive or index pages
                if not re.search(r"/\d{4}/[^/]+\.shtml$", original):
                    continue
                if "archives" in original.lower() or "about" in original.lower():
                    continue

                # keep the latest timestamp for each URL
                if original not in all_urls or timestamp > all_urls[original]:
                    all_urls[original] = timestamp
                    year_count += 1

            log(f"    year {year}: +{year_count} new URLs (total: {len(all_urls)})")
            time.sleep(DELAY)

        except Exception as e:
            log(f"    year {year} error: {e}")
            time.sleep(DELAY)
            continue

    return all_urls


def build_wayback_url(original_url, timestamp):
    """Construct the Wayback URL for a specific snapshot."""
    return f"{WAYBACK_BASE}/{timestamp}/{original_url}"


def main():
    Path(LOG_FILE).write_text("")
    log("=" * 60)
    log("Verse Daily scraper via Wayback Machine")
    log("=" * 60)

    # Step 1: get every archived poem URL from CDX
    urls_map = query_cdx_for_urls()

    log(f"\nFound {len(urls_map)} unique archived poem URLs")

    if not urls_map:
        log("\nNo URLs found. Something may be wrong with the CDX query.")
        sys.exit(1)

    # save URL list so we can resume later if we need to
    with open(URLS_FILE, "w") as f:
        json.dump(urls_map, f, indent=2)
    log(f"URL list saved to {URLS_FILE}")

    # Step 2: fetch each poem's Wayback snapshot
    est_hours = (len(urls_map) * DELAY) / 3600
    log(f"\nEstimated runtime: ~{est_hours:.1f} hours")
    log("Starting fetch...\n")

    poems = []
    now = datetime.utcnow().isoformat()
    urls_list = sorted(urls_map.items())

    for i, (original_url, timestamp) in enumerate(urls_list, 1):
        wayback_url = build_wayback_url(original_url, timestamp)

        if i % 50 == 0 or i == 1:
            log(f"  [{i}/{len(urls_list)}] {original_url}")

        html = get(wayback_url)
        if html:
            poems.append({
                "url": original_url,
                "wayback_url": wayback_url,
                "wayback_timestamp": timestamp,
                "html": html,
                "fetched_at": now,
            })

        time.sleep(DELAY)

        # incremental save every 100
        if i % 100 == 0:
            with open(OUTPUT_FILE, "w") as f:
                json.dump(poems, f, ensure_ascii=False)
            log(f"    (incremental save: {len(poems)} poems)")

    # final save
    log(f"\nSaving {len(poems)} poems to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(poems, f, indent=2, ensure_ascii=False)

    size_mb = Path(OUTPUT_FILE).stat().st_size / 1024 / 1024
    log(f"Saved. File size: {size_mb:.1f} MB")
    log(f"\nDone. Poems fetched: {len(poems)}/{len(urls_list)}")


if __name__ == "__main__":
    main()
