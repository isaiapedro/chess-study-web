"""OCR spaced-SAN glue + Informator aliases (permanent Layer 3 rules)."""

from __future__ import annotations

import re

from chess_coach.ocr_chess import glue_spaced_san, ocr_clean_chess


def test_lilc_spaced_rank_to_knight():
    assert "Nc6" in ocr_clean_chess("32.lilc 6 lilg6")
    assert "Nc2" in ocr_clean_chess("If28.lilc 2 McShane")
    assert "lilc" not in ocr_clean_chess("lilc 6")


def test_move_number_l_before_lil_glyph():
    assert ocr_clean_chess("3 Llilb4").startswith("31.")
    assert "Nb4" in ocr_clean_chess("3 Llilb4")
    cleaned = ocr_clean_chess("30 ... lllg8 3 Llilb4 llle7 32.lilc 6")
    assert "31. Nb4" in cleaned or "31.Nb4" in cleaned.replace(" ", "")
    assert "32. Nc6" in cleaned or "32.Nc6" in cleaned.replace(" ", "")


def test_fxe4_spaced_and_fic_ocr():
    assert glue_spaced_san("fx e4") == "fxe4"
    assert glue_spaced_san("fic e4") == "fxe4"
    assert "fxe4" in ocr_clean_chess("29. fx e4")
    assert "fxe4" in ocr_clean_chess("31...fic e4")


def test_pawn_capture_missing_x():
    assert glue_spaced_san("fg5") == "fxg5"
    assert glue_spaced_san("ee4") == "ee4"
    # leading h + square = bishop figurine, not missing-x pawn
    assert glue_spaced_san("hg3") == "Bxg3"
    assert glue_spaced_san("hxg3") == "hxg3"
    assert "hxg4" in ocr_clean_chess("32.h xg4")
    assert "Bxg3" in ocr_clean_chess("32.hg3")
    assert "hxg3" not in ocr_clean_chess("32.hg3")


def test_bishop_figurine_as_h_before_square():
    assert glue_spaced_san("hc4") == "Bxc4"
    assert glue_spaced_san(".hc4") == "Bxc4"
    assert glue_spaced_san("hg3") == "Bxg3"
    assert "Bxc4" in ocr_clean_chess("32. hc4 Rxc4")
    assert "hc4" not in ocr_clean_chess("32. hc4 Rxc4")
    assert glue_spaced_san("hd5") == "Bxd5"


def test_queen_figurine_brace_salad():
    assert "Qg7" in ocr_clean_chess("'{!ig7")
    assert "'{!" not in ocr_clean_chess("32.hg3 '{!ig7 33.Bf2")


def test_illfl_to_nf7_and_score_split():
    from chess_coach.chapter import extract_move_notes

    # ill + fl → Nfl → Nf7 (knight l→7). illf1 keeps digit 1 (Layer 5 if wrong).
    assert "Nf7" in ocr_clean_chess("illfl?!")
    assert "Nf1" in ocr_clean_chess("illf1?!") or "Nf7" in ocr_clean_chess("illf1?!")
    assert "illf" not in ocr_clean_chess("30... illfl?!")
    raw = """
30.fxe4?!
Better was 30.axb6! forcing a weakness on b6, rather than a7; 30...axb6 31.fxe4± is similar to the game.
30... illfl?!
Once again allowing White to create a weakness on b6. The correct way was 30...bxa5
31.\ufffd xa5 with a playable position for Black.
31.axb6
And as I said ten moves ago, only White benefits.
"""
    _pre, notes = extract_move_notes(raw)
    white = next(n for n in notes if n.fullmove == 30 and n.side == "white")
    black = next(n for n in notes if n.fullmove == 30 and n.side == "black")
    assert "Better was 30" in white.text
    assert "Once again" not in white.text
    assert "illf" not in white.text
    assert "Once again" in black.text
    assert "Nf7" in (black.san_hint or "") or black.san_hint.lower().startswith("nf7")
    assert "Qxa5" in black.text.replace(" ", "")
    assert "playable position" in black.text
    assert not any(
        n.fullmove == 31 and n.side == "white" and "xa5" in (n.san_hint or "").lower()
        for n in notes
    )


