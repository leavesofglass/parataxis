#!/usr/bin/env python3
"""
versedaily_parse.py -- Parse versedaily_wayback_raw.json into structured JSON.

Input:  versedaily_wayback_raw.json   (5,903 records, fields: url, wayback_url,
                                        wayback_timestamp, html, fetched_at)
Output: versedaily_parsed.json
        versedaily_parse_drops.json
        versedaily_parse_report.txt

HTML structure (Wayback Machine snapshots of versedaily.org):
  - All pages share one layout: logo → "Today's poem is by POET" → <blockquote>
  - <blockquote> contains: bold title → optional epigraph → poem body → copyright block
  - Poem lines: TEXT<br>  (stanza break: trailing <p> at end of each stanza)
  - Indented lines: TEXT<br>&nbsp; &nbsp; ...\\n INDENTED_TEXT
  - Prose poems (114 records): <p align="justify">PROSE</p>
  - Copyright block: inside <font size="-1">, contains "Copyright © YEAR POET" and
    "from <i>BOOK_OR_JOURNAL</i>" then optional PUBLISHER line before "Reprinted"
  - No specific publication date on pages; year inferred from copyright block.

Field shape matches ralp_parsed.json / slowdown_parsed.json / poetrydaily_parsed.json.
"""

import html as html_lib
import json
import re
from pathlib import Path

