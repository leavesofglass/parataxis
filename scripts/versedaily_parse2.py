"""
versedaily_parse2.py — Adds poem_text_html to Verse Daily records.

poem_text is produced by the original versedaily_parse.py logic (imported).
poem_text_html adds:
  • <i> (VD's exclusive italic form) preserved and normalized to <em>
  • Indentation from &nbsp; runs already preserved by the existing parser;
    poem_text_html uses the same logic.

Output: scripts/versedaily_parsed2.json
"""

import html as html_lib
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS))
import versedaily_parse as _vd

INPUT  = SCRIPTS / 'versedaily_wayback_raw.json'
OUTPUT = SCRIPTS / 'versedaily_parsed2.json'

_STRIP_NOT_EM = re.compile(r'<(?!/?em\b)[^>]+>', re.IGNORECASE)


def _normalize_em(html_fragment: str) -> str:
    html_fragment = re.sub(r'<i\b[^>]*>', '<em>', html_fragment, flags=re.IGNORECASE)
    html_fragment = re.sub(r'</i>', '</em>', html_fragment, flags=re.IGNORECASE)
    return _STRIP_NOT_EM.sub('', html_fragment)


# ── HTML-preserving poem body converter ───────────────────────────────────────

def _prose_block_html(m: re.Match) -> str:
    """Like versedaily_parse._prose_block but preserves <i> as <em>."""
    content = m.group(1)
    content = re.sub(r'<br\s*/?>', '\n', content)
    content = re.sub(r'<i\b[^>]*>', '<em>', content, flags=re.IGNORECASE)
    content = re.sub(r'</i>', '</em>', content, flags=re.IGNORECASE)
    content = _STRIP_NOT_EM.sub(' ', content)
    content = html_lib.unescape(content).replace('\xa0', ' ')
    return '\n\n' + ' '.join(content.split()) + '\n\n'


