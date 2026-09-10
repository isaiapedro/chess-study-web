"""Attach illustrative FENs / SAN windows to GPT notes that lack position locks."""

from __future__ import annotations

import re
from typing import Any

import chess

from chess_coach.rag.bookwalk_passages import BookwalkPassage

# Canonical teaching FENs (well-known theoretical / opening snapshots).
KEY_SEED_FENS: dict[str, tuple[str, str]] = {
    # fen, san_line
    "endgame.theoretical.lucena": (
        "1K1k4/1P6/8/8/8/8/r7/2R5 w - - 0 1",
        "Rd1+ Kc7 Rd4",
    ),
    "endgame.theoretical.philidor": (
        "8/8/8/4k3/8/4P3/4K3/4R3 b - - 0 1",
        "Ra6 Ke2 Ra1",
    ),
    "endgame.theoretical.vancura": (
        "8/8/P5rk/8/8/8/1R4K1/8 w - - 0 1",
        "Rb6 Kg7 a7",
    ),
    "endgame.theoretical.fortress": (
        "8/5k2/4b3/4P3/5K2/8/8/8 w - - 0 1",
        "Ke4 Bb3",
    ),
    "endgame.theoretical.triangulation": (
        "8/8/8/3k4/2p5/2K5/8/8 w - - 0 1",
        "Kd2 Kd4 Kc2",
    ),
    "endgame.strategic.active_king": (
        "8/5p2/5k2/8/5K2/8/5P2/8 w - - 0 1",
        "Ke4 Ke6 f4",
    ),
    "endgame.strategic.opposite_bishops": (
        "8/4b3/8/3k4/8/4B3/4K3/8 w - - 0 1",
        "Bd4 Ke6",
    ),
    "endgame.strategic.pawn_break": (
        "8/5pp1/4p3/4P3/5P2/8/6K1/6k1 w - - 0 1",
        "f5 gxf5 Kf3",
    ),
    "attack.greek_gift": (
        "r1bq1rk1/pppp1ppp/2n2n2/4p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQ - 0 6",
        "Bxh7+ Kxh7 Ng5+",
    ),
    "attack.f7_f2_vulnerability": (
        "rnbqkbnr/pppp1ppp/8/4p3/2B1P3/8/PPPP1PPP/RNBQK1NR b KQkq - 0 2",
        "Nc6 Qh5",
    ),
    "structure.iqp": (
        "r1bq1rk1/pp2ppbp/2n2np1/3p4/3P4/2N2NP1/PP2PPBP/R1BQ1RK1 w - - 0 9",
        "Bg5 Ne4",
    ),
    "structure.carlsbad": (
        "r1bq1rk1/pp2ppbp/2n2np1/3p4/2PP4/2N2N2/PP2PPPP/R1BQKB1R w KQ - 0 7",
        "cxd5 Nxd5",
    ),
    "structure.hanging_pawns": (
        "rnbq1rk1/pp2ppbp/3p1np1/2p5/2PPP3/2N2N2/PP2BPPP/R1BQK2R w KQ - 0 8",
        "d5 e6",
    ),
    "structure.pawn_chain": (
        "rnbqkbnr/pp3ppp/4p3/2ppP3/3P4/2P5/PP3PPP/RNBQKBNR b KQkq - 0 4",
        "Nc6 Nf3",
    ),
    "structure.maroczy_bind": (
        "rnbqkb1r/pp2pppp/2p2n2/3p4/2PP4/4PN2/PP3PPP/RNBQKB1R b KQkq - 0 4",
        "e6 Nc3",
    ),
    "structure.hedgehog": (
        "rnbqkb1r/1p2pppp/p2p1n2/8/2PNP3/8/PP3PPP/RNBQKB1R w KQkq - 0 6",
        "Nc3 e6",
    ),
    "structure.scheveningen": (
        "rnbqkb1r/pp2pp1p/3p1np1/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6",
        "Be2 Bg7",
    ),
    "structure.doubled_pawns": (
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
        "Nf3 Nc6",
    ),
    "structure.dragon_formation": (
        "rnbqkb1r/pp2pp1p/3p1np1/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6",
        "Be3 Bg7",
    ),
    "structure.passed_pawn": (
        "8/3k4/8/3P4/8/8/4K3/8 w - - 0 1",
        "Kd3 Kd6",
    ),
    "structure.caro_slav": (
        "rnbqkbnr/pp2pppp/2p5/3p4/3PP3/8/PPP2PPP/RNBQKBNR w KQkq - 0 3",
        "e5 Bf5",
    ),
}

