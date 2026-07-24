"""
fix_mojibake.py — Fix Windows-1252 mojibake in poems table.

The Verse Daily scraper stored raw cp1252 byte values as Unicode codepoints
for the 0x80–0x9F range instead of decoding them first.  Examples:
  U+0092 → ' (right single quotation mark)
  U+0093 → " (left double quotation mark)
  U+0094 → " (right double quotation mark)
  U+0091 → ' (left single quotation mark)
  U+0096 → – (en dash)
  U+0097 → — (em dash)
  U+0085 → … (ellipsis)

Fix: for every character whose codepoint is in 0x80–0x9F, map it through
Python's cp1252 codec.  The five bytes undefined in cp1252 (0x81, 0x8D,
0x8F, 0x90, 0x9D) are left unchanged.

Safety guard for body: skip any row where the fix would alter a character
outside the 0x80–0x9F range (shouldn't happen, but guards against surprises).

Columns: title, body, body_html.

Usage:
  python scripts/fix_mojibake.py --dry-run   # show affected rows, no writes
  python scripts/fix_mojibake.py --write      # apply fixes
"""

import os
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent

# cp1252 → unicode map for the 0x80–0x9F range.
# Bytes 0x81, 0x8D, 0x8F, 0x90, 0x9D are undefined in cp1252 and are omitted.
CP1252_MAP: dict[int, str] = {}
for _b in range(0x80, 0xA0):
    try:
        CP1252_MAP[_b] = bytes([_b]).decode('cp1252')
    except UnicodeDecodeError:
        pass

COLUMNS = ['title', 'body', 'body_html']
EXPECTED_COUNT = 207

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

def has_mojibake(value: str | None) -> bool:
    if not value:
        return False
    return any(0x80 <= ord(ch) <= 0x9F for ch in value)


def fix_cp1252(value: str) -> str:
    out = []
    for ch in value:
        cp = ord(ch)
        if 0x80 <= cp <= 0x9F and cp in CP1252_MAP:
            out.append(CP1252_MAP[cp])
        else:
            out.append(ch)
    return ''.join(out)


def only_mojibake_changed(original: str, fixed: str) -> bool:
    """True iff every position that differs had a codepoint in 0x80–0x9F."""
    if len(original) != len(fixed):
        return False
    for o, f in zip(original, fixed):
        if o != f and not (0x80 <= ord(o) <= 0x9F):
            return False
    return True


def excerpt(before: str, after: str, context: int = 35) -> tuple[str, str]:
    """Return repr-quoted before/after snippets centred on the first difference."""
    for i, (b, a) in enumerate(zip(before, after)):
        if b != a:
            lo = max(0, i - context)
            hi = min(len(before), i + context + 1)
            b_snip = ('…' if lo > 0 else '') + before[lo:hi] + ('…' if hi < len(before) else '')
            a_snip = ('…' if lo > 0 else '') + after[lo:hi]  + ('…' if hi < len(after)  else '')
            return repr(b_snip), repr(a_snip)
    return repr(before[:80]), repr(after[:80])


def fetch_all(client) -> list[dict]:
    rows: list[dict] = []
    page = 0
    while True:
        batch = (
            client.table('poems')
            .select('id, title, body, body_html')
            .range(page * 1000, page * 1000 + 999)
            .execute()
        )
        rows.extend(batch.data)
        if len(batch.data) < 1000:
            break
        page += 1
    return rows


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    dry_run    = '--dry-run' in args
    write_mode = '--write'   in args

    if not dry_run and not write_mode:
        sys.exit('Specify --dry-run or --write')

    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    print('Fetching poems …', flush=True)
    rows = fetch_all(client)
    print(f'  {len(rows):,} rows fetched.\n')

    # Build per-poem update plan.
    # by_poem[poem_id][col] = {'before', 'after', 'skip', 'skip_reason'}
    by_poem: dict[str, dict[str, dict]] = {}

    for row in rows:
        poem_id = row['id']
        col_updates: dict[str, dict] = {}

        for col in COLUMNS:
            val: str | None = row.get(col)
            if not has_mojibake(val):
                continue
            assert val is not None
            fixed = fix_cp1252(val)
            if fixed == val:
                continue

            skip = False
            skip_reason = ''
            if col == 'body' and not only_mojibake_changed(val, fixed):
                skip = True
                skip_reason = 'fix would change non-mojibake chars — skipped'

            col_updates[col] = {
                'before':      val,
                'after':       fixed,
                'skip':        skip,
                'skip_reason': skip_reason,
            }

        if col_updates:
            by_poem[poem_id] = col_updates

    affected = len(by_poem)
    pending  = sum(
        1
        for cols in by_poem.values()
        for u in cols.values()
        if not u['skip']
    )

    # Count check
    check = '✓' if affected == EXPECTED_COUNT else '✗'
    print(f'Affected poems : {affected}  ({check} expected {EXPECTED_COUNT})')
    print(f'Column updates : {pending} (excluding skipped)\n')

    # Show up to 10 examples
    for poem_id, col_updates in list(by_poem.items())[:10]:
        print(f'── {poem_id} ──')
        for col, u in col_updates.items():
            bef_ex, aft_ex = excerpt(u['before'], u['after'])
            status = f'  [SKIP: {u["skip_reason"]}]' if u['skip'] else ''
            print(f'  [{col}]{status}')
            print(f'    BEFORE: {bef_ex}')
            print(f'    AFTER:  {aft_ex}')
        print()

    if affected > 10:
        print(f'  … {affected - 10} more poems not shown …\n')

    if dry_run:
        print(f'Dry run complete — {pending} updates pending, nothing written.')
        return

    # ── Write ────────────────────────────────────────────────────────────────
    print(f'Writing updates for {affected} poems …', flush=True)
    written = 0
    nothing  = 0
    errors: list[tuple[str, str]] = []

    for poem_id, col_updates in by_poem.items():
        payload = {col: u['after'] for col, u in col_updates.items() if not u['skip']}
        if not payload:
            nothing += 1
            continue
        try:
            client.table('poems').update(payload).eq('id', poem_id).execute()
            written += 1
        except Exception as exc:
            errors.append((poem_id, str(exc)))

    print(f'Done. {written} poems updated, {nothing} fully-skipped.')
    if errors:
        print(f'{len(errors)} errors:')
        for pid, msg in errors:
            print(f'  {pid}: {msg}')


if __name__ == '__main__':
    main()
