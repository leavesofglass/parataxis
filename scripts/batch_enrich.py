#!/usr/bin/env python3
"""
batch_enrich.py — Prepare and launch two OpenAI batch jobs:
  1. Embeddings  : text-embedding-3-small on each poem body
  2. Scoring     : gpt-4.1-nano rubric (5 dims) + 2-sentence summary per poem

Reads : dedup_cleaned.json
Writes: batch_embeddings.jsonl   — uploaded + batch started
        batch_scoring.jsonl      — uploaded + batch started
        batch_ids.json           — {"embeddings": <id>, "scoring": <id>}

Usage:
  OPENAI_API_KEY=sk-... python3 batch_enrich.py
  python3 batch_enrich.py --env app/.env.local

Retrieve results later with:
  python3 batch_retrieve.py
"""

import argparse, json, os, sys, time
from pathlib import Path

SCRIPTS    = Path(__file__).parent
ROOT       = SCRIPTS.parent
IN_PATH    = SCRIPTS / "dedup_cleaned.json"
EMB_JSONL  = SCRIPTS / "batch_embeddings.jsonl"
SCR_JSONL  = SCRIPTS / "batch_scoring.jsonl"
IDS_PATH   = SCRIPTS / "batch_ids.json"

EMBED_MODEL  = "text-embedding-3-small"
SCORE_MODEL  = "gpt-4o-mini"
MAX_TOKENS   = 512   # rubric+summary output is compact

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


def load_env(path: str):
    """Load KEY=value pairs from a .env file into os.environ."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, _, v = line.partition('=')
        os.environ.setdefault(k.strip(), v.strip())


def build_embedding_request(poem_id: str, text: str) -> dict:
    return {
        "custom_id": poem_id,
        "method": "POST",
        "url": "/v1/embeddings",
        "body": {
            "model": EMBED_MODEL,
            "input": text,
            "encoding_format": "float",
        },
    }


def build_scoring_request(poem_id: str, author: str, title: str, text: str) -> dict:
    user_content = f'Author: {author}\nTitle: {title}\n\n{text}'
    return {
        "custom_id": poem_id,
        "method": "POST",
        "url": "/v1/chat/completions",
        "body": {
            "model": SCORE_MODEL,
            "max_tokens": MAX_TOKENS,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": RUBRIC_SYSTEM},
                {"role": "user",   "content": user_content},
            ],
        },
    }


def write_jsonl(path: Path, records: list) -> None:
    lines = [json.dumps(r, ensure_ascii=False) for r in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    size_mb = path.stat().st_size / 1_048_576
    print(f"  Wrote {len(lines)} lines ({size_mb:.1f} MB) → {path.name}")


def upload_and_start(client, jsonl_path: Path, description: str) -> str:
    print(f"  Uploading {jsonl_path.name}...")
    with open(jsonl_path, "rb") as f:
        file_obj = client.files.create(file=f, purpose="batch")
    print(f"    file_id={file_obj.id}")

    batch = client.batches.create(
        input_file_id=file_obj.id,
        endpoint="/v1/chat/completions" if "scoring" in jsonl_path.name else "/v1/embeddings",
        completion_window="24h",
        metadata={"description": description},
    )
    print(f"    batch_id={batch.id}  status={batch.status}")
    return batch.id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="app/.env.local",
                        help="Path to .env file (default: app/.env.local)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Build JSONL files only, don't upload")
    args = parser.parse_args()

    load_env(ROOT / args.env if not Path(args.env).is_absolute() else args.env)

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key and not args.dry_run:
        sys.exit("ERROR: OPENAI_API_KEY not set. Pass --env path/to/.env.local")

    print("Loading cleaned corpus...")
    data = json.loads(IN_PATH.read_text(encoding="utf-8"))
    print(f"  {len(data)} poems")

    emb_requests = []
    scr_requests = []

    for i, rec in enumerate(data):
        poem_id  = f"poem_{i:05d}"
        text     = (rec.get("poem_text") or "").strip()
        author   = rec.get("author", "")
        title    = rec.get("title", "")

        if not text:
            continue

        emb_requests.append(build_embedding_request(poem_id, text))
        scr_requests.append(build_scoring_request(poem_id, author, title, text))

    print(f"  {len(emb_requests)} embedding requests")
    print(f"  {len(scr_requests)} scoring requests")

    print("\nWriting batch JSONL files...")
    write_jsonl(EMB_JSONL, emb_requests)
    write_jsonl(SCR_JSONL, scr_requests)

    if args.dry_run:
        print("\nDry-run: JSONL files written, not uploaded.")
        return

    print("\nUploading and starting batch jobs...")
    import openai
    client = openai.OpenAI(api_key=api_key)

    emb_batch_id = upload_and_start(
        client, EMB_JSONL, "poetry-app: embeddings text-embedding-3-small"
    )
    scr_batch_id = upload_and_start(
        client, SCR_JSONL, f"poetry-app: rubric scoring {SCORE_MODEL}"
    )

    ids = {"embeddings": emb_batch_id, "scoring": scr_batch_id}
    IDS_PATH.write_text(json.dumps(ids, indent=2), encoding="utf-8")
    print(f"\nSaved batch IDs → {IDS_PATH.name}")
    print(json.dumps(ids, indent=2))
    print("\nBatches are running (up to 24h). Run batch_retrieve.py when done.")


if __name__ == "__main__":
    main()
