from __future__ import annotations

import re
from dataclasses import dataclass, field

import chess
import chess.pgn

from chess_coach.chapter import BookMoveNote
from chess_coach.note_legalize import legalize_aligned_note_text
from chess_coach.ocr_chess import (
    _ENGLISH_HINT_RE,
    _PROSE_START_RE,
    _SAN_TOKEN_RE,
    clean_book_note,
    extract_variation_snippets,
    ocr_clean_chess,
    prose_is_usable,
    split_movelist_and_prose,
)

_RESULT_RE = re.compile(r"\b(?:1-0|0-1|1/2-1/2|½-½)\b")
_FINAL_REMARKS_RE = re.compile(r"(?i)\bFinal\s+remarks\b")

# Longest-first so ?? wins over ?, ?! over !
_BOOK_MARKS = ("!!", "??", "!?", "?!", "!", "?")
_BOOK_MARK_NAG = {"!": 1, "?": 2, "!!": 3, "??": 4, "!?": 5, "?!": 6}
_BOOK_MARK_DISPLAY = frozenset({"!", "?", "?!", "??", "!!", "!?"})


def split_san_mark(san: str) -> tuple[str, str]:
    """Split ``Na4!`` / ``Qf1?!`` into (``Na4``, ``!``) / (``Qf1``, ``?!``)."""
    s = (san or "").strip()
    if not s:
        return "", ""
    # Check/mate before annotation: Qh7+! → base Qh7+, mark !
    for mark in _BOOK_MARKS:
        if s.endswith(mark):
            return s[: -len(mark)].rstrip(), mark
    return s, ""


def collect_mainline_book_marks(
    game: chess.pgn.Game,
    notes: list[BookMoveNote],
    *,
    context: str = "",
) -> dict[int, str]:
    """
    Map mainline ply → book annotation mark (! / ?! / ? / ?? / …).

    Sources: note ``san_hint`` and every labeled move in note bodies / context
    that matches a mainline ply (OCR-tolerant), e.g. ``44.Na4!`` inside a
    longer note.
    """
    from chess_coach.chess_text_grammar import MOVE_LABEL_RE

    mainline = _mainline(game)
    marks: dict[int, str] = {}

    def try_set(fullmove: int, side: str, san: str) -> None:
        base, mark = split_san_mark(san)
        if mark not in _BOOK_MARK_DISPLAY or not base:
            return
        for ply, g_fm, g_side, g_san in mainline:
            if g_fm != fullmove or g_side != side:
                continue
            if _san_eq(base, g_san) or _san_similar(base, g_san):
                marks[ply] = mark
                return
            # Figurine OCR salad (tlia4 ≈ Na4): same destination on this slot
            bd, gd = _san_dest(base), _san_dest(g_san)
            if bd and bd == gd:
                marks[ply] = mark
                return

    blobs = [ocr_clean_chess(n.text or "") for n in notes]
    if context:
        blobs.append(ocr_clean_chess(context))
    for blob in blobs:
        for m in MOVE_LABEL_RE.finditer(blob):
            side = "black" if m.group("dots") else "white"
            try_set(int(m.group("num")), side, m.group("move"))
    # Note heads win over mid-body mentions of the same ply
    for note in notes:
        if note.san_hint:
            try_set(note.fullmove, note.side, note.san_hint)
    return marks


def apply_book_mark_nags(game: chess.pgn.Game, marks: dict[int, str]) -> int:
    """Write book !/? marks as NAGs on mainline nodes. Returns how many set."""
    if not marks:
        return 0
    node: chess.pgn.GameNode = game
    ply = 0
    applied = 0
    while node.variations:
        node = node.variation(0)
        ply += 1
        mark = marks.get(ply)
        if not mark:
            continue
        nag = _BOOK_MARK_NAG.get(mark)
        if nag is None:
            continue
        for old in (1, 2, 3, 4, 5, 6):
            node.nags.discard(old)
        node.nags.add(nag)
        applied += 1
    return applied


@dataclass
class AlignedBookNote:
    ply: int
    fullmove: int
    side: str
    san: str
    text: str
    variations: list[str] = field(default_factory=list)


