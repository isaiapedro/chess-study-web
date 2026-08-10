from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import httpx

from chess_coach.config import ROOT

LICHESS_API = "https://lichess.org"
USER_AGENT = "chess-coach/0.1 (local coaching; study:write; +https://lichess.org/api)"
MAX_CHAPTERS = 64
MAX_PGN_CHARS = 100_000


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_token(explicit: str | None = None) -> str:
    _load_dotenv()
    token = (explicit or os.environ.get("LICHESS_TOKEN") or "").strip()
    if not token:
        raise RuntimeError(
            "Missing Lichess token. Set LICHESS_TOKEN or pass --token "
            "(https://lichess.org/account/oauth/token — scope study:write)."
        )
    return token


def _headers_from_pgn(pgn: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for match in re.finditer(r'^\[(\w+)\s+"(.*)"\]\s*$', pgn, re.M):
        headers[match.group(1)] = match.group(2)
    return headers


def chapter_name_from_pgn(pgn: str, fallback: str = "Chapter") -> str:
    headers = _headers_from_pgn(pgn)
    white = (headers.get("White") or "").strip()
    black = (headers.get("Black") or "").strip()
    if white and black:
        name = f"{white} - {black}"
    else:
        name = (headers.get("Event") or headers.get("Opening") or fallback).strip()
    name = re.sub(r"\s+", " ", name).strip() or fallback
    return name[:100]


def split_pgn_games(text: str) -> list[str]:
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


def collect_pgn_paths(paths: Sequence[Path], *, include_raw: bool = False) -> list[Path]:
    found: list[Path] = []
    for path in paths:
        path = path.resolve()
        if path.is_file() and path.suffix.lower() == ".pgn":
            found.append(path)
            continue
        if path.is_dir():
            for pgn in sorted(path.rglob("*.pgn")):
                if not include_raw and "raw" in pgn.parts:
                    continue
                found.append(pgn)
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in found:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def load_annotated_games(paths: Sequence[Path], *, include_raw: bool = False) -> list[tuple[str, str]]:
    """Return (chapter_hint, pgn_text) preserving variations/comments from annotated files."""
    games: list[tuple[str, str]] = []
    for path in collect_pgn_paths(paths, include_raw=include_raw):
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if not text:
            continue
        for block in split_pgn_games(text):
            if len(block) > MAX_PGN_CHARS:
                raise ValueError(f"PGN too large for Lichess ({len(block)} > {MAX_PGN_CHARS}): {path}")
            hint = chapter_name_from_pgn(block, fallback=path.stem)
            games.append((hint, block if block.endswith("\n") else block + "\n"))
    if not games:
        raise FileNotFoundError("No .pgn games found")
    if len(games) > MAX_CHAPTERS:
        raise ValueError(f"Lichess studies allow at most {MAX_CHAPTERS} chapters; got {len(games)}")
    return games


@dataclass
class StudyChapter:
    id: str
    name: str


@dataclass
class StudyPushResult:
    study_id: str
    url: str
    chapters: list[StudyChapter] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return bool(self.study_id) and not self.errors


class LichessStudyClient:
    """Bearer + study:write — same auth pattern as chess-wrapped mobile."""

    def __init__(self, token: str, *, timeout: float = 60.0) -> None:
        self.token = token
        self._client = httpx.Client(
            base_url=LICHESS_API,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": USER_AGENT,
            },
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> LichessStudyClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def create_study(
        self,
        name: str,
        *,
        visibility: str = "unlisted",
        computer: str = "everyone",
        explorer: str = "everyone",
        cloneable: str = "everyone",
        shareable: str = "everyone",
        chat: str = "member",
        sticky: bool = True,
    ) -> str:
        body = {
            "name": name[:100],
            "visibility": visibility,
            "computer": computer,
            "explorer": explorer,
            "cloneable": cloneable,
            "shareable": shareable,
            "chat": chat,
            "sticky": "true" if sticky else "false",
        }
        response = self._client.post("/api/study", data=body)
        if response.status_code >= 400:
            raise RuntimeError(f"Create study failed ({response.status_code}): {response.text}")
        study_id = str((response.json() or {}).get("id") or "")
        if not study_id:
            raise RuntimeError(f"Create study response missing id: {response.text}")
        return study_id

    def import_pgn(
        self,
        study_id: str,
        pgn: str,
        *,
        name: str | None = None,
        orientation: str | None = None,
        variant: str = "standard",
        mode: str | None = None,
        initial: bool = False,
        sticky: bool = True,
        is_default_name: bool | None = None,
    ) -> tuple[list[StudyChapter], str | None]:
        if is_default_name is None:
            is_default_name = not bool(name and name.strip())
        data: dict[str, str] = {
            "pgn": pgn.strip() + "\n",
            "variant": variant,
            "initial": "true" if initial else "false",
            "sticky": "true" if sticky else "false",
            "isDefaultName": "true" if is_default_name else "false",
        }
        if name and name.strip() and not is_default_name:
            data["name"] = name.strip()[:100]
        if orientation in ("white", "black"):
            data["orientation"] = orientation
        if mode in ("practice", "conceal", "gamebook"):
            data["mode"] = mode
        response = self._client.post(f"/api/study/{study_id}/import-pgn", data=data)
        if response.status_code >= 400:
            raise RuntimeError(f"Import PGN failed ({response.status_code}): {response.text}")
        payload = response.json() or {}
        chapters = [
            StudyChapter(id=str(ch.get("id") or ""), name=str(ch.get("name") or ""))
            for ch in payload.get("chapters") or []
            if ch.get("id")
        ]
        err = payload.get("error")
        error_text = str(err) if err else None
        return chapters, error_text


def push_annotated_pgns(
    paths: Sequence[Path],
    *,
    token: str | None = None,
    study_name: str | None = None,
    study_id: str | None = None,
    visibility: str = "unlisted",
    orientation: str | None = None,
    per_chapter: bool = True,
    delay_s: float = 0.35,
    include_raw: bool = False,
    dry_run: bool = False,
) -> StudyPushResult:
    """Upload annotated PGNs (comments + variations) into a Lichess study."""
    games = load_annotated_games(paths, include_raw=include_raw)
    name = (study_name or _default_study_name(paths, games)).strip()[:100]
    if dry_run:
        preview = StudyPushResult(study_id=study_id or "(new)", url="", chapters=[])
        for hint, pgn in games:
            has_var = "(" in pgn
            preview.chapters.append(
                StudyChapter(id="-", name=f"{hint} ({'vars' if has_var else 'mainline-only'})")
            )
        return preview

    auth = resolve_token(token)
    created = False
    with LichessStudyClient(auth) as client:
        sid = (study_id or "").strip()
        if not sid:
            sid = client.create_study(name, visibility=visibility)
            created = True
        chapters: list[StudyChapter] = []
        errors: list[str] = []
        if per_chapter:
            for index, (hint, pgn) in enumerate(games):
                imported, err = client.import_pgn(
                    sid,
                    pgn,
                    name=hint,
                    orientation=orientation,
                    initial=created and index == 0,
                    is_default_name=False,
                )
                chapters.extend(imported)
                if err:
                    errors.append(f"{hint}: {err}")
                if delay_s > 0 and index + 1 < len(games):
                    time.sleep(delay_s)
        else:
            joined = "\n\n".join(pgn.strip() for _, pgn in games) + "\n"
            imported, err = client.import_pgn(
                sid,
                joined,
                name=games[0][0] if games else name,
                orientation=orientation,
                initial=created,
                is_default_name=False,
            )
            chapters.extend(imported)
            if err:
                errors.append(str(err))
    return StudyPushResult(
        study_id=sid,
        url=f"https://lichess.org/study/{sid}",
        chapters=chapters,
        errors=errors,
    )


def _default_study_name(paths: Sequence[Path], games: Iterable[tuple[str, str]]) -> str:
    for path in paths:
        if path.is_dir():
            return f"Chess Coach · {path.name}"[:100]
        if path.is_file():
            return chapter_name_from_pgn(
                path.read_text(encoding="utf-8", errors="replace"),
                fallback=path.stem,
            )
    first = next(iter(games), None)
    return (first[0] if first else "Chess Coach")[:100]
