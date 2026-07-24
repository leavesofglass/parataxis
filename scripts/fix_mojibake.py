"""
fix_mojibake.py — Replace U+00B4 (´) and U+0060 (`) with straight apostrophe (')
in the body_html and title columns of the poems table.

Body is intentionally left untouched.

Usage:
  python scripts/fix_mojibake.py --dry-run   # show affected rows, no writes
  python scripts/fix_mojibake.py --write      # apply fixes
"""

import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent

BAD_CHARS = ['´', '`']   # ´ acute accent, ` grave accent
REPLACEMENT = "'"             # straight apostrophe U+0027

COLUMNS = ['title', 'body_html']

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
    sys.exit('ERROR: SUPABASE_URL not found.')
if not SUPABASE_KEY:
    sys.exit('ERROR: SUPABASE_SERVICE_ROLE_KEY not found.')

try:
    from supabase import create_client
except ImportError:
    sys.exit('supabase package not found — run: pip install supabase')


# ── Helpers ──────────────────────────────────────────────────────────────────

def needs_fix(value: str | None) -> bool:
    if not value:
        return False
    return any(c in value for c in BAD_CHARS)


def fix(value: str | None) -> str | None:
    if not value:
        return value
    for c in BAD_CHARS:
        value = value.replace(c, REPLACEMENT)
    return value


def excerpt(text: str, bad_char: str, context: int = 30) -> str:
    """Return a short excerpt centred on the first occurrence of bad_char."""
    idx = text.find(bad_char)
    if idx < 0:
        return ''
    start = max(0, idx - context)
    end   = min(len(text), idx + context + 1)
    snippet = text[start:end]
    if start > 0:
        snippet = '…' + snippet
    if end < len(text):
        snippet = snippet + '…'
    return repr(snippet)


def fetch_all(client) -> list[dict]:
    """Paginate through all poems, fetching only id, title, body_html."""
    rows = []
    page = 0
    while True:
        batch = (
            client.table('poems')
            .select('id, title, body_html')
            .range(page * 1000, page * 1000 + 999)
            .execute()
        )
        rows.extend(batch.data)
        if len(batch.data) < 1000:
            break
        page += 1
    return rows


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    dry_run    = '--dry-run' in args
    write_mode = '--write'   in args

    if not dry_run and not write_mode:
        sys.exit('Specify --dry-run or --write')

    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    print('Fetching poems (id, title, body_html) …', flush=True)
    rows = fetch_all(client)
    print(f'  {len(rows):,} rows fetched.\n')

    # Collect all needed updates
    updates: list[dict] = []   # {'id', 'col', 'before', 'after'}

    for row in rows:
        poem_id = row['id']
        for col in COLUMNS:
            val = row.get(col)
            if needs_fix(val):
                updates.append({
                    'id':     poem_id,
                    'col':    col,
                    'before': val,
                    'after':  fix(val),
                })

    if not updates:
        print('No affected rows found.')
        return

    # Group by poem_id for cleaner display
    by_poem: dict[str, list[dict]] = {}
    for u in updates:
        by_poem.setdefault(u['id'], []).append(u)

    print(f'Affected poems: {len(by_poem)}  |  Affected column×row pairs: {len(updates)}\n')

    for poem_id, cols in by_poem.items():
        print(f'── {poem_id} ──')
        for u in cols:
            col    = u['col']
            before = u['before']
            after  = u['after']
            # Show one excerpt per bad character type found
            for bad_char in BAD_CHARS:
                if bad_char not in before:
                    continue
                count = before.count(bad_char)
                char_name = 'U+00B4 ´' if bad_char == '´' else 'U+0060 `'
                print(f'  [{col}]  {char_name}  ×{count}')
                print(f'    BEFORE: {excerpt(before, bad_char)}')
                fixed_excerpt = excerpt(before, bad_char, context=30)
                # Show after by replacing just around the bad char
                after_ex = excerpt(after, REPLACEMENT, context=30) if REPLACEMENT in after else repr(after[:60])
                print(f'    AFTER:  {after_ex}')
        print()

    if dry_run:
        print(f'Dry run complete — {len(updates)} updates pending, nothing written.')
        return

    # ── Write ────────────────────────────────────────────────────────────────
    print(f'Writing {len(updates)} updates …')
    written = 0
    errors  = []

    for u in updates:
        try:
            client.table('poems').update({u['col']: u['after']}).eq('id', u['id']).execute()
            written += 1
        except Exception as exc:
            errors.append((u['id'], u['col'], str(exc)))

    print(f'Done. {written} updates applied.')
    if errors:
        print(f'{len(errors)} errors:')
        for poem_id, col, msg in errors:
            print(f'  {poem_id} [{col}]: {msg}')


if __name__ == '__main__':
    main()
