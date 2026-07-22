#!/usr/bin/env python3
"""
author_norm_apply.py — Read confirmed groups from author_norm_review.yaml
and write author_norm_map.json: a flat {raw_variant → canonical} dict
for use in the dedup pipeline.

Only groups with confirmed: true are written. Unconfirmed groups are
reported but skipped so they don't silently pollute the map.

Usage:
  python3 author_norm_apply.py [--strict]   # --strict exits non-zero if any unconfirmed
"""

import argparse, json, re
from pathlib import Path

SCRIPTS  = Path(__file__).parent
REVIEW   = SCRIPTS / "author_norm_review.yaml"
OUT_MAP  = SCRIPTS / "author_norm_map.json"


def _unquote(s: str) -> str:
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1].replace('\\"', '"').replace('\\\\', '\\')
    return s.replace('’', "'").replace('‘', "'")


def load_review(path: Path) -> tuple[dict[str, str], list[str]]:
    """
    Returns:
      mapping      — {raw_variant: canonical} for confirmed groups only
      unconfirmed  — list of canonical names for groups not yet confirmed
    """
    mapping: dict[str, str] = {}
    unconfirmed: list[str] = []

    text = path.read_text(encoding="utf-8")
    for block in re.split(r'\n  - canonical:', text)[1:]:
        lines = block.splitlines()
        canonical  = _unquote(lines[0].strip())
        confirmed  = any(re.match(r"\s+confirmed:\s+true", l) for l in lines)

        variants: list[str] = []
        for line in lines:
            m = re.match(r"^\s{6}- name:\s*(.+)$", line)
            if m:
                variants.append(_unquote(m.group(1).strip()))

        if confirmed:
            for v in variants:
                mapping[v] = canonical
        else:
            unconfirmed.append(canonical)

    return mapping, unconfirmed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="Exit non-zero if any groups are unconfirmed")
    args = parser.parse_args()

    mapping, unconfirmed = load_review(REVIEW)

    if unconfirmed:
        print(f"WARNING: {len(unconfirmed)} unconfirmed group(s) skipped:")
        for name in unconfirmed:
            print(f"  - {name}")
        if args.strict:
            raise SystemExit(1)
    else:
        print("All groups confirmed.")

    OUT_MAP.write_text(
        json.dumps(mapping, indent=2, ensure_ascii=False, sort_keys=True),
        encoding="utf-8",
    )
    print(f"Wrote {len(mapping)} variant→canonical mappings → {OUT_MAP}")


if __name__ == "__main__":
    main()
