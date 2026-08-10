from __future__ import annotations

import chess

from chess_coach.note_legalize import legalize_note_prose


def test_wrong_piece_capture_becomes_unique_queen() -> None:
    board = chess.Board("4k3/8/8/p7/8/8/3Q4/4K3 w - - 0 1")
    out = legalize_note_prose(board, "preferable to play 30.Bxa5 next")
    assert "30.Qxa5" in out
    assert "Bxa5" not in out


def test_walk_then_repair_qxa5() -> None:
    board = chess.Board("4k3/8/1p6/P7/8/8/3Q4/4K3 b - - 0 29")
    text = "preferable to play 29...bxa5 30.Bxa5 and White is fine"
    out = legalize_note_prose(board, text)
    assert "29...bxa5" in out
    assert "30.Qxa5" in out
    assert "Bxa5" not in out


def test_bare_square_becomes_unique_piece() -> None:
    board = chess.Board("4k3/8/8/Q7/8/8/8/7K w - - 0 1")
    out = legalize_note_prose(board, "better was d2")
    assert "Qd2" in out
    assert " was d2" not in out


def test_threat_list_does_not_swallow_or_sideline_pawn() -> None:
    """After 'followed by e8=Q: 51...', later '(or … 54. e7)' stays a pawn push."""
    from pathlib import Path

    import chess.pgn

    pgn = Path("data/annotated/bookwalk/Magnus_Carlsen_vs_Luke_McShane_2009_bookwalk.pgn")
    if not pgn.exists():
        return
    game = chess.pgn.read_game(pgn.open())
    board = game.board()
    node = game
    while node.variations:
        nxt = node.variation(0)
        if board.fullmove_number == 50 and board.san(nxt.move).startswith("Be8"):
            text = (
                "Suicidal is 50... Bxe6? 51. dxe6 when the threat is Rb8 followed by "
                "e6-e7-e8=Q: 51... Bf8 52. Rb8 Kg7 53. Rb7+ Kf6 (or 53... Kg8 54. e7 +-)"
            )
            out = legalize_note_prose(board, text)
            assert "54. e7" in out or "54.e7" in out.replace(" ", "")
            assert "Be7" not in out
            break
        board.push(nxt.move)
        node = nxt


def test_ambiguous_capture_left_untouched() -> None:
    board = chess.Board("4k3/8/1B6/p7/8/8/3Q4/4K3 w - - 0 1")
    sans = {board.san(m) for m in board.legal_moves}
    assert "Qxa5" in sans
    assert "Bxa5" in sans
    out = legalize_note_prose(board, "try 30.Nxa5 instead")
    assert "Nxa5" in out


def test_parenthetical_does_not_poison_main_cursor() -> None:
    board = chess.Board("4k3/8/8/p7/8/8/3Q4/4K3 w - - 0 1")
    text = "(nonsense) then 30.Bxa5"
    out = legalize_note_prose(board, text)
    assert "30.Qxa5" in out


def test_keeps_legal_pawn_capture() -> None:
    board = chess.Board("4k3/8/8/6p1/7P/8/8/4K3 w - - 0 1")
    out = legalize_note_prose(board, "White plays hxg5")
    assert "hxg5" in out


def test_lookahead_rc2_becomes_nc2() -> None:
    """Wrong-but-plausible R vs real N — continuation Nb4-Nc6 decides."""
    # Position before 28.Nc2 in Carlsen-McShane style structure.
    board = chess.Board(
        "2r2q1k/p1rb3p/1p1p1bpn/1P1Ppp2/P3P3/3BNP1P/5BP1/1R1QR1K1 w - - 1 28"
    )
    text = (
        "If 28. Rc2 then 28... fxe4 29. fxe4 g5. For example: "
        "30. g4 30... Ng8 31. Rb4 Ne7 32. Nc6 Ng6 33. a5 f4 34. Bf1 h5"
    )
    out = legalize_note_prose(board, text)
    assert "28. Nc2" in out or "28.Nc2" in out.replace(" ", "")
    assert "Rc2" not in out
    assert "Nb4" in out
    assert "Nf4" in out


def test_lookahead_rd2_becomes_qd2() -> None:
    board = chess.Board(
        "2r2q1k/p1rb3p/1p1p1bpn/1P1Ppp2/P3P3/3BNP1P/5BP1/1R1QR1K1 w - - 1 28"
    )
    board.push_san("Nc2")
    board.push_san("fxe4")
    board.push_san("fxe4")
    board.push_san("g5")
    text = "or 30. Rd2 g4 31. Be3 Ng8 32. hxg4 Bxg4"
    out = legalize_note_prose(board, text)
    assert "Qd2" in out
    assert "Rd2" not in out


def test_pawn_strip_bh4_bg3() -> None:
    board = chess.Board(
        "2r2q1k/p1rb3p/1p1p1bpn/1P1Ppp2/P3P3/3BNP1P/5BP1/1R1QR1K1 w - - 1 28"
    )
    for san in ("Nc2", "fxe4", "fxe4", "g5", "Qe2", "g4"):
        board.push_san(san)
    text = "31. Bh4 Bg3! 32. Bxg3 Qg7 33. Qf2 Rg8"
    out = legalize_note_prose(board, text)
    assert "h4" in out
    assert "g3" in out
    assert "Bh4" not in out
    assert "Bg3" not in out
    assert "Bf2" in out
    assert "Qf2" not in out


def test_piece_fill_f4_to_nf4() -> None:
    board = chess.Board(
        "2r2q1k/p1rb3p/1p1p1bpn/1P1Ppp2/P3P3/3BNP1P/5BP1/1R1QR1K1 w - - 1 28"
    )
    for san in (
        "Nc2",
        "fxe4",
        "fxe4",
        "g5",
        "g4",
        "Ng8",
        "Nb4",
        "Ne7",
        "Nc6",
        "Ng6",
        "a5",
    ):
        board.push_san(san)
    out = legalize_note_prose(board, "f4 34. Bf1")
    assert "Nf4" in out


def test_preserve_check_suffix_and_bg5_to_g5():
    import chess.pgn
    from pathlib import Path

    pgn = Path("data/annotated/bookwalk/Magnus_Carlsen_vs_Luke_McShane_2009_bookwalk.pgn")
    if not pgn.exists():
        return
    game = chess.pgn.read_game(pgn.open())
    board = game.board()
    node = game
    before = None
    while node.variations:
        node = node.variation(0)
        san = board.san(node.move)
        if san == "Kh1":
            before = board.copy()
            break
        board.push(node.move)
    assert before is not None
    note = (
        "35. Bxb6? 35... Rxb6 36. Qf2 (or 36. Rxf7+ Kxf7 37. Qf2+ Kg7 38. Nxb6 Bh4! "
        "39. g3 [39. Qe3 Bg5 40. Qf2 Bh4=] 39... Bxg3 40. Qxg3 Qxb6+ with a drawn position) "
        "36... Rxb5 37. Qxf7+ Kh6"
    )
    out = legalize_note_prose(before, note)
    assert "Rxf7+" in out.replace(" ", "")
    assert "Qf2+" in out.replace(" ", "")
    assert "Qxf7+" in out.replace(" ", "")
    assert "Qxb6+" in out.replace(" ", "")
    assert "Bg5" not in out
    assert "g5" in out
    assert "Nxb6" in out.replace(" ", "")
