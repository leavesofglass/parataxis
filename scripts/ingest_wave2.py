#!/usr/bin/env python3
"""
ingest_wave2.py — Insert wave2_final.json (1,364 poems) into the Supabase
poems table, joining scores and embeddings from the live-scoring and
embedding outputs.

Sources (joined on w2_NNNNN IDs):
  scripts/wave2_final.json          — poems  (corpus, title, author, body)
  scripts/score_wave2_results.jsonl — rubric + summary
  scripts/embed_wave2_results.jsonl — 1536-dim vectors

Assigns new sequential IDs starting from (current DB max) + 1.
Never touches existing rows.

Usage:
  python3 scripts/ingest_wave2.py               # dry run (default, no DB writes)
  python3 scripts/ingest_wave2.py --full        # actually insert
  python3 scripts/ingest_wave2.py --only-missing  # insert absent rows, batch=10
"""

import json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS        = Path(__file__).parent
ROOT           = SCRIPTS.parent
POEMS_PATH     = SCRIPTS / "wave2_final.json"
SCORES_PATH    = SCRIPTS / "score_wave2_results.jsonl"
EMBEDDINGS_PATH = SCRIPTS / "embed_wave2_results.jsonl"

BATCH_SIZE         = 50
BATCH_SIZE_MISSING = 10
ENRICHED_AT = datetime.now(timezone.utc).isoformat()


# ── Env ───────────────────────────────────────────────────────────────────────

def _load_env_local() -> dict[str, str]:
    env_path = ROOT / "app" / ".env.local"
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


# ── Helpers ───────────────────────────────────────────────────────────────────

def nonempty(val) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def count_nonempty_lines(text: str) -> int:
    return sum(1 for line in (text or "").split("\n") if line.strip())


def load_scores(path: Path) -> dict[str, dict]:
    """Return {poem_id: rubric_dict} for successful score results."""
    out: dict[str, dict] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            if d["response"]["status_code"] != 200:
                continue
            content = d["response"]["body"]["choices"][0]["message"]["content"]
            rubric = json.loads(content)
            out[d["custom_id"]] = rubric
        except Exception:
            pass
    return out


