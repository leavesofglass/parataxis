#!/usr/bin/env python3
"""
dedup_candidates.py — Cross-source duplicate detection across 4 scraped
sources.  Does NOT modify any data; outputs a review report only.

Signals checked (in order of confidence):
  1. title_exact     — normalized title match
  2. firstline_exact — normalized first-line match
  3. body_fuzzy      — body-text SequenceMatcher ratio ≥ FUZZY_THRESHOLD

RALP bilingual pairs (same poem, two languages) are excluded from flagging
via bilingual_group_id.

Live-DB poems (/tmp/live_poems_0.json) only carry id+author, so they are
used only to show which authors have a live presence; body dedup against
live is not possible.

Deleted-poems CSV: not found in project — skipped (pass --deleted path.csv
to enable that check if the file exists).

Usage:
  python3 dedup_candidates.py [--live path] [--deleted path] [--out report.txt]
"""

import argparse, csv, json, re, unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

SCRIPTS = Path(__file__).parent

SOURCES = {
    "versedaily":  (SCRIPTS / "versedaily_parsed.json",  "poet_name", "poem_title", "poem_text"),
    "poetrydaily": (SCRIPTS / "poetrydaily_parsed.json", "poet_name", "poem_title", "poem_text"),
    "ralp":        (SCRIPTS / "ralp_parsed.json",         "poet_name", "poem_title", "poem_text"),
    "slowdown":    (SCRIPTS / "slowdown_parsed.json",     "poet_name", "poem_title", "poem_text"),
}

NORM_MAP_PATH  = SCRIPTS / "author_norm_map.json"
LIVE_DEFAULT   = Path("/tmp/live_poems_0.json")
OUT_DEFAULT    = SCRIPTS / "dedup_report.txt"

FUZZY_THRESHOLD = 0.90


# ── normalisation helpers ─────────────────────────────────────────────────────

