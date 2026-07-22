#!/usr/bin/env python3
"""
dedup_merge.py — Apply merge decisions from the dedup candidate report.

Auto-merges:
  1. Slowdown encore re-runs            (same source, /encore-/ in URL)
  2. Cross-source or same-source, body ≥ BODY_THRESHOLD (includes title+firstline exact)
  3. Confirmed fuzzy matches             (Wallschlaeger, Hunley — user confirmed)

Keeps both:
  - RALP bilingual A/B pairs (same post, two languages — excluded by post-ID prefix match)
  - Same-source/cross-source where ONLY firstline matched and body < threshold
  - Coincidental same-title different poems (body < 0.50)

Special cases:
  - Rilke "Autumn Day" RALP×2: keep newer (2025), drop 2011

Output:
  dedup_merged.json      — merged corpus (one record per poem)
  dedup_merge_log.txt    — every merge decision with reason
  dedup_ambiguous.txt    — clusters needing manual review

Usage:
  python3 dedup_merge.py [--live path] [--out-dir .]
"""

import argparse, json, re, unicodedata
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

NORM_MAP_PATH   = SCRIPTS / "author_norm_map.json"
LIVE_DEFAULT    = Path("/tmp/live_poems_0.json")
BODY_THRESHOLD  = 0.90
FUZZY_THRESHOLD = 0.90

# These two pairs were confirmed by user as dupes despite different titles
CONFIRMED_FUZZY = {
    ("Nikki Wallschlaeger", "Crying", "The Lunch Counter of Eternal Tears"),
    ("Tom C. Hunley",
     "Self-Portrait as a Childs Stick Figure Drawing on a Refrigerator",
     "Self-Portrait as a Child's Stick Figure Drawing on a Refrigerator"),
}


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


# ── metadata richness score ───────────────────────────────────────────────────

def richness(p):
    score = 0
    for field in ("source_book", "source_publisher", "source_year"):
        if p.get(field, ""):
            score += 1
    if p.get("title"):
        score += 1
    score += len(p.get("body", "")) / 10000  # fractional tiebreak on text length
    return score


# ── load ──────────────────────────────────────────────────────────────────────

def load_norm_map(path):
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {norm_apos(k): v for k, v in raw.items()}

def canonical_author(raw, norm_map):
    c = clean(raw)
    return norm_map.get(c, c)

def load_poems(norm_map):
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
                "source":        src,
                "source_url":    r.get("source_url", ""),
                "author_raw":    raw_author,
                "author":        canonical_author(raw_author, norm_map),
                "title":         title,
                "title_norm":    norm_str(title),
                "first_line":    first_line(text),
                "body":          text,
                "source_book":   r.get("source_book", ""),
                "source_journal":r.get("source_journal", ""),
                "source_publisher": r.get("source_publisher", ""),
                "source_year":   r.get("source_year", ""),
                "date":          r.get("published_date", ""),
                "bilingual_id":  r.get("bilingual_group_id"),
                "translator":    r.get("translator", ""),
            })
    return poems


# ── cluster detection (same logic as dedup_candidates.py) ─────────────────────

