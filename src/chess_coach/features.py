from __future__ import annotations

from dataclasses import dataclass, field

import chess

from chess_coach.ontology.detect import detect_pattern_ids
from chess_coach.ontology.load import expand_related


THEME_KEYWORDS = {
    "isolated queen pawn": ["isolated queen pawn", "iqp", "isolani"],
    "hanging pawns": ["hanging pawns"],
    "carlsbad": ["carlsbad", "minority attack"],
    "maroczy": ["maroczy", "maróczy"],
    "hedgehog": ["hedgehog"],
    "pawn chain": ["pawn chain", "locked centre", "locked center"],
    "scheveningen": ["scheveningen", "small centre", "small center"],
    "dragon formation": ["dragon formation", "dragon structure"],
    "caro slav": ["caro-slav", "caro slav", "slav structure"],
    "doubled pawns": ["doubled pawns"],
    "passed pawn": ["passed pawn", "passer"],
    "symmetrical center": ["symmetrical center", "symmetrical centre"],
    "bishop pair": ["bishop pair", "two bishops"],
    "good vs bad bishop": ["good bishop", "bad bishop"],
    "knight vs bishop": ["knight vs bishop", "bishop vs knight"],
    "space": ["space advantage", "cramped"],
    "material asymmetry": ["exchange sacrifice", "material imbalance", "piece for pawns"],
    "outpost": ["outpost", "strong square"],
    "prophylaxis": ["prophylaxis", "prophylactic"],
    "color complexes": ["dark-square", "light-square", "color complex"],
    "restriction": ["restriction", "domination"],
    "two weaknesses": ["two weaknesses", "second weakness"],
    "pawn break": ["pawn break", "pawn lever", "undermining"],
    "king safety": ["king safety", "attack on the king", "kingside attack"],
    "piece activity": ["piece activity", "centralization"],
    "endgame": ["endgame", "opposition", "zugzwang"],
    "opening": ["opening", "development", "theory", "tabiya"],
    "sicilian": ["sicilian", "dragon", "najdorf", "scheveningen", "sveshnikov", "rossolimo", "alapin"],
    "french": ["french defence", "french defense"],
    "caro-kann": ["caro-kann", "caro kann"],
    "king's indian": ["king's indian", "kings indian", "kíd"],
    "queen's gambit": ["queen's gambit", "queens gambit", "qgd", "qga", "slav", "catalan"],
    "english": ["english opening"],
    "london": ["london system", "london"],
    "petroff": ["petroff", "russian defence", "russian defense"],
    "scandinavian": ["scandinavian", "center counter"],
    "ruy lopez": ["ruy lopez", "spanish"],
    "italian": ["italian game", "giuoco", "two knights"],
}

ECO_FAMILY = {
    "A": "flank / english / dutch / various",
    "B": "semi-open (sicilian / caro-kann / …)",
    "C": "open games (e4 e5) / french",
    "D": "closed / queen's gambit / slav",
    "E": "indian defences",
}

_PATTERN_THEME = {
    "structure.iqp": "isolated queen pawn",
    "structure.hanging_pawns": "hanging pawns",
    "structure.carlsbad": "carlsbad",
    "structure.maroczy_bind": "maroczy",
    "structure.hedgehog": "hedgehog",
    "structure.pawn_chain": "pawn chain",
    "structure.scheveningen": "scheveningen",
    "structure.dragon_formation": "dragon formation",
    "structure.caro_slav": "caro slav",
    "structure.doubled_pawns": "doubled pawns",
    "structure.passed_pawn": "passed pawn",
    "structure.symmetrical_center": "symmetrical center",
    "imbalance.bishop_pair": "bishop pair",
    "imbalance.good_vs_bad_bishop": "good vs bad bishop",
    "imbalance.knight_vs_bishop": "knight vs bishop",
    "imbalance.space": "space",
    "imbalance.material_asymmetry": "material asymmetry",
    "positional.outpost": "outpost",
    "positional.prophylaxis": "prophylaxis",
    "positional.color_complexes": "color complexes",
    "positional.restriction": "restriction",
    "positional.two_weaknesses": "two weaknesses",
    "positional.pawn_break": "pawn break",
    "piece.centralization": "piece activity",
    "attack.king_safety": "king safety",
    "opening.sicilian": "sicilian",
    "opening.french": "french",
    "opening.caro_kann": "caro-kann",
    "opening.kings_indian": "king's indian",
    "opening.queens_gambit": "queen's gambit",
    "opening.english": "english",
    "opening.london_system": "london",
    "opening.petroff": "petroff",
    "opening.scandinavian": "scandinavian",
    "endgame.theoretical.lucena": "endgame",
    "endgame.theoretical.philidor": "endgame",
    "endgame.strategic.opposite_bishops": "endgame",
}

