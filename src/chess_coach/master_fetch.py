from __future__ import annotations

from pathlib import Path
from typing import Any

from chess_coach.chessgames import ChessgamesClient, ChessgamesHit, FetchResult
from chess_coach.logutil import log
from chess_coach.masters_db import LocalMastersDB


def masters_db_from_config(config: dict[str, Any]) -> LocalMastersDB | None:
    masters = config.get("masters") or {}
    if not masters.get("enabled", True):
        return None
    index_path = Path(masters.get("index_path", "data/masters/index.sqlite"))
    pgn_dir = Path(masters.get("pgn_dir", "data/masters/pgn"))
    return LocalMastersDB(index_path=index_path, pgn_dir=pgn_dir)


def fetch_master_game(
    white: str,
    black: str,
    year: int | None = None,
    event_hint: str | None = None,
    *,
    config: dict[str, Any],
    out_dir: Path | None = None,
    client: ChessgamesClient | None = None,
) -> FetchResult | None:
    """Local Gigabase/PGN index first, then Chessgames fallback."""
    masters = config.get("masters") or {}
    db = masters_db_from_config(config)
    if db is not None and db.available:
        log(
            "Master fetch: local index (%d games) %s vs %s %s",
            db.game_count(),
            white,
            black,
            year or "?",
        )
        hit = db.find(
            white,
            black,
            year=year,
            event_hint=event_hint,
            soft_year=bool(masters.get("soft_year", True)),
        )
        if hit is not None:
            pgn = db.fetch_pgn(hit)
            path: Path | None = None
            if out_dir is not None:
                out_dir.mkdir(parents=True, exist_ok=True)
                path = out_dir / f"{hit.gid}.pgn"
                path.write_text(pgn if pgn.endswith("\n") else pgn + "\n", encoding="utf-8")
            return FetchResult(
                pgn=pgn,
                hit=ChessgamesHit(
                    gid=hit.gid,
                    white=hit.white,
                    black=hit.black,
                    year=str(hit.year or ""),
                    result=hit.result,
                    event=hit.event,
                    eco=hit.eco,
                    url=f"file://{hit.path}#offset={hit.offset}",
                ),
                path=path,
            )
        log("Master fetch: no local hit — trying Chessgames")
    else:
        if db is not None:
            log(
                "Master fetch: local index unavailable (%s) — Chessgames",
                db.index_path,
            )
        else:
            log("Master fetch: local masters disabled — Chessgames")

    if not masters.get("chessgames_fallback", True):
        log("Master fetch: Chessgames fallback disabled")
        return None

    owns = client is None
    client = client or ChessgamesClient(delay_s=float(masters.get("chessgames_delay_s", 1.8)))
    try:
        return client.fetch_best_match(
            white,
            black,
            year=year,
            event_hint=event_hint,
            out_dir=out_dir,
        )
    finally:
        if owns:
            client.close()
