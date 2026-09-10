from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import chess
import httpx

from chess_coach.analyze import CriticalMoment
from chess_coach.eco_names import format_eco_phrase, normalize_eco
from chess_coach.logutil import log
from chess_coach.ontology.cards import format_exemplars, format_pattern_cards
from chess_coach.ontology.load import load_ontology
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


SYSTEM_PROMPT = """You are a local chess coach writing short educational notes for a student.
Stockfish numbers are ground truth.

Rules:
1. Never invent evaluations that contradict the provided engine data.
2. Do NOT open by repeating the move number and SAN (the board already shows it).
3. If an ECO code appears, always expand it once in plain language
   (e.g. "Catalan Opening (ECO E01)" — never leave bare "E01").
4. Teach one concrete idea for THIS position: a structure theme, plan, or
   fundamental rule (open files, space, bad bishop, pawn breaks, etc.).
5. Only mention moves from the played move, best move, or PV — or label plans
   as ideas without illegal SANs.
6. Use book passages ONLY when they clearly discuss this structure/move.
7. Pattern ontology cards are trusted structure rules — use at most one fresh
   idea; do not paste the same card text every ply.
8. Keep 2–4 short sentences. Educational, not a move dump.
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


def _side_word(moment: CriticalMoment) -> str:
    return "White" if moment.side == "white" else "Black"


def _opening_concept(moment: CriticalMoment) -> str:
    return format_eco_phrase(moment.features.eco, moment.features.opening)


def _move_idea(moment: CriticalMoment) -> str:
    """Plain-language description of what the move does — no SAN echo."""
    side = _side_word(moment)
    try:
        board = chess.Board(moment.fen_before)
        move = board.parse_san(moment.played_san)
    except ValueError:
        return f"{side} continues development."
    piece = board.piece_at(move.from_square)
    to_name = chess.square_name(move.to_square)
    from_name = chess.square_name(move.from_square)

    if board.is_castling(move):
        wing = "kingside" if chess.square_file(move.to_square) == 6 else "queenside"
        return f"{side} castles {wing}, connecting the rooks and tucking the king away."

    if board.is_en_passant(move):
        return f"{side} takes en passant on {to_name}, clearing a central foothold."

    if board.is_capture(move):
        victim = board.piece_at(move.to_square)
        vname = {
            chess.PAWN: "pawn",
            chess.KNIGHT: "knight",
            chess.BISHOP: "bishop",
            chess.ROOK: "rook",
            chess.QUEEN: "queen",
        }.get(victim.piece_type, "piece") if victim else "piece"
        pname = {
            chess.PAWN: "pawn",
            chess.KNIGHT: "knight",
            chess.BISHOP: "bishop",
            chess.ROOK: "rook",
            chess.QUEEN: "queen",
            chess.KING: "king",
        }.get(piece.piece_type, "piece") if piece else "piece"
        return f"{side}'s {pname} captures the {vname} on {to_name}."

    if piece and piece.piece_type == chess.PAWN:
        advance = abs(chess.square_rank(move.to_square) - chess.square_rank(move.from_square))
        if advance == 2:
            return f"{side} leaps the pawn to {to_name}, grabbing space and opening lines."
        return f"{side} nudges the pawn to {to_name}, shaping the pawn structure."

    if piece:
        pname = {
            chess.KNIGHT: "knight",
            chess.BISHOP: "bishop",
            chess.ROOK: "rook",
            chess.QUEEN: "queen",
            chess.KING: "king",
        }.get(piece.piece_type, "piece")
        return f"{side} reroutes the {pname} from {from_name} to {to_name}."
    return f"{side} improves the position."


def _quality_clause(moment: CriticalMoment) -> str:
    side = _side_word(moment)
    best = (moment.best_san or "").strip()
    played = (moment.played_san or "").strip()
    if best and best == played:
        if moment.delta_cp >= 80:
            return (
                f"It is Stockfish's top choice here, yet the eval still swings "
                f"{moment.delta_cp}cp — tactics are sharp."
            )
        return "Engine agrees this is one of the strongest replies."
    if moment.delta_cp >= 300:
        return f"A serious mistake ({moment.delta_cp}cp); safer was {best or 'the engine move'}."
    if moment.delta_cp >= 150:
        return f"An error ({moment.delta_cp}cp); {best or 'the engine move'} was more reliable."
    if moment.delta_cp >= 80:
        return f"Slightly inaccurate ({moment.delta_cp}cp); engine prefers {best or 'another idea'}."
    if best and best != played and moment.delta_cp >= 40:
        return f"Playable, though the engine leans toward {best} ({moment.delta_cp}cp)."
    return f"A solid continuation for {side} at this depth."


def _knowledge_nugget(
    moment: CriticalMoment,
    used_fingerprints: set[str] | None,
) -> str:
    """One fresh fundamental idea for this structure — never the same text twice."""
    used = used_fingerprints if used_fingerprints is not None else set()
    catalog = load_ontology()
    for pid in moment.features.patterns:
        pattern = catalog.get(pid)
        if not pattern:
            continue
        bits: list[str] = []
        bits.extend(pattern.rules_of_thumb)
        bits.extend(pattern.plans)
        for bit in bits:
            text = (bit or "").strip()
            if len(text) < 20:
                continue
            fp = f"nugget:{(pid + ':' + text[:100]).lower()}"
            if fp in used:
                continue
            used.add(fp)
            label = pattern.label.strip()
            return f"Key idea ({label}): {text}"
    # Theme-only fallback when ontology silent
    themes = [t for t in moment.features.themes if t not in {"opening", "endgame"}]
    for theme in themes:
        fp = f"theme:{theme}"
        if fp in used:
            continue
        used.add(fp)
        tips = {
            "open file": "Controlling an open file only pays off if you can invade on the 7th/2nd rank or create a concrete target.",
            "bishop pair": "The two bishops shine in open centres — look to open lines before the opponent can trade one off.",
            "space": "With a space advantage, improve slowly and deny counterplay; avoid random piece trades that free the cramped side.",
            "passed pawn": "A passed pawn is a long-term asset — escort it, or force the opponent's pieces into passive blockade.",
            "king safety": "When kings are exposed, tempo and open lines matter more than quiet positional gains.",
            "piece activity": "Active pieces compensate for structure flaws — ask which piece has no useful job yet.",
            "isolated queen pawn": "IQP play: use open files and piece activity before the endgame, where the isolani can become a weakness.",
            "hanging pawns": "Hanging pawns want mobility (advance or pressure); if frozen, they become fixed targets.",
            "minority attack": "A minority attack (...b5–b4 or b4–b5) aims to create a weak pawn on the queenside majority.",
            "pawn chain": "Attack a pawn chain at its base; the tip advances, the base is the structural hinge.",
        }
        tip = tips.get(theme)
        if tip:
            return tip
    return ""


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
    opening = _opening_concept(moment) or "n/a"
    return f"""Position FEN: {moment.fen_before}
