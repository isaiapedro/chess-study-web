from __future__ import annotations

from dataclasses import dataclass, field

import chess

from chess_coach.ontology.cards import pattern_query_text
from chess_coach.ontology.detect import detect_pattern_ids
from chess_coach.ontology.load import expand_related


THEME_KEYWORDS = {
    "isolated queen pawn": ["isolated queen pawn", "iqp", "isolani"],
    "hanging pawns": ["hanging pawns"],
    "minority attack": ["minority attack"],
    "passed pawn": ["passed pawn", "passer"],
    "open file": ["open file", "half-open"],
    "bishop pair": ["bishop pair", "two bishops"],
    "king safety": ["king safety", "attack on the king", "kingside attack"],
    "piece activity": ["piece activity", "centralization"],
    "endgame": ["endgame", "opposition", "zugzwang"],
    "opening": ["opening", "development", "theory", "tabiya"],
    "sicilian": ["sicilian", "dragon", "najdorf", "scheveningen", "sveshnikov"],
    "french": ["french defence", "french defense"],
    "caro-kann": ["caro-kann", "caro kann"],
    "king's indian": ["king's indian", "kings indian", "kíd"],
    "nimzo-indian": ["nimzo-indian", "nimzo indian"],
    "queen's gambit": ["queen's gambit", "queens gambit", "qgd", "qga"],
    "english": ["english opening"],
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
    "structure.minority_attack": "minority attack",
    "structure.doubled_pawns": "doubled pawns",
    "structure.open_c_file": "open file",
    "structure.open_e_file": "open file",
    "structure.passed_pawn": "passed pawn",
    "structure.pawn_chain": "pawn chain",
    "structure.maroczy_bind": "maroczy",
    "structure.hedgehog": "hedgehog",
    "imbalance.bishop_pair": "bishop pair",
    "imbalance.opposite_bishops": "opposite bishops",
    "imbalance.king_safety": "king safety",
    "imbalance.material": "material imbalance",
    "imbalance.space": "space",
    "opening.sicilian_najdorf": "sicilian",
    "opening.sicilian_dragon": "sicilian",
    "opening.sicilian_scheveningen": "sicilian",
    "opening.french": "french",
    "opening.caro_kann": "caro-kann",
    "opening.kings_indian": "king's indian",
    "opening.queens_gambit": "queen's gambit",
    "endgame.lucena": "endgame",
    "endgame.philidor": "endgame",
    "endgame.opposite_bishops": "endgame",
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

    def query_text(self) -> str:
        ont = pattern_query_text(self.patterns) if self.patterns else ""
        parts = [
            ont,
            f"{self.phase} plans and typical moves in this structure",
            f"Themes: {', '.join(t for t in self.themes if t != 'opening')}"
            if any(t != "opening" for t in self.themes)
            else "",
            f"Opening: {self.opening} middlegame plans" if self.opening else "",
            f"ECO {self.eco} pawn structure plans" if self.eco else "",
            self.narrative,
        ]
        return ". ".join(p for p in parts if p).strip()


def _piece_count(board: chess.Board) -> int:
    return len(board.piece_map())


def _phase(board: chess.Board) -> str:
    count = _piece_count(board)
    if board.fullmove_number <= 12 and count >= 28:
        return "opening"
    if count <= 12:
        return "endgame"
    return "middlegame"


def _material_imbalance(board: chess.Board) -> int:
    values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
    }
    score = 0
    for square, piece in board.piece_map().items():
        delta = values.get(piece.piece_type, 0)
        score += delta if piece.color == chess.WHITE else -delta
    return score


def extract_features(
    fen: str,
    *,
    eco: str = "",
    opening: str = "",
    delta_cp: int | None = None,
    played_san: str = "",
    best_san: str = "",
    ontology_dir: str | None = None,
) -> PositionFeatures:
    board = chess.Board(fen)
    phase = _phase(board)
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
    narrative_bits = []
    if patterns:
        narrative_bits.append("Patterns: " + ", ".join(patterns))
    if opening:
        narrative_bits.append(f"Opening line: {opening}")
    if eco:
        family = ECO_FAMILY.get(eco[:1].upper(), "")
        narrative_bits.append(f"ECO {eco}" + (f" ({family})" if family else ""))
    if played_san:
        narrative_bits.append(f"Move played: {played_san}")
    if delta_cp is not None and abs(delta_cp) >= 40:
        narrative_bits.append(f"Eval swing {delta_cp:+d} centipawns")
    if best_san and played_san and best_san != played_san:
        narrative_bits.append(f"Engine prefers {best_san}")
    if themes:
        narrative_bits.append("Positional themes: " + ", ".join(themes))
    return PositionFeatures(
        phase=phase,
        themes=themes,
        patterns=patterns,
        material_imbalance=imb,
        eco=eco,
        opening=opening,
        narrative=". ".join(narrative_bits),
    )
