#!/usr/bin/env python3
"""
dedup_live.py — Cross-dedup live public-domain poems against the scraped corpus.

Blocks by canonical author, then matches on:
  1. title_exact     — normalized title match
  2. firstline_exact — normalized first content line match (len > 10)
  3. body_fuzzy      — SequenceMatcher ratio ≥ BODY_THRESHOLD

Outputs:
  dedup_live_matches.txt  — match report (review before dropping)
  dedup_scraped_clean.json — scraped corpus with live-matched records removed

Usage:
  python3 dedup_live.py [--dry-run]   (default: dry-run; use --write to produce output JSON)
"""

import argparse, csv, json, re, unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

SCRIPTS        = Path(__file__).parent
LIVE_CSV       = SCRIPTS / "pubdomainlist.csv"
SCRAPED_JSON   = SCRIPTS / "dedup_merged.json"
NORM_MAP_PATH  = SCRIPTS / "author_norm_map.json"
MATCHES_OUT    = SCRIPTS / "dedup_live_matches.txt"
CLEAN_OUT      = SCRIPTS / "dedup_scraped_clean.json"

BODY_THRESHOLD = 0.85   # slightly looser than inter-source: different editions vary more


# ── normalisation ─────────────────────────────────────────────────────────────

def _strip_diacritics(s):
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()

def norm_str(s):
    s = _strip_diacritics(s).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def norm_apos(s):
    return s.replace("’", "'").replace("‘", "'")

def clean(s):
    return re.sub(r"\s+", " ", norm_apos(s)).strip()

def first_line(text):
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.match(r"^by\s+\S", line, re.IGNORECASE):
            continue
        return norm_str(line)
    return ""

def body_norm(text):
    return re.sub(r"\s+", "", text.lower())

def body_ratio(a, b):
    return SequenceMatcher(None, body_norm(a), body_norm(b), autojunk=False).ratio()


# ── load ──────────────────────────────────────────────────────────────────────

def load_norm_map(path):
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {norm_apos(k): v for k, v in raw.items()}

def canonical_author(raw, norm_map):
    c = clean(raw)
    return norm_map.get(c, c)

