# Decisions — Chess Coach CLI

## 2026-08-08 — CLI-first MVP, defer Scid

Hypothesis: a headless PGN→report pipeline validates the Stockfish + RAG + LLM contract before GUI/archive work.

Outcome: implement `chess-coach analyze` / `ingest` only. Scid vs PC, Lichess Master scraping, and multi-million game DBs remain future work.

## 2026-08-08 — Stockfish is ground truth; RAG is pedagogy

LLMs hallucinate illegal moves and fake evals. Engine numbers and PVs are injected into prompts and never overridden by book text.

RAG (Chroma) stores chunked book paragraphs with theme metadata. Retrieval query is built from board features (phase, IQP, Sicilian, eval swing), not free chat. Hybrid scoring = cosine similarity + theme/keyword bonus.

If retrieval is empty or below `min_score`, commentary falls back to engine-only templates (optionally still via LLM with no passages).

## 2026-08-08 — Embedding fallback

Prefer Ollama `nomic-embed-text`. If unavailable, use a deterministic hashing embedder so ingest/retrieve still smoke-test without network/GPU. Production coaching quality assumes real embeddings.

## 2026-08-08 — Real embeddings + preflight

- Ingest defaults to **Ollama only** (`allow_hash_fallback=False`). Hash dims (384) must never mix with nomic dims (768).
- Added `chess-coach preflight` to validate embed model + PDF text extract before full ingest.
- Many archive PDFs are image-scans (pypdf ≈ empty); ingest skips those. Prefer OCR/txt for BAD books.
- Theme sidecars match by slug prefix so short `logical_chess.themes.yaml` links to long Z-Library filenames.

## 2026-08-08 — Scraper + Scid visualizer

- Lichess opening explorer (`explorer.lichess.ovh`) returns **401** from this host; scraper prefers Lichess user/game export + Chess.com public archives.
- `annotate` embeds Stockfish NAGs, `[%eval]`, coach comments, and engine best as PGN variations — importable into Scid vs PC.
- HTML viewer (`visualize` / `--html`) is the offline board UI when Scid is not installed; does not replace Scid database features.

## 2026-08-08 — Book-chapter Chessgames walkthrough

- Desired workflow is **book chapter → cited master game → dual commentary**, not amateur/user scrapes.
- Plain `httpx`/`requests` get AWS WAF 202; Chessgames client shells out to system **`curl --http1.1`** with a cookie jar.
- Annotation layers in PGN comments: `[Book:…]` primary from chapter move notes; `[Engine/RAG]` secondary from Stockfish + other ingested books.
- CLI entrypoint: `chess-coach chapter BOOK --chapter N`.
- Section schemes differ per book (`GAME N` vs `Chapter N`); `chess-coach sections` auto-writes `.sections.yaml` sidecars.
- OCR player names (`Corro`→`Corzo`) normalized via `names.py`; Chessgames search retries surname variants.

## 2026-08-08 — Local masters DB primary (no TWIC)

- Chessgames has gaps on less-famous OTB games + rate limits. Source of truth shifts to a **local PGN index** (Lumbra Gigabase OTB recommended).
- `chess-coach masters-index` builds SQLite `(surname, surname, year) → file offset` over `data/masters/pgn/**/*.pgn`.
- Fetch order: **local index → Chessgames fallback**. TWIC not wired — book corpus is historical, not weekly freshness.
- Config: `masters.*` in `configs/default.yaml`.
- Gigabase names are `Last, First`. Index must key on the **pre-comma** surname (`Carlsen, Magnus` → `carlsen`). Bug stored given names; fix via `chess-coach masters-index --fix-surnames`.

## 2026-08-08 — Book-text PGN + missing pages

- Third fallback: reconstruct playable mainline from citation context / move notes in the PDF text (`book_pgn.py`). Partial scores OK if ≥8 legal plies.
- If local + Chessgames + book-text all fail: emit `*_missing.html` and keep a **missing page** in the chapter book (TOC mark ✗) with tried methods + context preview.

## 2026-08-08 — Chapter UX + dense RAG

- Chapter book: mouse wheel over board/dock steps **moves**; games only via TOC / PageUp-Down / `[` `]`. Removed IntersectionObserver auto-game-switch (was jumping mid-game).
- Secondary commentary denser: all opening plies (default 18) + every Nth later ply + critical + book anchors. Opening RAG prefers opening-titled books (`top_k_opening`, lower `min_score_opening`). Pedagogical fallback quotes passages instead of fake “inaccuracy 0cp”.

## 2026-08-09 — TOC-only chapter UI + position notes + local Stockfish

- Removed top “page-stack” game list; left TOC is the only game menu (plus header Game ⟪/⟫).
- Stockfish WASM always copied beside the HTML (`bookwalk/stockfish/…`) so Worker URL is `stockfish/….js` whether you serve `viewer_out` or `bookwalk`.
- `--no-llm` secondary notes are **engine-grounded only** (move facts, themes, eval/PV). Raw FCO/intro RAG quotes removed — they repeated unrelated opening essays.
- `chess-coach refresh-notes` rewrites `[Engine/RAG]` on existing bookwalk PGNs and rebuilds the chapter book without re-fetching masters.

## 2026-08-09 — Pattern ontology (Family-4 scaffold)