INPUT_FILE  = "versedaily_wayback_raw.json"
OUTPUT_FILE = "versedaily_parsed.json"
DROPS_FILE  = "versedaily_parse_drops.json"
REPORT_FILE = "versedaily_parse_report.txt"


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def inner_text(html_fragment: str) -> str:
    """Strip tags, decode entities, collapse whitespace."""
    t = re.sub(r"<[^>]+>", " ", html_fragment)
    t = html_lib.unescape(t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

def extract_title(html: str) -> str:
    """Extract poem title from <b><font>TITLE</font></b> in blockquote."""
    bq_start = html.find("<blockquote>")
    if bq_start >= 0:
        bq = html[bq_start : bq_start + 800]
        # Both nested-font and single-font variants appear in the corpus
        m = re.search(
            r"<b><font[^>]*>(?:<font[^>]*>)?(.*?)(?:</font>)?</font></b>",
            bq,
            re.DOTALL,
        )
        if m:
            title = inner_text(m.group(1)).strip("\"'")
            if title:
                return title

    # Fallback: <title> tag (strip "Verse Daily: " prefix and " by POET" suffix)
    m = re.search(r"<title>([^<]+)</title>", html)
    if not m:
        return ""
    title = html_lib.unescape(m.group(1))
    title = re.sub(r"^Verse Daily:\s*", "", title, flags=re.IGNORECASE)
    title = re.sub(r'\s+by\s+.*$', "", title, flags=re.IGNORECASE)
    return title.strip().strip("\"'")


# ---------------------------------------------------------------------------
# Poet name
# ---------------------------------------------------------------------------

def extract_poet(html: str) -> str:
    """Extract poet name(s) from 'Today's poem is by POET' line."""
    m = re.search(
        r"Today's poems?\s+(?:is|are)\s+by\s+(.*?)(?:</center>|</font>\s*\n|<br|\n\n)",
        html,
        re.DOTALL | re.IGNORECASE,
    )
    if not m:
        return ""
    by_html = m.group(1)
    links = re.findall(r"<a[^>]*>(.*?)</a>", by_html, re.DOTALL)
    if links:
        parts = [inner_text(lk) for lk in links if inner_text(lk)]
        return " and ".join(parts)
    return inner_text(by_html).strip(", ")


# ---------------------------------------------------------------------------
# Poem text
# ---------------------------------------------------------------------------

def _get_blockquote_html(html: str) -> str:
    """Return the content of the outermost <blockquote>...</blockquote>.
    Tracks nesting depth so that nested <blockquote> tags don't terminate early."""
    start = html.find("<blockquote>")
    if start < 0:
        return ""
    content_start = start + len("<blockquote>")
    depth = 1
    pos = content_start
    while depth > 0 and pos < len(html):
        open_pos  = html.find("<blockquote>", pos)
        close_pos = html.find("</blockquote>", pos)
        if close_pos < 0:
            return html[content_start:]          # no close tag; return rest
        if open_pos >= 0 and open_pos < close_pos:
            depth += 1
            pos = open_pos + len("<blockquote>")
        else:
            depth -= 1
            if depth == 0:
                return html[content_start:close_pos]
            pos = close_pos + len("</blockquote>")
    return html[content_start:]


def _prose_block(m: re.Match) -> str:
    """Collapse a <p align="justify">...</p> prose paragraph to plain text."""
    content = m.group(1)
    content = re.sub(r"<br\s*/?>", "\n", content)
    content = re.sub(r"<[^>]+>", " ", content)
    content = html_lib.unescape(content).replace("\xa0", " ")
    return "\n\n" + " ".join(content.split()) + "\n\n"


def _br_to_newline(m: re.Match) -> str:
    """Convert <br> + trailing &nbsp; indentation + optional physical newline
    to a newline followed by indentation spaces."""
    indent = m.group(1).replace("&nbsp;", " ").replace("&#160;", " ")
    return "\n" + indent


def _html_to_poem_text(html_fragment: str) -> str:
    """Convert poem-body HTML to plain text, preserving lineation and indentation."""
    text = html_fragment

    # 1. Prose poem blocks: whitespace-normalize their interior
    text = re.sub(
        r'<p[^>]*\bjustify\b[^>]*>(.*?)</p>',
        _prose_block,
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 2. <br> + &nbsp; indentation + optional physical newline → "\n" + spaces
    #    Pattern captures the (&nbsp; or &#160;) + literal-space sequences that follow
    #    the <br> and precede the physical newline (HTML formatting noise).
    text = re.sub(
        r"<br[ \t]*/?>[ \t]*((?:(?:&nbsp;|&#160;)[ \t]*)*)\n?",
        _br_to_newline,
        text,
    )

    # 3. Stanza breaks: <p> (or <p ...>) marks end-of-stanza on VD pages
    text = re.sub(r"</p\s*>", "\n\n", text)
    text = re.sub(r"<p[^>]*>", "\n\n", text)

    # 4. Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)

    # 5. Decode entities; replace non-breaking space with regular space
    text = html_lib.unescape(text)
    text = text.replace("\xa0", " ")

    # 6. Normalize each line: strip trailing whitespace, collapse internal runs
    #    of spaces to one (handles physical source-line wrapping in prose areas),
    #    but preserve leading spaces (meaningful indentation).
    lines = text.split("\n")
    processed = []
    for line in lines:
        rstripped = line.rstrip()
        if not rstripped.strip():
            processed.append("")
            continue
        leading = len(rstripped) - len(rstripped.lstrip(" "))
        content = " ".join(rstripped.split())
        processed.append(" " * leading + content)
    text = "\n".join(processed)

    # 7. Collapse 3+ consecutive blank lines to one blank line (stanza break)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip("\n").strip()


def _find_copyright_pos(bq: str) -> int:
    """Return the position of the copyright block within the blockquote HTML.
    Keys off 'Copyright' (with &copy; or ©) rather than <font size="-1">,
    because the font tag also appears (empty) in the epigraph slot near the title."""
    for pat in ("Copyright &copy;", "Copyright ©", "Copyright &#169;"):
        pos = bq.find(pat)
        if pos >= 0:
            return pos
    return -1


def extract_poem_text(html: str) -> str:
    bq = _get_blockquote_html(html)
    if not bq:
        return ""

    # Poem body starts after the title </b> block (rare records use </i>).
    title_end = bq.find("</b>")
    if title_end < 0:
        title_end = bq.find("</i>")
    if title_end < 0:
        return ""
    after_title = bq[title_end:]

    # Limit poem-start search to the region before the copyright block so we
    # don't accidentally match the copyright block's own font tags.
    cp_pos_in_bq = _find_copyright_pos(bq)
    search_limit = (
        (cp_pos_in_bq - title_end) if cp_pos_in_bq > title_end else len(after_title)
    )
    search_area = after_title[:search_limit]

    # Primary: optional <p> + <font face="Times New..."> (handles standard layout,
    # missing <p>, and one corrupted "Times New RoPond,Times" font name).
    # Search in the full after_title so the content-after-match is visible for
    # the check below; use search_limit to ignore matches past the copyright.
    poem_start_m = None
    for _m in re.finditer(
        r'(?:<p[^>]*>\s*)?<font face="Times New[^"]*"[^>]*>(?:\s*<font[^>]*>)?',
        after_title,
    ):
        if _m.start() >= search_limit:
            break
        # Reject the copyright block's own font tag (immediately followed by "Copyright")
        if re.match(r"\s*Copyright", after_title[_m.end() :]):
            continue
        poem_start_m = _m
        break
    # Fallback: poem starts with <p><br>\n\n (no font wrapper; rare ~2 records)
    if not poem_start_m:
        poem_start_m = re.search(r"<p[^>]*>\s*<br\s*/?>\s*\n\s*\n", search_area)
    if not poem_start_m:
        return ""

    poem_html = after_title[poem_start_m.end():]

    # Poem body ends at social share buttons (<iframe) or the copyright block.
    cp_pos_in_poem = (
        cp_pos_in_bq - (title_end + poem_start_m.end())
        if cp_pos_in_bq >= 0 else -1
    )
    end_markers = [
        pos
        for pos in (poem_html.find("<iframe"), cp_pos_in_poem)
        if pos >= 0
    ]
    if end_markers:
        poem_html = poem_html[: min(end_markers)]

    # Image-only poems have no extractable text
    if "<img" in poem_html:
        stripped = re.sub(r"<[^>]+>", "", poem_html).replace("&nbsp;", "").strip()
        if not stripped:
            return ""

    return _html_to_poem_text(poem_html)


# ---------------------------------------------------------------------------
# Copyright / source block
# ---------------------------------------------------------------------------

def extract_copyright_block(html: str) -> str:
    """Return ~800 chars of raw HTML starting from 'Copyright' in the blockquote.
    Works for both older records (copyright in <font size="-1">) and newer ones
    where copyright is placed directly after the social share buttons."""
    bq = _get_blockquote_html(html)
    if not bq:
        return ""
    pos = _find_copyright_pos(bq)
    if pos < 0:
        return ""
    return bq[pos : pos + 800]


def extract_source_year(copyright_html: str) -> str | None:
    m = re.search(r"(?:©|&copy;)\s*(\d{4})", copyright_html)
    return m.group(1) if m else None


def extract_source_name(copyright_html: str) -> str | None:
    """Return book or journal title from 'from <i>NAME</i>'."""
    m = re.search(r"from\s*<i>(.*?)</i>", copyright_html, re.DOTALL)
    if not m:
        return None
    return inner_text(m.group(1)) or None


def extract_publisher(copyright_html: str) -> str | None:
    """Return publisher name from the line after 'from <i>...</i>', if present.
    A publisher line indicates the source is a book rather than a journal."""
    m = re.search(r"</i>(.*?)(?:Reprinted|$)", copyright_html, re.DOTALL)
    if not m:
        return None
    between = m.group(1)
    # Prefer link text (publisher usually has a hyperlink)
    link_m = re.search(r"<a[^>]*>(.*?)</a>", between, re.DOTALL)
    if link_m:
        pub = inner_text(link_m.group(1))
        if pub and len(pub) > 2:
            return pub
    # Fallback: plain text between tags
    plain = inner_text(between)
    if plain and len(plain) > 2:
        return plain
    return None


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

class ParseDrop(Exception):
    pass


def parse_record(rec: dict) -> dict:
    url  = rec["url"]
    html = rec["html"]

    if "<blockquote>" not in html:
        raise ParseDrop("no <blockquote> found")
    if "Today's poem" not in html:
        raise ParseDrop("no 'Today's poem' found")

    bq = _get_blockquote_html(html)

    title = extract_title(html)
    poet  = extract_poet(html)

    poem_text     = extract_poem_text(html)
    copyright_html = extract_copyright_block(html)

    source_year  = extract_source_year(copyright_html) if copyright_html else None
    source_name  = extract_source_name(copyright_html) if copyright_html else None
    publisher    = extract_publisher(copyright_html) if copyright_html else None

    # Book vs journal: a publisher name after the source <i>...</i> means it's a book.
    # Amazon links also signal a book (some small-press records link elsewhere).
    is_book = bool(publisher and len(publisher.strip()) > 2)
    if not is_book and copyright_html and "amazon.com" in copyright_html:
        is_book = True

    source_book    = source_name if is_book else None
    source_journal = source_name if not is_book else None
    has_poem = bool(poem_text and poem_text.strip())
    if not has_poem:
        cp_pos_in_bq   = _find_copyright_pos(bq)
        title_end_in_bq = bq.find("</b>")
        if title_end_in_bq >= 0:
            after_title_area = bq[title_end_in_bq : cp_pos_in_bq if cp_pos_in_bq >= 0 else len(bq)]
            if "<img" in after_title_area:
                raise ParseDrop("image-only poem")

    return {
        "source_url":       url,
        "published_date":   None,   # VD pages show no specific date; year in source_year
        "poem_title":       title or None,
        "poet_name":        poet or None,
        "poem_text":        poem_text or None,
        "source_book":      source_book,
        "source_journal":   source_journal,
        "source_publisher": publisher,
        "source_year":      source_year,
        "has_poem":         has_poem,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Verse Daily parser")
    print("=" * 60)

    with open(INPUT_FILE) as f:
        data = json.load(f)
    print(f"Loaded {len(data)} records from {INPUT_FILE}")

    poems: list[dict] = []
    drops: list[dict] = []

    for i, rec in enumerate(data):
        url = rec.get("url", f"record_{i}")
        try:
            result = parse_record(rec)
            poems.append(result)
        except ParseDrop as e:
            title = ""
            try:
                title = extract_title(rec["html"])
            except Exception:
                pass
            drops.append({"url": url, "title": title, "reason": str(e)})

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(poems, f, indent=2, ensure_ascii=False)

    with open(DROPS_FILE, "w", encoding="utf-8") as f:
        json.dump(drops, f, indent=2, ensure_ascii=False)

    # --- Stats ---
    has_poem_count = sum(1 for p in poems if p["has_poem"])
    has_book       = sum(1 for p in poems if p["source_book"])
    has_journal    = sum(1 for p in poems if p["source_journal"])
    no_source      = sum(1 for p in poems if not p["source_book"] and not p["source_journal"])
    has_year       = sum(1 for p in poems if p["source_year"])
    has_publisher  = sum(1 for p in poems if p["source_publisher"])
    no_title       = sum(1 for p in poems if not p["poem_title"])

    report_lines = [
        "=" * 60,
        "Verse Daily parse report",
        "=" * 60,
        f"Input records:            {len(data)}",
        f"Parsed (kept):            {len(poems)}",
        f"Dropped:                  {len(drops)}",
        "",
        f"has_poem = true:          {has_poem_count}",
        f"has_poem = false:         {len(poems) - has_poem_count}",
        "",
        f"source_book:              {has_book}",
        f"source_journal:           {has_journal}",
        f"neither (no copyright):   {no_source}",
        f"has source_year:          {has_year}",
        f"has source_publisher:     {has_publisher}",
        "",
        f"missing poem_title:       {no_title}",
        "",
    ]

    if drops:
        report_lines.append(f"DROPPED RECORDS ({len(drops)}):")
        for d in drops:
            report_lines.append(f"  [{d['reason']}]  {d['url']}")
            if d["title"]:
                report_lines.append(f"    title: {d['title']}")
        report_lines.append("")

    # Sample 3 parsed records for spot-check
    report_lines.append("SAMPLE RECORDS (first 3 with has_poem=true):")
    count = 0
    for p in poems:
        if not p["has_poem"] or count >= 3:
            continue
        report_lines += [
            f"  url:    {p['source_url']}",
            f"  title:  {p['poem_title']}",
            f"  poet:   {p['poet_name']}",
            f"  book:   {p['source_book']}",
            f"  jrnl:   {p['source_journal']}",
            f"  pub:    {p['source_publisher']}",
            f"  year:   {p['source_year']}",
            f"  text:   {repr(p['poem_text'][:120]) if p['poem_text'] else 'None'}",
            "",
        ]
        count += 1

    report_text = "\n".join(report_lines)
    print(report_text)
    Path(REPORT_FILE).write_text(report_text)

    print(f"\nWrote {len(poems)} records to {OUTPUT_FILE}")
    print(f"Wrote {len(drops)} drops to {DROPS_FILE}")
    print(f"Report saved to {REPORT_FILE}")


if __name__ == "__main__":
    main()
