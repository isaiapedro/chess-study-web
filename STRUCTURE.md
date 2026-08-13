# Chess Coach — File Structure

Root (repo-relative):

`workspace/experiments/chess-coach/`

Absolute:

`/home/pedrosouza/pessoal/master_manager/workspace/experiments/chess-coach/`

---

## Tree (logical)

```
chess-coach/
├── README.md                 # Setup, CLI usage
├── STRUCTURE.md              # This file
├── BEHAVIOR.md               # Experiment boundaries
├── DECISIONS.md              # ADR log
├── PDF_PARSING_RULES.md      # Grammar layers vs dict lookups
├── tests/                    # pytest: grammar + PDF note fixtures
├── Chess_AI_Coaching_System_Design.md
├── manifest.yaml             # PIOS experiment manifest
├── pyproject.toml            # Package + `chess-coach` entrypoint
├── requirements.txt
├── preflight.md              # Generated book OCR/preflight report
│
├── configs/
│   └── default.yaml          # Stockfish path, Ollama, depths, Chroma
│
├── scripts/
│   └── ingest_books.sh       # Background full-book ingest helper
│
├── src/chess_coach/          # Python package
│   ├── __main__.py           # python -m chess_coach
│   ├── cli.py                # CLI commands
│   ├── config.py
│   ├── logutil.py            # stderr progress logs
│   ├── pgn_io.py
│   ├── engine.py             # Local Stockfish (offline annotate)
│   ├── analyze.py            # Critical-moment scan
│   ├── features.py
│   ├── comment.py            # Ollama coaching notes
│   ├── validate.py
│   ├── annotate.py           # Annotated PGN export
│   ├── report.py
│   ├── viewer.py             # Interactive HTML + SF18 WASM bootstrap
│   ├── chapter.py            # Book sections / citations
│   ├── ocr_chess.py          # PDF glyph cleanup (uses grammar heads)
│   ├── chess_text_grammar.py # Move heads + score-line segmenter
│   ├── notation_dict.py      # Squares / pieces / marks / eval reference
│   ├── notes_align.py        # Anchor book notes to game plies
│   ├── book_walkthrough.py   # Dual Book + Engine/RAG annotate
│   ├── masters_db.py         # Local PGN → SQLite index (Gigabase)
│   ├── master_fetch.py       # Local first, Chessgames fallback
│   ├── chessgames.py         # chessgames.com via curl
│   ├── names.py              # OCR name fixes / search variants
│   ├── sections_init.py      # Auto-write *.sections.yaml
│   ├── scrape.py             # Legacy scrape helpers
│   └── rag/
│       ├── chunking.py
│       ├── embeddings.py
│       ├── ingest.py
│       ├── retrieve.py
│       ├── preflight.py
│       └── synthesize_annotated.py  # bookwalk → annotated_positions
│
└── data/
    ├── books/                # PDFs (gitignored) + sidecars
    ├── chroma/               # Vector DB (gitignored, local)
    ├── sample_games/         # Demo PGNs
    ├── sample_chapters/      # Demo book text
    ├── masters/              # Local OTB PGNs + index.sqlite (gitignored)
    ├── pgn_archive/          # Fetched raw masters PGNs
    ├── annotated/            # Annotated PGNs (+ bookwalk/)
    └── viewer_out/           # HTML replay + Stockfish 18 WASM
```

---

## Package source (`src/chess_coach/`)

| Path | Role |
|------|------|
| `cli.py` | Commands: analyze, ingest, chapter, masters-index, scrape, visualize, sections, preflight |
| `engine.py` | Offline Stockfish binary (UCI) |
| `analyze.py` | Per-ply scan → critical moments |
| `book_walkthrough.py` | Chapter → masters fetch → dual annotations |
| `masters_db.py` | Index/search local Gigabase-style PGNs |
| `master_fetch.py` | Local index → Chessgames |
| `chapter.py` | Section schemes (`family` / `chapter` / `game`…), citation parse |
| `notes_align.py` | Map book prose to correct fullmove/SAN |
| `ocr_chess.py` | Clean Quality Chess / scan OCR |
| `notation_dict.py` | Squares, pieces, !/? marks, Informator eval + OCR aliases |
| `chessgames.py` | Search/fetch PGN (system `curl`) |
| `viewer.py` | Big board + coach panel + live SF18 HTML (wheel/arrow stepping) |
| `rag/*` | Chunk → embed → Chroma → retrieve; `synthesize_annotated` for bookwalk vectors |