- Patterns live in `data/ontology/patterns/*.yaml` (id, keywords, rules_of_thumb, plans, related, detect).
- Detectors in `ontology/detect.py` emit IDs from FEN/ECO (IQP, hanging pawns, Carlsbad minority, Sicilian schemes, bishop pair, rook endgames…).
- `PositionFeatures.patterns` feeds RAG query text + keyword boost; Ollama prompt gets pattern cards; `--no-llm` fallback appends one pattern rule line.
- Next: tag Chroma chunks with `patterns:` at ingest; attach master-game exemplars per node.

## 2026-08-09 — Ingest pattern tagging

- Chunks store `patterns` metadata (comma-separated ontology IDs) via keyword/alias tagger at ingest.
- `chess-coach retag-patterns` rewrites metadata on existing Chroma docs without re-embedding.
- Retrieve boosts overlap between board-detected pattern IDs and chunk `patterns` tags.

## 2026-08-09 — Ontology expansion + LLM refresh

- Pattern set expanded (~25 nodes): French, Caro-Kann, KID, QGD, passed pawn, opposite bishops, Maroczy, Hedgehog, pawn chain, space, open e-file.
- Board/ECO detectors wired; Chroma retagged (~8k/34k hits).
- `refresh-notes --llm` uses RAG automatically and strips Qwen3 think leakage from comments.

## 2026-08-09 — Playable variation forks

- Book sidelines + engine best/PV are injected as real PGN variations (`Book line:` / `Engine best`).
- Viewer move list shows dashed forks; click to play on the board (←/→ walk fork, Esc = mainline).
- Parser greedily legalizes OCR SAN from book prose at the ply’s before/after position.
- Engine forks only on book / critical / secondary-comment plies (not every quiet move).

## 2026-08-10 — Variation arrows on the board

- Chapter viewer draws SVG arrows over the board for next-move options: faint mainline, purple book forks, orange engine forks/PV, teal explore.
- Arrows update on position change, flip, resize, and live Stockfish PV.

## 2026-08-10 — Figurine book notes + Quality Chess OCR

- Book notes showed OCR glyph salad (`24.id3`, `ltJxf5`, `\Wxcl`, `l'kl`) instead of readable moves.
- `ocr_chess.ocr_clean_chess` maps those Quality Chess / ChessBase artifacts to SAN (`Bd3`, `Nxf5`, `Qxc1`, `Rc1`).
- Chapter viewer renders piece moves with Wikipedia piece icons (figurine notation) via `formatNoteHtml`.

## 2026-08-10 — Push annotated PGNs to Lichess study

- chess-wrapped mobile auth: Bearer token + `study:write` (OAuth / PAT). Used undocumented one-shot `POST /api/study/import-pgn`.
- Current Lichess API: `POST /api/study` (create) then `POST /api/study/{id}/import-pgn` (chapters). PGN variations/comments/NAGs pass through StudyPgnImport.
- `chess-coach study-push` uploads `*_bookwalk.pgn` / `*_annotated.pgn` as study chapters (default one request per game; `--batch` joins games). Token: `LICHESS_TOKEN`.

## 2026-08-10 — Notation dictionary for OCR

- Canonical reference: `notation_dict.py` — squares a1–h8, piece letters NBRQK, move marks (`??`…`!!`), Informator evals (`=` `⩲` `⩱` `±` `∓` `+-` `-+` `∞` `=/∞`).
- `OCR_ALIASES` maps scan junk (`?f`→`?!`, `;i;`/`+=`→`⩲`, …). `ocr_chess` resolves trailing aliases through this module.
- `PIECE_OCR_GLYPHS` maps Quality Chess figurines (`'Wie`→`Qe`, `ltJ`→`N`, `%'m`→`Qf8`, …). Mid-prose pass rewrites `"a3-a4, 'Wie2, ltJc4"` → SAN; viewer figurizes bare SAN with piece icons.
- Non-dictionary PDF rules (move-number surgery, mainline detection, page strip, lookahead piece OCR, …) catalogued in `PDF_PARSING_RULES.md`.

## 2026-08-12 — Book notes: curated + RAG pivot (no 90/95 PDF SLA)

- Auto PDF→ply book sync cannot hit ~90% text / ~95% move accuracy for Family 4 at scale (figurine fonts, segment/align drops, thin fixtures).
- **Production book voice:** curated `*.book_notes.yaml` sidecars next to `*_bookwalk.pgn`; tags `[Book:curated|…]`.
- **PDF extract:** draft-only (`chess-coach draft-book-notes`, optional `--font-glyphs` via PyMuPDF). Tags `[Book:draft|…]`. Never treat live extract as curated.
- **Viewer honesty:** badge “Book note (curated|draft)” vs “Book ideas (RAG)” when no ply book note but Engine/RAG text exists.
- **Metrics:** `chess-coach book-note-metrics` (fixture recall + Family-4 `[Book:]` density) — wall numbers, not a fake SLA.
- Flagship Family 4 games (McShane / Wojtaszek / Bouaziz) frozen via curated sidecars; other games rely on masters PGN + engine/RAG until curated.
- EPUB/HTML can clean glyphs; still does not solve move↔comment sync. Annotated PGN/CBV remains gold when available.

## 2026-08-10 — Chapter viewer: book + session user lines only

- TEMP (`SHOW_ENGINE_VAR_BOOKS = false` in `chapter_book.template.html`): hide Engine/RAG notes, PGN book/engine forks, and the “engine / variants” legend.
- Book notes + live explore lines remain.
- User lines persist for the browser session (in-memory per game); reopen via green brackets in the move tree. Lost on full page reload.
- Flip flag to `true` to restore engine notes + playable forks.