Side to move: {moment.side}
Move number: {moment.fullmove}
Played (do not echo as the first words): {moment.played_san}
Engine best: {moment.best_san or "n/a"}
Eval before (White POV): {_format_eval(moment.eval_before_cp, moment.mate_before)}
Eval after (White POV): {_format_eval(moment.eval_after_cp, moment.mate_after)}
Loss for side to move: {moment.delta_cp} cp
PV: {' '.join(moment.pv_san) if moment.pv_san else 'n/a'}
Depth: {moment.depth}
Themes: {', '.join(moment.features.themes) or 'none'}
Patterns: {', '.join(moment.features.patterns) or 'none'}
Opening label (already expanded — use this wording, not bare ECO codes): {opening}

Ontology pattern cards (pick ONE fresh idea max):
{cards}

Archive exemplar games (cite only from this list if useful):
{exemplars}

Book passages (only use if clearly about this position/plan):
{passage_block}

Write 2–4 educational sentences about THIS position after the move.
Start with a concept or plan, not "{moment.fullmove}. {moment.played_san}".
Expand any ECO jargon. Teach one fundamental for this structure.
"""


def engine_grounded_note(
    moment: CriticalMoment,
    *,
    used_fingerprints: set[str] | None = None,
) -> str:
    """Didactic engine note — no move-number spam, ECO explained, one concept."""
    sentences: list[str] = []
    opening = _opening_concept(moment)
    eco = normalize_eco(moment.features.eco)
    used = used_fingerprints if used_fingerprints is not None else set()

    if opening:
        fp = f"opening:{eco or opening[:40].lower()}"
        if fp not in used:
            used.add(fp)
            if moment.features.phase == "opening":
                sentences.append(f"We are in the {opening}.")
            else:
                sentences.append(f"The pawn structure still reflects the {opening}.")

    sentences.append(_move_idea(moment))

    nugget = _knowledge_nugget(moment, used)
    if nugget:
        sentences.append(nugget)

    sentences.append(_quality_clause(moment))

    if moment.pv_san and (
        moment.delta_cp >= 40 or (moment.best_san and moment.best_san != moment.played_san)
    ):
        cont = [s for s in moment.pv_san[:4] if s != moment.played_san]
        if cont:
            sentences.append("Typical engine continuation: " + " ".join(cont) + ".")

    if moment.eval_after_cp is not None or moment.mate_after is not None:
        sentences.append(f"Eval now {_format_eval(moment.eval_after_cp, moment.mate_after)}.")

    text = " ".join(s.strip() for s in sentences if s and s.strip())
    text = re.sub(
        rf"^\s*{moment.fullmove}\s*\.\.?\.?\s*{re.escape(moment.played_san or '')}\s*",
        "",
        text,
    ).strip()
    return text


def pedagogical_fallback(
    moment: CriticalMoment,
    passages: list[Passage],
    *,
    used_fingerprints: set[str] | None = None,
    allow_book_quote: bool = False,
) -> Commentary:
    """Engine-first didactic note + optional filtered book quote."""
    used = used_fingerprints if used_fingerprints is not None else set()
    lines = [engine_grounded_note(moment, used_fingerprints=used)]
    citations: list[str] = []
    exemplars = format_exemplars(moment.features.patterns, limit=1)
    if exemplars:
        line = "cf. " + exemplars.lstrip("- ").strip()
        fp = f"ex:{line[:80].lower()}"
        if fp not in used:
            used.add(fp)
            lines.append(line)
    if allow_book_quote:
        good = filter_passages(passages, moment, used_fingerprints=used, limit=1)
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
            if "\n" in content and content.lower().startswith(("okay,", "ok,", "the user")):
                paras = [p.strip() for p in content.split("\n\n") if p.strip()]
                content = paras[-1] if paras else content
        # Expand bare ECO leftovers the model might still emit
        eco = normalize_eco(moment.features.eco)
        if eco and re.search(rf"\b{eco}\b", content) and "ECO" not in content:
            phrase = format_eco_phrase(eco, moment.features.opening)
            if phrase:
                content = re.sub(rf"\b{eco}\b", phrase, content, count=1)
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