def test_replacement_char_before_capture_is_queen():
    out = ocr_clean_chess("31 .\ufffd xa5 with a playable")
    assert "Qxa5" in out.replace(" ", "")
    assert "\ufffd" not in out
    assert re.search(r"\b31\.\s*xa5\b", out) is None


def test_score_line_ffe2_ttlc4_and_kh1_caption():
    """Diagram score-line OCR must open Nc4 / Kh1 so prose is not dumped on axb6."""
    from chess_coach.chapter import extract_move_notes

    raw = """
30... illfl?!
Once again allowing White to create a weakness on b6. The correct way was 30...bxa5
31.\ufffd xa5 with a playable position for Black.
31.axb6 axb6 32.ffe2 !:ib7 33.ttlc4:t:
a b c d e f g h
And as I said ten moves ago, only White is going to benefit from queenside play.
33 ... f?ds 34.m:t @g7 35.@hi
Again, White can slowly improve his position, while Black's pieces are cramped.
As McShane points out, 35.axb6? gives away most of the advantage after: 35...Rxb6
35... Be8 36.Qb2 Nh6?
And as usually happens, passive defence leads to mistakes.
"""
    cleaned = ocr_clean_chess(raw)
    assert "Qe2" in cleaned
    assert "Rb7" in cleaned
    assert "Nc4" in cleaned
    assert "Qd8" in cleaned
    assert "Kh1" in cleaned
    assert "ffe2" not in cleaned
    assert "ttlc4" not in cleaned.lower()
    assert "@hi" not in cleaned
    assert "f?ds" not in cleaned
    # m:t is diagram salad left for Layer 5 / skipped in score walk — not Rf1 hardcode

    _pre, notes = extract_move_notes(raw)
    assert not any(n.fullmove == 31 and n.side == "white" for n in notes)
    nc4 = next(n for n in notes if n.fullmove == 33 and n.side == "white")
    assert "And as I said" in nc4.text
    assert "f?ds" not in nc4.text
    kh1 = next(n for n in notes if n.fullmove == 35 and n.side == "white")
    assert "Again, White" in kh1.text
    assert "f?ds" not in kh1.text
    assert "Khi" not in kh1.text
    assert "@" not in kh1.text


def test_replacement_char_before_square_is_queen():
    raw = "30.g4 (or 30.\ufffdd2 g4; but not 30.\ufffde2?! g4)"
    out = ocr_clean_chess(raw)
    assert "30. Qd2" in out or "30.Qd2" in out.replace(" ", "")
    assert "30. Qe2" in out or "30.Qe2" in out.replace(" ", "")
    assert "\ufffd" not in out
    assert re.search(r"\b30\.\s*d2\b", out) is None


