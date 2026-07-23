"""
ralp_parse.py — Parse scripts/ralp_raw.json into structured poem records.

Blockquote classification:
  POEM bq  — has <h5>...<strong>title</strong>...<em>poet</em>...</h5>
  PROSE bq — quoted text with no poem h5 (epigraph, interview, lyrics, etc.)

Per-post rules:
  0 POEM bqs → no poem record; flagged has_poem=False, is_roundup=(total_bqs≥2)
  1 POEM bq  → single output row; prose bqs dropped (epigraphs discarded)
  2+ POEM bqs → bilingual; one output row per POEM bq; bilingual_group_id links them

Output: scripts/ralp_parsed.json (flat array — bilingual posts contribute 2 items)
Report: scripts/ralp_parse_report.txt
"""

import json
import random
import re
import sys
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

INPUT  = Path(__file__).parent / 'ralp_raw.json'
OUTPUT = Path(__file__).parent / 'ralp_parsed.json'
REPORT = Path(__file__).parent / 'ralp_parse_report.txt'

BILINGUAL_SUFFIXES = ['-A', '-B', '-C', '-D']


# ── HTML utilities ─────────────────────────────────────────────────────────────

class _TextExtractor(HTMLParser):
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


def html_to_text(html: str) -> str:
    p = _TextExtractor()
    p.feed(html)
    return p.get_text()


def strip_tags(html: str) -> str:
    return unescape(re.sub(r'<[^>]+>', '', html))


def collapse_lines(text: str) -> str:
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


# ── Blockquote classification ──────────────────────────────────────────────────

POEM_H5_RE = re.compile(
    r'<h5[^>]*>.*?<strong[^>]*>.*?</strong>.*?<em[^>]*>.*?</em>.*?</h5>',
    re.DOTALL | re.IGNORECASE,
)

def is_poem_bq(bq_inner: str) -> bool:
    return POEM_H5_RE.search(bq_inner) is not None


# ── Poem extraction from a single poem blockquote ──────────────────────────────

def parse_poem_bq(bq_inner: str) -> dict:
    """Extract poem_title, poet_name, translator, poem_text from a poem bq."""
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

    poem_text = collapse_lines(html_to_text(bq_inner))
    return {
        'poem_title': poem_title,
        'poet_name':  poet_name,
        'translator': translator,
        'poem_text':  poem_text,
    }


# ── Curator notes (text before first blockquote) ──────────────────────────────

def extract_curator_notes(html_before: str) -> str:
    text = collapse_lines(html_to_text(html_before))
    # Drop WordPress shortcode artifacts
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

    # Fallback title/poet from slug then post_title
    poem_title = poem['poem_title'] if poem else ''
    poet_name  = poem['poet_name']  if poem else ''
    translator = poem['translator'] if poem else ''
    poem_text  = poem['poem_text']  if poem else ''

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

    rec: dict = {
        'post_id':            p['id'],
        'source_url':         p['link'],
        'published_date':     p['date'],
        'post_title':         post_title,
        'post_categories':    p['categories'],
        'poet_name':          poet_name,
        'translator':         translator,
        'poem_title':         poem_title,
        'poem_text':          poem_text,
        'bilingual_group_id': bilingual_group_id,
        'flags': {
            'has_poem':        has_poem,
            'is_multipost':    is_multipost,
            'is_roundup':      is_roundup,
            'is_announcement': announcement,
        },
    }
    return rec


# ── Per-post parsing (returns 1 or 2 records) ─────────────────────────────────

