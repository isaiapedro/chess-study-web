from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection

from chess_coach.ontology.tag import tag_text_patterns
from chess_coach.rag.chunking import _load_sidecar, load_book_chunks, sidecar_patterns
from chess_coach.rag.embeddings import get_embedder


def _client(persist_dir: str) -> chromadb.PersistentClient:
    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=persist_dir)


def get_collection(config: dict[str, Any]) -> Collection:
    rag = config["rag"]
    client = _client(rag["persist_dir"])
    return client.get_or_create_collection(
        name=rag.get("collection", "chess_books"),
        metadata={"hnsw:space": "cosine"},
    )


def _existing_source_counts(collection: Collection) -> dict[str, int]:
    """Map source_path -> chunk count already in the collection."""
    counts: dict[str, int] = {}
    total = collection.count()
    if total <= 0:
        return counts
    offset = 0
    page = 256
    while offset < total:
        raw = collection.get(include=["metadatas"], limit=page, offset=offset)
        ids = raw.get("ids") or []
        metas = raw.get("metadatas") or []
        if not ids:
            break
        for meta in metas:
            if not meta:
                continue
            src = str(meta.get("source_path") or "").strip()
            if not src:
                continue
            counts[src] = counts.get(src, 0) + 1
        offset += len(ids)
    return counts


def _source_keys(path: Path) -> list[str]:
    keys = [str(path)]
    try:
        resolved = str(path.resolve())
        if resolved not in keys:
            keys.append(resolved)
    except OSError:
        pass
    return keys


def _lookup_existing(counts: dict[str, int], path: Path) -> int:
    best = 0
    for key in _source_keys(path):
        best = max(best, counts.get(key, 0))
    return best


def _chunk_metadata(chunk: Any, ontology_dir: str | None) -> dict[str, Any]:
    patterns = tag_text_patterns(
        chunk.text,
        ontology_dir=ontology_dir,
        book_patterns=getattr(chunk, "book_patterns", None) or [],
    )
    return {
        "book": chunk.book,
        "chapter": chunk.chapter,
        "themes": ",".join(chunk.themes),
        "patterns": ",".join(patterns),
        "source_path": chunk.source_path,
    }


