#!/usr/bin/env python3
"""
corpus_clean.py — Clean dedup_scraped_clean.json poem bodies.

Auto-strips (unambiguous non-poem residue):
  1. Slowdown "by Author" first line (72 poems)
  2. Slowdown "Title\\nby Author" prefix block (18 poems)
  3. Slowdown copyright/attribution tails (2 poems)
  4. Poetry Daily "In Memoriam" editorial blocks (2 poems)
  5. Encoding artifacts: latin1-misread UTF-8 (Ã© → é etc.) (8 poems)
  6. Non-breaking spaces \\xa0 → regular space (66 poems)

Keeps (shown in report, not removed):
  - Epigraphs with em-dash attributions (part of the poem)

Output:
  dedup_cleaned.json      — cleaned corpus
  corpus_clean_report.txt — what was changed + epigraph samples
"""

import json, re, unicodedata
from pathlib import Path

SCRIPTS  = Path(__file__).parent
IN_PATH  = SCRIPTS / "dedup_scraped_clean.json"
OUT_PATH = SCRIPTS / "dedup_cleaned.json"
RPT_PATH = SCRIPTS / "corpus_clean_report.txt"


# ── encoding fix ──────────────────────────────────────────────────────────────

def fix_encoding(text):
    """Fix latin1-misread UTF-8 (e.g. Ã© → é)."""
    try:
        return text.encode("latin1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


def needs_encoding_fix(text):
    return 'Ã' in text and bool(re.search(r'Ã[\x80-\xff]', text))


# ── slowdown prefix strip ─────────────────────────────────────────────────────

def strip_slowdown_prefix(text):
    """
    Strip leading "by Author" or "Title\\nby Author" from Slowdown bodies.
    Returns (cleaned_text, description_of_what_was_stripped | None).
    """
    stripped = text.strip()
    lines = stripped.splitlines()
    if not lines:
        return text, None

    # Case 1: first line is "by Author Name"
    if re.match(r'^by\s+\S', lines[0], re.IGNORECASE):
        rest = "\n".join(lines[1:]).strip()
        return rest, f"stripped leading 'by ...' line: {lines[0]!r}"

    # Case 2: first line is the title, second is "by Author Name"
    if (len(lines) >= 2
            and re.match(r'^by\s+\S', lines[1].strip(), re.IGNORECASE)
            and not re.match(r'^by\s+\S', lines[0].strip(), re.IGNORECASE)):
        rest = "\n".join(lines[2:]).strip()
        return rest, f"stripped title+by-author block: {lines[0]!r} / {lines[1].strip()!r}"

    return text, None


# ── slowdown copyright tail ───────────────────────────────────────────────────

def strip_slowdown_copyright(text, source):
    """Strip trailing copyright/attribution line from Slowdown poems."""
    if source != "slowdown":
        return text, None
    # Match: final line matching "Title" from [Book] by Author. Copyright © ...
    pat = re.compile(
        r'\n+"[^"]+"\s+from\s+.*?by\s+\S.*?[Cc]opyright\s*©.*$',
        re.DOTALL
    )
    m = pat.search(text)
    if m and m.start() > len(text) * 0.7:
        cleaned = text[:m.start()].rstrip()
        return cleaned, f"stripped copyright tail: {text[m.start():][:80]!r}..."
    return text, None


# ── poetry daily editorial block ──────────────────────────────────────────────

def strip_pd_editorial(text, source):
    """Strip Poetry Daily 'In Memoriam' editorial blocks appended after poem."""
    if source != "poetrydaily":
        return text, None
    pat = re.compile(r'\n\s*\n\s*[ ]*\n\s*\*{3,}\s*\n\s*In Memoriam\b', re.IGNORECASE)
    m = pat.search(text)
    if m:
        cleaned = text[:m.start()].rstrip()
        return cleaned, "stripped 'In Memoriam' editorial block"
    return text, None


# ── nbsp fix ──────────────────────────────────────────────────────────────────

def fix_nbsp(text):
    return text.replace('\xa0', ' ')


# ── epigraph detection (report only, not removed) ────────────────────────────

def has_leading_epigraph(text, source):
    """Return the attribution line if poem has a leading em-dash epigraph."""
    if source != "slowdown":
        return None
    stripped = text.strip()
    # Strip by-author prefix first
    lines = stripped.splitlines()
    start = 0
    if lines and re.match(r'^by\s+\S', lines[0], re.IGNORECASE):
        start = 1
    elif len(lines) >= 2 and re.match(r'^by\s+\S', lines[1].strip(), re.IGNORECASE):
        start = 2

    for li, line in enumerate(lines[start:start+15]):
        if re.match(r'^\s*—\s*[A-Za-z\[]', line):
            return line.strip()
    return None


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading corpus...")
    data = json.loads(IN_PATH.read_text(encoding="utf-8"))
    print(f"  {len(data)} records")

    cleaned_records = []
    changes = []        # (i, record, list-of-change-descriptions)
    epigraphs = []      # (record, attribution_line) — kept, shown in report

    for i, rec in enumerate(data):
        orig_text = rec.get("poem_text", "") or ""
        text = orig_text
        rec_changes = []
        source = rec.get("primary_source", "")

        # 1. Encoding fix
        if needs_encoding_fix(text):
            fixed = fix_encoding(text)
            if fixed != text:
                rec_changes.append(f"fixed encoding artifacts")
                text = fixed

        # 2. Non-breaking spaces
        if '\xa0' in text:
            text = fix_nbsp(text)
            rec_changes.append("replaced \\xa0 with space")

        # 3. Slowdown copyright tail (before prefix strip, so we work on raw text)
        text, change = strip_slowdown_copyright(text, source)
        if change:
            rec_changes.append(change)

        # 4. Poetry Daily editorial block
        text, change = strip_pd_editorial(text, source)
        if change:
            rec_changes.append(change)

        # 5. Slowdown prefix (after other cleanups so prefix detection is clean)
        if source == "slowdown":
            text, change = strip_slowdown_prefix(text)
            if change:
                rec_changes.append(change)

        # 6. Final whitespace normalisation
        text = text.strip()

        # Track epigraphs (not stripped, just noted)
        epig = has_leading_epigraph(text, source)
        if epig:
            epigraphs.append((rec, epig))

        new_rec = dict(rec)
        new_rec["poem_text"] = text
        cleaned_records.append(new_rec)

        if rec_changes:
            changes.append((i, rec, rec_changes))

    # Write cleaned corpus
    OUT_PATH.write_text(
        json.dumps(cleaned_records, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"Wrote {len(cleaned_records)} cleaned records → {OUT_PATH}")

    # Write report
    report_lines = [
        "CORPUS CLEANING REPORT",
        "=" * 72,
        f"Input records : {len(data)}",
        f"Output records: {len(cleaned_records)}",
        f"Records changed: {len(changes)}",
        "",
        "AUTO-STRIPPED CHANGES",
        "─" * 72,
        "",
    ]

    by_type = {}
    for i, rec, clist in changes:
        for c in clist:
            key = re.sub(r':.+', '', c)  # normalise to category
            by_type.setdefault(key, []).append((rec, c))

    for cat, items in sorted(by_type.items()):
        report_lines.append(f"[{len(items)}]  {cat}")
        for rec, detail in items[:3]:
            report_lines.append(f"    [{rec['primary_source']}] {rec['author']!r} — {rec['title']!r}")
            report_lines.append(f"      {detail}")
        if len(items) > 3:
            report_lines.append(f"    ... and {len(items)-3} more")
        report_lines.append("")

    report_lines += [
        "",
        "EPIGRAPHS — KEPT (shown for review, not removed)",
        "─" * 72,
        f"{len(epigraphs)} Slowdown poems have a leading em-dash attribution.",
        "These are legitimate poetic elements. Confirm to remove or keep.",
        "",
    ]
    for rec, epig in epigraphs:
        body = rec["poem_text"]
        # Show a few lines of context
        first_poem_lines = [l for l in body.splitlines() if l.strip()][:3]
        report_lines.append(f"  [{rec['title']!r}] by {rec['author']}")
        report_lines.append(f"    attribution: {epig!r}")
        report_lines.append(f"    poem opens: {first_poem_lines[0]!r}")
        report_lines.append("")

    RPT_PATH.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"Wrote report → {RPT_PATH}")

    print(f"\nSummary of changes:")
    for cat, items in sorted(by_type.items()):
        print(f"  {len(items):3d}  {cat}")
    print(f"  {len(epigraphs):3d}  epigraphs kept (not removed)")


if __name__ == "__main__":
    main()
