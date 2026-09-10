from __future__ import annotations

import io

import chess.pgn

from chess_coach.chapter import BookMoveNote
from chess_coach.notes_align import (
    align_notes_proportionally,
    align_notes_to_game,
    ocr_labels_look_noisy,
    proportional_ply_slots,
)


def _long_game() -> chess.pgn.Game:
    # 20 plies
    moves = "1.e4 e5 2.Nf3 Nc6 3.Bb5 a6 4.Ba4 Nf6 5.O-O Be7 6.Re1 b5 7.Bb3 d6 8.c3 O-O 9.h3 Nb8 10.d4 Nbd7"
    g = chess.pgn.read_game(io.StringIO(moves + " *"))
    assert g is not None
    return g


def test_proportional_slots_fifteen():
    slots = proportional_ply_slots(15, 60)
    assert len(slots) == 15
    assert slots[0] < slots[-1]
    assert slots == sorted(slots)
    # roughly every 4 plies
    assert slots[0] <= 4
    assert slots[-1] >= 56


def test_align_proportionally_spreads_comments():
    game = _long_game()
    notes = [
        BookMoveNote(fullmove=0, side="white", san_hint="", text="First idea about the centre fight and development plans for both sides here.")
        for _ in range(5)
    ]
    # same collapsed fullmove → noisy
    assert ocr_labels_look_noisy(notes, [(i, i, "white", "e4") for i in range(1, 21)])
    aligned = align_notes_proportionally(game, notes, skip_opening_plies=0)
    assert len(aligned) == 5
    plies = [a.ply for a in aligned]
    assert plies == sorted(plies)
    assert plies[-1] - plies[0] >= 8


def test_ocr_path_falls_back_to_proportional():
    game = _long_game()
    notes = [
        BookMoveNote(
            fullmove=99,
            side="white",
            san_hint="Zz9",
            text=f"Comment number {i} explaining the plan and the structure for this chapter section.",
        )
        for i in range(6)
    ]
    aligned = align_notes_to_game(
        game, notes, curated=False, proportional_fallback=True
    )
    assert len(aligned) >= 4
    plies = [a.ply for a in aligned]
    assert max(plies) - min(plies) >= 4
