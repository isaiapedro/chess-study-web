from __future__ import annotations

from chess_coach.rag.summarize_knowledge import (
    _eco_hints,
    _extractive_summary,
    chunk_is_teachable,
    summary_is_teachable,
)


def test_extractive_summary_keeps_substance():
    raw = (
        "When the kingside opens, bring more attackers than defenders before the final break. "
        "Quiet pawn moves hand the initiative back. "
        "Trade only if the attack is gone."
    )
    text = _extractive_summary(raw, ["king safety", "attack"])
    assert "attackers" in text.lower()
    assert "Themes:" in text


def test_eco_hints_from_themes():
    ecos = _eco_hints("plan text", ["sicilian", "king safety"])
    assert any(e.startswith("B") for e in ecos)


def test_chunk_is_teachable_rejects_toc():
    toc = "Contents Foreword 1 2 3 5 6 7 9 12 36 51 69 86 103 " * 5
    assert not chunk_is_teachable(toc)
    good = (
        "Attack the base of the pawn chain and play on the side where your chain points. "
        "When the centre is locked, improve the worst-placed piece before forcing a break. "
        "Rooks belong on open files once the structure opens."
    )
    assert chunk_is_teachable(good)
    assert summary_is_teachable(good)
