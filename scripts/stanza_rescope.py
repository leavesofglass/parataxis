"""
stanza_rescope.py — scope re-fetch candidates for corpus=null poems missing
stanza breaks. Read-only: fetches from Wikisource / Gutenberg / poets.org
and writes a report. Never modifies the DB.

Usage:
  python scripts/stanza_rescope.py             # all 98 candidates
  python scripts/stanza_rescope.py --limit 10  # quick smoke test

Output:
  scripts/stanza_rescope_cache/<poem_id>.json   # per-poem fetch cache
  scripts/stanza_rescope_report.json            # machine-readable summary
  scripts/stanza_rescope_report.txt             # human-readable table
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import requests
from supabase import create_client

# ── Config ────────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / "app" / ".env.local"
CACHE_DIR = Path(__file__).resolve().parent / "stanza_rescope_cache"
REPORT_JSON = Path(__file__).resolve().parent / "stanza_rescope_report.json"
REPORT_TXT = Path(__file__).resolve().parent / "stanza_rescope_report.txt"

UA = "poetry-app stanza-rescope (contact: notmattsiegel@gmail.com)"
HEADERS = {"User-Agent": UA}
SLEEP_BETWEEN = 0.6  # be polite to APIs

WIKISOURCE_API = "https://en.wikisource.org/w/api.php"
GUTENDEX = "https://gutendex.com/books"
POETS_ORG_SEARCH = "https://poets.org/search"


# ── Env / Supabase ────────────────────────────────────────────────────────────

def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def sb_client():
    env = load_env()
    return create_client(
        env["NEXT_PUBLIC_SUPABASE_URL"],
        env["SUPABASE_SERVICE_ROLE_KEY"],
    )


# ── Text normalization ────────────────────────────────────────────────────────

_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")


def norm_line(s: str) -> str:
    """Aggressive line normalization for matching."""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii")
    s = s.lower()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def split_lines_flat(body: str) -> list[str]:
    """Non-empty lines only, in order."""
    return [ln.strip() for ln in body.split("\n") if ln.strip()]


def split_lines_with_blanks(body: str) -> list[str]:
    """All lines, preserving blanks (as empty strings), stripped."""
    return [ln.strip() for ln in body.split("\n")]


def has_stanza_breaks(body: str) -> bool:
    return "\n\n" in body


# ── Matching ──────────────────────────────────────────────────────────────────

@dataclass
class MatchResult:
    matched: bool           # true = strict match, safe to overwrite body
    near_match: bool        # true = same poem, same line count, but edition differs
    ratio: float
    stored_lines: int
    fetched_lines: int      # after blank-strip
    fetched_has_breaks: bool
    reason: str = ""


def compare(stored_body: str, fetched_body: str) -> MatchResult:
    stored = [norm_line(ln) for ln in split_lines_flat(stored_body)]
    fetched_flat = split_lines_flat(fetched_body)
    fetched_norm = [norm_line(ln) for ln in fetched_flat]
    has_breaks = has_stanza_breaks(fetched_body)

    if not fetched_norm:
        return MatchResult(False, False, 0.0, len(stored), 0, has_breaks, "empty fetched")

    ratio = difflib.SequenceMatcher(None, stored, fetched_norm).ratio()
    line_delta = abs(len(stored) - len(fetched_norm))

    # Strict: safe to overwrite. Line count identical (or ±1) and high content match.
    strict = line_delta <= 1 and ratio >= 0.92
    # Near: same poem, same length, but wording drift (edition variance).
    #   Line count MUST match exactly (or ±1) so stanza-break positions transplant.
    #   Low ratio bar because 18C/19C editions differ heavily on punctuation, capitalization,
    #   contractions ("bereav'd" vs "bereaved"), and archaic ampersand vs "and".
    near = (not strict) and line_delta <= 1 and ratio >= 0.55

    if strict:
        reason = "ok"
    elif near:
        reason = f"near (r={ratio:.3f}, lines {len(stored)}={len(fetched_norm)}) — edition drift"
    elif line_delta > 1:
        reason = f"line-count differs by {line_delta}"
    else:
        reason = f"ratio {ratio:.3f} below 0.55"

    return MatchResult(
        strict, near, ratio, len(stored), len(fetched_norm), has_breaks, reason,
    )


# ── Wikisource ────────────────────────────────────────────────────────────────

def _clean_title(t: str) -> str:
    # e.g. "The Snake." → "The Snake"
    return t.strip().rstrip(".").strip()


def wikisource_search(title: str, author: str) -> list[str]:
    """Return candidate page titles (namespace 0), plus direct-page guesses."""
    t_clean = _clean_title(title)
    last = author.strip().split()[-1] if author.strip() else ""
    # Direct-page guesses (checked as high-priority candidates)
    guesses = [
        t_clean,                    # "The Tyger"
        f"{t_clean} ({last})",      # "The Tyger (Blake)"
    ]
    queries = [
        f'"{t_clean}" {author}',
        f'{t_clean} {author}',
        t_clean,
    ]
    seen: list[str] = []
    # Direct guesses go first; they may 404 but html_to_poem handles that gracefully.
    for g in guesses:
        if g and g not in seen:
            seen.append(g)
    for q in queries:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": q,
            "srlimit": "8",
            "srnamespace": "0",
            "format": "json",
        }
        try:
            r = requests.get(WIKISOURCE_API, params=params, headers=HEADERS, timeout=20)
            r.raise_for_status()
            hits = r.json().get("query", {}).get("search", [])
            for h in hits:
                t = h.get("title", "")
                if t and t not in seen:
                    seen.append(t)
        except Exception:
            continue
        if len(seen) > 6:  # stop early once we have enough
            break
        time.sleep(SLEEP_BETWEEN)
    return seen


def wikisource_fetch_text(page_title: str) -> Optional[str]:
    """Fetch parsed page, extract plain-text poem lines with stanza breaks.
    Follows redirects transparently via the ``redirects=1`` parameter.
    """
    params = {
        "action": "parse",
        "page": page_title,
        "prop": "text",
        "format": "json",
        "formatversion": "2",
        "disableeditsection": "1",
        "disabletoc": "1",
        "redirects": "1",  # follow "Ulysses (Tennyson)" → "Poems (Tennyson, 1843)/Volume 2/Ulysses"
    }
    try:
        r = requests.get(WIKISOURCE_API, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None

    html = data.get("parse", {}).get("text")
    if not html:
        return None
    # Resolved page title (after redirect) — used for title-line stripping
    resolved = data.get("parse", {}).get("title") or page_title
    return html_to_poem(html, page_title=resolved)


_NOISE_SELECTORS = [
    "style", "script",
    ".ws-header", ".wst-header", ".ws-noexport", ".noprint",
    ".similar", ".navigation-not-searchable",
    "sup.reference", ".reference", ".mw-editsection",
    ".wst-gap",  # decorative indentation spacer
    ".authority-control", "table.header-notes",
    ".dynlayout-exempt", ".licenseContainer",
    "#ws-data",
    ".ws-pagenum",  # ProofreadPage inline page number markers
    ".pagenum",
]

_POEM_CONTAINER_SELECTORS = [
    "div.poem",
    "div.verse",
    "div.wst-block-center",
    "div.wst-verse",
    "div.wst-block",
]

# Lines that look like structural headings, not body content.
_HEADING_PATTERNS = [
    re.compile(r"^[IVXLCDM]+\.?$"),                              # I, II, III, IV
    re.compile(r"^\d+\.?$"),                                     # 1, 2, 10
    re.compile(r"^\d+$"),                                        # bare line-number
    re.compile(r"^Layout\s*\d+$", re.I),                         # "Layout 2" gadget artifact
    re.compile(r"^Contents$", re.I),
    re.compile(r"^Notes?$", re.I),
]


def html_to_poem(html: str, page_title: str = "") -> Optional[str]:
    """Extract stanza-broken plaintext from Wikisource HTML.

    Handles these template families:
      • Modern ProofreadPage: <div class="ws-poem-stanza"> with <span class="ws-poem-line">
      • Classic .poem / .verse / .wst-block-center wrappers with <br> line breaks
      • Plain <p> stanzas with <br> line breaks (older transcripts)
      • Per-<p>-line layout: each <p> holds a single line, empty <p> = stanza break
    """
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return _html_to_poem_regex(html)

    soup = BeautifulSoup(html, "html.parser")

    # Strip navigation, headers, footnotes, decorative spacers
    for sel in _NOISE_SELECTORS:
        for el in soup.select(sel):
            el.decompose()

    root = soup.find("div", class_="mw-parser-output") or soup

    poem: Optional[str] = None

    # ── Attempt 1: Modern ProofreadPage ws-poem-* markup ──────────────────
    stanzas = _extract_ws_poem_markup(root)
    if stanzas:
        poem = "\n\n".join(stanzas)

    # ── Attempt 2: Classic poem containers ────────────────────────────────
    if not poem:
        containers: list = []
        for sel in _POEM_CONTAINER_SELECTORS:
            found = root.select(sel)
            if found:
                containers = found
                break
        if containers:
            ps: list = []
            for c in containers:
                inner_ps = c.find_all("p")
                if inner_ps:
                    ps.extend(inner_ps)
                else:
                    ps.append(c)
            stanzas = [t for t in (_extract_stanza_text(p) for p in ps) if t and t.strip()]
            if stanzas:
                poem = "\n\n".join(stanzas)

    # ── Attempt 3: Per-<p>-line layout (single line per <p>, blank <p> = break) ─
    if not poem:
        top_ps = _top_level_ps(root)
        if _looks_like_per_p_line_layout(top_ps):
            poem = _extract_per_p_line(top_ps)

    # ── Attempt 4: Fallback — treat each <p> as a stanza ──────────────────
    if not poem:
        ps = root.find_all("p", recursive=False)
        if not ps:
            ps = root.find_all("p")
        stanzas = [t for t in (_extract_stanza_text(p) for p in ps) if t and t.strip()]
        if stanzas:
            poem = "\n\n".join(stanzas)

    if not poem:
        return None

    poem = _strip_editorial(poem)
    poem = _filter_heading_lines(poem)
    poem = _strip_inline_line_numbers(poem)
    poem = _drop_title_line(poem, page_title)
    return poem if poem.strip() else None


def _extract_ws_poem_markup(root) -> list[str]:
    """Return list of stanza strings using ws-poem-stanza / ws-poem-line markup."""
    stanzas: list[str] = []
    for stanza_el in root.select("div.ws-poem-stanza"):
        lines: list[str] = []
        line_els = stanza_el.select("span.ws-poem-line")
        if line_els:
            for ln_el in line_els:
                # Strip break markers before pulling text
                for br in ln_el.select("span.ws-poem-break"):
                    br.decompose()
                # Drop page-number spans only — drop-cap wrappers hold the initial
                # letter of the line, so their text content must be preserved.
                for junk in ln_el.select(".ws-pagenum, .pagenum"):
                    junk.decompose()
                text = ln_el.get_text().strip()
                text = _WS_RE.sub(" ", text)
                if text:
                    lines.append(text)
        else:
            # Fallback: extract text of whole stanza, split by <br>
            lines = _extract_stanza_text(stanza_el).split("\n")
            lines = [l.strip() for l in lines if l.strip()]
        if lines:
            stanzas.append("\n".join(lines))
    return stanzas


def _top_level_ps(root) -> list:
    """All <p> children directly under root (skip <p> nested in other blocks)."""
    return [c for c in root.children if getattr(c, "name", None) == "p"]


def _looks_like_per_p_line_layout(ps: list) -> bool:
    """Heuristic: many bare <p> siblings, most containing a single short line."""
    if len(ps) < 8:
        return False
    single_line_count = 0
    for p in ps:
        text = p.get_text("\n").strip()
        if not text:
            single_line_count += 1  # blank <p> — potential stanza break
            continue
        # If <p> contains multiple non-empty lines, it's a stanza, not a per-line layout
        real_lines = [l for l in text.split("\n") if l.strip()]
        if len(real_lines) == 1 and len(real_lines[0]) < 120:
            single_line_count += 1
    return single_line_count >= 0.85 * len(ps)


def _extract_per_p_line(ps: list) -> str:
    """Convert per-<p>-line layout into stanza-broken text."""
    stanzas: list[list[str]] = [[]]
    for p in ps:
        text = p.get_text("\n").strip()
        text = _WS_RE.sub(" ", text)
        if not text:
            if stanzas[-1]:  # blank <p> ends a stanza
                stanzas.append([])
            continue
        stanzas[-1].append(text)
    stanzas = [s for s in stanzas if s]
    return "\n\n".join("\n".join(s) for s in stanzas)


def _filter_heading_lines(poem: str) -> str:
    """Drop lone lines that match structural-heading patterns (roman numerals,
    bare line numbers, 'Contents', 'Notes', 'Layout N')."""
    out_lines: list[str] = []
    for ln in poem.split("\n"):
        stripped = ln.strip()
        if any(pat.fullmatch(stripped) for pat in _HEADING_PATTERNS):
            continue
        out_lines.append(ln)
    text = "\n".join(out_lines)
    # Collapse any resulting triple-blank runs
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _strip_inline_line_numbers(poem: str) -> str:
    """Strip trailing digit-runs that were fused to a line's tail
    (Wikisource inline line-number markers like '...Quiet by day10')."""
    out_lines: list[str] = []
    for ln in poem.split("\n"):
        # Only strip if line has letters before the digits (avoid killing "1863")
        stripped = re.sub(r"([A-Za-z,.;:!?)\]'])\s*(\d{1,3})\s*$", r"\1", ln)
        out_lines.append(stripped)
    return "\n".join(out_lines)


def _extract_stanza_text(node) -> str:
    """Given a <p> (or block) element, return its text with <br> as \\n."""
    try:
        from bs4 import NavigableString, Tag
    except Exception:
        return node.get_text()
    parts: list[str] = []
    for child in node.descendants:
        # We walk descendants but only capture text nodes and <br>.
        if isinstance(child, NavigableString):
            # Skip text that's inside a script/style (already removed) — safe here.
            parts.append(str(child))
        elif isinstance(child, Tag) and child.name == "br":
            parts.append("\n")
    text = "".join(parts)
    # Normalize per-line: collapse internal whitespace, strip
    out_lines = []
    for ln in text.split("\n"):
        ln = re.sub(r"[ \t]+", " ", ln).strip()
        if ln:
            out_lines.append(ln)
    return "\n".join(out_lines)


def _drop_title_line(poem: str, page_title: str) -> str:
    """If the first line matches the page title (or its last path component),
    drop it — it's a heading, not the first line of the poem."""
    if not poem:
        return poem
    first, _, rest = poem.partition("\n")
    candidates = [page_title, page_title.split("/")[-1] if page_title else ""]
    first_norm = norm_line(first)
    for c in candidates:
        if c and first_norm == norm_line(c):
            return rest.lstrip("\n")
    return poem