Install editable: `pip install -e .` → CLI `chess-coach`.

---

## Config

| Path | Role |
|------|------|
| `configs/default.yaml` | `stockfish_path`, analyze depth, Ollama host/models, Chroma path, thresholds |

Local Stockfish binary often under `.tools/stockfish/` (gitignored).

---

## Data layout (`data/`)

### Books — `data/books/`

| Kind | Location | Notes |
|------|----------|--------|
| PDF binaries | `data/books/*.pdf` | **Not committed** (`.gitignore`) |
| Section sidecars | `data/books/<slug>.sections.yaml` | Scheme: `family`, `game`, `chapter`… |
| Theme sidecars | `data/books/<slug>.themes.yaml` | RAG theme hints |
| README | `data/books/README.md` | Local book notes |

Example: Chess Structures →  
`chess_structures_a_grandmaster_guide_standard_patterns_and_plans_explained.sections.yaml`  
(`section_scheme: family`)

### RAG store — `data/chroma/`

Local Chroma persistence. **Gitignored.**

### Samples

| Path | Role |
|------|------|
| `data/sample_games/*.pgn` | Demo games for `analyze` |
| `data/sample_chapters/*.txt` | Demo chapter text |

### Archives & annotations

| Path | Role |
|------|------|
| `data/pgn_archive/` | Scraped / fetched raw PGNs |
| `data/annotated/` | Offline-annotated PGNs |
| `data/annotated/bookwalk/` | Book-walkthrough annotated PGNs |
| `data/annotated/bookwalk/raw/` | Chessgames raw downloads (`cg_<gid>.pgn`) |
| `data/annotated/**/SCID_IMPORT.md` | How to open in Scid / HTTP viewer |

Example walkthrough PGN:

`data/annotated/bookwalk/Levon_Aronian_vs_Hrvoje_Stevie_2011_bookwalk.pgn`

### HTML viewer — `data/viewer_out/`

| Path | Role |
|------|------|
| `data/viewer_out/*.html` | Single-game viewers |
| `data/viewer_out/bookwalk/*_bookwalk.html` | Chapter walkthrough replay UI |
| `data/viewer_out/stockfish/stockfish-18-lite-single.js` | SF18 worker loader |
| `data/viewer_out/stockfish/stockfish-18-lite-single.wasm` | SF18 lite WASM (~7MB, downloaded on first visualize) |

Serve:

```bash
cd data/viewer_out && python -m http.server 8765
# e.g. http://127.0.0.1:8765/bookwalk/Levon_Aronian_vs_Hrvoje_Stevie_2011_bookwalk.html
```

Viewer UI: title = book + chapter, subtitle = players / event / result.
Board is the focus (`min(70vh, 640px)`); book notes render as a coach speech
bubble beside it, with `next note ↠` jumps. Mouse wheel over the board steps
moves; arrows/Home/End/F/N also bound.

Live engine: **Stockfish 18 lite-single**, depth **22** (browser).  
Offline annotate: local Stockfish from `configs/default.yaml` (separate).

---

## Scripts & tooling (local-only / gitignored)

| Path | Role |
|------|------|
| `.venv/` | Python virtualenv |
| `.tools/stockfish/` | Optional bundled Stockfish binary |
| `scripts/ingest_books.sh` | Long-running ingest (`setsid`/`nohup` friendly) |
| `preflight.md` | Last preflight report |

---

## CLI → outputs (quick map)

| Command | Writes |
|---------|--------|
| `chess-coach preflight data/books` | `preflight.md` (or `--out`) |
| `chess-coach ingest data/books` | `data/chroma/` |
| `chess-coach sections data/books` | `data/books/*.sections.yaml` |
| `chess-coach chapter BOOK --chapter N` | `data/annotated/bookwalk/*.pgn` + per-game HTML + `*_chapter_book.html` (all ok games, book order) |
| `chess-coach scrape …` | `data/pgn_archive/` |
| `chess-coach analyze PGN` | `data/annotated/*_annotated.pgn` (+ optional HTML) |
| `chess-coach visualize PGN` | `data/viewer_out/…html` (+ ensures `stockfish/` assets) |

---

## Git ignore highlights

Committed: source, configs, docs, `*.sections.yaml`, samples, `.gitkeep`s.  
Local-only: `.venv/`, `.tools/`, `data/books/*.pdf`, `data/chroma/`, `data/annotated/**`, `data/viewer_out/**`, `data/pgn_archive/**` (except keep/readme stubs).
