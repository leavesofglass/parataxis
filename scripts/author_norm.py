#!/usr/bin/env python3
"""
author_norm.py — Build an author-normalization review file.

Collects every distinct author string across:
  versedaily_parsed.json, poetrydaily_parsed.json,
  ralp_parsed.json, slowdown_parsed.json, live_poems.json

Outputs:
  author_norm_review.yaml   — edit this, then run author_norm_apply.py
  author_norm_stats.txt     — flat sorted list of all names for spot-checking

Usage:
  python3 author_norm.py [--live /path/to/live_poems.json]
"""

import json, re, unicodedata, argparse
from collections import defaultdict
from pathlib import Path

SCRIPTS = Path(__file__).parent

PARSED_SOURCES = {
    "versedaily":  (SCRIPTS / "versedaily_parsed.json",   "poet_name"),
    "poetrydaily": (SCRIPTS / "poetrydaily_parsed.json",  "poet_name"),
    "ralp":        (SCRIPTS / "ralp_parsed.json",          "poet_name"),
    "slowdown":    (SCRIPTS / "slowdown_parsed.json",      "poet_name"),
}

REVIEW_FILE = SCRIPTS / "author_norm_review.yaml"
STATS_FILE  = SCRIPTS / "author_norm_stats.txt"


# ---------------------------------------------------------------------------
# String utilities
# ---------------------------------------------------------------------------

def strip_diacritics(s: str) -> str:
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode()


def letters_only(s: str) -> str:
    """Lowercase, no diacritics, only a-z and spaces."""
    s = strip_diacritics(s).lower()
    return re.sub(r"[^a-z\s]", "", s)


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------------------
# Author-string cleaning: strip translator attribution
# ---------------------------------------------------------------------------

# Matches: ", translated from X by ...", " translated by ...",
#          " (translated by ...)", "Translated by ..." (capitalised, no comma)
# The pattern deliberately allows zero preceding whitespace so it catches
# the ralp format "AkhmatovaTranslated by ..." where there is no separator.
_TRANSLATOR_RE = re.compile(
    r",?\s*\(?\s*translated?\s+(?:from\s+\S+\s+)?by\s+.*$",
    re.IGNORECASE,
)

# Some ralp records have "Translated by NAME" glued to the poet name without
# any separator.  The regex above still matches because ",?" and "\s*" can
# both match zero characters.


def poet_only(raw: str) -> str:
    """Strip translator / editor attribution; return just the primary poet name."""
    cleaned = clean(_TRANSLATOR_RE.sub("", raw))
    # Parenthesised forms leave a trailing "(" — strip trailing punctuation artefacts.
    cleaned = cleaned.rstrip("( ,;")
    return clean(cleaned)


# ---------------------------------------------------------------------------
# Name decomposition
# ---------------------------------------------------------------------------

def _expand_initials(first: str) -> str:
    """
    Expand compressed initial sequences so matching is consistent:
      "A.R."  → "a r"
      "A. R." → "a r"
      "T.S."  → "t s"
    Works by replacing every [letter][.] with [letter][space].
    """
    expanded = re.sub(r"([a-zA-Z])\.", r"\1 ", first)
    return re.sub(r"\s+", " ", letters_only(expanded)).strip()


