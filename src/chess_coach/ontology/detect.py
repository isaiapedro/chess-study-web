from __future__ import annotations

import chess

from chess_coach.ontology.load import Pattern, load_ontology


def _pawn_files(board: chess.Board, color: chess.Color) -> dict[int, list[int]]:
    files: dict[int, list[int]] = {}
    for square, piece in board.piece_map().items():
        if piece.piece_type == chess.PAWN and piece.color == color:
            files.setdefault(chess.square_file(square), []).append(chess.square_rank(square))
    return files


def _has_iqp(board: chess.Board, color: chess.Color) -> bool:
    files = _pawn_files(board, color)
    for file_idx, ranks in files.items():
        if file_idx not in (3, 4):
            continue
        if len(ranks) != 1:
            continue
        if not files.get(file_idx - 1) and not files.get(file_idx + 1):
            return True
    return False


def _has_hanging_pawns(board: chess.Board, color: chess.Color) -> bool:
    """
    Classic hanging duo: c+d or d+e, each file one pawn, no outer neighbor pawns,
    ranks close (same/adjacent), advanced off the home rank.
    """
    if board.fullmove_number < 8:
        return False
    files = _pawn_files(board, color)
    for left, right in ((2, 3), (3, 4)):
        if left not in files or right not in files:
            continue
        if len(files[left]) != 1 or len(files[right]) != 1:
            continue
        if files.get(left - 1) or files.get(right + 1):
            continue
        r1, r2 = files[left][0], files[right][0]
        if abs(r1 - r2) > 1:
            continue
        # White duo typically on 3rd–5th; Black on 2nd–4th
        if color == chess.WHITE:
            if min(r1, r2) < 2 or max(r1, r2) > 4:
                continue
        else:
            if max(r1, r2) > 5 or min(r1, r2) < 3:
                continue
        return True
    return False


def _has_doubled(board: chess.Board, color: chess.Color) -> bool:
    files = _pawn_files(board, color)
    return any(len(ranks) >= 2 for ranks in files.values())


def _pawns_on_file(board: chess.Board, file_idx: int) -> int:
    count = 0
    for rank in range(8):
        piece = board.piece_at(chess.square(file_idx, rank))
        if piece and piece.piece_type == chess.PAWN:
            count += 1
    return count


def _open_c_file(board: chess.Board) -> bool:
    return _pawns_on_file(board, 2) <= 1


def _open_e_file(board: chess.Board) -> bool:
    return _pawns_on_file(board, 4) <= 1


def _carlsbad_minority(board: chess.Board) -> bool:
    """
    Stricter Carlsbad/minority shape:
    - past early opening
    - White d4, Black d5+c6
    - White has no c4 (c-pawn missing or only c3)
    - White still has a b-pawn (the minority lever)
    - Black has a- or b-pawn (queenside mass to fix)
    """
    if board.fullmove_number < 10:
        return False
    wd4 = board.piece_at(chess.D4) == chess.Piece.from_symbol("P")
    bd5 = board.piece_at(chess.D5) == chess.Piece.from_symbol("p")
    bc6 = board.piece_at(chess.C6) == chess.Piece.from_symbol("p")
    if not (wd4 and bd5 and bc6):
        return False
    wc4 = board.piece_at(chess.C4) == chess.Piece.from_symbol("P")
    if wc4:
        return False
    white_c = sum(
        1
        for rank in range(8)
        if board.piece_at(chess.square(2, rank)) == chess.Piece.from_symbol("P")
    )
    if white_c > 1:
        return False
    white_b = any(
        board.piece_at(chess.square(1, rank)) == chess.Piece.from_symbol("P") for rank in range(8)
    )
    black_ab = any(
        board.piece_at(chess.square(f, rank)) == chess.Piece.from_symbol("p")
        for f in (0, 1)
        for rank in range(8)
    )
    return white_b and black_ab


def _has_bishop_pair(board: chess.Board, color: chess.Color) -> bool:
    bishops = [
        sq
        for sq, p in board.piece_map().items()
        if p.piece_type == chess.BISHOP and p.color == color
    ]
    if len(bishops) < 2:
        return False
    colors = {(chess.square_rank(sq) + chess.square_file(sq)) % 2 for sq in bishops}
    return len(colors) == 2


