#!/usr/bin/env python3
"""
score_live.py — Score poems via live (non-batch) OpenAI API calls with concurrency.

Reads:
  scripts/dedup_cleaned.json        — full corpus
  scripts/batch_score_chunks.json   — determines which poem IDs are already scored
                                      (chunk 0: poem_00000–poem_02544)
Writes:
  scripts/score_live_results.jsonl  — one JSON line per poem, same format as
                                      batch output so batch_retrieve.py can read it

Usage:
  python3 scripts/score_live.py
  python3 scripts/score_live.py --concurrency 40
  python3 scripts/score_live.py --resume        # skip poems already in output file
"""

import argparse, asyncio, json, os, sys, time
from pathlib import Path

SCRIPTS    = Path(__file__).parent
ROOT       = SCRIPTS.parent
CLEANED    = SCRIPTS / "dedup_cleaned.json"
STATE_PATH = SCRIPTS / "batch_score_chunks.json"
OUT_PATH   = SCRIPTS / "score_live_results.jsonl"

SCORE_MODEL = "gpt-4.1-nano"

RUBRIC_SYSTEM = """\
You are a careful poetry analyst. Given a poem, output JSON with these keys:
  "mood"               : int 1–5  (1=very dark/heavy, 5=light/playful/uplifting)
  "emotional_intensity": int 1–5  (1=quiet/restrained, 5=intense/visceral)
  "imagery"            : int 1–5  (1=abstract/conceptual, 5=concrete/sensory)
  "accessibility"      : int 1–5  (1=very dense/difficult, 5=accessible/conversational)
  "formality"          : int 1–5  (1=very experimental/fragmented, 5=very traditional/formal)
  "summary"            : str  2–3 sentences describing subject, tone, and what makes this poem
                               distinctive — for a recommendation engine.

Output valid JSON only. No explanation outside the JSON object."""


def load_env():
    p = ROOT / "app" / ".env.local"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())


def already_scored_ids() -> set[str]:
    """Poem IDs already covered by completed batch chunks."""
    if not STATE_PATH.exists():
        return set()
    state = json.loads(STATE_PATH.read_text())
    scored = set()
    for chunk in state.get("chunks", []):
        if chunk.get("status") == "completed":
            scored.update(chunk.get("poem_indices", []))
    return scored


def load_output_successes() -> tuple[set[str], list[str]]:
    """Return (set of successfully-scored poem IDs, list of successful raw lines)."""
    if not OUT_PATH.exists():
        return set(), []
    ids: set[str] = set()
    good_lines: list[str] = []
    for line in OUT_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            if d["response"]["status_code"] == 200:
                ids.add(d["custom_id"])
                good_lines.append(line)
        except Exception:
            pass
    return ids, good_lines


def make_result(poem_id: str, content: str) -> dict:
    return {
        "custom_id": poem_id,
        "response": {
            "status_code": 200,
            "body": {
                "choices": [{"message": {"content": content}}],
            },
        },
    }


def make_error_result(poem_id: str, error: str) -> dict:
    return {
        "custom_id": poem_id,
        "response": {
            "status_code": 500,
            "body": {"error": error},
        },
    }


async def score_one(client, sem: asyncio.Semaphore, poem_id: str,
                    author: str, title: str, text: str,
                    retries: int = 8) -> dict:
    async with sem:
        for attempt in range(retries):
            try:
                resp = await client.chat.completions.create(
                    model=SCORE_MODEL,
                    max_tokens=512,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": RUBRIC_SYSTEM},
                        {"role": "user",
                         "content": f"Author: {author}\nTitle: {title}\n\n{text}"},
                    ],
                )
                return make_result(poem_id, resp.choices[0].message.content)
            except Exception as exc:
                err = str(exc)
                if attempt == retries - 1:
                    return make_error_result(poem_id, err)
                # 429 rate limit: back off longer
                backoff = 30 * (attempt + 1) if "429" in err else 2 ** attempt
                await asyncio.sleep(backoff)


async def run(concurrency: int, resume: bool):
    load_env()
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        sys.exit("ERROR: OPENAI_API_KEY not set")

    try:
        import openai
    except ImportError:
        sys.exit("openai package not found — run: .venv/bin/pip install openai")

    data = json.loads(CLEANED.read_text(encoding="utf-8"))

    batch_done = already_scored_ids()
    live_done, good_lines = load_output_successes() if resume else (set(), [])
    skip       = batch_done | live_done

    # Build work list: (poem_id, author, title, text)
    work = []
    for i, rec in enumerate(data):
        poem_id = f"poem_{i:05d}"
        if poem_id in skip:
            continue
        text = (rec.get("poem_text") or "").strip()
        if not text:
            continue
        work.append((poem_id, rec.get("author", ""), rec.get("title", ""), text))

    n_batch   = len(batch_done)
    n_resume  = len(live_done)
    n_todo    = len(work)

    print(f"\n{'='*60}")
    print(f" LIVE SCORING  ({SCORE_MODEL})")
    print(f"{'='*60}")
    print(f"  Total poems  : {len(data):,}")
    print(f"  Batch done   : {n_batch:,}  (chunk 0)")
    if resume:
        print(f"  Resumed      : {n_resume:,}  (already in output file)")
    print(f"  To score     : {n_todo:,}")
    print(f"  Concurrency  : {concurrency}")
    print()

    if n_todo == 0:
        print("Nothing to do.")
        return

    # On resume, rewrite output file with only the successful lines to purge errors
    if resume and good_lines:
        OUT_PATH.write_text("\n".join(good_lines) + "\n", encoding="utf-8")
    out_file = OUT_PATH.open("a", encoding="utf-8")

    client    = openai.AsyncOpenAI(api_key=api_key)
    sem       = asyncio.Semaphore(concurrency)
    done      = 0
    errors    = 0
    t0        = time.monotonic()
    lock      = asyncio.Lock()

    async def worker(item):
        nonlocal done, errors
        poem_id, author, title, text = item
        result = await score_one(client, sem, poem_id, author, title, text)
        if result["response"]["status_code"] != 200:
            errors += 1
        async with lock:
            out_file.write(json.dumps(result, ensure_ascii=False) + "\n")
            out_file.flush()
            done += 1
            if done % 100 == 0 or done == n_todo:
                elapsed = time.monotonic() - t0
                rate    = done / elapsed if elapsed > 0 else 0
                eta     = (n_todo - done) / rate if rate > 0 else 0
                print(f"  [{done:>5}/{n_todo}]  {rate:.1f} req/s  ETA {eta/60:.1f} min"
                      + (f"  ({errors} errors)" if errors else ""))

    await asyncio.gather(*[worker(item) for item in work])

    out_file.close()
    elapsed = time.monotonic() - t0
    print(f"\n  Done in {elapsed/60:.1f} min.  {errors} errors.")
    print(f"  Output: {OUT_PATH}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--resume", action="store_true",
                        help="Skip poems already written to output file")
    args = parser.parse_args()
    asyncio.run(run(args.concurrency, args.resume))


if __name__ == "__main__":
    main()