def _norm_san(san: str) -> str:
    s = (san or "").strip().rstrip("?!#+")
    s = s.replace("0-0-0", "O-O-O").replace("0-0", "O-O")
    return s.lower()


def _san_eq(a: str, b: str) -> bool:
    return _norm_san(a) == _norm_san(b)


def _san_dest(san: str) -> str:
    m = re.search(r"[a-h][1-8](?!.*[a-h][1-8])", _norm_san(san))
    return m.group(0) if m else ""


def _san_piece(san: str) -> str:
    s = _norm_san(san)
    if s.startswith("o-o"):
        return "k"
    return s[0] if s and s[0] in "nbrqk" else "p"


def _san_similar(hint: str, game_san: str) -> bool:
    """
    OCR-tolerant match: Qf1≈Qf2 (rank drift), Qg3≈Rg3 / Qf3≈Bf3 (piece drift,
    same square), plus substring equality used by ``_san_eq`` neighbors.
    """
    h, g = _norm_san(hint), _norm_san(game_san)
    if not h or not g:
        return False
    if h == g or h in g or g.endswith(h) or h.endswith(g):
        return True
    hd, gd = _san_dest(h), _san_dest(g)
    if not hd or not gd:
        return False
    if hd == gd:
        return True
    if _san_piece(h) == _san_piece(g) and hd[0] == gd[0]:
        return abs(int(hd[1]) - int(gd[1])) <= 1
    return False


def _mainline(game: chess.pgn.Game) -> list[tuple[int, int, str, str]]:
    out: list[tuple[int, int, str, str]] = []
    board = game.board()
    node: chess.pgn.GameNode = game
    ply = 0
    while node.variations:
        nxt = node.variation(0)
        ply += 1
        san = board.san(nxt.move)
        fullmove = board.fullmove_number
        side = "white" if board.turn == chess.WHITE else "black"
        out.append((ply, fullmove, side, san))
        board.push(nxt.move)
        node = nxt
    return out


def _ply_for_note(fullmove: int, side: str) -> int:
    return fullmove * 2 - (1 if side == "white" else 0)


def _anchor_ply(
    mainline: list[tuple[int, int, str, str]],
    note: BookMoveNote,
    prefix_moves: list[tuple[int | None, str | None, str]],
) -> int | None:
    target = _ply_for_note(note.fullmove, note.side)

    # 1) Trust the labeled move when it matches mainline (most reliable).
    for ply, g_fm, g_side, g_san in mainline:
        if g_fm == note.fullmove and g_side == note.side and _san_eq(g_san, note.san_hint):
            return ply

    same_slot = [m for m in mainline if m[1] == note.fullmove and m[2] == note.side]
    if same_slot and note.san_hint:
        hint = _norm_san(note.san_hint)
        for ply, _fm, _side, g_san in same_slot:
            g = _norm_san(g_san)
            if not hint:
                continue
            if hint == g or hint in g or g.endswith(hint) or hint.endswith(g):
                return ply
            if _san_similar(hint, g_san):
                return ply

    # 2) Walk leading score fragments, but only accept hits near the labeled move.
    last_hit: int | None = None
    for fullmove, side, san in prefix_moves:
        if fullmove is None or side is None:
            start = last_hit or max(0, target - 6)
            for ply, _fm, _side, g_san in mainline:
                if ply <= start:
                    continue
                if abs(ply - target) > 6:
                    if ply > target + 6:
                        break
                    continue
                if _san_eq(g_san, san):
                    last_hit = ply
                    break
            continue
        for ply, g_fm, g_side, g_san in mainline:
            if g_fm == fullmove and g_side == side and _san_eq(g_san, san):
                if abs(ply - target) <= 8:
                    last_hit = ply
                break
    if last_hit is not None:
        return last_hit

    # 3) Nearby identical SAN (variations often reprint the same move).
    best: tuple[int, int] | None = None
    hint = _norm_san(note.san_hint)
    # Refuse to latch OCR garbage ('m, i, etc.) onto a distant same-SAN hit.
    if hint and re.fullmatch(r"[nbrqka-h1-8x+#=o\-]{2,}", hint):
        for ply, _fm, _side, g_san in mainline:
            if _san_eq(g_san, note.san_hint):
                dist = abs(ply - target)
                if best is None or dist < best[0]:
                    best = (dist, ply)
        if best is not None and best[0] <= 3:
            return best[1]

    if same_slot and (not hint or len(hint) <= 1 or not re.fullmatch(r"[nbrqka-h1-8x+#=o\-]{2,}", hint)):
        # Empty / garbage hint: trust the labeled fullmove+side slot (e.g. prose
        # retargeted from 1.d4 dump onto 21... with san_hint cleared).
        return same_slot[0][0]
    return None