def load_embeddings(path: Path) -> dict[str, list[float]]:
    """Return {poem_id: vector} for successful embedding results."""
    out: dict[str, list[float]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            if d["response"]["status_code"] != 200:
                continue
            out[d["custom_id"]] = d["response"]["body"]["data"][0]["embedding"]
        except Exception:
            pass
    return out


def get_max_poem_num(client) -> int:
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


def build_row(poem: dict, poem_id: str, rubric: dict, vector: list[float]) -> dict:
    return {
        "id":                  poem_id,
        "title":               poem["title"],
        "author":              poem["author"],
        "body":                poem["body"],
        "line_count":          count_nonempty_lines(poem["body"]),
        "embedding":           vector,
        "corpus":              nonempty(poem.get("corpus")),
        "translator":          "",
        "summary":             nonempty(rubric.get("summary")),
        "mood":                rubric.get("mood"),
        "emotional_intensity": rubric.get("emotional_intensity"),
        "imagery":             rubric.get("imagery"),
        "accessibility":       rubric.get("accessibility"),
        "formality":           rubric.get("formality"),
        "enriched_at":         ENRICHED_AT,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def _report_total(client):
    resp = client.table("poems").select("id", count="exact").limit(1).execute()
    print(f"  Total rows in poems table: {resp.count:,}")


def get_existing_ids(client, target_ids: list[str]) -> set[str]:
    """Return the subset of target_ids that already exist in the DB."""
    existing: set[str] = set()
    chunk_size = 500
    for start in range(0, len(target_ids), chunk_size):
        chunk = target_ids[start : start + chunk_size]
        resp = client.table("poems").select("id").in_("id", chunk).execute()
        for row in resp.data:
            existing.add(row["id"])
    return existing


def main():
    only_missing = "--only-missing" in sys.argv
    dry_run      = "--full" not in sys.argv and not only_missing

    # Load all three sources
    poems      = json.loads(POEMS_PATH.read_text(encoding="utf-8"))
    scores     = load_scores(SCORES_PATH)
    embeddings = load_embeddings(EMBEDDINGS_PATH)

    # Validate: find any w2 IDs missing a score or embedding
    missing_score = []
    missing_embed = []
    for i, rec in enumerate(poems):
        w2_id = f"w2_{i:05d}"
        if w2_id not in scores:
            missing_score.append(w2_id)
        if w2_id not in embeddings:
            missing_embed.append(w2_id)

    # Corpus breakdown
    import collections
    corpus_counts = collections.Counter(r.get("corpus") for r in poems)

    mode_label = "[DRY RUN]" if dry_run else ("[ONLY MISSING]" if only_missing else "[FULL]")
    print(f"\n{'='*62}")
    print(f" INGEST WAVE 2  {mode_label}")
    print(f"{'='*62}")
    print(f"  Poems        : {len(poems):,}  ({POEMS_PATH.name})")
    print(f"  Scores loaded: {len(scores):,}  ({SCORES_PATH.name})")
    print(f"  Embeds loaded: {len(embeddings):,}  ({EMBEDDINGS_PATH.name})")
    print()
    print(f"  Corpus breakdown:")
    for corpus, count in sorted(corpus_counts.items()):
        print(f"    {corpus or '(none)':15s} {count:>5,}")
    print()

    if missing_score:
        print(f"  MISSING SCORES ({len(missing_score)}):")
        for w in missing_score[:20]:
            print(f"    {w}")
        if len(missing_score) > 20:
            print(f"    … and {len(missing_score) - 20} more")
        print()

    if missing_embed:
        print(f"  MISSING EMBEDDINGS ({len(missing_embed)}):")
        for w in missing_embed[:20]:
            print(f"    {w}")
        if len(missing_embed) > 20:
            print(f"    … and {len(missing_embed) - 20} more")
        print()

    if missing_score or missing_embed:
        print("  Cannot ingest with missing scores or embeddings. Fix and re-run.")
        print(f"{'='*62}\n")
        sys.exit(1)

    # Connect to Supabase
    SUPABASE_URL = _get("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
    SUPABASE_KEY = _get("SUPABASE_SERVICE_ROLE_KEY")

    if not SUPABASE_URL:
        sys.exit("ERROR: NEXT_PUBLIC_SUPABASE_URL not found in app/.env.local")
    if not SUPABASE_KEY:
        sys.exit("ERROR: SUPABASE_SERVICE_ROLE_KEY not found in app/.env.local")

    try:
        from supabase import create_client
    except ImportError:
        sys.exit("supabase package not found — run: pip install supabase")

    client  = create_client(SUPABASE_URL, SUPABASE_KEY)
    max_num = get_max_poem_num(client)

    if only_missing:
        # The full run already assigned IDs poem_{base+1}..poem_{base+1364}.
        # Derive base: max_num is the highest ID now in the DB (poem_13620),
        # so base = max_num - len(poems) = 12256.
        base     = max_num - len(poems)
        first_id = f"poem_{base + 1:04d}"
        last_id  = f"poem_{base + len(poems):04d}"

        # Build all target rows
        all_rows = []
        for i, rec in enumerate(poems):
            w2_id   = f"w2_{i:05d}"
            poem_id = f"poem_{base + i + 1:04d}"
            all_rows.append(build_row(rec, poem_id, scores[w2_id], embeddings[w2_id]))

        # Query which target IDs already exist
        target_ids   = [r["id"] for r in all_rows]
        existing_ids = get_existing_ids(client, target_ids)
        rows         = [r for r in all_rows if r["id"] not in existing_ids]

        print(f"  Derived base   : poem_{base:04d}")
        print(f"  Target range   : {first_id} … {last_id}")
        print(f"  Already in DB  : {len(existing_ids):,}")
        print(f"  Missing (to insert): {len(rows):,}")
        if rows:
            print(f"  Missing IDs    : {rows[0]['id']} … {rows[-1]['id']}")
        print(f"  Batch size     : {BATCH_SIZE_MISSING}")
        print()

        if not rows:
            print("  Nothing missing — all 1,364 rows are present.")
            print(f"{'='*62}\n")
            _report_total(client)
            return

        inserted = 0
        errors   = []

        for batch_start in range(0, len(rows), BATCH_SIZE_MISSING):
            batch     = rows[batch_start : batch_start + BATCH_SIZE_MISSING]
            batch_end = batch_start + len(batch)
            try:
                client.table("poems").upsert(
                    batch, on_conflict="id", ignore_duplicates=True
                ).execute()
                inserted += len(batch)
                print(
                    f"  [{inserted:>4}/{len(rows)}]  OK  "
                    f"{batch[0]['id']}–{batch[-1]['id']}"
                )
            except Exception as exc:
                errors.append((batch_start, str(exc)))
                print(f"  [{batch_start + 1}–{batch_end}]  ERROR: {exc}")

        print()
        print(f"{'='*62}")
        if errors:
            print(f"  DONE with {len(errors)} error(s). Inserted {inserted}/{len(rows)} missing rows.")
            for start, msg in errors:
                print(f"    batch at index {start}: {msg}")
            sys.exit(1)
        else:
            print(f"  DONE. {inserted:,} missing rows inserted.")
        print(f"{'='*62}\n")
        _report_total(client)
        return

    # ── Dry run / Full ingest (original flow) ────────────────────────────────

    first_id = f"poem_{max_num + 1:04d}"
    last_id  = f"poem_{max_num + len(poems):04d}"

    # Build all rows
    rows = []
    for i, rec in enumerate(poems):
        w2_id   = f"w2_{i:05d}"
        poem_id = f"poem_{max_num + i + 1:04d}"
        rows.append(build_row(rec, poem_id, scores[w2_id], embeddings[w2_id]))

    print(f"  Current DB max : poem_{max_num:04d}")
    print(f"  New ID range   : {first_id} … {last_id}")
    print(f"  Rows to insert : {len(rows):,}")
    print()

    # Sample preview (first 5 rows)
    print(f"  Sample rows (first 5):")
    for row in rows[:5]:
        rubric_str = (
            f"mood={row['mood']} ei={row['emotional_intensity']} "
            f"img={row['imagery']} acc={row['accessibility']} form={row['formality']}"
        )
        summary_preview = (row["summary"] or "")[:60].replace("\n", " ")
        print(f"    {row['id']}  [{row['corpus']}]  {row['title']!r}  by {row['author']}")
        print(f"      lines={row['line_count']}  {rubric_str}")
        print(f"      emb_dim={len(row['embedding'])}  summary={summary_preview!r}")
    print()

    if dry_run:
        print(f"  Dry run complete — no rows written.")
        print(f"  Re-run with --full to insert {len(rows):,} rows.")
        print(f"{'='*62}\n")
        return

    # ── Full ingest ───────────────────────────────────────────────────────────
    inserted = 0
    errors   = []

    for batch_start in range(0, len(rows), BATCH_SIZE):
        batch     = rows[batch_start : batch_start + BATCH_SIZE]
        batch_end = batch_start + len(batch)
        try:
            client.table("poems").upsert(
                batch, on_conflict="id", ignore_duplicates=True
            ).execute()
            inserted += len(batch)
            print(
                f"  [{inserted:>5}/{len(rows)}]  OK  "
                f"{batch[0]['id']}–{batch[-1]['id']}"
            )
        except Exception as exc:
            errors.append((batch_start, str(exc)))
            print(f"  [{batch_start + 1}–{batch_end}]  ERROR: {exc}")

    print()
    print(f"{'='*62}")
    if errors:
        print(f"  DONE with {len(errors)} error(s). Inserted {inserted}/{len(rows)} rows.")
        for start, msg in errors:
            print(f"    batch at index {start}: {msg}")
        sys.exit(1)
    else:
        print(f"  DONE. {inserted:,} poems inserted ({first_id} … {last_id}).")
    print(f"{'='*62}\n")


if __name__ == "__main__":
    main()
