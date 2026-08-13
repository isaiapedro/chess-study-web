from __future__ import annotations

import re

import chess
import chess.pgn

_SAN_TOKEN_RE = re.compile(
    r"(?P<head>\b\d+\.(?:\.\.)?\s*)?"
    r"(?P<san>"
    r"O-O-O|O-O|"
    r"[NBRQK][a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?(?:#|\+(?!-))?|"
    r"[a-h]x[a-h][1-8](?:=[NBRQ])?(?:#|\+(?!-))?|"
    r"[a-h][1-8](?:=[NBRQ])?(?:#|\+(?!-))?|"
    r"x[a-h][1-8](?:=[NBRQ])?(?:#|\+(?!-))?"
    r")"
    r"(?P<marks>[!?]{0,3})",
    re.I,
)

_DEST_RE = re.compile(r"([a-h][1-8])(?:=[NBRQ])?[+#]?$", re.I)
_PIECE_SAN_RE = re.compile(r"^[NBRQK]", re.I)
_BARE_SQUARE_RE = re.compile(r"^[a-h][1-8](?:=[NBRQ])?$", re.I)
_CASTLE_RE = re.compile(r"^(O-O-O|O-O|0-0-0|0-0)$", re.I)
_PAWN_CHAIN_RE = re.compile(r"[a-h][1-8](?:\s*-\s*[a-h][1-8])+")

_LOOKAHEAD = 16

_THREAT_CUE_RE = re.compile(
    r"(?i)(?:threats?|threatening|as well as|followed by|aiming(?:\s+for)?|preventing)\s+$"
)
_MANEUVER_RE = re.compile(r"\b[NBRQK][a-h][1-8]-[a-h][1-8]\b")
_THREAT_WORD_RE = re.compile(
    r"(?i)\b(?:threats?|threatening|as well as|followed by|aiming(?:\s+for)?|preventing)\b"
)


def _in_threat_phrase(text: str, pos: int) -> bool:
    """True when the next SAN sits in a threat list, not a playable variation."""
    window = text[max(0, pos - 72) : pos]
    # Threat lists stop before a resumed score: "e8=Q: 51... Bf8"
    window = re.split(r"[:.]\s*(?=\d+\.(?:\.\.)?\s*[NBRQKa-hx])", window)[-1]
    if _THREAT_CUE_RE.search(window):
        return True
    m = _THREAT_WORD_RE.search(window)
    if not m:
        return False
    tail = window[m.start() :]
    rest = _THREAT_WORD_RE.sub(" ", tail)
    rest = re.sub(
        r"(?i)(?:\d+\.(?:\.\.)?\s*)?[NBRQK]?[a-h]?x?[a-h][1-8](?:=[NBRQ])?[+#]*",
        " ",
        rest,
    )
    rest = re.sub(r"(?i)\b(?:and|or)\b|[,\s\-]+", " ", rest)
    return not re.search(r"[A-Za-z]", rest)


def board_before_ply(game: chess.pgn.Game, ply: int) -> chess.Board:
    """Position before the mainline move at ``ply`` (1-based)."""
    board = game.board()
    if ply <= 1:
        return board
    node: chess.pgn.GameNode = game
    for _ in range(ply - 1):
        if not node.variations:
            break
        node = node.variation(0)
        board.push(node.move)
    return board


def _strip_marks(san: str) -> str:
    return san.strip().rstrip("?!#+")


def _piece_class(san: str) -> str:
    s = _strip_marks(san)
    if not s:
        return "?"
    if s[0].upper() in "NBRQK":
        return s[0].upper()
    return "P"


def _try_parse(board: chess.Board, san: str) -> chess.Move | None:
    for cand in (_strip_marks(san), san.strip()):
        if not cand:
            continue
        try:
            return board.parse_san(cand.replace("0-0-0", "O-O-O").replace("0-0", "O-O"))
        except ValueError:
            continue
    return None


def _legal_to_dest(
    board: chess.Board,
    dest: str,
    *,
    require_capture: bool | None,
) -> list[tuple[str, chess.Move]]:
    dest = dest.lower()
    out: list[tuple[str, chess.Move]] = []
    seen: set[str] = set()
    for move in board.legal_moves:
        if chess.square_name(move.to_square) != dest:
            continue
        is_cap = board.is_capture(move) or board.is_en_passant(move)
        if require_capture is True and not is_cap:
            continue
        if require_capture is False and is_cap:
            continue
        san = _strip_marks(board.san(move))
        if san in seen:
            continue
        seen.add(san)
        out.append((san, move))
    return out


