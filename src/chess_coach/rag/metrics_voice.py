"""
GPT pack voice → impersonal directive lists keyed to soft-key metric ids.

Soft-key id is the metric lookup key (structure.iqp, motif.sacrifice, …).
Prose is didactic directives only — fit the key + opening principles when opening.*.
No game stories, no metrics narrative hooks.

Mirrors mobile coach-call wiring (metricNoteKeys / BoardMetricSnap, cache ~v96):
soft keys are selected via softKeysForNoteRequest from structural kinds,
moment inputs, and engine-vs-played metric Δ — never free theme labels.
Hanging on snaps is material-value only (hanging_material_own /
hanging_material_opponent); never piece-count hanging_own / hanging_opp.
"""

from __future__ import annotations

import re

# mobile BoardMetricSnap fields (diffMetricSnaps / line compare horizon 8).
BOARD_METRIC_SNAP_FIELDS: tuple[str, ...] = (
    "material_balance",
    "mobility",
    "king_attackers_pct",
    "opp_king_attackers_pct",
    "space_advantage_pct",
    "hanging_material_own",
    "hanging_material_opponent",
    "open_file_utilization",
    "seventh_rank_infiltration",
    "queenside_advance",
    "queenside_advance_opponent",
    "kingside_advance",
    "kingside_advance_opponent",
    "center_advance",
    "center_advance_opponent",
    "bishop_diagonal_influence_light",
    "bishop_diagonal_influence_dark",
    "bishop_diagonal_influence_light_opponent",
    "bishop_diagonal_influence_dark_opponent",
    "bishop_openness_light",
    "bishop_openness_dark",
    "bishop_openness_light_opponent",
    "bishop_openness_dark_opponent",
    "castled_kingside",
    "castled_queenside",
    "castled_kingside_opponent",
    "castled_queenside_opponent",
    "opposite_side_castling",
    "closed_center",
    "blockade_square_control",
    "maroczy_bind",
    "carlsbad",
    "minority_attack",
    "caro_slav",
    "hedgehog",
    "scheveningen",
    "dragon_formation",
    "knight_vs_bishop",
    "good_vs_bad_bishop",
    "pawn_storm_tempo",
    "center_fluidity_index",
    "pawn_storm_tempo_delta",
    "king_center_file_exposure",
    "opp_king_in_centre",
    "opp_king_uncastled",
    "king_attack_ratio",
    "attack_setup",
    "opp_king_weaknesses",
    "second_weakness",
    "queen_centralization",
    "connected_rooks",
    "piece_liberation",
    "side_clamp",
    "key_square_control",
    "piece_support",
    "wp",
    "eval_cp",
)

