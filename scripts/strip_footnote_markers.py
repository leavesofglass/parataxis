"""
strip_footnote_markers.py — remove fused footnote markers like [1], [2], [604]
from a targeted list of poems.

Rule: only strip [N] when preceded by a non-whitespace character (regex
``(?<=\\S)\\[\\d+\\]``). Bracketed numbers on their own line — e.g. Berryman's
stanza numbers, Trujillo's section markers — are left untouched.

Usage:
  python scripts/strip_footnote_markers.py           # dry run
  python scripts/strip_footnote_markers.py --apply   # write to DB

Affected poems (hard-coded — this is a one-shot cleanup, not a rule):
  poem_0545  Byron — Sonnet On Chillon             [1] [2]
  poem_0547  Byron — Stanzas ... Florence and Pisa [604]
  poem_0743  Swift — A Description Of The Morning  [1] [2] [3]
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Optional

from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / "app" / ".env.local"

TARGET_IDS = ["poem_0545", "poem_0547", "poem_0743"]
MARKER_RE = re.compile(r"(?<=\S)\[\d+\]")


def sb_client():
    env = {}
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return create_client(
        env["NEXT_PUBLIC_SUPABASE_URL"],
        env["SUPABASE_SERVICE_ROLE_KEY"],
    )


def strip(text: Optional[str]) -> tuple[Optional[str], list[str]]:
    """Return (new_text, matched_markers). None-in → None-out."""
    if text is None:
        return None, []
    matches = [m.group(0) for m in MARKER_RE.finditer(text)]
    return MARKER_RE.sub("", text), matches


def preview_diff(field: str, old: Optional[str], new: Optional[str], matches: list[str]) -> None:
    if old is None:
        print(f"  {field}: NULL — nothing to strip")
        return
    if not matches:
        print(f"  {field}: no markers matched by heuristic")
        return
    print(f"  {field}: stripped {len(matches)} marker(s) {matches}")
    # Show each marker's line before/after
    old_lines = old.splitlines()
    new_lines = new.splitlines() if new else []
    for i, (ol, nl) in enumerate(zip(old_lines, new_lines)):
        if ol != nl:
            print(f"    line {i+1}:")
            print(f"      old: {ol!r}")
            print(f"      new: {nl!r}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write to DB (default: dry run)")
    args = ap.parse_args()

    sb = sb_client()
    rows = (
        sb.table("poems")
        .select("id, title, author, corpus, body, body_html")
        .in_("id", TARGET_IDS)
        .execute()
        .data
    )
    rows = sorted(rows, key=lambda r: r["id"])

    plans = []
    print("=" * 80)
    print("STRIP-FOOTNOTE-MARKERS DRY RUN")
    print("=" * 80)
    for r in rows:
        new_body, body_hits = strip(r["body"])
        new_html, html_hits = strip(r["body_html"])
        print(f"\n{r['id']}  corpus={r['corpus']!r}  {r['author']} — {r['title']}")
        preview_diff("body", r["body"], new_body, body_hits)
        preview_diff("body_html", r["body_html"], new_html, html_hits)

        update: dict = {}
        if body_hits and new_body != r["body"]:
            update["body"] = new_body
        if html_hits and new_html != r["body_html"]:
            update["body_html"] = new_html
        if update:
            plans.append((r["id"], update))

    print("\n" + "=" * 80)
    print(f"planned writes: {len(plans)}")
    print("=" * 80)

    if not args.apply:
        print("dry-run only. re-run with --apply to write.")
        return

    print("applying …")
    for pid, update in plans:
        res = sb.table("poems").update(update).eq("id", pid).execute()
        ok = bool(res.data)
        fields = ", ".join(update.keys())
        print(f"  {pid}  fields={fields}  {'ok' if ok else 'FAILED'}")
    print("done.")


if __name__ == "__main__":
    main()
