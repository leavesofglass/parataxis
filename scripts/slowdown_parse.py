"""
Parse a raw Slowdown scrape (slowdown_raw.json) into structured poem records.

Two HTML formats in the wild:
  Format A (eps 1-122, encores, some replays):
    No <pre class="verse">. Poem lives in <p> elements with <br/> line breaks;
    stanza breaks are separate <p> elements.

  Format B (eps 123+):
    Has <pre class="verse"> for the poem body (some early ones still use <br/>
    inside the pre; later ones use literal newlines). In eps 580+, host
    commentary appears before an <hr/> separator.

Host eras (by episode number — determined empirically from HTML intros):
  1-579    → Tracy K. Smith
  580-918  → Ada Limón
  919-1331 → Major Jackson
  1332+    → Maggie Smith
  (ep 1332 appears twice: a June 2025 live event [has_poem=false] and the regular
   Aug 2025 debut; both are correctly handled by episode content, not by number alone)
"""

import json
import re
import random
import sys
from html.parser import HTMLParser


# ---------------------------------------------------------------------------
# HTML utilities
# ---------------------------------------------------------------------------

def extract_section(html: str, marker: str) -> str:
    """Return the substring of html starting at marker up to (but not past)
    the closing tags of the article element."""
    start = html.find(marker)
    if start == -1:
        return ''
    # End at the close of the article container
    end = html.find('</article>', start)
    return html[start:end] if end != -1 else html[start:]


def text_of(fragment: str, br_to_newline: bool = True) -> str:
    """Strip all HTML tags from fragment; replace <br/> with \\n if requested."""
    if br_to_newline:
        fragment = re.sub(r'<br\s*/?>', '\n', fragment, flags=re.IGNORECASE)
    return re.sub(r'<[^>]+>', '', fragment)


def decode_entities(s: str) -> str:
    """Decode common HTML entities (HTMLParser.unescape equivalent)."""
    from html import unescape
    return unescape(s)


def clean_text(s: str) -> str:
    """Normalize whitespace within a string (but preserve intentional newlines)."""
    lines = s.split('\n')
    return '\n'.join(line.strip() for line in lines).strip()


# ---------------------------------------------------------------------------
# Structural extraction helpers
# ---------------------------------------------------------------------------

def get_body_html(html: str) -> str:
    """Return the innerHTML of <div class="userContent content_body">."""
    marker = 'class="userContent content_body">'
    start = html.find(marker)
    if start == -1:
        return ''
    start += len(marker)
    # The closing tag sequence is consistent across all pages
    end = html.find('</div></div></div></article>', start)
    return html[start:end] if end != -1 else ''


def get_published_date(html: str) -> str:
    """Extract published date string from content_date div."""
    m = re.search(r'class="content_date">([^<]+)<', html)
    if m:
        raw = m.group(1).strip()
        # Convert "November 26, 2018" → "2018-11-26"
        from datetime import datetime
        try:
            dt = datetime.strptime(raw, '%B %d, %Y')
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            return raw
    # Fallback: parse from URL YYYY/MM/DD
    m = re.search(r'/episode/(\d{4})/(\d{2})/(\d{2})/', html)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    return ''


def get_episode_number(url: str) -> int | None:
    """Extract episode number from URL slug like /580-walking-the-dogs."""
    m = re.search(r'/(\d+)-', url)
    return int(m.group(1)) if m else None


def get_host(ep_num: int | None) -> str:
    if ep_num is None:
        return 'Unknown'
    if ep_num <= 579:
        return 'Tracy K. Smith'
    if ep_num <= 918:
        return 'Ada Limón'
    if ep_num <= 1331:
        return 'Major Jackson'
    return 'Maggie Smith'


# ---------------------------------------------------------------------------
# Title / author extraction
# ---------------------------------------------------------------------------

def _parse_title_author_from_text(combined: str) -> tuple[str, str]:
    """
    Given a text string that combines title and 'by AUTHOR' (possibly on the
    same or adjacent lines), return (title, author).

    Uses last-occurrence of a line starting with 'by ' to avoid mismatching
    poem titles that themselves begin with 'By' (e.g. 'By Then').
    """
    lines = [l.strip() for l in combined.split('\n') if l.strip()]
    by_idx = -1
    for i, line in enumerate(lines):
        if re.match(r'^by\s+\S', line, re.IGNORECASE):
            by_idx = i  # keep updating → last occurrence wins

    if by_idx == -1:
        return combined.strip(), ''

    author = re.sub(r'^by\s+', '', lines[by_idx], flags=re.IGNORECASE).strip()
    title = '\n'.join(lines[:by_idx]).strip()
    return title, author