def _extend_anchor_through_replies(
    mainline: list[tuple[int, int, str, str]],
    ply: int,
    note: BookMoveNote,
) -> int:
    """
    Books often write `22.cxb5 Rxc5` then a diagram. The note label is White's move,
    but the diagram / 'position of interest' is after Black's reply. Walk any leading
    SAN tokens after the labeled move and advance the anchor.

    Label may exist only on the note header — body often starts at the reply
    (`21.bxc5` note whose text begins `Nxb5 An interesting…`).
    """
    head = ocr_clean_chess((note.text or "")[:120])
    tokens = _SAN_TOKEN_RE.findall(head)
    if not tokens:
        return ply
    index = {m[0]: m for m in mainline}
    cur = ply
    i = 0
    if _san_eq(tokens[0], note.san_hint) or (
        cur in index and _san_eq(tokens[0], index[cur][3])
    ):
        i = 1
    for tok in tokens[i:]:
        nxt = cur + 1
        if nxt not in index:
            break
        if _san_eq(index[nxt][3], tok):
            cur = nxt
        else:
            break
    # Position-of-interest / diagram after a White+Black move-pair: books label
    # White's move but the assessment is of the position after Black's reply.
    if (
        cur == ply
        and re.search(r"reached the position|position of interest|\bdiagram\b", note.text or "", re.I)
        and ply + 1 in index
        and index[ply][2] == "white"
        and index[ply + 1][2] == "black"
    ):
        cur = ply + 1
    return cur


def _result_cut(text: str) -> int | None:
    """Index just after the last game-result marker (1-0 / 0-1 / draw)."""
    last: re.Match[str] | None = None
    for m in _RESULT_RE.finditer(text or ""):
        last = m
    return last.end() if last else None


def _strip_post_game_tail(prose: str) -> str:
    """Drop result + Final remarks from a mid-game note (belongs on the finale)."""
    text = (prose or "").strip()
    if not text:
        return ""
    m = _RESULT_RE.search(text)
    if m:
        return text[: m.start()].strip()
    m = _FINAL_REMARKS_RE.search(text)
    if m:
        return text[: m.start()].strip()
    return text


def extract_final_move_book_tail(
    context: str,
    *,
    last_fullmove: int,
    last_side: str,
    last_san: str,
) -> str:
    """
    Book text after the game's final move until the next game/chapter.

    Citation ``context`` is already sliced to the next game boundary. Prefer the
    last mainline move when it appears in the score; otherwise take everything
    after the result marker (``1-0`` / …), including Final remarks.
    """
    from chess_coach.chess_text_grammar import MOVE_LABEL_RE

    raw = (context or "").strip()
    if not raw:
        return ""
    text = ocr_clean_chess(raw)
    cut: int | None = None
    for m in MOVE_LABEL_RE.finditer(text):
        fm = int(m.group("num"))
        side = "black" if m.group("dots") else "white"
        if fm != last_fullmove or side != last_side:
            continue
        if _san_similar(m.group("move"), last_san):
            cut = m.end()
    if cut is None:
        cut = _result_cut(text)
    if cut is None:
        m = _FINAL_REMARKS_RE.search(text)
        if m:
            cut = m.start()
    if cut is None:
        return ""
    tail = text[cut:]
    # Drop page chrome that rides the chapter footer
    tail = re.sub(r"(?m)^\d+\s+Family\b.*$", "", tail)
    tail = re.sub(r"(?m)^Chapter\s+\d+\s*[-–—].*$", "", tail)
    tail = re.sub(r"(?m)^Family\s+\d+\b.*$", "", tail)
    tail = clean_book_note(tail)
    tail = re.sub(r"\s+", " ", tail).strip()
    # Prefer keeping "Final remarks" as the epilogue lead-in
    m = _FINAL_REMARKS_RE.search(tail)
    if m and m.start() <= 40:
        tail = tail[m.start() :].strip()
    elif m and _RESULT_RE.match(tail):
        # Result already consumed by cut; remarks may follow noise
        tail = tail[m.start() :].strip()
    if not prose_is_usable(tail, min_alpha=40):
        return ""
    return tail[:6000]


