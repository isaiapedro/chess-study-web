"""
Diagram ↔ score FEN cross-check.

When a PDF page has a board diagram, an image reader (e.g. ChessCog) can emit a
FEN. Compare that to ``board.fen()`` from the parsed mainline at the same cue
(diagram caption / \"position of interest\") to catch move-desync early.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import chess


@dataclass(frozen=True)
class FenMismatch:
    ply: int
    parsed_fen: str
    diagram_fen: str
    reason: str


def normalize_fen_position(fen: str) -> str:
    """Compare piece placement + side to move only (ignore clocks / EP noise)."""
    parts = (fen or "").split()
    if len(parts) < 2:
        return (fen or "").strip()
    return f"{parts[0]} {parts[1]}"


def compare_parsed_to_diagram(
    parsed_fen: str,
    diagram_fen: str,
    *,
    ply: int = 0,
) -> FenMismatch | None:
    """
    Return a mismatch when placement/side differ; ``None`` when they agree.

    Empty diagram FEN skips the check (reader unavailable).
    """
    if not (diagram_fen or "").strip():
        return None
    left = normalize_fen_position(parsed_fen)
    right = normalize_fen_position(diagram_fen)
    if left == right:
        return None
    return FenMismatch(
        ply=ply,
        parsed_fen=left,
        diagram_fen=right,
        reason="diagram FEN disagrees with parsed board",
    )


def board_fen_at_ply(game: chess.pgn.Game, ply: int) -> str:
    """FEN after ``ply`` mainline half-moves (0 = start)."""
    board = game.board()
    if ply <= 0:
        return board.fen()
    node: chess.pgn.GameNode = game
    for _ in range(ply):
        if not node.variations:
            break
        node = node.variation(0)
        board.push(node.move)
    return board.fen()


DiagramReader = Callable[[bytes], str]
"""Callable: diagram image bytes → FEN string (empty if undecodable)."""


def crosscheck_diagrams(
    game: chess.pgn.Game,
    cues: list[tuple[int, bytes]],
    reader: DiagramReader,
) -> list[FenMismatch]:
    """
    For each ``(ply, image_bytes)`` cue, read diagram FEN and compare to the
    parsed game at that ply.

    Pass a real ChessCog (or similar) wrapper as ``reader``. This module does
    not bundle an OCR model — it only defines the sync contract.
    """
    mismatches: list[FenMismatch] = []
    for ply, image in cues:
        diagram_fen = (reader(image) or "").strip()
        parsed = board_fen_at_ply(game, ply)
        hit = compare_parsed_to_diagram(parsed, diagram_fen, ply=ply)
        if hit is not None:
            mismatches.append(hit)
    return mismatches