def test_qf1_ocr_and_align_to_qf2():
    """38.�fl?! → Qf1; align to game Qf2. Leading prose before If kept."""
    from pathlib import Path

    import chess.pgn

    from chess_coach.chapter import BookMoveNote
    from chess_coach.notes_align import _san_similar, align_notes_to_game
    from chess_coach.ocr_chess import ocr_clean_chess, prose_is_usable, split_movelist_and_prose

    assert "Qf1" in ocr_clean_chess("38.\ufffdfl?!")
    assert "Qf1" in ocr_clean_chess("38.fl?!")
    assert _san_similar("Qf1", "Qf2")
    assert _san_similar("Qg3", "Rg3")
    assert _san_similar("Qf3", "Bf3")

    _prefix, prose = split_movelist_and_prose(
        "Making things easier for White.\n\nIf 47... dxc5?? 48. d6"
    )
    assert "Making things easier" in prose
    assert prose_is_usable(prose)

    pgn = Path("data/annotated/bookwalk/Magnus_Carlsen_vs_Luke_McShane_2009_bookwalk.pgn")
    if not pgn.exists():
        return
    game = chess.pgn.read_game(pgn.open())
    notes = [
        BookMoveNote(
            fullmove=38,
            side="white",
            san_hint="Qf1?!",
            text="We are close to the time control on move 40, and Carlsen makes some imprecisions.",
        ),
        BookMoveNote(
            fullmove=47,
            side="black",
            san_hint="Qg3",
            text="Making things easier for White.\n\nIf 47... dxc5?? 48. d6 Qc7",
        ),
    ]
    aligned = align_notes_to_game(game, notes)
    sans = {a.san for a in aligned}
    assert "Qf2" in sans
    assert "Rg3" in sans

    """Qe7 weak/force salad: lt>/4o/!'l:/hfl; # stays mate; same-ply reset."""
    from pathlib import Path

    import chess.pgn

    from chess_coach.note_legalize import legalize_note_prose

    raw = (
        "Weak is: 37 ... \ufffdd7? 38.l0x e5! dxe5 39.\ufffdxe5t lt>g8 4o.id4+- "
        "Black loses by force after: 37 ... !'l:xb6 38.\ufffdf2! "
        "(threatening \ufffdf8# as well as l0xb6) 38... hb5 "
        "(38... !'l:xb5?? 39.\ufffdf8#) 39.l0xb6! ixd3 40.l0xc8 hfl "
        "41.\ufffda7t! 'itlh8 42.E:b8 (42... id3? 43.l0xd6)"
    )
    cleaned = ocr_clean_chess(raw)
    assert "Qd7?" in cleaned
    assert "Kg8" in cleaned
    assert "lt>" not in cleaned
    assert "40.Bd4" in cleaned.replace(" ", "") or "40. Bd4" in cleaned
    assert "+-" in cleaned
    assert "Rxb6" in cleaned
    assert "!'l:" not in cleaned
    assert "Qf8#" in cleaned
    assert "Bxf1" in cleaned
    assert "Qa7+" in cleaned
    assert "#" in cleaned

    pgn = Path("data/annotated/bookwalk/Magnus_Carlsen_vs_Luke_McShane_2009_bookwalk.pgn")
    if not pgn.exists():
        return
    game = chess.pgn.read_game(pgn.open())
    board = game.board()
    node = game
    while node.variations:
        node = node.variation(0)
        san = board.san(node.move)
        if san.startswith("Qe7") and board.fullmove_number >= 36:
            out = legalize_note_prose(board, cleaned)
            assert "Qd7?" in out
            assert "Bd4" in out and "Qd4" not in out
            assert "Rxb6" in out
            assert "Qf2" in out
            assert "Qf8#" in out
            assert "Nxb6" in out
            assert "Qa7+" in out
            assert "Nxd6" in out
            break
        board.push(node.move)

    """Ral → Ra1 (not Ra7); Rxa l → Rxa1; Nfl still Nf7."""
    assert "Ra1" in ocr_clean_chess("37.E:al!?")
    assert "Ra7" not in ocr_clean_chess("37.E:al!?")
    assert "Rxa1" in ocr_clean_chess("38.Elxa l ih4").replace(" ", "")
    assert "Rxa l" not in ocr_clean_chess("38. Rxa l Bh4")
    assert "Nf7" in ocr_clean_chess("30... Nfl?!")
    assert "Bh4" in ocr_clean_chess("iBh4")
    assert "iBh4" not in ocr_clean_chess("iBh4")
    assert "Be3" in ocr_clean_chess("41. iBe3±")
    raw = "36 ... E:a8 37.E:al!? E:xal 38.Elxa l ih4 39 . .igl Qb8 40.E:a6 id8 41. ie3±"
    out = ocr_clean_chess(raw)
    assert "Ra1!?" in out.replace(" ", "") or "Ra1!?" in out
    assert "Rxa1" in out.replace(" ", "")
    assert "Bh4" in out
    assert "Bg1" in out
    assert "Be3" in out
    assert "Ra7" not in out


