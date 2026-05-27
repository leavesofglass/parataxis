"""
enrich_corpus.py — corpus enrichment + embeddings pipeline for parataxis.

For each poem where enriched_at IS NULL:
  1. GPT-4.1 via Batch API scores 5 rubric dimensions and writes a 1-2 sentence
     interpretive summary, returning JSON conforming to a strict json_schema.
  2. text-embedding-3-large (dimensions=1536) embeds title + author + body +
     summary into the existing `vector(1536)` column.
  3. All 7 fields plus `enriched_at = now()` are written back via service-role.

Idempotent (skips enriched_at IS NOT NULL).
Resumable (state file persists batch IDs across runs).

Required env (read from environment, falling back to app/.env.local):
  OPENAI_API_KEY
  SUPABASE_SERVICE_ROLE_KEY
  NEXT_PUBLIC_SUPABASE_URL  (or SUPABASE_URL)

Run:
  .venv/bin/python scripts/enrich_corpus.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


# ── Pricing (USD per 1M tokens) ───────────────────────────────────────────────
# GPT-4.1 Batch API is 50% off the standard rate.
GPT41_BATCH_INPUT_PER_M  = 1.00
GPT41_BATCH_OUTPUT_PER_M = 4.00
EMBED_LARGE_PER_M        = 0.13


# ── Paths ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT  = SCRIPT_DIR.parent
ENV_LOCAL  = REPO_ROOT / "app" / ".env.local"
STATE_FILE = SCRIPT_DIR / ".enrich_state.json"
BATCH_INPUT_FILE  = SCRIPT_DIR / ".enrich_batch_input.jsonl"
BATCH_OUTPUT_FILE = SCRIPT_DIR / ".enrich_batch_output.jsonl"


# ── env loading (.env.local fallback) ─────────────────────────────────────────

def _read_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            out[key.strip()] = val.strip()
    return out


def load_env(name: str, *fallbacks: str) -> str:
    if val := os.environ.get(name, "").strip():
        return val
    dotenv = _read_dotenv(ENV_LOCAL)
    for key in (name, *fallbacks):
        if val := dotenv.get(key, "").strip():
            return val
    return ""


SUPABASE_URL = load_env("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = load_env("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_KEY   = load_env("OPENAI_API_KEY")

for var, name in [(SUPABASE_URL, "SUPABASE_URL / NEXT_PUBLIC_SUPABASE_URL"),
                  (SUPABASE_KEY, "SUPABASE_SERVICE_ROLE_KEY"),
                  (OPENAI_KEY,   "OPENAI_API_KEY")]:
    if not var:
        sys.exit(f"ERROR: {name} not set in env or {ENV_LOCAL}")

try:
    from supabase import create_client
except ImportError:
    sys.exit("supabase package missing — run: pip install supabase")
try:
    from openai import OpenAI
    from openai import APIConnectionError, APITimeoutError, RateLimitError, InternalServerError
except ImportError:
    sys.exit("openai package missing — run: pip install openai")


supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
openai   = OpenAI(api_key=OPENAI_KEY)


# ── Prompt + schema ───────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a literary critic scoring poems on 5 dimensions, each on a 0–10 scale. Be calibrated: 5 is average, 10 is extreme. Then write a 1–2 sentence summary of what the poem is doing (its move, tone, register, what it's actually about), not a paraphrase of content.

Dimensions:
- emotional_intensity: quiet/restrained → searing/anguished
- intellectual_demand: immediately accessible → requires multiple readings
- sensory_richness: spare/abstract → image-saturated/lush
- formal_structure: free verse / loose → strict meter and rhyme
- voice_register: impersonal/observational → confessional/personal

Return JSON matching the provided schema."""

RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "poem_enrichment",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "emotional_intensity": {"type": "integer", "minimum": 0, "maximum": 10},
                "intellectual_demand": {"type": "integer", "minimum": 0, "maximum": 10},
                "sensory_richness":    {"type": "integer", "minimum": 0, "maximum": 10},
                "formal_structure":    {"type": "integer", "minimum": 0, "maximum": 10},
                "voice_register":      {"type": "integer", "minimum": 0, "maximum": 10},
                "summary":             {"type": "string"},
            },
            "required": [
                "emotional_intensity", "intellectual_demand", "sensory_richness",
                "formal_structure", "voice_register", "summary",
            ],
            "additionalProperties": False,
        },
    },
}

MODEL_ENRICH = "gpt-4.1"
MODEL_EMBED  = "text-embedding-3-large"
EMBED_DIMS   = 1536


def user_message(title: str, author: str, body: str) -> str:
    return f"TITLE: {title}\nAUTHOR: {author}\n\n{body}"


def embed_input(title: str, author: str, body: str, summary: str) -> str:
    return f"TITLE: {title}\nAUTHOR: {author}\n\n{body}\n\nSUMMARY: {summary}"


# ── State persistence ────────────────────────────────────────────────────────

def load_state() -> dict | None:
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def clear_state() -> None:
    for p in (STATE_FILE, BATCH_INPUT_FILE, BATCH_OUTPUT_FILE):
        if p.exists():
            p.unlink()


# ── Retry helper ─────────────────────────────────────────────────────────────

TRANSIENT_EXC = (APIConnectionError, APITimeoutError, RateLimitError, InternalServerError)


def with_one_retry(fn, *, label: str):
    """Run fn(); on transient error, wait 2s and retry once."""
    try:
        return fn()
    except TRANSIENT_EXC as exc:
        time.sleep(2)
        try:
            return fn()
        except Exception as exc2:
            raise RuntimeError(f"{label}: {type(exc2).__name__}: {exc2}") from exc2
    except Exception as exc:
        # Treat unknown HTTP errors with 5xx as transient too.
        msg = str(exc).lower()
        if any(code in msg for code in ("500", "502", "503", "504", "timeout", "connection")):
            time.sleep(2)
            try:
                return fn()
            except Exception as exc2:
                raise RuntimeError(f"{label}: {type(exc2).__name__}: {exc2}") from exc2
        raise


# ── Phase 1: build & submit batch ────────────────────────────────────────────

def count_enriched_poems() -> int:
    """Return the count of poems where enriched_at IS NOT NULL."""
    resp = (
        supabase.table("poems")
        .select("id", count="exact")
        .filter("enriched_at", "not.is", "null")
        .limit(1)
        .execute()
    )
    return resp.count or 0


def fetch_unenriched_poems() -> list[dict]:
    """Pull all poems where enriched_at IS NULL, paging through 1000-row chunks."""
    rows: list[dict] = []
    offset = 0
    page_size = 1000
    while True:
        resp = (
            supabase.table("poems")
            .select("id, title, author, body")
            .is_("enriched_at", "null")
            .order("id")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        chunk = resp.data or []
        rows.extend(chunk)
        if len(chunk) < page_size:
            break
        offset += page_size
    return rows


def build_batch_jsonl(poems: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for poem in poems:
            line = {
                "custom_id": poem["id"],
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": MODEL_ENRICH,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_message(
                            poem["title"], poem["author"], poem["body"])},
                    ],
                    "response_format": RESPONSE_FORMAT,
                },
            }
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def submit_batch(poems: list[dict]) -> dict:
    print(f"  Building JSONL for {len(poems)} poems …")
    build_batch_jsonl(poems, BATCH_INPUT_FILE)

    print(f"  Uploading to OpenAI Files …")
    with BATCH_INPUT_FILE.open("rb") as fh:
        uploaded = openai.files.create(file=fh, purpose="batch")

    print(f"  Creating batch (file_id={uploaded.id}) …")
    batch = openai.batches.create(
        input_file_id=uploaded.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"purpose": "parataxis_enrichment"},
    )
    state = {
        "batch_id":       batch.id,
        "input_file_id":  uploaded.id,
        "submitted_at":   datetime.now(timezone.utc).isoformat(),
        "poem_count":     len(poems),
    }
    save_state(state)
    print(f"  Batch submitted: {batch.id}  (state → {STATE_FILE.name})")
    return state