_THEME_TO_PATTERN = {
    "isolated queen pawn": "structure.iqp",
    "hanging pawns": "structure.hanging_pawns",
    "carlsbad": "structure.carlsbad",
    "minority attack": "structure.carlsbad",
    "maroczy": "structure.maroczy_bind",
    "hedgehog": "structure.hedgehog",
    "pawn chain": "structure.pawn_chain",
    "scheveningen": "structure.scheveningen",
    "dragon formation": "structure.dragon_formation",
    "caro slav": "structure.caro_slav",
    "doubled pawns": "structure.doubled_pawns",
    "passed pawn": "structure.passed_pawn",
    "symmetrical center": "structure.symmetrical_center",
    "bishop pair": "imbalance.bishop_pair",
    "good vs bad bishop": "imbalance.good_vs_bad_bishop",
    "knight vs bishop": "imbalance.knight_vs_bishop",
    "space": "imbalance.space",
    "material asymmetry": "imbalance.material_asymmetry",
    "outpost": "positional.outpost",
    "prophylaxis": "positional.prophylaxis",
    "color complexes": "positional.color_complexes",
    "restriction": "positional.restriction",
    "two weaknesses": "positional.two_weaknesses",
    "pawn break": "positional.pawn_break",
    "king safety": "attack.king_safety",
    "piece activity": "piece.centralization",
    "sicilian": "opening.sicilian",
    "french": "opening.french",
    "caro-kann": "opening.caro_kann",
    "king's indian": "opening.kings_indian",
    "queen's gambit": "opening.queens_gambit",
    "english": "opening.english",
    "london": "opening.london_system",
    "petroff": "opening.petroff",
    "scandinavian": "opening.scandinavian",
}


COACH_ENDGAME_MATERIAL_MAX = 14
COACH_ENDGAME_DROP_CP = 150

_PIECE_POINTS = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
}


@dataclass
class PositionFeatures:
    phase: str
    themes: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    material_imbalance: int = 0
    eco: str = ""
    opening: str = ""
    narrative: str = ""
    played_san: str = ""
    best_san: str = ""
    drop_cp: int = 0
    tactical_kind: str = ""
    tactical_head: str = ""
    trap_square: str = ""
    piece_label: str = ""
    stm: str = "w"

    def query_text(self) -> str:
        if self.narrative.strip() and not self.narrative.startswith("Patterns:"):
            return self.narrative.strip()
        return build_narrative_query(self)


def _piece_count(board: chess.Board) -> int:
    return len(board.piece_map())


def material_points_excluding_kings(board: chess.Board) -> tuple[int, int]:
    white = 0
    black = 0
    for piece in board.piece_map().values():
        val = _PIECE_POINTS.get(piece.piece_type, 0)
        if piece.color == chess.WHITE:
            white += val
        else:
            black += val
    return white, black


def is_coach_endgame(
    board: chess.Board,
    *,
    tactical_kind: str | None = None,
    drop_cp: int = 0,
) -> bool:
    if tactical_kind:
        return False
    if (drop_cp or 0) > COACH_ENDGAME_DROP_CP:
        return False
    white, black = material_points_excluding_kings(board)
    return white <= COACH_ENDGAME_MATERIAL_MAX and black <= COACH_ENDGAME_MATERIAL_MAX


def _phase(
    board: chess.Board,
    *,
    tactical_kind: str | None = None,
    drop_cp: int = 0,
) -> str:
    count = _piece_count(board)
    if board.fullmove_number <= 12 and count >= 28:
        return "opening"
    if is_coach_endgame(board, tactical_kind=tactical_kind, drop_cp=drop_cp):
        return "endgame"
    return "middlegame"


def _material_imbalance(board: chess.Board) -> int:
    white, black = material_points_excluding_kings(board)
    return white - black


def _kind_label(kind: str) -> str:
    return (kind or "").replace("_", " ").strip()


def _side_name(stm: str) -> str:
    return "White" if stm == "w" else "Black"


