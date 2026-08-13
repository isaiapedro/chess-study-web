from __future__ import annotations

from pathlib import Path

from chess_coach.rag.synthesize_annotated import extract_chunks_from_pgn


def test_extract_chunks_prefers_curated_yaml():
    root = Path(__file__).resolve().parents[2]
    pgn = root / "data/annotated/bookwalk/Bouaziz_vs_Beliavsky_1987_bookwalk.pgn"
    if not pgn.is_file():
        return
    chunks = extract_chunks_from_pgn(pgn)
    assert chunks, "expected annotated plies"
    assert any(c.metadata.get("quality") == "curated" for c in chunks)
    assert all(c.metadata.get("fen_key") for c in chunks)
    assert all(len(c.text) <= 400 for c in chunks)
