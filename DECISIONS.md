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


## 2026-08-13 — Similarity RAG bridge (annotated positions → Chess Wrapped)

- New Chroma collection `chess_annotated_positions`: bookwalk ply notes (curated YAML preferred) embedded with Ollama `nomic-embed-text`.
- CLI: `chess-coach synthesize-annotated` (idempotent upsert); `chess-coach rag-hit-rate` samples FENs and reports curated/draft/book/empty mix.
- `retrieve_for_position`: annotated first (curated boost + fen_key/ECO soft boost), then `chess_books` fallback.
- Chess Wrapped API: `POST /api/v1/coach/retrieve` via `CHESS_COACH_ROOT` (default `workspace/experiments/chess-coach`). Soft-fails to [].
- Mobile gameCoach: hybrid merge (vector then theme pack); coach cache `v48`. Privacy: FEN+themes+SAN only.
- Grow attack/tactic coverage: `chess-coach chapter` on Art of Attack / Excelling at Chess Calculation, curate YAML, re-run synthesize.

## 2026-08-13 — PDF → knowledge summaries → PGN-linked RAG

- Order: `ingest` raw book chunks → `summarize-knowledge` (Ollama or extractive) writes short teaching cards → link masters games by ECO/theme → embed `chess_knowledge_summaries`.
- `retrieve_for_position` priority: knowledge_summary → annotated bookwalk → raw book chunks.
- CLI: `chess-coach knowledge-pipeline` orchestrates the full chain.
- Mobile still hybrid via `/api/v1/coach/retrieve`; cache `v49`.

## 2026-08-13 — Soft-key taxonomy v2 (structures → methodology)

- Replaced thin pattern catalog with 60 soft keys across 7 families:
  `structure.*`, `imbalance.*` / `positional.*`, `piece.*`, `motif.*` / `attack.*`,
  `endgame.theoretical.*` / `endgame.strategic.*`, `opening.*`, `methodology.*`.
- Sources: Flores Rios / Soltis / Kmoch / Shankland / Silman / Dvoretsky / Aagaard et al. (curated list).
- Sicilian openings collapsed to `opening.sicilian`; Scheveningen/Dragon as **structures**.
- Carlsbad replaces `structure.minority_attack`; king safety → `attack.king_safety`.
- Board detectors + theme maps + `summarize-by-key` extractors updated to match.
- Pipeline still: elect chunks → append under keys → Ollama summary per key (`summarize-by-key`).
- `export-mobile-pack` defaults to **key** summaries (`--source auto|key|chunk`) → Expo `derivedCoachPack.ts` v2 (`keyId` / `games` / longer text). Mobile retrieve scores soft-key id overlap.


## 2026-08-14 — Bookwalk FEN passages in mobile pack

Hypothesis: theme-only notes miss positions; book commentary must lock to game sections.

Outcome: `export-mobile-pack` reads `data/annotated/bookwalk/*_bookwalk.pgn` (+ sidecars), extracts per-ply book notes with `fen`/`sanLines`, assigns keys via ontology detect + chapter hints, prepends up to 4 passages per key. Pack v6 / mobile cache v64. Prefer curated sidecars; filter OCR salad.

## 2026-08-14 — Proportional align for OCR-noise book notes

When draft/OCR chapter notes have collapsed or out-of-range move labels, skip SAN anchoring. Split the mainline into N equal slices (N = distinct comments) and place comment *i* at the midpoint of slice *i*. Curated sidecars and PGN-embedded `[Book:]` layers still use exact ply labels.

## 2026-08-14 — Prefer SAN anchors over proportional FENs for mobile pack

Hypothesis: proportional midpoints invent wrong FENs → Games tab reuses the same mismatched tip.

Outcome: `align_notes_to_game` always tries SAN/fullmove first; proportional only when zero notes land. Seed teaching FENs tagged `fen-seed` in `note_fen_enrich`; mobile matcher demotes them unless near-exact FEN or SAN hit. Export-book-notes promoted 8 bookwalk PGNs with dense `[Book:]` layers to curated YAML (12 sidecars total). Pack v7 / mobile cache v68.

## 2026-08-14 — Richer mobile comment pool (pack v8)

Grow FEN-locked commentary without dumping OCR buckets:

1. Export curated YAML for every bookwalk PGN that still had `[Book:]` layers.
2. Union sidecar notes with PGN `[Book:]` plies so gaps fill.
3. SAN windows include prior + following moves; notes ship multiple `sanLines`.
4. GPT seed FENs replaced by best-matching bookwalk FENs when available (`fen-bookwalk`).
5. Caps raised (`MAX_BOOKWALK_NOTES_PER_KEY=40`, `MAX_NOTES_PER_KEY=48`). Pack v8 / mobile cache v69.

## 2026-08-14 — Metrics-voiced GPT summaries (pack v9)

Hypothesis: tip selection is metric-driven, but GPT compact/summary prose still read like diagram/FEN teaching.

Outcome:

1. `metrics_voice.adapt_*` frames each GPT note/compact with a per-key metrics hook + book principle body.
2. `export-mobile-pack` applies voice to GPT notes (bookwalk passages stay raw book text).
3. `summarize-key-ideas` IDEA_PROMPT rewritten for metrics-triggered commentary (no FEN-matching voice).
4. Mobile `metricFallbackText` uses the same book-principle voice when the pack has no tip.
5. Pack v9 / mobile cache v72.

## 2026-08-15 — Metric soft-key note schedule (mobile v77)

Hypothesis: quiet opening spam + theme-catalog tip browse misaligned notes with coach metrics.

Outcome:

1. Mobile rigid moments: eco@5, aggregate@10, MG@endgame_start, EG@advantage; live pawn-break + opp-mistake; flexible bad/praise only.
2. Tip pool = `softKeysForNoteRequest` only (metric fields / structural kinds). `allowPhaseStructure=false`.
3. `metrics_voice.py` documents `METRIC_FIELD_SOFT_KEYS` / `STRUCTURAL_KIND_SOFT_KEYS` mirroring mobile.
4. `summarize-key-ideas` prompt: opening.* = general plans; metric keys didactic.
5. Manual: run `chess-coach summarize-key-ideas` (LLM optional) + `export-mobile-pack` → copy to mobile assets.

## 2026-08-15 — Directive GPT tips + critical moments (pack v10 / v78)

1. GPT tips = impersonal directive lists (no metrics narrative, no game anecdotes); soft-key id is metric lookup.
2. Coach moments exclude inaccuracy; mistake/blunder always count (win over fixed checkpoints).
3. Opening coach input uses `formatOpeningLabel` name (OpeningPrep-style), never raw ECO.
4. `higher_threats` counts checks; `kingAttackersScore` keeps x-ray through friendly blockers.
5. Pack v10 / mobile cache v78.

## 2026-08-15 — GPT prompts ↔ BoardMetricSnap v96

Hypothesis: summarize / metrics_voice lagged hanging rename + open-file / seventh-rank snaps.

Outcome:

1. `metrics_voice` mirrors mobile `METRIC_FIELD_SOFT_KEYS` / `STRUCTURAL_KIND_SOFT_KEYS` / `BOARD_METRIC_SNAP_FIELDS` (`hanging_material_*`, `open_file_utilization`, `seventh_rank_infiltration`; no `hanging_own`/`hanging_opp`).
2. `summarize-key-ideas` IDEA_PROMPT documents coach-call soft-key selection + snap fields.
3. Mobile `scripts/dump_coach_moments.mjs` prints per-moment note-request inputs + pack tip text from annotate JSON.