def first_norm(raw: str) -> str:
    """Normalised first+middle name tokens (last name already stripped)."""
    name = poet_only(raw)
    # For 'A and B' collaborative credits, use only the first named poet.
    name = re.split(r"\s+and\s+", name, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    tokens = name.split()
    if len(tokens) <= 1:
        return ""
    return _expand_initials(" ".join(tokens[:-1]))


def last_norm(raw: str) -> str:
    """Normalised last name (letters only, no diacritics)."""
    name = poet_only(raw)
    name = re.split(r"\s+and\s+", name, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    tokens = name.split()
    if not tokens:
        return ""
    return re.sub(r"[^a-z]", "", strip_diacritics(tokens[-1]).lower())


def sort_key_for(raw: str) -> str:
    """Sort key: normalised last name first, then first name."""
    ln = last_norm(raw)
    fn = first_norm(raw)
    return ln + " " + fn


# ---------------------------------------------------------------------------
# First-name compatibility
# ---------------------------------------------------------------------------

def _is_initial(part: str) -> bool:
    """
    True only when a name part is a *single letter* — i.e. an actual initial
    abbreviation like 'J', not a full name like 'James'.
    Operates on an already-letters-only, lowercase string.
    """
    return len(part) == 1


def first_compatible(a: str, b: str) -> str:
    """
    Returns 'yes', 'initial', or 'no'.
      'yes'     — names are identical after normalization
      'initial' — one side uses initials that match the other's full first name
      'no'      — clearly different first names
    """
    if not a and not b:
        return "yes"
    if not a or not b:
        # One record has no first name recorded; treat as compatible (insufficient data)
        return "initial"

    # Both already normalised by caller (letters + spaces, no diacritics)
    if a == b:
        return "yes"

    parts_a = a.split()
    parts_b = b.split()

    if not parts_a or not parts_b:
        return "initial"

    # ── Case 1: same first token (e.g. "Robert T. Frost" ≈ "Robert Frost") ──
    if parts_a[0] == parts_b[0]:
        return "yes"

    # ── Case 2: A is a single initial that matches B's first token ──
    if _is_initial(parts_a[0]) and parts_a[0] == parts_b[0][0]:
        return "initial"

    # ── Case 3: B is a single initial that matches A's first token ──
    if _is_initial(parts_b[0]) and parts_b[0] == parts_a[0][0]:
        return "initial"

    # ── Case 4: A is entirely initials (e.g. "t s" for T.S.) matching B ──
    if all(_is_initial(p) for p in parts_a):
        if len(parts_a) <= len(parts_b) and all(
            parts_a[i] == parts_b[i][0] for i in range(len(parts_a))
        ):
            return "initial"

    # ── Case 5: B is entirely initials matching A ──
    if all(_is_initial(p) for p in parts_b):
        if len(parts_b) <= len(parts_a) and all(
            parts_b[i] == parts_a[i][0] for i in range(len(parts_b))
        ):
            return "initial"

    return "no"


# ---------------------------------------------------------------------------
# Levenshtein (used for full-name fuzzy grouping only, not first-name matching)
# ---------------------------------------------------------------------------

def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for ca in a:
        curr = [prev[0] + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if ca == cb else 1)))
        prev = curr
    return prev[-1]


def _lev_ratio(a: str, b: str) -> float:
    d = _levenshtein(a, b)
    return 1.0 - d / max(len(a), len(b), 1)


# ---------------------------------------------------------------------------
# Grouping algorithm
# ---------------------------------------------------------------------------

def _union_find(n: int):
    parent = list(range(n))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(x, y):
        parent[find(x)] = find(y)
    return find, union


def group_by_last_name(rows: list[dict]) -> list[list[dict]]:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        buckets[row["last_norm"]].append(row)
    return list(buckets.values())


def split_by_first_name(cluster: list[dict]) -> list[list[dict]]:
    """Within a last-name cluster, split by first-name compatibility."""
    if len(cluster) == 1:
        return [cluster]
    n = len(cluster)
    find, union = _union_find(n)
    for i in range(n):
        for j in range(i + 1, n):
            if first_compatible(cluster[i]["first_norm"], cluster[j]["first_norm"]) != "no":
                union(i, j)
    groups: dict[int, list[dict]] = defaultdict(list)
    for i, row in enumerate(cluster):
        groups[find(i)].append(row)
    return list(groups.values())


def find_cross_cluster_fuzzy_flags(
    all_groups: list[list[dict]],
) -> list[tuple[str, str]]:
    """
    Advisory-only: find pairs of SEPARATE groups (different last_norm) whose
    representative full-norm names are very close — likely last-name typos or
    rare diacritic issues that survived the exact last-norm step.

    Returns list of (rep_name_a, rep_name_b) pairs to surface in the review file.
    Uses a high ratio threshold (≥ 0.92) and only compares groups whose last
    names differ by ≤ 2 characters.
    """
    flags = []
    reps = []
    for sg in all_groups:
        if not sg:
            continue
        best = max(sg, key=lambda r: r["count"])
        reps.append((poet_only(best["name"]), best["last_norm"]))

    n = len(reps)
    for i in range(n):
        for j in range(i + 1, n):
            la, lb = reps[i][1], reps[j][1]
            if la == lb:
                continue  # same cluster — already merged
            if abs(len(la) - len(lb)) > 2:
                continue
            if _levenshtein(la, lb) > 2:
                continue
            # Last names are close; now check full name ratio
            na, nb = reps[i][0], reps[j][0]
            if _lev_ratio(
                re.sub(r"[^a-z]", "", strip_diacritics(na).lower()),
                re.sub(r"[^a-z]", "", strip_diacritics(nb).lower()),
            ) >= 0.92:
                flags.append((na, nb))
    return flags


# ---------------------------------------------------------------------------
# Canonical suggestion
# ---------------------------------------------------------------------------

