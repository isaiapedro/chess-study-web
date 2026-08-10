from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import chess
import httpx

from chess_coach.analyze import CriticalMoment
from chess_coach.logutil import log
from chess_coach.ontology.cards import format_exemplars, format_pattern_cards
from chess_coach.rag.quality import filter_passages
from chess_coach.rag.retrieve import Passage
from chess_coach.validate import validate_commentary

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.I)
_THINK_TRAIL_RE = re.compile(r"(?i)\s*/\s*think\s*$")


@dataclass
class Commentary:
    text: str
    citations: list[str]
    engine_only: bool
    warnings: list[str]


SYSTEM_PROMPT = """You are a local chess coach. Stockfish numbers are ground truth.
Rules:
1. Never invent evaluations that contradict the provided engine data.
2. Only mention moves that appear in the played move, best move, or PV list — or clearly label speculative plans without concrete illegal SANs.
3. Use book passages ONLY when they clearly discuss this structure/move; never paste generic opening introductions.
4. Pattern ontology cards are trusted rule-of-thumb context for THIS structure — use them when relevant.
5. Exemplar games are real archive references — you may say "cf. X vs Y, year" only from that list; never invent games.
6. Cite book titles when you borrow phrasing or plans.
7. Keep the note short and specific to THIS ply: what the move does, what White/Black wants next, engine alternative if relevant.
"""


def _format_eval(cp: int | None, mate: int | None) -> str:
    if mate is not None:
        return f"mate {mate:+d}"
    if cp is None:
        return "n/a"
    return f"{cp / 100:+.2f}"


def _clip_passage(text: str, limit: int = 220) -> str:
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return (cut or text[: limit - 1]) + "…"


def build_prompt(moment: CriticalMoment, passages: list[Passage]) -> str:
    passage_block = "No matching book passages (engine-only mode)."
    if passages:
        parts = []
        for idx, passage in enumerate(passages, start=1):
            parts.append(
                f"[{idx}] {passage.book} ({passage.chapter}) score={passage.score:.2f}\n{passage.text}"
            )
        passage_block = "\n\n".join(parts)

    cards = format_pattern_cards(moment.features.patterns) or "(none detected)"
    exemplars = format_exemplars(moment.features.patterns) or "(none)"
    return f"""Position FEN: {moment.fen_before}
Side to move: {moment.side}
Move number: {moment.fullmove}
Played: {moment.played_san}
Engine best: {moment.best_san or "n/a"}
Eval before (White POV): {_format_eval(moment.eval_before_cp, moment.mate_before)}
Eval after (White POV): {_format_eval(moment.eval_after_cp, moment.mate_after)}
Loss for side to move: {moment.delta_cp} cp
PV: {' '.join(moment.pv_san) if moment.pv_san else 'n/a'}
Depth: {moment.depth}
Themes: {', '.join(moment.features.themes) or 'none'}
Patterns: {', '.join(moment.features.patterns) or 'none'}
Opening/ECO: {moment.features.opening or 'n/a'} / {moment.features.eco or 'n/a'}

Ontology pattern cards (structure rules of thumb):
{cards}

Archive exemplar games (cite only from this list if useful):
{exemplars}

Book passages (only use if clearly about this position/plan):
{passage_block}

Write 1-3 sentences about THIS move in THIS game. Tie plans to the pattern cards when they fit. No generic opening history.
"""


def _move_facts(moment: CriticalMoment) -> list[str]:
    """Concrete board facts from the played move (no book text)."""
    facts: list[str] = []
    try:
        board = chess.Board(moment.fen_before)
        move = board.parse_san(moment.played_san)
    except ValueError:
        return facts
    piece = board.piece_at(move.from_square)
    pname = piece.symbol().upper() if piece else "?"
    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        if move.drop is None and chess.BB_SQUARES[move.to_square] & board.occupied == 0 and board.is_en_passant(move):
            facts.append(f"{pname} takes en passant on {chess.square_name(move.to_square)}")
        elif victim:
            facts.append(f"{pname}x{victim.symbol().upper()} on {chess.square_name(move.to_square)}")
        else:
            facts.append(f"captures on {chess.square_name(move.to_square)}")
    elif piece and piece.piece_type == chess.PAWN and abs(chess.square_file(move.from_square) - chess.square_file(move.to_square)) == 0:
        advance = abs(chess.square_rank(move.to_square) - chess.square_rank(move.from_square))
        if advance == 2:
            facts.append(f"pawn leaps to {chess.square_name(move.to_square)}")
        else:
            facts.append(f"pawn to {chess.square_name(move.to_square)}")
    elif board.is_castling(move):
        facts.append("short castle" if chess.square_file(move.to_square) == 6 else "long castle")
    elif piece:
        facts.append(f"{pname}→{chess.square_name(move.to_square)}")

    board.push(move)
    if board.is_checkmate():
        facts.append("checkmate")
    elif board.is_check():
        facts.append("check")
    return facts


