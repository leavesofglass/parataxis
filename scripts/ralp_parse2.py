"""
ralp_parse2.py — Like ralp_parse.py but preserves inline emphasis and leading
indentation in poem bodies.

What poem_text_html adds vs plain poem_text:
  • <em> and <i> normalized to <em>; all other tags stripped
  • <strong> elements whose content is only whitespace/&nbsp; are emitted as
    literal spaces (the indentation hack RALP editors used)
  • Leading \xa0 (decoded &nbsp;) in text nodes converted to regular space
  • Leading whitespace on each content line is never stripped

Stanza breaks (blank lines) are identical to poem_text.

Output: scripts/ralp_parsed2.json
"""

import json
import random
import re
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

INPUT  = Path(__file__).parent / 'ralp_raw.json'
OUTPUT = Path(__file__).parent / 'ralp_parsed2.json'

BILINGUAL_SUFFIXES = ['-A', '-B', '-C', '-D']


# ── HTML utilities ─────────────────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
    """Identical to original parser — used to produce poem_text (no change)."""
    BLOCK = {'p', 'div', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
             'li', 'tr', 'blockquote'}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCK:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in self.BLOCK:
            self.parts.append('\n')

    def handle_data(self, data):
        self.parts.append(data)

    def get_text(self) -> str:
        return unescape(''.join(self.parts))


class _EmExtractor(HTMLParser):
    """
    Like _TextExtractor but:
      • <em>/<i> → <em>…</em> in output
      • <strong> whose content is all whitespace/\xa0 → emitted as spaces
      • <strong> with real text → content emitted as plain text (not discarded)
      • \xa0 in all text nodes → converted to regular space
      • Leading whitespace on lines is NOT stripped (caller handles collapse)
    """
    BLOCK = {'p', 'div', 'br', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
             'li', 'tr', 'blockquote'}

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._strong_buf: list[str] | None = None  # None = not inside <strong>

    # ── strong-buffering helpers ──────────────────────────────────────────────

    def _flush_strong(self) -> None:
        if self._strong_buf is None:
            return
        raw = ''.join(self._strong_buf)
        normalized = raw.replace('\xa0', ' ')
        if normalized.strip() == '':
            # All whitespace — indentation hack; emit as spaces
            self.parts.append(normalized)
        else:
            # Real content inside <strong> — emit as plain text
            self.parts.append(normalized)
        self._strong_buf = None

    # ── HTMLParser callbacks ──────────────────────────────────────────────────

    def handle_starttag(self, tag, attrs):
        if tag == 'strong':
            self._flush_strong()  # nested or adjacent strongs
            self._strong_buf = []
        elif tag in ('em', 'i'):
            self._flush_strong()
            self.parts.append('<em>')
        elif tag in self.BLOCK:
            self._flush_strong()
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag == 'strong':
            self._flush_strong()
        elif tag in ('em', 'i'):
            self.parts.append('</em>')
        elif tag in self.BLOCK:
            self._flush_strong()
            self.parts.append('\n')

    def handle_data(self, data):
        text = data.replace('\xa0', ' ')
        if self._strong_buf is not None:
            self._strong_buf.append(text)
        else:
            self.parts.append(text)

    def get_html(self) -> str:
        self._flush_strong()
        # unescape catches any residual HTML entities the parser didn't decode
        return unescape(''.join(self.parts))


def html_to_text(html: str) -> str:
    p = _TextExtractor()
    p.feed(html)
    return p.get_text()


def html_to_em_html(html: str) -> str:
    p = _EmExtractor()
    p.feed(html)
    return p.get_html()


def strip_tags(html: str) -> str:
    return unescape(re.sub(r'<[^>]+>', '', html))


def collapse_lines(text: str) -> str:
    """Original collapse — strips leading/trailing whitespace from each line."""
    lines = text.split('\n')
    out, prev_blank = [], False
    for line in lines:
        s = line.strip()
        if s == '':
            if not prev_blank:
                out.append('')
            prev_blank = True
        else:
            out.append(s)
            prev_blank = False
    return '\n'.join(out).strip()


def collapse_lines_html(text: str) -> str:
    """
    Like collapse_lines but preserves leading whitespace on content lines.
    A line is blank if it has no visible text after stripping tags.
    """
    lines = text.split('\n')
    out, prev_blank = [], False
    for line in lines:
        # Trailing whitespace only — preserve leading spaces
        rstripped = line.rstrip()
        # Blank if no visible text after removing tags
        content = re.sub(r'<[^>]+>', '', rstripped).strip()
        if content == '':
            if not prev_blank:
                out.append('')
            prev_blank = True
        else:
            out.append(rstripped)
            prev_blank = False
    # Strip blank lines from the very start and end, but never content indentation
    joined = '\n'.join(out)
    lines2 = joined.split('\n')
    start = 0
    while start < len(lines2) and lines2[start] == '':
        start += 1
    end = len(lines2)
    while end > start and lines2[end - 1] == '':
        end -= 1
    return '\n'.join(lines2[start:end])