def _bishop_pair_imbalance(board: chess.Board) -> bool:
    """True only when one side has the pair and the other does not."""
    w = _has_bishop_pair(board, chess.WHITE)
    b = _has_bishop_pair(board, chess.BLACK)
    return w != b


def _king_safety_signal(board: chess.Board) -> bool:
    if board.is_check():
        return True
    for weak, attacker in ((chess.F7, chess.WHITE), (chess.F2, chess.BLACK)):
        for sq in board.attackers(attacker, weak):
            piece = board.piece_at(sq)
            if piece and piece.piece_type in (chess.QUEEN, chess.BISHOP):
                return True
    wk = board.king(chess.WHITE)
    bk = board.king(chess.BLACK)
    if wk is None or bk is None:
        return False
    # opposite wings (files far apart) after castling-ish
    return abs(chess.square_file(wk) - chess.square_file(bk)) >= 4


def _material_imbalance(board: chess.Board) -> int:
    values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
    }
    score = 0
    for _, piece in board.piece_map().items():
        delta = values.get(piece.piece_type, 0)
        score += delta if piece.color == chess.WHITE else -delta
    return score


def _rook_pawn_endgame(board: chess.Board) -> bool:
    pieces = list(board.piece_map().values())
    if len(pieces) > 8:
        return False
    queens = sum(1 for p in pieces if p.piece_type == chess.QUEEN)
    if queens:
        return False
    rooks = sum(1 for p in pieces if p.piece_type == chess.ROOK)
    pawns = sum(1 for p in pieces if p.piece_type == chess.PAWN)
    minors = sum(1 for p in pieces if p.piece_type in (chess.KNIGHT, chess.BISHOP))
    return rooks >= 1 and pawns >= 1 and minors == 0 and len(pieces) <= 6


def _is_passed(board: chess.Board, square: int, color: chess.Color) -> bool:
    file_idx = chess.square_file(square)
    rank = chess.square_rank(square)
    enemy = not color
    if color == chess.WHITE:
        ranks = range(rank + 1, 8)
    else:
        ranks = range(rank - 1, -1, -1)
    for r in ranks:
        for f in (file_idx - 1, file_idx, file_idx + 1):
            if f < 0 or f > 7:
                continue
            piece = board.piece_at(chess.square(f, r))
            if piece and piece.piece_type == chess.PAWN and piece.color == enemy:
                return False
    return True


def _has_passed_pawn(board: chess.Board) -> bool:
    for sq, piece in board.piece_map().items():
        if piece.piece_type == chess.PAWN and _is_passed(board, sq, piece.color):
            # ignore 2nd-rank "passers" in opening clutter
            rank = chess.square_rank(sq)
            if piece.color == chess.WHITE and rank < 3:
                continue
            if piece.color == chess.BLACK and rank > 4:
                continue
            return True
    return False


def _opposite_bishops(board: chess.Board) -> bool:
    wb = [sq for sq, p in board.piece_map().items() if p.piece_type == chess.BISHOP and p.color == chess.WHITE]
    bb = [sq for sq, p in board.piece_map().items() if p.piece_type == chess.BISHOP and p.color == chess.BLACK]
    if len(wb) != 1 or len(bb) != 1:
        return False
    wcol = (chess.square_rank(wb[0]) + chess.square_file(wb[0])) % 2
    bcol = (chess.square_rank(bb[0]) + chess.square_file(bb[0])) % 2
    return wcol != bcol


def _opposite_bishops_endgame(board: chess.Board) -> bool:
    if len(board.piece_map()) > 12:
        return False
    if not _opposite_bishops(board):
        return False
    queens = any(p.piece_type == chess.QUEEN for p in board.piece_map().values())
    return not queens


def _pawn_chain(board: chess.Board) -> bool:
    """Locked central chain hint: white pawn attacks black pawn diagonally in centre."""
    for sq, piece in board.piece_map().items():
        if piece.piece_type != chess.PAWN or piece.color != chess.WHITE:
            continue
        f, r = chess.square_file(sq), chess.square_rank(sq)
        if f not in (3, 4, 5) or r not in (3, 4):
            continue
        for df in (-1, 1):
            tf, tr = f + df, r + 1
            if 0 <= tf <= 7 and 0 <= tr <= 7:
                other = board.piece_at(chess.square(tf, tr))
                if other and other.piece_type == chess.PAWN and other.color == chess.BLACK:
                    return True
    return False


