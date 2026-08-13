# Chess Coach (CLI MVP)

Local coaching pipeline: **PGN → Stockfish → RAG books → Ollama commentary → Scid/HTML**.

Stockfish owns evaluations and PVs. RAG supplies pedagogical language from ingested books. The LLM translates grounded facts into coaching prose. Annotated PGNs open in **Scid vs PC**; HTML viewer previews boards offline.

## System deps

- **Stockfish**: `apt install stockfish`, or `.tools/stockfish/...` (see `configs/default.yaml`)
- **Ollama**: [ollama.com](https://ollama.com)

```bash
ollama pull nomic-embed-text
ollama pull qwen3:8b
```

- **Scid vs PC** (optional GUI): `sudo apt install scid-vs-pc` — import annotated PGNs from `data/annotated/`

## Setup

```bash
cd workspace/experiments/chess-coach
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Books: preflight → ingest

```bash
chess-coach preflight data/books --out preflight.md
chess-coach ingest data/books          # real embeddings (Ollama)
# watch: tail -f /tmp/full_ingest.log
```

Scanned/empty PDFs auto-skipped. Prefer OCR → `.txt` for BAD books in preflight.

## Similarity RAG → Chess Wrapped mobile

Pipeline: **ingest PDFs → write knowledge summaries → link similar masters PGNs → embed RAG** (+ optional annotated bookwalk).

```bash
# Full pipeline (Ollama: nomic-embed-text + qwen3:8b recommended)
chess-coach knowledge-pipeline data/books --reset-summaries

# Or step-by-step:
chess-coach ingest data/books
chess-coach summarize-knowledge data/books --reset          # LLM summaries + ECO/PGN links
chess-coach summarize-knowledge data/books --no-llm         # extractive fallback
chess-coach synthesize-annotated                            # bookwalk ply vectors

# Hit-rate sample (summary / curated / book mix)
chess-coach rag-hit-rate --limit 40 --out data/viewer_out/rag_hit_rate.md

# Grow attack / tactics coverage:
# chess-coach chapter "data/books/The Art of Attack in Chess....pdf" --scheme chapter --chapter 1 --max-games 3
```

Summaries land in `data/knowledge_summaries/*.jsonl` and Chroma `chess_knowledge_summaries`.
Each summary carries `eco_hints` + `similar_games` from the local masters index.

### Ship to Expo (derived product only)

The mobile app must **not** embed PDFs or the masters DB. Export a compact pack:

```bash
chess-coach export-mobile-pack
# writes:
#   data/derived/mobile_coach_pack.json
#   ../../side_projects/chess/mobile/src/engine/gameCoach/derivedCoachPack.ts
```

Pack fields: summary text, themes/motifs, ECO hints, **frequent SAN lines** sampled from masters for those ECOs.
`knowledge-pipeline` runs this export by default (`--no-export-mobile` to skip).

Chess Wrapped API (from `workspace/side_projects/chess`):

```bash
export CHESS_COACH_ROOT=/absolute/path/to/workspace/experiments/chess-coach
# start API as usual; POST /api/v1/coach/retrieve { fen, themes, phase, san, wantCount }
```

Mobile Games analysis calls that endpoint; if down, falls back to on-device theme pack.

## Local masters DB (recommended)


Chessgames alone misses many book citations. Put a large OTB dump (e.g. [Lumbra Gigabase](https://lumbrasgigabase.com/en/)) in `data/masters/pgn/`, then:

```bash
chess-coach masters-index
```

`chapter` / `scrape` fetch order: **local index → Chessgames → book-text move rebuild**.  
Total miss → `*_missing.html` + missing page in chapter book (tried methods listed).  
Details: `data/masters/README.md`.

## Book section → masters → dual walkthrough

Primary flow: read a **book section**, detect cited professional games, fetch from **local masters** (Chessgames fallback), walk with:

1. **Primary** — curated `*.book_notes.yaml` when present (`[Book:curated|…]`); otherwise draft PDF extract (`[Book:draft|…]`)  
2. **Secondary** — Stockfish eval/PV + other RAG book excerpts (viewer: “Book ideas (RAG)” when no ply book note)

PDF auto-sync is **not** a 90/95 accuracy SLA — see `DECISIONS.md`. Prefer curated sidecars for flagship games.

```bash
chess-coach book-note-metrics --out data/viewer_out/book_note_metrics.md
chess-coach export-book-notes data/annotated/bookwalk/Foo_bookwalk.pgn   # freeze curated YAML
chess-coach reapply-book-notes data/annotated/bookwalk/Foo_bookwalk.pgn --html
chess-coach draft-book-notes "data/books/Chess Structures….pdf" --chapter "Family 4" --font-glyphs
```

### Sections differ per book

Auto-detect heading scheme among: `chapter`, `game`, `ending`, `part`, `lesson`, `section`.  
Only headings with a long enough body count (skips TOC stubs).

```bash
# see how THIS book is sliced
chess-coach chapter "data/books/Capablancas Best Chess Endings....pdf" --list-sections

# Capablanca endings book = Game N, not Chapter N
chess-coach chapter "data/books/Capablancas Best Chess Endings....pdf" --scheme game --chapter 1 --dry-run
```

Optional per-book sidecar — **auto-generate for whole archive**:

```bash
chess-coach sections data/books
# overwrite:
chess-coach sections data/books --force
```

Writes `data/books/<slug>.sections.yaml` with detected scheme (`game` / `chapter` / …).

```bash
# list citations only
chess-coach chapter data/sample_chapters/capablanca_alekhine_sample.txt --chapter 1 --dry-run

# fetch + annotate (needs `curl` on PATH)
chess-coach chapter data/sample_chapters/capablanca_alekhine_sample.txt --chapter 1 --max-games 2 --no-llm

# real PDF section
chess-coach chapter "data/books/Logical Chess....pdf" --chapter 3 --max-games 3
```

Outputs:

- `data/annotated/bookwalk/*_bookwalk.pgn` — Scid-ready  
- `data/viewer_out/bookwalk/*_bookwalk.html` — interactive replay (board, ←/→, live browser Stockfish, Book / Engine notes)

Manual Chessgames fetch:

```bash
chess-coach scrape --white Alekhine --black Capablanca --year 1927
chess-coach scrape --gid 1012524
```

Requires system `curl` (site blocks plain Python HTTP via AWS WAF).

## Annotate any PGN + visualize

```bash
chess-coach annotate data/pgn_archive/cg_1012524.pgn
xdg-open data/viewer_out/cg_1012524.html
```

### Open in Scid vs PC

1. Scid → New/Open database
2. Tools → Import PGN → `data/annotated/*_annotated.pgn`
3. Move list shows `??` / `?` glyphs + coach comments

See also `data/pgn_archive/SCID_IMPORT.md`.

### Push to Lichess study

Same auth idea as `workspace/side_projects/chess` (Bearer + `study:write`). Create a PAT at https://lichess.org/account/oauth/token and export it:

```bash
export LICHESS_TOKEN=lip_...   # or copy .env.example → .env
# one-click from the chapter book UI (embeds full PGN + comments + variations):
python scripts/serve_bookwalk.py --port 8081
# open the chapter book → header "Lichess" button
# or CLI:
chess-coach study-push data/annotated/bookwalk --name "Bookwalk chapter"
chess-coach study-push data/annotated/sample_blunder_annotated.pgn --dry-run
# append to existing study:
chess-coach study-push path/to/game_bookwalk.pgn --study-id AbCdEfGh
```

Lichess keeps coach comments and move variations (book lines / engine best). Max 64 chapters per study. Without `serve_bookwalk.py`, the button downloads the PGN instead.

## Markdown analysis report

```bash
chess-coach analyze path/to/game.pgn --out report.md
```

Flags: `--no-rag`, `--no-llm`, `--depth`, `--threshold`, `--json`

## Config

[`configs/default.yaml`](configs/default.yaml) — engine path, depth, models, RAG thresholds.

## Architecture

| Concern | Owner |
| --- | --- |
| Legal moves / eval / PV | Stockfish |
| Theme language from books | Chroma RAG |
| Fluent coaching note | Ollama (or engine-only fallback) |
| Browse annotated games | Scid vs PC + HTML viewer |
| Lichess study upload | `study-push` (PAT `study:write`) |
| Fetch training games | `scrape` (Lichess / Chess.com) |

See [`DECISIONS.md`](DECISIONS.md).
