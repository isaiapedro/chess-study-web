from __future__ import annotations

from pathlib import Path
from typing import Any

import chess
import chess.pgn

from chess_coach.analyze import CriticalMoment, find_critical_moments
from chess_coach.comment import Commentary, engine_only_fallback, explain
from chess_coach.engine import StockfishEngine
from chess_coach.rag.retrieve import retrieve_passages


def _nag_for_loss(delta_cp: int) -> int | None:
    if delta_cp >= 300:
        return chess.pgn.NAG_BLUNDER
    if delta_cp >= 150:
        return chess.pgn.NAG_MISTAKE
    if delta_cp >= 80:
        return chess.pgn.NAG_DUBIOUS_MOVE
    return None


def _comment_text(moment: CriticalMoment, commentary: Commentary) -> str:
    if moment.mate_before is not None:
        eval_bit = f"[%eval #{moment.mate_before}]"
    elif moment.eval_before_cp is not None:
        eval_bit = f"[%eval {moment.eval_before_cp / 100:.2f}]"
    else:
        eval_bit = ""
    body = commentary.text.replace("{", "(").replace("}", ")")
    cites = ""
    if commentary.citations:
        cites = " Sources: " + ", ".join(sorted(set(commentary.citations))) + "."
    best = f" Best: {moment.best_san}." if moment.best_san else ""
    pv = f" PV: {' '.join(moment.pv_san)}." if moment.pv_san else ""
    return f"{eval_bit} {body}{best}{pv}{cites}".strip()


def annotate_game(
    game: chess.pgn.Game,
    config: dict[str, Any],
    *,
    use_rag: bool = True,
    use_llm: bool = True,
    depth: int | None = None,
    threshold: int | None = None,
) -> tuple[chess.pgn.Game, list[CriticalMoment], list[Commentary]]:
    depth = depth or int(config.get("analyze_depth", 12))
    threshold = threshold or int(config.get("critical_cp_threshold", 120))

    with StockfishEngine(path=config.get("stockfish_path", "stockfish"), depth=depth) as engine:
        moments = find_critical_moments(game, engine, threshold_cp=threshold)

    commentaries: list[Commentary] = []
    for moment in moments:
        passages = []
        if use_rag:
            try:
                passages = retrieve_passages(moment.features, config)
            except Exception:
                passages = []
        if use_llm:
            commentaries.append(explain(moment, passages, config, allow_fallback=True))
        else:
            commentaries.append(engine_only_fallback(moment, passages))

    by_ply = {m.ply: (m, c) for m, c in zip(moments, commentaries)}
    board = game.board()
    node: chess.pgn.GameNode = game
    ply = 0
    while node.variations:
        next_node = node.variation(0)
        ply += 1
        if ply in by_ply:
            moment, commentary = by_ply[ply]
            nag = _nag_for_loss(moment.delta_cp)
            if nag is not None:
                next_node.nags.add(nag)
            next_node.comment = _comment_text(moment, commentary)
            if moment.best_uci and moment.best_uci != moment.played_uci:
                try:
                    best_move = chess.Move.from_uci(moment.best_uci)
                    if best_move in board.legal_moves:
                        variation = node.add_variation(best_move)
                        variation.comment = f"Engine best (depth {moment.depth})"
                except Exception:
                    pass
        board.push(next_node.move)
        node = next_node

    game.headers["Annotator"] = "chess-coach + Stockfish"
    if moments:
        game.headers["CoachMoments"] = str(len(moments))
    return game, moments, commentaries


def export_annotated_pgn(game: chess.pgn.Game, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
    text = game.accept(exporter)
    out_path.write_text(text.strip() + "\n", encoding="utf-8")


def annotate_pgn_file(
    pgn_path: Path,
    config: dict[str, Any],
    out_pgn: Path,
    *,
    game_index: int = 0,
    use_rag: bool = True,
    use_llm: bool = True,
    depth: int | None = None,
    threshold: int | None = None,
) -> tuple[chess.pgn.Game, list[CriticalMoment], list[Commentary]]:
    with pgn_path.open(encoding="utf-8", errors="replace") as handle:
        game = None
        for _ in range(game_index + 1):
            game = chess.pgn.read_game(handle)
            if game is None:
                raise ValueError(f"No game at index {game_index} in {pgn_path}")
    assert game is not None
    annotated, moments, commentaries = annotate_game(
        game,
        config,
        use_rag=use_rag,
        use_llm=use_llm,
        depth=depth,
        threshold=threshold,
    )
    export_annotated_pgn(annotated, out_pgn)
    return annotated, moments, commentaries
