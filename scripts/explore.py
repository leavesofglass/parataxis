"""
explore.py — exploratory analysis of the public-domain-poetry dataset.
Run from the repo root:  python3 scripts/explore.py
Outputs:
  - console report
  - data/authors.txt  (authors ranked by poem count)
"""

import json
import os
import sys
import unicodedata
from collections import Counter, defaultdict
from statistics import mean, median, stdev

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'poems.json')
AUTHORS_OUT = os.path.join(os.path.dirname(__file__), '..', 'data', 'authors.txt')

# ── length buckets ──────────────────────────────────────────────────────────
VERY_SHORT_CHARS = 150    # fewer than this → likely a fragment / haiku / epigram
SHORT_CHARS      = 500
MEDIUM_CHARS     = 2_000
LONG_CHARS       = 5_000
# ≥ LONG_CHARS → very long (possible prose)

PROSE_SUSPICION_CHARS = 8_000   # above this AND few newlines → possibly prose


def char_length(text: str) -> int:
    return len(text or '')


def newline_density(text: str) -> float:
    """Newlines per 1000 characters.  Poetry should be high (>30).  Prose is low."""
    if not text:
        return 0.0
    return text.count('\n') / len(text) * 1_000


def has_control_chars(text: str) -> bool:
    for ch in (text or ''):
        cat = unicodedata.category(ch)
        if cat.startswith('C') and ch not in ('\n', '\r', '\t'):
            return True
    return False


def looks_like_prose(text: str) -> bool:
    if not text or len(text) < PROSE_SUSPICION_CHARS:
        return False
    density = newline_density(text)
    return density < 10.0   # very few line-breaks for a very long piece


