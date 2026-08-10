from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import chess
import chess.engine


@dataclass
class EngineResult:
    eval_cp: int | None
    mate: int | None
    best_move_uci: str | None
    pv_san: list[str]
    depth: int

    def white_pov_cp(self) -> int | None:
        return self.eval_cp


class StockfishEngine:
    def __init__(self, path: str = "stockfish", depth: int = 18) -> None:
        self.path = path
        self.depth = depth
        self._engine: chess.engine.SimpleEngine | None = None

    def __enter__(self) -> StockfishEngine:
        self.open()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def open(self) -> None:
        if self._engine is None:
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)

    def close(self) -> None:
        if self._engine is not None:
            self._engine.quit()
            self._engine = None

    def analyze_fen(self, fen: str, depth: int | None = None) -> EngineResult:
        if self._engine is None:
            self.open()
        assert self._engine is not None
        board = chess.Board(fen)
        limit = chess.engine.Limit(depth=depth or self.depth)
        info = self._engine.analyse(board, limit, multipv=1)
        if isinstance(info, list):
            info = info[0]
        score = info.get("score")
        eval_cp: int | None = None
        mate: int | None = None
        if score is not None:
            pov = score.white()
            if pov.is_mate():
                mate = pov.mate()
            else:
                eval_cp = pov.score(mate_score=100000)
        pv = info.get("pv") or []
        best_move = pv[0].uci() if pv else None
        temp = board.copy()
        pv_san: list[str] = []
        for move in pv[:8]:
            pv_san.append(temp.san(move))
            temp.push(move)
        return EngineResult(
            eval_cp=eval_cp,
            mate=mate,
            best_move_uci=best_move,
            pv_san=pv_san,
            depth=info.get("depth") or (depth or self.depth),
        )
