from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import chess
import chess.pgn

from chess_coach.engine import EngineResult, StockfishEngine
from chess_coach.features import PositionFeatures, extract_features
from chess_coach.logutil import log
from chess_coach.pgn_io import iter_plies


@dataclass
class CriticalMoment:
    ply: int
    fullmove: int
    side: str
    fen_before: str
    played_san: str
    played_uci: str
    best_san: str
    best_uci: str | None
    eval_before_cp: int | None
    eval_after_cp: int | None
    delta_cp: int
    mate_before: int | None
    mate_after: int | None
    pv_san: list[str]
    depth: int
    features: PositionFeatures = field(default_factory=lambda: PositionFeatures(phase="middlegame"))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


def _white_pov_score(result: EngineResult) -> int:
    if result.mate is not None:
        if result.mate > 0:
            return 100000 - result.mate * 100
        if result.mate < 0:
            return -100000 - result.mate * 100
        return 0
    return result.eval_cp if result.eval_cp is not None else 0


def _loss_for_side(before: EngineResult, after: EngineResult, side: str, board_after: chess.Board) -> int:
    if board_after.is_checkmate():
        return 0
    before_cp = _white_pov_score(before)
    after_cp = _white_pov_score(after)
    if side == "white":
        return before_cp - after_cp
    return after_cp - before_cp


def is_critical_moment(moment: CriticalMoment, threshold_cp: int) -> bool:
    if moment.delta_cp >= threshold_cp:
        return True
    if moment.mate_before is None and moment.mate_after is not None:
        if moment.side == "white" and moment.mate_after < 0:
            return True
        if moment.side == "black" and moment.mate_after > 0:
            return True
    return False


def analyze_game_plies(
    game: chess.pgn.Game,
    engine: StockfishEngine,
) -> list[CriticalMoment]:
    """Stockfish every ply — used for critical filter + dense RAG commentary."""
    eco = game.headers.get("ECO", "")
    opening = game.headers.get("Opening", "") or game.headers.get("Variation", "")
    moments: list[CriticalMoment] = []
    plies = list(iter_plies(game))
    total = len(plies)
    log("Stockfish scan: %d plies (depth=%s)", total, engine.depth)

    for ply_info in plies:
        ply = ply_info["ply"]
        if ply == 1 or ply % 5 == 0 or ply == total:
            log(
                "  analyzing ply %d/%d (%s %s)...",
                ply,
                total,
                ply_info["turn_before"],
                ply_info["move_san"],
            )
        before = engine.analyze_fen(ply_info["fen_before"])
        after = engine.analyze_fen(ply_info["fen_after"])
        side = ply_info["turn_before"]
        board_after = chess.Board(ply_info["fen_after"])
        loss = _loss_for_side(before, after, side, board_after)

        board = chess.Board(ply_info["fen_before"])
        best_san = ""
        if before.best_move_uci:
            best_move = chess.Move.from_uci(before.best_move_uci)
            if best_move in board.legal_moves:
                best_san = board.san(best_move)

        features = extract_features(
            ply_info["fen_before"],
            eco=eco,
            opening=opening,
            delta_cp=-loss if side == "white" else loss,
            played_san=ply_info["move_san"],
            best_san=best_san,
        )
        moments.append(
            CriticalMoment(
                ply=ply_info["ply"],
                fullmove=ply_info["fullmove"],
                side=side,
                fen_before=ply_info["fen_before"],
                played_san=ply_info["move_san"],
                played_uci=ply_info["move_uci"],
                best_san=best_san,
                best_uci=before.best_move_uci,
                eval_before_cp=before.eval_cp,
                eval_after_cp=after.eval_cp,
                delta_cp=max(0, loss),
                mate_before=before.mate,
                mate_after=after.mate,
                pv_san=before.pv_san,
                depth=before.depth,
                features=features,
            )
        )
    log("Stockfish scan done: %d plies", len(moments))
    return moments


def find_critical_moments(
    game: chess.pgn.Game,
    engine: StockfishEngine,
    threshold_cp: int = 120,
) -> list[CriticalMoment]:
    moments = analyze_game_plies(game, engine)
    critical = [m for m in moments if is_critical_moment(m, threshold_cp)]
    for moment in critical:
        log(
            "  critical: ply %d %s loss=%scp best=%s",
            moment.ply,
            moment.played_san,
            moment.delta_cp,
            moment.best_san or "?",
        )
    log("Stockfish critical filter: %d moments (threshold=%scp)", len(critical), threshold_cp)
    return critical