def extract_title_author(section_html: str) -> tuple[str, str]:
    """
    Find the poem title and poet name from section_html.

    Pass 1: look for <strong> or <em> elements (common in most eras).
    Pass 2 (fallback): scan plain <p> blocks for 'TITLE\\nby AUTHOR' text.

    Handles:
      - <p><strong>TITLE</strong><strong><br/></strong><strong>by AUTHOR</strong></p>
      - <p><strong>TITLE<br/>by AUTHOR</strong></p>
      - Split across two <p> blocks
      - <p>TITLE<br/>by AUTHOR</p>  (no bold — some Ada Limón / Major era eps)
      - <p><em>TITLE</em><em><br/></em><em>by AUTHOR</em></p>
      - Titles that begin with 'By ...' (last-occurrence attribution detection)
    """
    p_blocks = re.findall(r'<p>(.*?)</p>', section_html, re.DOTALL)

    title = ''
    author = ''

    # --- Pass 1: <strong> or <em> elements ---
    for block in p_blocks:
        clean = re.sub(r'<a\b[^>]*>.*?</a>', '', block, flags=re.DOTALL)

        has_strong = '<strong>' in clean
        has_em = '<em>' in clean
        if not has_strong and not has_em:
            continue

        stripped_text = re.sub(r'<[^>]+>', '', clean).strip()
        if not stripped_text:
            continue

        # Skip copyright/source lines (em-only blocks with attribution keywords)
        if not has_strong and has_em:
            lower = stripped_text.lower()
            if any(kw in lower for kw in ('copyright', 'used by', 'used with', 'permission of')):
                continue

        # Prefer <strong>; fall back to <em> if no <strong> in block
        if has_strong:
            tags = re.findall(r'<strong>(.*?)</strong>', clean, re.DOTALL)
        else:
            tags = re.findall(r'<em>(.*?)</em>', clean, re.DOTALL)

        combined = '\n'.join(text_of(s) for s in tags)
        combined = decode_entities(combined).strip()
        if not combined:
            continue

        t, a = _parse_title_author_from_text(combined)
        if a:
            if t:
                title = t
            author = a
            break
        elif t and not title and has_strong:
            # Only use <strong> blocks as title-without-author candidates.
            # <em>-only blocks without a "by" attribution are typically editorial
            # notes or prose intros, not poem titles.
            title = t  # look ahead for "by AUTHOR" in the next block

    if title and author:
        return title, author

    # --- Pass 2: plain <p> text fallback (no bold/italic markup) ---
    for block in p_blocks:
        clean = re.sub(r'<a\b[^>]*>.*?</a>', '', block, flags=re.DOTALL)
        # Skip blocks that already have bold/italic (handled in pass 1)
        if '<strong>' in clean or '<em>' in clean:
            continue
        raw_text = text_of(clean)
        raw_text = decode_entities(raw_text).strip()
        if not raw_text or len(raw_text) > 300:
            continue  # skip long prose blocks

        t, a = _parse_title_author_from_text(raw_text)
        if a and t:
            if not title:
                title = t
            if not author:
                author = a
            break
        elif a and title:
            author = a
            break

    return title, author


# ---------------------------------------------------------------------------
# Poem text extraction
# ---------------------------------------------------------------------------

def extract_poem_pre(body_html: str) -> str:
    """Extract poem from <pre class="verse">...</pre>."""
    m = re.search(r'<pre class="verse">(.*?)</pre>', body_html, re.DOTALL)
    if not m:
        return ''
    raw = m.group(1)
    # Handle <br/> inside pre (early format) AND literal newlines (later format)
    raw = re.sub(r'<br\s*/?>', '\n', raw, flags=re.IGNORECASE)
    # Strip remaining tags (e.g. <a>, <em> for emphasized words)
    raw = re.sub(r'<[^>]+>', '', raw)
    raw = decode_entities(raw)
    return clean_stanza_text(raw)