# ── Phase 2: poll batch ──────────────────────────────────────────────────────

POLL_INTERVAL_SEC = 15


def poll_batch(batch_id: str) -> object:
    while True:
        batch = openai.batches.retrieve(batch_id)
        counts = batch.request_counts
        done = (counts.completed or 0) + (counts.failed or 0) if counts else 0
        total = counts.total or 0 if counts else 0
        print(f"  status={batch.status:<12} completed={counts.completed if counts else 0}"
              f" failed={counts.failed if counts else 0} total={total}")
        if batch.status in {"completed", "failed", "expired", "cancelled"}:
            return batch
        time.sleep(POLL_INTERVAL_SEC)


# ── Phase 3: process results ─────────────────────────────────────────────────

def download_output(output_file_id: str) -> list[dict]:
    print(f"  Downloading output_file_id={output_file_id} …")
    raw = openai.files.content(output_file_id).text
    BATCH_OUTPUT_FILE.write_text(raw, encoding="utf-8")
    lines = [json.loads(ln) for ln in raw.splitlines() if ln.strip()]
    print(f"  Parsed {len(lines)} result lines.")
    return lines


def parse_enrichment(line: dict) -> tuple[str, dict | None, str | None, dict | None]:
    """Returns (poem_id, parsed_json, error_msg, usage_dict)."""
    poem_id = line.get("custom_id", "<unknown>")
    if line.get("error"):
        return poem_id, None, f"batch error: {line['error']}", None
    body = (line.get("response") or {}).get("body") or {}
    choices = body.get("choices") or []
    if not choices:
        return poem_id, None, "no choices in response", None
    msg = choices[0].get("message") or {}
    if msg.get("refusal"):
        return poem_id, None, f"refusal: {msg['refusal']}", None
    content = msg.get("content")
    if not content:
        return poem_id, None, "empty content", None
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        return poem_id, None, f"json parse: {exc}", None
    return poem_id, parsed, None, body.get("usage")


def call_embedding(text: str) -> tuple[list[float], int]:
    """Returns (vector, tokens_used)."""
    def _go():
        return openai.embeddings.create(
            model=MODEL_EMBED, input=text, dimensions=EMBED_DIMS,
        )
    resp = with_one_retry(_go, label="embedding")
    return resp.data[0].embedding, resp.usage.total_tokens


