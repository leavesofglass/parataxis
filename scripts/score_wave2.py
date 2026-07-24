#!/usr/bin/env python3
"""
score_wave2.py — Score wave2_final.json (1,364 poems) via live OpenAI API.

Reads : scripts/wave2_final.json
Writes: scripts/score_wave2_results.jsonl  — one JSON line per poem, same
        format as batch output so downstream ingest can read it directly.

Stable IDs: w2_00000 … w2_01363

Usage:
  python3 scripts/score_wave2.py
  python3 scripts/score_wave2.py --resume        # skip already-written successes
  python3 scripts/score_wave2.py --concurrency 6 # default
"""

import argparse, asyncio, json, os, sys, time
from pathlib import Path

SCRIPTS   = Path(__file__).parent
ROOT      = SCRIPTS.parent
IN_PATH   = SCRIPTS / "wave2_final.json"
OUT_PATH  = SCRIPTS / "score_wave2_results.jsonl"

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

    data = json.loads(IN_PATH.read_text(encoding="utf-8"))

    live_done, good_lines = load_output_successes() if resume else (set(), [])

    work = []
    for i, rec in enumerate(data):
        poem_id = f"w2_{i:05d}"
        if poem_id in live_done:
            continue
        text = (rec.get("body") or "").strip()
        if not text:
            continue
        work.append((poem_id, rec.get("author", ""), rec.get("title", ""), text))

    n_resume = len(live_done)
    n_todo   = len(work)

    print(f"\n{'='*60}")
    print(f" WAVE-2 SCORING  ({SCORE_MODEL})")
    print(f"{'='*60}")
    print(f"  Input file   : {IN_PATH.name}")
    print(f"  Total poems  : {len(data):,}")
    if resume:
        print(f"  Resumed      : {n_resume:,}  (already in output file)")
    print(f"  To score     : {n_todo:,}")
    print(f"  Concurrency  : {concurrency}")
    print(f"  Output       : {OUT_PATH.name}")
    print()

    if n_todo == 0:
        print("Nothing to do.")
        _verify(data)
        return

    if resume and good_lines:
        OUT_PATH.write_text("\n".join(good_lines) + "\n", encoding="utf-8")
    out_file = OUT_PATH.open("a", encoding="utf-8")

    client = openai.AsyncOpenAI(api_key=api_key)
    sem    = asyncio.Semaphore(concurrency)
    done   = 0
    errors = 0
    t0     = time.monotonic()
    lock   = asyncio.Lock()

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

    _verify(data)


def _verify(data):
    """Count successful scores and assert against expected total."""
    if not OUT_PATH.exists():
        print("WARNING: output file not found.")
        return
    successes = 0
    errors    = 0
    for line in OUT_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            if d["response"]["status_code"] == 200:
                successes += 1
            else:
                errors += 1
        except Exception:
            errors += 1

    expected = len(data)
    status   = "OK" if successes == expected else "MISMATCH"
    print(f"{'='*60}")
    print(f" VERIFICATION  [{status}]")
    print(f"{'='*60}")
    print(f"  Expected successes : {expected:,}")
    print(f"  Actual successes   : {successes:,}")
    if errors:
        print(f"  Errors/bad lines   : {errors:,}")
    if successes == expected:
        print(f"  All {expected:,} poems scored successfully.")
    else:
        diff = expected - successes
        print(f"  MISSING {diff:,} poems. Run with --resume to fill gaps.")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--resume", action="store_true",
                        help="Skip poems already written to output file")
    parser.add_argument("--verify", action="store_true",
                        help="Just verify the output file without scoring")
    args = parser.parse_args()

    if args.verify:
        load_env()
        data = json.loads(IN_PATH.read_text(encoding="utf-8"))
        _verify(data)
        return

    asyncio.run(run(args.concurrency, args.resume))


if __name__ == "__main__":
    main()
