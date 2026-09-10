from __future__ import annotations

from pathlib import Path

from chess_coach.rag.bookwalk_passages import (
    extract_passages_from_pgn,
    load_bookwalk_passages,
    passage_to_note,
    passages_by_key,
)
from chess_coach.rag.export_mobile_pack import build_mobile_pack


ROOT = Path(__file__).resolve().parents[1]
BOOKWALK = ROOT / "data" / "annotated" / "bookwalk"
BOUAZIZ = BOOKWALK / "Bouaziz_vs_Beliavsky_1987_bookwalk.pgn"


def test_extract_bouaziz_has_fen_locked_sections():
    assert BOUAZIZ.is_file()
    passages = extract_passages_from_pgn(BOUAZIZ)
    assert passages, "expected book sections from Bouaziz bookwalk"
    hit = passages[0]
    assert hit.fen
    assert hit.san
    assert hit.san_line
    assert len(hit.text) >= 40
    assert hit.key_ids
    assert " " in hit.fen  # full FEN


def test_load_bookwalk_index_nonempty():
    passages = load_bookwalk_passages(BOOKWALK)
    assert len(passages) >= 5
    by_key = passages_by_key(passages)
    assert by_key
    # at least one note carries fens when converted
    kid, rows = next(iter(by_key.items()))
    note = passage_to_note(rows[0], kid, 0)
    assert note["fens"]
    assert note["sanLines"]
    assert note["id"].startswith("bookwalk:")


def test_build_pack_attaches_bookwalk_fens(tmp_path):
    config = {
        "rag": {
            "persist_dir": str(tmp_path / "chroma"),
            "key_summaries_dir": str(tmp_path / "empty_key"),
            "summaries_dir": str(tmp_path / "empty_summaries"),
            "key_ideas_dir": str(ROOT / "data" / "knowledge_key_ideas"),
            "key_summaries_collection": "chess_knowledge_key_summaries",
            "summaries_collection": "chess_knowledge_summaries",
        },
        "masters": {"enabled": False},
        "ollama_host": "http://localhost:11434",
        "embed_model": "nomic-embed-text",
    }
    pack = build_mobile_pack(
        config,
        max_entries=80,
        attach_frequent_lines=False,
        attach_bookwalk=True,
        bookwalk_dir=BOOKWALK,
        source="key",
    )
    assert pack["version"] >= 6
    fen_notes = 0
    for entry in pack["entries"]:
        for note in entry.get("notes") or []:
            if note.get("fens") and str(note.get("id") or "").startswith("bookwalk:"):
                fen_notes += 1
    assert fen_notes >= 1, "pack should include FEN-locked bookwalk notes"


def test_pack_coverage_bookwalk_and_gpt_fens(tmp_path):
    from chess_coach.rag.export_mobile_pack import build_mobile_pack

    config = {
        "rag": {
            "persist_dir": str(tmp_path / "chroma"),
            "key_summaries_dir": str(tmp_path / "empty_key"),
            "summaries_dir": str(tmp_path / "empty_summaries"),
            "key_ideas_dir": str(ROOT / "data" / "knowledge_key_ideas"),
            "key_summaries_collection": "chess_knowledge_key_summaries",
            "summaries_collection": "chess_knowledge_summaries",
        },
        "masters": {"enabled": False},
        "ollama_host": "http://localhost:11434",
        "embed_model": "nomic-embed-text",
    }
    from chess_coach.rag.bookwalk_passages import load_bookwalk_passages, passage_fingerprint

    passages = load_bookwalk_passages(BOOKWALK)
    pack = build_mobile_pack(
        config,
        max_entries=80,
        attach_frequent_lines=False,
        attach_bookwalk=True,
        bookwalk_dir=BOOKWALK,
        source="key",
    )
    extracted_fps = {passage_fingerprint(p) for p in passages}
    # fen|text head used when attaching orphans
    extracted_alt = {f"{p.fen}|{p.text[:96]}" for p in passages}

    in_pack = set()
    gpt_total = gpt_fen = 0
    for e in pack["entries"]:
        for n in e.get("notes") or []:
            nid = str(n.get("id") or "")
            if nid.startswith("bookwalk:"):
                fens = n.get("fens") or []
                in_pack.add(f"{fens[0] if fens else ''}|{(n.get('text') or '')[:96]}")
            else:
                gpt_total += 1
                if n.get("fens"):
                    gpt_fen += 1

    retained = len(in_pack & extracted_alt)
    rate = retained / max(1, len(extracted_alt))
    assert rate >= 0.90, f"bookwalk retention {rate:.2%} retained={retained}/{len(extracted_alt)}"
    assert gpt_total > 0
    assert gpt_fen == gpt_total, f"gpt fen coverage {gpt_fen}/{gpt_total}"
