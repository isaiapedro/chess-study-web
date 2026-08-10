from __future__ import annotations

import re

import chess

from chess_coach.analyze import CriticalMoment


SAN_PATTERN = re.compile(
    r"\b(?:O-O-O|O-O|[KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b"
)


def extract_move_tokens(text: str) -> list[str]:
    return SAN_PATTERN.findall(text)


def _normalize_san(san: str) -> str:
    return san.rstrip("+#").replace("0-0-0", "O-O-O").replace("0-0", "O-O")


def validate_commentary(
    moment: CriticalMoment,
    text: str,
    *,
    attach_notes: bool = True,
) -> tuple[str, list[str]]:
    """Return possibly annotated text and list of warnings."""
    warnings: list[str] = []
    allowed = {_normalize_san(s) for s in moment.pv_san}
    allowed.add(_normalize_san(moment.played_san))
    if moment.best_san:
        allowed.add(_normalize_san(moment.best_san))

    board = chess.Board(moment.fen_before)
    legal_sans = {_normalize_san(board.san(move)) for move in board.legal_moves}
    # Destination / origin squares from the played move (e.g. "on b5") are not SANs.
    try:
        mv = board.parse_san(moment.played_san)
        allowed.add(chess.square_name(mv.to_square))
        allowed.add(chess.square_name(mv.from_square))
    except ValueError:
        pass

    for token in extract_move_tokens(text):
        norm = _normalize_san(token)
        if norm in allowed or norm in legal_sans:
            continue
        # Bare square names (a1–h8) in prose are usually coordinates, not move claims.
        if re.fullmatch(r"[a-h][1-8]", norm):
            continue
        warnings.append(f"Unverified move mention: {token}")

    if warnings and attach_notes:
        note = "\n\n> Validation notes: " + "; ".join(warnings)
        return text + note, warnings
    return text, warnings