def test_nh6_better_defence_stays_one_note():
    """Soft-wrap after White+bare reply must not open 38.Rxa1 as new note."""
    from chess_coach.chapter import extract_move_notes

    raw = """36. Qb2 Nh6?
And as usually happens, passive defence leads to mistakes.
A better defence was 36 ... E:a8 37.E:al!? E:xal
38.Elxa l ih4 39 . .igl Qb8 40.E:a6 id8 41. ie3±
when Black's position is extremely difficult to hold.
Black missed the tactical shot:
37.hb6!
37 ... Qe7!
The only move to stay in the game.
"""
    _pre, notes = extract_move_notes(raw)
    nh6 = next(n for n in notes if n.fullmove == 36 and n.side == "black")
    assert "A better defence" in nh6.text
    assert "Ra1!?" in nh6.text.replace(" ", "")
    assert "Rxa1" in nh6.text.replace(" ", "")
    assert "Bh4" in nh6.text
    assert "Be3" in nh6.text
    assert "difficult to hold" in nh6.text
    assert not any(n.fullmove == 38 and "Rxa1" in (n.san_hint or "") for n in notes)


def test_kh1_sideline_ocr_and_paren_continue():
    """Quality Chess salad after Kh1 stays on one note; t→+; ix→B; paren continue."""
    from chess_coach.chapter import extract_move_notes

    raw = """35. Kh1
Again, White can slowly improve his position, while Black's pieces are cramped and have little to do.
As McShane points out, 35.ixb6? gives away most of the advantage after: 35 ... E:xb6 36.\ufffdf2
(or 36.E'.xf7t Wxf7 37.\ufffdf2t 'itlg7 38.l0 xb6 ih4!
39.g3 [39.\ufffde3 ig5 40.\ufffdf2 ih4=] 39 ... hg3
40.'Ml'xg3 \ufffdxb6t with a drawn position)
36 ... E:xb5 37.\ufffdxf7t 'itlh6;t
35 ... Be8 36.\ufffdb2 l0h6?
And as usually happens, passive defence leads to mistakes.
"""
    cleaned = ocr_clean_chess(raw)
    assert "Bxb6" in cleaned.replace(" ", "")
    assert "Rxf7+" in cleaned.replace(" ", "")
    assert "Qf2+" in cleaned.replace(" ", "")
    assert "Kg7" in cleaned
    assert "Nxb6" in cleaned.replace(" ", "")
    assert "Bh4" in cleaned
    assert "Qxg3" in cleaned.replace(" ", "")
    assert "Qxb6+" in cleaned.replace(" ", "")
    assert "Kh6" in cleaned
    assert "⩲" in cleaned
    assert "E'." not in cleaned
    assert "'itl" not in cleaned.lower()
    assert "'Ml'" not in cleaned
    assert glue_spaced_san("Ba7!") == "Ba7!"
    assert glue_spaced_san("Ba6") == "Ba6"

    _pre, notes = extract_move_notes(raw)
    kh1 = next(n for n in notes if n.fullmove == 35 and n.side == "white")
    assert "Again, White" in kh1.text
    assert "Rxf7+" in kh1.text.replace(" ", "")
    assert "36...Rxb5" in kh1.text.replace(" ", "") or "36... Rxb5" in kh1.text
    assert "Qxf7+" in kh1.text.replace(" ", "")
    assert "Kh6" in kh1.text
    assert "drawn position" in kh1.text
    assert not any(n.fullmove == 36 and n.side == "black" and "Rxb5" in (n.san_hint or "") for n in notes)


