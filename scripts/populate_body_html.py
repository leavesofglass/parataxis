"""
populate_body_html.py — Populate the body_html column in the poems table.

Matches each *_parsed2.json record to its live DB row by exact (author, body)
pair. Writes body_html only where it differs from body. Reports any record that
matches zero rows (unmatched) or more than one row (ambiguous) rather than
guessing.

Usage:
  python scripts/populate_body_html.py --dry-run   # match + report, no writes
  python scripts/populate_body_html.py --write      # actually update Supabase

Reads SUPABASE credentials from app/.env.local (same as other scripts).
"""

import json
import os
import sys
from collections import defaultdict
from pathlib import Path

SCRIPTS = Path(__file__).parent

# ── Sources ──────────────────────────────────────────────────────────────────

SOURCES = [
    {
        'label':    'ralp',
        'file':     SCRIPTS / 'ralp_parsed2.json',
        'has_poem': lambda r: r.get('flags', {}).get('has_poem', False),
    },
    {
        'label':    'slowdown',
        'file':     SCRIPTS / 'slowdown_parsed2.json',
        'has_poem': lambda r: r.get('has_poem', False),
    },
    {
        'label':    'versedaily',
        'file':     SCRIPTS / 'versedaily_parsed2.json',
        'has_poem': lambda r: r.get('has_poem', False),
    },
    {
        'label':    'poetrydaily',
        'file':     SCRIPTS / 'poetrydaily_parsed2.json',
        'has_poem': lambda r: r.get('has_poem', False),
    },
]

BATCH_SIZE = 100

# ── Env ──────────────────────────────────────────────────────────────────────

