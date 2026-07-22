#!/usr/bin/env python3
"""
author_list_gen.py — Generate author_list.csv and author_list.md from
parsed sources + live DB, using canonical names from author_norm_review.yaml.

Run after editing author_norm_review.yaml (no need to confirm groups first —
both confirmed and unconfirmed canonicals are applied).

Usage:
  python3 author_list_gen.py [--live /path/to/live_poems.json]
"""

import csv, io, json, re, unicodedata, argparse
from collections import defaultdict
from pathlib import Path

SCRIPTS   = Path(__file__).parent
REVIEW    = SCRIPTS / "author_norm_review.yaml"
OUT_CSV   = SCRIPTS / "author_list.csv"
OUT_MD    = SCRIPTS / "author_list.md"
LIVE_DEFAULT = Path("/tmp/live_poems_0.json")

PARSED_SOURCES = {
    "versedaily":  (SCRIPTS / "versedaily_parsed.json",   "poet_name"),
    "poetrydaily": (SCRIPTS / "poetrydaily_parsed.json",  "poet_name"),
    "ralp":        (SCRIPTS / "ralp_parsed.json",          "poet_name"),
    "slowdown":    (SCRIPTS / "slowdown_parsed.json",      "poet_name"),
}

SOURCE_ORDER  = ["live", "versedaily", "poetrydaily", "ralp", "slowdown"]
SOURCE_LABELS = {
    "live":        "Live",
    "versedaily":  "Verse Daily",
    "poetrydaily": "Poetry Daily",
    "ralp":        "RALP",
    "slowdown":    "Slowdown",
}


# ---------------------------------------------------------------------------
# Helpers (mirrors author_norm.py)
# ---------------------------------------------------------------------------

_TRANSLATOR_RE = re.compile(
    r",?\s*\(?\s*translated?\s+(?:from\s+\S+\s+)?by\s+.*$", re.IGNORECASE
)


def poet_only(raw: str) -> str:
    cleaned = re.sub(r"\s+", " ", _TRANSLATOR_RE.sub("", raw)).strip()
    return cleaned.rstrip("( ,;").strip()


def strip_diacritics(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()


def last_sort_key(name: str) -> str:
    tokens = name.split()
    if not tokens:
        return ""
    last  = re.sub(r"[^a-z]", "", strip_diacritics(tokens[-1]).lower())
    first = re.sub(r"[^a-z\s]", "", strip_diacritics(" ".join(tokens[:-1])).lower()).strip()
    return last + " " + first


def clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s.replace('’', "'").replace('‘', "'")


# ---------------------------------------------------------------------------
# Parse author_norm_review.yaml → variant→canonical map
# ---------------------------------------------------------------------------

def _unquote(s: str) -> str:
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1].replace('\\"', '"').replace('\\\\', '\\')
    return s.replace('’', "'").replace('‘', "'")


def load_review(path: Path) -> dict[str, str]:
    """Return {raw_variant_name: canonical_name} for all groups."""
    mapping: dict[str, str] = {}
    text = path.read_text(encoding="utf-8")
    for block in re.split(r'\n  - canonical:', text)[1:]:
        lines = block.splitlines()
        canonical = _unquote(lines[0].strip())
        for line in lines:
            m = re.match(r"^\s{6}- name:\s*(.+)$", line)
            if m:
                mapping[_unquote(m.group(1).strip())] = canonical
    return mapping


# ---------------------------------------------------------------------------
# Load sources and aggregate
# ---------------------------------------------------------------------------

def build_tally(
    variant_map: dict[str, str], live_path: Path
) -> dict[str, dict[str, int]]:
    """Return {canonical: {source: count}}."""
    tally: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for src, (path, field) in PARSED_SOURCES.items():
        for r in json.loads(path.read_text()):
            raw = r.get(field, "")
            if not raw:
                continue
            if "has_poem" in r and not r["has_poem"]:
                continue
            raw = clean(raw)
            canon = variant_map.get(raw, poet_only(raw))
            tally[canon][src] += 1

    if live_path.exists():
        for r in json.loads(live_path.read_text()):
            raw = clean(r.get("author", ""))
            if not raw:
                continue
            canon = variant_map.get(raw, poet_only(raw))
            tally[canon]["live"] += 1

    return tally


# ---------------------------------------------------------------------------
# Build and sort rows
# ---------------------------------------------------------------------------

def build_rows(tally: dict[str, dict[str, int]]) -> list[dict]:
    rows = []
    for canon, src_counts in tally.items():
        total     = sum(src_counts.values())
        src_parts = [
            f"{SOURCE_LABELS[s]} ({src_counts[s]})"
            for s in SOURCE_ORDER if s in src_counts
        ]
        rows.append({
            "name":     canon,
            "total":    total,
            "src_str":  ", ".join(src_parts),
            "src_counts": src_counts,
            "sort_key": last_sort_key(canon),
        })
    rows.sort(key=lambda r: (r["sort_key"], r["name"]))
    return rows


# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------

def write_csv(rows: list[dict]) -> None:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["#", "Author", "Total Poems", "Live", "Verse Daily", "Poetry Daily", "RALP", "Slowdown"])
    for i, r in enumerate(rows, 1):
        sc = r["src_counts"]
        w.writerow([
            i, r["name"], r["total"],
            sc.get("live", ""), sc.get("versedaily", ""),
            sc.get("poetrydaily", ""), sc.get("ralp", ""), sc.get("slowdown", ""),
        ])
    OUT_CSV.write_text(buf.getvalue(), encoding="utf-8")
    print(f"Wrote {OUT_CSV}  ({len(rows)} rows)")


def write_md(rows: list[dict]) -> None:
    lines = [
        "# Author List",
        "",
        f"**{len(rows)} authors** across Verse Daily, Poetry Daily, RALP, The Slowdown, and the live corpus.",
        "Sorted by last name. Poem counts per source in parentheses.",
        "",
        "| # | Author | Total | Sources |",
        "|---|--------|------:|---------|",
    ]
    for i, r in enumerate(rows, 1):
        lines.append(f"| {i} | {r['name']} | {r['total']} | {r['src_str']} |")
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_MD}  ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", default=str(LIVE_DEFAULT))
    args = parser.parse_args()

    variant_map = load_review(REVIEW)
    print(f"Loaded {len(variant_map)} variant→canonical mappings from {REVIEW.name}")

    tally = build_tally(variant_map, Path(args.live))
    print(f"Aggregated {len(tally)} canonical authors")

    rows = build_rows(tally)
    write_csv(rows)
    write_md(rows)


if __name__ == "__main__":
    main()
