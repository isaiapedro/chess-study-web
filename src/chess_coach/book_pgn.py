from __future__ import annotations

import io
import re

import chess
import chess.pgn

from chess_coach.chapter import GameCitation
from chess_coach.logutil import log
from chess_coach.ocr_chess import (
    _NUMBERED_MOVE_RE,
    _SAN_TOKEN_RE,
    ocr_clean_chess,
    strip_diagrams,
)


def _citation_move_text(citation: GameCitation) -> str:
    chunks = [citation.context or ""]
    for note in citation.notes:
        chunks.append(note.text or "")
        if note.san_hint:
            side_dots = "..." if note.side == "black" else "."
            chunks.append(f"{note.fullmove}{side_dots} {note.san_hint}")
    return "\n".join(chunks)


def _prepare_score_text(text: str) -> str:
    cleaned = strip_diagrams(ocr_clean_chess(text or ""))
    # Drop parenthetical sidelines so greedy SAN parse stays on main line
    cleaned = re.sub(r"\([^)]{0,260}\)", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_playable_sans(text: str, *, max_fails: int = 14) -> list[str]:
    """Greedy legal SAN stream from book OCR (numbered moves + replies)."""
    cleaned = _prepare_score_text(text)
    if not cleaned:
        return []

    board = chess.Board()
    sans: list[str] = []
    fail_streak = 0
    pos = 0

    def try_token(raw: str) -> bool:
        nonlocal fail_streak
        token = raw.replace("0-0-0", "O-O-O").replace("0-0", "O-O")
        try:
            move = board.parse_san(token)
        except ValueError:
            fail_streak += 1
            return False
        san = board.san(move)
        board.push(move)
        sans.append(san)
        fail_streak = 0
        return True

    for match in _NUMBERED_MOVE_RE.finditer(cleaned):
        gap = cleaned[pos : match.start()]
        for tm in _SAN_TOKEN_RE.finditer(gap):
            try_token(tm.group(0))
            if fail_streak >= max_fails and sans:
                return sans
        try_token(match.group("san"))
        if fail_streak >= max_fails and sans:
            return sans
        pos = match.end()

    for tm in _SAN_TOKEN_RE.finditer(cleaned[pos:]):
        try_token(tm.group(0))
        if fail_streak >= max_fails and sans:
            break
    return sans


def reconstruct_pgn_from_citation(
    citation: GameCitation,
    *,
    min_plies: int = 8,
) -> str | None:
    """
    Best-effort PGN from book section text around the citation.
    Returns None if fewer than min_plies legal moves could be replayed.
    """
    text = _citation_move_text(citation)
    sans = extract_playable_sans(text)
    if len(sans) < min_plies:
        log(
            "Book PGN: only %d legal ply(s) from text (need %d) for %s vs %s",
            len(sans),
            min_plies,
            citation.white,
            citation.black,
        )
        return None

    game = chess.pgn.Game()
    game.headers["Event"] = citation.event or "Book score (reconstructed)"
    game.headers["Site"] = citation.source_book or "book"
    game.headers["Date"] = f"{citation.year}.??.??"
    game.headers["White"] = citation.white
    game.headers["Black"] = citation.black
    game.headers["Result"] = "*"
    game.headers["Annotator"] = "chess-coach book-text reconstruct"
    game.headers["Source"] = "book PDF/text"

    node: chess.pgn.GameNode = game
    board = game.board()
    for san in sans:
        move = board.parse_san(san)
        node = node.add_variation(move)
        board.push(move)

    handle = io.StringIO()
    print(game, file=handle, end="\n\n")
    pgn = handle.getvalue()
    log(
        "Book PGN: reconstructed %d plies for %s vs %s %s",
        len(sans),
        citation.white,
        citation.black,
        citation.year,
    )
    return pgn
