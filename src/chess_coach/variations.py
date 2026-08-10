from __future__ import annotations

import re

import chess
import chess.pgn

from chess_coach.ocr_chess import ocr_clean_chess, san_tokens

BOOK_VAR_TAG = "Book line"
ENGINE_VAR_TAG = "Engine best"

_LINE_HINT_RE = re.compile(
    r"(?i)\b(?:"
    r"better was|instead(?: of)?|an interesting alternative was|alternative was|"
    r"not\s+\d|but not|if\s+\d|preferable to play|the try|or\s+\d|"
    r"a possible continuation is|for example|points?\s+out|"
    r"imprecision|serious (?:mistake|imprecision)|"
    r"white is forced|black is forced|is (?:met )?by"
    r")\b"
)
_NUMBERED_CHUNK_RE = re.compile(
    r"(?:\d+\.(?:\.\.)?\s*[NBRQKOa-h][^\s.;,]{1,8}"
    r"(?:\s+\d+\.(?:\.\.)?\s*[NBRQKOa-h][^\s.;,]{1,8}){0,10}"
    r"|(?:\d+\.(?:\.\.)?\s*)?[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?"
    r"(?:\s+(?:\d+\.(?:\.\.)?\s*)?[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?){0,10})",
    re.I,
)


def _fix_token(token: str) -> list[str]:
    t = ocr_clean_chess(token).strip().rstrip("?!#").strip()
    if not t:
        return []
    out = [t]
    # OCR often drops piece letter on captures: xb5 → try Nxb5/Bxb5/...
    if re.fullmatch(r"x[a-h][1-8]", t, re.I):
        for piece in "NBRQK":
            out.append(piece + t)
    if re.fullmatch(r"[a-h]x[a-h][1-8]", t, re.I):
        out.append(t)  # pawn capture already
    # 0-0 vs O-O
    if t in {"0-0", "0-0-0"}:
        out.append(t.replace("0", "O"))
    return list(dict.fromkeys(out))


def greedy_legal_line(
    board: chess.Board,
    tokens: list[str],
    *,
    max_moves: int = 12,
    max_skip: int = 2,
) -> list[chess.Move]:
    """Play as many tokens as possible; skip a little OCR junk between hits."""
    work = board.copy()
    moves: list[chess.Move] = []
    skips = 0
    for raw in tokens:
        if len(moves) >= max_moves:
            break
        parsed: chess.Move | None = None
        for cand in _fix_token(raw):
            try:
                parsed = work.parse_san(cand)
                break
            except ValueError:
                continue
        if parsed is None:
            skips += 1
            if skips > max_skip and moves:
                break
            continue
        work.push(parsed)
        moves.append(parsed)
        skips = 0
    return moves


def candidate_line_texts(text: str) -> list[str]:
    """Split book prose into variation-shaped chunks worth trying on the board."""
    if not text:
        return []
    cleaned = ocr_clean_chess(text)
    chunks: list[str] = []
    for match in re.finditer(r"\(([^)]{6,240})\)", cleaned):
        chunks.append(match.group(1))
    for match in _LINE_HINT_RE.finditer(cleaned):
        tail = cleaned[match.start() : match.start() + 220]
        stop = re.search(r"[.!?](?:\s|[A-Z]|$)", tail[20:])
        chunks.append(tail[: 20 + (stop.start() if stop else 160)])
    for match in _NUMBERED_CHUNK_RE.finditer(cleaned):
        piece = match.group(0).strip()
        if len(san_tokens(piece)) >= 1:
            chunks.append(piece)
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for c in chunks:
        key = re.sub(r"\s+", " ", c).strip().lower()
        if len(key) < 3 or key in seen:
            continue
        seen.add(key)
        out.append(c.strip())
    return out[:24]


def playable_lines_from_text(
    board: chess.Board,
    text: str,
    *,
    also_after: chess.Board | None = None,
) -> list[tuple[chess.Board, list[chess.Move], str]]:
    """
    Return (root_board, moves, source_chunk) lines legal from board and/or also_after.
    """
    roots = [board]
    if also_after is not None and also_after.fen() != board.fen():
        roots.append(also_after)
    found: list[tuple[chess.Board, list[chess.Move], str]] = []
    seen_keys: set[str] = set()
    for chunk in candidate_line_texts(text):
        tokens = san_tokens(chunk)
        if not tokens:
            continue
        for root in roots:
            moves = greedy_legal_line(root, tokens)
            if not moves:
                continue
            key = root.fen() + "|" + " ".join(m.uci() for m in moves)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            found.append((root, moves, chunk))
            break
    return found


def _variation_already_present(parent: chess.pgn.GameNode, first: chess.Move) -> bool:
    return any(v.move == first for v in parent.variations)


def add_move_line(
    parent: chess.pgn.GameNode,
    board: chess.Board,
    moves: list[chess.Move],
    *,
    comment: str = "",
) -> bool:
    """Attach moves as a sideline starting from parent (position == board)."""
    if not moves:
        return False
    if parent.variations and parent.variation(0).move == moves[0]:
        # first move is the mainline — extend/create deeper only if rest differs
        if len(moves) == 1:
            return False
        # start sideline from after main move using remaining? skip — caller should root correctly
        return False
    if _variation_already_present(parent, moves[0]):
        return False
    work = board.copy()
    node: chess.pgn.GameNode | None = None
    for i, move in enumerate(moves):
        if move not in work.legal_moves:
            return node is not None
        if node is None:
            node = parent.add_variation(move)
            if comment:
                node.comment = comment
        else:
            node = node.add_main_variation(move)
        work.push(move)
        _ = i
    return node is not None


