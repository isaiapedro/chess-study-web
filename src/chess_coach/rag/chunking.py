from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from chess_coach.features import THEME_KEYWORDS


@dataclass
class TextChunk:
    chunk_id: str
    text: str
    book: str
    chapter: str
    themes: list[str]
    source_path: str
    book_patterns: list[str] = field(default_factory=list)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return "\n".join(pages)
    raise ValueError(f"Unsupported book format: {path}")


def resolve_sidecar(path: Path) -> Path | None:
    direct = path.with_suffix(path.suffix + ".themes.yaml")
    if direct.exists():
        return direct
    same_stem = path.with_suffix(".themes.yaml")
    if same_stem.exists():
        return same_stem

    stem_slug = _slug(path.stem)
    candidates: list[tuple[int, Path]] = []
    for sidecar in path.parent.glob("*.themes.yaml"):
        name = sidecar.name
        if name.endswith(".themes.themes.yaml"):
            key = name[: -len(".themes.themes.yaml")]
        elif name.endswith(".themes.yaml"):
            key = name[: -len(".themes.yaml")]
        else:
            continue
        key_slug = _slug(key)
        if not key_slug:
            continue
        if stem_slug == key_slug or stem_slug.startswith(key_slug) or key_slug in stem_slug:
            candidates.append((len(key_slug), sidecar))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _load_sidecar(path: Path) -> dict:
    sidecar = resolve_sidecar(path)
    if sidecar and sidecar.exists():
        with sidecar.open(encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    return {}


def detect_themes(text: str, extra: list[str] | None = None) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for theme, keywords in THEME_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            found.append(theme)
    for theme in extra or []:
        if theme not in found:
            found.append(theme)
    return found


def _chunk_id(source_path: str, index: int) -> str:
    digest = hashlib.sha1(source_path.encode("utf-8")).hexdigest()[:12]
    return f"{digest}-{index}"


def _split_oversized(text: str, max_chars: int) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            window = text[start:end]
            split_at = max(window.rfind("\n"), window.rfind(". "), window.rfind(" "))
            if split_at > max_chars // 3:
                end = start + split_at + 1
        piece = text[start:end].strip()
        if piece:
            parts.append(piece)
        if end <= start:
            end = start + max_chars
        start = end
    return parts


def chunk_text(
    text: str,
    *,
    book: str,
    source_path: str,
    max_chars: int = 1800,
    overlap_chars: int = 200,
    extra_themes: list[str] | None = None,
    book_patterns: list[str] | None = None,
) -> list[TextChunk]:
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text.strip()] if text.strip() else []
    # PDF extracts often lack blank lines — also split on single newlines when huge
    normalized: list[str] = []
    for para in paragraphs:
        if len(para) > max_chars * 2 and "\n" in para:
            normalized.extend(p.strip() for p in para.split("\n") if p.strip())
        else:
            normalized.append(para)
    paragraphs = normalized

    chunks: list[TextChunk] = []
    buffer = ""
    chapter = "body"
    index = 0

    declared = list(book_patterns or [])

    def emit(body: str) -> None:
        nonlocal index
        for piece in _split_oversized(body, max_chars):
            themes = detect_themes(piece, extra_themes)
            chunks.append(
                TextChunk(
                    chunk_id=_chunk_id(source_path, index),
                    text=piece,
                    book=book,
                    chapter=chapter,
                    themes=themes,
                    source_path=source_path,
                    book_patterns=declared,
                )
            )
            index += 1

    for para in paragraphs:
        heading = re.match(r"^(chapter\s+\d+|part\s+\d+)[:.\s-]*(.*)$", para, re.I)
        if heading and len(para) < 120:
            chapter = para.split("\n", 1)[0][:80]
        candidate = f"{buffer}\n\n{para}".strip() if buffer else para
        if len(candidate) <= max_chars:
            buffer = candidate
            continue
        if buffer:
            emit(buffer)
            overlap = buffer[-overlap_chars:] if overlap_chars and len(buffer) > overlap_chars else ""
            buffer = f"{overlap}\n\n{para}".strip() if overlap else para
            if len(buffer) > max_chars:
                emit(buffer)
                buffer = ""
        else:
            emit(para)
            buffer = ""
    if buffer.strip():
        emit(buffer)
    return chunks


def sidecar_patterns(meta: dict) -> list[str]:
    raw = meta.get("patterns") or meta.get("ontology_patterns") or []
    if isinstance(raw, str):
        return [p.strip() for p in raw.split(",") if p.strip()]
    return [str(p).strip() for p in raw if str(p).strip()]


def load_book_chunks(path: Path, max_chars: int = 1800, overlap_chars: int = 200) -> list[TextChunk]:
    meta = _load_sidecar(path)
    book = meta.get("book") or re.sub(r"\s+", " ", path.stem.split("(")[0]).strip()
    if not book:
        book = path.stem
    text = extract_text(path)
    extra = meta.get("themes") if isinstance(meta.get("themes"), list) else None
    return chunk_text(
        text,
        book=book,
        source_path=str(path),
        max_chars=max_chars,
        overlap_chars=overlap_chars,
        extra_themes=[str(t) for t in (extra or [])],
        book_patterns=sidecar_patterns(meta),
    )