def load_data(path: str):
    print(f"Loading {path} …", flush=True)
    with open(path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    # Dataset is a list of dicts: {"Title": ..., "Author": ..., "text": ...}
    return raw


def bucket_name(n_chars: int) -> str:
    if n_chars < VERY_SHORT_CHARS:
        return 'very short  (<150 chars)'
    if n_chars < SHORT_CHARS:
        return 'short       (150–499)'
    if n_chars < MEDIUM_CHARS:
        return 'medium      (500–1999)'
    if n_chars < LONG_CHARS:
        return 'long        (2000–4999)'
    return 'very long   (≥5000)'


def fmt(n: int, total: int) -> str:
    return f"{n:>7,}  ({n/total*100:5.1f}%)"


def main():
    poems = load_data(DATA_FILE)
    total = len(poems)
    print(f"\n{'='*60}")
    print(f" PUBLIC-DOMAIN POETRY — EXPLORATORY ANALYSIS")
    print(f"{'='*60}")
    print(f"\nTotal poems: {total:,}\n")

    # ── per-poem metrics ────────────────────────────────────────────────────
    author_counts   = Counter()
    length_buckets  = Counter()
    lengths         = []

    issues = defaultdict(list)   # issue_type → list of (index, title, author)

    seen_texts      = {}   # normalized_text → first index
    seen_title_auth = {}   # (title, author) → first index

    for i, p in enumerate(poems):
        title  = p.get('Title',  '')
        author = p.get('Author', '')
        text   = p.get('text',   '')

        # Normalize for duplicate checks
        norm_text = (text or '').strip().lower()
        key_ta    = ((title or '').strip().lower(), (author or '').strip().lower())

        # ── author counting ────────────────────────────────────────────────
        author_counts[author or '(blank)'] += 1

        # ── length ────────────────────────────────────────────────────────
        n = char_length(text)
        lengths.append(n)
        length_buckets[bucket_name(n)] += 1

        # ── quality checks ────────────────────────────────────────────────
        if not text or not text.strip():
            issues['empty_text'].append((i, title, author))

        if not title or not title.strip():
            issues['missing_title'].append((i, title, author))

        if not author or not author.strip():
            issues['missing_author'].append((i, title, author))

        if has_control_chars(text):
            issues['control_chars'].append((i, title, author))

        if norm_text and norm_text in seen_texts:
            issues['duplicate_text'].append((i, title, author, seen_texts[norm_text]))
        elif norm_text:
            seen_texts[norm_text] = i

        if key_ta[0] and key_ta in seen_title_auth:
            issues['duplicate_title_author'].append((i, title, author, seen_title_auth[key_ta]))
        elif key_ta[0]:
            seen_title_auth[key_ta] = i

        if looks_like_prose(text):
            issues['possible_prose'].append((i, title, author))

    # ── LENGTH DISTRIBUTION ─────────────────────────────────────────────────
    print("── LENGTH DISTRIBUTION (by character count) ──────────────────")
    bucket_order = [
        'very short  (<150 chars)',
        'short       (150–499)',
        'medium      (500–1999)',
        'long        (2000–4999)',
        'very long   (≥5000)',
    ]
    for b in bucket_order:
        print(f"  {b}: {fmt(length_buckets[b], total)}")

    if lengths:
        print(f"\n  avg length : {mean(lengths):>8,.0f} chars")
        print(f"  median     : {median(lengths):>8,.0f} chars")
        print(f"  stdev      : {stdev(lengths):>8,.0f} chars")
        print(f"  min        : {min(lengths):>8,} chars")
        print(f"  max        : {max(lengths):>8,} chars")

    # ── DATA QUALITY ────────────────────────────────────────────────────────
    print(f"\n── DATA QUALITY ISSUES ────────────────────────────────────────")
    quality_labels = {
        'empty_text':            'Empty / blank text',
        'missing_title':         'Missing title',
        'missing_author':        'Missing author',
        'control_chars':         'Control chars in text',
        'duplicate_text':        'Exact text duplicates',
        'duplicate_title_author':'Same title+author (possible dup)',
        'possible_prose':        f'Possible prose (≥{PROSE_SUSPICION_CHARS} chars, low newline density)',
    }
    any_issues = False
    for key, label in quality_labels.items():
        n = len(issues[key])
        if n:
            any_issues = True
            print(f"  {label:45s}: {n:,}")
    if not any_issues:
        print("  None detected.")

    # Spot-check: show a few examples of each serious issue
    for key in ('empty_text', 'duplicate_text', 'possible_prose'):
        examples = issues[key][:3]
        if examples:
            print(f"\n  Sample — {quality_labels[key]}:")
            for ex in examples:
                idx = ex[0]; title = ex[1]; author = ex[2]
                print(f"    [{idx}] \"{title[:60]}\"  by {author[:40]}")

    # ── AUTHORS ─────────────────────────────────────────────────────────────
    print(f"\n── AUTHOR BREAKDOWN ───────────────────────────────────────────")
    print(f"  Unique authors : {len(author_counts):,}")
    top = author_counts.most_common(20)
    print(f"\n  Top 20 by poem count:")
    print(f"    {'Author':<45} {'Poems':>6}  {'Share':>6}")
    print(f"    {'-'*45}  {'-'*6}  {'-'*6}")
    for auth, cnt in top:
        print(f"    {auth[:45]:<45} {cnt:>6,}  {cnt/total*100:>5.1f}%")

    single = sum(1 for c in author_counts.values() if c == 1)
    print(f"\n  Authors with only 1 poem : {single:,}  ({single/len(author_counts)*100:.0f}% of authors)")

    # ── WRITE AUTHORS FILE ───────────────────────────────────────────────────
    with open(AUTHORS_OUT, 'w', encoding='utf-8') as f:
        f.write(f"# Public-domain-poetry authors ranked by poem count\n")
        f.write(f"# Total poems: {total:,}  |  Unique authors: {len(author_counts):,}\n")
        f.write(f"# Columns: rank, poem_count, author\n\n")
        for rank, (auth, cnt) in enumerate(author_counts.most_common(), start=1):
            f.write(f"{rank:>5}  {cnt:>5}  {auth}\n")
    print(f"\n  Authors file written → data/authors.txt")

    print(f"\n{'='*60}\n")


if __name__ == '__main__':
    main()