def _space_advantage(board: chess.Board) -> bool:
    """Rough space: pawn rank sum differ by >= 4 (White POV)."""
    w = b = 0
    for sq, piece in board.piece_map().items():
        if piece.piece_type != chess.PAWN:
            continue
        rank = chess.square_rank(sq)
        if piece.color == chess.WHITE:
            w += rank
        else:
            b += 7 - rank
    return abs(w - b) >= 5


def _maroczy(board: chess.Board) -> bool:
    wc4 = board.piece_at(chess.C4) == chess.Piece.from_symbol("P")
    we4 = board.piece_at(chess.E4) == chess.Piece.from_symbol("P")
    return wc4 and we4


def _hedgehog(board: chess.Board) -> bool:
    """Black pawns on a6,b6,d6,e6 (classic hedgehog shelf)."""
    need = (chess.A6, chess.B6, chess.D6, chess.E6)
    return all(board.piece_at(sq) == chess.Piece.from_symbol("p") for sq in need)


def _eco_opening_match(pattern: Pattern, eco: str, opening: str) -> bool:
    eco_u = (eco or "").upper()
    open_l = (opening or "").lower()
    for prefix in pattern.eco_prefixes:
        if eco_u.startswith(prefix.upper()):
            return True
    for token in pattern.opening_tokens:
        if token.lower() in open_l:
            return True
    # broad Sicilian family tag from ECO B20–B99 when pattern family is sicilian
    if pattern.family == "sicilian" and eco_u.startswith("B") and len(eco_u) >= 2:
        try:
            code = int(eco_u[1:3])
        except ValueError:
            return False
        # only match specific patterns via prefixes/tokens above; generic skip
        _ = code
    return False


def detect_pattern_ids(
    fen: str,
    *,
    eco: str = "",
    opening: str = "",
    ontology_dir: str | None = None,
) -> list[str]:
    board = chess.Board(fen)
    catalog = load_ontology(ontology_dir)
    hits: list[str] = []

    def add(pid: str) -> None:
        if pid in catalog and pid not in hits:
            hits.append(pid)

    # Board detectors
    if _has_iqp(board, chess.WHITE) or _has_iqp(board, chess.BLACK):
        add("structure.iqp")
    if _has_hanging_pawns(board, chess.WHITE) or _has_hanging_pawns(board, chess.BLACK):
        add("structure.hanging_pawns")
    if _has_doubled(board, chess.WHITE) or _has_doubled(board, chess.BLACK):
        add("structure.doubled_pawns")
    if _open_c_file(board):
        add("structure.open_c_file")
    if _open_e_file(board):
        add("structure.open_e_file")
    if _carlsbad_minority(board):
        add("structure.minority_attack")
    if _has_passed_pawn(board):
        add("structure.passed_pawn")
    if _pawn_chain(board):
        add("structure.pawn_chain")
    if _maroczy(board):
        add("structure.maroczy_bind")
    if _hedgehog(board):
        add("structure.hedgehog")
    if _bishop_pair_imbalance(board):
        add("imbalance.bishop_pair")
    if _opposite_bishops(board):
        add("imbalance.opposite_bishops")
    if _opposite_bishops_endgame(board):
        add("endgame.opposite_bishops")
    if _king_safety_signal(board):
        add("imbalance.king_safety")
    if abs(_material_imbalance(board)) >= 3:
        add("imbalance.material")
    if _space_advantage(board):
        add("imbalance.space")
    if _rook_pawn_endgame(board):
        add("endgame.lucena")
        add("endgame.philidor")

    # ECO / opening name detectors
    for pattern in catalog.values():
        if pattern.detect == "eco_or_opening" and _eco_opening_match(pattern, eco, opening):
            add(pattern.id)

    # Phase gate
    phase_pieces = len(board.piece_map())
    if phase_pieces > 12:
        hits = [h for h in hits if not h.startswith("endgame.")]
    elif phase_pieces <= 12:
        hits = [h for h in hits if not h.startswith("opening.")]

    return hits
