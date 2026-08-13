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
        preamble="Learning objective: test.",
        notes=[
            BookMoveNote(fullmove=8, side="black", san_hint="Bd6", text="Imprecision note.")
        ],
    )
    save_sidecar(path, data)
    loaded = load_sidecar(path)
    assert loaded.is_curated
    assert loaded.preamble.startswith("Learning")
    assert loaded.notes[0].san_hint == "Bd6"
