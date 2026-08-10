from __future__ import annotations

from pathlib import Path

import yaml

from chess_coach.chapter import list_book_sections


def slug_for_book(path: Path) -> str:
    stem = path.stem.split("(")[0].strip()
    import re

    return re.sub(r"[^a-z0-9]+", "_", stem.lower()).strip("_") or path.stem.lower()


def detect_and_write_sections_yaml(
    book_path: Path,
    *,
    force: bool = False,
    min_body_chars: int = 800,
) -> Path | None:
    """
    Auto-detect section scheme for a book and write <slug>.sections.yaml.
    Returns path written, or None if nothing useful detected.
    """
    slug = slug_for_book(book_path)
    out = book_path.parent / f"{slug}.sections.yaml"
    if out.exists() and not force:
        return out

    sections = list_book_sections(book_path, scheme=None, min_body_chars=min_body_chars)
    if not sections:
        # try lower threshold once for sparse OCR books
        sections = list_book_sections(book_path, scheme=None, min_body_chars=400)
    if not sections:
        return None

    scheme = sections[0].scheme
    numbers = [s.number for s in sections if s.number is not None]
    payload = {
        "book": book_path.stem.split("(")[0].strip().replace("_", " "),
        "section_scheme": scheme,
        "sections": {
            "scheme": scheme,
            "min_body_chars": min_body_chars,
            "detected_count": len(sections),
            "number_range": [min(numbers), max(numbers)] if numbers else None,
        },
    }
    out.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return out


def init_sections_for_dir(
    books_dir: Path,
    *,
    force: bool = False,
    min_body_chars: int = 800,
) -> list[tuple[Path, Path | None, str]]:
    results: list[tuple[Path, Path | None, str]] = []
    files = sorted(
        p for p in books_dir.iterdir() if p.suffix.lower() in {".pdf", ".txt"} and p.is_file()
    )
    for book in files:
        try:
            path = detect_and_write_sections_yaml(
                book,
                force=force,
                min_body_chars=min_body_chars,
            )
            if path is None:
                results.append((book, None, "no sections detected"))
            else:
                results.append((book, path, "ok"))
        except Exception as exc:
            results.append((book, None, f"error: {exc}"))
    return results
