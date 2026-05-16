"""
finalize.py — applies a 20-poem-per-author hard cap to the curated corpus,
expands Dickinson's canonical list, and drops Schiller + Hugo.

Priority within cap (lower sort key = higher priority):
  1. Exact title match (preprocessed poem title in canonical set for that author)
  2. Higher fuzzy match score (closer to a canonical title)
  3. Medium line count (sweet spot 10–35 lines for phone-screen reading)
  4. Medium char count (sweet spot 400–2 000 chars)

Output: data/curated_corpus_v2.json  +  data/curated_counts_v2.txt

Run: .venv/bin/python scripts/finalize.py
"""

import json, os, sys, re
from collections import defaultdict, Counter

try:
    from rapidfuzz import fuzz, process
except ImportError:
    sys.exit("rapidfuzz not found — run: .venv/bin/pip install rapidfuzz")

CAP       = 20
THRESHOLD = 85

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

# ── Authors to drop entirely ─────────────────────────────────────────────────
DROP_AUTHORS = {"Friedrich Schiller", "Victor-Marie Hugo"}

# ── Dickinson expanded canonical list ────────────────────────────────────────
# Uses BOTH standard first-line forms AND this dataset's alternate titles.
DICKINSON_CANONICAL = [
    # ── canonical first-line titles (standard forms) ────────────────────────
    "Because I could not stop for Death",
    "I heard a Fly buzz - when I died",
    "I heard a Fly buzz when I died",
    "Hope is the thing with feathers",
    "I'm Nobody! Who are you?",
    "I'm Nobody!",                              # dataset drops second half
    "Tell all the truth but tell it slant",
    "After great pain, a formal feeling comes",
    "Success is counted sweetest",
    "This is my letter to the World",
    "A narrow Fellow in the Grass",
    "Safe in their Alabaster Chambers",
    "Much Madness is Divinest Sense",
    "I dwell in Possibility",
    "There's a certain Slant of light",
    "Wild Nights - Wild Nights!",
    "Wild Nights! Wild Nights!",                # dataset punctuation variant
    "The Brain - is wider than the Sky",
    "I died for Beauty - but was scarce",
    "I died for Beauty, but was scarce",
    "I felt a Funeral, in my Brain",
    "I felt a Funeral in my Brain",
    "The Soul selects her own Society",
    "One need not be a Chamber - to be Haunted",
    "I like to see it lap the Miles",
    "Pain - has an Element of Blank",
    "My Life had stood - a Loaded Gun",
    "There is no Frigate like a Book",
    "Some keep the Sabbath going to Church",
    "Apparently with no surprise",
    "The Heart asks Pleasure - first",
    "I taste a liquor never brewed",
    "I never saw a Moor",
    "I never lost as much but twice",
    "I never lost as much but twice,",
    "The Bustle in a House",
    "If I can stop one Heart from breaking",
    "This World is not Conclusion",
    "Death is a Dialogue between",
    "I know that He exists",
    "What Soft, Cherubic Creatures",
    "Surgeons must be very careful",
    # ── dataset-specific alternate titles ────────────────────────────────────
    "The Chariot",                  # = Because I could not stop for Death
    "The Railway Train",            # = I like to see it lap the Miles
    "The Snake",                    # = A narrow Fellow in the Grass
    "The Brain",                    # = The Brain—is wider than the Sky
    "The Heart Asks Pleasure First",# = The Heart asks Pleasure—first
    # ── Johnson / Franklin number forms (user request; won't match but documented)
    "J712", "J465", "J254", "J288", "J1129", "J341", "J67",
    "Fr479", "Fr591", "Fr314", "Fr288", "Fr1263", "Fr372", "Fr112",
]

# ── Preprocessing ─────────────────────────────────────────────────────────────
_FOOTNOTE = re.compile(r'[\.\s]*[\[\{]\d+[\]\}][^\w]*$')

def preprocess(title: str) -> str:
    t = (title or '').strip()
    if t.startswith('"') and t.endswith('"'):
        t = t[1:-1]
    t = _FOOTNOTE.sub('', t)
    return t.rstrip('.,!?;:').strip().lower()


# ── Priority scoring ──────────────────────────────────────────────────────────
def line_score(n: int) -> int:
    """Higher = more desirable line count for reading on a phone screen."""
    if n < 5:   return 0
    if n < 10:  return 1
    if n <= 35: return 3   # sweet spot
    if n <= 45: return 2
    return 1               # 46–50 border cases

def char_score(n: int) -> int:
    if n < 150:  return 0
    if n < 400:  return 1
    if n < 2000: return 3   # sweet spot
    if n < 5000: return 2
    return 1

def nonempty_lines(text: str) -> int:
    return len([l for l in (text or '').split('\n') if l.strip()])