def _candidates(board: chess.Board, token: str) -> list[tuple[str, chess.Move]]:
    """
    Legal interpretations of a SAN-like token.

    Piece-shaped tokens: all moves to destination (figurine OCR confuses piece id).
    Pawn captures with from-file: exact parse only when legal (do not expand to Bxe4).
    Bare squares: all moves to that square (missing piece letter).
    """
    raw = _strip_marks(token)
    if not raw:
        return []
    if _CASTLE_RE.match(raw):
        parsed = _try_parse(board, raw)
        if parsed is None:
            return []
        return [(_strip_marks(board.san(parsed)), parsed)]

    dest_m = _DEST_RE.search(raw)
    if not dest_m:
        return []
    dest = dest_m.group(1)
    has_x = "x" in raw.lower()

    if _PIECE_SAN_RE.match(raw):
        # Disambiguated piece+file/rank (Rac8, R1c8): same piece only — do not
        # expand to every mover to that square (Rac8 must not become Qxc8).
        if re.match(r"^[NBRQK](?:[a-h]|[1-8])[a-h][1-8]", raw, re.I):
            parsed = _try_parse(board, raw)
            if parsed is not None:
                return [(_strip_marks(board.san(parsed)), parsed)]
            want = raw[0].upper()
            same: list[tuple[str, chess.Move]] = []
            for san, move in _legal_to_dest(
                board, dest, require_capture=True if has_x else None
            ):
                if _piece_class(san) == want:
                    same.append((san, move))
            if has_x and not same:
                for san, move in _legal_to_dest(board, dest, require_capture=None):
                    if _piece_class(san) == want:
                        same.append((san, move))
            return same
        cands = _legal_to_dest(board, dest, require_capture=True if has_x else None)
        if has_x and not cands:
            cands = _legal_to_dest(board, dest, require_capture=None)
        return cands

    if has_x:
        parsed = _try_parse(board, raw)
        if parsed is not None:
            return [(_strip_marks(board.san(parsed)), parsed)]
        cands = _legal_to_dest(board, dest, require_capture=True)
        return cands or _legal_to_dest(board, dest, require_capture=None)

    # Bare square: if a legal pawn move matches, keep it alone so OCR does not
    # promote g5 → Bg5. If the pawn push is illegal, allow piece fills (f4 → Nf4).
    parsed = _try_parse(board, raw)
    if parsed is not None and _piece_class(board.san(parsed)) == "P":
        return [(_strip_marks(board.san(parsed)), parsed)]
    return _legal_to_dest(board, dest, require_capture=None)


def _classify_choice(
    token: str,
    chosen_san: str,
    *,
    exact: chess.Move | None,
    chosen: chess.Move,
    n_cands: int,
) -> tuple[int, int, int]:
    """
    Return (exact_credit, pawn_strip, piece_swap).

    exact_credit: 1 if written token matches play, bare→unique piece, or unique pawn-strip.
    pawn_strip: piece-shaped OCR that is really a pawn move.
    piece_swap: piece-shaped OCR resolved to a different piece.
    """
    raw = _strip_marks(token)
    is_exact = exact is not None and chosen == exact
    written_p = _piece_class(raw)
    chosen_p = _piece_class(chosen_san)
    is_bare = bool(_BARE_SQUARE_RE.match(raw))
    is_uniq = exact is None and n_cands == 1
    is_pawn_strip = written_p != "P" and chosen_p == "P"
    is_piece_swap = written_p != "P" and chosen_p != "P" and written_p != chosen_p
    is_piece_fill = written_p == "P" and chosen_p != "P" and (is_bare or not is_exact)

    if is_exact:
        return 1, 0, 0
    if is_pawn_strip and (is_uniq or n_cands > 1):
        return 1, 1, 0
    if is_bare and is_uniq:
        return 1, 0, 0
    if is_piece_fill and is_uniq:
        return 1, 0, 0
    if is_piece_swap:
        return 0, 0, 1
    return 0, 0, 1 if written_p != chosen_p else 0