def load_live(norm_map):
    poems = []
    with open(LIVE_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            text  = row["body"] or ""
            title = clean(row["title"] or "")
            author_raw = clean(row["author"] or "")
            if not author_raw or not text.strip():
                continue
            poems.append({
                "id":          row["id"],
                "author_raw":  author_raw,
                "author":      canonical_author(author_raw, norm_map),
                "title":       title,
                "title_norm":  norm_str(title),
                "first_line":  first_line(text),
                "body":        text,
            })
    return poems

def load_scraped(norm_map):
    data = json.loads(SCRAPED_JSON.read_text(encoding="utf-8"))
    poems = []
    for r in data:
        text  = r.get("poem_text", "") or ""
        title = clean(r.get("title", "") or "")
        author_raw = clean(r.get("author_raw", "") or r.get("author", "") or "")
        if not author_raw or not text.strip():
            continue
        poems.append({
            "_rec":        r,          # keep original record for output
            "author_raw":  author_raw,
            "author":      canonical_author(r.get("author", author_raw), norm_map),
            "title":       title,
            "title_norm":  norm_str(title),
            "first_line":  first_line(text),
            "body":        text,
        })
    return poems


# ── match ─────────────────────────────────────────────────────────────────────

def find_matches(live_poems, scraped_poems):
    """
    For each live poem, find any scraped poems by the same canonical author
    that match on title, first line, or body similarity.
    Returns list of match dicts.
    """
    # Index scraped by canonical author
    scraped_by_author = defaultdict(list)
    for sp in scraped_poems:
        scraped_by_author[sp["author"]].append(sp)

    matches = []
    scraped_matched_ids = set()  # id(sp) → already matched

    for lp in live_poems:
        candidates = scraped_by_author.get(lp["author"], [])
        for sp in candidates:
            sigs = []

            # Signal 1: title exact
            if lp["title_norm"] and lp["title_norm"] == sp["title_norm"]:
                sigs.append("title_exact")

            # Signal 2: first-line exact
            if (lp["first_line"] and sp["first_line"]
                    and lp["first_line"] == sp["first_line"]
                    and len(lp["first_line"]) > 10):
                sigs.append("firstline_exact")

            # Signal 3: body fuzzy (only if no cheaper signal yet)
            ratio = None
            if not sigs:
                shorter = min(len(body_norm(lp["body"])), len(body_norm(sp["body"])))
                if shorter >= 100:
                    ratio = body_ratio(lp["body"], sp["body"])
                    if ratio >= BODY_THRESHOLD:
                        sigs.append(f"body_fuzzy({ratio:.3f})")

            if sigs:
                if ratio is None:
                    ratio = body_ratio(lp["body"], sp["body"])
                matches.append({
                    "live":    lp,
                    "scraped": sp,
                    "sigs":    sigs,
                    "ratio":   ratio,
                })
                scraped_matched_ids.add(id(sp))

    return matches, scraped_matched_ids


# ── report ────────────────────────────────────────────────────────────────────

def write_report(matches, live_poems, scraped_poems, scraped_matched_ids):
    lines = [
        "LIVE × SCRAPED DEDUP MATCH REPORT",
        "=" * 72,
        f"Live poems  : {len(live_poems)}",
        f"Scraped poems: {len(scraped_poems)}",
        f"Matches found: {len(matches)}  (scraped records to DROP)",
        "=" * 72,
        "",
    ]

    for i, m in enumerate(matches, 1):
        lp = m["live"]
        sp = m["scraped"]
        rec = sp["_rec"]
        sigs_str = " + ".join(m["sigs"])
        lines += [
            f"[{i}]  Author : {lp['author']}",
            f"     Signal : {sigs_str}  (body_ratio={m['ratio']:.3f})",
            f"     LIVE   : id={lp['id']}  title={lp['title']!r}",
            f"     SCRAPED: [{rec.get('primary_source','')}]  title={sp['title']!r}",
            f"             url={rec.get('primary_url','')}",
            "",
        ]

    # Authors with live poems but no scraped match
    live_authors = {lp["author"] for lp in live_poems}
    matched_live_authors = {m["live"]["author"] for m in matches}
    unmatched_authors = sorted(live_authors - matched_live_authors)
    if unmatched_authors:
        lines += [
            "── LIVE AUTHORS WITH NO SCRAPED MATCH ─────────────────────────────",
            "   (live poem kept; no scraped duplicate found)",
            "",
        ]
        for a in unmatched_authors:
            live_titles = [lp["title"] for lp in live_poems if lp["author"] == a]
            for t in live_titles:
                lines.append(f"  {a} — {t!r}")
        lines.append("")

    MATCHES_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote match report → {MATCHES_OUT}")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true",
                        help="Write dedup_scraped_clean.json (default: dry-run, report only)")
    args = parser.parse_args()

    print("Loading norm map...")
    norm_map = load_norm_map(NORM_MAP_PATH)

    print("Loading live CSV...")
    live_poems = load_live(norm_map)
    print(f"  {len(live_poems)} live poems")

    print("Loading scraped corpus...")
    scraped_poems = load_scraped(norm_map)
    print(f"  {len(scraped_poems)} scraped poems")

    print("Matching...")
    matches, scraped_matched_ids = find_matches(live_poems, scraped_poems)
    print(f"  {len(matches)} scraped poems matched (to drop)")

    write_report(matches, live_poems, scraped_poems, scraped_matched_ids)

    if args.write:
        clean_records = [sp["_rec"] for sp in scraped_poems if id(sp) not in scraped_matched_ids]
        CLEAN_OUT.write_text(
            json.dumps(clean_records, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"Wrote {len(clean_records)} scraped records → {CLEAN_OUT}")
        print(f"  (dropped {len(scraped_matched_ids)} scraped duplicates of live poems)")
    else:
        print("Dry-run: pass --write to produce dedup_scraped_clean.json")


if __name__ == "__main__":
    main()