def test_qf1_block_splits_and_keeps_pieces():
    """38.Qf1 note must not swallow 39...Ng8; {or keeps Rxb5/Nxd6 (not Q/R swaps)."""
    from pathlib import Path

    import chess.pgn

    from chess_coach.chapter import extract_move_notes
    from chess_coach.note_legalize import legalize_note_prose
    from chess_coach.ocr_chess import ocr_clean_chess

    raw = """38.\ufffdfl?!
We are close to the time control on move 40, and Carlsen makes some imprecisions.
The most accurate was 38.i a5! ixb5 {or
38 ... E:xb5 39.ib4 !'l:d8 40.l0 xd6!+-) 39.l0x d6
\ufffdxd6 40.ixb5 with a near-winning position.
38 .. Jkb8 39.gb3 tlig8
Aiming for ... l0f6-h5 with some counterplay.
40 . .ie2
Covering the h5 -square.
"""
    cleaned = ocr_clean_chess(raw)
    assert "Ba5!" in cleaned.replace(" ", "") or "Ba5!" in cleaned
    assert "(or" in cleaned
    assert "Bb4 Rd8" in cleaned
    assert "Rcb8" in cleaned
    assert "Rb3" in cleaned
    assert "Ng8" in cleaned

    _pre, notes = extract_move_notes(raw)
    n38 = next(n for n in notes if n.fullmove == 38 and n.side == "white")
    assert "Aiming" not in n38.text
    assert "near-winning" in n38.text
    n39 = next(n for n in notes if n.fullmove == 39 and n.side == "black")
    assert "Aiming" in n39.text

    pgn = Path("data/annotated/bookwalk/Magnus_Carlsen_vs_Luke_McShane_2009_bookwalk.pgn")
    if not pgn.exists():
        return
    game = chess.pgn.read_game(pgn.open())
    board = game.board()
    node = game
    while node.variations:
        node = node.variation(0)
        san = board.san(node.move)
        if board.fullmove_number == 38 and board.turn and san.startswith("Qf2"):
            out = legalize_note_prose(board, n38.text)
            assert "Rxb5" in out
            assert "Nxd6" in out
            assert "Qxb5" not in out
            assert "Aiming" not in out
            break
        board.push(node.move)


def test_ra1_informator_plus_over():
    out = ocr_clean_chess("Ra 1!?;!;")
    assert "Ra1" in out
    assert "⩲" in out
    assert ";!;" not in out
    out2 = ocr_clean_chess("(30 . .§a 1 !?;!; is safer)")
    assert "Ra1" in out2
    assert "⩲" in out2


def test_collect_mainline_book_marks_na4():
    """44.Na4! inside a note body attaches ! to the matching mainline ply."""
    from pathlib import Path

    import chess.pgn

    from chess_coach.chapter import BookMoveNote
    from chess_coach.notes_align import collect_mainline_book_marks, split_san_mark

    assert split_san_mark("Na4!") == ("Na4", "!")
    assert split_san_mark("Qf1?!") == ("Qf1", "?!")
    assert split_san_mark("Nh6?") == ("Nh6", "?")
    assert split_san_mark("dxc5??") == ("dxc5", "??")

    pgn = Path("data/annotated/bookwalk/Magnus_Carlsen_vs_Luke_McShane_2009_bookwalk.pgn")
    if not pgn.exists():
        return
    game = chess.pgn.read_game(pgn.open())
    notes = [
        BookMoveNote(
            fullmove=40,
            side="white",
            san_hint="Be2",
            text="Covering h5. 44.Na4! Threatening Nb6. 45.Be2! is the key.",
        ),
        BookMoveNote(fullmove=45, side="white", san_hint="Be2!", text="Key move."),
        BookMoveNote(fullmove=36, side="black", san_hint="Nh6?", text="Passive."),
    ]
    marks = collect_mainline_book_marks(game, notes)
    sans = {}
    board = game.board()
    node = game
    ply = 0
    while node.variations:
        node = node.variation(0)
        ply += 1
        sans[ply] = board.san(node.move)
        board.push(node.move)
    by_san = {sans[p]: m for p, m in marks.items() if p in sans}
    assert by_san.get("Na4") == "!"
    assert by_san.get("Be2") == "!" or any(
        sans[p] == "Be2" and marks[p] == "!" for p in marks
    )
    assert by_san.get("Nh6") == "?"


