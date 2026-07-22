#!/usr/bin/env python3
"""
poetrydaily_parse.py -- Parse poetrydaily_raw.json into structured JSON.

Input:  poetrydaily_raw.json   (1,999 records, fields: url, html, fetched_at)
Output: poetrydaily_parsed.json
        poetrydaily_parse_drops.json   (records dropped with reasons)
        poetrydaily_parse_report.txt

Field shape matches ralp_parsed.json / slowdown_parsed.json where applicable.
"""

import html as html_lib
import json
import re
from pathlib import Path

INPUT_FILE  = "poetrydaily_raw.json"
OUTPUT_FILE = "poetrydaily_parsed.json"
DROPS_FILE  = "poetrydaily_parse_drops.json"
REPORT_FILE = "poetrydaily_parse_report.txt"

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

# Signals that a text-editor block is editorial commentary or boilerplate, not poem text.
_EDITORIAL_SIGNALS = (
    "Inspired by ",
    "Poems to Read",
    "Read editor",
    "staff readers",
    "Read poems by selecting",
    "Poetry Daily Depends",
    "University Drive",
    # Copyright / permission blocks
    "All rights reserved",
    "Reproduced by Poetry Daily",
    "Reprinted with permission",
    "Reprinted by permission",
)


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def inner_text(html_fragment: str) -> str:
    """Strip tags, decode entities, collapse internal whitespace."""
    t = re.sub(r"<[^>]+>", "", html_fragment)
    t = html_lib.unescape(t)
    return t.strip()


def find_shortcode_content(html: str, css_class: str) -> str:
    """Return text content of the elementor-shortcode div inside the element
    whose class list contains css_class. Returns '' if not found."""
    idx = html.find(css_class)
    if idx < 0:
        return ""
    block = html[idx : idx + 600]
    m = re.search(r'elementor-shortcode">(.*?)</div>', block, re.DOTALL)
    if not m:
        return ""
    return inner_text(m.group(1))


