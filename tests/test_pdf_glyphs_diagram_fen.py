"""Font-glyph and diagram FEN helper contracts."""

from __future__ import annotations

import chess
import chess.pgn

from chess_coach.diagram_fen import (
    compare_parsed_to_diagram,
    crosscheck_diagrams,
    normalize_fen_position,
)
from chess_coach.pdf_font_glyphs import (
    extract_page_text_with_font_glyphs,
    is_chess_figurine_font,
    map_figurine_char,
    rewrite_spans_with_font_glyphs,
)


def test_chess_font_detection_and_map():
    assert is_chess_figurine_font("ChessMerida")
    assert is_chess_figurine_font("ABCDEE+ChessAlpha")
    assert not is_chess_figurine_font("TimesNewRoman")
    assert map_figurine_char("n", "ChessMerida") == "N"
    assert map_figurine_char("n", "TimesNewRoman") == "n"


def test_rewrite_spans_maps_only_figurine_fonts():
    spans = [
        ("1.", "TimesNewRoman"),
        ("n", "ChessMerida"),
        ("f6", "TimesNewRoman"),
    ]
    assert rewrite_spans_with_font_glyphs(spans) == "1.Nf6"


def test_extract_page_uses_dict_when_figurine_present():
    class FakePage:
        def get_text(self, mode="text"):
            if mode == "dict":
                return {
                    "blocks": [
                        {
                            "type": 0,
                            "lines": [
                                {
                                    "spans": [
                                        {"text": "8...", "font": "Helvetica"},
                                        {"text": "q", "font": "ChessMerida"},
                                        {"text": "d5", "font": "Helvetica"},
                                    ]
                                }
                            ],
                        }
                    ]
                }
            return "8...qd5"

    assert extract_page_text_with_font_glyphs(FakePage()) == "8...Qd5"


def test_diagram_fen_compare_and_crosscheck():
    start = chess.Board().fen()
    assert compare_parsed_to_diagram(start, start) is None
    bad = compare_parsed_to_diagram(start, "8/8/8/8/8/8/8/8 w - - 0 1", ply=3)
    assert bad is not None and bad.ply == 3
    assert normalize_fen_position(start).endswith(" w")

    game = chess.pgn.Game()
    mismatches = crosscheck_diagrams(
        game,
        [(0, b"fake-png")],
        reader=lambda _b: chess.Board().fen(),
    )
    assert mismatches == []
    mismatches = crosscheck_diagrams(
        game,
        [(0, b"fake-png")],
        reader=lambda _b: "7k/8/8/8/8/8/8/7K w - - 0 1",
    )
    assert len(mismatches) == 1