def test_final_move_gets_post_game_tail():
    """Last mainline ply gets book text after 1-0 / Final remarks; mid-game notes lose it."""
    import re
    from pathlib import Path

    import chess.pgn

    from chess_coach.chapter import BookMoveNote
    from chess_coach.notes_align import align_notes_to_game, extract_final_move_book_tail

    ctx = (
        "51. Qf3 +- Black cannot defend. Chessbase Magazine.\n"
        "1-0\n"
        "Final remarks\n"
        "1. The option 21... bxc5 deserves serious consideration.\n"
        "2. White gained queenside space.\n"
    )
    tail = extract_final_move_book_tail(
        ctx, last_fullmove=61, last_side="white", last_san="d7"
    )
    assert "Final remarks" in tail
    assert "bxc5" in tail
    assert "Chessbase" not in tail
    assert re.search(r"(?i)Final\s+remarks\n\n1\.", tail)
    assert not re.search(r"(?i)Final\s+remarks[ \t]+1\.", tail)

    pgn = Path("data/annotated/bookwalk/Magnus_Carlsen_vs_Luke_McShane_2009_bookwalk.pgn")
    if not pgn.exists():
        return
    game = chess.pgn.read_game(pgn.open())
    notes = [
        BookMoveNote(
            fullmove=51,
            side="white",
            san_hint="Qf3",
            text=(
                "Black cannot defend. Chessbase Magazine. 1-0 "
                "Final remarks 1. Study 21... bxc5 carefully."
            ),
        ),
    ]
    aligned = align_notes_to_game(game, notes, context=ctx)
    by_san = {a.san: a for a in aligned}
    assert "d7" in by_san
    assert "Final remarks" in by_san["d7"].text
    assert "bxc5" in by_san["d7"].text
    if "Bf3" in by_san:
        assert "Final remarks" not in by_san["Bf3"].text
        assert "Chessbase" in by_san["Bf3"].text


def test_nf6_does_not_swallow_rxb6_resource():
    """41 FFFD+0 &.b6 → f3 Bb6 shape; dest-align + L5 → Rxb6; prose on 41..."""
    from pathlib import Path

    import chess.pgn

    from chess_coach.chapter import extract_move_notes
    from chess_coach.note_legalize import legalize_note_prose
    from chess_coach.notes_align import _san_similar
    from chess_coach.ocr_chess import ocr_clean_chess

    raw = (
        "40... Nf6\n"
        "And we have passed the time control.\n"
        "41\uFFFD 0 &.b6\n"
        "This is an interesting practical resource, but Carlsen manages "
        "to find a beautiful way to refute it.\n"
        "The alternative McShane suggests is 41... Nd7\n"
        "42. Nxb6 Qc7\n"
    )
    cleaned = ocr_clean_chess(raw)
    assert "f3" in cleaned and "Bb6" in cleaned
    assert "41 0" not in cleaned
    assert _san_similar("f3", "Bf3")
    assert _san_similar("Bb6", "Rxb6")
    _pre, notes = extract_move_notes(raw)
    nf6 = next(n for n in notes if n.fullmove == 40 and n.side == "black")
    assert "interesting" not in nf6.text
    assert "time control" in nf6.text
    rxb = next(n for n in notes if "interesting" in n.text)
    assert rxb.fullmove == 41 and rxb.side == "black"
    assert "Bb6" in (rxb.san_hint or "") or "Rxb6" in (rxb.san_hint or "")

    pgn = Path("data/annotated/bookwalk/Magnus_Carlsen_vs_Luke_McShane_2009_bookwalk.pgn")
    if not pgn.exists():
        return
    game = chess.pgn.read_game(pgn.open())
    board = game.board()
    node = game
    while node.variations:
        node = node.variation(0)
        if board.fullmove_number == 41 and board.turn == chess.WHITE:
            board.push(node.move)  # Bf3
            assert legalize_note_prose(board, "Bb6") == "Rxb6"
            break
        board.push(node.move)