def engine_grounded_note(moment: CriticalMoment) -> str:
    """Concrete note from engine + board features — never a book dump."""
    move = f"{moment.fullmove}{'.' if moment.side == 'white' else '...'} {moment.played_san}"
    side = "White" if moment.side == "white" else "Black"
    bits: list[str] = [move]

    facts = _move_facts(moment)
    if facts:
        bits.append("(" + "; ".join(facts) + ")")

    themes = [t for t in moment.features.themes if t not in {"opening"}]
    if themes:
        bits.append("Theme: " + ", ".join(themes[:3]) + ".")
    elif moment.features.phase == "opening" and (moment.features.eco or moment.features.opening):
        label = moment.features.opening or moment.features.eco
        bits.append(f"Developing in {label}.")
    else:
        bits.append(f"{moment.features.phase.capitalize()} phase.")

    imb = moment.features.material_imbalance
    if abs(imb) >= 2:
        leader = "White" if imb > 0 else "Black"
        bits.append(f"Material tip {leader} (~{abs(imb)}).")

    best = moment.best_san or ""
    played = moment.played_san or ""
    if best and best == played:
        if moment.delta_cp >= 80:
            bits.append(
                f"Top engine move, but eval still swings {moment.delta_cp}cp after it (tactical).")
        else:
            bits.append(f"Matches Stockfish's top choice for {side}.")
    elif moment.delta_cp >= 300:
        bits.append(
            f"{side} blunders ({moment.delta_cp}cp); better was {best or 'the engine move'}."
        )
    elif moment.delta_cp >= 150:
        bits.append(
            f"{side} errs ({moment.delta_cp}cp); {best or 'engine move'} was safer."
        )
    elif moment.delta_cp >= 80:
        bits.append(
            f"Inaccuracy ({moment.delta_cp}cp); engine likes {best or 'another move'}."
        )
    elif best and best != played and moment.delta_cp >= 40:
        bits.append(f"Playable; engine slight preference {best} ({moment.delta_cp}cp).")
    else:
        bits.append(f"Solid for {side} at this depth.")

    if moment.pv_san and (moment.delta_cp >= 40 or (best and best != played)):
        cont = [s for s in moment.pv_san[:5] if s != played]
        if cont:
            bits.append("Main line " + " ".join(cont) + ".")
    if moment.eval_after_cp is not None or moment.mate_after is not None:
        bits.append(f"Eval now {_format_eval(moment.eval_after_cp, moment.mate_after)}.")
    return " ".join(bits)


def pedagogical_fallback(
    moment: CriticalMoment,
    passages: list[Passage],
    *,
    used_fingerprints: set[str] | None = None,
    allow_book_quote: bool = False,
) -> Commentary:
    """Engine-first note + short ontology rule; optional filtered book quote."""
    lines = [engine_grounded_note(moment)]
    citations: list[str] = []
    cards = format_pattern_cards(moment.features.patterns, hops=0, limit=2)
    if cards:
        first = cards.splitlines()[0].lstrip("- ").strip()
        if first:
            lines.append(f"Pattern: {first}")
    exemplars = format_exemplars(moment.features.patterns, limit=1)
    if exemplars:
        lines.append("cf. " + exemplars.lstrip("- ").strip())
    if allow_book_quote:
        good = filter_passages(passages, moment, used_fingerprints=used_fingerprints, limit=1)
        if good:
            citations = [good[0].book]
            lines.append(f"[{good[0].book}] {_clip_passage(good[0].text)}")
    text = " ".join(lines)
    text, warnings = validate_commentary(moment, text, attach_notes=False)
    return Commentary(text=text, citations=citations, engine_only=True, warnings=warnings)


def engine_only_fallback(
    moment: CriticalMoment,
    passages: list[Passage],
    *,
    used_fingerprints: set[str] | None = None,
) -> Commentary:
    return pedagogical_fallback(
        moment, passages, used_fingerprints=used_fingerprints, allow_book_quote=False
    )


def explain(
    moment: CriticalMoment,
    passages: list[Passage],
    config: dict[str, Any],
    *,
    allow_fallback: bool = True,
    used_fingerprints: set[str] | None = None,
) -> Commentary:
    good = filter_passages(passages, moment, used_fingerprints=used_fingerprints, limit=2)
    prompt = build_prompt(moment, good)
    citations = [p.book for p in good]
    model = config["chat_model"]
    log("Ollama chat: model=%s (timeout 180s)...", model)
    try:
        with httpx.Client(timeout=180.0) as client:
            response = client.post(
                f"{config['ollama_host'].rstrip('/')}/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            response.raise_for_status()
            message = response.json().get("message") or {}
            content = str(message.get("content") or "").strip()
            content = _THINK_RE.sub("", content).strip()
            content = _THINK_TRAIL_RE.sub("", content).strip()
            # Drop leaked chain-of-thought if model stuffed it into content
            if "\n" in content and content.lower().startswith(("okay,", "ok,", "the user")):
                paras = [p.strip() for p in content.split("\n\n") if p.strip()]
                content = paras[-1] if paras else content
        text, warnings = validate_commentary(moment, content)
        return Commentary(
            text=text,
            citations=citations,
            engine_only=not bool(good),
            warnings=warnings,
        )
    except Exception as exc:
        log("Ollama chat failed: %s", exc)
        if not allow_fallback:
            raise
        return pedagogical_fallback(
            moment,
            passages,
            used_fingerprints=used_fingerprints,
            allow_book_quote=False,
        )
