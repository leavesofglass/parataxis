"""
clean_corpus.py — applies targeted fixes to a curated poetry corpus JSON file.

Fixes applied (in order):
  1. Remove poems with missing/empty title, author, or text
  2. Strip parenthetical editor notes from the start of poem text
  3. Fix encoding artifacts: backtick → apostrophe, \xa0 → space
  4. Strip footnote/annotation markers from titles
  5. Remove near-identical text duplicates (same first 200 normalised chars)
  6. Remove clearly prose items (low newline density, long text)

IDs are preserved as-is; no renumbering.

Run:
  .venv/bin/python scripts/clean_corpus.py data/corpus_full_746.json data/corpus_full_clean.json
  .venv/bin/python scripts/clean_corpus.py data/corpus_screenshot_250.json data/corpus_screenshot_clean.json
"""

import json, re, sys, os
from collections import defaultdict


# ── Regex patterns ────────────────────────────────────────────────────────────

# Footnote/annotation markers in titles: [1], [578], .[603], ,[59]
TITLE_FOOTNOTE = re.compile(r'[\s.,]*[\[\{]\d+[\]\}]\s*$')

# Parenthetical first line that is an editor/publication note.
# Matches when the ENTIRE first non-empty line is a parenthetical.
# e.g. "(Lines on the loss of the Titanic)" or "(Hindenburg Line, April 1917.)"
# We accept up to ~200 chars to handle long subtitles but reject very short
# ones that might be part of the poem (dialogue markers, etc.).
PAREN_EDITOR_LINE = re.compile(r'^\s*\([^\)]{8,200}\)\s*$')


# ── Helpers ───────────────────────────────────────────────────────────────────

def nonempty_lines(text: str) -> int:
    return sum(1 for l in (text or '').split('\n') if l.strip())

def newline_density(text: str) -> float:
    if not text:
        return 0.0
    return text.count('\n') / len(text) * 1000

def norm_text_key(text: str) -> str:
    """Normalise first 200 chars for duplicate detection."""
    return re.sub(r'\s+', ' ', (text or '')[:200].strip().lower())


# ── Per-fix functions ─────────────────────────────────────────────────────────

def fix_missing_fields(poems: list) -> tuple[list, list]:
    """Remove poems with empty title, author, or text."""
    kept, removed = [], []
    for p in poems:
        if (p.get('Title', '').strip()
                and p.get('Author', '').strip()
                and p.get('text', '').strip()):
            kept.append(p)
        else:
            removed.append(p)
    return kept, removed


def fix_editor_notes(poems: list) -> tuple[list, int]:
    """Strip parenthetical editor notes from the start of poem text."""
    changed = 0
    for p in poems:
        text = p.get('text', '')
        lines = text.split('\n')
        # Find the first non-empty line
        first_idx = next((i for i, l in enumerate(lines) if l.strip()), None)
        if first_idx is None:
            continue
        first_line = lines[first_idx]
        if PAREN_EDITOR_LINE.match(first_line):
            # Remove that line (and any immediately following blank line)
            new_lines = lines[:first_idx] + lines[first_idx + 1:]
            # Trim leading blank lines left after removal
            while new_lines and not new_lines[0].strip():
                new_lines = new_lines[1:]
            p['text'] = '\n'.join(new_lines)
            changed += 1
    return poems, changed


def fix_encoding(poems: list) -> tuple[list, int]:
    """Fix backtick→apostrophe and \xa0→space encoding artifacts."""
    changed = 0
    for p in poems:
        original = p.get('text', '')
        fixed = original.replace('\xa0', ' ').replace('`', "'")
        if fixed != original:
            p['text'] = fixed
            changed += 1
    return poems, changed


