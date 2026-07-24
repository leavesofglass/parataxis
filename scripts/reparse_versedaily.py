"""
reparse_versedaily.py — Recover stanza breaks (and clean encoding) for Verse
Daily poems by re-parsing the raw Wayback HTML in versedaily_wayback_raw.json.

Rules learned from the raw markup (see prior investigation):
  * Every line ends with <br>              -> newline
  * A bare <p> between lines               -> stanza break (\\n\\n)
  * &nbsp; runs are hanging indents        -> collapsed to leading spaces
  * <i>/<em>                               -> <em> in body_html, stripped in body
  * <b>Roman-numeral heading</b>           -> own stanza (\\n\\n TEXT \\n\\n)
  * Numeric HTML entities (e.g. &#151;)    -> decoded
  * cp1252 bytes stored as U+0080-U+009F   -> mapped through cp1252 table
  * Trailing iframe / share widget / copy  -> cut

Writes to BOTH body and body_html for matched poems.  Poems not found in the
raw dump are skipped and logged.

Usage:
  python scripts/reparse_versedaily.py --dry-run
  python scripts/reparse_versedaily.py --write
"""

import bisect
import html as H
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS  = Path(__file__).parent
RAW_PATH = SCRIPTS / "versedaily_wayback_raw.json"

# ── cp1252 mapping ──────────────────────────────────────────────────────────
CP1252_MAP: dict[int, str] = {}
for _b in range(0x80, 0xA0):
    try:
        CP1252_MAP[_b] = bytes([_b]).decode("cp1252")
    except UnicodeDecodeError:
        pass

def fix_cp1252(s: str) -> str:
    if not s:
        return s
    out = []
    for ch in s:
        cp = ord(ch)
        if 0x80 <= cp <= 0x9F and cp in CP1252_MAP:
            out.append(CP1252_MAP[cp])
        else:
            out.append(ch)
    return "".join(out)