def main():
    # ── Load canonical list ───────────────────────────────────────────────────
    canonical_path = os.path.join(DATA_DIR, 'canonical_titles.json')
    filtered_path  = os.path.join(DATA_DIR, 'length_filtered.json')

    with open(canonical_path, encoding='utf-8') as f:
        canonical: dict = json.load(f)
    with open(filtered_path, encoding='utf-8') as f:
        poems: list = json.load(f)

    # Apply overrides
    canonical["Emily Elizabeth Dickinson"] = DICKINSON_CANONICAL
    for a in DROP_AUTHORS:
        canonical.pop(a, None)

    # Pre-process canonical sets
    canonical_proc  = {a: [preprocess(t) for t in titles]
                       for a, titles in canonical.items()}
    canonical_sets  = {a: set(ts) for a, ts in canonical_proc.items()}

    # ── Match every poem ──────────────────────────────────────────────────────
    scored: dict[str, list] = defaultdict(list)

    for p in poems:
        author = p.get('Author', '')
        title  = p.get('Title',  '')
        text   = p.get('text',   '') or ''

        if author not in canonical_proc:
            continue

        ptitle = preprocess(title)
        best   = process.extractOne(
            ptitle, canonical_proc[author], scorer=fuzz.token_sort_ratio
        )
        score = best[1] if best else 0
        if score < THRESHOLD:
            continue

        is_exact = ptitle in canonical_sets[author]
        n_lines  = nonempty_lines(text)
        n_chars  = len(text)

        # Sort key: lower = higher priority
        sort_key = (
            0 if is_exact else 1,        # exact first
            -score,                       # higher match score first
            -line_score(n_lines),         # better line count first
            -char_score(n_chars),         # better char count first
        )

        scored[author].append((sort_key, p))

    # ── Apply cap ─────────────────────────────────────────────────────────────
    kept    = []
    capped  = {}  # author → (kept, total_matched)

    for author, entries in scored.items():
        entries.sort(key=lambda x: x[0])
        total = len(entries)
        taken = entries[:CAP]
        kept.extend(p for _, p in taken)
        capped[author] = (len(taken), total)

    # ── Report ────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f" FINAL CORPUS (cap={CAP})   {len(kept):,} poems total")
    print(f"{'='*60}")

    cap_triggered = {a: (k, t) for a, (k, t) in capped.items() if t > CAP}
    no_match      = [a for a in canonical if a not in capped]

    print(f"\n── ALL AUTHORS (kept / matched) ──────────────────────────────")
    print(f"  {'Author':<48}  {'Kept':>5}  {'Matched':>7}  {'Capped':>6}")
    print(f"  {'-'*48}  {'-----':>5}  {'-------':>7}  {'------':>6}")
    for a, (k, t) in sorted(capped.items(), key=lambda x: -x[1][0]):
        flag = " ◀ CAP" if t > CAP else ""
        print(f"  {a[:48]:<48}  {k:>5}  {t:>7}  {flag}")

    if no_match:
        print(f"\n── ZERO MATCHES ({len(no_match)}) ───────────────────────────────────")
        for a in sorted(no_match):
            reason = "0 poems pass 50-line filter" if a in {
                "Dante Alighieri","James Hogg","Sophocles"
            } else "title format mismatch"
            print(f"  {a}  ({reason})")

    print(f"\n── CAP TRIGGERED ({len(cap_triggered)}) ─────────────────────────────────────")
    for a, (k, t) in sorted(cap_triggered.items(), key=lambda x: -x[1][1]):
        print(f"  {a}:  kept {k} of {t} matched")

    print(f"\n  TOTAL: {len(kept):,} poems across {len(capped)} authors")

    # ── Save ──────────────────────────────────────────────────────────────────
    author_counts = Counter(p['Author'] for p in kept)

    corpus_path = os.path.join(DATA_DIR, 'curated_corpus_v2.json')
    counts_path = os.path.join(DATA_DIR, 'curated_counts_v2.txt')

    with open(corpus_path, 'w', encoding='utf-8') as f:
        json.dump(kept, f, ensure_ascii=False, indent=2)

    with open(counts_path, 'w', encoding='utf-8') as f:
        f.write(f"# Curated corpus v2 — cap={CAP}, threshold={THRESHOLD}\n")
        f.write(f"# kept\tmatched\tauthor\n")
        for a, (k, t) in sorted(capped.items(), key=lambda x: -x[1][0]):
            f.write(f"{k}\t{t}\t{a}\n")

    print(f"\n  Saved → data/curated_corpus_v2.json")
    print(f"  Saved → data/curated_counts_v2.txt")
    print(f"\n{'='*60}\n")


if __name__ == '__main__':
    main()