# Mirrors mobile metricNoteKeys.METRIC_FIELD_TO_KEYS (phase prefixes stripped).
METRIC_FIELD_SOFT_KEYS: dict[str, list[str]] = {
    "pawn_break": ["positional.pawn_break", "structure.pawn_chain"],
    "pawn_breaks": ["positional.pawn_break", "structure.pawn_chain"],
    "defended_pawn": ["positional.prophylaxis", "methodology.prophylactic_thinking"],
    "defended_pawns": ["positional.prophylaxis", "methodology.prophylactic_thinking"],
    "unblocking_bishop_light": ["imbalance.bishop_pair", "positional.color_complexes"],
    "unblocking_bishop_dark": ["imbalance.bishop_pair", "positional.color_complexes"],
    "checks": ["motif.pin_and_skewer", "attack.initiative"],
    "blocking_checks": ["methodology.prophylactic_thinking", "motif.pin_and_skewer"],
    "king_attackers": ["attack.king_safety", "attack.initiative"],
    "king_attackers_score": ["attack.king_safety", "attack.initiative"],
    "king_attackers_pct": ["attack.king_safety"],
    "opp_king_attackers": ["attack.king_safety", "attack.initiative"],
    "opp_king_attackers_pct": ["attack.king_safety", "attack.initiative"],
    "opp_king_attackers_score": ["attack.king_safety", "attack.initiative"],
    "space_advantage_pct": ["imbalance.space", "positional.restriction"],
    "pawn_shield_pct": ["attack.king_safety"],
    "hanging_material_own": ["methodology.candidate_moves", "motif.trapped_piece"],
    "hanging_material_opponent": ["attack.initiative", "motif.trapped_piece"],
    "mobility": ["piece.centralization", "piece.coordination"],
    "material_balance": ["imbalance.material_asymmetry", "piece.simplification"],
    "seventh_rank_infiltration": ["piece.seventh_rank_invasion"],
    "open_file_utilization": ["piece.coordination", "imbalance.space"],
    "center_fluidity_index": ["positional.pawn_break", "imbalance.space"],
    "pawn_storm_tempo_delta": ["attack.opposite_side_castling", "attack.initiative"],
    "king_center_file_exposure": ["attack.king_safety", "positional.pawn_break"],
    "opp_king_in_centre": ["attack.king_safety", "attack.initiative"],
    "opp_king_uncastled": ["attack.king_safety", "attack.initiative"],
    "second_weakness": ["positional.two_weaknesses", "attack.initiative"],
    "connected_rooks": ["piece.coordination"],
    "piece_liberation": ["piece.coordination", "positional.restriction"],
    "queen_centralization": ["piece.centralization"],
    "piece_support": ["piece.coordination", "attack.initiative"],
    "queenside_advance": ["imbalance.space", "positional.pawn_break"],
    "queenside_advance_opponent": ["imbalance.space", "attack.initiative"],
    "kingside_advance": ["imbalance.space", "attack.initiative"],
    "kingside_advance_opponent": ["imbalance.space", "attack.initiative"],
    "center_advance": ["imbalance.space", "piece.centralization"],
    "center_advance_opponent": ["imbalance.space", "piece.centralization"],
    "bishop_diagonal_influence_light": [
        "positional.color_complexes",
        "imbalance.good_vs_bad_bishop",
    ],
    "bishop_diagonal_influence_dark": [
        "positional.color_complexes",
        "imbalance.good_vs_bad_bishop",
    ],
    "bishop_diagonal_influence_light_opponent": [
        "positional.color_complexes",
        "attack.initiative",
    ],
    "bishop_diagonal_influence_dark_opponent": [
        "positional.color_complexes",
        "attack.initiative",
    ],
    "bishop_openness_light": [
        "positional.color_complexes",
        "imbalance.bishop_pair",
    ],
    "bishop_openness_dark": [
        "positional.color_complexes",
        "imbalance.bishop_pair",
    ],
    "bishop_openness_light_opponent": [
        "positional.color_complexes",
        "imbalance.good_vs_bad_bishop",
    ],
    "bishop_openness_dark_opponent": [
        "positional.color_complexes",
        "imbalance.good_vs_bad_bishop",
    ],
    "castled_kingside": ["attack.king_safety", "attack.opposite_side_castling"],
    "castled_queenside": ["attack.king_safety", "attack.opposite_side_castling"],
    "castled_kingside_opponent": [
        "attack.king_safety",
        "attack.opposite_side_castling",
    ],
    "castled_queenside_opponent": [
        "attack.king_safety",
        "attack.opposite_side_castling",
    ],
    "opposite_side_castling": [
        "attack.opposite_side_castling",
        "attack.king_safety",
        "attack.initiative",
    ],
    "closed_center": [
        "structure.pawn_chain",
        "positional.pawn_break",
        "positional.outpost",
    ],
    "blockade_square_control": ["piece.blockade", "structure.iqp"],
    "maroczy_bind": [
        "structure.maroczy_bind",
        "imbalance.space",
        "positional.restriction",
    ],
    "carlsbad": [
        "structure.carlsbad",
        "imbalance.space",
        "positional.pawn_break",
    ],
    "minority_attack": [
        "structure.carlsbad",
        "imbalance.space",
        "positional.pawn_break",
    ],
    "caro_slav": [
        "structure.caro_slav",
        "structure.pawn_chain",
        "positional.pawn_break",
    ],
    "hedgehog": [
        "structure.hedgehog",
        "imbalance.space",
        "positional.pawn_break",
    ],
    "scheveningen": [
        "structure.scheveningen",
        "imbalance.space",
        "positional.pawn_break",
    ],
    "dragon_formation": [
        "structure.dragon_formation",
        "attack.initiative",
        "positional.color_complexes",
    ],
    "knight_vs_bishop": [
        "imbalance.knight_vs_bishop",
        "positional.outpost",
        "positional.color_complexes",
    ],
    "good_vs_bad_bishop": [
        "imbalance.good_vs_bad_bishop",
        "positional.color_complexes",
        "imbalance.bishop_pair",
    ],
    "pawn_storm_tempo": [
        "attack.opposite_side_castling",
        "attack.initiative",
        "imbalance.space",
    ],
    "opposition": [
        "endgame.strategic.active_king",
        "endgame.theoretical.triangulation",
    ],
    "minors_developed": ["piece.centralization", "methodology.candidate_moves"],
    "pawn_moves": ["positional.pawn_break", "structure.pawn_chain"],
    "castle_fullmove": ["attack.king_safety"],
    "uncastled": ["attack.king_safety", "attack.opposite_side_castling"],
    "opening_accuracy_pct": ["methodology.candidate_moves"],
    "center_control_pct": ["piece.centralization", "imbalance.space"],
    "blunders": ["methodology.candidate_moves", "methodology.visualization"],
    "mistakes": ["methodology.comparison_and_elimination"],
    "inaccuracies": ["methodology.candidate_moves"],
    "accuracy_pct": ["methodology.candidate_moves"],
    "brilliant_moves": ["motif.sacrifice"],
    "important_moves": ["methodology.comparison_and_elimination"],
    "excellent_moves": ["methodology.candidate_moves"],
    "eco": [],
    "opening": [],
    "opening_name": [],
    "opp_wp_gift": ["methodology.candidate_moves", "attack.initiative"],
    "engine_line": ["methodology.visualization", "methodology.candidate_moves"],
    "best_line_wp": ["endgame.strategic.active_king", "piece.simplification"],
    "best_line_eval_cp": ["endgame.strategic.active_king"],
    "had_endgame_advantage": [
        "endgame.strategic.active_king",
        "piece.simplification",
    ],
    "converted_endgame": ["endgame.strategic.active_king"],
    "endgame_advantage_start_ply": ["endgame.strategic.active_king"],
}

