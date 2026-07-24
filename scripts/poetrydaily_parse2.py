"""
poetrydaily_parse2.py — Adds poem_text_html to Poetry Daily records.

poem_text is produced by the original poetrydaily_parse.py logic (imported).
poem_text_html adds:
  • <em>/<i> preserved and normalized to <em>
  • Handles both excerpt_line span format (~85% of records) and fallback format
  • Indentation from &nbsp; runs already preserved by existing span extraction;
    poem_text_html follows the same convention.

Output: scripts/poetrydaily_parsed2.json
"""

import html as html_lib
import json
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS))
import poetrydaily_parse as _pd

INPUT  = SCRIPTS / 'poetrydaily_raw.json'
OUTPUT = SCRIPTS / 'poetrydaily_parsed2.json'

_STRIP_NOT_EM = re.compile(r'<(?!/?em\b)[^>]+>', re.IGNORECASE)


def _normalize_em(html_fragment: str) -> str:
    html_fragment = re.sub(r'<i\b[^>]*>', '<em>', html_fragment, flags=re.IGNORECASE)
    html_fragment = re.sub(r'</i>', '</em>', html_fragment, flags=re.IGNORECASE)
    return _STRIP_NOT_EM.sub('', html_fragment)


# ── HTML-preserving poem body converters ──────────────────────────────────────

def _span_to_html(span: str) -> str:
    """Like the span processing in extract_poem_text but preserves <em>/<i>."""
    # Replace &nbsp; / &#160; / literal nbsp with space (indentation preserved as spaces)
    line = re.sub(r'&nbsp;|&#160;|\xa0', ' ', span)
    # Normalize <i> to <em>
    line = re.sub(r'<i\b[^>]*>', '<em>', line, flags=re.IGNORECASE)
    line = re.sub(r'</i>', '</em>', line, flags=re.IGNORECASE)
    # Strip other tags
    line = _STRIP_NOT_EM.sub('', line)
    line = html_lib.unescape(line)
    return line.rstrip()


def _fallback_html(raw_html: str) -> str:
    """Like poetrydaily_parse.fallback_text_from_html but preserves <em>/<i>."""
    text = raw_html
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'</p>', '\n\n', text)
    text = re.sub(r'<p[^>]*>', '', text)
    # Normalize <i> to <em>
    text = re.sub(r'<i\b[^>]*>', '<em>', text, flags=re.IGNORECASE)
    text = re.sub(r'</i>', '</em>', text, flags=re.IGNORECASE)
    # Strip other tags
    text = _STRIP_NOT_EM.sub('', text)
    # Strip unclosed partial tag at end
    text = re.sub(r'<[^>]*$', '', text)
    text = html_lib.unescape(text)
    text = re.sub(r'&nbsp;|&#160;|\xa0', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _nested_elementor_html(html: str, poem_idx: int) -> str:
    """Like _pd._extract_nested_elementor but preserves <em>/<i>."""
    window = html[poem_idx: poem_idx + 40_000]
    parts = []
    for m in re.finditer(r'data-widget_type="text-editor\.default"', window):
        block = window[m.start(): m.start() + 8000]
        inner = re.search(
            r'elementor-widget-container">(.*?)</div>\s*</div>', block, re.DOTALL
        )
        if not inner:
            continue
        content = inner.group(1)
        stripped = re.sub(r'<[^>]+>', '', content).strip()
        if not stripped or len(stripped) < 10:
            continue
        if any(sig in stripped for sig in _pd._EDITORIAL_SIGNALS):
            continue
        text = _fallback_html(content)
        if text:
            parts.append(text)
    return '\n\n'.join(parts) if parts else ''


def get_poem_text_html(html: str, orig_poem_text: str | None) -> str | None:
    """Return poem_text_html for one PD record."""
    poem_idx = html.find('id="daily-poem"')
    if poem_idx < 0:
        return orig_poem_text

    # Nested Elementor
    if 'data-elementor-type="wp-post"' in html[poem_idx: poem_idx + 500]:
        result = _nested_elementor_html(html, poem_idx)
        return result if result else orig_poem_text

    widget_end = html.find('data-widget_type=', poem_idx + 100)
    block = html[poem_idx: widget_end if widget_end > 0 else poem_idx + 20000]

    inner_m = re.search(r'elementor-widget-container">(.*)', block, re.DOTALL)
    if not inner_m:
        return orig_poem_text
    inner = inner_m.group(1)

    # Strip editorial footnotes (same as original)
    inner = re.sub(
        r'<p[^>]*>[^<]*(?:<br\s*/?>)?[^<]*<small>.*?</small>[^<]*</p>',
        '', inner, flags=re.DOTALL
    )
    inner = re.sub(r'<small>.*?</small>', '', inner, flags=re.DOTALL)

    # --- Span format (primary) ---
    spans = re.findall(r'<span class = "excerpt_line">(.*?)</span>', inner, re.DOTALL)
    if spans:
        lines = [_span_to_html(sp) for sp in spans]
        while lines and not lines[-1].strip():
            lines.pop()
        return '\n'.join(lines)

    # --- Fallback ---
    if '<table' in inner:
        return orig_poem_text

    result = _fallback_html(inner)
    return result if result else orig_poem_text


def main():
    print(f'Reading {INPUT} …')
    with open(INPUT, encoding='utf-8') as f:
        raw = json.load(f)
    print(f'  {len(raw)} records.')

    poems = []
    drops_count = 0

    for i, rec in enumerate(raw):
        if i % 200 == 0:
            print(f'  Processing {i+1}/{len(raw)} …', end='\r', flush=True)
        try:
            result = _pd.parse_record(rec)
            if result is not None:
                result['poem_text_html'] = get_poem_text_html(
                    rec['html'], result.get('poem_text')
                )
                poems.append(result)
        except _pd.ParseDrop:
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

        poem_idx = html.find('id="daily-poem"')
        if poem_idx < 0:
            continue

        # Check span format
        widget_end = html.find('data-widget_type=', poem_idx + 100)
        block = html[poem_idx: widget_end if widget_end > 0 else poem_idx + 20000]
        inner_m = re.search(r'elementor-widget-container">(.*)', block, re.DOTALL)
        if not inner_m:
            continue
        inner = inner_m.group(1)

        # Strip <small> blocks before checking — the parser strips these too,
        # so em/i inside them are not false misses.
        inner = re.sub(r'<small>.*?</small>', '', inner, flags=re.DOTALL)

        spans = re.findall(r'<span class = "excerpt_line">(.*?)</span>', inner, re.DOTALL)
        if spans:
            body = ''.join(spans)
        else:
            body = inner

        if re.search(r'<(?:em|i)\b', body, re.IGNORECASE) and '<em>' not in (res.get('poem_text_html') or ''):
            misses += 1

    print(f'\nMissed-emphasis check:      {misses} records with em/i in body but no <em> in poem_text_html')


if __name__ == '__main__':
    main()