def _html_to_poem_regex(html: str) -> Optional[str]:
    m = re.search(r'<div[^>]*class="[^"]*poem[^"]*"[^>]*>(.*?)</div>', html, re.S | re.I)
    if not m:
        return None
    inner = m.group(1)
    inner = re.sub(r"<br\s*/?>", "\n", inner, flags=re.I)
    inner = re.sub(r"</?p[^>]*>", "\n\n", inner, flags=re.I)
    inner = re.sub(r"<[^>]+>", "", inner)
    import html as htmllib
    inner = htmllib.unescape(inner)
    return _strip_editorial(inner)


def _strip_editorial(text: str) -> str:
    """Drop bracketed footnote markers and leading/trailing editorial notes."""
    text = re.sub(r"\[\s*\d+\s*\]", "", text)  # footnote markers like [1]
    # collapse >2 newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Gutenberg (via gutendex) ──────────────────────────────────────────────────

_GUTEN_CACHE: dict[str, str] = {}  # author -> concatenated text of top book(s)


def gutendex_texts_for_author(author: str) -> list[tuple[str, str]]:
    """Return list of (book_title, text) for top-ranked books by author."""
    if author in _GUTEN_CACHE:
        return _GUTEN_CACHE[author]  # type: ignore

    out: list[tuple[str, str]] = []
    try:
        r = requests.get(
            GUTENDEX, params={"search": author, "languages": "en"},
            headers=HEADERS, timeout=20,
        )
        r.raise_for_status()
        books = r.json().get("results", [])[:5]
    except Exception:
        _GUTEN_CACHE[author] = []
        return []

    for b in books:
        # Filter books whose author list actually contains our person
        authors = " ".join(a.get("name", "") for a in b.get("authors", []))
        if not _author_matches(author, authors):
            continue
        formats = b.get("formats", {})
        url = (
            formats.get("text/plain; charset=utf-8")
            or formats.get("text/plain; charset=us-ascii")
            or formats.get("text/plain")
        )
        if not url:
            continue
        try:
            resp = requests.get(url, headers=HEADERS, timeout=45)
            resp.raise_for_status()
            out.append((b.get("title", ""), resp.text))
            time.sleep(SLEEP_BETWEEN)
        except Exception:
            continue
        if len(out) >= 3:
            break

    _GUTEN_CACHE[author] = out
    return out


