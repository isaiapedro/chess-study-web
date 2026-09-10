from __future__ import annotations

from types import SimpleNamespace

from chess_coach.ontology.load import load_ontology
from chess_coach.rag.key_bucket_summarize import (
    SoftKey,
    build_key_buckets,
    extract_soft_keys,
    write_key_buckets,
)


def test_ontology_has_new_taxonomy_families():
    load_ontology.cache_clear()
    ont = load_ontology()
    assert "structure.carlsbad" in ont
    assert "structure.scheveningen" in ont
    assert "positional.prophylaxis" in ont
    assert "piece.blockade" in ont
    assert "attack.greek_gift" in ont
    assert "endgame.theoretical.lucena" in ont
    assert "endgame.strategic.tarrasch_rule" in ont
    assert "opening.sicilian" in ont
    assert "opening.london_system" in ont
    assert "methodology.candidate_moves" in ont
    assert "opening.sicilian_najdorf" not in ont
    assert len(ont) >= 55


def test_extract_soft_keys_opening_structure_and_motif():
    text = (
        "In the Sicilian Najdorf, look for a pawn break and piece activity. "
        "An isolani can appear after exchanges. A sacrifice may seize the initiative."
    )
    keys = extract_soft_keys(
        text,
        themes=["sicilian", "isolated queen pawn", "carlsbad"],
        patterns=["opening.sicilian", "structure.iqp"],
        eco_hints=["B90", "B92"],
    )
    ids = {k.key_id for k in keys}
    assert "opening.sicilian" in ids
    assert "structure.iqp" in ids
    assert "structure.carlsbad" in ids
    assert "eco.b" in ids
    assert "motif.sacrifice" in ids or "positional.pawn_break" in ids


def test_build_key_buckets_appends_same_chunk_under_multiple_keys(tmp_path):
    good = (
        "Attack the base of the pawn chain and play on the side where your chain points. "
        "When the centre is locked, improve the worst-placed piece before forcing a break. "
        "Rooks belong on open files once the structure opens. Sicilian plans often wait."
    )
    chunks = [
        SimpleNamespace(
            chunk_id="c1",
            text=good,
            book="demo",
            chapter="body",
            themes=["sicilian", "pawn chain"],
            book_patterns=[],
            source_path="demo.txt",
        ),
        SimpleNamespace(
            chunk_id="c2",
            text=good + " Minority attack ideas still matter in Carlsbad structures.",
            book="demo",
            chapter="body",
            themes=["carlsbad", "sicilian"],
            book_patterns=[],
            source_path="demo.txt",
        ),
    ]
    buckets = build_key_buckets(chunks, {"masters": {"enabled": False}}, max_chunks=None)
    assert buckets
    total_entries = sum(len(b.entries) for b in buckets.values())
    assert total_entries >= 2
    written = write_key_buckets(buckets, tmp_path)
    assert written == len(buckets)
    assert (tmp_path / "index.json").is_file()


def test_soft_key_types_cover_families():
    keys = [
        SoftKey("opening.french", "opening", "French"),
        SoftKey("structure.iqp", "structure", "IQP"),
        SoftKey("motif.sacrifice", "motif", "Sacrifice"),
        SoftKey("positional.outpost", "positional", "Outpost"),
    ]
    assert {k.key_type for k in keys} == {"opening", "structure", "motif", "positional"}