def test_h4_dot_bh6_retargets_defenceless_prose():
    """43.h4 .ih6 + 'The knight…' belongs on 43...Bh6, not white h4."""
    from chess_coach.chapter import extract_move_notes
    from chess_coach.ocr_chess import ocr_clean_chess

    raw = (
        "42.tlixb6 \ufffdc7 43.h4 .ih6\n"
        "The knight on f6 is now defenceless.\n"
        "44.tlia4!\n"
        "Threatening 45. l0c3, forcing Black to capture.\n"
    )
    cleaned = ocr_clean_chess(raw)
    assert "h4.Bh6" not in cleaned
    assert "h4 Bh6" in cleaned or "h4  Bh6" in cleaned
    _pre, notes = extract_move_notes(raw)
    bh6 = next(n for n in notes if "defenceless" in n.text)
    assert bh6.fullmove == 43 and bh6.side == "black"
    assert "Bh6" in (bh6.san_hint or "")
    assert not any(n.fullmove == 43 and n.side == "white" for n in notes)


def test_na4_threat_not_glued_to_rxb5():
    """44.Na4 keeps Threatening 45.Nc3; 44...gxbS → Rxb5 with But now; L5 skips threat."""
    from pathlib import Path

    import chess.pgn

    from chess_coach.chapter import extract_move_notes
    from chess_coach.note_legalize import legalize_note_prose
    from chess_coach.ocr_chess import ocr_clean_chess

    raw = (
        "44.tlia4!\n"
        "Threatening 45. l0c3, forcing Black to capture.\n"
        "44 .. . gxbS\n"
        "But now:\n"
        "45 . .ie2! &.b3\n"
    )
    cleaned = ocr_clean_chess(raw)
    assert "44... Rxb5" in cleaned or "44...Rxb5" in cleaned.replace(" ", "")
    assert "gxbS" not in cleaned
    assert "44...." not in cleaned
    assert "Nc3" in cleaned
    _pre, notes = extract_move_notes(raw)
    na4 = next(n for n in notes if n.fullmove == 44 and n.side == "white")
    assert "Threatening 45" in na4.text and "Nc3" in na4.text
    assert "But now" not in na4.text
    assert "Rxb5" not in na4.text and "gxb" not in na4.text.lower()
    rxb = next(n for n in notes if n.fullmove == 44 and n.side == "black")
    assert "Rxb5" in (rxb.san_hint or "")
    assert "But now" in rxb.text

    pgn = Path("data/annotated/bookwalk/Magnus_Carlsen_vs_Luke_McShane_2009_bookwalk.pgn")
    if not pgn.exists():
        return
    game = chess.pgn.read_game(pgn.open())
    board = game.board()
    node = game
    while node.variations:
        node = node.variation(0)
        if board.fullmove_number == 44 and board.turn == chess.WHITE:
            fixed = legalize_note_prose(
                board, "Threatening 45. Nc3, forcing Black to capture."
            )
            assert "Nc3" in fixed
            assert "Rc3" not in fixed
            break
        board.push(node.move)


