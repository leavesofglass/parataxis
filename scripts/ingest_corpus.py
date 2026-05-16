"""
ingest_corpus.py — load data/corpus_30lines_clean.json into the Supabase poems table.

Requires environment variables:
  SUPABASE_URL              — project URL (auto-read from app/.env.local if not set)
  SUPABASE_SERVICE_ROLE_KEY — service role key (must be set manually; never use anon key)

Run:
  SUPABASE_SERVICE_ROLE_KEY=<key> .venv/bin/python scripts/ingest_corpus.py
"""

import json
import os
import re
import sys

# ── Resolve SUPABASE_URL ──────────────────────────────────────────────────────
# Use env var if set; otherwise parse app/.env.local automatically.

def load_supabase_url() -> str:
    url = os.environ.get("SUPABASE_URL", "").strip()
    if url:
        return url

    env_path = os.path.join(os.path.dirname(__file__), "..", "app", ".env.local")
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("NEXT_PUBLIC_SUPABASE_URL="):
                    val = line.split("=", 1)[1].strip()
                    if val:
                        return val
    except FileNotFoundError:
        pass

    return ""


SUPABASE_URL = load_supabase_url()
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

if not SUPABASE_URL:
    sys.exit(
        "ERROR: SUPABASE_URL not found.\n"
        "  Set it as an env var or add NEXT_PUBLIC_SUPABASE_URL to app/.env.local"
    )
if not SUPABASE_KEY:
    sys.exit(
        "ERROR: SUPABASE_SERVICE_ROLE_KEY environment variable is not set.\n"
        "  Run:  export SUPABASE_SERVICE_ROLE_KEY=<your-service-role-key>"
    )

try:
    from supabase import create_client
except ImportError:
    sys.exit("supabase package not found — run: .venv/bin/pip install supabase")


# ── Config ────────────────────────────────────────────────────────────────────

CORPUS_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "corpus_30lines_clean.json")
BATCH_SIZE  = 50


# ── Helpers ───────────────────────────────────────────────────────────────────

def count_nonempty_lines(text: str) -> int:
    return sum(1 for line in (text or "").split("\n") if line.strip())


def build_row(poem: dict) -> dict:
    return {
        "id":         poem["id"],
        "title":      poem["Title"],
        "author":     poem["Author"],
        "body":       poem["text"],
        "line_count": count_nonempty_lines(poem["text"]),
        # embedding left null; populated separately
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Load corpus
    with open(CORPUS_PATH, encoding="utf-8") as f:
        poems = json.load(f)

    print(f"\n{'='*60}")
    print(f" INGEST: parataxis corpus → Supabase")
    print(f"{'='*60}")
    print(f"  Corpus      : {len(poems):,} poems")
    print(f"  Target table: poems")
    print(f"  Batch size  : {BATCH_SIZE}")
    print(f"  Supabase URL: {SUPABASE_URL}")
    print()

    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    rows = [build_row(p) for p in poems]

    inserted = 0
    errors   = []

    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch = rows[batch_start : batch_start + BATCH_SIZE]
        batch_end = batch_start + len(batch)

        try:
            result = (
                client.table("poems")
                .upsert(batch, on_conflict="id")
                .execute()
            )
            inserted += len(batch)
            print(f"  [{inserted:>4}/{len(rows)}]  batch {batch_start//BATCH_SIZE + 1} OK"
                  f"  (poems {batch_start+1}–{batch_end})")
        except Exception as exc:
            errors.append((batch_start, str(exc)))
            print(f"  [{batch_start+1}–{batch_end}]  ERROR: {exc}")

    print()
    print(f"{'='*60}")
    if errors:
        print(f"  DONE with {len(errors)} error(s). Inserted {inserted}/{len(rows)} poems.")
        for start, msg in errors:
            print(f"    batch starting at {start}: {msg}")
        sys.exit(1)
    else:
        print(f"  DONE. {inserted:,} poems upserted successfully.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