def fix_title_footnotes(poems: list) -> tuple[list, int]:
    """Strip footnote/annotation markers from titles."""
    changed = 0
    for p in poems:
        original = p.get('Title', '')
        cleaned = TITLE_FOOTNOTE.sub('', original)
        if cleaned != original:            # only strip trailing punct when we removed a marker
            cleaned = cleaned.rstrip(' ,.')
            p['Title'] = cleaned
            changed += 1
    return poems, changed


def fix_duplicates(poems: list) -> tuple[list, list]:
    """
    Remove near-identical text duplicates.
    For each group sharing a normalised text key, keep the poem with the
    longest text (most complete); on tie keep the first encountered.
    """
    groups: dict[str, list] = defaultdict(list)
    for p in poems:
        key = norm_text_key(p.get('text', ''))
        if len(key) >= 50:   # ignore very short poems from dedup
            groups[key].append(p)

    drop_ids: set = set()
    for key, group in groups.items():
        if len(group) < 2:
            continue
        # Keep the one with the most text; break ties by original order (stable)
        group.sort(key=lambda x: -len(x.get('text', '')))
        for dup in group[1:]:
            drop_ids.add(dup['id'])

    kept    = [p for p in poems if p['id'] not in drop_ids]
    removed = [p for p in poems if p['id'] in drop_ids]
    return kept, removed


def fix_prose(poems: list) -> tuple[list, list]:
    """Remove poems that look like prose (long, very low newline density)."""
    kept, removed = [], []
    for p in poems:
        text = p.get('text', '')
        if len(text) > 1000 and newline_density(text) < 5 and nonempty_lines(text) < 6:
            removed.append(p)
        else:
            kept.append(p)
    return kept, removed


# ── Main ──────────────────────────────────────────────────────────────────────

def clean(input_path: str, output_path: str):
    with open(input_path, encoding='utf-8') as f:
        poems = json.load(f)

    original_count = len(poems)
    stats = {}

    poems, removed_missing = fix_missing_fields(poems)
    stats['removed_missing_fields'] = len(removed_missing)

    poems, n_editor = fix_editor_notes(poems)
    stats['editor_notes_stripped'] = n_editor

    poems, n_enc = fix_encoding(poems)
    stats['encoding_artifacts_fixed'] = n_enc

    poems, n_foot = fix_title_footnotes(poems)
    stats['title_footnotes_stripped'] = n_foot

    poems, removed_dups = fix_duplicates(poems)
    stats['duplicates_removed'] = len(removed_dups)

    poems, removed_prose = fix_prose(poems)
    stats['prose_removed'] = len(removed_prose)

    final_count = len(poems)
    stats['total_removed'] = original_count - final_count
    stats['final_count'] = final_count

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(poems, f, ensure_ascii=False, indent=2)

    # ── Report ─────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f" CORPUS CLEAN  {os.path.basename(input_path)} → {os.path.basename(output_path)}")
    print(f"{'='*60}")
    print(f"  Input  : {original_count:,} poems")
    print(f"  Output : {final_count:,} poems")
    print()
    print(f"  Changes / removals:")
    print(f"    Missing or empty fields removed : {stats['removed_missing_fields']}")
    print(f"    Editor notes stripped from text : {stats['editor_notes_stripped']}")
    print(f"    Encoding artifacts fixed (text) : {stats['encoding_artifacts_fixed']}")
    print(f"    Title footnotes stripped        : {stats['title_footnotes_stripped']}")
    print(f"    Near-identical duplicates removed: {stats['duplicates_removed']}")
    if removed_dups:
        for p in removed_dups:
            print(f"      dropped {p['id']} | {p['Author'][:28]} | {p['Title'][:40]}")
    print(f"    Prose items removed             : {stats['prose_removed']}")
    print(f"  ─────────────────────────────────────────────────────")
    print(f"  Net removed : {stats['total_removed']}")
    print(f"\n  Saved → {output_path}")
    print(f"{'='*60}\n")

    return stats


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit("Usage: clean_corpus.py <input.json> <output.json>")
    clean(sys.argv[1], sys.argv[2])
