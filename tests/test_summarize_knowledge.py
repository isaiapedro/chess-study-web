from __future__ import annotations

from types import SimpleNamespace

from chess_coach.rag.summarize_knowledge import (
    _eco_hints,
    _extractive_summary,
    chunk_is_teachable,
    evenly_spaced_indices,
    select_summary_source_chunks,
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


def test_evenly_spaced_indices_cover_ends():
    idxs = evenly_spaced_indices(100, 5)
    assert idxs[0] == 0
    assert idxs[-1] == 99
    assert len(idxs) == 5
    assert len(set(idxs)) == 5


def test_select_summary_source_chunks_spans_whole_book():
    good = (
        "Attack the base of the pawn chain and play on the side where your chain points. "
        "When the centre is locked, improve the worst-placed piece before forcing a break. "
        "Rooks belong on open files once the structure opens."
    )
    junk = "Contents Foreword 1 2 3 5 6 7 9 12 36 51 69 86 103 " * 5
    chunks = []
    for i in range(40):
        text = junk if i % 7 == 0 else good
        chunks.append(
            SimpleNamespace(text=text, chapter="body" if i < 20 else "chapter 2")
        )
    picked = select_summary_source_chunks(chunks, 8)
    assert len(picked) == 8
    chapters = {c.chapter for c in picked}
    assert "body" in chapters and "chapter 2" in chapters


def test_select_summary_source_chunks_unlimited():
    good = (
        "Attack the base of the pawn chain and play on the side where your chain points. "
        "When the centre is locked, improve the worst-placed piece before forcing a break. "
        "Rooks belong on open files once the structure opens."
    )
    chunks = [SimpleNamespace(text=good, chapter="body") for _ in range(5)]
    assert len(select_summary_source_chunks(chunks, 0)) == 5
    assert len(select_summary_source_chunks(chunks, None)) == 5