def _author_matches(query_name: str, candidate: str) -> bool:
    q = set(w.lower() for w in re.findall(r"\w+", query_name) if len(w) > 2)
    c = set(w.lower() for w in re.findall(r"\w+", candidate))
    return bool(q) and len(q & c) >= min(2, len(q))


def gutenberg_find_poem(title: str, author: str) -> Optional[str]:
    title_clean = _clean_title(title)
    for _book_title, text in gutendex_texts_for_author(author):
        chunk = _extract_by_title(text, title_clean)
        if chunk:
            return chunk
    return None


def _extract_by_title(book_text: str, title: str) -> Optional[str]:
    """Locate a poem title in a book text and pull lines until next title/heading.

    Heuristics: the title usually appears on its own line (often uppercase),
    followed by the poem, then a blank line and another heading (uppercase
    line, or 'ROMAN' numeral, or another title-cased short line).
    """
    lines = book_text.splitlines()
    tnorm = norm_line(title)
    if not tnorm:
        return None

    # Find candidate title lines
    for idx, ln in enumerate(lines):
        if norm_line(ln) == tnorm:
            # Skip to first non-blank after title
            j = idx + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            start = j
            # Read until we hit what looks like the next heading or end marker
            body_lines: list[str] = []
            blank_run = 0
            while j < len(lines):
                cur = lines[j]
                stripped = cur.strip()
                if not stripped:
                    blank_run += 1
                    body_lines.append("")
                    # Two blank lines usually separate poems in Gutenberg
                    if blank_run >= 2:
                        # Peek next non-blank; if it looks like a heading, stop
                        k = j + 1
                        while k < len(lines) and not lines[k].strip():
                            k += 1
                        if k >= len(lines) or _looks_like_heading(lines[k]):
                            break
                    j += 1
                    continue
                blank_run = 0
                # End markers
                if re.match(r"\*\*\*\s*END OF", cur):
                    break
                body_lines.append(cur)
                j += 1
                if len(body_lines) > 400:  # sanity limit
                    break
            body = "\n".join(body_lines).strip("\n")
            body = re.sub(r"\n{3,}", "\n\n", body)
            if body.strip():
                return body
    return None