def suggest_canonical(variants: list[dict]) -> str:
    """
    Pick the best canonical form:
    1. Prefer forms from the live DB (already manually curated).
    2. Among ties, prefer highest poem count.
    3. Prefer full first name over single-initial-only.
    4. Prefer forms without trailing punctuation artefacts.
    """
    def score(v: dict):
        src_prio   = 3 if "live" in v["sources"] else 0
        count_prio = v["count"]
        po = poet_only(v["name"])
        toks = po.split()
        full_first = 2 if len(toks) >= 2 and len(toks[-2]) > 1 and not toks[-2].endswith(".") else 0
        clean_prio = 1 if not re.search(r"[.,;!]$", v["name"]) else 0
        return (src_prio, count_prio, full_first, clean_prio)

    best = max(variants, key=score)
    return poet_only(best["name"])


def flag_possible_split(subgroup: list[dict]) -> str | None:
    """
    Return a warning when ≥2 substantial variants have clearly different first
    names (suggesting two different poets with the same last name).
    """
    substantial = [r for r in subgroup if r["count"] >= 2]
    if len(substantial) < 2:
        return None
    for i in range(len(substantial)):
        for j in range(i + 1, len(substantial)):
            if first_compatible(substantial[i]["first_norm"], substantial[j]["first_norm"]) == "no":
                fi = poet_only(substantial[i]["name"])
                fj = poet_only(substantial[j]["name"])
                return (
                    f"Possible two-person split: '{fi}' vs '{fj}' "
                    f"have incompatible first names (both ≥2 poems)."
                )
    return None


# ---------------------------------------------------------------------------
# Build all groups
# ---------------------------------------------------------------------------

def build_groups(rows: list[dict]) -> tuple[list[dict], list[tuple[str, str]]]:
    """
    Returns:
      groups      — list of group dicts (only multi-variant groups)
      fuzzy_flags — list of (name_a, name_b) advisory cross-cluster pairs
    """
    last_clusters = group_by_last_name(rows)
    all_subgroups: list[list[dict]] = []
    output_groups: list[dict] = []

    for cluster in last_clusters:
        subgroups = split_by_first_name(cluster)
        for sg in subgroups:
            all_subgroups.append(sg)
            if len(sg) < 2:
                continue

            # Deduplicate exact name strings
            seen: dict[str, dict] = {}
            for r in sg:
                if r["name"] not in seen or r["count"] > seen[r["name"]]["count"]:
                    seen[r["name"]] = r
            sg = sorted(seen.values(), key=lambda r: (-r["count"], r["name"]))

            canonical = suggest_canonical(sg)
            flag      = flag_possible_split(sg)
            sources_u = sorted({s for r in sg for s in r["sources"]})

            output_groups.append({
                "canonical":     canonical,
                "variants":      sg,
                "flag":          flag,
                "sources_union": sources_u,
            })

    output_groups.sort(key=lambda g: sort_key_for(g["canonical"]))

    fuzzy_flags = find_cross_cluster_fuzzy_flags(all_subgroups)
    return output_groups, fuzzy_flags


# ---------------------------------------------------------------------------
# YAML output helpers
# ---------------------------------------------------------------------------

def _yaml_str(s: str) -> str:
    """Quote for YAML when the value contains special characters."""
    needs_quote = re.search(r'[:#\[\]{}&*!|>\'",\?@`]', s) or \
                  s.startswith((" ", "-", ".", "~")) or \
                  s.endswith((" ",))
    if needs_quote:
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_sources(live_path: Path | None) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for src_name, (path, field) in PARSED_SOURCES.items():
        records = json.loads(path.read_text())
        authors = []
        for r in records:
            name = r.get(field, "")
            if not name:
                continue
            if "has_poem" in r and not r["has_poem"]:
                continue
            authors.append(clean(name))
        result[src_name] = authors

    if live_path and live_path.exists():
        records = json.loads(live_path.read_text())
        result["live"] = [clean(r["author"]) for r in records if r.get("author")]
    else:
        result["live"] = []

    return result