OPENING_SAN_SEEDS: dict[str, str] = {
    "opening.sicilian": "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6",
    "opening.french": "e4 e6 d4 d5 Nc3 Bb4 e5 c5 a3 Bxc3+",
    "opening.caro_kann": "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5 Ng3 Bg6",
    "opening.ruy_lopez": "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6 O-O Be7",
    "opening.italian": "e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6 d4 exd4",
    "opening.queens_gambit": "d4 d5 c4 e6 Nc3 Nf6 Bg5 Be7 e3 O-O",
    "opening.kings_indian": "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6 Nf3 O-O",
    "opening.english": "c4 e5 Nc3 Nf6 Nf3 Nc6 g3 Bb4 Bg2 O-O",
    "opening.london_system": "d4 d5 Nf3 Nf6 Bf4 c5 e3 Nc6 c3 e6",
    "opening.scandinavian": "e4 d5 exd5 Qxd5 Nc3 Qa5 d4 Nf6 Nf3 c6",
    "opening.petroff": "e4 e5 Nf3 Nf6 Nxe5 d6 Nf3 Nxe4 d4 d5",
}

_START = chess.STARTING_FEN
_TOKEN_RE = re.compile(r"[a-z0-9']+")


def _fens_from_san_line(san_line: str, start_fen: str | None = None) -> list[str]:
    board = chess.Board(start_fen or _START)
    fens = [board.fen()]
    for tok in san_line.split():
        try:
            board.push_san(tok)
        except Exception:
            break
        fens.append(board.fen())
        if len(fens) >= 5:
            break
    return fens


def _norm_game_label(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"^model game:\s*", "", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def build_model_game_fen_index(
    passages: list[BookwalkPassage],
) -> dict[str, list[tuple[str, str]]]:
    """Map normalized game label → [(fen, san_line), ...]."""
    out: dict[str, list[tuple[str, str]]] = {}
    for p in passages:
        key = _norm_game_label(p.game_label)
        if not key:
            continue
        out.setdefault(key, []).append((p.fen, p.san_line or p.san))
    return out


def _lookup_model_fens(
    model_game: str,
    index: dict[str, list[tuple[str, str]]],
) -> tuple[list[str], list[str]] | None:
    needle = _norm_game_label(model_game)
    if not needle:
        return None
    # exact
    if needle in index:
        pairs = index[needle]
        return [pairs[0][0]], [pairs[0][1]]
    # fuzzy token overlap
    best = None
    best_score = 0
    ntoks = set(needle.split())
    for label, pairs in index.items():
        ltoks = set(label.split())
        score = len(ntoks & ltoks)
        if score >= 2 and score > best_score:
            best_score = score
            best = pairs
    if best:
        return [best[0][0]], [best[0][1]]
    return None


def seed_for_key(key_id: str) -> tuple[list[str], list[str]] | None:
    if key_id in KEY_SEED_FENS:
        fen, san = KEY_SEED_FENS[key_id]
        return [fen], [san]
    if key_id in OPENING_SAN_SEEDS:
        san = OPENING_SAN_SEEDS[key_id]
        fens = _fens_from_san_line(san)
        # Prefer a mid-line position over the start
        mid = fens[min(len(fens) - 1, 4)] if fens else _START
        return [mid], [san]
    return None


def type_fallback_seed(key_id: str) -> tuple[list[str], list[str]]:
    """Last-resort position so every GPT note has a board lock."""
    prefix = key_id.split(".", 1)[0]
    if prefix == "opening":
        fens = _fens_from_san_line("e4 e5 Nf3 Nc6 Bb5 a6")
        return [fens[min(4, len(fens) - 1)]], ["e4 e5 Nf3 Nc6 Bb5 a6"]
    if prefix == "endgame":
        fen, san = KEY_SEED_FENS["endgame.strategic.active_king"]
        return [fen], [san]
    if prefix == "structure":
        fen, san = KEY_SEED_FENS["structure.pawn_chain"]
        return [fen], [san]
    if prefix in {"attack", "motif"}:
        fen, san = KEY_SEED_FENS["attack.greek_gift"]
        return [fen], [san]
    if prefix == "imbalance":
        fen = "r1bq1rk1/pp2ppbp/2n2np1/3p4/3P4/2N2NP1/PP2PPBP/R1BQ1RK1 w - - 0 9"
        return [fen], ["Bg5 Ne4"]
    # methodology / piece / positional
    fen = "r2q1rk1/ppp2ppp/2n1bn2/3p4/3P4/2N1PN2/PP2BPPP/R1BQ1RK1 w - - 0 9"
    return [fen], ["Ne5 Bd6"]


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall((text or "").lower()) if len(t) >= 3}


