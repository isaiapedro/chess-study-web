# PDF chess-text parsing

Layered grammar for Quality Chess / Informator-style PDFs. Prefer **universal rules** over per-game patches.

```text
PDF text
  → normalize + strip page chrome
  → Rule B ellipsis / White two-dot
  → Rule A move heads + SAN token OCR (dict, bootstrap)
  → score-line segmenter
  → notes → PGN align
  → board-legalize SANs in note prose (unique legal only)
  → [Book:] PGN comments
```

| Layer | Module | Role |
| --- | --- | --- |
| Grammar | [`chess_text_grammar.py`](src/chess_coach/chess_text_grammar.py) | Move heads, ellipsis order, score-line cuts |
| OCR clean | [`ocr_chess.py`](src/chess_coach/ocr_chess.py) | Walk heads, clean SAN tokens, prose helpers |
| Dict | [`notation_dict.py`](src/chess_coach/notation_dict.py) | Figurine / mark / eval **lookups only** (bootstrap) |
| Notes | [`chapter.py`](src/chess_coach/chapter.py) | `extract_move_notes` → segmenter |
| Align | [`notes_align.py`](src/chess_coach/notes_align.py) | Anchor notes to mainline ply |
| Board legalize | [`note_legalize.py`](src/chess_coach/note_legalize.py) | Repair comment SANs vs board at ply |
| Fixtures | [`tests/fixtures/pdf_notes/`](tests/fixtures/pdf_notes/) | Golden anchors across games |

**Policy:** Glyph dict is **bootstrap for segmentation** (move heads / score cuts), not piece-identity fidelity in comment bodies. Piece mistakes in prose (`Rc2` vs `Nc2`, `Bxa5` vs `Qxa5`) are fixed by Layer 5 via board + variation lookahead. Structural bug → grammar rule + fixture. Do not grow per-token glyph rows for comment body fidelity.

---

## Layer 1 — Universal token grammar

### Rule A — Square ≠ move number

A move number is `\d{1,3}` + `.` / `...` **only if** the digit is not a rank after a file or hyphen:

| Illegal as move head | Why |
| --- | --- |
| `a5.` `h4.` | file + rank + sentence dot |
| `a4-a5.` `exd5.` | pawn advance / capture ending in rank+dot |
| `24.Bd3` | OK — digit not after `[a-h]` or `-` |

Pattern: `(?<![a-h\-])(?P<num>\d{1,3})\s*(?P<dots>\.\.\.|\.\.(?!\.)|\.)`  
Also: bare `...` = Black-reply head (no number).

### Rule B — Ellipsis order

1. `•{2,}` / `.•.` → `...`
2. Glue spaced `N ...` / `N . .`
3. Then `N..` + piece → White `N.` (Quality Chess OCR)

Never run White two-dot before bullet ellipsis normalize (`28 .• .Bg5` must become Black `28...Bg5`).

### Rule C — SAN tokens only

Piece OCR (`ocr_clean_move_token` / `PIECE_OCR_GLYPHS`) runs on tokens after move heads and mid-prose via `PIECE_OCR_PROSE_SAFE` — not on arbitrary English.

### Rule D — Page chrome

Strip: `a b c d e f g h`, `NNN Family …`, `Chapter N … page`, diagram rank salad.

---

## Layer 2 — Score-line segmenter

Primary cut is **structural** (`segment_score_lines`), not an 80-word keyword lookbehind.

**Open** when: start of text / after real sentence (`.` or prose bang) / score-only tail; not inside `(...)`; not immediately after scoped cues (`If`, `After`, `with`, `followed by`, …); **not** mid-sideline after `For example` / `A possible continuation is` / `manoeuvre` (those move-runs stay attached to the current note even across newlines).

**Continue** when: next label is same or +1 fullmove with only whitespace between (e.g. `27...Bf6 28.Qd2`); or next label resumes the ply after a closed `(or …)` sideline (`36.Qf2 (or 36.Rxf7+ …) 36...Rxb5` — do not open a new note on `36...Rxb5`); or soft-wrap after White label + bare reply (`37.Ra1!? Rxa1` / newline / `38.Rxa1`).

**End** when: coaching prose starts. Commentary attaches to the **last move** of the closed score line.

**Secondary:** `_retarget_through_leading_score` if note text still begins with a short score then prose — including a **bare reply SAN** after a White label (`21.bxc5` body `Nxb5` + `An interesting…` → attach to `21...Nxb5`). Align layer `_extend_anchor_through_replies` walks the same reply when the label lived only on the header. Trailing broken OCR crumbs (`25... 5`) are stripped from note text.

Annotation `?!` on a SAN is **not** a sentence break (does not open a new score line).

---

## Layer 3 — OCR dictionary

| Table | Examples |
| --- | --- |
| `PIECE_OCR_GLYPHS` | `'Wie`→`Qe`, `ltJ`/`lll`/`lil`/`ill`→`N`, `f?`→`Q`, `%'m`→`Qf8`, `E:`/`.§`/`§`→`R` |
| `OCR_ALIASES` | `?f`→`?!`, `;i;`/`;!;`/`!;!;`/`+=`→`⩲` |
| Lookahead leftovers | `W`→K/Q by file; lone `i`→`B`; `iB`→`B`; `lt>`/`'itl`→`K`; `!'l:`/`El`/`E'`→`R`; `l0`→`N`; `4o.`→`40.`; `hfl`→`Bxf1`; SAN `t`→`+` (check); `#` = checkmate (dict); `;t`→`⩲`; R/`l`→rank1, N/`l`→rank7. |

