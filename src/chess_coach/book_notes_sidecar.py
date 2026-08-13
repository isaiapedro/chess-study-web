"""
Curated book-note sidecars (`*.book_notes.yaml`).

Production book voice prefers these over live PDF extract. Format:

```yaml
source: curated   # or draft
source_book: "Chess Structures …"
chapter: "Family 4"
preamble: "Learning objective: …"
notes:
  - fullmove: 8
    side: black
    san: Bd6
    text: "This opening imprecision…"
```
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chess.pgn
import yaml

from chess_coach.chapter import BookMoveNote, GameCitation

BOOK_TAG_RE = re.compile(
    r"^\[Book:(?:(?P<kind>curated|draft)\|)?(?P<title>[^\]]*)\]\s*",
    re.I,
)


@dataclass
class BookNotesSidecar:
    source: str  # curated | draft
    source_book: str
    chapter: str = ""
    preamble: str = ""
    notes: list[BookMoveNote] = field(default_factory=list)
    path: Path | None = None

    @property
    def is_curated(self) -> bool:
        return (self.source or "").lower() == "curated"


def sidecar_path_for_pgn(pgn_path: Path) -> Path:
    """``Foo_bookwalk.pgn`` → ``Foo_bookwalk.book_notes.yaml``."""
    return pgn_path.with_name(pgn_path.stem + ".book_notes.yaml")


def resolve_sidecar(pgn_path: Path) -> Path | None:
    path = sidecar_path_for_pgn(pgn_path)
    return path if path.is_file() else None


def book_tag_prefix(source_book: str, *, kind: str) -> str:
    title = (source_book or "Book").strip() or "Book"
    kind = (kind or "draft").lower()
    if kind not in {"curated", "draft"}:
        kind = "draft"
    return f"[Book:{kind}|{title}] "


def parse_book_kind(book_chunk: str) -> tuple[str, str]:
    """
    Return ``(kind, remainder)`` where kind is curated|draft|legacy.
    ``remainder`` still includes ``[Book:…]`` for downstream cleaners.
    """
    text = (book_chunk or "").strip()
    m = BOOK_TAG_RE.match(text)
    if not m:
        if text.startswith("[Book"):
            return "legacy", text
        return "none", text
    kind = (m.group("kind") or "legacy").lower()
    if kind not in {"curated", "draft"}:
        kind = "legacy"
    return kind, text


def load_sidecar(path: Path) -> BookNotesSidecar:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    notes: list[BookMoveNote] = []
    for row in raw.get("notes") or []:
        if not isinstance(row, dict):
            continue
        text = str(row.get("text") or "").strip()
        if not text:
            continue
        notes.append(
            BookMoveNote(
                fullmove=int(row.get("fullmove") or 0),
                side=str(row.get("side") or "white").lower(),
                san_hint=str(row.get("san") or row.get("san_hint") or ""),
                text=text,
            )
        )
    return BookNotesSidecar(
        source=str(raw.get("source") or "curated").lower(),
        source_book=str(raw.get("source_book") or ""),
        chapter=str(raw.get("chapter") or ""),
        preamble=str(raw.get("preamble") or ""),
        notes=notes,
        path=path,
    )


def save_sidecar(path: Path, data: BookNotesSidecar) -> Path:
    payload: dict[str, Any] = {
        "source": data.source,
        "source_book": data.source_book,
        "chapter": data.chapter,
        "preamble": data.preamble,
        "notes": [
            {
                "fullmove": n.fullmove,
                "side": n.side,
                "san": n.san_hint,
                "text": n.text,
            }
            for n in data.notes
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def citation_from_sidecar(sidecar: BookNotesSidecar) -> GameCitation:
    return GameCitation(
        white="",
        black="",
        year=0,
        event="",
        context="",
        notes=list(sidecar.notes),
        preamble=sidecar.preamble,
        source_book=sidecar.source_book,
        chapter=sidecar.chapter,
    )


def export_sidecar_from_game(
    game: chess.pgn.Game,
    *,
    source: str = "curated",
    source_book: str = "",
    chapter: str = "",
) -> BookNotesSidecar:
    """Pull existing ``[Book:]`` layers off a PGN into a sidecar."""
    from chess_coach.viewer import _split_layers

    book_hdr = source_book or game.headers.get("Annotator", "")
    book_hdr = re.sub(r"^Book:\s*", "", book_hdr)
    book_hdr = re.sub(r"\s*\+\s*Stockfish.*$", "", book_hdr).strip()
    ch = chapter or game.headers.get("BookChapter", "")

    preamble = ""
    start_book, _, _, _ = _split_layers(game.comment or "")
    if start_book:
        preamble = start_book.strip()

    notes: list[BookMoveNote] = []
    board = game.board()
    node: chess.pgn.GameNode = game
    while node.variations:
        nxt = node.variation(0)
        san = board.san(nxt.move)
        fullmove = board.fullmove_number
        side = "white" if board.turn == chess.WHITE else "black"
        book, _, _, _ = _split_layers(nxt.comment or "")
        board.push(nxt.move)
        node = nxt
        if not book:
            continue
        text = book.strip()
        if not text:
            continue
        notes.append(
            BookMoveNote(
                fullmove=fullmove,
                side=side,
                san_hint=san.rstrip("?!+#"),
                text=text,
            )
        )
    return BookNotesSidecar(
        source=source,
        source_book=book_hdr or source_book,
        chapter=ch,
        preamble=preamble,
        notes=notes,
    )


def merge_citation_with_sidecar(
    citation: GameCitation,
    sidecar: BookNotesSidecar | None,
) -> tuple[GameCitation, str]:
    """
    Prefer curated/draft sidecar notes when present.

    Returns ``(citation, kind)`` with kind curated|draft|extract.
    """
    if sidecar is None or not sidecar.notes:
        return citation, "extract"
    kind = "curated" if sidecar.is_curated else "draft"
    merged = GameCitation(
        white=citation.white,
        black=citation.black,
        year=citation.year,
        event=citation.event,
        context=citation.context,
        notes=list(sidecar.notes),
        preamble=sidecar.preamble or citation.preamble,
        source_book=sidecar.source_book or citation.source_book,
        chapter=sidecar.chapter or citation.chapter,
        offset=citation.offset,
    )
    return merged, kind
