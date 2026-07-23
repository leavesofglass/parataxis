"""
bilingual_filter.py — drop non-English halves of bilingual pairs from dedup_cleaned.json.

Rules applied per bilingual group (linked by bilingual_group_id in ralp_parsed.json):

  1. If exactly one record in the pair has a credited translator ("Translated by …")
     AND that record has an ASCII title (i.e. it IS the English translation):
       → keep it; drop the source-language original.

  2. If exactly one record has a credited translator but its title is non-ASCII
     (e.g. Olivarez: English is the original; the credited record is a Spanish
     translation of an English poem):
       → keep the uncredited English original; drop the non-English translation.

  3. If neither record has a credited translator:
       → drop both (e.g. Darwish "On this Land", Auvaiyar "Untitled").

The translator field in the output is normalised:
  "Translated by Jane Smith"  →  "Jane Smith"
  ""                          →  ""   (non-translations or English originals)

Input:  scripts/dedup_enriched.json  +  scripts/ralp_parsed.json
Output: scripts/dedup_filtered.json
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

SCRIPTS = Path(__file__).parent
CLEANED_PATH  = SCRIPTS / "dedup_enriched.json"
RALP_PATH     = SCRIPTS / "ralp_parsed.json"
OUTPUT_PATH   = SCRIPTS / "dedup_filtered.json"


# Typographic characters that appear in English text (smart quotes, dashes, ellipsis, NBSP).
_TYPOGRAPHIC = frozenset(
    '‘’“”'   # ' ' " "
    '–—'               # – —
    '…'                     # …
    ' '                     # non-breaking space
)


def is_likely_english(text: str) -> bool:
    """True if the poem body appears to be primarily in English.

    Allows common typographic Unicode (smart quotes, dashes) while treating
    combining diacritics, non-Latin scripts, and precomposed accented letters
    as signs of a non-English text.
    """
    foreign_chars = [c for c in (text or "") if ord(c) >= 128 and c not in _TYPOGRAPHIC]
    return len(foreign_chars) <= 2


def norm_translator(raw: str) -> str:
    """Strip all leading 'Translated by ' prefixes; return the bare name(s)."""
    s = (raw or "").strip()
    while s.lower().startswith("translated by "):
        s = s[len("translated by "):].strip()
    return s


def build_decisions(ralp: list[dict]) -> dict:
    """
    Returns a dict keyed by RALP source_url with the keep decision for each
    bilingual pair at that URL:

      {'drop_all': True}
        — drop every record from dedup_cleaned that came from this URL

      {'drop_all': False, 'keep_title': str, 'keep_translator_raw': str}
        — keep only the record whose (title, translator) matches these values;
          drop any sibling records from the same URL.
    """
    bil = [p for p in ralp if p.get("bilingual_group_id")]

    groups: dict[str, list[dict]] = defaultdict(list)
    for p in bil:
        prefix = p["bilingual_group_id"].rsplit("-", 1)[0]
        groups[prefix].append(p)

    decisions: dict[str, dict] = {}

    for prefix, records in groups.items():
        url = records[0]["source_url"]
        credited   = [r for r in records if (r.get("translator") or "").startswith("Translated by")]
        uncredited = [r for r in records if not (r.get("translator") or "").startswith("Translated by")]

        if len(credited) == 0:
            # No translator on either side → drop both
            decisions[url] = {"drop_all": True}
            print(f"  DROP BOTH  {prefix}  ({records[0].get('poet_name')}) — no translator credited")

        elif len(credited) == 1:
            cred   = credited[0]
            uncred = uncredited[0] if uncredited else None
            title  = cred.get("poem_title") or ""

            if is_likely_english(cred.get("poem_text") or ""):
                # Standard case: the credited record is the English translation.
                decisions[url] = {
                    "drop_all": False,
                    "keep_title":          title,
                    "keep_translator_raw": cred["translator"],
                }
                drop_title = (uncred or {}).get("poem_title", "?")
                print(f"  KEEP TRANS {prefix}  keep={repr(title[:40])}  drop={repr(drop_title[:40])}")
            else:
                # Credited record is non-English (e.g. Olivarez: Spanish translation
                # of an English original). The uncredited record is the English original.
                if uncred:
                    decisions[url] = {
                        "drop_all": False,
                        "keep_title":          uncred.get("poem_title") or "",
                        "keep_translator_raw": "",   # it's the original; no translator
                    }
                    keep_t = (uncred.get("poem_title") or "")[:40]
                    print(f"  KEEP ORIG  {prefix}  keep={repr(keep_t)}  drop={repr(title[:40])}")
                else:
                    decisions[url] = {"drop_all": True}
                    print(f"  DROP BOTH  {prefix}  (no English record found)")

        else:
            # Multiple credited records — shouldn't occur in this corpus
            print(f"  WARNING    {prefix}  multiple credited translators at {url}; skipping")

    return decisions


def should_drop(poem: dict, decisions: dict) -> bool:
    if poem.get("primary_source") != "ralp":
        return False
    url = poem.get("primary_url")
    if url not in decisions:
        return False

    dec = decisions[url]
    if dec.get("drop_all"):
        return True

    keep_title = dec["keep_title"]
    keep_trans = dec["keep_translator_raw"]

    poem_title = poem.get("title") or ""
    poem_trans = poem.get("translator") or ""

    # Match on both title and raw translator to distinguish same-title pairs
    # (e.g. Mohidin "Maya" where both records share the title).
    return not (poem_title == keep_title and poem_trans == keep_trans)


def apply_translator_norm(poem: dict) -> dict:
    """Normalise the translator field in-place on a copy."""
    p = dict(poem)
    raw = p.get("translator") or ""
    p["translator"] = norm_translator(raw)
    return p


def main():
    print(f"\n{'='*60}")
    print(" BILINGUAL FILTER")
    print(f"{'='*60}")

    cleaned = json.loads(CLEANED_PATH.read_text())
    ralp    = json.loads(RALP_PATH.read_text())

    print(f"\n  Input records : {len(cleaned):,}")
    print(f"\n  Bilingual pair decisions:")
    decisions = build_decisions(ralp)

    kept   = []
    dropped = []
    for poem in cleaned:
        if should_drop(poem, decisions):
            dropped.append(poem)
        else:
            kept.append(apply_translator_norm(poem))

    OUTPUT_PATH.write_text(json.dumps(kept, ensure_ascii=False, indent=2))

    print(f"\n  Dropped : {len(dropped):,} records")
    for p in dropped:
        print(f"    - {p.get('title')!r:45s}  {p.get('author')!r}  translator={p.get('translator')!r}")

    print(f"\n  Output  : {len(kept):,} records → {OUTPUT_PATH}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
