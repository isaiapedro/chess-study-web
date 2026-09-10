from __future__ import annotations

from pathlib import Path

from chess_coach.rag.export_mobile_pack import build_mobile_pack, write_mobile_pack_ts


def test_build_mobile_pack_canon_notes(tmp_path):
    config = {
        "rag": {
            "persist_dir": str(tmp_path / "chroma"),
            "key_summaries_dir": str(tmp_path / "key_summaries"),
            "summaries_dir": str(tmp_path / "empty_summaries"),
            "key_summaries_collection": "chess_knowledge_key_summaries",
            "summaries_collection": "chess_knowledge_summaries",
        },
        "masters": {"enabled": False},
        "ollama_host": "http://localhost:11434",
        "embed_model": "nomic-embed-text",
    }

    pack = build_mobile_pack(
        config,
        max_entries=10,
        attach_frequent_lines=False,
        attach_bookwalk=False,
        source="key",
    )
    assert pack["source"] in {"key", "gpt-book-notes", "gpt-book-notes+bookwalk"}
    assert pack["entryCount"] >= 1
    entry = pack["entries"][0]
    assert entry.get("keyId")
    assert entry.get("notes")
    assert len(entry["notes"]) >= 1
    assert entry["notes"][0]["text"]

    ts_out = tmp_path / "derivedCoachPack.ts"
    write_mobile_pack_ts(pack, ts_out)
    body = ts_out.read_text(encoding="utf-8")
    assert "keyId?" in body