# ── Blockquote classification ──────────────────────────────────────────────────

POEM_H5_RE = re.compile(
    r'<h5[^>]*>.*?<strong[^>]*>.*?</strong>.*?<em[^>]*>.*?</em>.*?</h5>',
    re.DOTALL | re.IGNORECASE,
)

def is_poem_bq(bq_inner: str) -> bool:
    return POEM_H5_RE.search(bq_inner) is not None


# ── Poem extraction from a single poem blockquote ──────────────────────────────

def parse_poem_bq(bq_inner: str) -> dict:
    h5_match = re.search(r'<h5[^>]*>(.*?)</h5>', bq_inner, re.DOTALL | re.IGNORECASE)
    poem_title = ''
    poet_name  = ''
    translator = ''

    if h5_match:
        h5 = h5_match.group(1)
        strong = re.search(r'<strong[^>]*>(.*?)</strong>', h5, re.DOTALL)
        if strong:
            poem_title = strip_tags(strong.group(1)).strip()

        ems = re.findall(r'<em[^>]*>(.*?)</em>', h5, re.DOTALL)
        for i, em in enumerate(ems):
            val = strip_tags(em).strip()
            if i == 0:
                poet_name = val
            elif re.match(r'(?i)translated?\s+by', val):
                translator = val

        bq_inner = bq_inner[h5_match.end():]

    poem_text      = collapse_lines(html_to_text(bq_inner))
    poem_text_html = collapse_lines_html(html_to_em_html(bq_inner))

    return {
        'poem_title':      poem_title,
        'poet_name':       poet_name,
        'translator':      translator,
        'poem_text':       poem_text,
        'poem_text_html':  poem_text_html,
    }


# ── Curator notes ─────────────────────────────────────────────────────────────

def extract_curator_notes(html_before: str) -> str:
    text = collapse_lines(html_to_text(html_before))
    if re.fullmatch(r'[\[\]\w\s=\'"#,;./-]*', text):
        return ''
    if len(text) < 40:
        return ''
    return text


# ── Slug helpers ──────────────────────────────────────────────────────────────

def parse_slug(slug: str) -> tuple[str, str]:
    if '-by-' not in slug:
        return '', ''
    parts = slug.rsplit('-by-', 1)
    return parts[0].replace('-', ' ').title(), parts[1].replace('-', ' ').title()


# ── Announcement detection ────────────────────────────────────────────────────

ANNOUNCEMENT_RE = re.compile(
    r'join us|thank you|20 years|anniversary|letter from|love letter|'
    r'found language|field guide|hello.{0,10}update|subscribe|'
    r'what we seek|power of poetry|in praise of|poems we carry|'
    r'this place has given|rapture to rediscover|grief can give|'
    r'encounter with you|quiet in your words|you are awesome|'
    r'a stranger|earning|earnest',
    re.IGNORECASE,
)

def is_announcement(slug: str, title: str) -> bool:
    return '-by-' not in slug and bool(ANNOUNCEMENT_RE.search(f'{slug} {title}'))


# ── Record builder ────────────────────────────────────────────────────────────

def build_record(
    p: dict,
    poem: dict | None,
    bilingual_group_id: str | None,
    has_poem: bool,
    is_roundup: bool,
    is_multipost: bool,
    announcement: bool,
) -> dict:
    post_title = unescape(p['title']['rendered'])
    slug = p['slug']

    poem_title     = poem['poem_title']     if poem else ''
    poet_name      = poem['poet_name']      if poem else ''
    translator     = poem['translator']     if poem else ''
    poem_text      = poem['poem_text']      if poem else ''
    poem_text_html = poem['poem_text_html'] if poem else ''

    if has_poem and (not poem_title or not poet_name):
        slug_title, slug_poet = parse_slug(slug)
        if not poem_title:
            poem_title = slug_title
        if not poet_name:
            poet_name = slug_poet

    if has_poem and (not poem_title or not poet_name):
        m = re.match(r'^(.+?)\s+by\s+(.+)$', post_title, re.IGNORECASE)
        if m:
            if not poem_title: poem_title = m.group(1).strip()
            if not poet_name:  poet_name  = m.group(2).strip()

    return {
        'post_id':            p['id'],
        'source_url':         p['link'],
        'published_date':     p['date'],
        'post_title':         post_title,
        'post_categories':    p['categories'],
        'poet_name':          poet_name,
        'translator':         translator,
        'poem_title':         poem_title,
        'poem_text':          poem_text,
        'poem_text_html':     poem_text_html,
        'bilingual_group_id': bilingual_group_id,
        'flags': {
            'has_poem':        has_poem,
            'is_multipost':    is_multipost,
            'is_roundup':      is_roundup,
            'is_announcement': announcement,
        },
    }