def _load_env() -> dict[str, str]:
    env_path = SCRIPTS.parent / 'app' / '.env.local'
    values: dict[str, str] = {}
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    values[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return values

_env = _load_env()

def _get(env_key: str, file_key: str | None = None) -> str:
    return (
        os.environ.get(env_key, '').strip()
        or _env.get(file_key or env_key, '').strip()
    )

SUPABASE_URL = _get('SUPABASE_URL', 'NEXT_PUBLIC_SUPABASE_URL')
SUPABASE_KEY = _get('SUPABASE_SERVICE_ROLE_KEY')

if not SUPABASE_URL:
    sys.exit('ERROR: SUPABASE_URL not found. Add NEXT_PUBLIC_SUPABASE_URL to app/.env.local')
if not SUPABASE_KEY:
    sys.exit('ERROR: SUPABASE_SERVICE_ROLE_KEY not found. Add it to app/.env.local')

try:
    from supabase import create_client
except ImportError:
    sys.exit('supabase package not found — run: pip install supabase')


# ── DB fetch ─────────────────────────────────────────────────────────────────

def fetch_all_poems(client) -> list[dict]:
    """Fetch id, author, body for every poem, paginating as needed."""
    rows = []
    page = 0
    while True:
        batch = (
            client.table('poems')
            .select('id,author,body')
            .range(page * 1000, page * 1000 + 999)
            .execute()
        )
        rows.extend(batch.data)
        if len(batch.data) < 1000:
            break
        page += 1
    return rows


# ── Matching ─────────────────────────────────────────────────────────────────

def _norm_author(name: str | None) -> str:
    """Collapse internal whitespace runs to a single space and strip ends."""
    return ' '.join((name or '').split())


def build_index(db_rows: list[dict]) -> dict[tuple[str, str], list[str]]:
    """(normalized_author, body) → list of poem_ids.

    Author names in the parsed files sometimes have extra internal spaces
    (e.g. 'Bret  Yamanaka') that the DB normalized on ingest, so we
    normalize both sides before keying.
    """
    index: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in db_rows:
        key = (_norm_author(row['author']), row['body'])
        index[key].append(row['id'])
    return index


def load_candidates(source: dict) -> list[dict]:
    """Return records that have a poem and a body_html that differs from body."""
    with open(source['file'], encoding='utf-8') as f:
        recs = json.load(f)
    out = []
    for r in recs:
        if not source['has_poem'](r):
            continue
        body      = r.get('poem_text') or ''
        body_html = r.get('poem_text_html') or ''
        if not body_html or body_html == body:
            continue
        out.append({
            'author':    _norm_author(r.get('poet_name', '')),
            'body':      body,
            'body_html': body_html,
            'title':     r.get('poem_title', ''),
            'source':    source['label'],
        })
    return out


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    dry_run   = '--dry-run' in args
    write_mode = '--write' in args

    if not dry_run and not write_mode:
        sys.exit('Specify --dry-run or --write')

    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    print('Fetching all poems from Supabase …', flush=True)
    db_rows = fetch_all_poems(client)
    print(f'  {len(db_rows):,} rows fetched.')
    index = build_index(db_rows)

    # poem_id → {'body_html': str, 'sources': list[str]}
    # Conflict if two sources produce different body_html for the same poem_id.
    updates: dict[str, dict] = {}
    conflicts: list[dict]    = []

    totals = {
        'matched':    0,
        'unmatched':  0,
        'ambiguous':  0,
        'would_update': 0,
    }

    print()
    for source in SOURCES:
        candidates = load_candidates(source)
        label = source['label']

        matched   = 0
        unmatched = []
        ambiguous = []
        source_update_ids: set[str] = set()

        for c in candidates:
            key = (c['author'], c['body'])
            matches = index.get(key, [])

            if len(matches) == 0:
                unmatched.append(c)
            elif len(matches) > 1:
                ambiguous.append({'candidate': c, 'ids': matches})
            else:
                poem_id = matches[0]
                matched += 1
                if poem_id in updates:
                    existing = updates[poem_id]
                    if existing['body_html'] != c['body_html']:
                        # Truly different markup for the same DB row (e.g. same
                        # poem scraped from two sources with different em spans).
                        conflicts.append({
                            'poem_id':   poem_id,
                            'source_a':  existing['sources'],
                            'html_a':    existing['body_html'][:120],
                            'source_b':  label,
                            'html_b':    c['body_html'][:120],
                            'author':    c['author'],
                            'title':     c['title'],
                        })
                    else:
                        # Identical markup from multiple records — deduplicated, no conflict.
                        updates[poem_id]['sources'].append(label)
                else:
                    updates[poem_id] = {'body_html': c['body_html'], 'sources': [label]}
                source_update_ids.add(poem_id)

        totals['matched']      += matched
        totals['unmatched']    += len(unmatched)
        totals['ambiguous']    += len(ambiguous)
        totals['would_update'] += len(source_update_ids)

        print(f'── {label.upper()} ──')
        print(f'  Candidates (poem_text_html ≠ poem_text): {len(candidates):>5}')
        print(f'  Matched:                                  {matched:>5}')
        print(f'  Unmatched (0 DB rows):                    {len(unmatched):>5}')
        print(f'  Ambiguous (>1 DB rows):                   {len(ambiguous):>5}')

        if unmatched:
            print(f'  Unmatched detail (first 5):')
            for u in unmatched[:5]:
                print(f'    author={u["author"]!r}  title={u["title"]!r}')
        if ambiguous:
            print(f'  Ambiguous detail (first 5):')
            for a in ambiguous[:5]:
                ids = ', '.join(a['ids'])
                print(f'    author={a["candidate"]["author"]!r}  title={a["candidate"]["title"]!r}  → {ids}')
        print()

    # Cross-source conflicts
    if conflicts:
        print(f'── CROSS-SOURCE CONFLICTS ({len(conflicts)}) ──')
        print('  Same poem_id matched from two sources with DIFFERENT body_html.')
        print('  The first match wins in the update map; these will NOT be written.')
        for c in conflicts[:10]:
            print(f'  poem_id={c["poem_id"]}  {c["author"]!r}  {c["title"]!r}')
            print(f'    source_a={c["source_a"]}  html_a={c["html_a"]!r}')
            print(f'    source_b={c["source_b"]}  html_b={c["html_b"]!r}')
        print()

    # De-conflict: remove conflicted poem_ids from updates
    conflict_ids = {c['poem_id'] for c in conflicts}
    clean_updates = {pid: v for pid, v in updates.items() if pid not in conflict_ids}

    print('═' * 60)
    print(f'  Total candidates across all sources: {totals["matched"] + totals["unmatched"] + totals["ambiguous"]:>6}')
    print(f'  Matched:                             {totals["matched"]:>6}')
    print(f'  Unmatched:                           {totals["unmatched"]:>6}')
    print(f'  Ambiguous:                           {totals["ambiguous"]:>6}')
    print(f'  Cross-source conflicts (skipped):    {len(conflicts):>6}')
    print(f'  Unique poem_ids to update:           {len(clean_updates):>6}')
    print('═' * 60)

    if dry_run:
        print('\nDry run complete — no writes made.')
        return

    # ── Write ────────────────────────────────────────────────────────────────
    print(f'\nWriting {len(clean_updates):,} updates …')
    update_items = list(clean_updates.items())
    written = 0
    errors  = []

    for batch_start in range(0, len(update_items), BATCH_SIZE):
        batch = update_items[batch_start: batch_start + BATCH_SIZE]
        for poem_id, v in batch:
            try:
                client.table('poems').update({'body_html': v['body_html']}).eq('id', poem_id).execute()
                written += 1
            except Exception as exc:
                errors.append((poem_id, str(exc)))
        if (batch_start + len(batch)) % 500 == 0 or batch_start + len(batch) == len(update_items):
            print(f'  {written}/{len(update_items)} written …', end='\r', flush=True)

    print()
    print(f'\nDone. {written:,} rows updated.')
    if errors:
        print(f'{len(errors)} errors:')
        for pid, msg in errors[:10]:
            print(f'  {pid}: {msg}')


if __name__ == '__main__':
    main()