def extract_poem_paragraphs(body_html: str, title_end_hint: str = '') -> str:
    """
    Extract poem from <p> sequences in Format A (no <pre class="verse">).

    Strategy:
    - Split on </p> boundaries.
    - Skip the title/author block, transcript links, and empty/whitespace-only paras.
    - Collect poem paragraphs until we hit a copyright <em> line or run out.
    - Within each paragraph, <br/> → \\n.
    - Between paragraphs → \\n\\n (stanza break).
    """
    # Split body into <p>...</p> chunks
    p_blocks = re.findall(r'<p>(.*?)</p>', body_html, re.DOTALL)

    found_title = False
    stanzas = []

    for block in p_blocks:
        text_only = re.sub(r'<[^>]+>', '', block).strip()

        # Skip empty blocks
        if not text_only or text_only in (' ', '\xa0'):
            if found_title and stanzas:
                # Could be a stanza separator — we handle via paragraph boundaries
                pass
            continue

        # Strip <a> link elements (transcript PDF links) from the block.
        # Same fix as in extract_title_author: title and link can share a <p>.
        block = re.sub(r'<a\b[^>]*>.*?</a>', '', block, flags=re.DOTALL)

        # Stop at copyright line (<em> italic text, no poem content)
        if block.strip().startswith('<em>') and ('Copyright' in block or
           'Used by' in block or 'Used with' in block or 'copyright' in block.lower()):
            break

        # Title/author block: skip it and mark that we've passed the header.
        # Covers <strong>, <em>, and plain-text 'TITLE\nby AUTHOR' blocks.
        raw_text = text_of(block)
        is_title_block = (
            '<strong>' in block
            or ('<em>' in block and not any(
                kw in block.lower() for kw in ('copyright', 'used by', 'used with')))
            or (not found_title and re.search(r'(?:^|\n)by\s+\S', raw_text, re.IGNORECASE)
                and len(raw_text) < 300)
        )
        if is_title_block and not found_title:
            found_title = True
            continue

        if found_title:
            # Convert <br/> to newlines within the paragraph
            line_text = re.sub(r'<br\s*/?>', '\n', block, flags=re.IGNORECASE)
            line_text = re.sub(r'<[^>]+>', '', line_text)
            line_text = decode_entities(line_text).strip()
            if line_text:
                stanzas.append(line_text)

    poem = '\n\n'.join(stanzas)
    return clean_stanza_text(poem)


def clean_stanza_text(text: str) -> str:
    """Normalize poem text: strip per-line trailing whitespace, collapse 3+
    blank lines into 2, strip leading/trailing blank lines."""
    lines = text.split('\n')
    lines = [ln.rstrip() for ln in lines]
    # Collapse runs of 3+ blank lines into 2
    result = []
    blank_run = 0
    for ln in lines:
        if ln == '':
            blank_run += 1
            if blank_run <= 2:
                result.append(ln)
        else:
            blank_run = 0
            result.append(ln)
    text = '\n'.join(result).strip('\n')
    return text


# ---------------------------------------------------------------------------
# Main per-episode parser
# ---------------------------------------------------------------------------

def parse_episode(record: dict) -> dict:
    url = record['url']
    html = record['html']

    ep_num = get_episode_number(url)
    published_date = get_published_date(html)
    host_name = get_host(ep_num)

    body_html = get_body_html(html)
    if not body_html:
        return _no_poem(url, ep_num, published_date, host_name, 'no_body')

    # Check for image-only poem (poem rendered as a picture, no text available)
    has_pre = '<pre class="verse">' in body_html
    has_hr = '<hr/>' in body_html

    # If there's an <hr/> but the poem section is just a <figure>, we can't extract text.
    # These two episodes need manual transcription: ep 986 and ep 1332 (Slow Take).
    if has_hr and not has_pre:
        after_hr = body_html[body_html.find('<hr/>'):]
        if '<figure' in after_hr:
            before_figure = after_hr[:after_hr.find('<figure')]
            # If nothing meaningful precedes the figure (just a title block, no <p> poem lines)
            text_before = re.sub(r'<[^>]+>', '', before_figure).strip()
            if not text_before or (len(text_before) < 200 and '<strong>' in before_figure):
                return _no_poem(url, ep_num, published_date, host_name, 'poem_is_image')

    # Determine which section to extract title/author and poem from.
    # When <hr/> is present, all poem content (title, author, text) follows the
    # last <hr/>. When there are multiple <pre class="verse"> blocks (e.g. host
    # commentary quotes a poem, then the featured poem follows the <hr/>), we
    # must anchor to the <hr/> rather than the first <pre> in the document.
    if has_pre:
        if has_hr:
            hr_pos = body_html.rfind('<hr/>')
            after_hr = body_html[hr_pos:]
            local_pre = after_hr.find('<pre class="verse">')
            if local_pre >= 0:
                # Normal case: featured poem's <pre> is after the <hr/>
                section_for_title = after_hr[:local_pre]
                poem_section = after_hr
            else:
                # Unusual: <pre> precedes <hr/> — use body-wide search
                pre_start = body_html.find('<pre class="verse">')
                section_for_title = body_html[:pre_start]
                if '<hr/>' in section_for_title:
                    section_for_title = section_for_title[section_for_title.rfind('<hr/>'):]
                poem_section = body_html
        else:
            pre_start = body_html.find('<pre class="verse">')
            section_for_title = body_html[:pre_start]
            poem_section = body_html
    else:
        if has_hr:
            poem_section = body_html[body_html.rfind('<hr/>'):]
            section_for_title = poem_section
        else:
            poem_section = body_html
            section_for_title = body_html

    poem_title, poet_name = extract_title_author(section_for_title)

    # If we couldn't find a title, this isn't a poem episode
    if not poem_title:
        return _no_poem(url, ep_num, published_date, host_name, 'no_title_found')

    # Extract poem text
    if has_pre:
        poem_text = extract_poem_pre(poem_section)
    else:
        poem_text = extract_poem_paragraphs(poem_section)

    # Flag very short poems (< 3 lines) as suspicious
    line_count = len([l for l in poem_text.split('\n') if l.strip()])
    flags = []
    if line_count < 3:
        flags.append('very_short')
    if not poet_name:
        flags.append('missing_attribution')
    if not poem_text:
        return _no_poem(url, ep_num, published_date, host_name, 'no_poem_text')

    return {
        'episode_number': ep_num,
        'source_url': url,
        'published_date': published_date,
        'host_name': host_name,
        'poem_title': decode_entities(poem_title),
        'poet_name': decode_entities(poet_name),
        'poem_text': poem_text,
        'has_poem': True,
        'flags': flags,
    }