def detect_clusters(poems):
    by_author = defaultdict(list)
    for p in poems:
        by_author[p["author"]].append(p)

    raw_clusters = []  # list of lists-of-poem-dicts

    for author, group in by_author.items():
        n = len(group)
        if n < 2:
            continue

        parent = list(range(n))
        pair_sigs = {}  # (i,j) → set of signal strings
        pair_ratio = {}  # (i,j) → float body ratio (computed lazily)

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            rx, ry = find(x), find(y)
            if rx != ry:
                parent[rx] = ry

        for i in range(n):
            for j in range(i + 1, n):
                p, q = group[i], group[j]
                # Exclude RALP bilingual A/B pairs (same post, two languages).
                # bilingual_group_id is like "11337-A" / "11337-B" — they share
                # the same base post ID, so compare on that prefix, not full string.
                if p["bilingual_id"] and q["bilingual_id"]:
                    base_p = p["bilingual_id"].rsplit("-", 1)[0]
                    base_q = q["bilingual_id"].rsplit("-", 1)[0]
                    if base_p == base_q:
                        continue

                sigs = set()
                if p["title_norm"] and p["title_norm"] == q["title_norm"]:
                    sigs.add("title_exact")
                if (p["first_line"] and q["first_line"]
                        and p["first_line"] == q["first_line"]
                        and len(p["first_line"]) > 10):
                    sigs.add("firstline_exact")

                # body fuzzy only if no cheaper signal fired yet
                if not sigs:
                    shorter = min(len(body_norm(p["body"])), len(body_norm(q["body"])))
                    if shorter >= 100:
                        ratio = body_ratio(p["body"], q["body"])
                        pair_ratio[(i, j)] = ratio
                        if ratio >= FUZZY_THRESHOLD:
                            sigs.add(f"body_fuzzy({ratio:.3f})")

                if sigs:
                    pair_sigs[(i, j)] = sigs
                    union(i, j)

        root_to_idx = defaultdict(list)
        for i in range(n):
            root_to_idx[find(i)].append(i)

        for indices in root_to_idx.values():
            if len(indices) < 2:
                continue
            members = [group[i] for i in indices]
            # collect all pair signals within this cluster
            cluster_pairs = []
            for ia in indices:
                for ib in indices:
                    if ia >= ib:
                        continue
                    key = (ia, ib)
                    if key in pair_sigs:
                        ratio = pair_ratio.get(key)
                        if ratio is None:
                            ratio = body_ratio(group[ia]["body"], group[ib]["body"])
                            pair_ratio[key] = ratio
                        cluster_pairs.append({
                            "i": ia, "j": ib,
                            "sigs": pair_sigs[key],
                            "ratio": ratio,
                        })
            raw_clusters.append({
                "author":  author,
                "members": members,
                "pairs":   cluster_pairs,
            })

    return raw_clusters


# ── classify cluster ──────────────────────────────────────────────────────────

def is_encore(p, q):
    return (p["source"] == q["source"]
            and ("/encore" in (p["source_url"] or "").lower()
                 or "/encore" in (q["source_url"] or "").lower()))

def is_confirmed_fuzzy(members):
    titles = {m["title"] for m in members}
    author = members[0]["author"]
    for a, t1, t2 in CONFIRMED_FUZZY:
        if author == a and {t1, t2} <= titles:
            return True
    return False

def classify_cluster(cluster):
    members = cluster["members"]
    pairs   = cluster["pairs"]
    author  = cluster["author"]

    # — confirmed fuzzy (user confirmed same poem despite different titles) —
    if is_confirmed_fuzzy(members):
        return "fuzzy_confirmed"

    sources = {m["source"] for m in members}
    cross = len(sources) > 1

    has_title_firstline = any("title_exact" in p["sigs"] and "firstline_exact" in p["sigs"]
                              for p in pairs)
    has_firstline_only = any("firstline_exact" in p["sigs"] and "title_exact" not in p["sigs"]
                             for p in pairs)

    max_ratio = max((p["ratio"] for p in pairs), default=0.0)

    # — encore: any same-source pair where one URL contains /encore/ —
    any_encore = not cross and any(
        is_encore(members[i], members[j])
        for i in range(len(members)) for j in range(i + 1, len(members))
    )
    if any_encore:
        return "encore"

    # — high body similarity: merge regardless of source or signal match —
    # Covers: cross-source title+firstline, cross-source title-only with high body,
    #         same-source body match, and the 18 "ambiguous" clusters with body ≥ 0.90.
    if max_ratio >= BODY_THRESHOLD:
        return "body_match"

    # — Rilke "Autumn Day": same source, same title, body 0.5–0.9
    #   (two different translations 14 years apart) — keep newer date —
    if (author == "Rainer Maria Rilke"
            and any(m["title"] == "Autumn Day" for m in members)):
        return "keep_newer"

    # — firstline only, body below threshold → not a dupe —
    if has_firstline_only and not has_title_firstline:
        return "not_dupe_firstline_only"

    # — everything else → ambiguous —
    return "ambiguous"