# ── env / supabase client ───────────────────────────────────────────────────
def _load_env() -> dict[str, str]:
    env_path = SCRIPTS.parent / "app" / ".env.local"
    values: dict[str, str] = {}
    try:
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    values[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return values

_env = _load_env()

def _get(env_key: str, file_key: str | None = None) -> str:
    return (
        os.environ.get(env_key, "").strip()
        or _env.get(file_key or env_key, "").strip()
    )

SUPABASE_URL = _get("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = _get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    sys.exit("ERROR: SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not found.")

try:
    from supabase import create_client
except ImportError:
    sys.exit("supabase package not found — pip install supabase")

# ── parser ──────────────────────────────────────────────────────────────────

NBSP = " "
BR_MARK = "\x01"   # placeholder for <br>
PP_MARK = "\x02"   # placeholder for <p> / section-header boundary
ROMAN_RE = re.compile(r"^\s*[IVXLCDM]+\.", re.IGNORECASE)

def _trim_trailing_junk(bq: str) -> str:
    """Cut Wayback iframe, twitter share, copyright, etc. from the poem region."""
    end_markers = [
        "<iframe",
        'class="twitter-share',
        "Copyright &copy;",
        "Copyright ©",
        "Reprinted by Verse Daily",
        "amazon.com/gp/product",
    ]
    cuts = [bq.find(m) for m in end_markers]
    cuts = [c for c in cuts if c > 0]
    if cuts:
        bq = bq[:min(cuts)]
    return bq

def _strip_title(bq: str) -> str:
    """Remove the leading <p><b>TITLE</b> header block."""
    m = re.search(r"</b>", bq, re.IGNORECASE)
    if m and m.start() < 800:
        bq = bq[m.end():]
    return bq

def _to_text(bq: str, preserve_em: bool) -> str:
    """Convert a blockquote fragment to stanza-aware text.

    Preserves <em> tags when preserve_em is True.

    Key trick: real line breaks come only from <br>/<p> tags; raw \\n in the
    source HTML is just formatting. We convert tags to placeholders, decode
    and clean everything, THEN flip placeholders to real newlines while
    eating adjacent ASCII spaces.  U+00A0 (from &nbsp;) is left alone during
    that step so hanging-indent runs survive as leading spaces after \\n.
    """
    s = bq

    # 1. Normalize <i>/<em> variants -> <em>
    s = re.sub(r"<i\b[^>]*>",  "<em>",  s, flags=re.IGNORECASE)
    s = re.sub(r"</i\s*>",     "</em>", s, flags=re.IGNORECASE)
    s = re.sub(r"<em\b[^>]*>", "<em>",  s, flags=re.IGNORECASE)
    s = re.sub(r"</em\s*>",    "</em>", s, flags=re.IGNORECASE)

    # 2. Bold section headers: <b>ROMAN. …</b> -> its own stanza.
    #    Other <b>…</b> is unwrapped as inline text.
    def _handle_b(m: re.Match) -> str:
        inner = m.group(1)
        text_only = re.sub(r"<[^>]+>", "", inner).strip()
        if ROMAN_RE.match(text_only):
            return f"{PP_MARK}{inner}{PP_MARK}"
        return inner
    s = re.sub(r"<b\b[^>]*>(.*?)</b>", _handle_b, s,
               flags=re.DOTALL | re.IGNORECASE)

    # 3. <br> -> BR placeholder
    s = re.sub(r"<br\s*/?>", BR_MARK, s, flags=re.IGNORECASE)

    # 4. <p>/</p> -> PP placeholder (stanza break)
    s = re.sub(r"</?p\b[^>]*>", PP_MARK, s, flags=re.IGNORECASE)

    # 5. Anchor text: <a …>text</a> -> text
    s = re.sub(r"<a\b[^>]*>(.*?)</a>", r"\1", s,
               flags=re.DOTALL | re.IGNORECASE)

    # 6. Strip other tags. Keep <em>/</em> if requested.
    if preserve_em:
        s = re.sub(r"<(?!/?em\b)[^>]+>", "", s, flags=re.IGNORECASE)
    else:
        s = re.sub(r"<[^>]+>", "", s)

    # 7. Decode HTML entities (both named and numeric, incl. &#151;)
    s = H.unescape(s)

    # 8. Fix cp1252 mojibake (bytes 0x80-0x9F stored as raw codepoints)
    s = fix_cp1252(s)

    # 9. Neutralise raw source whitespace so it doesn't become content.
    s = s.replace("\r", " ").replace("\n", " ").replace("\t", " ")

    # 10. Flip placeholders to newlines, eating adjacent ASCII spaces only
    #     (U+00A0 hanging-indent chars are preserved).
    s = re.sub(r"[ ]*" + re.escape(BR_MARK) + r"[ ]*", "\n",   s)
    s = re.sub(r"[ ]*" + re.escape(PP_MARK) + r"[ ]*", "\n\n", s)

    # 11. Now NBSP -> regular space (line boundaries already set)
    s = s.replace(NBSP, " ")

    # 12. Cleanup: collapse 3+ newlines, rstrip each line, trim edges
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = "\n".join(ln.rstrip() for ln in s.split("\n")).strip("\n")

    # 13. Drop empty <em></em> pairs (from empty italic spans in the source)
    s = re.sub(r"<em>\s*</em>", "", s)
    return s

_BQ_TAG = re.compile(r"</?blockquote\b[^>]*>", re.IGNORECASE)

def _find_outer_blockquote(html: str) -> str | None:
    """Return inner content of the OUTERMOST <blockquote>, honouring nesting.

    Some poems have a nested <blockquote> for the epigraph, so a plain
    non-greedy regex closes on the epigraph's </blockquote> and drops the
    body.  This walks tag-by-tag maintaining depth.
    """
    open_m = re.search(r"<blockquote\b[^>]*>", html, re.IGNORECASE)
    if not open_m:
        return None
    content_start = open_m.end()
    pos = content_start
    depth = 1
    while depth > 0:
        m = _BQ_TAG.search(html, pos)
        if not m:
            return None
        if m.group(0).lower().startswith("</"):
            depth -= 1
            if depth == 0:
                return html[content_start:m.start()]
        else:
            depth += 1
        pos = m.end()
    return None

def parse_entry(html: str) -> tuple[str, str] | None:
    """Return (body_plain, body_html) for one raw HTML entry, or None on failure."""
    bq = _find_outer_blockquote(html)
    if bq is None:
        return None
    bq = _trim_trailing_junk(bq)
    bq = _strip_title(bq)
    body_plain = _to_text(bq, preserve_em=False)
    body_html  = _to_text(bq, preserve_em=True)
    if not body_plain.strip():
        return None
    return body_plain, body_html

# ── entry lookup ────────────────────────────────────────────────────────────

def make_probes(body: str) -> list[str]:
    if not body:
        return []
    lines = [ln.strip() for ln in body.split("\n") if len(ln.strip()) >= 20]
    def score(ln: str):
        clean = not any(c in ln for c in "'\"’“”—–…&<>")
        return (clean, len(ln))
    lines.sort(key=score, reverse=True)
    return lines[:5]

def probe_variants(s: str) -> list[str]:
    vs = [s]
    if "'" in s:
        vs += [s.replace("'", "&#39;"), s.replace("'", "’"),
               s.replace("'", "&#146;"), s.replace("'", "&#8217;")]
    if "’" in s:
        vs += [s.replace("’", "&#8217;"), s.replace("’", "'")]
    if '"' in s:
        vs += [s.replace('"', "&#34;"), s.replace('"', "&quot;")]
    if "&" in s:
        vs.append(s.replace("&", "&amp;"))
    if "—" in s:
        vs += [s.replace("—", "&#151;"), s.replace("—", "&#8212;")]
    if "–" in s:
        vs += [s.replace("–", "&#150;"), s.replace("–", "&#8211;")]
    if "…" in s:
        vs += [s.replace("…", "&#133;"), s.replace("…", "...")]
    vs.append(H.escape(s))
    seen, out = set(), []
    for v in vs:
        if v not in seen:
            seen.add(v); out.append(v)
    return out

# ── db fetch ────────────────────────────────────────────────────────────────

def fetch_all_versedaily() -> list[dict]:
    poems, offset, PAGE = [], 0, 1000
    while True:
        q = (
            f"{SUPABASE_URL}/rest/v1/poems"
            f"?select=id,title,author,body,body_html,line_count"
            f"&corpus=eq.versedaily&order=id.asc&limit={PAGE}&offset={offset}"
        )
        r = subprocess.run(
            ["curl", "-s",
             "-H", f"apikey: {SUPABASE_KEY}",
             "-H", f"Authorization: Bearer {SUPABASE_KEY}", q],
            capture_output=True, text=True,
        )
        d = json.loads(r.stdout)
        poems.extend(d)
        if len(d) < PAGE:
            break
        offset += PAGE
    return poems

# ── counting helpers for reporting ──────────────────────────────────────────

def stanza_count(body: str) -> int:
    if not body:
        return 0
    return sum(1 for g in re.split(r"\n\n+", body) if g.strip())

def line_count(body: str) -> int:
    if not body:
        return 0
    return sum(1 for ln in body.split("\n") if ln.strip())

# ── main ────────────────────────────────────────────────────────────────────

def main() -> None:
    args = sys.argv[1:]
    dry_run    = "--dry-run" in args
    write_mode = "--write"   in args
    if not dry_run and not write_mode:
        sys.exit("Specify --dry-run or --write")

    print("Fetching versedaily poems ...", flush=True)
    poems = fetch_all_versedaily()
    print(f"  {len(poems)} poems.", flush=True)

    print("Loading raw dump ...", flush=True)
    t0 = time.time()
    with open(RAW_PATH) as f:
        entries = json.load(f)
    print(f"  {len(entries)} entries in {time.time()-t0:.1f}s", flush=True)

    print("Indexing raw dump ...", flush=True)
    t0 = time.time()
    SEP = "\n\x1e\n"
    parts, offsets, pos = [], [], 0
    for e in entries:
        offsets.append(pos)
        parts.append(e["html"])
        pos += len(e["html"]) + len(SEP)
    BIG = SEP.join(parts)
    print(f"  {len(BIG):,} chars in {time.time()-t0:.1f}s", flush=True)

    def find_entry_for(body: str) -> int:
        for probe in make_probes(body):
            for v in probe_variants(probe):
                p = BIG.find(v)
                if p >= 0:
                    return bisect.bisect_right(offsets, p) - 1
        return -1

    print("Matching + parsing ...", flush=True)
    t0 = time.time()
    plans: list[dict] = []
    missed: list[dict] = []
    parse_failed: list[dict] = []
    implausible: list[dict] = []

    for i, p in enumerate(poems):
        if i and i % 500 == 0:
            print(f"  {i}/{len(poems)}  ({time.time()-t0:.1f}s)", flush=True)

        idx = find_entry_for(p.get("body") or "")
        if idx < 0:
            missed.append(p)
            continue

        parsed = parse_entry(entries[idx]["html"])
        if parsed is None:
            parse_failed.append({**p, "entry_url": entries[idx]["url"]})
            continue
        new_body, new_body_html = parsed

        old_body = p.get("body") or ""
        old_lc   = line_count(old_body)
        new_lc   = line_count(new_body)
        old_sc   = stanza_count(old_body)
        new_sc   = stanza_count(new_body)

        flags: list[str] = []
        if new_lc == 0:
            flags.append("empty-body")
        else:
            # Flag "every line its own stanza" only when NEW invents the
            # pattern.  If OLD already had it, the source really is written
            # that way (e.g. poem_2113 "First Domestic").
            new_ratio = new_sc / max(new_lc, 1)
            old_ratio = old_sc / max(old_lc, 1)
            if new_lc > 3 and new_ratio > 0.7 and old_ratio < 0.5:
                flags.append(f"too-many-stanzas ({new_sc}/{new_lc})")
            if old_lc >= 3:
                drift = abs(new_lc - old_lc) / old_lc
                if drift > 0.4:
                    flags.append(f"line-drift {old_lc}->{new_lc} ({drift*100:.0f}%)")

        plan = {
            "id":               p["id"],
            "title":            p["title"],
            "author":           p["author"],
            "entry_url":        entries[idx]["url"],
            "old_body":         old_body,
            "new_body":         new_body,
            "new_body_html":    new_body_html,
            "old_line_count":   old_lc,
            "new_line_count":   new_lc,
            "old_stanza_count": old_sc,
            "new_stanza_count": new_sc,
            "flags":            flags,
            "gained_stanzas":   old_sc <= 1 and new_sc > 1,
        }
        plans.append(plan)
        if flags:
            implausible.append(plan)

    print(f"  parse+match done in {time.time()-t0:.1f}s\n", flush=True)

    # ── Report ──
    print("=" * 70)
    print("PARSE PLAN")
    print("=" * 70)
    print(f"Total live versedaily poems       : {len(poems)}")
    print(f"Matched + parsed successfully     : {len(plans)}")
    print(f"Not found in raw dump (skip)      : {len(missed)}")
    print(f"Parse failed (no blockquote/empty): {len(parse_failed)}")
    print()
    gained  = sum(1 for p in plans if p["gained_stanzas"])
    already = sum(1 for p in plans if p["old_stanza_count"] > 1)
    single  = sum(1 for p in plans
                  if p["old_stanza_count"] <= 1 and p["new_stanza_count"] <= 1)
    print(f"Poems that GAIN stanza breaks     : {gained}")
    print(f"Poems already had stanza breaks   : {already}")
    print(f"Poems that stay single-block      : {single}")
    print()
    print(f"Implausible parses (flagged)      : {len(implausible)}")
    print()

    # Prefer gained-stanza samples (the actual point of the exercise);
    # fill the rest with untouched-structure samples for regression sanity.
    gained_samples = [p for p in plans if p["gained_stanzas"]][:6]
    kept_samples   = [p for p in plans
                      if not p["gained_stanzas"] and not p["flags"]][:4]
    sample = gained_samples + kept_samples

    print("── 10 sample parses (before / after) ──\n")
    for pl in sample:
        print(f"── {pl['id']} · {pl['title']} · {pl['author']} ──")
        print(f"   {pl['entry_url']}")
        print(f"   lines {pl['old_line_count']}->{pl['new_line_count']}    "
              f"stanzas {pl['old_stanza_count']}->{pl['new_stanza_count']}    "
              f"flags={pl['flags'] or 'ok'}")
        old_show = pl["old_body"][:320].replace("\n", "\\n")
        new_show = pl["new_body"][:320].replace("\n", "\\n")
        print(f"   OLD: {old_show!r}")
        print(f"   NEW: {new_show!r}")
        print()

    if implausible:
        print("── Flagged (implausible) parses — first 20 ──\n")
        for pl in implausible[:20]:
            print(f"  {pl['id']:<12} {pl['flags']}   {(pl['title'] or '')[:40]}")
            print(f"    {pl['entry_url']}")
        if len(implausible) > 20:
            print(f"  … {len(implausible)-20} more not shown …")
        print()

    with open("/tmp/vd_missed.json", "w") as f:
        json.dump([{"id": p["id"], "title": p["title"], "author": p["author"]}
                   for p in missed], f, indent=2, ensure_ascii=False)
    with open("/tmp/vd_flagged.json", "w") as f:
        json.dump([{k: v for k, v in p.items()
                    if k not in ("old_body", "new_body", "new_body_html")}
                   for p in implausible], f, indent=2, ensure_ascii=False)
    print("(missed -> /tmp/vd_missed.json, flagged -> /tmp/vd_flagged.json)")

    if dry_run:
        print("\nDry run — no writes.")
        return

    print(f"\nWriting {len(plans) - len(implausible)} poems "
          f"(skipping {len(implausible)} flagged) ...", flush=True)
    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    written, errors = 0, []
    to_write = [p for p in plans if not p["flags"]]
    for i, pl in enumerate(to_write):
        if i and i % 200 == 0:
            print(f"  {i}/{len(to_write)}", flush=True)
        payload = {"body": pl["new_body"], "body_html": pl["new_body_html"]}
        try:
            client.table("poems").update(payload).eq("id", pl["id"]).execute()
            written += 1
        except Exception as exc:
            errors.append((pl["id"], str(exc)))
    print(f"Done. {written} updated.")
    if errors:
        print(f"{len(errors)} errors:")
        for pid, msg in errors[:20]:
            print(f"  {pid}: {msg}")

if __name__ == "__main__":
    main()
