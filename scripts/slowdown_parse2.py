"""
slowdown_parse2.py — Adds poem_text_html to Slowdown records.

poem_text is produced by the original slowdown_parse.py logic (imported).
poem_text_html adds:
  • <em> preserved from <pre class="verse"> blocks (Format B, 574 records)
  • <em>/<i> preserved in poem paragraphs after title block (Format A)
  • Both normalized to <em>
  • Leading whitespace already preserved in poem_text (rstrip not strip);
    poem_text_html follows the same convention.

Output: scripts/slowdown_parsed2.json
"""

import json
import re
import sys
from html import unescape
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS))
import slowdown_parse as _sd

INPUT  = SCRIPTS / 'slowdown_raw.json'
OUTPUT = SCRIPTS / 'slowdown_parsed2.json'

# Regex to strip all tags except <em> and </em>
_STRIP_NOT_EM = re.compile(r'<(?!/?em\b)[^>]+>', re.IGNORECASE)


def _normalize_em(html: str) -> str:
    """Normalize <i>/<em> to <em>, return fragment with only <em> tags remaining."""
    html = re.sub(r'<i\b[^>]*>', '<em>', html, flags=re.IGNORECASE)
    html = re.sub(r'</i>', '</em>', html, flags=re.IGNORECASE)
    html = _STRIP_NOT_EM.sub('', html)
    return html


def extract_poem_pre_html(body_html: str) -> str:
    """Like _sd.extract_poem_pre but preserves <em>/<i> as <em>."""
    m = re.search(r'<pre class="verse">(.*?)</pre>', body_html, re.DOTALL)
    if not m:
        return ''
    raw = m.group(1)
    raw = re.sub(r'<br\s*/?>', '\n', raw, flags=re.IGNORECASE)
    raw = _normalize_em(raw)
    raw = unescape(raw)
    return _sd.clean_stanza_text(raw)


def extract_poem_paragraphs_html(body_html: str) -> str:
    """Like _sd.extract_poem_paragraphs but preserves <em>/<i> as <em> after the title block."""
    p_blocks = re.findall(r'<p>(.*?)</p>', body_html, re.DOTALL)
    found_title = False
    stanzas = []

    for block in p_blocks:
        text_only = re.sub(r'<[^>]+>', '', block).strip()
        if not text_only or text_only in (' ', '\xa0'):
            continue

        # Strip link elements (transcript PDF links)
        block_clean = re.sub(r'<a\b[^>]*>.*?</a>', '', block, flags=re.DOTALL)

        # Stop at copyright em block
        if block_clean.strip().startswith('<em>') and any(
            kw in block_clean.lower()
            for kw in ('copyright', 'used by', 'used with')
        ):
            break

        # Title/author block detection — same logic as original
        raw_text = _sd.text_of(block_clean)
        is_title_block = (
            '<strong>' in block_clean
            or ('<em>' in block_clean and not any(
                kw in block_clean.lower()
                for kw in ('copyright', 'used by', 'used with')
            ))
            or (not found_title and re.search(r'(?:^|\n)by\s+\S', raw_text, re.IGNORECASE)
                and len(raw_text) < 300)
        )
        if is_title_block and not found_title:
            found_title = True
            continue

        if found_title:
            line_text = re.sub(r'<br\s*/?>', '\n', block_clean, flags=re.IGNORECASE)
            line_text = _normalize_em(line_text)
            line_text = unescape(line_text).strip()
            if line_text:
                stanzas.append(line_text)

    poem = '\n\n'.join(stanzas)
    return _sd.clean_stanza_text(poem)


def get_poem_text_html(record: dict, orig: dict) -> str:
    """Extract poem_text_html for one episode record."""
    if not orig['has_poem']:
        return ''

    html = record['html']
    body_html = _sd.get_body_html(html)
    if not body_html:
        return ''

    has_pre = '<pre class="verse">' in body_html
    has_hr  = '<hr/>' in body_html

    # Replicate poem_section logic from parse_episode
    if has_pre:
        if has_hr:
            hr_pos  = body_html.rfind('<hr/>')
            after_hr = body_html[hr_pos:]
            local_pre = after_hr.find('<pre class="verse">')
            poem_section = after_hr if local_pre >= 0 else body_html
        else:
            poem_section = body_html
    else:
        poem_section = body_html[body_html.rfind('<hr/>'):] if has_hr else body_html

    if has_pre:
        return extract_poem_pre_html(poem_section)
    else:
        return extract_poem_paragraphs_html(poem_section)


