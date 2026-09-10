from __future__ import annotations

from chess_coach.rag.offline_llm_comments import (
    build_llm_moment_payload,
    comment_is_concrete,
    generate_coach_comments,
    generate_offline_comment_notes,
    generalize_comment,
    stitch_fallback,
)


def test_build_llm_moment_payload():
    moment = {
        "ply": 37,
        "playedSan": "h4",
        "bestSan": "Re1",
        "severity": "blunder",
        "dropCp": 343,
        "inputs": {
            "tactical_head": "Your knight on d2 has no escape.",
            "tactical_kind": "trapped_piece",
            "tactical_self_inflicted": 1,
            "why_better": "save the knight",
            "key_id": "motif.trapped_piece",
        },
    }
    payload = build_llm_moment_payload(moment)
    assert payload["played_move"] == "h4"
    assert payload["best_move"] == "Re1"
    assert payload["tactical_kind"] == "trapped_piece"
    assert payload["tactical_head"].startswith("Your knight")
    assert payload["self_inflicted"] is True
    assert payload["drop_cp"] == 343


def test_stitch_fallback_uses_board_facts():
    text = stitch_fallback(
        {
            "played_move": "h4",
            "best_move": "Re1",
            "tactical_head": "Your knight on d2 has no escape",
        }
    )
    assert "h4" in text
    assert "knight on d2" in text
    assert "Re1" in text
    assert "forcing replies" not in text.lower()


def test_reject_generic_filler():
    assert not comment_is_concrete("Compare forcing replies before committing.")
    assert comment_is_concrete(
        "h4 leaves your knight on d2 trapped. Best was Re1."
    )


def test_generate_offline_notes_without_llm():
    data = {
        "coach": {
            "momentsByPly": {
                "37": {
                    "ply": 37,
                    "playedSan": "h4",
                    "bestSan": "Re1",
                    "severity": "blunder",
                    "dropCp": 343,
                    "inputs": {
                        "tactical_head": "Your knight on d2 has no escape.",
                        "tactical_kind": "trapped_piece",
                        "tactical_self_inflicted": True,
                        "key_id": "motif.trapped_piece",
                    },
                }
            }
        }
    }
    notes = generate_offline_comment_notes(
        data, {}, use_llm=False, game_specific=True
    )
    assert notes
    exact = next(n for n in notes if n["guards"].get("played_san") == "h4")
    assert exact["eventKinds"] == ["tactical_blunder"]
    assert exact["guards"]["tactical_kind"] == "trapped_piece"
    assert exact["text"]
    assert "h4" in exact["text"]
    pattern = next(n for n in notes if "played_san" not in n["guards"])
    assert "{playedSan}" in pattern["text"] or "h4" not in pattern["text"]


def test_generalize_replaces_sans():
    out = generalize_comment(
        "h4 leaves your knight on d2 trapped. Re1 saves it.",
        {"played_move": "h4", "best_move": "Re1", "piece": "knight", "square": "d2"},
    )
    assert "{playedSan}" in out
    assert "{bestSan}" in out
    assert "{piece}" in out
    assert "{square}" in out


def test_generate_coach_comments_stitches_without_llm():
    payloads = [
        {
            "played_move": "h4",
            "best_move": "Re1",
            "tactical_head": "Your knight on d2 has no escape",
            "task": "mistake",
        },
        {
            "played_move": "Nxf7",
            "best_move": "Nxf7",
            "tactical_head": "",
            "task": "praise",
            "mark": "brilliant",
        },
    ]
    texts = generate_coach_comments(payloads, {}, use_llm=False)
    assert len(texts) == 2
    assert "h4" in texts[0]
    assert "knight on d2" in texts[0]
    assert "Nxf7" in texts[1]