def align_notes_to_game(
    game: chess.pgn.Game,
    notes: list[BookMoveNote],
    *,
    context: str = "",
) -> list[AlignedBookNote]:
    mainline = _mainline(game)
    if not mainline:
        return []

    by_ply: dict[int, AlignedBookNote] = {}
    for note in notes:
        prefix, prose = split_movelist_and_prose(note.text)
        prose, variations = extract_variation_snippets(prose)

        if not prose_is_usable(prose):
            fallback = clean_book_note(note.text)
            m = _PROSE_START_RE.search(fallback)
            if m:
                fallback = fallback[m.start() :]
            # also allow !/? commentary and mid-sentence coaching
            if not prose_is_usable(fallback):
                # strip leading move-salad until English kicks in
                m2 = re.search(
                    r"(?:[!?]+\s+|(?=\b(?:A |The |This |White |Black |There |Something |Getting |Now |After |His |In |Not )))",
                    fallback,
                )
                if m2:
                    fallback = fallback[m2.start() :].strip()
            if not prose_is_usable(fallback):
                continue
            prose = fallback
        prose = re.sub(r"\ba\s+b\s+c\s+d\s+e\s+f\s+g\s+h\b", " ", prose, flags=re.I)
        prose = re.sub(r"\s+", " ", prose).strip()
        prose = re.sub(r"^[?!+\s]+", "", prose).strip()
        if re.search(r"\ba\s+b\s+c\s+d\b", prose, re.I):
            m = _PROSE_START_RE.search(prose)
            if m:
                prose = prose[m.start() :].strip()
            elif not prose_is_usable(prose, min_alpha=60):
                continue
        if not prose_is_usable(prose):
            continue
        # skip pure move-list crumbs that snuck through (keep "If 28... … arrives faster")
        if (
            not _PROSE_START_RE.search(prose)
            and len(re.findall(r"\b\d+\.", prose)) >= 4
            and len(_ENGLISH_HINT_RE.findall(prose)) < 2
        ):
            continue
        ply = _anchor_ply(mainline, note, prefix)
        if ply is None:
            continue
        ply = _extend_anchor_through_replies(mainline, ply, note)
        _p, fullmove, side, san = next(m for m in mainline if m[0] == ply)
        # Reject anchors that wandered far from the labeled move number
        # (e.g. variation "Bg5 and Black…" latching onto 15.Bg5).
        if abs(fullmove - note.fullmove) > 5:
            continue
        existing = by_ply.get(ply)
        if existing is None:
            by_ply[ply] = AlignedBookNote(
                ply=ply,
                fullmove=fullmove,
                side=side,
                san=san,
                text=prose,
                variations=list(variations),
            )
        else:
            if prose and prose not in existing.text:
                existing.text = (existing.text + " " + prose).strip()
            for var in variations:
                if var not in existing.variations:
                    existing.variations.append(var)

    last_ply, last_fm, last_side, last_san = mainline[-1]
    tail = extract_final_move_book_tail(
        context,
        last_fullmove=last_fm,
        last_side=last_side,
        last_san=last_san,
    )
    if tail:
        for note in by_ply.values():
            if note.ply != last_ply:
                before = note.text
                note.text = _strip_post_game_tail(note.text)
                if note.text != before:
                    note.variations = []
                if not prose_is_usable(note.text):
                    note.text = ""
        by_ply[last_ply] = AlignedBookNote(
            ply=last_ply,
            fullmove=last_fm,
            side=last_side,
            san=last_san,
            text=tail,
            variations=[],
        )

    aligned = [by_ply[k] for k in sorted(by_ply) if by_ply[k].text.strip()]
    for note in aligned:
        note.text = legalize_aligned_note_text(game, note.ply, note.text)
        note.variations = [
            legalize_aligned_note_text(game, note.ply, v) for v in note.variations
        ]
    return aligned