def _no_poem(url, ep_num, published_date, host_name, reason):
    return {
        'episode_number': ep_num,
        'source_url': url,
        'published_date': published_date,
        'host_name': host_name,
        'poem_title': '',
        'poet_name': '',
        'poem_text': '',
        'has_poem': False,
        'flags': [reason],
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    raw_path = 'scripts/slowdown_raw.json'
    out_path = 'scripts/slowdown_parsed.json'
    report_path = 'scripts/slowdown_parse_report.txt'

    with open(raw_path, encoding='utf-8') as f:
        raw = json.load(f)

    print(f'Processing {len(raw)} episodes…', file=sys.stderr)
    results = [parse_episode(r) for r in raw]

    poems = [r for r in results if r['has_poem']]
    no_poem = [r for r in results if not r['has_poem']]
    flagged = [r for r in poems if r['flags']]

    # Write output (has_poem=True only)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(poems, f, ensure_ascii=False, indent=2)

    # Write report
    samples = random.sample(poems, min(10, len(poems)))
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f'SLOWDOWN PARSE REPORT\n{"="*60}\n\n')
        image_eps = [r for r in no_poem if 'poem_is_image' in r['flags']]
        f.write(f'Total episodes processed : {len(results)}\n')
        f.write(f'has_poem = True          : {len(poems)}\n')
        f.write(f'has_poem = False         : {len(no_poem)}\n')
        f.write(f'Flagged (unusual)        : {len(flagged)}\n')
        f.write(f'Poem-as-image (dropped)  : {len(image_eps)}\n\n')

        if image_eps:
            f.write('EPISODES DROPPED — POEM IS AN IMAGE (manual transcription needed)\n' + '-'*60 + '\n')
            for r in image_eps:
                f.write(f"  ep {r['episode_number']} — {r['source_url']}\n")
            f.write('\n')

        f.write('HAS_POEM = FALSE EPISODES\n' + '-'*40 + '\n')
        for r in sorted(no_poem, key=lambda x: (x['episode_number'] or 0)):
            f.write(f"  [{r['flags']}] ep {r['episode_number']} — {r['source_url']}\n")

        f.write('\nFLAGGED EPISODES (has_poem=True but unusual)\n' + '-'*40 + '\n')
        for r in flagged:
            f.write(f"  [{r['flags']}] ep {r['episode_number']} — {r['source_url']}\n")
            f.write(f"    title: {r['poem_title']} / poet: {r['poet_name']}\n")
            f.write(f"    text:  {r['poem_text'][:120]!r}\n")

        f.write('\n' + '='*60 + '\n10 RANDOM SAMPLES\n' + '='*60 + '\n\n')
        for i, r in enumerate(samples, 1):
            f.write(f'--- Sample {i} ---\n')
            f.write(f"ep         : {r['episode_number']}\n")
            f.write(f"url        : {r['source_url']}\n")
            f.write(f"date       : {r['published_date']}\n")
            f.write(f"host       : {r['host_name']}\n")
            f.write(f"poem_title : {r['poem_title']}\n")
            f.write(f"poet_name  : {r['poet_name']}\n")
            f.write(f"flags      : {r['flags']}\n")
            f.write(f"poem_text  :\n")
            preview = r['poem_text'][:400]
            for line in preview.split('\n'):
                f.write(f"  {line}\n")
            if len(r['poem_text']) > 400:
                f.write('  […]\n')
            f.write('\n')

    print(f'Done. {len(poems)} poem records → {out_path}', file=sys.stderr)
    print(f'Report → {report_path}', file=sys.stderr)


if __name__ == '__main__':
    main()