def _html_to_poem_text_html(html_fragment: str) -> str:
    """Like versedaily_parse._html_to_poem_text but preserves <i>/<em> as <em>."""
    text = html_fragment

    # 1. Prose poem blocks
    text = re.sub(
        r'<p[^>]*\bjustify\b[^>]*>(.*?)</p>',
        _prose_block_html,
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 2. <br> + &nbsp; indentation → "\n" + spaces (same as original)
    text = re.sub(
        r'<br[ \t]*/?>[ \t]*((?:(?:&nbsp;|&#160;)[ \t]*)*)\n?',
        _vd._br_to_newline,
        text,
    )

    # 3. Stanza breaks
    text = re.sub(r'</p\s*>', '\n\n', text)
    text = re.sub(r'<p[^>]*>', '\n\n', text)

    # 3.5 Remove malformed unclosed tags (no `>` before end of line) so that
    #      _STRIP_NOT_EM can't consume across newlines into legitimate content.
    text = re.sub(r'<(?!/?em\b)[^>\n]*$', '', text, flags=re.MULTILINE | re.IGNORECASE)

    # 4. Normalize <i>/<em> before stripping
    text = re.sub(r'<i\b[^>]*>', '<em>', text, flags=re.IGNORECASE)
    text = re.sub(r'</i>', '</em>', text, flags=re.IGNORECASE)
    text = _STRIP_NOT_EM.sub('', text)

    # 5. Decode entities; non-breaking space → regular space
    text = html_lib.unescape(text)
    text = text.replace('\xa0', ' ')

    # 6. Normalize each line: preserve leading spaces, collapse internal runs
    lines = text.split('\n')
    processed = []
    for line in lines:
        rstripped = line.rstrip()
        if not rstripped.strip():
            processed.append('')
            continue
        leading = len(rstripped) - len(rstripped.lstrip(' '))
        content = ' '.join(rstripped.split())
        processed.append(' ' * leading + content)
    text = '\n'.join(processed)

    # 7. Collapse 3+ blank lines to 1
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip('\n').strip()


def get_poem_text_html(html: str, orig_poem_text: str | None) -> str | None:
    """Return poem_text_html for one VD record."""
    if not orig_poem_text:
        return orig_poem_text  # None or empty string

    bq = _vd._get_blockquote_html(html)
    if not bq:
        return orig_poem_text

    title_end = bq.find('</b>')
    if title_end < 0:
        title_end = bq.find('</i>')
    if title_end < 0:
        return orig_poem_text

    after_title = bq[title_end:]
    cp_pos_in_bq = _vd._find_copyright_pos(bq)
    search_limit = (
        (cp_pos_in_bq - title_end) if cp_pos_in_bq > title_end else len(after_title)
    )

    poem_start_m = None
    for _m in re.finditer(
        r'(?:<p[^>]*>\s*)?<font face="Times New[^"]*"[^>]*>(?:\s*<font[^>]*>)?',
        after_title,
    ):
        if _m.start() >= search_limit:
            break
        if re.match(r'\s*Copyright', after_title[_m.end():]):
            continue
        poem_start_m = _m
        break
    if not poem_start_m:
        poem_start_m = re.search(
            r'<p[^>]*>\s*<br\s*/?>\s*\n\s*\n', after_title[:search_limit]
        )
    if not poem_start_m:
        return orig_poem_text

    poem_html = after_title[poem_start_m.end():]
    cp_pos_in_poem = (
        cp_pos_in_bq - (title_end + poem_start_m.end()) if cp_pos_in_bq >= 0 else -1
    )
    end_markers = [
        p for p in (poem_html.find('<iframe'), cp_pos_in_poem) if p >= 0
    ]
    if end_markers:
        poem_html = poem_html[:min(end_markers)]

    result = _html_to_poem_text_html(poem_html)
    return result if result else orig_poem_text


def main():
    print(f'Reading {INPUT} …')
    with open(INPUT, encoding='utf-8') as f:
        raw = json.load(f)
    print(f'  {len(raw)} records.')

    poems = []
    drops_count = 0

    for i, rec in enumerate(raw):
        if i % 500 == 0:
            print(f'  Processing {i+1}/{len(raw)} …', end='\r', flush=True)
        try:
            result = _vd.parse_record(rec)
            result['poem_text_html'] = get_poem_text_html(
                rec['html'], result.get('poem_text')
            )
            poems.append(result)
        except _vd.ParseDrop:
            drops_count += 1

    print(f'\n  Done. {len(poems)} kept, {drops_count} dropped.')

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(poems, f, ensure_ascii=False, indent=2)
    print(f'Wrote {OUTPUT}')

    # ── Stats ─────────────────────────────────────────────────────────────────
    poem_recs = [r for r in poems if r.get('has_poem')]
    gained_em = [r for r in poem_recs if '<em>' in (r['poem_text_html'] or '')]
    gained_indent = [
        r for r in poem_recs
        if any(l.startswith(' ') for l in (r['poem_text_html'] or '').split('\n'))
    ]

    print(f'\nTotal records:              {len(poems)}')
    print(f'has_poem=True:              {len(poem_recs)}')
    print(f'Gained <em> emphasis:       {len(gained_em)}')
    print(f'With indentation in html:   {len(gained_indent)}')

    # ── Missed-emphasis check ──────────────────────────────────────────────────
    result_map = {r['source_url']: r for r in poems}
    misses = 0

    for rec in raw:
        url  = rec['url']
        html = rec['html']
        res  = result_map.get(url)
        if not res or not res.get('has_poem'):
            continue

        bq = _vd._get_blockquote_html(html)
        if not bq:
            continue

        title_end = bq.find('</b>')
        if title_end < 0:
            title_end = bq.find('</i>')
        if title_end < 0:
            continue

        after_title = bq[title_end:]
        cp_pos_in_bq = _vd._find_copyright_pos(bq)
        search_limit = (
            (cp_pos_in_bq - title_end) if cp_pos_in_bq > title_end else len(after_title)
        )

        # Replicate poem_start_m logic from get_poem_text_html
        poem_start_m = None
        for _m in re.finditer(
            r'(?:<p[^>]*>\s*)?<font face="Times New[^"]*"[^>]*>(?:\s*<font[^>]*>)?',
            after_title,
        ):
            if _m.start() >= search_limit:
                break
            if re.match(r'\s*Copyright', after_title[_m.end():]):
                continue
            poem_start_m = _m
            break
        if not poem_start_m:
            poem_start_m = re.search(
                r'<p[^>]*>\s*<br\s*/?>\s*\n\s*\n', after_title[:search_limit]
            )
        if not poem_start_m:
            continue

        poem_html = after_title[poem_start_m.end():]
        cp_pos_in_poem = (
            cp_pos_in_bq - (title_end + poem_start_m.end()) if cp_pos_in_bq >= 0 else -1
        )
        end_markers = [p for p in (poem_html.find('<iframe'), cp_pos_in_poem) if p >= 0]
        if end_markers:
            poem_html = poem_html[:min(end_markers)]

        if re.search(r'<(?:em|i)\b', poem_html, re.IGNORECASE) and '<em>' not in (res.get('poem_text_html') or ''):
            misses += 1

    print(f'\nMissed-emphasis check:      {misses} records with <i> in body but no <em> in poem_text_html')


if __name__ == '__main__':
    main()
