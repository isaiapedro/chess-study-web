from __future__ import annotations

import re
from dataclasses import dataclass, field

import chess
import chess.pgn

from chess_coach.chapter import BookMoveNote
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
    """
    head = ocr_clean_chess((note.text or "")[:120])
    tokens = _SAN_TOKEN_RE.findall(head)
    if not tokens:
        return ply
    index = {m[0]: m for m in mainline}
    cur = ply
    seen_label = False
    for tok in tokens:
        if not seen_label:
            if _san_eq(tok, note.san_hint) or (cur in index and _san_eq(tok, index[cur][3])):
                seen_label = True
            continue
        nxt = cur + 1
        if nxt not in index:
            break
        if _san_eq(index[nxt][3], tok):
            cur = nxt
        else:
            break
    # Position-of-interest prose after a move-pair: prefer last reply if we only matched label
    if (
        cur == ply
        and re.search(r"reached the position|position of interest|diagram", note.text or "", re.I)
        and ply + 1 in index
    ):
        reply = index[ply + 1][3]
        if any(_san_eq(tok, reply) for tok in tokens):
            cur = ply + 1
    return cur


def align_notes_to_game(
    game: chess.pgn.Game,
    notes: list[BookMoveNote],
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
        # skip pure move-list crumbs that snuck through
        if len(re.findall(r"\b\d+\.", prose)) >= 4 and len(_ENGLISH_HINT_RE.findall(prose)) < 2:
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
    return [by_ply[k] for k in sorted(by_ply)]