def _move_key_parts(
    token: str,
    san: str,
    move: chess.Move,
    *,
    exact: chess.Move | None,
    n_cands: int,
    trail: frozenset[int],
) -> tuple[int, int, int, int]:
    """Local score parts: (exact_or_strip_credit, link, -swap, strip)."""
    ex_c, strip_c, swap_c = _classify_choice(
        token, san, exact=exact, chosen=move, n_cands=n_cands
    )
    link_c = 1 if move.from_square in trail else 0
    return ex_c + strip_c, link_c, -swap_c, strip_c


def _combine_keys(
    left: tuple[int, int, int, int],
    right: tuple[int, int, int, int],
) -> tuple[int, int, int, int]:
    return (
        left[0] + right[0],
        left[1] + right[1],
        left[2] + right[2],
        left[3] + right[3],
    )


def _best_continuation(
    board: chess.Board,
    tokens: list[str],
    depth: int,
    trail: frozenset[int],
) -> tuple[int, int, int, int]:
    """Best comparable key for playing ``tokens`` from ``board``."""
    if not tokens or depth <= 0:
        return 0, 0, 0, 0

    tok = tokens[0]
    exact = _try_parse(board, tok)
    cands = _candidates(board, tok)
    if not cands:
        # Prose false-positive SAN (e.g. repeated g5-g4) — skip, no credit.
        return _best_continuation(board, tokens[1:], depth - 1, trail)

    best: tuple[int, int, int, int] | None = None
    n = len(cands)
    for san, move in cands:
        local = _move_key_parts(
            tok, san, move, exact=exact, n_cands=n, trail=trail
        )
        new_trail = set(trail)
        new_trail.discard(move.from_square)
        new_trail.add(move.to_square)
        work = board.copy()
        work.push(move)
        rest = _best_continuation(work, tokens[1:], depth - 1, frozenset(new_trail))
        key = _combine_keys(local, rest)
        if best is None or key > best:
            best = key
    assert best is not None
    return best


def _dest_capture_piece_hint(rest: list[str], dest: str) -> str | None:
    """If a later token captures ``dest`` with an explicit piece, return that piece."""
    dest = (dest or "").lower()
    if not dest:
        return None
    for tok in rest[:8]:
        m = re.match(rf"^([NBRQK])x{re.escape(dest)}$", _strip_marks(tok), re.I)
        if m:
            return m.group(1).upper()
    return None