def main():
    print(f'Reading {INPUT} …')
    with open(INPUT, encoding='utf-8') as f:
        raw = json.load(f)
    print(f'  {len(raw)} episodes.')

    results = []
    for i, r in enumerate(raw):
        if i % 200 == 0:
            print(f'  Processing {i+1}/{len(raw)} …', end='\r', flush=True)
        orig = _sd.parse_episode(r)
        orig['poem_text_html'] = get_poem_text_html(r, orig)
        results.append(orig)
    print(f'\n  Done.')

    # Only poem records (matching original output behaviour)
    poems = [r for r in results if r['has_poem']]

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(poems, f, ensure_ascii=False, indent=2)
    print(f'Wrote {OUTPUT}')

    # ── Stats ─────────────────────────────────────────────────────────────────
    gained_em     = [r for r in poems if '<em>' in (r['poem_text_html'] or '')]
    gained_indent = [
        r for r in poems
        if any(
            l.startswith(' ')
            for l in (r['poem_text_html'] or '').split('\n')
        )
    ]
    # Indentation that's NEW (not already in poem_text) — for Slowdown pre blocks,
    # poem_text already has indentation. Report how many have it in poem_text_html.
    new_indent = [
        r for r in poems
        if any(
            hl.startswith(' ') and not pl.startswith(' ')
            for pl, hl in zip(
                (r['poem_text'] or '').split('\n'),
                (r['poem_text_html'] or '').split('\n'),
            )
        )
    ]

    print(f'\nTotal poem records:         {len(poems)}')
    print(f'Gained <em> emphasis:       {len(gained_em)}')
    print(f'With indentation in html:   {len(gained_indent)}')
    print(f'  (indentation also in poem_text for pre-format; new_indent above '
          f'counts lines where html gained leading space poem_text lacked: {len(new_indent)})')

    # ── Missed-emphasis check ──────────────────────────────────────────────────
    # Build map from source_url to result
    result_map = {r['source_url']: r for r in poems}

    misses = 0
    for r in raw:
        url      = r['url']
        html     = r['html']
        body_html = _sd.get_body_html(html)
        if not body_html:
            continue
        res = result_map.get(url)
        if not res:
            continue

        has_pre = '<pre class="verse">' in body_html
        has_hr  = '<hr/>' in body_html

        if has_pre:
            if has_hr:
                hr_pos = body_html.rfind('<hr/>')
                after_hr = body_html[hr_pos:]
                local_pre = after_hr.find('<pre class="verse">')
                poem_section = after_hr if local_pre >= 0 else body_html
            else:
                poem_section = body_html
            pre_m = re.search(r'<pre class="verse">(.*?)</pre>', poem_section, re.DOTALL)
            body = pre_m.group(1) if pre_m else ''
        else:
            poem_section = body_html[body_html.rfind('<hr/>'):] if has_hr else body_html
            # Format A: collect blocks after title
            p_blocks = re.findall(r'<p>(.*?)</p>', poem_section, re.DOTALL)
            found_title = False
            body_parts = []
            for block in p_blocks:
                block_clean = re.sub(r'<a\b[^>]*>.*?</a>', '', block, flags=re.DOTALL)
                raw_text = _sd.text_of(block_clean)
                has_markup = '<strong>' in block_clean or '<em>' in block_clean
                if has_markup and not found_title:
                    found_title = True
                    continue
                if found_title:
                    # Same copyright stop as extract_poem_paragraphs
                    if block_clean.strip().startswith('<em>') and any(
                        kw in block_clean.lower()
                        for kw in ('copyright', 'used by', 'used with')
                    ):
                        break
                    body_parts.append(block_clean)
            body = '\n'.join(body_parts)

        if re.search(r'<(?:em|i)\b', body, re.IGNORECASE) and '<em>' not in (res.get('poem_text_html') or ''):
            misses += 1

    print(f'\nMissed-emphasis check:      {misses} records with em/i in body but no <em> in poem_text_html')


if __name__ == '__main__':
    main()
