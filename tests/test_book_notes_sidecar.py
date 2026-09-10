"""Curated sidecar + book-layer tag helpers."""

from __future__ import annotations

from pathlib import Path

from chess_coach.book_notes_sidecar import (
    book_tag_prefix,
    load_sidecar,
    parse_book_kind,
    save_sidecar,
    BookNotesSidecar,
)
from chess_coach.chapter import BookMoveNote
from chess_coach.viewer import _split_layers


def test_book_tag_prefix_and_parse():
    assert book_tag_prefix("Chess Structures", kind="curated").startswith(
        "[Book:curated|Chess Structures]"
    )
    kind, _ = parse_book_kind("[Book:curated|X] hello")
    assert kind == "curated"
    kind, _ = parse_book_kind("[Book:draft|X] hello")
    assert kind == "draft"
    kind, _ = parse_book_kind("[Book:Old Title] hello")
    assert kind == "legacy"


def test_split_layers_strips_curated_tag():
    book, engine, _vars, kind = _split_layers(
        "[Book:curated|Demo] Opening imprecision. | [Engine/RAG] eval note"
    )
    assert kind == "curated"
    assert "Opening imprecision" in book
    assert "curated" not in book.lower() or "Opening" in book
    assert "eval note" in engine or "Engine" in engine


def test_sidecar_roundtrip(tmp_path: Path):
    path = tmp_path / "game.book_notes.yaml"
    data = BookNotesSidecar(
        source="curated",
        source_book="Demo",
        chapter="Family 4",
        preamble="What this game teaches\n\nA short intro.",
        notes=[
            BookMoveNote(fullmove=8, side="black", san_hint="Bd6", text="Imprecision note.")
        ],
    )
    save_sidecar(path, data)
    loaded = load_sidecar(path)
    assert loaded.is_curated
    assert loaded.preamble.startswith("What this")
    assert loaded.notes[0].san_hint == "Bd6"


def test_curated_sidecar_skips_ocr_mangle(tmp_path: Path):
    from chess_coach.book_walkthrough import reapply_book_layer
    from chess_coach.book_notes_sidecar import citation_from_sidecar
    import chess.pgn
    import io

    pgn_text = """
[Event "Test"]
[White "A"]
[Black "B"]
[Result "*"]

1. d4 d5 2. c4 e6 *
"""
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    assert game is not None
    side = BookNotesSidecar(
        source="curated",
        source_book="Demo Guide",
        chapter="Family 4",
        preamble="What this game teaches\n\nBlack can own the open file.",
        notes=[
            BookMoveNote(
                fullmove=1,
                side="white",
                san_hint="d4",
                text="Pause and assess\n\nBlack's rooks sit on the only open file.",
            )
        ],
    )
    path = tmp_path / "demo_bookwalk.pgn"
    path.write_text(pgn_text, encoding="utf-8")
    side_path = tmp_path / "demo_bookwalk.book_notes.yaml"
    save_sidecar(side_path, side)
    cite = citation_from_sidecar(side)
    out, n = reapply_book_layer(game, cite, book_kind="curated", pgn_path=path)
    assert n >= 1
    node = out.variation(0)
    comment = node.comment or ""
    assert "sit on the only open file" in comment
    assert "s it" not in comment
    assert "Pause and assess" in comment
    book, _, _, kind = _split_layers(comment)
    assert kind == "curated"
    assert "sit on" in book
    assert "Pause and assess" in book
    assert "\n\n" in book