def _choose_move(
    board: chess.Board,
    token: str,
    rest: list[str],
    trail: frozenset[int],
    *,
    capture_to: int | None = None,
) -> tuple[str, chess.Move] | None:
    cands = _candidates(board, token)
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]

    exact = _try_parse(board, token)
    # Bare dest + later Qxd5/Nxd5: prefer the piece that captures that square.
    dest_m = _DEST_RE.search(_strip_marks(token))
    if exact is None and dest_m and _BARE_SQUARE_RE.match(_strip_marks(token)):
        hint = _dest_capture_piece_hint(rest, dest_m.group(1))
        if hint:
            hinted = [(san, move) for san, move in cands if _piece_class(san) == hint]
            if len(hinted) == 1:
                return hinted[0]

    n = len(cands)

    def rest_after(move: chess.Move) -> tuple[int, int, int, int]:
        work = board.copy()
        work.push(move)
        new_trail = set(trail)
        new_trail.discard(move.from_square)
        new_trail.add(move.to_square)
        return _best_continuation(work, rest, _LOOKAHEAD, frozenset(new_trail))

    if exact is not None:
        exact_rest = rest_after(exact)
        overrides: list[tuple[tuple[int, int, int, int], str, chess.Move]] = []
        from_sq_name = chess.square_name(exact.from_square)

        def _returns_to_from(tok: str) -> bool:
            dest_m = _DEST_RE.search(_strip_marks(tok))
            return bool(
                dest_m
                and dest_m.group(1) == from_sq_name
                and _piece_class(tok) == _piece_class(token)
            )

        round_trip = _piece_class(token) != "P" and any(
            _returns_to_from(t) for t in rest[:6]
        )

        def _bishop_development_next(
            bishop_move: chess.Move, pawn_move: chess.Move
        ) -> bool:
            """True when next B-SAN is real development (Bg4 Bg7), not pawn OCR."""
            if not rest or _piece_class(rest[0]) != "B":
                return False
            after_b = board.copy()
            after_b.push(bishop_move)
            if _try_parse(after_b, rest[0]) is None:
                return False
            after_p = board.copy()
            after_p.push(pawn_move)
            return not any(
                _piece_class(s) == "P" for s, _ in _candidates(after_p, rest[0])
            )

        for san, move in cands:
            if move == exact:
                continue
            _ex_c, strip_c, swap_c = _classify_choice(
                token, san, exact=exact, chosen=move, n_cands=n
            )
            # Never invent a king move from a non-king token (Bf8 ≠ Kf8).
            if _piece_class(san) == "K" and _piece_class(token) != "K":
                continue
            # Keep exact bishop over queen (Bg7 ≠ Qg7).
            if _piece_class(token) == "B" and _piece_class(san) == "Q":
                continue
            alt_rest = rest_after(move)
            better = alt_rest > exact_rest
            # OCR bishop→pawn (Bh4/Bg5), but keep real development (Bg4 Bg7)
            better = better or (
                strip_c > 0
                and _piece_class(token) == "B"
                and _piece_class(san) == "P"
                and (
                    round_trip
                    or (
                        alt_rest[0] >= exact_rest[0]
                        and not _bishop_development_next(exact, move)
                    )
                )
            )
            better = better or (
                alt_rest == exact_rest
                and capture_to is not None
                and move.from_square == capture_to
                and exact.from_square != capture_to
                and _piece_class(san)
                == (
                    board.piece_at(capture_to).symbol().upper()
                    if board.piece_at(capture_to)
                    else ""
                )
                # Figurine OCR: after Bxg3, Qf2 → Bf2. Do not override Bd4 after Qxe5+.
                and (
                    (
                        board.piece_at(capture_to) is not None
                        and board.piece_at(capture_to).symbol().upper() == "B"
                        and _piece_class(token) in ("Q", "R")
                    )
                    or _piece_class(token)
                    == (
                        board.piece_at(capture_to).symbol().upper()
                        if board.piece_at(capture_to)
                        else ""
                    )
                )
            )
            if better:
                overrides.append((alt_rest, san, move))
        if not overrides:
            return _strip_marks(board.san(exact)), exact
        if round_trip:
            pawn_wins = [
                (san, move)
                for _key, san, move in overrides
                if _piece_class(san) == "P"
            ]
            if len(pawn_wins) == 1:
                return pawn_wins[0]
        overrides.sort(key=lambda row: row[0], reverse=True)
        best_rest = overrides[0][0]
        winners = [(san, move) for key, san, move in overrides if key == best_rest]
        if len(winners) == 1:
            return winners[0]
        return _strip_marks(board.san(exact)), exact

    scored: list[tuple[tuple[int, int, int, int], str, chess.Move]] = []
    for san, move in cands:
        _ex_c, strip_c, swap_c = _classify_choice(
            token, san, exact=exact, chosen=move, n_cands=n
        )
        link_c = 1 if move.from_square in trail else 0
        local = (strip_c, link_c, -swap_c, strip_c)
        scored.append((_combine_keys(local, rest_after(move)), san, move))
    scored.sort(key=lambda row: row[0], reverse=True)
    best_key = scored[0][0]
    winners = [(san, move) for key, san, move in scored if key == best_key]
    if len(winners) == 1:
        return winners[0]
    dest_m = _DEST_RE.search(_strip_marks(token))
    hint = _dest_capture_piece_hint(rest, dest_m.group(1) if dest_m else "")
    if hint:
        hinted = [(san, move) for san, move in winners if _piece_class(san) == hint]
        if len(hinted) == 1:
            return hinted[0]
    return None