def parse_post(p: dict) -> list[dict]:
    html = p['content']['rendered']
    slug = p['slug']
    post_title = unescape(p['title']['rendered'])
    announcement = is_announcement(slug, post_title)

    # Extract all blockquote inner HTML
    all_bqs = re.findall(
        r'<blockquote[^>]*>(.*?)</blockquote>', html, re.DOTALL | re.IGNORECASE
    )
    poem_bqs = [bq for bq in all_bqs if is_poem_bq(bq)]

    # Curator notes: text before the first blockquote of any kind
    curator_notes = ''
    first_bq_match = re.search(r'<blockquote', html, re.IGNORECASE)
    if first_bq_match:
        curator_notes = extract_curator_notes(html[:first_bq_match.start()])

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

    # Bilingual: one row per poem bq
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
    print(f'\n  Done. {len(all_records)} records from {len(posts)} posts.')

    with open(OUTPUT, 'w') as f:
        json.dump(all_records, f, indent=2, ensure_ascii=False)
    print(f'Wrote {OUTPUT}')

    # ── Report ────────────────────────────────────────────────────────────────
    poem_recs     = [r for r in all_records if r['flags']['has_poem']]
    no_poem_recs  = [r for r in all_records if not r['flags']['has_poem']]
    bilingual_recs = [r for r in all_records if r['bilingual_group_id']]
    roundup_recs  = [r for r in all_records if r['flags']['is_roundup']]
    announce_recs = [r for r in all_records if r['flags']['is_announcement']]
    with_notes    = []  # curator_notes extracted during parse but not stored in output
    missing_poet  = [r for r in poem_recs if not r['poet_name']]
    missing_title = [r for r in poem_recs if not r['poem_title']]
    short_poem    = [r for r in poem_recs if len(r['poem_text']) < 30]
    long_poem     = [r for r in poem_recs if len(r['poem_text'].split('\n')) > 100]

    # Bilingual group count = unique group IDs / 2
    group_ids = set(r['bilingual_group_id'] for r in bilingual_recs if r['bilingual_group_id'])
    bilingual_posts = len(group_ids) // 2 + len(group_ids) % 2  # ≈ unique posts

    samples = random.sample(poem_recs, min(10, len(poem_recs)))

    lines = [
        '═══════════════════════════════════════════════════════════',
        'RALP PARSE REPORT',
        '═══════════════════════════════════════════════════════════',
        f'Input posts:                 {len(posts)}',
        f'Output records (total):      {len(all_records)}',
        f'  → poem records:            {len(poem_recs)}',
        f'  → bilingual rows (pairs):  {len(bilingual_recs)} rows from ~{len(group_ids)} posts',
        f'  → no-poem records:         {len(no_poem_recs)}',
        f'     • roundup / multi-quote: {len(roundup_recs)}',
        f'     • announcement / meta:   {len(announce_recs)}',
        f'Missing poet name:           {len(missing_poet)}',
        f'Missing poem title:          {len(missing_title)}',
        f'Very short poem text (<30c): {len(short_poem)}',
        f'Very long poem (>100 lines): {len(long_poem)}',
        '',
        '── Missing poet name ───────────────────────────────────────',
    ]
    for r in missing_poet[:10]:
        lines.append(f'  [{r["post_id"]}] {r["post_title"]}')
        lines.append(f'    {r["source_url"]}')
    lines += [
        '',
        '── Short poem text (<30 chars) ─────────────────────────────',
    ]
    for r in short_poem[:10]:
        lines.append(f'  [{r["post_id"]}] {r["post_title"]}')
        lines.append(f'    poem_text: {repr(r["poem_text"][:80])}')
    lines += [
        '',
        '── Sample bilingual pair ────────────────────────────────────',
    ]
    if bilingual_recs:
        # Show first bilingual pair
        first_group = sorted(group_ids)[0].rsplit('-', 1)[0] + '-'
        pair = [r for r in bilingual_recs if r['bilingual_group_id'] and r['bilingual_group_id'].startswith(first_group)][:2]
        for r in pair:
            lines.append(f'  bilingual_group_id: {r["bilingual_group_id"]}')
            lines.append(f'  poem_title: {r["poem_title"]}')
            lines.append(f'  poet_name:  {r["poet_name"]}')
            lines.append(f'  translator: {r["translator"] or "(none)"}')
            lines.append(f'  poem_text:  {r["poem_text"][:80].replace(chr(10), " ↵ ")} …')
            lines.append('')
    lines += [
        '── 10 Random Poem Samples ───────────────────────────────────',
    ]
    for r in samples:
        poem_preview  = r['poem_text'][:120].replace('\n', ' ↵ ')

        lines += [
            '',
            f'  post_id:            {r["post_id"]}',
            f'  poem_title:         {r["poem_title"]}',
            f'  poet_name:          {r["poet_name"]}',
            f'  translator:         {r["translator"] or "(none)"}',
            f'  published:          {r["published_date"]}',
            f'  bilingual_group_id: {r["bilingual_group_id"] or "(none)"}',
            f'  is_multipost:       {r["flags"]["is_multipost"]}',
            f'  poem_text:          {poem_preview}',
        ]

    report = '\n'.join(lines)
    with open(REPORT, 'w') as f:
        f.write(report + '\n')
    print(f'Wrote {REPORT}')
    print()
    print(report)


if __name__ == '__main__':
    random.seed(42)
    main()
