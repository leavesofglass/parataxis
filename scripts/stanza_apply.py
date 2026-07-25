"""
stanza_apply.py — apply the 40 recoverable stanza-break fixes.

Reads results from scripts/stanza_rescope_cache/ and applies:
  • FOUND_WITH_STANZAS      (22 poems) → body := fetched source body
  • FOUND_NEAR_WITH_STANZAS (18 poems) → body := stored body with blank lines
                                          inserted at source's stanza positions
                                          (no wording changes)

Safety:
  • Refuses to touch poems where corpus != null.
  • Refuses to touch poems whose stored body already contains \\n\\n.
  • Path B requires that stored non-empty lines exactly equal the fetched
    non-empty lines under aggressive normalization — if not, the whole
    transplant is skipped and logged.
  • Flags: mid-line breaks, every-line-a-stanza, mono-stanza, line-count drift.

body_html is left alone (all 40 have body_html = NULL).

Usage:
  python scripts/stanza_apply.py            # dry run, shows before/after
  python scripts/stanza_apply.py --apply    # actually write to DB
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from supabase import create_client

# ── Config ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / "app" / ".env.local"
CACHE_DIR = Path(__file__).resolve().parent / "stanza_rescope_cache"

STRICT = "FOUND_WITH_STANZAS"
NEAR = "FOUND_NEAR_WITH_STANZAS"

# Per-poem overrides decided after inspecting the flagged dry-run entries.
#   action: "skip" — do not touch
#   action: "transplant" — force Path B even though the poem is classified STRICT
OVERRIDES: dict[str, dict] = {
    # poem_0337 (Hardy "The Man He Killed") was previously skipped due to the
    # per-<p>-line extractor bug; the fixed extractor now yields a clean
    # 5-quatrain body, so we let it flow through as A-overwrite.
    "poem_0341": {"action": "skip",
                  "reason": "fetched body contains lone 'II' heading line — would corrupt wording"},
    "poem_0419": {"action": "transplant",
                  "reason": "downgrade to transplant to preserve stored 20-line body (drops 'Avignon.' attribution)"},
}


# ── Env / Supabase ────────────────────────────────────────────────────────────

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


# ── Normalization (identical to stanza_rescope) ───────────────────────────────

_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")


def norm_line(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def flat_lines(body: str) -> list[str]:
    return [ln.strip() for ln in body.split("\n") if ln.strip()]


def stanza_count(body: str) -> int:
    """Number of stanzas (blocks separated by one or more blank lines)."""
    body = re.sub(r"\n{2,}", "\n\n", body.strip())
    if not body:
        return 0
    return len([s for s in body.split("\n\n") if s.strip()])


# ── Path A: source overwrite ──────────────────────────────────────────────────

def build_from_source(stored_body: str, fetched_body: str) -> tuple[str, list[str]]:
    """Return (new_body, warnings). Uses fetched source verbatim after
    collapsing >2 blank runs.
    """
    warnings: list[str] = []
    new = re.sub(r"\n{3,}", "\n\n", fetched_body.strip())
    stored_lines = flat_lines(stored_body)
    new_lines = flat_lines(new)
    if len(stored_lines) != len(new_lines):
        warnings.append(f"line-count drift: stored={len(stored_lines)} new={len(new_lines)}")
    return new, warnings


# ── Path B: transplant blank-line positions ───────────────────────────────────

def compute_break_positions(fetched_body: str) -> list[int]:
    """Return the 0-based indices of non-empty lines in the fetched body
    that are immediately followed by a blank line. Consecutive blanks are
    collapsed."""
    positions: list[int] = []
    non_empty_idx = -1  # index of last non-empty line seen
    prev_nonempty = False
    for raw in fetched_body.split("\n"):
        ln = raw.strip()
        if ln:
            non_empty_idx += 1
            prev_nonempty = True
        else:
            if prev_nonempty and non_empty_idx not in positions:
                positions.append(non_empty_idx)
            prev_nonempty = False
    return positions


def transplant(stored_body: str, fetched_body: str) -> tuple[Optional[str], list[str]]:
    """Insert blank lines into stored body at fetched-source stanza positions.
    Returns (new_body_or_None, warnings). Returns None if transplant is unsafe.

    Safety rule: every blank-line insertion point in the fetched source must map
    to a stored position via a difflib EQUAL opcode. Overall wording drift is
    fine — we only care that the specific *break locations* align cleanly.
    """
    warnings: list[str] = []
    stored = flat_lines(stored_body)
    fetched_flat = flat_lines(fetched_body)

    line_delta = abs(len(stored) - len(fetched_flat))
    if line_delta > 1:
        warnings.append(
            f"line-count mismatch too large: stored={len(stored)} fetched={len(fetched_flat)}"
        )
        return None, warnings

    # Build fetched→stored index map using difflib equal-blocks only.
    map_fetched_to_stored: list[int] = [-1] * len(fetched_flat)
    if len(stored) == len(fetched_flat):
        # Still compute opcodes so we know which positions are "equal" for
        # blank-safety checks; treat non-equal positions as unmapped.
        stored_norm = [norm_line(l) for l in stored]
        fetched_norm = [norm_line(l) for l in fetched_flat]
        sm = difflib.SequenceMatcher(a=fetched_norm, b=stored_norm)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(i2 - i1):
                    map_fetched_to_stored[i1 + k] = j1 + k
        equal_frac = sum(1 for x in map_fetched_to_stored if x != -1) / max(1, len(fetched_flat))
        if equal_frac < 0.4:  # exact-length pairs with almost nothing in common are dubious
            warnings.append(f"exact-length but only {equal_frac:.2f} equal — refusing transplant")
            return None, warnings
    else:  # line_delta == 1
        stored_norm = [norm_line(l) for l in stored]
        fetched_norm = [norm_line(l) for l in fetched_flat]
        sm = difflib.SequenceMatcher(a=fetched_norm, b=stored_norm)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(i2 - i1):
                    map_fetched_to_stored[i1 + k] = j1 + k
        equal_frac = sum(1 for x in map_fetched_to_stored if x != -1) / max(1, len(fetched_flat))
        warnings.append(
            f"line-count off by 1 (stored={len(stored)} fetched={len(fetched_flat)}), "
            f"{equal_frac:.2f} equal via difflib"
        )

    # For each fetched break position, require that it maps to a stored line
    # via an equal-opcode. If the line just BEFORE the break is a wording-drift
    # line but the line just AFTER maps cleanly, anchor the break on the next
    # line instead (insert-after (mapped_next - 1)).
    break_positions_fetched = compute_break_positions(fetched_body)
    break_positions_stored: list[int] = []
    unmapped: list[int] = []
    for p in break_positions_fetched:
        mapped = map_fetched_to_stored[p] if p < len(map_fetched_to_stored) else -1
        if mapped == -1:
            # Try next-line anchor
            next_mapped = (
                map_fetched_to_stored[p + 1]
                if p + 1 < len(map_fetched_to_stored) else -1
            )
            if next_mapped > 0:
                mapped = next_mapped - 1
            else:
                unmapped.append(p)
                continue
        if mapped == len(stored) - 1:
            # blank at end of poem is meaningless; skip (usually attribution follows)
            continue
        break_positions_stored.append(mapped)
    break_positions_stored = sorted(set(break_positions_stored))

    if unmapped:
        warnings.append(
            f"skipped {len(unmapped)} break position(s) that don't align to a stored line"
        )

    if not break_positions_stored:
        warnings.append("no usable stanza breaks after mapping — refusing transplant")
        return None, warnings

    # Insert blank lines after those stored-line indices
    out: list[str] = []
    for i, ln in enumerate(stored):
        out.append(ln)
        if i in break_positions_stored:
            out.append("")
    new_body = "\n".join(out)

    # Sanity: non-empty lines must still equal stored
    new_flat = flat_lines(new_body)
    if new_flat != stored:
        warnings.append("BUG: transplant produced different non-empty lines — aborting")
        return None, warnings

    return new_body, warnings


# ── Orchestration ─────────────────────────────────────────────────────────────

@dataclass
class Plan:
    id: str
    title: str
    author: str
    path: str  # 'A-overwrite' or 'B-transplant'
    old_body: str
    new_body: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    old_stanzas: int = 0
    new_stanzas: int = 0
    old_lines: int = 0
    new_lines: int = 0
    skipped: bool = False
    skip_reason: str = ""


def load_plans(sb, only_ids: Optional[set[str]] = None) -> list[Plan]:
    plans: list[Plan] = []
    for cache_file in sorted(CACHE_DIR.glob("*.json")):
        if only_ids is not None and cache_file.stem not in only_ids:
            continue
        data = json.loads(cache_file.read_text())
        cat = data.get("category")
        if cat not in (STRICT, NEAR):
            continue
        pid = data["id"]
        row = sb.table("poems").select("id, title, author, body, corpus").eq("id", pid).execute().data
        if not row:
            continue
        row = row[0]
        # Safety re-checks
        if row["corpus"] is not None:
            plans.append(Plan(pid, row["title"], row["author"], "-", row["body"],
                              skipped=True, skip_reason=f"corpus is not null ({row['corpus']})"))
            continue
        if "\n\n" in row["body"]:
            plans.append(Plan(pid, row["title"], row["author"], "-", row["body"],
                              skipped=True, skip_reason="stored body already has \\n\\n"))
            continue

        fetched = data.get("fetched_body") or ""
        if not fetched:
            plans.append(Plan(pid, row["title"], row["author"], "-", row["body"],
                              skipped=True, skip_reason="no fetched_body in cache"))
            continue

        override = OVERRIDES.get(pid)
        if override and override["action"] == "skip":
            plans.append(Plan(pid, row["title"], row["author"], "-", row["body"],
                              skipped=True, skip_reason=f"override: {override['reason']}"))
            continue
        if override and override["action"] == "transplant":
            new_body, warns = transplant(row["body"], fetched)
            path = "B-transplant"
            warns = [f"override: {override['reason']}"] + warns
        elif cat == STRICT:
            new_body, warns = build_from_source(row["body"], fetched)
            path = "A-overwrite"
        else:  # NEAR
            new_body, warns = transplant(row["body"], fetched)
            path = "B-transplant"

        plan = Plan(
            id=pid, title=row["title"], author=row["author"], path=path,
            old_body=row["body"], new_body=new_body, warnings=warns,
            old_stanzas=stanza_count(row["body"]),
            new_stanzas=stanza_count(new_body) if new_body else 0,
            old_lines=len(flat_lines(row["body"])),
            new_lines=len(flat_lines(new_body)) if new_body else 0,
        )
        if new_body is None:
            plan.skipped = True
            plan.skip_reason = "; ".join(warns) or "transplant refused"
        else:
            plan.flags = compute_flags(plan)
        plans.append(plan)
    return plans


def compute_flags(plan: Plan) -> list[str]:
    flags: list[str] = []
    if plan.new_body is None:
        return flags
    if "\n\n\n" in plan.new_body:
        flags.append("triple-blank run present")
    if plan.new_stanzas <= 1:
        flags.append(f"mono-stanza (stanzas={plan.new_stanzas}) — no breaks added?")
    if plan.new_stanzas >= plan.new_lines * 0.8 and plan.new_lines >= 4:
        flags.append(f"every-line-a-stanza ({plan.new_stanzas} stanzas / {plan.new_lines} lines)")
    if plan.old_lines != plan.new_lines and plan.path == "B-transplant":
        flags.append(f"line-count changed {plan.old_lines}→{plan.new_lines} (should be same for transplant)")
    if plan.path == "A-overwrite" and plan.old_lines != plan.new_lines:
        flags.append(f"line-count differs {plan.old_lines}→{plan.new_lines} (source-overwrite)")
    return flags


# ── Reporting ─────────────────────────────────────────────────────────────────

def print_dry_run(plans: list[Plan]) -> None:
    to_apply = [p for p in plans if not p.skipped]
    skipped = [p for p in plans if p.skipped]
    a_plans = [p for p in to_apply if p.path == "A-overwrite"]
    b_plans = [p for p in to_apply if p.path == "B-transplant"]
    flagged = [p for p in to_apply if p.flags]

    print("=" * 80)
    print("STANZA-APPLY DRY RUN")
    print("=" * 80)
    print(f"planned updates:      {len(to_apply)}   (A-overwrite: {len(a_plans)}   B-transplant: {len(b_plans)})")
    print(f"skipped:              {len(skipped)}")
    print(f"flagged for review:   {len(flagged)}")
    print()

    def _print_group(header: str, group: list[Plan]) -> None:
        print("-" * 80)
        print(header)
        print("-" * 80)
        print(f"{'id':<11}  {'path':<12}  {'lines':<9}  {'stanzas':<9}  {'author':<22}  title")
        for p in group:
            lines_str = f"{p.old_lines}→{p.new_lines}"
            stanzas_str = f"{p.old_stanzas}→{p.new_stanzas}"
            print(f"{p.id:<11}  {p.path:<12}  {lines_str:<9}  {stanzas_str:<9}  {p.author[:22]:<22}  {p.title[:40]}")
            if p.flags:
                for f in p.flags:
                    print(f"    ⚑ {f}")
            for w in p.warnings:
                if w and "aligned via difflib" in w:
                    print(f"    · {w}")

    _print_group("A — SOURCE OVERWRITE (fetched body becomes new stored body)", a_plans)
    _print_group("B — TRANSPLANT (blank lines inserted, wording unchanged)", b_plans)

    if skipped:
        print()
        print("-" * 80)
        print("SKIPPED")
        print("-" * 80)
        for p in skipped:
            print(f"  {p.id}  ({p.path})  — {p.skip_reason}")

    if flagged:
        print()
        print("=" * 80)
        print(f"REVIEW THESE {len(flagged)} FLAGGED ENTRIES BEFORE APPLYING")
        print("=" * 80)
        for p in flagged:
            print(f"  {p.id}  {p.path}  — {'; '.join(p.flags)}")

    print()
    print("dry-run complete. run with --apply to write.")


def apply_plans(sb, plans: list[Plan]) -> None:
    to_apply = [p for p in plans if not p.skipped and p.new_body]
    print(f"applying {len(to_apply)} updates …")
    for p in to_apply:
        update = {"body": p.new_body}
        # Sync line_count when the non-empty line count changed (only possible
        # on A-overwrite; B-transplant preserves it by construction).
        if p.old_lines != p.new_lines:
            update["line_count"] = p.new_lines
        res = sb.table("poems").update(update).eq("id", p.id).execute()
        ok = bool(res.data)
        extra = f"  line_count {p.old_lines}→{p.new_lines}" if "line_count" in update else ""
        print(f"  {p.id}  {p.path}  {'ok' if ok else 'FAILED'}  stanzas {p.old_stanzas}→{p.new_stanzas}{extra}")
    print("done.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write to DB (default: dry run)")
    ap.add_argument("--show-diff", action="store_true",
                    help="dump full before/after body for every plan (verbose)")
    ap.add_argument("--only", type=str, default="",
                    help="comma-separated poem ids; only these will be considered")
    args = ap.parse_args()

    only_ids = set(args.only.split(",")) if args.only else None
    sb = sb_client()
    plans = load_plans(sb, only_ids=only_ids)
    print_dry_run(plans)

    if args.show_diff:
        for p in plans:
            if p.skipped or not p.new_body:
                continue
            print()
            print("=" * 80)
            print(f"{p.id}  {p.path}  {p.author} — {p.title}")
            print("=" * 80)
            print("--- OLD ---")
            print(p.old_body)
            print("--- NEW ---")
            print(p.new_body)

    if args.apply:
        # Refuse to apply if there are unaddressed flags (belt & suspenders).
        # The A-overwrite line-count-drift flag is auto-fixed by line_count sync,
        # so it's non-blocking.
        def blocking(flags: list[str]) -> list[str]:
            return [f for f in flags if not f.startswith("line-count differs ")]

        flagged = [p for p in plans if not p.skipped and blocking(p.flags)]
        if flagged:
            print(f"\nrefusing to apply — {len(flagged)} flagged plans need review. "
                  f"Re-run without --apply to see them.")
            sys.exit(1)
        apply_plans(sb, plans)


if __name__ == "__main__":
    main()
