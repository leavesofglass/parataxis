#!/usr/bin/env python3
"""
versedaily_wayback_resume.py — Resume the Verse Daily Wayback scrape from
where it left off.

Reads the existing URL list and raw poems file, figures out which URLs
haven't been fetched yet, and fetches only those. Appends to the same
output file, no clobbering.

Usage:
    cd ~/Projects/poetry-app/scripts
    python3 versedaily_wayback_resume.py

Requires these files already on disk:
    versedaily_wayback_urls.json    (master URL list from previous run)
    versedaily_wayback_raw.json     (poems fetched so far)
"""

import json
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


WAYBACK_BASE = "http://web.archive.org/web"
DELAY = 3.0
OUTPUT_FILE = "versedaily_wayback_raw.json"
URLS_FILE = "versedaily_wayback_urls.json"
LOG_FILE = "versedaily_wayback_resume.log"

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


def build_wayback_url(original_url, timestamp):
    return f"{WAYBACK_BASE}/{timestamp}/{original_url}"


def main():
    Path(LOG_FILE).write_text("")
    log("=" * 60)
    log("Verse Daily Wayback scraper -- RESUME")
    log("=" * 60)

    # Step 1: load the master URL list from the previous run
    if not Path(URLS_FILE).exists():
        log(f"\nERROR: {URLS_FILE} not found. Cannot resume without master URL list.")
        log("You need to run the original scraper first.")
        sys.exit(1)

    log(f"\nLoading master URL list from {URLS_FILE}...")
    with open(URLS_FILE) as f:
        urls_map = json.load(f)
    log(f"  {len(urls_map)} URLs in master list")

    # Step 2: load what we already have
    already_fetched = set()
    existing_poems = []

    if Path(OUTPUT_FILE).exists():
        log(f"\nLoading existing poems from {OUTPUT_FILE}...")
        try:
            with open(OUTPUT_FILE) as f:
                existing_poems = json.load(f)
            for poem in existing_poems:
                already_fetched.add(poem["url"])
            log(f"  {len(existing_poems)} poems already fetched")
        except json.JSONDecodeError as e:
            log(f"  WARNING: could not parse {OUTPUT_FILE}: {e}")
            log("  If this is an incomplete write from a crash, we'll start over")
            log("  from what's in the file backup, if any. Aborting to be safe.")
            log(f"  Rename {OUTPUT_FILE} to something else and run again, or")
            log("  investigate the file manually.")
            sys.exit(1)
    else:
        log(f"\nNo existing {OUTPUT_FILE} found. Starting from scratch.")

    # Step 3: figure out what's left
    remaining = [
        (url, ts) for url, ts in urls_map.items()
        if url not in already_fetched
    ]
    log(f"\nRemaining URLs to fetch: {len(remaining)}")

    if not remaining:
        log("Nothing to do. Everything is already fetched.")
        sys.exit(0)

    est_hours = (len(remaining) * DELAY) / 3600
    log(f"Estimated runtime: ~{est_hours:.1f} hours")
    log("Starting fetch...\n")

    # Step 4: fetch the missing ones
    now = datetime.now(timezone.utc).isoformat()
    remaining_sorted = sorted(remaining)

    for i, (original_url, timestamp) in enumerate(remaining_sorted, 1):
        wayback_url = build_wayback_url(original_url, timestamp)

        if i % 50 == 0 or i == 1:
            total_so_far = len(existing_poems)
            log(f"  [{i}/{len(remaining_sorted)}] (total on disk: {total_so_far}) {original_url}")

        html = get(wayback_url)
        if html:
            existing_poems.append({
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
                json.dump(existing_poems, f, ensure_ascii=False)
            log(f"    (incremental save: {len(existing_poems)} total poems on disk)")

    # final save
    log(f"\nSaving {len(existing_poems)} total poems to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w") as f:
        json.dump(existing_poems, f, indent=2, ensure_ascii=False)

    size_mb = Path(OUTPUT_FILE).stat().st_size / 1024 / 1024
    log(f"Saved. File size: {size_mb:.1f} MB")
    log(f"\nDone.")
    log(f"  Master list: {len(urls_map)}")
    log(f"  Fetched this run: {i}")
    log(f"  Total on disk: {len(existing_poems)}")


if __name__ == "__main__":
    main()
