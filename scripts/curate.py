"""
curate.py — fuzzy-match length_filtered.json against canonical_titles.json,
save curated_corpus.json and curated_counts.txt.

Matching strategy:
  - Preprocess titles: strip outer whitespace, strip surrounding double-quotes,
    strip trailing punctuation, lowercase
  - Use rapidfuzz token_sort_ratio (handles word-order variance, punctuation,
    minor spelling differences) at threshold THRESHOLD
  - Match is within-author only (never cross-match)

Run: .venv/bin/python scripts/curate.py
"""

import json, os, sys
from collections import defaultdict, Counter

try:
    from rapidfuzz import fuzz, process
except ImportError:
    sys.exit("rapidfuzz not found — run: .venv/bin/pip install rapidfuzz")

THRESHOLD = 85

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')


import re
_FOOTNOTE = re.compile(r'[\.\s]*[\[\{]\d+[\]\}][^\w]*$')

def preprocess(title: str) -> str:
    """Normalize a title for fuzzy comparison."""
    t = (title or '').strip()
    # strip surrounding double-quote characters
    if t.startswith('"') and t.endswith('"'):
        t = t[1:-1]
    # strip footnote / annotation markers like .[578], [1], {1} at end
    t = _FOOTNOTE.sub('', t)
    # strip trailing punctuation
    t = t.rstrip('.,!?;:')
    return t.strip().lower()


def best_match_score(title: str, canonical_processed: list[str]) -> float:
    """Return the highest token_sort_ratio against any canonical title."""
    if not canonical_processed:
        return 0.0
    query = preprocess(title)
    result = process.extractOne(
        query,
        canonical_processed,
        scorer=fuzz.token_sort_ratio,
    )
    return result[1] if result else 0.0


def main():
    # Load data
    canonical_path = os.path.join(DATA_DIR, 'canonical_titles.json')
    filtered_path  = os.path.join(DATA_DIR, 'length_filtered.json')

    with open(canonical_path, encoding='utf-8') as f:
        canonical: dict[str, list[str]] = json.load(f)
    with open(filtered_path, encoding='utf-8') as f:
        poems: list[dict] = json.load(f)

    # Pre-process canonical titles per author
    canonical_proc: dict[str, list[str]] = {
        author: [preprocess(t) for t in titles]
        for author, titles in canonical.items()
    }

    # Match
    kept   = []
    skipped_author = 0   # author not in canonical list
    skipped_title  = 0   # author in list but title below threshold

    author_scores: dict[str, list[float]] = defaultdict(list)  # for diagnostics

    for p in poems:
        author = p.get('Author', '')
        title  = p.get('Title',  '')

        if author not in canonical_proc:
            skipped_author += 1
            continue

        score = best_match_score(title, canonical_proc[author])
        author_scores[author].append(score)

        if score >= THRESHOLD:
            kept.append(p)
        else:
            skipped_title += 1

    # Per-author breakdown
    author_kept   = Counter(p['Author'] for p in kept)
    author_total  = Counter()
    for author, scores in author_scores.items():
        author_total[author] = len(scores)

    zero_match = [a for a in canonical_proc if author_kept.get(a, 0) == 0]

    # ── Console report ─────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f" CURATION RESULTS  (threshold={THRESHOLD})")
    print(f"{'='*60}")
    print(f"  Input poems (filtered set) : {len(poems):>6,}")
    print(f"  Skipped — author not in list: {skipped_author:>5,}")
    print(f"  Evaluated against canonical : {len(poems)-skipped_author:>5,}")
    print(f"  Below threshold             : {skipped_title:>5,}")
    print(f"  Kept (curated corpus)       : {len(kept):>5,}")

    print(f"\n── PER-AUTHOR (sorted by kept count) ─────────────────────────")
    print(f"  {'Author':<48}  {'Kept':>5}  {'Avail':>5}")
    print(f"  {'-'*48}  {'-----':>5}  {'-----':>5}")
    for author, cnt in sorted(author_kept.items(), key=lambda x: -x[1]):
        avail = author_total.get(author, 0)
        print(f"  {author[:48]:<48}  {cnt:>5}  {avail:>5}")

    if zero_match:
        print(f"\n── AUTHORS WITH ZERO MATCHES ({len(zero_match)}) ─────────────────────")
        for a in sorted(zero_match):
            avail = author_total.get(a, 0)
            scores = author_scores.get(a, [])
            best = max(scores) if scores else 0
            print(f"  {a}  (poems evaluated: {avail}, best score: {best:.0f})")

    # ── Save outputs ───────────────────────────────────────────────────────
    corpus_path = os.path.join(DATA_DIR, 'curated_corpus.json')
    counts_path = os.path.join(DATA_DIR, 'curated_counts.txt')

    with open(corpus_path, 'w', encoding='utf-8') as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)

    with open(counts_path, 'w', encoding='utf-8') as f:
        f.write(f"# Curated corpus — poems per author (threshold={THRESHOLD})\n")
        f.write(f"# kept\tavailable\tauthor\n")
        for author, cnt in sorted(author_kept.items(), key=lambda x: -x[1]):
            avail = author_total.get(author, 0)
            f.write(f"{cnt}\t{avail}\t{author}\n")

    print(f"\n  Saved → data/curated_corpus.json  ({len(kept):,} poems)")
    print(f"  Saved → data/curated_counts.txt")
    print(f"\n{'='*60}\n")


if __name__ == '__main__':
    main()
