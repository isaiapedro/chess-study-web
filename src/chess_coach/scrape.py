from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

LICHESS_GAMES = "https://lichess.org/api/games/user/{user}"
LICHESS_GAME = "https://lichess.org/game/export/{game_id}"
LICHESS_MASTERS = "https://explorer.lichess.ovh/masters"
LICHESS_MASTER_PGN = "https://explorer.lichess.ovh/masters/pgn/{game_id}"
CHESSCOM_ARCHIVES = "https://api.chess.com/pub/player/{user}/games/archives"
USER_AGENT = "chess-coach/0.1 (local offline coaching; +https://lichess.org/api)"


@dataclass
class ScrapeResult:
    saved: list[Path]
    skipped: int
    errors: list[str]


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=60.0,
        headers={"User-Agent": USER_AGENT, "Accept": "application/x-chess-pgn"},
        follow_redirects=True,
    )


def _safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return cleaned[:80] or "game"


def _split_pgn_games(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.startswith("[Event ") and current:
            blocks.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    return [b for b in blocks if b and "[" in b]


def _headers_from_pgn(pgn: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for match in re.finditer(r'^\[(\w+)\s+"(.*)"\]\s*$', pgn, re.M):
        headers[match.group(1)] = match.group(2)
    return headers


def _write_game(pgn: str, out_dir: Path, prefix: str) -> Path:
    headers = _headers_from_pgn(pgn)
    white = _safe_name(headers.get("White", "White"))
    black = _safe_name(headers.get("Black", "Black"))
    date = _safe_name(headers.get("Date", "0000.00.00").replace(".", "-"))
    site = headers.get("Site", "")
    game_id = headers.get("GameId") or headers.get("LichessId")
    if not game_id and "lichess.org/" in site:
        game_id = site.rstrip("/").split("/")[-1]
    game_id = _safe_name(game_id or f"{prefix}_{white}_{black}_{date}")
    path = out_dir / f"{game_id}.pgn"
    # Standardize a few coach tags for Scid filtering
    if "Annotator" not in headers:
        pgn = pgn.replace("[Result ", '[Annotator "chess-coach"]\n[Result ', 1)
    if "ECO" not in headers and "Opening" in headers:
        pass
    path.write_text(pgn.strip() + "\n", encoding="utf-8")
    return path


def scrape_lichess_user(user: str, out_dir: Path, *, max_games: int = 20, rated: bool = True) -> ScrapeResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    errors: list[str] = []
    params = {"max": str(max_games), "rated": "true" if rated else "false", "moves": "true", "pgnInJson": "false"}
    url = LICHESS_GAMES.format(user=quote(user))
    try:
        with _client() as client:
            response = client.get(url, params=params)
            response.raise_for_status()
            for block in _split_pgn_games(response.text):
                saved.append(_write_game(block, out_dir, prefix=user))
    except Exception as exc:
        errors.append(f"lichess user {user}: {exc}")
    return ScrapeResult(saved=saved, skipped=0, errors=errors)


def scrape_lichess_game_ids(game_ids: list[str], out_dir: Path) -> ScrapeResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    errors: list[str] = []
    with _client() as client:
        for game_id in game_ids:
            try:
                response = client.get(LICHESS_GAME.format(game_id=game_id))
                response.raise_for_status()
                saved.append(_write_game(response.text, out_dir, prefix=game_id))
                time.sleep(0.2)
            except Exception as exc:
                errors.append(f"lichess game {game_id}: {exc}")
    return ScrapeResult(saved=saved, skipped=0, errors=errors)


def scrape_chesscom_month(user: str, year: int, month: int, out_dir: Path, *, max_games: int = 50) -> ScrapeResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    errors: list[str] = []
    url = f"https://api.chess.com/pub/player/{quote(user.lower())}/games/{year}/{month:02d}"
    try:
        with httpx.Client(timeout=60.0, headers={"User-Agent": USER_AGENT}) as client:
            response = client.get(url)
            response.raise_for_status()
            games = response.json().get("games") or []
            for game in games[:max_games]:
                pgn = game.get("pgn")
                if not pgn:
                    continue
                saved.append(_write_game(pgn, out_dir, prefix=user))
    except Exception as exc:
        errors.append(f"chess.com {user} {year}-{month:02d}: {exc}")
    return ScrapeResult(saved=saved, skipped=0, errors=errors)


def scrape_masters_opening(
    play: str,
    out_dir: Path,
    *,
    max_games: int = 10,
) -> ScrapeResult:
    """Fetch master games from Lichess opening explorer (may 401 in some networks)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    errors: list[str] = []
    try:
        with httpx.Client(timeout=60.0, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}) as client:
            response = client.get(LICHESS_MASTERS, params={"play": play, "topGames": max_games})
            if response.status_code == 401:
                errors.append(
                    "masters explorer returned 401 — use --lichess-user / --chesscom-user / --game-id instead"
                )
                return ScrapeResult(saved=saved, skipped=0, errors=errors)
            response.raise_for_status()
            payload = response.json()
            games = payload.get("topGames") or payload.get("recentGames") or []
            for game in games[:max_games]:
                game_id = game.get("id")
                if not game_id:
                    continue
                pgn_resp = client.get(LICHESS_MASTER_PGN.format(game_id=game_id))
                pgn_resp.raise_for_status()
                saved.append(_write_game(pgn_resp.text, out_dir, prefix=f"master_{game_id}"))
                time.sleep(0.25)
    except Exception as exc:
        errors.append(f"masters opening {play}: {exc}")
    return ScrapeResult(saved=saved, skipped=0, errors=errors)


def scrape_pgn_url(url: str, out_dir: Path) -> ScrapeResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    errors: list[str] = []
    try:
        with _client() as client:
            response = client.get(url)
            response.raise_for_status()
            for block in _split_pgn_games(response.text):
                saved.append(_write_game(block, out_dir, prefix="url"))
    except Exception as exc:
        errors.append(f"url {url}: {exc}")
    return ScrapeResult(saved=saved, skipped=0, errors=errors)


def summarize(result: ScrapeResult) -> str:
    lines = [f"Saved {len(result.saved)} PGN(s)."]
    for path in result.saved:
        lines.append(f"  - {path}")
    for err in result.errors:
        lines.append(f"ERROR: {err}")
    return "\n".join(lines)