def _peek_san_tokens(
    text: str,
    start: int,
    *,
    after_fm: int | None = None,
    after_black: bool | None = None,
) -> list[str]:
    """
    Upcoming SAN tokens after ``start`` at the same parenthesis/bracket depth.

    Nested ``(...)`` / ``[...]`` sidelines are skipped so an outer line does not
    look ahead into a fork; tokens inside the current sideline remain visible.

    Stops before a sibling alternative: earlier fullmove, or same fullmove+side
    as the token we just scored (``37...Qd7`` must not peek into ``37...Rxb6``).
    """
    out: list[str] = []
    pos = start
    depth = 0
    while pos < len(text) and len(out) < _LOOKAHEAD:
        ch = text[pos]
        if ch in "([":
            depth += 1
            pos += 1
            continue
        if ch in ")]":
            if depth == 0:
                break
            depth -= 1
            pos += 1
            continue
        if ch == ";" and depth == 0:
            # Sibling alternative inside the same parenthesis.
            break
        if depth:
            pos += 1
            continue
        if _in_threat_phrase(text, pos):
            m_skip = _SAN_TOKEN_RE.match(text, pos)
            if m_skip and not (m_skip.group("head") or ""):
                pos = m_skip.end()
                continue
        m = _SAN_TOKEN_RE.match(text, pos)
        if not m:
            pos += 1
            continue
        head = m.group("head") or ""
        if head and after_fm is not None:
            hm = re.match(r"(\d+)", head)
            if hm:
                fm = int(hm.group(1))
                label_black = "..." in head or ".." in head
                if fm < after_fm:
                    break
                if (
                    fm == after_fm
                    and after_black is not None
                    and label_black == after_black
                ):
                    break
        out.append(m.group("san"))
        pos = m.end()
    return out