def _pick_bookwalk_locks(
    note_text: str,
    bw: list[BookwalkPassage],
    *,
    limit: int = 3,
) -> tuple[list[str], list[str]]:
    """Pick FEN/SAN locks from bookwalk passages that best match note prose."""
    if not bw:
        return [], []
    ntoks = _tokens(note_text)
    scored: list[tuple[int, BookwalkPassage]] = []
    for p in bw:
        score = 0
        if ntoks:
            score = len(ntoks & _tokens(p.text))
        # Prefer curated + longer pedagogical sections
        if p.curated:
            score += 2
        score += min(3, len(p.text) // 120)
        scored.append((score, p))
    scored.sort(key=lambda row: (-row[0], 0 if row[1].curated else 1, -len(row[1].text)))
    # Always keep at least the top passage even if token overlap is 0.
    picks = [p for _, p in scored[:limit]]
    fens: list[str] = []
    sans: list[str] = []
    for p in picks:
        for fen in (p.fen, p.fen_after):
            if fen and fen not in fens:
                fens.append(fen)
        line = p.san_line or p.san
        if line and line not in sans:
            sans.append(line)
        if p.san and p.san not in sans:
            sans.append(p.san)
    return fens[:4], sans[:4]


def _is_seed_note(note: dict[str, Any]) -> bool:
    feats = list(note.get("features") or [])
    return "fen-seed" in feats or (
        "fen-enriched" in feats and not str(note.get("id") or "").startswith("bookwalk:")
    )


def enrich_gpt_notes_with_fens(
    notes: list[dict[str, Any]],
    *,
    key_id: str,
    bookwalk_for_key: list[BookwalkPassage] | None = None,
    model_game: str = "",
    model_index: dict[str, list[tuple[str, str]]] | None = None,
) -> list[dict[str, Any]]:
    """Ensure every non-bookwalk note has fens + sanLines.

    Prefer real bookwalk FENs over canonical seed positions. Seed FENs are
    tagged ``fen-seed`` so mobile can demote soft mismatches.
    """
    bw = bookwalk_for_key or []
    index = model_index or {}
    out: list[dict[str, Any]] = []
    for note in notes:
        nid = str(note.get("id") or "")
        if nid.startswith("bookwalk:"):
            out.append(note)
            continue

        feats = list(note.get("features") or [])
        has_fens = bool(note.get("fens"))
        seedish = _is_seed_note(note) or not has_fens

        fens: list[str] = []
        sans: list[str] = []
        seed_used = False
        from_bookwalk = False

        if bw and seedish:
            fens, sans = _pick_bookwalk_locks(str(note.get("text") or ""), bw)
            from_bookwalk = bool(fens)

        if not fens and model_game:
            hit = _lookup_model_fens(model_game, index)
            if hit:
                fens, sans = hit

        if not fens and has_fens and not seedish:
            # Keep existing high-quality locks (e.g. model-game attached).
            out.append(note)
            continue

        if not fens:
            seeded = seed_for_key(key_id)
            if seeded:
                fens, sans = seeded
                seed_used = True
        if not fens:
            fens, sans = type_fallback_seed(key_id)
            seed_used = True

        enriched = dict(note)
        enriched["fens"] = [f for f in fens if f][:4]
        enriched["sanLines"] = [s for s in sans if s][:4]
        feats = [f for f in feats if f not in {"fen-seed", "fen-enriched", "fen-bookwalk"}]
        feats.append("fen-enriched")
        if from_bookwalk:
            feats.append("fen-bookwalk")
        elif seed_used:
            feats.append("fen-seed")
        enriched["features"] = feats[:12]
        out.append(enriched)
    return out
