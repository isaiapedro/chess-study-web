from chess_coach.rag.metrics_voice import (
    BOARD_METRIC_SNAP_FIELDS,
    METRIC_FIELD_SOFT_KEYS,
    STRUCTURAL_KIND_SOFT_KEYS,
    adapt_compact,
    adapt_summary,
)


def test_adapt_summary_is_directive_list():
    raw = (
        "An IQP grants space, open lines, and active piece play, "
        "but becomes a long-term target if its advance is stopped."
    )
    out = adapt_summary(
        "structure.iqp",
        raw,
        principle="Use IQP activity before simplification",
    )
    assert out.startswith("- ")
    assert "When game metrics" not in out
    assert "Kasparov" not in out
    assert "Use IQP activity" in out or "IQP" in out


def test_adapt_compact_impersonal():
    raw = (
        "A sacrifice gives up material for concrete compensation "
        "such as exposed king safety or initiative."
    )
    out = adapt_compact("motif.sacrifice", raw)
    assert out.startswith("- ")
    assert "when a sacrifice offer" not in out.lower()
    assert "compensation" in out.lower()


def test_board_metric_snap_covers_new_fields():
    assert "open_file_utilization" in BOARD_METRIC_SNAP_FIELDS
    assert "seventh_rank_infiltration" in BOARD_METRIC_SNAP_FIELDS
    assert "hanging_material_own" in BOARD_METRIC_SNAP_FIELDS
    assert "hanging_material_opponent" in BOARD_METRIC_SNAP_FIELDS
    assert "hanging_own" not in BOARD_METRIC_SNAP_FIELDS
    assert "hanging_opp" not in BOARD_METRIC_SNAP_FIELDS


def test_metric_field_soft_keys_align_new_metrics():
    assert METRIC_FIELD_SOFT_KEYS["open_file_utilization"] == [
        "piece.seventh_rank_invasion",
        "piece.coordination",
    ]
    assert METRIC_FIELD_SOFT_KEYS["seventh_rank_infiltration"] == [
        "piece.seventh_rank_invasion"
    ]
    assert METRIC_FIELD_SOFT_KEYS["hanging_material_own"] == [
        "methodology.candidate_moves"
    ]
    assert METRIC_FIELD_SOFT_KEYS["hanging_material_opponent"] == [
        "attack.initiative"
    ]
    assert "hanging_own" not in METRIC_FIELD_SOFT_KEYS
    assert "hanging_opp" not in METRIC_FIELD_SOFT_KEYS


def test_structural_kind_soft_keys_present():
    assert "opening_name" in STRUCTURAL_KIND_SOFT_KEYS
    assert "endgame_advantage" in STRUCTURAL_KIND_SOFT_KEYS
    assert "piece.seventh_rank_invasion" in STRUCTURAL_KIND_SOFT_KEYS[
        "endgame_advantage"
    ]
