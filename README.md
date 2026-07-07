# Sheaf

Sheaf is a mobile web app for poetry discovery. Poems are presented one at a time in a swipe-based interface — swipe past to skip, save to your library, or super-like to signal strong resonance. The app learns your taste over time through these interactions and surfaces poems you're more likely to connect with. v1 ships with a curated corpus of ~600 public-domain poems drawn from 68 authors, selected and cleaned from the DanFosing/public-domain-poetry dataset.

## Data pipeline

Source: [DanFosing/public-domain-poetry](https://huggingface.co/datasets/DanFosing/public-domain-poetry) (Hugging Face) — 38,499 poems, 496 authors.

| File | Description |
|------|-------------|
| `data/poems.json` | Raw dataset download (90 MB, gitignored) |
| `data/length_filtered.json` | 11,828 poems: 74 authors, ≤50 non-empty lines |
| `data/canonical_titles.json` | Hand-curated canonical title lists for 74 authors |
| `data/corpus_full_746.json` | 746-poem curated corpus, 20-poem-per-author cap (archive) |
| `data/corpus_full_clean.json` | 742-poem corpus after dedup and artifact cleanup |
| `data/corpus_30lines.json` | 599-poem subset: ≤30 non-empty lines per poem |
| `data/corpus_30lines_clean.json` | Same, confirmed clean — **primary working corpus** |
| `data/authors.txt` | All 496 authors ranked by poem count |
| `data/authors_by_count.txt` | Tab-separated: count, author (descending) |
| `data/curated_counts_v2.txt` | Per-author kept/matched counts for v2 corpus |

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/explore.py` | EDA of the raw dataset; outputs `data/authors.txt` |
| `scripts/build_canonical.py` | Generates `data/canonical_titles.json` from literary knowledge |
| `scripts/curate.py` | Fuzzy-matches poems against canonical lists (rapidfuzz, threshold 85) |
| `scripts/finalize.py` | Applies 20-poem cap with priority scoring; drops Schiller + Hugo |
| `scripts/clean_corpus.py` | Strips editor notes, encoding artifacts, footnotes, duplicates |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install rapidfuzz
```
