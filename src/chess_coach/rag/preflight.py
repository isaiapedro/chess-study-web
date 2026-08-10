from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from pypdf import PdfReader

from chess_coach.rag.chunking import detect_themes, resolve_sidecar
from chess_coach.rag.embeddings import OllamaEmbedder


@dataclass
class BookCheck:
    path: Path
    pages: int | None
    sample_chars: int
    estimated_chunks: int
    themes_sample: list[str]
    sidecar: str | None
    book_title: str
    ok: bool
    notes: list[str]


def list_book_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    return sorted(p for p in path.rglob("*") if p.suffix.lower() in {".txt", ".pdf"} and p.is_file())


def sample_extract(path: Path, max_pages: int = 8, max_chars: int = 12000) -> tuple[str, int | None]:
    if path.suffix.lower() == ".txt":
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:max_chars], None
    reader = PdfReader(str(path))
    pages = len(reader.pages)
    parts: list[str] = []
    for page in reader.pages[:max_pages]:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)[:max_chars], pages


def check_ollama(host: str, embed_model: str, chat_model: str | None = None) -> list[str]:
    notes: list[str] = []
    host = host.rstrip("/")
    try:
        with httpx.Client(timeout=30.0) as client:
            tags = client.get(f"{host}/api/tags")
            tags.raise_for_status()
            names = {m.get("name", "") for m in tags.json().get("models", [])}
            bare = {n.split(":")[0] for n in names}
            embed_ok = embed_model in names or embed_model.split(":")[0] in bare
            if not embed_ok:
                notes.append(f"FAIL embed model missing: {embed_model}. Run: ollama pull {embed_model}")
            else:
                embedder = OllamaEmbedder(host, embed_model)
                vec = embedder.embed(["chess isolated queen pawn"])[0]
                notes.append(f"OK embed model {embed_model} dims={len(vec)}")
            if chat_model:
                chat_ok = chat_model in names or chat_model.split(":")[0] in bare
                if not chat_ok:
                    notes.append(f"WARN chat model missing: {chat_model}. Run: ollama pull {chat_model}")
                else:
                    notes.append(f"OK chat model present: {chat_model}")
    except Exception as exc:
        notes.append(f"FAIL ollama unreachable at {host}: {exc}")
    return notes


def check_book(path: Path, chunk_cfg: dict[str, Any]) -> BookCheck:
    notes: list[str] = []
    try:
        sample, pages = sample_extract(path)
    except Exception as exc:
        return BookCheck(
            path=path,
            pages=None,
            sample_chars=0,
            estimated_chunks=0,
            themes_sample=[],
            sidecar=None,
            book_title=path.stem,
            ok=False,
            notes=[f"extract failed: {exc}"],
        )

    sidecar_path = resolve_sidecar(path)
    meta = {}
    if sidecar_path and sidecar_path.exists():
        import yaml

        with sidecar_path.open(encoding="utf-8") as handle:
            meta = yaml.safe_load(handle) or {}
    book_title = meta.get("book") or path.stem.split("(")[0].strip()[:80]
    themes = detect_themes(sample)
    alpha = sum(1 for c in sample if c.isalpha())
    density = alpha / max(len(sample), 1)

    if len(sample.strip()) < 200:
        notes.append("likely scanned/empty OCR — extract almost empty")
    elif density < 0.45:
        notes.append("low text density — possible bad OCR or diagram-heavy pages")
    else:
        notes.append("text extract looks usable")

    if sidecar_path:
        notes.append(f"sidecar matched: {sidecar_path.name}")
    else:
        notes.append("no sidecar (themes from text only)")

    max_chars = int(chunk_cfg.get("max_chars", 700))
    if pages:
        estimated = max(1, int(pages * 1800 / max(max_chars, 1)))
    else:
        estimated = max(1, len(sample) // max(max_chars // 2, 1)) if sample else 0

    ok = len(sample.strip()) >= 200 and density >= 0.35
    return BookCheck(
        path=path,
        pages=pages,
        sample_chars=len(sample),
        estimated_chunks=estimated,
        themes_sample=themes[:8],
        sidecar=sidecar_path.name if sidecar_path else None,
        book_title=book_title,
        ok=ok,
        notes=notes,
    )


def run_preflight(
    path: Path,
    config: dict[str, Any],
    *,
    limit: int | None = None,
) -> tuple[list[str], list[BookCheck]]:
    ollama_notes = check_ollama(
        config["ollama_host"],
        config["embed_model"],
        config.get("chat_model"),
    )
    files = list_book_files(path)
    if limit is not None:
        files = files[:limit]
    chunk_cfg = config.get("chunk", {})
    checks = [check_book(file_path, chunk_cfg) for file_path in files]
    return ollama_notes, checks


def format_preflight_report(ollama_notes: list[str], checks: list[BookCheck]) -> str:
    lines = ["# Chess Coach Preflight", "", "## Ollama", ""]
    lines.extend(f"- {n}" for n in ollama_notes)
    lines.extend(["", "## Books", ""])
    ok_n = sum(1 for c in checks if c.ok)
    est = sum(max(c.estimated_chunks, 0) for c in checks)
    lines.append(
        f"Checked {len(checks)} files — {ok_n} OK, {len(checks) - ok_n} need attention. Est. chunks≈{est}."
    )
    lines.append("")
    for check in checks:
        mark = "OK" if check.ok else "BAD"
        pages = f"{check.pages}p" if check.pages is not None else "txt"
        lines.append(
            f"- [{mark}] `{check.path.name}` | {pages} | sample={check.sample_chars}c | chunks≈{check.estimated_chunks} | sidecar={check.sidecar or '-'}"
        )
        if check.themes_sample:
            lines.append(f"  themes: {', '.join(check.themes_sample)}")
        for note in check.notes:
            lines.append(f"  - {note}")
    lines.extend(
        [
            "",
            "## Before full ingest",
            "1. Fix BAD books (OCR / export to `.txt` if PDF extract empty).",
            "2. Confirm Ollama embed line says OK with dims (real embeddings).",
            "3. Pilot one book first:",
            "   `chess-coach ingest \"data/books/Logical Chess....pdf\" --reset`",
            "4. Spot-check retrieve, then full archive:",
            "   `chess-coach ingest data/books --reset`",
            "",
        ]
    )
    return "\n".join(lines)