def fallback_text_from_html(raw_html: str) -> str:
    """Generic HTML-to-poem-text: br->newline, /p->double-newline, strip tags."""
    text = raw_html
    text = re.sub(r"<br\s*/?>", "\n", text)
    text = re.sub(r"</p>", "\n\n", text)
    text = re.sub(r"<p[^>]*>", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    # Strip any unclosed/partial HTML tag at end (block boundary may cut mid-tag,
    # leaving "<div class=..." with no closing >, which regex above won't catch).
    text = re.sub(r"<[^>]*$", "", text)
    text = html_lib.unescape(text)
    # Replace HTML non-breaking space entities and the U+00A0 code point with space.
    text = re.sub(r"&nbsp;|&#160;| ", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Title
# ---------------------------------------------------------------------------

def extract_title(html: str) -> str:
    # og:title has spaces around = on this site
    m = (
        re.search(
            r'<meta[^>]*property\s*=\s*["\']og:title["\']\s*content\s*=\s*["\']([^"\']+)',
            html,
        )
        or re.search(
            r'<meta[^>]*content\s*=\s*["\']([^"\']+)["\']\s*property\s*=\s*["\']og:title',
            html,
        )
        or re.search(
            r'property\s*=\s*["\'\s]*og:title["\'\s]*[^>]*content\s*=\s*["\']([^"\']+)',
            html,
        )
    )
    if not m:
        return ""
    title = html_lib.unescape(m.group(1))
    # Strip site suffix variants: " -- Poetry Daily", " - Poetry Daily", " | Poetry Daily"
    title = re.sub(r"\s*[-–—|]+\s*Poetry Daily\s*$", "", title, flags=re.IGNORECASE).strip()
    return title


# ---------------------------------------------------------------------------
# Published date
# ---------------------------------------------------------------------------

def extract_date(html: str) -> str:
    """Parse <time>Month DD, YYYY</time> -> 'YYYY-MM-DD'."""
    m = re.search(r"<time>([^<]+)</time>", html)
    if not m:
        return ""
    raw = m.group(1).strip()  # "January 17, 2023"
    parts = re.match(r"(\w+)\s+(\d+),\s+(\d{4})", raw)
    if not parts:
        return ""
    month_str, day_str, year_str = parts.group(1), parts.group(2), parts.group(3)
    month = MONTH_MAP.get(month_str.lower())
    if not month:
        return ""
    return f"{year_str}-{month:02d}-{int(day_str):02d}"


# ---------------------------------------------------------------------------
# Poet name
# ---------------------------------------------------------------------------

def extract_poet(html: str) -> str:
    return find_shortcode_content(html, "daily_poem_author")


# ---------------------------------------------------------------------------
# Poem text
# ---------------------------------------------------------------------------

def extract_poem_text(html: str) -> str:
    poem_idx = html.find('id="daily-poem"')
    if poem_idx < 0:
        return ""

    # Some pages embed a full nested Elementor document inside id=daily-poem.
    # Detect by presence of data-elementor-type="wp-post" within the next 500 chars.
    if 'data-elementor-type="wp-post"' in html[poem_idx : poem_idx + 500]:
        return _extract_nested_elementor(html, poem_idx)

    # Isolate this widget's content up to the next OUTER widget declaration.
    # The widget's own data-widget_type= attribute is within the first 100 chars,
    # so starting the search at poem_idx + 100 skips it.
    widget_end = html.find("data-widget_type=", poem_idx + 100)
    block = html[poem_idx : widget_end if widget_end > 0 else poem_idx + 20000]

    inner_m = re.search(r'elementor-widget-container">(.*)', block, re.DOTALL)
    if not inner_m:
        return ""
    inner = inner_m.group(1)

    # Strip editorial footnotes injected into the poem body as <small> blocks.
    # Typical pattern: <p ...>&nbsp;<br /><small><em>National Poetry Month...</em></small></p>
    inner = re.sub(r"<p[^>]*>[^<]*(?:<br\s*/?>)?[^<]*<small>.*?</small>[^<]*</p>", "", inner, flags=re.DOTALL)
    inner = re.sub(r"<small>.*?</small>", "", inner, flags=re.DOTALL)

    # --- Pass 1: excerpt_line spans (primary format, ~85% of records) ---
    spans = re.findall(r'<span class = "excerpt_line">(.*?)</span>', inner, re.DOTALL)
    if spans:
        lines = []
        for span in spans:
            # Replace HTML non-breaking space entities with regular space (preserves indentation)
            line = re.sub(r"&nbsp;|&#160;| ", " ", span)
            line = re.sub(r"<[^>]+>", "", line)
            line = html_lib.unescape(line)
            line = line.rstrip()  # keep leading spaces, strip trailing
            lines.append(line)
        # Drop trailing blank lines only
        while lines and not lines[-1].strip():
            lines.pop()
        return "\n".join(lines)

    # --- Pass 2: general fallback (br-separated, p-separated, div text) ---
    # <table> layouts return "" so the caller can log a drop.
    if "<table" in inner:
        return ""

    return fallback_text_from_html(inner)


def _extract_nested_elementor(html: str, poem_idx: int) -> str:
    """Handle pages where id=daily-poem wraps a nested Elementor wp-post document.
    Collects content from text-editor.default widgets, skipping editorial blocks."""
    # Use a generous 40K window -- nested Elementor posts can be long.
    window = html[poem_idx : poem_idx + 40_000]

    parts = []
    for m in re.finditer(r'data-widget_type="text-editor\.default"', window):
        block = window[m.start() : m.start() + 8000]
        inner = re.search(r'elementor-widget-container">(.*?)</div>\s*</div>', block, re.DOTALL)
        if not inner:
            continue
        content = inner.group(1)
        stripped = re.sub(r"<[^>]+>", "", content).strip()
        # Skip empty or known non-poem blocks
        if not stripped or len(stripped) < 10:
            continue
        if any(sig in stripped for sig in _EDITORIAL_SIGNALS):
            continue
        text = fallback_text_from_html(content)
        if text:
            parts.append(text)

    return "\n\n".join(parts) if parts else ""


# ---------------------------------------------------------------------------
# Copyright block
# ---------------------------------------------------------------------------

def extract_copyright_block(html: str) -> str:
    """Return plain text of the text-editor widget that contains a copyright symbol."""
    for m in re.finditer(r'data-widget_type="text-editor\.default"', html):
        block = html[m.start() : m.start() + 2000]
        inner = re.search(
            r'elementor-widget-container">(.*?)</div>\s*</div>', block, re.DOTALL
        )
        if not inner:
            continue
        t = re.sub(r"<[^>]+>", " ", inner.group(1))
        t = html_lib.unescape(t)
        t = re.sub(r"\s+", " ", t).strip()
        if "©" in t or "&copy;" in t:
            return t
    return ""


# ---------------------------------------------------------------------------
# Source metadata from copyright block
# ---------------------------------------------------------------------------

def extract_source_year(copyright_text: str) -> str | None:
    m = re.search(r"©\s*(\d{4})", copyright_text)
    return m.group(1) if m else None


def extract_publisher(copyright_text: str) -> str | None:
    # "Published by X ..." -- stop at year, "on ", "in [Month]", period, or copyright symbol
    m = re.search(
        r"Published by ([^\d.©]+?)(?=\s+(?:\d{4}|on\s|in\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))|[.,](?:\s|$)|\s*©|\.$)",
        copyright_text,
        re.IGNORECASE,
    )
    if m:
        pub = m.group(1).strip().rstrip(",")
        if len(pub) > 3:
            return pub
    # "(Publisher Name)" parenthetical format
    m = re.search(
        r"\(([^)]{5,60}(?:Press|Books|Publications|University|House|Publishing)[^)]*)\)",
        copyright_text,
    )
    if m:
        return m.group(1).strip()
    # "permission of X" (handles "Reprinted by permission of X", "with permission of X")
    m = re.search(r"permission of ([^.]+?)(?:\.|All rights|$)", copyright_text)
    if m:
        pub = m.group(1).strip()
        # Trim trailing city/state noise: "Publisher, Minneapolis, Minnesota"
        pub = re.sub(r",\s+[A-Z][a-z]+,\s+[A-Z][a-z]+.*$", "", pub).strip()
        if len(pub) > 3:
            return pub
    return None


def extract_publication_type_value(html: str) -> str:
    """Return the human-readable source name from daily_poem_publication_type.
    Prefers aria-label (properly cased); falls back to link text or plain text."""
    idx = html.find("daily_poem_publication_type")
    if idx < 0:
        return ""
    block = html[idx : idx + 600]
    inner_m = re.search(r'elementor-shortcode">(.*?)</div>', block, re.DOTALL)
    if not inner_m:
        return ""
    inner = inner_m.group(1)

    # aria-label='...' or aria-label="..." (single quotes may be HTML-entity encoded)
    aria = re.search(r"aria-label\s*=\s*[\"'&](?:&#039;|')(.*?)(?:&#039;|')[\"']?\s*", inner)
    if not aria:
        aria = re.search(r'aria-label\s*=\s*["\']([^"\']+)["\']', inner)
    if aria:
        return html_lib.unescape(aria.group(1)).strip()

    # fallback: link text
    link_text = re.search(r"<a[^>]*>(.*?)</a>", inner, re.DOTALL)
    if link_text:
        return inner_text(link_text.group(1))

    return inner_text(inner)


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------

class ParseDrop(Exception):
    pass


def parse_record(rec: dict) -> dict | None:
    """Return parsed dict or raises ParseDrop on unrecoverable problems."""
    url  = rec["url"]
    html = rec["html"]

    # --- Page-type guard ---
    body_class_m = re.search(r'<body[^>]*class="([^"]+)"', html)
    body_class = body_class_m.group(1) if body_class_m else ""
    if "single-daily_poem" not in body_class:
        raise ParseDrop("not a daily_poem post type")

    title      = extract_title(html)
    date       = extract_date(html)
    poet       = extract_poet(html)
    poem_text  = extract_poem_text(html)
    copyright  = extract_copyright_block(html)
    pub_value  = extract_publication_type_value(html)
    year       = extract_source_year(copyright) if copyright else None
    publisher  = extract_publisher(copyright) if copyright else None

    # Drop table/visual layouts where poem text was not extractable
    poem_idx = html.find('id="daily-poem"')
    if poem_idx >= 0:
        widget_end = html.find("data-widget_type=", poem_idx + 100)
        block = html[poem_idx : widget_end if widget_end > 0 else poem_idx + 20000]
        if "<table" in block and not poem_text:
            raise ParseDrop("table/visual layout -- poem text not extractable")

    has_poem = bool(poem_text.strip()) if poem_text else False

    # Book vs journal: "from [BOOK]" in copyright text signals a book source
    is_book = bool(re.search(r"\bfrom\b", copyright, re.IGNORECASE)) if copyright else False
    source_book    = pub_value if is_book else None
    source_journal = pub_value if not is_book and pub_value else None

    return {
        "source_url":       url,
        "published_date":   date or None,
        "poem_title":       title or None,
        "poet_name":        poet or None,
        "poem_text":        poem_text or None,
        "source_book":      source_book,
        "source_journal":   source_journal,
        "source_publisher": publisher,
        "source_year":      year,
        "has_poem":         has_poem,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Poetry Daily parser")
    print("=" * 60)

    with open(INPUT_FILE) as f:
        data = json.load(f)
    print(f"Loaded {len(data)} records from {INPUT_FILE}")

    poems = []
    drops = []

    for i, rec in enumerate(data):
        url = rec.get("url", f"record_{i}")
        try:
            result = parse_record(rec)
            if result is not None:
                poems.append(result)
        except ParseDrop as e:
            title = ""
            try:
                title = extract_title(rec["html"])
            except Exception:
                pass
            drops.append({"url": url, "title": title, "reason": str(e)})

    # Save outputs
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(poems, f, indent=2, ensure_ascii=False)

    with open(DROPS_FILE, "w", encoding="utf-8") as f:
        json.dump(drops, f, indent=2, ensure_ascii=False)

    # Stats
    has_poem_count = sum(1 for p in poems if p["has_poem"])
    has_book       = sum(1 for p in poems if p["source_book"])
    has_journal    = sum(1 for p in poems if p["source_journal"])
    no_source      = sum(1 for p in poems if not p["source_book"] and not p["source_journal"])
    has_year       = sum(1 for p in poems if p["source_year"])
    has_publisher  = sum(1 for p in poems if p["source_publisher"])
    no_title       = sum(1 for p in poems if not p["poem_title"])
    no_date        = sum(1 for p in poems if not p["published_date"])

    report_lines = [
        "=" * 60,
        "Poetry Daily parse report",
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
        f"missing published_date:   {no_date}",
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
            f"  date:   {p['published_date']}",
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
