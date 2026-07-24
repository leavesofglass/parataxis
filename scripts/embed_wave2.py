#!/usr/bin/env python3
"""
embed_wave2.py — Embed wave2_final.json via live OpenAI API calls.

Model : text-embedding-3-small (default dims = 1536, no dimensions param)
Input : body.strip() only — matches batch_enrich.py exactly
IDs   : w2_00000 … w2_01363

Reads : scripts/wave2_final.json
Writes: scripts/embed_wave2_results.jsonl  — one JSON line per poem,
        same format as the batch embeddings output so ingest can read it.

Usage:
  python3 scripts/embed_wave2.py
  python3 scripts/embed_wave2.py --resume      # skip already-written successes
  python3 scripts/embed_wave2.py --verify      # check output without embedding
"""

import argparse, asyncio, json, os, sys, time
from pathlib import Path

SCRIPTS    = Path(__file__).parent
ROOT       = SCRIPTS.parent
IN_PATH    = SCRIPTS / "wave2_final.json"
OUT_PATH   = SCRIPTS / "embed_wave2_results.jsonl"

EMBED_MODEL = "text-embedding-3-small"
EXPECTED_DIMS = 1536


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


def make_result(poem_id: str, vector: list[float]) -> dict:
    return {
        "custom_id": poem_id,
        "response": {
            "status_code": 200,
            "body": {
                "data": [{"embedding": vector}],
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


async def embed_one(client, sem: asyncio.Semaphore, poem_id: str, text: str,
                    retries: int = 8) -> dict:
    async with sem:
        for attempt in range(retries):
            try:
                resp = await client.embeddings.create(
                    model=EMBED_MODEL,
                    input=text,
                    encoding_format="float",
                )
                return make_result(poem_id, resp.data[0].embedding)
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
        work.append((poem_id, text))

    n_resume = len(live_done)
    n_todo   = len(work)

    print(f"\n{'='*60}")
    print(f" WAVE-2 EMBEDDINGS  ({EMBED_MODEL})")
    print(f"{'='*60}")
    print(f"  Input file   : {IN_PATH.name}")
    print(f"  Total poems  : {len(data):,}")
    if resume:
        print(f"  Resumed      : {n_resume:,}  (already in output file)")
    print(f"  To embed     : {n_todo:,}")
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
        poem_id, text = item
        result = await embed_one(client, sem, poem_id, text)
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
    if not OUT_PATH.exists():
        print("WARNING: output file not found.")
        return

    successes   = 0
    errors      = 0
    wrong_dims  = []

    for line in OUT_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
            if d["response"]["status_code"] == 200:
                vec = d["response"]["body"]["data"][0]["embedding"]
                if len(vec) != EXPECTED_DIMS:
                    wrong_dims.append((d["custom_id"], len(vec)))
                successes += 1
            else:
                errors += 1
        except Exception:
            errors += 1

    expected = len(data)
    count_ok = successes == expected
    dims_ok  = len(wrong_dims) == 0
    status   = "OK" if (count_ok and dims_ok) else "MISMATCH"

    print(f"{'='*60}")
    print(f" VERIFICATION  [{status}]")
    print(f"{'='*60}")
    print(f"  Expected successes : {expected:,}")
    print(f"  Actual successes   : {successes:,}")
    if errors:
        print(f"  Errors/bad lines   : {errors:,}")
    if wrong_dims:
        print(f"  Wrong-dim vectors  : {len(wrong_dims):,}  (expected {EXPECTED_DIMS})")
        for pid, d in wrong_dims[:10]:
            print(f"    {pid}: {d} dims")
    if count_ok and dims_ok:
        print(f"  All {expected:,} vectors present, all {EXPECTED_DIMS}-dim. Ready to ingest.")
    else:
        if not count_ok:
            print(f"  MISSING {expected - successes:,} poems. Run with --resume to fill gaps.")
        if wrong_dims:
            print(f"  FIX REQUIRED: wrong-dim vectors must be re-embedded.")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--resume", action="store_true",
                        help="Skip poems already written to output file")
    parser.add_argument("--verify", action="store_true",
                        help="Check output file without embedding")
    args = parser.parse_args()

    if args.verify:
        load_env()
        data = json.loads(IN_PATH.read_text(encoding="utf-8"))
        _verify(data)
        return

    asyncio.run(run(args.concurrency, args.resume))


if __name__ == "__main__":
    main()