# ── Per-post parsing ──────────────────────────────────────────────────────────

def parse_post(p: dict) -> list[dict]:
    html = p['content']['rendered']
    slug = p['slug']
    post_title = unescape(p['title']['rendered'])
    announcement = is_announcement(slug, post_title)

    all_bqs = re.findall(
        r'<blockquote[^>]*>(.*?)</blockquote>', html, re.DOTALL | re.IGNORECASE
    )
    poem_bqs = [bq for bq in all_bqs if is_poem_bq(bq)]

    has_poem   = len(poem_bqs) > 0
    is_roundup = not has_poem and len(all_bqs) >= 2
    bilingual  = len(poem_bqs) >= 2

    if not has_poem:
        return [build_record(
            p, poem=None,
            bilingual_group_id=None,
            has_poem=False, is_roundup=is_roundup,
            is_multipost=False, announcement=announcement,
        )]

    if not bilingual:
        parsed = parse_poem_bq(poem_bqs[0])
        return [build_record(
            p, poem=parsed,
            bilingual_group_id=None,
            has_poem=True, is_roundup=False,
            is_multipost=False, announcement=announcement,
        )]

    rows = []
    for i, bq in enumerate(poem_bqs):
        parsed = parse_poem_bq(bq)
        suffix = BILINGUAL_SUFFIXES[i] if i < len(BILINGUAL_SUFFIXES) else f'-{i}'
        group_id = f"{p['id']}{suffix}"
        rows.append(build_record(
            p, poem=parsed,
            bilingual_group_id=group_id,
            has_poem=True, is_roundup=False,
            is_multipost=True, announcement=announcement,
        ))
    return rows


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f'Reading {INPUT} …')
    with open(INPUT) as f:
        posts = json.load(f)
    print(f'  {len(posts)} posts loaded.')

    all_records: list[dict] = []
    for i, p in enumerate(posts):
        if i % 100 == 0:
            print(f'  Parsing post {i+1}/{len(posts)} …', end='\r', flush=True)
        all_records.extend(parse_post(p))
    print(f'\n  Done. {len(all_records)} records.')

    with open(OUTPUT, 'w') as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)
    print(f'Wrote {OUTPUT}')

    # ── Stats ─────────────────────────────────────────────────────────────────
    poem_recs = [r for r in all_records if r['flags']['has_poem']]

    gained_emphasis = []
    gained_indent   = []
    for r in poem_recs:
        plain = r['poem_text']
        html  = r['poem_text_html']
        if '<em>' in html:
            gained_emphasis.append(r)
        # Indentation: any line in html starts with a space that the plain line doesn't
        plain_lines = plain.split('\n')
        html_lines  = html.split('\n')
        indented = False
        for pl, hl in zip(plain_lines, html_lines):
            if hl.startswith(' ') and not pl.startswith(' '):
                indented = True
                break
        # Also catch lines added by indentation (len mismatch)
        if not indented:
            for hl in html_lines:
                if hl.startswith(' '):
                    indented = True
                    break
        if indented:
            gained_indent.append(r)

    print(f'\nPoem records:            {len(poem_recs)}')
    print(f'Gained <em> emphasis:    {len(gained_emphasis)}')
    print(f'Gained indentation:      {len(gained_indent)}')
    print()

    # ── Five before/after examples ────────────────────────────────────────────
    random.seed(42)

    indent_sample = random.sample(gained_indent, min(2, len(gained_indent)))
    em_only = [r for r in gained_emphasis if r not in gained_indent]
    em_sample = random.sample(em_only, min(3, len(em_only)))
    examples = indent_sample + em_sample

    for r in examples:
        print(f'── {r["poem_title"]} / {r["poet_name"]} (post {r["post_id"]}) ──')
        plain_lines = r['poem_text'].split('\n')
        html_lines  = r['poem_text_html'].split('\n')
        diff_shown  = 0
        for pl, hl in zip(plain_lines, html_lines):
            if pl != hl and diff_shown < 4:
                print(f'  BEFORE: {repr(pl)}')
                print(f'  AFTER:  {repr(hl)}')
                diff_shown += 1
        if diff_shown == 0:
            print(f'  BEFORE: {repr(r["poem_text"][:150])}')
            print(f'  AFTER:  {repr(r["poem_text_html"][:150])}')
        print()


if __name__ == '__main__':
    random.seed(42)
    main()