def find_parent_for_board(
    game: chess.pgn.Game,
    target_fen: str,
) -> tuple[chess.pgn.GameNode, chess.Board] | None:
    """Walk mainline to the node whose board position equals target_fen (before child moves)."""
    board = game.board()
    if board.fen() == target_fen:
        return game, board
    node: chess.pgn.GameNode = game
    while node.variations:
        nxt = node.variation(0)
        board.push(nxt.move)
        node = nxt
        # after push, children of node are from this fen
        if board.fen() == target_fen:
            return node, board.copy()
    return None


def inject_book_lines_at_ply(
    game: chess.pgn.Game,
    ply: int,
    text: str,
    *,
    max_lines: int = 4,
) -> int:
    """
    Parse book variation text at a mainline ply and add playable PGN forks.
    Tries position before the ply move and after it.
    """
    if ply < 1 or not text:
        return 0
    board_before = game.board()
    parent: chess.pgn.GameNode = game
    main_node: chess.pgn.GameNode | None = None
    for i in range(ply):
        if not parent.variations:
            return 0
        main_node = parent.variation(0)
        if i < ply - 1:
            board_before.push(main_node.move)
            parent = main_node
    if main_node is None:
        return 0
    board_after = board_before.copy()
    board_after.push(main_node.move)

    added = 0
    for root, moves, chunk in playable_lines_from_text(
        board_before, text, also_after=board_after
    ):
        if added >= max_lines:
            break
        if len(moves) < 2:
            continue
        label = f"{BOOK_VAR_TAG}: {re.sub(r'\s+', ' ', chunk)[:120]}"
        if root.fen() == board_before.fen():
            ok = add_move_line(parent, board_before, moves, comment=label)
        elif root.fen() == board_after.fen():
            ok = add_move_line(main_node, board_after, moves, comment=label)
        else:
            ok = False
        if ok:
            added += 1
    return added


def inject_engine_line(
    parent: chess.pgn.GameNode,
    board: chess.Board,
    *,
    best_uci: str | None,
    played_uci: str | None,
    pv_san: list[str] | None = None,
    depth: int | None = None,
) -> bool:
    """Add engine best (+ short PV) as a sideline when it differs from the played move."""
    if not best_uci or best_uci == played_uci:
        return False
    try:
        best = chess.Move.from_uci(best_uci)
    except ValueError:
        return False
    if best not in board.legal_moves:
        return False
    if _variation_already_present(parent, best):
        return False
    moves = [best]
    # extend with PV sans if they continue legally after best
    if pv_san:
        work = board.copy()
        work.push(best)
        # pv often starts with best_san — drop if duplicate
        tokens = list(pv_san)
        if tokens:
            try:
                first = work.parse_san(tokens[0])
                # if first is from before best, skip
                _ = first
            except ValueError:
                pass
            # Prefer tokens after the first if first equals best
            start = 0
            try:
                if board.san(best).rstrip("?!+#") == tokens[0].rstrip("?!+#"):
                    start = 1
            except ValueError:
                start = 0
            extra = greedy_legal_line(work, tokens[start:], max_moves=6, max_skip=1)
            moves.extend(extra)
    if len(moves) < 2:
        return False
    tag = ENGINE_VAR_TAG if depth is None else f"{ENGINE_VAR_TAG} (d{depth})"
    return add_move_line(parent, board, moves, comment=tag)


def strip_auto_variations(
    game: chess.pgn.Game,
    *,
    book: bool = True,
    engine: bool = True,
) -> None:
    """Remove previously injected Book/Engine sidelines (keep foreign ones)."""

    def _walk(node: chess.pgn.GameNode) -> None:
        for var in list(node.variations)[1:]:
            comment = var.comment or ""
            drop = (book and comment.startswith(BOOK_VAR_TAG)) or (
                engine and comment.startswith(ENGINE_VAR_TAG)
            )
            if drop:
                node.variations.remove(var)
        for var in list(node.variations):
            _walk(var)

    _walk(game)


def serialize_forks_from_parent(
    parent: chess.pgn.GameNode,
    board_before: chess.Board,
    *,
    max_depth: int = 10,
) -> list[dict]:
    """Sidelines (non-main children) as playable fork payloads for the viewer."""
    if len(parent.variations) < 2:
        return []
    forks: list[dict] = []
    for var in parent.variations[1:]:
        work = board_before.copy()
        moves: list[dict] = []
        cur: chess.pgn.GameNode | None = var
        steps = 0
        kind = "book"
        comment = (var.comment or "").strip()
        if comment.startswith(ENGINE_VAR_TAG):
            kind = "engine"
        elif comment.startswith(BOOK_VAR_TAG):
            kind = "book"
        else:
            kind = "line"
        while cur is not None and cur.move is not None and steps < max_depth:
            try:
                san = work.san(cur.move)
                uci = cur.move.uci()
                fen_before = work.fen()
                work.push(cur.move)
            except ValueError:
                break
            moves.append(
                {
                    "san": san,
                    "uci": uci,
                    "fen_before": fen_before,
                    "fen": work.fen(),
                    "fullmove": chess.Board(fen_before).fullmove_number,
                    "side": "white" if chess.Board(fen_before).turn == chess.WHITE else "black",
                    "comment": (cur.comment or "").strip(),
                }
            )
            cur = cur.variation(0) if cur.variations else None
            steps += 1
        if len(moves) >= 2:
            forks.append(
                {
                    "kind": kind,
                    "label": comment[:80] if comment else moves[0]["san"],
                    "moves": moves,
                }
            )
    return forks