def ingest_path(
    path: Path,
    config: dict[str, Any],
    *,
    reset: bool = False,
    allow_hash_fallback: bool = False,
    force: bool = False,
) -> int:
    rag = config["rag"]
    chunk_cfg = config.get("chunk", {})
    ont_dir = (config.get("ontology") or {}).get("dir")
    if reset:
        client = _client(rag["persist_dir"])
        name = rag.get("collection", "chess_books")
        try:
            client.delete_collection(name)
        except Exception:
            pass
    collection = get_collection(config)
    embedder = get_embedder(
        config["ollama_host"],
        config["embed_model"],
        allow_fallback=allow_hash_fallback,
    )
    embedder_name = type(embedder).__name__
    print(f"Using embedder: {embedder_name}", flush=True)

    files: list[Path]
    if path.is_dir():
        files = sorted(
            [p for p in path.rglob("*") if p.suffix.lower() in {".txt", ".pdf"} and p.is_file()]
        )
    else:
        files = [path]

    existing_counts: dict[str, int] = {}
    if not force and not reset:
        print("Scanning collection for already-ingested books…", flush=True)
        existing_counts = _existing_source_counts(collection)
        print(
            f"  {sum(existing_counts.values())} chunks across {len(existing_counts)} sources",
            flush=True,
        )

    total = 0
    tagged = 0
    skipped = 0
    skipped_existing = 0
    batch_ids: list[str] = []
    batch_docs: list[str] = []
    batch_meta: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal total, batch_ids, batch_docs, batch_meta
        if not batch_ids:
            return
        try:
            print(f"  embedding {len(batch_ids)} chunks...", flush=True)
            embeddings = embedder.embed(batch_docs)
            collection.upsert(
                ids=batch_ids,
                documents=batch_docs,
                metadatas=batch_meta,
                embeddings=embeddings,
            )
        except Exception as exc:
            print(f"  ERROR upsert batch failed: {exc}", flush=True)
            raise
        total += len(batch_ids)
        print(f"  upserted batch ({len(batch_ids)} chunks, total={total})", flush=True)
        batch_ids, batch_docs, batch_meta = [], [], []

    for idx, file_path in enumerate(files, start=1):
        print(f"[{idx}/{len(files)}] extracting {file_path.name}", flush=True)
        try:
            chunks = load_book_chunks(
                file_path,
                max_chars=int(chunk_cfg.get("max_chars", 1800)),
                overlap_chars=int(chunk_cfg.get("overlap_chars", 200)),
            )
        except Exception as exc:
            print(f"  SKIP extract error: {exc}", flush=True)
            skipped += 1
            continue
        total_chars = sum(len(c.text) for c in chunks)
        if total_chars < 400 or not chunks:
            print(f"  SKIP empty/scanned extract ({total_chars} chars, {len(chunks)} chunks)", flush=True)
            skipped += 1
            continue

        have = _lookup_existing(existing_counts, file_path)
        if not force and have >= len(chunks):
            print(
                f"  SKIP already ingested ({have} chunks ≥ {len(chunks)} extracted)",
                flush=True,
            )
            skipped_existing += 1
            continue
        if have and have < len(chunks):
            print(
                f"  RESUME partial book ({have}/{len(chunks)} chunks in DB) — re-upserting",
                flush=True,
            )

        print(f"  {len(chunks)} chunks ({total_chars} chars)", flush=True)
        for chunk in chunks:
            meta = _chunk_metadata(chunk, ont_dir)
            if meta.get("patterns"):
                tagged += 1
            batch_ids.append(chunk.chunk_id)
            batch_docs.append(chunk.text)
            batch_meta.append(meta)
            if len(batch_ids) >= 8:
                flush()
    flush()
    if skipped:
        print(f"Skipped {skipped} files (empty OCR or extract errors)")
    if skipped_existing:
        print(f"Skipped {skipped_existing} files already fully ingested (use --force to re-embed)")
    print(f"Pattern-tagged chunks: {tagged}/{total}", flush=True)
    return total


def retag_patterns(config: dict[str, Any], *, batch_size: int = 64) -> tuple[int, int]:
    """
    Rewrite `patterns` metadata on existing Chroma docs (no re-embed).
    Returns (updated, total_seen).
    """
    ont_dir = (config.get("ontology") or {}).get("dir")
    collection = get_collection(config)
    total = collection.count()
    if total == 0:
        return 0, 0
    updated = 0
    offset = 0
    print(f"Retagging {total} chunks with ontology patterns...", flush=True)
    while offset < total:
        raw = collection.get(
            include=["documents", "metadatas"],
            limit=batch_size,
            offset=offset,
        )
        ids = raw.get("ids") or []
        docs = raw.get("documents") or []
        metas = raw.get("metadatas") or []
        if not ids:
            break
        new_metas: list[dict[str, Any]] = []
        for doc, meta in zip(docs, metas):
            meta = dict(meta or {})
            book_patterns: list[str] = []
            src = str(meta.get("source_path") or "")
            if src:
                try:
                    book_patterns = sidecar_patterns(_load_sidecar(Path(src)))
                except OSError:
                    book_patterns = []
            patterns = tag_text_patterns(
                doc or "", ontology_dir=ont_dir, book_patterns=book_patterns
            )
            meta["patterns"] = ",".join(patterns)
            if patterns:
                updated += 1
            new_metas.append(meta)
        collection.update(ids=ids, metadatas=new_metas)
        offset += len(ids)
        print(f"  retagged {min(offset, total)}/{total} (pattern hits so far={updated})", flush=True)
    return updated, total