def legalize_note_prose(board: chess.Board, text: str) -> str:
    """
    Repair SAN-like tokens in book-note prose against ``board``.

    For each token, consider destination-sharing legal moves. When several fit,
    pick the unique maximizer of continuation fidelity:

    1. exact / bare-fill / pawn-strip matches in the rest of the line
    2. fewer piece-letter swaps
    3. more false piece→pawn strips (OCR bishop/pawn)
    4. more same-piece tours within the variation trail

    Parenthetical / bracket sidelines fork board + trail; they do not poison the outer cursor.
    Replace only when the choice is unique under that order (else keep parse or text).
    """
    if not text or not text.strip():
        return text

    work = board.copy()
    root = board.copy()
    root_fm = root.fullmove_number
    root_black = root.turn == chess.BLACK
    trail: frozenset[int] = frozenset()
    # (outer_board, outer_trail, alt_root_board|None, alt_root_trail|None, alt_fullmove|None)
    stack: list[
        tuple[
            chess.Board,
            frozenset[int],
            chess.Board | None,
            frozenset[int] | None,
            int | None,
        ]
    ] = []
    out: list[str] = []
    pos = 0
    alt_root: chess.Board | None = None
    alt_trail: frozenset[int] | None = None
    alt_fullmove: int | None = None
    # Square where each side's last capture landed (for retreat disambiguation).
    capture_to_by_color: dict[bool, int | None] = {True: None, False: None}

    def apply_move(move: chess.Move) -> None:
        nonlocal trail
        side = work.turn
        is_cap = work.is_capture(move) or work.is_en_passant(move)
        work.push(move)
        new_trail = set(trail)
        new_trail.discard(move.from_square)
        new_trail.add(move.to_square)
        trail = frozenset(new_trail)
        capture_to_by_color[side] = move.to_square if is_cap else None

    def push_fork(*, allow_or_reset: bool) -> None:
        nonlocal work, trail, alt_root, alt_trail, alt_fullmove
        stack.append(
            (
                work.copy(),
                trail,
                alt_root,
                alt_trail,
                alt_fullmove,
            )
        )
        if not allow_or_reset:
            alt_root = None
            alt_trail = None
            alt_fullmove = None
            return
        peek = text[pos + 1 : pos + 24]
        m_or = re.match(r"\s*or\s+(\d+)\.", peek, re.I)
        if m_or and work.move_stack:
            work.pop()
            trail = frozenset(mv.to_square for mv in work.move_stack[-8:])
            alt_root = work.copy()
            alt_trail = trail
            alt_fullmove = int(m_or.group(1))
        else:
            alt_root = None
            alt_trail = None
            alt_fullmove = None

    while pos < len(text):
        ch = text[pos]
        if ch == "(" or ch == "{":
            push_fork(allow_or_reset=True)
            out.append("(" if ch == "{" else ch)
            pos += 1
            continue
        if ch == "[":
            push_fork(allow_or_reset=False)
            peek = text[pos + 1 : pos + 20]
            m_alt = re.match(r"\s*(\d+)\.", peek)
            # Same-move white alternative: 39.g3 [39.Qe3 …] — share decision ply
            if (
                m_alt
                and work.move_stack
                and work.turn == chess.BLACK
                and work.fullmove_number == int(m_alt.group(1))
            ):
                work.pop()
                trail = frozenset(mv.to_square for mv in work.move_stack[-8:])
            out.append(ch)
            pos += 1
            continue
        if ch in ")]}" and stack:
            work, trail, alt_root, alt_trail, alt_fullmove = stack.pop()
            out.append(")" if ch == "}" else ch)
            pos += 1
            continue

        # Piece maneuver prose (Bg4-e6), not two SANs
        man = _MANEUVER_RE.match(text, pos)
        if man:
            out.append(man.group(0))
            pos = man.end()
            continue

        m = _SAN_TOKEN_RE.match(text, pos)
        if not m:
            chain = _PAWN_CHAIN_RE.match(text, pos)
            if chain:
                out.append(chain.group(0))
                pos = chain.end()
                continue
            out.append(ch)
            pos += 1
            continue

        chain = _PAWN_CHAIN_RE.match(text, pos)
        if chain and not (m.group("head") or ""):
            if text[pos : pos + len(m.group("san"))] == m.group("san"):
                end_chain = chain.end()
                if end_chain > m.end():
                    out.append(chain.group(0))
                    pos = end_chain
                    continue

        head = m.group("head") or ""
        san = m.group("san")
        marks = m.group("marks") or ""
        end = m.end()

        # Prose threats are not a playable line:
        # "(threatening Qf8# …)" / "Threatening 45.Nc3" / "threats Ne6 and Bg4"
        if _in_threat_phrase(text, pos):
            out.append(head + san + marks)
            pos = end
            continue

        # Same-ply alternatives reset to the note's decision board:
        # "Weak is: 37...Qd7? … Black loses after: 37...Rxb6"
        if head:
            hm = re.match(r"(\d+)", head)
            if hm and int(hm.group(1)) == root_fm:
                label_black = "..." in head or ".." in head
                if label_black == root_black:
                    work = root.copy()
                    trail = frozenset()
                    capture_to_by_color = {True: None, False: None}

        if head and alt_root is not None and alt_fullmove is not None:
            hm = re.match(r"(\d+)", head)
            if hm and int(hm.group(1)) == alt_fullmove:
                work = alt_root.copy()
                trail = alt_trail or frozenset()
                capture_to_by_color = {True: None, False: None}

        peek_fm: int | None = None
        peek_black: bool | None = None
        if head:
            _hm = re.match(r"(\d+)", head)
            if _hm:
                peek_fm = int(_hm.group(1))
                peek_black = "..." in head or ".." in head
        rest = _peek_san_tokens(
            text,
            end,
            after_fm=peek_fm,
            after_black=peek_black,
        )
        chosen = _choose_move(
            work,
            san,
            rest,
            trail,
            capture_to=capture_to_by_color[work.turn],
        )
        replacement = san
        if chosen is not None:
            _cand_san, move = chosen
            live = work.san(move).rstrip("?!")
            apply_move(move)
            replacement = live
        else:
            parsed = _try_parse(work, san)
            if parsed is not None:
                live = work.san(parsed).rstrip("?!")
                apply_move(parsed)
                replacement = live

        # Preserve explicit mate mark from the source token when still a mate SAN.
        if "#" in san and "#" not in replacement and replacement.rstrip("+#") == _strip_marks(san):
            replacement = _strip_marks(replacement) + "#"
        elif "#" in san and "#" not in replacement:
            # Source wrote mate; keep # if live move is mate-shaped same dest.
            if replacement.endswith("+"):
                replacement = replacement[:-1] + "#"

        out.append(head + replacement + marks)
        pos = end

    return "".join(out)


def legalize_aligned_note_text(
    game: chess.pgn.Game,
    ply: int,
    text: str,
) -> str:
    """Legalize note prose using the board before the anchored mainline ply."""
    if not text:
        return text
    return legalize_note_prose(board_before_ply(game, ply), text)
