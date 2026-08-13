"""
Draft book notes from PDF/text extract — review queue only.

Does not write production PGNs. Optional PyMuPDF font-glyph path when installed.
"""

from __future__ import annotations

import re
from pathlib import Path

from chess_coach.book_notes_sidecar import BookNotesSidecar, save_sidecar
from chess_coach.chapter import extract_citations
from chess_coach.logutil import log


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _read_book_text(book_path: Path, *, use_font_glyphs: bool) -> str:
    if book_path.suffix.lower() in {".txt", ".md"}:
        return book_path.read_text(encoding="utf-8", errors="replace")
    if use_font_glyphs:
        try:
            import fitz  # type: ignore

            from chess_coach.pdf_font_glyphs import extract_page_text_with_font_glyphs

            doc = fitz.open(book_path)
            parts: list[str] = []
            for page in doc:
                parts.append(extract_page_text_with_font_glyphs(page))
            doc.close()
            text = "\n".join(parts)
            if text.strip():
                log("Draft extract via PyMuPDF font glyphs (%d chars)", len(text))
                return text
        except Exception as exc:
            log("Font-glyph extract unavailable (%s) — falling back to pypdf", exc)
    from pypdf import PdfReader

    reader = PdfReader(str(book_path))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def draft_chapter_book_notes(
    book_path: Path,
    *,
    chapter: str,
    out_dir: Path,
    use_font_glyphs: bool = False,
) -> list[Path]:
    """
    Write one draft sidecar per citation in the chapter.

    Filenames: ``{white}_vs_{black}_{year}.book_notes.yaml`` under ``out_dir``.
    """
    from chess_coach.chapter import select_chapter, _load_book_section_config

    text = _read_book_text(book_path, use_font_glyphs=use_font_glyphs)
    cfg = _load_book_section_config(book_path)
    scheme = cfg.get("section_scheme") or (cfg.get("sections") or {}).get("scheme")
    custom = None
    sections_cfg = cfg.get("sections") if isinstance(cfg.get("sections"), dict) else {}
    min_body = 800
    if isinstance(sections_cfg, dict):
        custom = sections_cfg.get("pattern")
        min_body = int(sections_cfg.get("min_body_chars", min_body))
        scheme = scheme or sections_cfg.get("scheme")
    custom = custom or cfg.get("section_pattern")
    try:
        ch_label, body = select_chapter(
            text,
            chapter,
            scheme=scheme,
            custom_pattern=custom,
            min_body_chars=min_body,
        )
    except Exception as exc:
        log("select_chapter fallback (%s)", exc)
        ch_label, body = str(chapter), text
    book_title = cfg.get("book") or book_path.stem.split("(")[0].strip()

    citations = extract_citations(body, book=book_title, chapter=ch_label)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for cite in citations:
        stem = f"{cite.white}_vs_{cite.black}_{cite.year}".replace(" ", "_")
        path = out_dir / f"{stem}.book_notes.yaml"
        data = BookNotesSidecar(
            source="draft",
            source_book=cite.source_book or book_title,
            chapter=cite.chapter or ch_label,
            preamble=cite.preamble or "",
            notes=list(cite.notes),
            path=path,
        )
        save_sidecar(path, data)
        written.append(path)
        log("Draft sidecar %s (%d notes)", path.name, len(data.notes))
    return written
