"""Golden score-line note anchors from PDF book excerpts."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from chess_coach.chapter import extract_move_notes

FIXTURES = Path(__file__).parent / "fixtures" / "pdf_notes"


def _cases() -> list[tuple[str, Path, Path]]:
    out: list[tuple[str, Path, Path]] = []
    for anchors in sorted(FIXTURES.glob("*_anchors.yaml")):
        stem = anchors.name.replace("_anchors.yaml", "")
        excerpt = FIXTURES / f"{stem}_excerpt.txt"
        if excerpt.is_file():
            out.append((stem, excerpt, anchors))
    return out


@pytest.mark.parametrize("stem,excerpt_path,anchors_path", _cases())
def test_score_line_anchors(stem: str, excerpt_path: Path, anchors_path: Path):
    excerpt = excerpt_path.read_text(encoding="utf-8")
    spec = yaml.safe_load(anchors_path.read_text(encoding="utf-8"))
    expect = spec["expect"]
    _pre, notes = extract_move_notes(excerpt)
    assert notes, f"{stem}: no notes extracted"

    for exp in expect:
        fm = exp["fullmove"]
        side = exp["side"]
        needle = (exp.get("san_contains") or exp.get("san") or "").lower()
        prefix = exp["text_prefix"]
        hits = [
            n
            for n in notes
            if n.fullmove == fm
            and n.side == side
            and (not needle or needle in (n.san_hint or "").lower())
        ]
        assert hits, (
            f"{stem}: missing {fm} {side} ~{needle!r}; "
            f"have={[(n.fullmove, n.side, n.san_hint) for n in notes]}"
        )
        text = " ".join(hits[0].text.split())
        assert prefix in text or text.startswith(prefix), (
            f"{stem}: {fm} {side} text {text[:80]!r} missing prefix {prefix!r}"
        )


def test_mcshane_r5c7_not_on_a4():
    excerpt = (FIXTURES / "mcshane_ch14_excerpt.txt").read_text(encoding="utf-8")
    _pre, notes = extract_move_notes(excerpt)
    a4 = next(n for n in notes if n.fullmove == 26 and n.side == "white")
    r5 = next(n for n in notes if n.fullmove == 26 and n.side == "black")
    assert "Black is not ready" not in a4.text
    assert "Black is not ready" in r5.text
    assert "Getting ready" in a4.text
    assert "passed pawns decide the game" in r5.text
    assert "E:" not in r5.text
    assert "R5c7" in r5.text or "Rb7" in r5.text


def test_mcshane_bf2_no_trailing_broken_move():
    excerpt = (FIXTURES / "mcshane_ch14_excerpt.txt").read_text(encoding="utf-8")
    _pre, notes = extract_move_notes(excerpt)
    bf2 = next(n for n in notes if n.fullmove == 25 and n.side == "white")
    assert bf2.text.rstrip().endswith("queenside.")
    assert "25..." not in bf2.text


def test_mcshane_qf8_rook_not_e_colon():
    excerpt = (FIXTURES / "mcshane_ch14_excerpt.txt").read_text(encoding="utf-8")
    _pre, notes = extract_move_notes(excerpt)
    qf8 = next(n for n in notes if n.fullmove == 24 and n.side == "black")
    assert "E:" not in qf8.text
    assert "Rb3" in qf8.text or "Ra3" in qf8.text or "Rc3" in qf8.text


def test_variation_continuation_stays_on_parent_note():
    """'A possible continuation is 26… 28.Qd2 Rc5' must not open a new 28.Qd2 note."""
    from chess_coach.ocr_chess import ocr_clean_chess

    raw = """
23.f3!
A simple move that should be remembered. It provides extra support to the chain.
As McShane points out, 23.a4? is bad. A possible continuation is 26.Rc1 Rxc1 27.Qxc1 Rc8
28.Qd2 Rc5 with level chances.
23...Rac8 24.Bd3
Something to note is how White can improve slowly.
"""
    _pre, notes = extract_move_notes(ocr_clean_chess(raw))
    f3 = next(n for n in notes if n.fullmove == 23 and n.side == "white")
    assert "level chances" in f3.text
    assert "28. Qd2" in f3.text or "28.Qd2" in f3.text.replace(" ", "")
    assert not any(
        n.fullmove == 28 and "level chances" in n.text and "Preparing" not in n.text
        for n in notes
    )


def test_nxb5_comment_not_on_bxc5():
    """21...Nxb5 coaching must not park on White's 21.bxc5."""
    import chess.pgn

    from chess_coach.notes_align import align_notes_to_game

    excerpt = (FIXTURES / "mcshane_m21_excerpt.txt").read_text(encoding="utf-8")
    _pre, notes = extract_move_notes(excerpt)
    interesting = next(n for n in notes if "interesting alternative" in n.text.lower())
    assert interesting.fullmove == 21
    assert interesting.side == "black"
    assert "nxb5" in (interesting.san_hint or "").lower()

    game_path = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "annotated"
        / "bookwalk"
        / "Magnus_Carlsen_vs_Luke_McShane_2009_bookwalk.pgn"
    )
    if not game_path.is_file():
        pytest.skip("Carlsen-McShane bookwalk PGN not present")
    game = chess.pgn.read_game(game_path.open(encoding="utf-8"))
    assert game is not None
    aligned = align_notes_to_game(game, notes)
    hit = next(a for a in aligned if "interesting alternative" in a.text.lower())
    assert hit.fullmove == 21
    assert hit.side == "black"
    assert hit.san.lower().startswith("nxb5")
    assert not any(
        a.fullmove == 21 and a.side == "white" and "interesting alternative" in a.text.lower()
        for a in aligned
    )