def _looks_like_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 80:
        return False
    # All-uppercase heading, or roman numeral, or very short titlecase
    if s.isupper():
        return True
    if re.fullmatch(r"[IVXLCM]+\.?", s):
        return True
    if re.fullmatch(r"[IVXLCM]+\s*[.:-]?\s*.{0,60}", s) and s.split()[0].isupper():
        return True
    # Short title-cased line ending without terminal punctuation — very likely a title
    if (
        len(s) <= 60
        and not s.endswith((".", ",", ";", ":", "!", "?"))
        and s[0].isupper()
        and sum(1 for w in s.split() if w[:1].isupper()) >= max(1, len(s.split()) // 2)
    ):
        return True
    return False


# ── poets.org ─────────────────────────────────────────────────────────────────

def poets_org_find_poem(title: str, author: str) -> Optional[str]:
    """Search poets.org for the poem and extract the body."""
    q = quote(f"{_clean_title(title)} {author}")
    try:
        r = requests.get(f"{POETS_ORG_SEARCH}?query={q}", headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception:
        return None
    # Find first /poem/... link
    m = re.search(r'href="(/poem/[^"]+)"', r.text)
    if not m:
        return None
    url = "https://poets.org" + m.group(1)
    time.sleep(SLEEP_BETWEEN)
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception:
        return None
    return _poets_org_extract(r.text)


def _poets_org_extract(html: str) -> Optional[str]:
    try:
        from bs4 import BeautifulSoup
    except Exception:
        return None
    soup = BeautifulSoup(html, "html.parser")
    # The poem body sits in a .card__text or .poem__body — try several selectors
    for sel in [
        "div.poem__body",
        "div.card__text",
        "div.text--long",
        "article .poem",
        "div[class*='poem'] div[class*='body']",
    ]:
        el = soup.select_one(sel)
        if el:
            for br in el.find_all("br"):
                br.replace_with("\n")
            for p in el.find_all("p"):
                # Ensure paragraph boundaries become stanza breaks
                p.insert_after(soup.new_string("\n\n"))
            text = el.get_text()
            text = re.sub(r"\n{3,}", "\n\n", text).strip()
            if text.count("\n") >= 3:
                return text
    return None


# ── Orchestration ─────────────────────────────────────────────────────────────

@dataclass
class PoemFetch:
    id: str
    title: str
    author: str
    stored_line_count: int
    source: Optional[str] = None  # 'wikisource' | 'gutenberg' | 'poets.org'
    source_ref: Optional[str] = None
    fetched_body: Optional[str] = None
    match: Optional[dict] = None
    category: str = "NOT_FOUND"
    note: str = ""
    all_attempts: list[dict] = field(default_factory=list)


def evaluate(stored: dict) -> PoemFetch:
    pf = PoemFetch(
        id=stored["id"],
        title=stored["title"],
        author=stored["author"],
        stored_line_count=stored["line_count"],
    )

    def try_source(name: str, body: Optional[str], ref: str) -> Optional[MatchResult]:
        if not body:
            pf.all_attempts.append({"source": name, "ref": ref, "outcome": "no-text"})
            return None
        m = compare(stored["body"], body)
        pf.all_attempts.append({
            "source": name, "ref": ref,
            "ratio": round(m.ratio, 3), "fetched_lines": m.fetched_lines,
            "has_breaks": m.fetched_has_breaks,
            "matched": m.matched, "near_match": m.near_match, "reason": m.reason,
        })
        return m

    def adopt(name: str, ref: str, body: str, m: MatchResult) -> None:
        pf.source = name
        pf.source_ref = ref
        pf.fetched_body = body
        pf.match = asdict(m)

    # Try all Wikisource candidates; adopt strict match, keep best near-match.
    best_near: tuple[float, str, str, str, MatchResult] | None = None  # (ratio, name, ref, body, m)

    for page_title in wikisource_search(stored["title"], stored["author"])[:8]:
        body = wikisource_fetch_text(page_title)
        time.sleep(SLEEP_BETWEEN)
        m = try_source("wikisource", body, page_title)
        if not m:
            continue
        if m.matched:
            adopt("wikisource", page_title, body, m)
            break
        if m.near_match and (best_near is None or m.ratio > best_near[0]):
            best_near = (m.ratio, "wikisource", page_title, body, m)

    if not pf.fetched_body:
        body = gutenberg_find_poem(stored["title"], stored["author"])
        m = try_source("gutenberg", body, stored["author"])
        if m and m.matched:
            adopt("gutenberg", stored["author"], body, m)
        elif m and m.near_match and (best_near is None or m.ratio > best_near[0]):
            best_near = (m.ratio, "gutenberg", stored["author"], body, m)

    if not pf.fetched_body:
        body = poets_org_find_poem(stored["title"], stored["author"])
        m = try_source("poets.org", body, "search")
        if m and m.matched:
            adopt("poets.org", "search", body, m)
        elif m and m.near_match and (best_near is None or m.ratio > best_near[0]):
            best_near = (m.ratio, "poets.org", "search", body, m)

    # If no strict match but a near-match exists, adopt it as NEAR
    if not pf.fetched_body and best_near:
        _r, name, ref, body, m = best_near
        adopt(name, ref, body, m)
        # keep m.match for categorization below

    # Categorize
    if not pf.fetched_body:
        any_found = any(a.get("fetched_lines", 0) > 0 for a in pf.all_attempts)
        pf.category = "FOUND_MISMATCH" if any_found else "NOT_FOUND"
        if pf.category == "FOUND_MISMATCH":
            best = max(pf.all_attempts, key=lambda a: a.get("ratio", 0))
            pf.note = f"best {best['source']} ratio {best.get('ratio')} ({best.get('reason')})"
    else:
        assert pf.match
        if pf.match["matched"]:
            pf.category = "FOUND_WITH_STANZAS" if pf.match["fetched_has_breaks"] else "FOUND_NO_STANZAS"
        else:
            # near-match — same poem, edition differs
            pf.category = "FOUND_NEAR_WITH_STANZAS" if pf.match["fetched_has_breaks"] else "FOUND_NEAR_NO_STANZAS"

    return pf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="only process first N candidates")
    ap.add_argument("--only", type=str, default="", help="comma-sep poem ids to process only")
    ap.add_argument("--fresh", action="store_true", help="ignore cache")
    args = ap.parse_args()

    CACHE_DIR.mkdir(exist_ok=True)
    sb = sb_client()

    rows = (
        sb.table("poems")
        .select("id, title, author, line_count, body")
        .is_("corpus", "null")
        .gte("line_count", 20)
        .order("id")
        .execute()
        .data
    )
    candidates = [r for r in rows if "\n\n" not in r["body"]]
    print(f"loaded {len(candidates)} candidates (of {len(rows)} corpus=null line>=20)")

    if args.only:
        want = set(args.only.split(","))
        candidates = [r for r in candidates if r["id"] in want]
    elif args.limit:
        candidates = candidates[: args.limit]

    results: list[PoemFetch] = []
    for i, row in enumerate(candidates, 1):
        cache_file = CACHE_DIR / f"{row['id']}.json"
        if cache_file.exists() and not args.fresh:
            data = json.loads(cache_file.read_text())
            pf = PoemFetch(**{k: v for k, v in data.items()})
        else:
            print(f"[{i}/{len(candidates)}] {row['id']}  {row['author'][:25]} — {row['title'][:50]}")
            pf = evaluate(row)
            cache_file.write_text(json.dumps(asdict(pf), indent=2))
            time.sleep(SLEEP_BETWEEN)

        print(f"    → {pf.category}  {pf.source or '-'}  {pf.note or ''}")
        results.append(pf)

    write_report(results)


def write_report(results: list[PoemFetch]) -> None:
    counts: dict[str, int] = {}
    for r in results:
        counts[r.category] = counts.get(r.category, 0) + 1

    by_source: dict[str, int] = {}
    for r in results:
        if r.source:
            by_source[r.source] = by_source.get(r.source, 0) + 1

    summary = {
        "total_candidates": len(results),
        "by_category": counts,
        "by_source": by_source,
    }

    REPORT_JSON.write_text(json.dumps({
        "summary": summary,
        "results": [asdict(r) for r in results],
    }, indent=2))

    lines = [
        "STANZA-BREAK RE-FETCH SCOPING REPORT",
        "=" * 60,
        f"total candidates ............ {len(results)}",
        "",
        "by category:",
    ]
    for cat in [
        "FOUND_WITH_STANZAS", "FOUND_NO_STANZAS",
        "FOUND_NEAR_WITH_STANZAS", "FOUND_NEAR_NO_STANZAS",
        "FOUND_MISMATCH", "NOT_FOUND",
    ]:
        lines.append(f"  {cat:<26} {counts.get(cat, 0):>4}")
    lines += ["", "by source (of found+matched):"]
    for src, n in by_source.items():
        lines.append(f"  {src:<12} {n:>4}")

    for cat in [
        "FOUND_WITH_STANZAS", "FOUND_NO_STANZAS",
        "FOUND_NEAR_WITH_STANZAS", "FOUND_NEAR_NO_STANZAS",
        "FOUND_MISMATCH", "NOT_FOUND",
    ]:
        lines += ["", f"--- {cat} ---"]
        for r in results:
            if r.category == cat:
                extra = ""
                if r.match:
                    extra = (
                        f"  r={r.match['ratio']:.3f}  "
                        f"stanzas={'Y' if r.match['fetched_has_breaks'] else 'N'}  "
                        f"lines={r.match['stored_lines']}/{r.match['fetched_lines']}"
                    )
                elif r.note:
                    extra = f"  {r.note}"
                lines.append(
                    f"  {r.id}  {r.stored_line_count:>3}  {r.author[:22]:22} — {r.title[:44]:44}"
                    f"  [{r.source or '-'}]{extra}"
                )

    REPORT_TXT.write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines[:20]))
    print(f"\nfull report: {REPORT_TXT}")


if __name__ == "__main__":
    main()