def narrative_seed_for_key(
    key_id: str,
    *,
    label: str = "",
    opening: str = "",
    eco: str = "",
) -> str:
    name = (label or key_id.replace(".", " ")).strip()
    family = (key_id.split(".")[0] if key_id else "").lower()
    if family in {"motif", "attack"}:
        return (
            f"Tactical motif {name}: piece trap activity and candidate moves "
            f"prophylaxis against hanging material."
        )
    if family == "opening" or opening:
        opening_name = opening or name
        eco_bit = f" {eco}" if eco else ""
        return (
            f"{opening_name}{eco_bit} opening plan: developing minor pieces "
            f"before queen outings and typical pawn breaks."
        )
    if family == "endgame":
        return (
            f"Endgame technique {name}: king activation taking opposition "
            f"and king leading passed pawn."
        )
    return f"{name} strategic plans typical positions {key_id.replace('.', ' ')}".strip()


def build_narrative_query(features: PositionFeatures) -> str:
    side = _side_name(features.stm)
    played = (features.played_san or "").strip()
    best = (features.best_san or "").strip()
    kind = _kind_label(features.tactical_kind)
    head = (features.tactical_head or "").strip()
    piece = (features.piece_label or "piece").strip()
    square = (features.trap_square or "").strip()
    opening = (features.opening or "").strip()
    eco = (features.eco or "").strip()

    if features.tactical_kind or (features.drop_cp or 0) > COACH_ENDGAME_DROP_CP:
        trap_bit = ""
        if square:
            trap_bit = f" leaving {piece} on {square} without escape squares"
        elif kind:
            trap_bit = f" {kind}"
        engine_bit = ""
        if best and best != played:
            engine_bit = f" Engine best line {best} saving piece."
        lead = head or (
            f"Tactical blunder {kind or 'tactics'}: {side} played {played or 'the move'}"
            f"{trap_bit}."
        )
        if head and not lead.endswith("."):
            lead = lead.rstrip() + "."
        return f"{lead}{engine_bit} Prophylaxis against piece activity.".strip()

    if features.phase == "opening":
        name = opening or "Opening"
        eco_bit = f" {eco}" if eco else ""
        played_bit = f"{side} played {played}" if played else f"{side} to move"
        best_bit = ""
        if best and played and best != played:
            best_bit = f" wasting tempo instead of developing {best} minor piece"
        return (
            f"{name}{eco_bit} opening plan: {played_bit}{best_bit or ' developing minor pieces'}."
        ).strip()

    if features.phase == "endgame":
        played_bit = f"{side} played {played}" if played else f"{side} to move"
        engine_bit = ""
        if best and best != played:
            engine_bit = (
                f" Engine line {best} taking opposition and king leading passed pawn."
            )
        return (
            f"King and pawn endgame technique: {played_bit} pawn push before king activation."
            f"{engine_bit}"
        ).strip()

    name = opening or "Middlegame"
    return (
        f"{name} strategic plans typical moves"
        + (f" after {played}" if played else "")
        + (f". Engine line {best}" if best and best != played else "")
        + "."
    ).strip()


def extract_features(
    fen: str,
    *,
    eco: str = "",
    opening: str = "",
    delta_cp: int | None = None,
    played_san: str = "",
    best_san: str = "",
    ontology_dir: str | None = None,
    tactical_kind: str = "",
    tactical_head: str = "",
    trap_square: str = "",
    piece_label: str = "",
) -> PositionFeatures:
    board = chess.Board(fen)
    drop = int(delta_cp or 0)
    phase = _phase(board, tactical_kind=tactical_kind or None, drop_cp=drop)
    patterns = detect_pattern_ids(fen, eco=eco, opening=opening, ontology_dir=ontology_dir)
    patterns = expand_related(patterns, hops=0, ontology_dir=ontology_dir, limit=8)

    themes: list[str] = []
    if phase == "opening":
        themes.append("opening")
    if phase == "endgame":
        themes.append("endgame")
    for pid in patterns:
        theme = _PATTERN_THEME.get(pid)
        if theme and theme not in themes:
            themes.append(theme)

    blob = f"{opening} {eco}".lower()
    for theme, keys in THEME_KEYWORDS.items():
        if theme in ("opening", "endgame"):
            continue
        if any(k in blob for k in keys):
            if theme not in themes:
                themes.append(theme)

    imb = _material_imbalance(board)
    stm = "w" if board.turn == chess.WHITE else "b"
    features = PositionFeatures(
        phase=phase,
        themes=themes,
        patterns=patterns,
        material_imbalance=imb,
        eco=eco,
        opening=opening,
        played_san=played_san,
        best_san=best_san,
        drop_cp=drop,
        tactical_kind=tactical_kind,
        tactical_head=tactical_head,
        trap_square=trap_square,
        piece_label=piece_label,
        stm=stm,
    )
    features.narrative = build_narrative_query(features)
    return features