# Mirrors mobile metricNoteKeys.STRUCTURAL_KIND_KEYS.
STRUCTURAL_KIND_SOFT_KEYS: dict[str, list[str]] = {
    "opening_name": [
        "opening.caro_kann",
        "opening.english",
        "opening.french",
        "opening.italian",
        "opening.kings_indian",
        "opening.london_system",
        "opening.petroff",
        "opening.queens_gambit",
        "opening.ruy_lopez",
        "opening.scandinavian",
        "opening.sicilian",
        "methodology.candidate_moves",
    ],
    "opening_aggregate": [
        "piece.centralization",
        "attack.king_safety",
        "methodology.candidate_moves",
        "imbalance.space",
    ],
    "middlegame_aggregate": [
        "imbalance.space",
        "attack.king_safety",
        "positional.pawn_break",
        "methodology.candidate_moves",
    ],
    "endgame_advantage": [
        "endgame.strategic.active_king",
        "piece.simplification",
        "piece.seventh_rank_invasion",
    ],
    "decisive_pawn_break": ["positional.pawn_break", "imbalance.space"],
    "opponent_mistake": [
        "methodology.candidate_moves",
        "methodology.visualization",
        "attack.initiative",
    ],
}

_GAME_NOISE = re.compile(
    r"\b("
    r"Kasparov|Fischer|Karpov|Capablanca|Morphy|Botvinnik|Petrosian|Spassky|"
    r"Alekhine|Tal|Anand|Carlsen|Lasker|Euwe|Smyslov|Korchnoi|Topalov|"
    r"White|Black"
    r")\b[^.?!]*[.?!]?",
    re.I,
)
_POSITIONAL_STORY = re.compile(
    r"\b("
    r"in this position|in the diagram|in the game|after [NBRQK]?[a-h]?[1-8]?x?[a-h][1-8]|"
    r"model game|famous game|vs\.?"
    r")\b[^.?!]*[.?!]?",
    re.I,
)
_HOOK_LEAD = re.compile(
    r"^(when game metrics|metrics (flagged|flag|show|surface|lock|marked|locked)|"
    r"while opening metrics|when the (scan|evaluation|game)|"
    r"when a (sharp|brilliant|mistake|sacrifice|decisive)|"
    r"when (defending|style|king-safety|endgame|attacking|tactical|positional|"
    r"imbalance|piece-activity|prophylactic|outpost|carlsbad|hanging|"
    r"doubled|passed-pawn|maroczy|scheveningen|dragon|hedgehog|caro|"
    r"opposite-bishop|rook-ending|zugzwang|material) )\b.*?(?:,|:)\s*",
    re.I,
)
_SAN_RUN = re.compile(
    r"\b(?:\d+\.+)?(?:[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?|O-O-O|O-O)"
    r"(?:\s+(?:[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?|O-O-O|O-O)){1,6}\b"
)
_MULTI_SPACE = re.compile(r"\s+")

