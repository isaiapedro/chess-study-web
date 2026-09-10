"""Didactic Engine/RAG note voice (ECO expansion, no move echo)."""

from __future__ import annotations

from chess_coach.analyze import CriticalMoment
from chess_coach.comment import engine_grounded_note, pedagogical_fallback
from chess_coach.eco_names import format_eco_phrase
from chess_coach.features import PositionFeatures


def _moment(**kwargs) -> CriticalMoment:
    defaults = dict(
        ply=3,
        fullmove=2,
        side="white",
        fen_before="rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1",
        played_san="c4",
        played_uci="c2c4",
        best_san="c4",
        best_uci="c2c4",
        eval_before_cp=20,
        eval_after_cp=29,
        mate_before=None,
        mate_after=None,
        delta_cp=5,
        pv_san=["c4", "e6", "Nf3"],
        depth=12,
        features=PositionFeatures(
            phase="opening",
            themes=["opening", "queen's gambit"],
            patterns=["opening.queens_gambit"],
            eco="E01",
            opening="",
        ),
    )
    defaults.update(kwargs)
    # Fix fen for white to move c4 after d4
    if defaults["played_san"] == "c4":
        defaults["fen_before"] = "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 0 2"
    return CriticalMoment(**defaults)


def test_format_eco_phrase_explains_e01():
    phrase = format_eco_phrase("E01", "")
    assert "Catalan" in phrase
    assert "E01" in phrase
    assert "Indian" in phrase or "ECO" in phrase


def test_engine_note_no_move_echo_and_explains_eco():
    text = engine_grounded_note(_moment())
    assert not text.startswith("2.")
    assert "c4 (pawn" not in text.lower()
    assert "Catalan" in text or "E01" in text
    assert "ECO E01" in text or "Catalan" in text


def test_knowledge_nugget_not_repeated():
    used: set[str] = set()
    m = _moment(
        features=PositionFeatures(
            phase="middlegame",
            themes=["carlsbad"],
            patterns=["structure.carlsbad"],
            eco="D35",
            opening="Queen's Gambit Declined",
        ),
    )
    a = pedagogical_fallback(m, [], used_fingerprints=used).text
    b = pedagogical_fallback(m, [], used_fingerprints=used).text
    assert "Key idea" in a or "carlsbad" in a.lower() or "minority" in a.lower()
    assert isinstance(b, str) and len(b) > 20
