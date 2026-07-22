#!/usr/bin/env python3
"""
batch_retrieve.py — Check batch status and, when complete, merge results
back into dedup_cleaned.json → dedup_enriched.json.

Usage:
  python3 batch_retrieve.py [--env app/.env.local] [--status-only]

Output (when both batches complete):
  dedup_enriched.json  — cleaned corpus + embedding + rubric + summary fields
"""

import argparse, json, os, sys
from pathlib import Path

SCRIPTS      = Path(__file__).parent
ROOT         = SCRIPTS.parent
CLEANED_PATH = SCRIPTS / "dedup_cleaned.json"
IDS_PATH     = SCRIPTS / "batch_ids.json"
OUT_PATH     = SCRIPTS / "dedup_enriched.json"


def load_env(path):
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, _, v = line.partition('=')
        os.environ.setdefault(k.strip(), v.strip())


def download_results(client, batch_id: str) -> list[dict]:
    batch = client.batches.retrieve(batch_id)
    if batch.status != "completed":
        print(f"  Batch {batch_id} status: {batch.status} — not ready")
        return []
    content = client.files.content(batch.output_file_id)
    lines = content.text.strip().splitlines()
    return [json.loads(l) for l in lines if l.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env",         default="app/.env.local")
    parser.add_argument("--status-only", action="store_true",
                        help="Just show batch status, don't download")
    args = parser.parse_args()

    load_env(ROOT / args.env if not Path(args.env).is_absolute() else args.env)
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        sys.exit("ERROR: OPENAI_API_KEY not set")

    if not IDS_PATH.exists():
        sys.exit(f"ERROR: {IDS_PATH} not found — run batch_enrich.py first")

    import openai
    client = openai.OpenAI(api_key=api_key)

    ids = json.loads(IDS_PATH.read_text())
    emb_id = ids["embeddings"]
    scr_id = ids["scoring"]

    emb_batch = client.batches.retrieve(emb_id)
    scr_batch = client.batches.retrieve(scr_id)

    print("Batch status:")
    print(f"  embeddings  {emb_id}: {emb_batch.status}")
    print(f"  scoring     {scr_id}: {scr_batch.status}")

    if args.status_only:
        return

    if emb_batch.status != "completed" or scr_batch.status != "completed":
        print("\nNot ready yet — re-run when both show 'completed'.")
        return

    print("\nDownloading results...")
    emb_results = download_results(client, emb_id)
    scr_results = download_results(client, scr_id)
    print(f"  {len(emb_results)} embedding results")
    print(f"  {len(scr_results)} scoring results")

    # Index by custom_id
    emb_by_id = {r["custom_id"]: r for r in emb_results}
    scr_by_id = {r["custom_id"]: r for r in scr_results}

    data = json.loads(CLEANED_PATH.read_text(encoding="utf-8"))

    skipped_emb = 0
    skipped_scr = 0
    enriched = []

    for i, rec in enumerate(data):
        poem_id = f"poem_{i:05d}"
        new_rec = dict(rec)

        # Embedding
        emb_res = emb_by_id.get(poem_id)
        if emb_res and emb_res.get("response", {}).get("status_code") == 200:
            new_rec["embedding"] = emb_res["response"]["body"]["data"][0]["embedding"]
        else:
            new_rec["embedding"] = None
            skipped_emb += 1

        # Rubric + summary
        scr_res = scr_by_id.get(poem_id)
        if scr_res and scr_res.get("response", {}).get("status_code") == 200:
            content = scr_res["response"]["body"]["choices"][0]["message"]["content"]
            try:
                rubric = json.loads(content)
                new_rec["rubric"] = {
                    "mood":                rubric.get("mood"),
                    "emotional_intensity": rubric.get("emotional_intensity"),
                    "imagery":             rubric.get("imagery"),
                    "accessibility":       rubric.get("accessibility"),
                    "formality":           rubric.get("formality"),
                }
                new_rec["summary"] = rubric.get("summary", "")
            except json.JSONDecodeError:
                new_rec["rubric"]  = None
                new_rec["summary"] = None
                skipped_scr += 1
        else:
            new_rec["rubric"]  = None
            new_rec["summary"] = None
            skipped_scr += 1

        enriched.append(new_rec)

    OUT_PATH.write_text(
        json.dumps(enriched, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"\nWrote {len(enriched)} enriched records → {OUT_PATH}")
    if skipped_emb:
        print(f"  WARNING: {skipped_emb} missing embeddings (embedding=null)")
    if skipped_scr:
        print(f"  WARNING: {skipped_scr} missing rubric scores (rubric=null)")


if __name__ == "__main__":
    main()
