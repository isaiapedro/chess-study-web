"""Extract FEN-locked book commentary passages from bookwalk PGNs + sidecars.

Each passage is a short section (one book note on one ply), not a whole-game PGN.
Used by export-mobile-pack so mobile can match user FENs to book sections.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chess
import chess.pgn

from chess_coach.book_notes_sidecar import (
    export_sidecar_from_game,
    load_sidecar,
    resolve_sidecar,
)
from chess_coach.notes_align import (
    align_curated_notes_to_game,
    align_notes_to_game,
)
from chess_coach.ocr_chess import clean_book_note, prose_is_usable
from chess_coach.ontology.detect import detect_pattern_ids

BOOK_TAG_RE = re.compile(
    r"^\[Book:(?:(?:curated|draft)\|)?[^\]]*\]\s*",
    re.I,
)

# Chess Structures (Flores Rios) family chapters → soft key hints.
CHAPTER_KEY_HINTS: dict[str, list[str]] = {
    "family 1": ["structure.iqp"],
    "family 2": ["structure.hanging_pawns"],
    "family 3": ["structure.carlsbad"],
    "family 4": ["structure.pawn_chain", "opening.ruy_lopez", "piece.rerouting"],
    "family 5": ["structure.maroczy_bind", "structure.scheveningen"],
}

SAN_WINDOW = 10
SAN_CONTEXT_BEFORE = 3
MAX_PASSAGES_PER_GAME = 80
MIN_TEXT = 28
MIN_TEXT_CURATED = 20


@dataclass
class BookwalkPassage:
    fen: str
    fen_after: str
    san: str
    san_line: str
    text: str
    fullmove: int
    side: str
    ply: int
    eco: str
    chapter: str
    source_book: str
    game_label: str
    key_ids: list[str] = field(default_factory=list)
    curated: bool = False
    phase: str = "middlegame"


def _clip(text: str, limit: int = 520) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if len(cleaned) <= limit:
        return cleaned
    cut = cleaned[: limit - 1].rsplit(" ", 1)[0]
    return (cut or cleaned[: limit - 1]).rstrip() + "…"


def _strip_book_tag(text: str) -> str:
    t = (text or "").strip()
    t = BOOK_TAG_RE.sub("", t).strip()
    return t


def _phase_for_ply(ply: int, fen: str) -> str:
    board = chess.Board(fen)
    pieces = len(board.piece_map())
    if ply <= 16 and pieces >= 28:
        return "opening"
    if pieces <= 12:
        return "endgame"
    return "middlegame"


def _chapter_keys(chapter: str) -> list[str]:
    ch = (chapter or "").strip().lower()
    if not ch:
        return []
    for prefix, keys in CHAPTER_KEY_HINTS.items():
        if ch.startswith(prefix) or prefix in ch:
            return list(keys)
    return []


def _game_label(game: chess.pgn.Game, path: Path) -> str:
    white = (game.headers.get("White") or "").strip()
    black = (game.headers.get("Black") or "").strip()
    year = (game.headers.get("Date") or "")[:4]
    if white and black:
        label = f"{white} vs {black}"
        if year.isdigit():
            label += f" - {year}"
        return label
    return path.stem.replace("_bookwalk", "").replace("_", " ")


def _fen_at_ply(game: chess.pgn.Game, target_ply: int) -> tuple[str, str, str, list[str]]:
    """Return (fen_before, fen_after, san, san_window) for 1-based ply.

    san_window includes a few prior moves + the ply move + following moves so
    mobile SAN matching can stick on either side of the comment.
    """
    board = game.board()
    node: chess.pgn.GameNode = game
    ply = 0
    history: list[str] = []
    fen_before = board.fen()
    san = ""
    fen_after = fen_before
    while node.variations:
        nxt = node.variation(0)
        ply += 1
        move_san = board.san(nxt.move)
        if ply == target_ply:
            fen_before = board.fen()
            san = move_san
            board.push(nxt.move)
            fen_after = board.fen()
            prior = history[-SAN_CONTEXT_BEFORE:] if history else []
            sans = list(prior) + [move_san]
            walk = nxt
            tmp = board.copy()
            while walk.variations and len(sans) < SAN_WINDOW:
                wnext = walk.variation(0)
                try:
                    sans.append(tmp.san(wnext.move))
                    tmp.push(wnext.move)
                except Exception:
                    break
                walk = wnext
            return fen_before, fen_after, san, sans
        history.append(move_san)
        board.push(nxt.move)
        node = nxt
    return fen_before, fen_after, san, history


def _assign_keys(
    fen: str,
    *,
    eco: str,
    opening: str,
    chapter: str,
    text: str,
) -> list[str]:
    keys: list[str] = []
    for kid in detect_pattern_ids(fen, eco=eco, opening=opening or chapter):
        if kid not in keys:
            keys.append(kid)
    for kid in _chapter_keys(chapter):
        if kid not in keys:
            keys.append(kid)
    # Soft text tags (structure/piece names mentioned in book prose)
    blob = (text or "").lower()
    text_hits = [
        ("iqp", "structure.iqp"),
        ("isolani", "structure.iqp"),
        ("hanging pawn", "structure.hanging_pawns"),
        ("carlsbad", "structure.carlsbad"),
        ("minority", "structure.carlsbad"),
        ("maroczy", "structure.maroczy_bind"),
        ("hedgehog", "structure.hedgehog"),
        ("pawn chain", "structure.pawn_chain"),
        ("passed pawn", "structure.passed_pawn"),
        ("bishop pair", "imbalance.bishop_pair"),
        ("outpost", "positional.outpost"),
        ("prophylax", "positional.prophylaxis"),
        ("king safety", "attack.king_safety"),
        ("initiative", "attack.initiative"),
        ("greek gift", "attack.greek_gift"),
        ("sacrifice", "motif.sacrifice"),
        ("pin", "motif.pin_and_skewer"),
        ("discovered", "motif.discovered_attack"),
        ("zwischenzug", "motif.intermediate_move"),
        ("intermediate", "motif.intermediate_move"),
        ("blockade", "piece.blockade"),
        ("centraliz", "piece.centralization"),
        ("coordination", "piece.coordination"),
        ("seventh rank", "piece.seventh_rank_invasion"),
        ("simplif", "piece.simplification"),
        ("two weakness", "positional.two_weaknesses"),
        ("color complex", "positional.color_complexes"),
        ("good bishop", "imbalance.good_vs_bad_bishop"),
        ("bad bishop", "imbalance.good_vs_bad_bishop"),
        ("knight vs bishop", "imbalance.knight_vs_bishop"),
        ("space", "imbalance.space"),
        ("lucena", "endgame.theoretical.lucena"),
        ("philidor", "endgame.theoretical.philidor"),
        ("fortress", "endgame.theoretical.fortress"),
        ("opposite bishop", "endgame.strategic.opposite_bishops"),
        ("active king", "endgame.strategic.active_king"),
        ("caro", "opening.caro_kann"),
        ("sicilian", "opening.sicilian"),
        ("french", "opening.french"),
        ("king's indian", "opening.kings_indian"),
        ("queen's gambit", "opening.queens_gambit"),
        ("ruy lopez", "opening.ruy_lopez"),
        ("italian", "opening.italian"),
    ]
    for needle, kid in text_hits:
        if needle in blob and kid not in keys:
            keys.append(kid)
    return keys[:8]


def extract_passages_from_pgn(path: Path) -> list[BookwalkPassage]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    game = chess.pgn.read_game(io.StringIO(raw))
    if game is None:
        return []

    eco = (game.headers.get("ECO") or "").strip().upper()
    chapter = (game.headers.get("BookChapter") or "").strip()
    opening = (game.headers.get("Opening") or chapter).strip()
    label = _game_label(game, path)

    sidecar_path = resolve_sidecar(path)
    curated = False
    source_book = ""
    aligned = []

    if sidecar_path is not None:
        sidecar = load_sidecar(sidecar_path)
        source_book = sidecar.source_book
        chapter = sidecar.chapter or chapter
        curated = sidecar.is_curated
        notes = list(sidecar.notes)
        if curated:
            aligned = align_curated_notes_to_game(game, notes)
        else:
            # Draft/OCR: SAN/fullmove first. Proportional only if no anchors land.
            aligned = align_notes_to_game(
                game,
                notes,
                curated=False,
                proportional_fallback=True,
                skip_opening_plies=8,
            )

    # Always union PGN [Book:] layers so sidecar gaps still become FEN notes.
    extracted = export_sidecar_from_game(game)
    source_book = source_book or extracted.source_book
    chapter = chapter or extracted.chapter
    pgn_aligned = align_curated_notes_to_game(game, list(extracted.notes))
    if aligned:
        by_ply = {a.ply: a for a in aligned}
        for extra in pgn_aligned:
            if extra.ply not in by_ply and (extra.text or "").strip():
                by_ply[extra.ply] = extra
        aligned = [by_ply[k] for k in sorted(by_ply)]
    else:
        curated = False
        aligned = pgn_aligned

    out: list[BookwalkPassage] = []
    for note in aligned:
        raw_text = _strip_book_tag(note.text)
        if curated:
            text = raw_text
        else:
            text = clean_book_note(raw_text)
            if not prose_is_usable(text):
                continue
        min_len = MIN_TEXT_CURATED if curated else MIN_TEXT
        if len(text) < min_len:
            continue
        # Drop residual OCR salad (e.g. "aS Now that…")
        if re.match(r"^[a-z]{1,3}[A-Z]", text):
            continue
        # Soft-fix leading case for otherwise usable draft prose
        if text and not text[0].isupper():
            if curated:
                pass
            elif prose_is_usable(text) and len(text) >= 60:
                text = text[0].upper() + text[1:]
            else:
                continue
        fen_before, fen_after, san, sans = _fen_at_ply(game, note.ply)
        if not fen_before or not san:
            continue
        keys = _assign_keys(
            fen_before,
            eco=eco,
            opening=opening,
            chapter=chapter,
            text=text,
        )
        if not keys:
            # Still keep under a soft structure bucket via chapter or pawn_chain
            keys = _chapter_keys(chapter) or ["positional.prophylaxis"]
        out.append(
            BookwalkPassage(
                fen=fen_before,
                fen_after=fen_after,
                san=san.rstrip("?!+#"),
                san_line=" ".join(s.rstrip("?!+#") for s in sans[:SAN_WINDOW]),
                text=_clip(text),
                fullmove=note.fullmove,
                side=note.side,
                ply=note.ply,
                eco=eco,
                chapter=chapter,
                source_book=source_book or "Chess Structures",
                game_label=label,
                key_ids=keys,
                curated=curated,
                phase=_phase_for_ply(note.ply, fen_before),
            )
        )
        if len(out) >= MAX_PASSAGES_PER_GAME:
            break
    return out


def load_bookwalk_passages(
    bookwalk_dir: Path | None = None,
) -> list[BookwalkPassage]:
    root = Path(__file__).resolve().parents[3]
    directory = bookwalk_dir or (root / "data" / "annotated" / "bookwalk")
    if not directory.is_dir():
        return []
    passages: list[BookwalkPassage] = []
    for path in sorted(directory.glob("*_bookwalk.pgn")):
        try:
            passages.extend(extract_passages_from_pgn(path))
        except Exception:
            continue
    return passages


def passages_by_key(
    passages: list[BookwalkPassage],
) -> dict[str, list[BookwalkPassage]]:
    by_key: dict[str, list[BookwalkPassage]] = {}
    for p in passages:
        for kid in p.key_ids:
            by_key.setdefault(kid, []).append(p)
    for kid, rows in by_key.items():
        # Curated first, but keep draft/OCR slices for coverage.
        rows.sort(key=lambda r: (0 if r.curated else 1, -len(r.text), r.ply))
        # Dedupe identical fen+text within a key
        seen: set[str] = set()
        deduped: list[BookwalkPassage] = []
        for r in rows:
            fp = f"{r.fen}|{r.text[:80]}"
            if fp in seen:
                continue
            seen.add(fp)
            deduped.append(r)
        by_key[kid] = deduped
    return by_key


def passage_fingerprint(passage: BookwalkPassage) -> str:
    return f"{passage.fen}|{passage.san}|{passage.text[:96]}"


def passage_to_note(passage: BookwalkPassage, key_id: str, index: int) -> dict[str, Any]:
    san_clean = passage.san.rstrip("?!+#")
    line = passage.san_line or san_clean
    # Multiple SAN windows help mobile stick: full context, short tail, move alone.
    toks = [t for t in line.split() if t]
    san_lines = [line]
    if len(toks) > 4:
        san_lines.append(" ".join(toks[-4:]))
    if san_clean and san_clean not in san_lines:
        san_lines.append(san_clean)
    # Dedupe preserve order
    seen: set[str] = set()
    san_lines_u: list[str] = []
    for s in san_lines:
        if s not in seen:
            seen.add(s)
            san_lines_u.append(s)
    return {
        "id": f"bookwalk:{key_id}#{index}",
        "text": passage.text,
        "book": passage.source_book or "Bookwalk",
        "themes": [key_id.split(".", 1)[0], passage.chapter][:8],
        "ecoHints": [passage.eco] if passage.eco else [],
        "patterns": [key_id, "bookwalk"],
        "principle": f"{passage.san} — {passage.game_label}",
        "phase": passage.phase,
        "fens": [f for f in [passage.fen, passage.fen_after] if f][:4],
        "sanLines": san_lines_u[:4],
        "openings": [passage.chapter] if passage.chapter else [],
        "games": [f"{passage.game_label} [bookwalk]"],
        "specificity": 5 if passage.curated else 4,
        "features": [
            f"ply:{passage.ply}",
            f"san:{san_clean}",
            "bookwalk-passage",
            "curated" if passage.curated else "draft",
        ],
        "compact": _clip(passage.text, 160),
    }