def write_poem_row(poem_id: str, enrichment: dict, vector: list[float]) -> None:
    def _go():
        return (
            supabase.table("poems")
            .update({
                "emotional_intensity": enrichment["emotional_intensity"],
                "intellectual_demand": enrichment["intellectual_demand"],
                "sensory_richness":    enrichment["sensory_richness"],
                "formal_structure":    enrichment["formal_structure"],
                "voice_register":      enrichment["voice_register"],
                "summary":             enrichment["summary"],
                "embedding":           vector,
                "enriched_at":         datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", poem_id)
            .execute()
        )
    with_one_retry(_go, label=f"db update {poem_id}")


def process_results(result_lines: list[dict], poems_by_id: dict[str, dict]) -> dict:
    enriched_total = 0
    failed: list[tuple[str, str]] = []
    batch_input_tokens  = 0
    batch_output_tokens = 0
    embed_tokens        = 0
    total = len(result_lines)
    done  = 0

    def cost_so_far() -> float:
        return (
            batch_input_tokens  / 1_000_000 * GPT41_BATCH_INPUT_PER_M  +
            batch_output_tokens / 1_000_000 * GPT41_BATCH_OUTPUT_PER_M +
            embed_tokens        / 1_000_000 * EMBED_LARGE_PER_M
        )

    def worker(line: dict) -> tuple[str, str | None, dict | None]:
        poem_id, enrichment, err, usage = parse_enrichment(line)
        if err or not enrichment:
            return poem_id, err or "unknown parse error", usage
        poem = poems_by_id.get(poem_id)
        if not poem:
            return poem_id, f"no DB row for {poem_id}", usage
        try:
            text = embed_input(poem["title"], poem["author"], poem["body"], enrichment["summary"])
            vector, etoks = call_embedding(text)
        except Exception as exc:
            return poem_id, f"embedding: {exc}", {**(usage or {}), "_embed_tokens": 0}
        try:
            write_poem_row(poem_id, enrichment, vector)
        except Exception as exc:
            return poem_id, f"db write: {exc}", {**(usage or {}), "_embed_tokens": etoks}
        return poem_id, None, {**(usage or {}), "_embed_tokens": etoks}

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = [pool.submit(worker, line) for line in result_lines]
        for fut in as_completed(futures):
            poem_id, err, usage = fut.result()
            done += 1
            if usage:
                batch_input_tokens  += usage.get("prompt_tokens",     0) or 0
                batch_output_tokens += usage.get("completion_tokens", 0) or 0
                embed_tokens        += usage.get("_embed_tokens",     0) or 0
            if err:
                failed.append((poem_id, err))
                print(f"  [{done}/{total}] FAILED {poem_id}: {err}, continuing")
            else:
                enriched_total += 1
                print(f"  [{done}/{total}] Enriched {poem_id} (running cost: ${cost_so_far():.4f})")

    return {
        "enriched":            enriched_total,
        "failed":              failed,
        "batch_input_tokens":  batch_input_tokens,
        "batch_output_tokens": batch_output_tokens,
        "embed_tokens":        embed_tokens,
        "cost_usd":            cost_so_far(),
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 64)
    print(" enrich_corpus — parataxis")
    print("=" * 64)

    skipped = count_enriched_poems()
    enriched_this_run = 0
    exit_code = 0

    state = load_state()

    if state is None:
        poems = fetch_unenriched_poems()
        if not poems:
            print("Nothing to enrich (all poems have enriched_at). Done.")
        else:
            print(f"  Found {len(poems)} unenriched poems.")
            state = submit_batch(poems)
    else:
        print(f"  Resuming from state: batch={state['batch_id']}"
              f" submitted={state['submitted_at']}")

    if state is not None:
        batch = poll_batch(state["batch_id"])

        if batch.status != "completed":
            print(f"\n  Batch ended with status={batch.status}. Aborting.")
            if batch.errors:
                for err in (batch.errors.data or [])[:10]:
                    print(f"    error: {err}")
            exit_code = 1
        else:
            state["output_file_id"] = batch.output_file_id
            save_state(state)

            # Map poem_id → row (re-fetch in case the DB changed between submit + now).
            print("  Loading current poem rows for embedding stage …")
            poems_by_id = {p["id"]: p for p in fetch_unenriched_poems()}

            result_lines = download_output(batch.output_file_id)
            stats = process_results(result_lines, poems_by_id)
            enriched_this_run = stats["enriched"]

            print()
            print("=" * 64)
            print(" final report")
            print("=" * 64)
            print(f"  Enriched : {stats['enriched']}")
            print(f"  Failed   : {len(stats['failed'])}")
            if stats["failed"]:
                for poem_id, err in stats["failed"]:
                    print(f"    {poem_id}: {err}")
            print(f"  Tokens   : batch_in={stats['batch_input_tokens']:,}"
                  f" batch_out={stats['batch_output_tokens']:,}"
                  f" embed={stats['embed_tokens']:,}")
            print(f"  Cost     : ${stats['cost_usd']:.4f} USD (actual, from usage data)")
            print("=" * 64)

            if not stats["failed"]:
                clear_state()
                print("  state file cleared.")
            else:
                print("  state file retained — re-run to retry remaining unenriched poems.")
                exit_code = 1

    total_now = skipped + enriched_this_run
    print(f"  Skipped {skipped} already-enriched, processed {enriched_this_run} new, total now {total_now}.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