**Spaced SAN glue** (`glue_spaced_san` in `ocr_chess.py`, mirrored in viewer): after glyphs, collapse OCR spaces inside moves — `lilc 6`→`Nc6`, `fx e4`/`fic e4`→`fxe4`, `Ra 1`→`Ra1`, missing capture `x` on **adjacent** files **except leading `h`** (`fg5`→`fxg5`; `hg3`/`hc4`→`Bxg3`/`Bxc4` because Quality Chess bishop figurine OCR as `h`). Real h-pawn captures keep `x`: `hxg3` / `h xg4`. Glyph dict alone is not enough when file/rank is spaced. Bishop-as-`h` + file + OCR-rank `l`/`I`: `hfl`→`Bxf1`.

**Move-number `L` / `ll`**: `3 Llilb4` → `31.Nb4`; `ll.d5` / `ll .d5` → `11.d5` (digit `1` OCR as `l`).

**Lost piece + OCR rank digit**: after a move head, `U+FFFD` + `0`/`o`/`O` (rank `3↔0`) bootstraps an **f-file square** (`41.� 0` → `41. f3`). Dict maps `&.sq` → bishop (`Bb6`). Align matches same destination; Layer 5 fills piece / capture when unique (`f3`~`Bf3`, `Bb6`→`Rxb6`). Do **not** hardcode `Bf3 Rxb6` in OCR.

**Diagram salad after White head**: `34.m:t Kg7` → `34...Kg7` (drop non-SAN `x:y` crumb; promote next SAN to Black). Do not invent `Rf1`.

**Figurine leftover dots**: keep/unglue `h4 .Bh6` / `h4.Bh6` → `h4 Bh6` (punct rule must not treat `.Piece` / `.ih6` like sentence dots; still collapse `ll .d5` → `ll.d5` before `ll`→`11`).

**Queen back-rank `l`**: bare `fl` / `Qfl` after a move head → `Qf1` (lost queen figurine + rank `l`→`1`). Knights keep `l`→`7`; bishops/kings keep `l`→`7`.

**Bishop + file + marks, lost rank**: `ia?!` → `Ba?!` (Layer 5 fills when unique). Do not hardcode `Ba7!`.

**Rank letter `s`/`S`→`8`**: `f?ds` → `f?d8` → `Qd8` via glyph `f?`→`Q`.

**Retarget**: `_retarget_through_leading_score` walks labeled plies **and** bare replies (incl. leading `.SAN`) until a coaching opener; attaches prose to the last score move.
---

## Layer 4 — Fixture corpus

```text
tests/fixtures/pdf_notes/*_excerpt.txt
tests/fixtures/pdf_notes/*_anchors.yaml
tests/test_chess_text_grammar.py
tests/test_score_line_notes.py
```

Run: `pytest tests/ -q`

When fixing a new PDF bug: add/adjust a fixture first, then grammar or dict — not a one-off in note glue. Prefer Layer 5 for wrong/missing piece letters once the note is aligned.

---

## Layer 5 — Board-aware note legalize

Module: [`note_legalize.py`](src/chess_coach/note_legalize.py) (`legalize_note_prose`). Hooked from [`notes_align.align_notes_to_game`](src/chess_coach/notes_align.py) after ply is known (covers apply + reapply).

For each SAN-like token in aligned note prose / Vars:

1. Cursor = board **before** the anchored mainline ply; advance when a token is accepted.
2. Parenthetical sidelines fork a board copy. `(or 30.X …; but not 30.Y …)` resets to the shared decision point for each alternative; lookahead stops at `;` / `)`.
3. Candidates = destination-sharing legal moves (piece OCR confuses identity). Legal pawn pushes stay pawn-only (do not expand `g5` → `Bg5`). Bare illegal squares allow piece fill (`f4` → `Nf4`).
4. **Illegal token:** pick the unique maximizer of continuation fidelity (exact matches, pawn-strips, same-piece tours, fewer piece swaps).
5. **Legal but wrong piece:** override only when another candidate has a strictly better continuation, or a pawn-strip (`Bh4`→`h4`), or retreat of the piece that just captured (`Bxg3`→`Bf2` not `Qf2`).
6. Descriptive pawn marches `a4-a5` / `g5-g4` are not variation moves (do not advance the cursor).
7. Emit live `board.san(move)` so check/mate `+`/`#` survive rewrites.
8. Bracket sidelines `[…]` fork like `(…)`; `[39.Qe3` after `39.g3` resets to the shared white decision ply.
9. Piece→pawn OCR round-trip (`Bg5` … `Bh4` back to from-square) prefers the pawn push.

Examples: `Rc2`→`Nc2` via `Nb4`/`Nc6` tour; `Rd2`→`Qd2`; `Bh4 Bg3`→`h4 g3`; `f4`→`Nf4`; unique `Bxa5`→`Qxa5`. Ambiguous dual-legal with tied continuations stays untouched.

Tests: [`tests/test_note_legalize.py`](tests/test_note_legalize.py).

---

## Viewer mirror

[`chapter_book.template.html`](src/chess_coach/chapter_book.template.html) client cleaner mirrors Rule A lookbehind + Rule B ellipsis + dict glyphs for display-time cleanup. PGN `[Book:]` comments already include Layer 5 repairs; viewer cleanup remains display-only bootstrap.