_IMPERATIVE_START = re.compile(
    r"^(Use|Keep|Build|Create|Judge|Test|Stretch|Recognize|Activate|Convert|"
    r"Attack|Restrict|Develop|Castle|Calculate|Prefer|Avoid|Compare|Preserve|"
    r"Centralize|Blockade|Exchange|Push|Open|Remove|Count|Favor|Do|List|Track|"
    r"Identify|Secure|Place|Move|Force|Verify|Before|Treat|Play|Choose|Seek|"
    r"Hold|Trade|Advance|Defend|Improve|Simplify|Reroute|Occupy|Support|"
    r"Include|Evaluate|Maintain|Refuse|Delay|Time|Apply)\b",
    re.I,
)

# Soft-key → fallback directives when GPT prose is empty/noisy.
_KEY_DIRECTIVES: dict[str, list[str]] = {
    "positional.pawn_break": [
        "Prepare the liberating pawn break only after pieces support the resulting open lines.",
        "Time the break so it gains space or activity, not just creates a hole.",
    ],
    "piece.centralization": [
        "Develop minor pieces toward the center before launching wing attacks.",
        "Do not move the same piece twice in the opening unless forced.",
    ],
    "piece.coordination": [
        "Improve the worst-placed piece before inventing a new attack.",
        "Connect rooks and keep pieces defending each other.",
        "Put a rook or queen on an open or semi-open file before inventing a new plan.",
    ],
    "attack.initiative": [
        "Use the move to create a concrete threat the opponent must answer.",
        "Do not release the tension until the threat sequence is calculated.",
    ],
    "methodology.candidate_moves": [
        "List checks, captures, and threats before choosing a quiet move.",
        "Compare two candidate lines and eliminate the one that fails a tactic.",
    ],
    "positional.prophylaxis": [
        "Ask what the opponent wants and stop it before continuing your plan.",
        "Fix hanging pieces and soft squares before expanding.",
    ],
    "attack.king_safety": [
        "Castle before opening the center when the king is still exposed.",
        "Do not chase material if it leaves the king without a shield.",
    ],
    "piece.simplification": [
        "Exchange when ahead in material or when the trade kills counterplay.",
        "Refuse trades that activate the opponent's remaining pieces.",
    ],
    "piece.seventh_rank_invasion": [
        "Seize open files and invade the seventh when the enemy king is cut off.",
        "Double heavy pieces before entering the seventh rank.",
        "Place a rook or queen on an open or semi-open file, then look for the seventh.",
    ],
    "motif.trapped_piece": [
        "Count every safe escape square before leaving a piece short of flight squares.",
        "Calculate the trapping net before the capture appears on the board.",
        "Do not push your own piece into a pocket with zero safe replies.",
    ],
    "positional.two_weaknesses": [
        "Fix one weakness, then create a second so the defender cannot hold both.",
        "Switch wings once the first target is securely restrained.",
    ],
    "positional.outpost": [
        "Occupy a protected outpost and keep it supplied by pawns.",
        "Challenge enemy outposts before they become permanent.",
    ],
    "imbalance.space": [
        "Use space to restrict the opponent; only break when pieces are ready.",
        "Do not overextend pawns that leave backward weaknesses.",
    ],
    "endgame.strategic.active_king": [
        "Activate the king toward the center once queens are off.",
        "Use opposition and zugzwang ideas before pushing passed pawns blindly.",
    ],
    "structure.passed_pawn": [
        "Advance the passed pawn when pieces can escort it.",
        "Blockade enemy passers before creating your own.",
    ],
}

_OPENING_DIRECTIVES: dict[str, list[str]] = {
    "opening.sicilian": [
        "Contest the center with timely ...c5 ideas and complete development first.",
        "Prepare queenside pressure before premature wing pawn storms.",
    ],
    "opening.french": [
        "Challenge the center with ...c5 or ...f6 once development is ready.",
        "Solve the light-squared bishop before locking the structure forever.",
    ],
    "opening.caro_kann": [
        "Keep the solid pawn chain and time the liberating break.",
        "Develop minors to active squares before chasing material.",
    ],
    "opening.italian": [
        "Develop minors, castle, then choose between quiet build-up and a central break.",
        "Fight for d4/d5 tension without leaving the king exposed.",
    ],
    "opening.ruy_lopez": [
        "Pressure the pinned knight and prepare c3–d4 after castling.",
        "Castle early; only then expand on the queenside or center.",
    ],
    "opening.queens_gambit": [
        "Contest d5 with sound development; do not grab c4 if it costs tempi.",
        "Develop the queenside bishop before minority-attack plans.",
    ],
    "opening.london_system": [
        "Keep the London triangle solid and castle before pawn storms.",
        "Use e5/c5 breaks only after pieces cover the holes.",
    ],
    "opening.kings_indian": [
        "Prepare the thematic pawn break after kingside development.",
        "Do not open the center while the king is uncastled.",
    ],
    "opening.english": [
        "Control d5/c4 complexes with pieces before pawn grabs.",
        "Develop toward the queenside space edge, then break.",
    ],
    "opening.petroff": [
        "Neutralize early pressure with clean development and timely exchanges.",
        "Castle and only then look for central counterplay.",
    ],
    "opening.scandinavian": [
        "Recycle the queen without losing tempi, then finish development.",
        "Castle before chasing further material in the open center.",
    ],
}


