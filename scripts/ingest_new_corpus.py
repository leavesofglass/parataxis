"""
ingest_new_corpus.py — insert dedup_filtered.json into the Supabase poems table.

Adds ~10,169 poems from RALP / Slowdown / VerseDaily / PoetryDaily.
Existing public-domain poems (poem_0001…poem_0687) are never touched.

Reads SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from app/.env.local
(env vars take precedence if set).

Usage:
  # Test: insert 20 poems and show what landed
  python scripts/ingest_new_corpus.py --test

  # Full ingest of all ~10,169 poems
  python scripts/ingest_new_corpus.py --full
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

# ── Env ───────────────────────────────────────────────────────────────────────

def _load_env_local() -> dict[str, str]:
    env_path = os.path.join(os.path.dirname(__file__), "..", "app", ".env.local")
    values: dict[str, str] = {}
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    values[key.strip()] = val.strip()
    except FileNotFoundError:
        pass
    return values

_env = _load_env_local()

def _get(env_key: str, file_key: str | None = None) -> str:
    return (
        os.environ.get(env_key, "").strip()
        or _env.get(file_key or env_key, "").strip()
    )


SUPABASE_URL = _get("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = _get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL:
    sys.exit(
        "ERROR: SUPABASE_URL not found.\n"
        "  Add NEXT_PUBLIC_SUPABASE_URL to app/.env.local"
    )
if not SUPABASE_KEY:
    sys.exit(
        "ERROR: SUPABASE_SERVICE_ROLE_KEY not found.\n"
        "  Add SUPABASE_SERVICE_ROLE_KEY to app/.env.local"
    )

try:
    from supabase import create_client
except ImportError:
    sys.exit("supabase package not found — run: pip install supabase")


# ── Config ───────────────────────────────────────────────────────────────────

CORPUS_PATH = os.path.join(os.path.dirname(__file__), "dedup_filtered.json")
BATCH_SIZE  = 50
TEST_LIMIT  = 20


# ── Helpers ──────────────────────────────────────────────────────────────────

def nonempty(val) -> str | None:
    """Return None for blank/None values; otherwise return stripped string."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def count_nonempty_lines(text: str) -> int:
    return sum(1 for line in (text or "").split("\n") if line.strip())


def get_max_poem_num(client) -> int:
    """Return the highest numeric suffix among existing poem IDs.

    Must paginate all IDs — text-sort order breaks when IDs span different
    digit counts (e.g. poem_9999 sorts above poem_18426 in text order).
    """
    max_num = 0
    page = 0
    while True:
        batch = (
            client.table("poems")
            .select("id")
            .range(page * 1000, page * 1000 + 999)
            .execute()
        )
        for row in batch.data:
            m = re.search(r"(\d+)$", row["id"])
            if m:
                max_num = max(max_num, int(m.group(1)))
        if len(batch.data) < 1000:
            break
        page += 1
    return max_num


ENRICHED_AT = datetime.now(timezone.utc).isoformat()


def build_row(poem: dict, poem_id: str) -> dict:
    rubric = poem.get("rubric") or {}
    return {
        "id":               poem_id,
        "title":            poem["title"],
        "author":           poem["author"],
        "body":             poem["poem_text"],
        "line_count":       count_nonempty_lines(poem["poem_text"]),
        "embedding":        poem.get("embedding"),
        "corpus":           (poem.get("primary_source") or "").lower().strip() or None,
        # translator is NOT NULL DEFAULT '' in schema
        "translator":       nonempty(poem.get("translator")) or "",
        "summary":          nonempty(poem.get("summary")),
        # rubric dimensions
        "mood":                rubric.get("mood"),
        "emotional_intensity": rubric.get("emotional_intensity"),
        "imagery":             rubric.get("imagery"),
        "accessibility":       rubric.get("accessibility"),
        "formality":           rubric.get("formality"),
        # mark as enriched so old pipeline skips these poems
        "enriched_at":         ENRICHED_AT,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    test_mode = "--test" in args
    full_mode = "--full" in args

    if not test_mode and not full_mode:
        sys.exit(
            "Specify a mode:\n"
            "  --test   insert 20 poems and show what landed\n"
            "  --full   insert all ~10,169 poems"
        )

    with open(CORPUS_PATH, encoding="utf-8") as f:
        all_poems = json.load(f)

    poems = all_poems[:TEST_LIMIT] if test_mode else all_poems

    client   = create_client(SUPABASE_URL, SUPABASE_KEY)
    max_num  = get_max_poem_num(client)

    print(f"\n{'='*62}")
    print(f" INGEST: dedup_filtered.json → Supabase poems")
    print(f"{'='*62}")
    print(f"  Mode        : {'TEST (%d poems)' % TEST_LIMIT if test_mode else 'FULL'}")
    print(f"  Records     : {len(poems):,}")
    print(f"  Existing max: poem_{max_num:04d}")
    print(f"  New IDs     : poem_{max_num+1:04d} … poem_{max_num+len(poems):04d}")
    print(f"  Supabase URL: {SUPABASE_URL}")
    print()

    rows = [build_row(poem, f"poem_{max_num + i + 1:04d}") for i, poem in enumerate(poems)]

    inserted = 0
    errors   = []

    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch     = rows[batch_start : batch_start + BATCH_SIZE]
        batch_end = batch_start + len(batch)
        try:
            client.table("poems").upsert(batch, on_conflict="id", ignore_duplicates=True).execute()
            inserted += len(batch)
            print(
                f"  [{inserted:>5}/{len(rows)}]  OK  "
                f"{batch[0]['id']}–{batch[-1]['id']}"
            )
        except Exception as exc:
            errors.append((batch_start, str(exc)))
            print(f"  [{batch_start+1}–{batch_end}]  ERROR: {exc}")

    print()
    print(f"{'='*62}")
    if errors:
        print(f"  DONE with {len(errors)} error(s). Inserted {inserted}/{len(rows)} poems.")
        for start, msg in errors:
            print(f"    batch at index {start}: {msg}")
        sys.exit(1)
    else:
        print(f"  DONE. {inserted:,} poems inserted.")
    print(f"{'='*62}\n")

    if test_mode:
        _show_test_sample(client, rows)


def _show_test_sample(client, rows):
    first_id = rows[0]["id"]
    last_id  = rows[-1]["id"]

    result = (
        client.table("poems")
        .select(
            "id,title,author,corpus,line_count,"
            "mood,emotional_intensity,imagery,accessibility,formality,translator"
        )
        .in_("id", [r["id"] for r in rows])
        .order("id")
        .execute()
    )

    print(f"\n── What landed ({len(result.data)} rows, first_id={first_id} … last_id={last_id}) ──\n")
    for row in result.data:
        rubric_str = (
            f"mood={row['mood']} ei={row['emotional_intensity']} "
            f"img={row['imagery']} acc={row['accessibility']} form={row['formality']}"
        )
        print(f"  {row['id']}  [{row['corpus']}]  {row['title']!r}  by {row['author']}")
        print(f"    lines={row['line_count']}  {rubric_str}")
        if row.get("translator"):
            print(f"    translator={row['translator']!r}")
        print()


if __name__ == "__main__":
    main()
