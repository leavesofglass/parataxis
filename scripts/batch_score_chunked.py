#!/usr/bin/env python3
"""
batch_score_chunked.py — Submit scoring job in 4 sequential chunks to stay
under the org's 2M enqueued-token limit per model.

Each chunk is ~2,545 poems (~1.75M tokens). A chunk must complete before
the next is submitted.

Usage:
  python3 batch_score_chunked.py           # show status of all chunks
  python3 batch_score_chunked.py --submit  # submit next pending chunk
  python3 batch_score_chunked.py --run     # loop: submit + poll until all done

State is saved to batch_score_chunks.json.
"""

import argparse, json, os, time
from pathlib import Path

SCRIPTS    = Path(__file__).parent
ROOT       = SCRIPTS.parent
CLEANED    = SCRIPTS / "dedup_cleaned.json"
STATE_PATH = SCRIPTS / "batch_score_chunks.json"
CHUNK_SIZE = 2545   # ~1.75M tokens per chunk at avg 700 tok/poem
POLL_SEC   = 120

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


def load_env(path):
    p = Path(path)
    if not p.exists(): return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line: continue
        k, _, v = line.partition('=')
        os.environ.setdefault(k.strip(), v.strip())


def build_requests(data):
    reqs = []
    for i, rec in enumerate(data):
        text   = (rec.get("poem_text") or "").strip()
        author = rec.get("author", "")
        title  = rec.get("title", "")
        if not text:
            reqs.append(None)
            continue
        reqs.append({
            "custom_id": f"poem_{i:05d}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": "gpt-4o-mini",
                "max_tokens": 512,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": RUBRIC_SYSTEM},
                    {"role": "user",
                     "content": f"Author: {author}\nTitle: {title}\n\n{text}"},
                ],
            },
        })
    return reqs


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"chunks": [], "done": False}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2))


def submit_chunk(client, chunk_reqs, chunk_idx):
    jsonl = "\n".join(json.dumps(r, ensure_ascii=False) for r in chunk_reqs) + "\n"
    tmp = SCRIPTS / f"_chunk_{chunk_idx}.jsonl"
    tmp.write_text(jsonl, encoding="utf-8")
    size_mb = tmp.stat().st_size / 1_048_576
    print(f"  Uploading chunk {chunk_idx} ({len(chunk_reqs)} poems, {size_mb:.1f} MB)...")
    with open(tmp, "rb") as f:
        file_obj = client.files.create(file=f, purpose="batch")
    tmp.unlink()
    batch = client.batches.create(
        input_file_id=file_obj.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
        metadata={"description": f"poetry-app: scoring chunk {chunk_idx}"},
    )
    print(f"  batch_id={batch.id}  status={batch.status}")
    return {"chunk": chunk_idx, "batch_id": batch.id, "status": batch.status,
            "poem_indices": [r["custom_id"] for r in chunk_reqs]}


def refresh_status(client, state):
    for c in state["chunks"]:
        if c["status"] not in ("completed", "failed"):
            b = client.batches.retrieve(c["batch_id"])
            c["status"] = b.status
            c["request_counts"] = {
                "completed": b.request_counts.completed,
                "failed": b.request_counts.failed,
                "total": b.request_counts.total,
            }
    save_state(state)


def print_status(state, n_chunks, n_total):
    submitted = len(state["chunks"])
    print(f"Scoring chunks: {submitted}/{n_chunks} submitted")
    for c in state["chunks"]:
        counts = c.get("request_counts", {})
        print(f"  chunk {c['chunk']}: {c['status']}  "
              f"{counts.get('completed','?')}/{counts.get('total','?')} requests")
    if submitted < n_chunks:
        next_start = submitted * CHUNK_SIZE
        next_end   = min(next_start + CHUNK_SIZE, n_total)
        print(f"  chunk {submitted}: pending (poems {next_start}–{next_end})")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env",    default="app/.env.local")
    parser.add_argument("--submit", action="store_true", help="Submit next pending chunk")
    parser.add_argument("--run",    action="store_true", help="Submit + poll all chunks to completion")
    args = parser.parse_args()

    load_env(ROOT / args.env if not Path(args.env).is_absolute() else args.env)
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise SystemExit("ERROR: OPENAI_API_KEY not set")

    import openai
    client = openai.OpenAI(api_key=api_key)

    data = json.loads(CLEANED.read_text(encoding="utf-8"))
    all_reqs = build_requests(data)
    # Split into chunks (skip None placeholders but preserve poem_id alignment)
    valid_reqs = [r for r in all_reqs if r is not None]
    chunks = [valid_reqs[i:i+CHUNK_SIZE] for i in range(0, len(valid_reqs), CHUNK_SIZE)]
    n_chunks = len(chunks)

    state = load_state()
    refresh_status(client, state)
    print_status(state, n_chunks, len(valid_reqs))

    if not (args.submit or args.run):
        return

    while True:
        submitted = len(state["chunks"])

        # Check if last submitted chunk failed
        if state["chunks"] and state["chunks"][-1]["status"] == "failed":
            print(f"\nERROR: chunk {state['chunks'][-1]['chunk']} failed.")
            break

        # Check if last submitted chunk is still running
        if state["chunks"] and state["chunks"][-1]["status"] not in ("completed",):
            if args.run:
                print(f"\nWaiting {POLL_SEC}s for chunk {state['chunks'][-1]['chunk']}...")
                time.sleep(POLL_SEC)
                refresh_status(client, state)
                print_status(state, n_chunks, len(valid_reqs))
                continue
            else:
                print(f"\nChunk {state['chunks'][-1]['chunk']} still running — re-run with --submit when it completes.")
                break

        # All done?
        if submitted == n_chunks:
            state["done"] = True
            save_state(state)
            print("\nAll chunks complete!")
            break

        # Submit next chunk
        print(f"\nSubmitting chunk {submitted}...")
        chunk_info = submit_chunk(client, chunks[submitted], submitted)
        chunk_info["request_counts"] = {"completed": 0, "failed": 0, "total": len(chunks[submitted])}
        state["chunks"].append(chunk_info)
        save_state(state)
        print_status(state, n_chunks, len(valid_reqs))

        if not args.run:
            print("\nRe-run with --submit when this chunk completes.")
            break


if __name__ == "__main__":
    main()