def metric_lookup_key(key_id: str) -> str:
    return (key_id or "").strip()


def _clean_sentence(text: str) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    s = _HOOK_LEAD.sub("", s)
    s = _GAME_NOISE.sub(" ", s)
    s = _POSITIONAL_STORY.sub(" ", s)
    s = _SAN_RUN.sub(" ", s)
    s = _MULTI_SPACE.sub(" ", s).strip(" .,;:-")
    if not s:
        return ""
    if not s.endswith("."):
        s += "."
    return s[0].upper() + s[1:]


def _as_directive(text: str) -> str:
    s = _clean_sentence(text)
    if not s:
        return ""
    if len(s) > 220:
        s = s[:217].rsplit(" ", 1)[0].rstrip(".,;:") + "."
    if _IMPERATIVE_START.match(s):
        return s
    core = s.rstrip(".")
    if len(core.split()) <= 8:
        return f"Apply the lesson: {core[0].lower() + core[1:]}."
    return s


def key_fallback_directives(key_id: str) -> list[str]:
    kid = metric_lookup_key(key_id)
    if kid in _OPENING_DIRECTIVES:
        return list(_OPENING_DIRECTIVES[kid])
    if kid in _KEY_DIRECTIVES:
        return list(_KEY_DIRECTIVES[kid])
    family = kid.split(".", 1)[0] if "." in kid else ""
    for k, dirs in _KEY_DIRECTIVES.items():
        if k.startswith(family + ".") and dirs:
            return list(dirs)
    return [
        "Name the concrete threat before moving.",
        "Improve the worst piece or stop the opponent's idea first.",
    ]


def directives_from_parts(
    key_id: str,
    *,
    principle: str = "",
    summary: str = "",
    compact: str = "",
    max_items: int = 3,
) -> list[str]:
    """Build impersonal directive list for one soft key / metric lookup."""
    out: list[str] = []
    seen: set[str] = set()

    def add(raw: str) -> None:
        d = _as_directive(raw)
        if not d or len(d) < 16:
            return
        key = d.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(d)

    add(principle)
    if summary:
        parts = re.split(r"(?<=[.!?])\s+", summary.strip())
        for part in parts[:2]:
            add(part)
            if len(out) >= max_items:
                break
    if len(out) < 2 and compact:
        add(compact)
    if len(out) < 2:
        for d in key_fallback_directives(key_id):
            add(d)
            if len(out) >= max_items:
                break
    return out[:max_items]


def format_directive_list(directives: list[str]) -> str:
    lines = [f"- {d}" for d in directives if d]
    return "\n".join(lines)


def adapt_summary(key_id: str, summary: str, *, principle: str = "") -> str:
    """Export note body: bullet directives only (metric id is soft-key lookup)."""
    body = (summary or "").strip()
    if body.startswith("- "):
        return body
    dirs = directives_from_parts(
        key_id, principle=principle, summary=body, max_items=2
    )
    if not dirs:
        d = _as_directive(body) if body else ""
        dirs = [d] if d else key_fallback_directives(key_id)[:2]
    return format_directive_list([d for d in dirs if d])


def adapt_compact(key_id: str, compact: str) -> str:
    """Card glossary: one or two directives, no metrics narrative."""
    body = (compact or "").strip()
    if body.startswith("- "):
        return body
    dirs = directives_from_parts(key_id, compact=body, summary=body, max_items=2)
    if not dirs:
        d = _as_directive(body) if body else ""
        dirs = [d] if d else key_fallback_directives(key_id)[:2]
    return format_directive_list(dirs)


def adapt_note_fields(
    key_id: str,
    *,
    summary: str,
    compact: str = "",
    principle: str = "",
) -> tuple[str, str]:
    return (
        adapt_summary(key_id, summary, principle=principle),
        adapt_compact(key_id, compact) if compact else "",
    )