# ── merge a cluster into one record ──────────────────────────────────────────

def merge_cluster(members, reason):
    # Pick winner: richest metadata; use earliest non-encore URL for provenance
    winner = max(members, key=richness)
    provenance = []
    for m in members:
        provenance.append({
            "source": m["source"],
            "url":    m["source_url"],
            "date":   m["date"],
        })

    rec = {
        "author":            winner["author"],
        "author_raw":        winner["author_raw"],
        "title":             winner["title"],
        "poem_text":         winner["body"],
        "source_book":       winner.get("source_book", ""),
        "source_journal":    winner.get("source_journal", ""),
        "source_publisher":  winner.get("source_publisher", ""),
        "source_year":       winner.get("source_year", ""),
        "translator":        winner.get("translator", ""),
        "primary_source":    winner["source"],
        "primary_url":       winner["source_url"],
        "published_date":    winner["date"],
        "provenance":        provenance,
        "merge_reason":      reason,
    }
    return rec


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live",    default=str(LIVE_DEFAULT))
    parser.add_argument("--out-dir", default=str(SCRIPTS))
    args = parser.parse_args()
    out = Path(args.out_dir)

    print("Loading norm map...")
    norm_map = load_norm_map(NORM_MAP_PATH)

    print("Loading poems...")
    poems = load_poems(norm_map)
    print(f"  {len(poems)} poems with text")

    print("Detecting clusters...")
    clusters = detect_clusters(poems)
    print(f"  {len(clusters)} raw clusters")

    # ── classify ──────────────────────────────────────────────────────────────
    classified = []
    for c in clusters:
        cat = classify_cluster(c)
        classified.append((cat, c))

    counts = defaultdict(int)
    for cat, _ in classified:
        counts[cat] += 1
    print("  Classifications:")
    for cat, n in sorted(counts.items()):
        print(f"    {cat}: {n}")

    # ── build merged set ──────────────────────────────────────────────────────
    # Track which poems get absorbed (merged away, not output as standalone)
    absorbed = set()   # id(poem_dict)
    merged_records = []
    log_lines = []
    ambiguous_lines = []

    AUTO_MERGE_CATS = {"encore", "body_match", "fuzzy_confirmed"}

    for cat, c in classified:
        members = c["members"]
        pairs   = c["pairs"]

        if cat in AUTO_MERGE_CATS:
            winner_rec = merge_cluster(members, cat)
            merged_records.append(winner_rec)
            for m in members:
                absorbed.add(id(m))
            log_lines.append(f"MERGE [{cat}]  author={c['author']!r}")
            for m in members:
                log_lines.append(f"  [{m['source']}] {m['date'] or '?'}  {m['title']!r}  {m['source_url']}")
            log_lines.append(f"  → KEPT: [{winner_rec['primary_source']}] {winner_rec['title']!r}")
            log_lines.append("")

        elif cat == "keep_newer":
            # Pick the record with the latest date
            dated = [m for m in members if m["date"]]
            winner = max(dated, key=lambda m: m["date"]) if dated else max(members, key=richness)
            winner_rec = merge_cluster([winner], cat)
            # add provenance for dropped records too
            winner_rec["provenance"] = [{"source": m["source"], "url": m["source_url"], "date": m["date"]} for m in members]
            merged_records.append(winner_rec)
            for m in members:
                absorbed.add(id(m))
            log_lines.append(f"KEEP_NEWER [{cat}]  author={c['author']!r}")
            for m in members:
                kept = " ← KEPT" if m is winner else " (dropped)"
                log_lines.append(f"  [{m['source']}] {m['date'] or '?'}  {m['title']!r}  {m['source_url']}{kept}")
            log_lines.append("")

        elif cat in ("not_dupe_firstline_only", "not_dupe"):
            log_lines.append(f"KEEP_BOTH [not_dupe]  author={c['author']!r}")
            for m in members:
                log_lines.append(f"  [{m['source']}] {m['title']!r}  {m['source_url']}")
            log_lines.append("")

        else:  # ambiguous
            ambiguous_lines.append(f"AMBIGUOUS  author={c['author']!r}")
            for pair in pairs:
                sigs = "+".join(sorted(pair["sigs"]))
                ambiguous_lines.append(f"  signal={sigs}  body_ratio={pair['ratio']:.3f}")
            for m in members:
                ambiguous_lines.append(
                    f"  [{m['source']}] {m['date'] or '?'}  {m['title']!r}"
                    f"  {m['source_url']}"
                )
            ambiguous_lines.append("")

    # Add unmerged poems as singleton records
    for p in poems:
        if id(p) not in absorbed:
            merged_records.append({
                "author":           p["author"],
                "author_raw":       p["author_raw"],
                "title":            p["title"],
                "poem_text":        p["body"],
                "source_book":      p.get("source_book", ""),
                "source_journal":   p.get("source_journal", ""),
                "source_publisher": p.get("source_publisher", ""),
                "source_year":      p.get("source_year", ""),
                "translator":       p.get("translator", ""),
                "primary_source":   p["source"],
                "primary_url":      p["source_url"],
                "published_date":   p["date"],
                "provenance":       [{"source": p["source"], "url": p["source_url"], "date": p["date"]}],
                "merge_reason":     "none",
            })

    # ── live author overlap ───────────────────────────────────────────────────
    live_path = Path(args.live)
    live_authors = []
    if live_path.exists():
        live_data = json.loads(live_path.read_text(encoding="utf-8"))
        scraped_authors = {p["author"] for p in poems}
        seen = set()
        for r in live_data:
            raw = clean(r.get("author", "") or "")
            if raw:
                canon = canonical_author(raw, norm_map)
                if canon in scraped_authors and canon not in seen:
                    live_authors.append(canon)
                    seen.add(canon)
        live_authors.sort()

    # ── write outputs ─────────────────────────────────────────────────────────
    merged_path = out / "dedup_merged.json"
    merged_path.write_text(
        json.dumps(merged_records, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    log_header = [
        "DEDUP MERGE LOG",
        "=" * 72,
        f"Input poems (with text): {len(poems)}",
        f"Output records: {len(merged_records)}",
        f"Poems merged away (net): {len(poems) - len(merged_records)}",
        f"Total absorbed: {len(absorbed)}",
        "",
        "Auto-merge categories:",
        f"  encore              : {counts.get('encore', 0)} clusters",
        f"  body_match          : {counts.get('body_match', 0)} clusters",
        f"  fuzzy_confirmed     : {counts.get('fuzzy_confirmed', 0)} clusters",
        f"  keep_newer          : {counts.get('keep_newer', 0)} clusters",
        f"Not-dupe (kept both) : {counts.get('not_dupe_firstline_only', 0) + counts.get('ambiguous', 0)} clusters",
        f"  - firstline_only    : {counts.get('not_dupe_firstline_only', 0)}",
        f"  - ambiguous/low_sim : {counts.get('ambiguous', 0)}",
        "=" * 72,
        "",
    ]
    log_path = out / "dedup_merge_log.txt"
    log_path.write_text("\n".join(log_header + log_lines), encoding="utf-8")

    amb_path = out / "dedup_ambiguous.txt"
    amb_header = [
        "AMBIGUOUS CLUSTERS — manual review needed",
        f"{counts.get('ambiguous', 0)} clusters: signal fired but body similarity < {BODY_THRESHOLD}",
        "=" * 72,
        "",
    ]
    amb_path.write_text("\n".join(amb_header + ambiguous_lines), encoding="utf-8")

    # ── summary ───────────────────────────────────────────────────────────────
    print()
    print(f"Output poems : {len(merged_records)}")
    print(f"Merged away  : {len(absorbed)}")
    print(f"Wrote: {merged_path}")
    print(f"Wrote: {log_path}")
    print(f"Wrote: {amb_path}")

    print()
    print(f"{'─'*60}")
    print(f"LIVE-DB AUTHOR OVERLAP ({len(live_authors)} authors):")
    for a in live_authors:
        print(f"  {a}")

    print()
    print("DELETED-POEMS CSV: not found in project — skipped.")


if __name__ == "__main__":
    main()