def build_name_table(sources: dict[str, list[str]]) -> list[dict]:
    tally: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for src, names in sources.items():
        for name in names:
            tally[name][src] += 1

    rows = []
    for name, src_counts in tally.items():
        rows.append({
            "name":       name,
            "count":      sum(src_counts.values()),
            "sources":    sorted(src_counts.keys()),
            "src_counts": dict(src_counts),
            "sort_key":   sort_key_for(name),
            "last_norm":  last_norm(name),
            "first_norm": first_norm(name),
        })

    rows.sort(key=lambda r: (r["sort_key"], r["name"]))
    return rows


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def write_review(groups: list[dict], rows: list[dict], fuzzy_flags: list[tuple[str, str]]) -> None:
    lines = [
        "# author_norm_review.yaml",
        "# ─────────────────────────────────────────────────────────────────────────────",
        "# INSTRUCTIONS",
        "#   1. For each group, verify the canonical form and edit if needed.",
        "#   2. Set confirmed: true once you are happy with the canonical.",
        "#   3. Groups flagged possible_split: add a note: explaining your decision",
        "#      (keep merged or split into two separate groups).",
        "#   4. After editing, run:  python3 author_norm_apply.py",
        "#",
        "# GROUPS: only names with ≥2 variants are shown.",
        "# Singletons appear only in author_norm_stats.txt.",
        "#",
        "# FUZZY ADVISORY section at bottom lists possible last-name typos/variants",
        "# that are NOT auto-grouped (review manually).",
        "# ─────────────────────────────────────────────────────────────────────────────",
        "",
        f"# Total distinct author strings : {len(rows)}",
        f"# Groups proposed               : {len(groups)}",
        f"# Variants covered              : {sum(len(g['variants']) for g in groups)}",
        f"# Possible-split flags          : {sum(1 for g in groups if g['flag'])}",
        f"# Cross-cluster fuzzy advisories: {len(fuzzy_flags)}",
        "",
        "groups:",
        "",
    ]

    current_letter = None
    for g in groups:
        sk = sort_key_for(g["canonical"])
        letter = sk[0].upper() if sk else "?"
        if letter != current_letter:
            current_letter = letter
            lines.append(f"  # {'─' * 10} {letter} {'─' * 10}")
            lines.append("")

        lines.append(f"  - canonical: {_yaml_str(g['canonical'])}")
        lines.append(f"    confirmed: false")
        if g["flag"]:
            lines.append(f"    possible_split: {_yaml_str(g['flag'])}")
            lines.append(f"    note: \"\"  # explain your decision here")
        lines.append(f"    variants:")
        for v in g["variants"]:
            src_str = ", ".join(v["sources"])
            lines.append(f"      - name: {_yaml_str(v['name'])}")
            lines.append(f"        count: {v['count']}")
            lines.append(f"        sources: [{src_str}]")
        lines.append("")

    if fuzzy_flags:
        lines += [
            "# ─────────────────────────────────────────────────────────────────────────────",
            "# FUZZY ADVISORY: possible last-name typos / rare variants not auto-grouped.",
            "# These are pairs of groups whose representative names are very close (≥0.92",
            "# similarity) but have different normalized last names.",
            "# Review in author_norm_stats.txt; if they are the same person, manually add",
            "# both raw strings to a group above.",
            "# ─────────────────────────────────────────────────────────────────────────────",
            "",
            "fuzzy_advisory:",
            "",
        ]
        for a, b in fuzzy_flags:
            lines.append(f"  - [{_yaml_str(a)}, {_yaml_str(b)}]")
        lines.append("")

    REVIEW_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote review file  → {REVIEW_FILE}  ({len(lines)} lines)")


def write_stats(rows: list[dict], groups: list[dict]) -> None:
    variant_to_group: dict[str, str] = {}
    for g in groups:
        for v in g["variants"]:
            variant_to_group[v["name"]] = g["canonical"]

    lines = [
        "author_norm_stats.txt — all distinct author strings, sorted by last name",
        f"{'─'*90}",
        f"{'NAME':<55} {'CT':>5}  {'SOURCES':<35}  GROUP",
        f"{'─'*90}",
    ]

    current_letter = None
    for r in rows:
        sk = r["sort_key"]
        letter = sk[0].upper() if sk else "?"
        if letter != current_letter:
            current_letter = letter
            lines.append(f"\n── {letter} ──")
        group_tag = f"→ {variant_to_group[r['name']]}" if r["name"] in variant_to_group else ""
        src_str = ",".join(r["sources"])
        lines.append(
            f"  {r['name']:<55} {r['count']:>5}  {src_str:<35}  {group_tag}"
        )

    STATS_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote stats file   → {STATS_FILE}  ({len(rows)} names)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", default="/tmp/live_poems_0.json",
                        help="Path to pre-fetched live poems JSON")
    args = parser.parse_args()

    print("Loading sources…")
    sources = load_sources(Path(args.live))
    for src, names in sources.items():
        print(f"  {src:<14}: {len(names):>5} poems, {len(set(names)):>4} distinct author strings")

    print("\nBuilding name table…")
    rows = build_name_table(sources)
    print(f"  {len(rows)} unique raw author strings")

    print("\nGrouping variants…")
    groups, fuzzy_flags = build_groups(rows)
    n_split = sum(1 for g in groups if g["flag"])
    print(f"  {len(groups)} groups, {sum(len(g['variants']) for g in groups)} variants, "
          f"{n_split} possible-split flags, {len(fuzzy_flags)} cross-cluster fuzzy advisories")

    print("\nWriting output files…")
    write_review(groups, rows, fuzzy_flags)
    write_stats(rows, groups)
    print("\nDone.")


if __name__ == "__main__":
    main()