def _strip_diacritics(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()

def norm_str(s: str) -> str:
    """Lowercase, strip diacritics, collapse punctuation+whitespace to single spaces."""
    s = _strip_diacritics(s).lower()
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def norm_apos(s: str) -> str:
    return s.replace("’", "'").replace("‘", "'")

def clean(s: str) -> str:
    return re.sub(r"\s+", " ", norm_apos(s)).strip()

def first_line(text: str) -> str:
    """Return normalised first non-empty content line, stripping 'by Author' prefix."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # slowdown prepends "by Poet Name" as first line — skip it
        if re.match(r"^by\s+\S", line, re.IGNORECASE):
            continue
        return norm_str(line)
    return ""

def body_norm(text: str) -> str:
    """Strip all whitespace for exact body comparison; used only for fuzzy ratio."""
    return re.sub(r"\s+", "", text.lower())


# ── load author map ───────────────────────────────────────────────────────────

def load_norm_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {norm_apos(k): v for k, v in raw.items()}

def canonical_author(raw: str, norm_map: dict) -> str:
    c = clean(raw)
    return norm_map.get(c, c)


# ── load poems ────────────────────────────────────────────────────────────────

def load_poems(norm_map: dict) -> list[dict]:
    poems = []
    for src, (path, name_f, title_f, text_f) in SOURCES.items():
        data = json.loads(path.read_text(encoding="utf-8"))
        for r in data:
            raw_author = clean(r.get(name_f, "") or "")
            if not raw_author:
                continue
            text = r.get(text_f, "") or ""
            if not text.strip():
                continue
            title = clean(r.get(title_f, "") or "")
            poems.append({
                "source":      src,
                "source_url":  r.get("source_url", ""),
                "author_raw":  raw_author,
                "author":      canonical_author(raw_author, norm_map),
                "title":       title,
                "title_norm":  norm_str(title),
                "first_line":  first_line(text),
                "body":        text,
                "body_norm":   body_norm(text),
                "bilingual_id": r.get("bilingual_group_id"),
                "date":        r.get("published_date", ""),
            })
    return poems


# ── deleted-poems check ───────────────────────────────────────────────────────

def load_deleted(path: Path) -> set[str]:
    """Return set of normalised titles from deleted-poems CSV."""
    deleted = set()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            t = row.get("title") or row.get("poem_title") or ""
            if t:
                deleted.add(norm_str(t))
    return deleted


# ── duplicate detection ───────────────────────────────────────────────────────

def find_clusters(poems: list[dict], deleted_titles: set[str]) -> list[dict]:
    """
    Group by canonical author, then within each author find duplicate clusters.
    Returns list of cluster dicts.
    """
    # Group by author
    by_author: dict[str, list[dict]] = defaultdict(list)
    for p in poems:
        by_author[p["author"]].append(p)

    clusters = []

    for author, group in sorted(by_author.items()):
        n = len(group)
        if n < 2:
            # Still check singletons against deleted list
            for p in group:
                if deleted_titles and p["title_norm"] in deleted_titles:
                    clusters.append({
                        "type": "deleted_match",
                        "author": author,
                        "signal": "deleted_title",
                        "poems": [p],
                    })
            continue

        # Union-find for clustering
        parent = list(range(n))
        signal_map: dict[tuple, list[str]] = defaultdict(list)

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y, sig):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry
            signal_map[(min(x, y), max(x, y))].append(sig)

        for i in range(n):
            for j in range(i + 1, n):
                p, q = group[i], group[j]

                # Skip RALP bilingual pairs — same poem in two languages
                if (p["bilingual_id"] and q["bilingual_id"]
                        and p["bilingual_id"] == q["bilingual_id"]):
                    continue

                sigs = []

                # Signal 1: title exact
                if p["title_norm"] and q["title_norm"] and p["title_norm"] == q["title_norm"]:
                    sigs.append("title_exact")

                # Signal 2: first-line exact
                if (p["first_line"] and q["first_line"]
                        and p["first_line"] == q["first_line"]
                        and len(p["first_line"]) > 10):
                    sigs.append("firstline_exact")

                # Signal 3: body fuzzy (only when shorter text ≥ 100 chars)
                if not sigs:
                    shorter = min(len(p["body_norm"]), len(q["body_norm"]))
                    if shorter >= 100:
                        ratio = SequenceMatcher(
                            None, p["body_norm"], q["body_norm"], autojunk=False
                        ).ratio()
                        if ratio >= FUZZY_THRESHOLD:
                            sigs.append(f"body_fuzzy({ratio:.3f})")

                if sigs:
                    union(i, j, "+".join(sigs))

            # Deleted-titles check
            if deleted_titles and group[i]["title_norm"] in deleted_titles:
                clusters.append({
                    "type": "deleted_match",
                    "author": author,
                    "signal": "deleted_title",
                    "poems": [group[i]],
                })

        # Collect clusters (groups with ≥2 members sharing a root)
        root_to_indices: dict[int, list[int]] = defaultdict(list)
        for i in range(n):
            root_to_indices[find(i)].append(i)

        for indices in root_to_indices.values():
            if len(indices) < 2:
                continue
            members = [group[i] for i in indices]
            # Collect all signals for this cluster
            all_sigs = []
            for pair, sigs in signal_map.items():
                ia, ib = pair
                if find(ia) == find(indices[0]) or find(ib) == find(indices[0]):
                    all_sigs.extend(sigs)
            unique_sigs = sorted(set(all_sigs))

            # Sort members: scraped sources first, live last; then by date
            members.sort(key=lambda p: (p["source"] == "live", p["date"] or ""))

            clusters.append({
                "type": "duplicate",
                "author": author,
                "signal": ", ".join(unique_sigs),
                "poems": members,
            })

    return clusters


# ── report ────────────────────────────────────────────────────────────────────

def write_report(clusters: list[dict], live_authors: set[str],
                 out_path: Path, deleted_path: str | None) -> None:
    dup_clusters    = [c for c in clusters if c["type"] == "duplicate"]
    deleted_matches = [c for c in clusters if c["type"] == "deleted_match"]

    lines = [
        "DEDUP CANDIDATE REPORT",
        "=" * 72,
        f"Sources: versedaily, poetrydaily, ralp, slowdown",
        f"Live-DB authors present in scraped data: {len(live_authors)} authors",
        f"  (Live body text unavailable — only author overlap noted below)",
        f"Deleted-poems CSV: {'not found — skipped' if not deleted_path else deleted_path}",
        "",
        f"Duplicate clusters found : {len(dup_clusters)}",
        f"Deleted-title matches    : {len(deleted_matches)}",
        "=" * 72,
    ]

    if live_authors:
        lines += ["", "── LIVE-DB AUTHOR OVERLAP ──────────────────────────────────────────",
                  "  These authors appear in both live DB and scraped sources.",
                  "  Body-text dedup against live not possible (no text in export).", ""]
        for a in sorted(live_authors):
            lines.append(f"  {a}")

    lines += ["", "── DUPLICATE CLUSTERS ──────────────────────────────────────────────", ""]

    for i, c in enumerate(dup_clusters, 1):
        lines.append(f"[{i}]  Author: {c['author']}")
        lines.append(f"     Signal: {c['signal']}")
        for p in c["poems"]:
            title_disp  = p["title"] or "(no title)"
            date_disp   = p["date"] or "?"
            url_disp    = p["source_url"] or "(no url)"
            lines.append(f"     • [{p['source']}]  {date_disp}  “{title_disp}”")
            lines.append(f"       {url_disp}")
        lines.append("")

    if deleted_matches:
        lines += ["── DELETED-TITLE MATCHES ───────────────────────────────────────────", ""]
        for c in deleted_matches:
            p = c["poems"][0]
            lines.append(f"  Author: {c['author']} | Title: {p['title']!r}")
            lines.append(f"  Source: [{p['source']}] {p['source_url']}")
            lines.append("")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    print(f"  {len(dup_clusters)} duplicate clusters, {len(deleted_matches)} deleted-title matches")


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live",    default=str(LIVE_DEFAULT))
    parser.add_argument("--deleted", default=None,
                        help="Path to deleted-poems CSV (optional)")
    parser.add_argument("--out",     default=str(OUT_DEFAULT))
    args = parser.parse_args()

    print("Loading author norm map...")
    norm_map = load_norm_map(NORM_MAP_PATH)
    print(f"  {len(norm_map)} variant→canonical mappings")

    print("Loading poems from 4 scraped sources...")
    poems = load_poems(norm_map)
    print(f"  {len(poems)} poems with text loaded")

    # Authors present in live DB
    live_path = Path(args.live)
    live_authors: set[str] = set()
    if live_path.exists():
        live_data = json.loads(live_path.read_text(encoding="utf-8"))
        scraped_authors = {p["author"] for p in poems}
        for r in live_data:
            raw = clean(r.get("author", "") or "")
            if raw:
                canon = canonical_author(raw, norm_map)
                if canon in scraped_authors:
                    live_authors.add(canon)
        print(f"  {len(live_authors)} live-DB authors also appear in scraped data")

    # Deleted poems
    deleted_titles: set[str] = set()
    if args.deleted:
        dp = Path(args.deleted)
        if dp.exists():
            deleted_titles = load_deleted(dp)
            print(f"  {len(deleted_titles)} deleted-poem titles loaded")
        else:
            print(f"  WARNING: --deleted path not found: {args.deleted}")

    print("Finding duplicate clusters...")
    clusters = find_clusters(poems, deleted_titles)

    out_path = Path(args.out)
    write_report(clusters, live_authors, out_path, args.deleted)


if __name__ == "__main__":
    main()