def test_be2_score_retargets_key_comment_to_nc5():
    """45.Be2 … 47.tlicS! + 'This is the key…' belongs on 47.Nc5, not Be2/Qxf6."""
    from chess_coach.chapter import extract_move_notes
    from chess_coach.ocr_chess import ocr_clean_chess

    raw = (
        "But now:\n"
        "45 . .ie2! &.b3 46.\ufffdxf6t 'it>g8 47.tlicS!\n"
        "This is the key to White's last four moves: the "
        "knight is immune, and Black's position is near "
        "collapse due to the threats l0e6 and ig4-e6.\n"
        "47 ... \ufffdg3\n"
        "Making things easier for White.\n"
    )
    cleaned = ocr_clean_chess(raw)
    assert "Kg8" in cleaned
    assert "'it>" not in cleaned
    assert "Nc5" in cleaned
    assert "Nc8" not in cleaned
    _pre, notes = extract_move_notes(raw)
    key = next(n for n in notes if "key to White" in n.text)
    assert key.fullmove == 47 and key.side == "white"
    assert "Nc5" in (key.san_hint or "")
    assert not any(n.fullmove == 45 and "key" in n.text for n in notes)
    assert not any(n.fullmove == 46 and "key" in n.text for n in notes)
    qg3 = next(n for n in notes if n.fullmove == 47 and n.side == "black")
    assert "Making things easier" in qg3.text
    assert "key to White" not in qg3.text


def test_rg3_late_game_notes_ocr_and_targets():
    """47...Rg3 keeps full If/Or/Rb2 note; Suicidal on 50...Be8; 51.Qf3+- strips eval."""
    from chess_coach.chapter import extract_move_notes
    from chess_coach.ocr_chess import ocr_clean_chess

    raw = (
        "47 ... \ufffdg3\n"
        "Making things easier for White.\n"
        "If 47 ... dxc5?? 48.d6 Wfff7 (or 48 ... Wffd7 49 .i.c4t)\n"
        "49 .d7! Wffxd7 50.i.c4t with forced mate.\n"
        "Or: 47 ... Wffxc5?? 48 .Wie6t 'tt>g7 49.Wff e7t 'tt>g8\n"
        "50.Wffxe8t 'tt>g7 5 l .Wfff8#\n"
        "The best defence was 47 .. J\ufffdb2 bur after the\n"
        "forcing sequence 48.i.g4 i.g7 49.tee 6 Wif7\n"
        "50.tex g7 Wffxf6 5 l. E:xf6 'tt>xg7 52 .:9'.xd6 the\n"
        "endgame should be winning for White.\n"
        "48.tlie6 Yfifl 49.Yfixflt hi7 50.l!bl! \ufffdes\n"
        "Suicidal is 50 ... i.xe6? 5 l .dxe6 when the threat\n"
        "is :9'.b8 followed by e6-e7-e8= Wff: 5 l ... i.f8 52.:9'.b8\n"
        "'tt>g7 53.:9'.b7t 'tt>f6 (or 53 ... 'tt>g8 54. e7+-)\n"
        "54.E: flt+-\n"
        "51. \ufffdf3+-\n"
        "Black cannot defend without the help of his trapped rook.\n"
    )
    cleaned = ocr_clean_chess(raw)
    assert "Qf7" in cleaned and "Wfff" not in cleaned
    assert "Kg7" in cleaned and "tt>" not in cleaned
    assert "Rb2" in cleaned and "Ne6" in cleaned and "Nxg7" in cleaned
    assert "Qxf7+" in cleaned and "Bxf7" in cleaned
    assert "Be8" in cleaned
    assert "Rf1+-" in cleaned.replace(" ", "") or "Rf1 +-" in cleaned
    _pre, notes = extract_move_notes(raw)
    rg3 = next(n for n in notes if n.fullmove == 47 and n.side == "black")
    assert "Making things easier" in rg3.text
    assert "Qf8#" in rg3.text
    assert "Rb2" in rg3.text
    assert "winning for White" in rg3.text
    assert "Wff" not in rg3.text
    assert not any(
        n.fullmove == 48 and n.side == "white" and "Suicidal" in n.text for n in notes
    )
    be8 = next(n for n in notes if "Suicidal" in n.text)
    assert be8.fullmove == 50 and be8.side == "black"
    assert "Be8" in (be8.san_hint or "")
    qf3 = next(n for n in notes if n.fullmove == 51 and n.side == "white")
    assert qf3.text.startswith("Black")
    assert not qf3.text.startswith("-")
