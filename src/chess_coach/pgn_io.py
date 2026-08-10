from __future__ import annotations

import io
from pathlib import Path
from typing import Iterator

import chess
import chess.pgn


def load_game(path: Path | None = None, text: str | None = None, game_index: int = 0) -> chess.pgn.Game:
    if text is not None:
        handle = io.StringIO(text)
        games = []
        while True:
            game = chess.pgn.read_game(handle)
            if game is None:
                break
            games.append(game)
        if not games:
            raise ValueError("No PGN games found in text")
        if game_index >= len(games):
            raise IndexError(f"Game index {game_index} out of range ({len(games)} games)")
        return games[game_index]
    if path is None:
        raise ValueError("Provide path or text")
    with path.open(encoding="utf-8", errors="replace") as handle:
        games = []
        while True:
            game = chess.pgn.read_game(handle)
            if game is None:
                break
            games.append(game)
    if not games:
        raise ValueError(f"No PGN games found in {path}")
    if game_index >= len(games):
        raise IndexError(f"Game index {game_index} out of range ({len(games)} games)")
    return games[game_index]


def iter_plies(game: chess.pgn.Game) -> Iterator[dict]:
    board = game.board()
    ply = 0
    node = game
    while node.variations:
        next_node = node.variation(0)
        move = next_node.move
        fen_before = board.fen()
        turn_before = "white" if board.turn == chess.WHITE else "black"
        fullmove = board.fullmove_number
        san = board.san(move)
        board.push(move)
        ply += 1
        yield {
            "ply": ply,
            "fen_before": fen_before,
            "fen_after": board.fen(),
            "move_uci": move.uci(),
            "move_san": san,
            "turn_before": turn_before,
            "fullmove": fullmove,
        }
        node = next_node
