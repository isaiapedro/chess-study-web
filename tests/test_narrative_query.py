from chess_coach.features import PositionFeatures, build_narrative_query, narrative_seed_for_key


def test_tactical_query_text_is_narrative():
    features = PositionFeatures(
        phase="endgame",
        played_san="Nd2",
        best_san="Re1",
        drop_cp=220,
        tactical_kind="trapped_piece",
        piece_label="knight",
        trap_square="d2",
        stm="w",
    )
    query = features.query_text()
    assert "Themes:" not in query
    assert "typical moves" not in query.lower()
    assert "Nd2" in query
    assert "Re1" in query
    assert "d2" in query


def test_opening_query_text_is_plan():
    features = PositionFeatures(
        phase="opening",
        opening="Sicilian Defence",
        eco="B90",
        played_san="Qd4",
        best_san="Nc3",
        stm="w",
    )
    query = build_narrative_query(features)
    assert "Sicilian" in query
    assert "opening plan" in query.lower()
    assert "Themes:" not in query


def test_narrative_seed_for_motif_key():
    seed = narrative_seed_for_key("motif.trapped_piece")
    assert "Tactical motif" in seed
    opening = narrative_seed_for_key(
        "opening.sicilian", opening="Sicilian Defence", eco="B90"
    )
    assert "Sicilian" in opening
    endgame = narrative_seed_for_key("endgame.strategic.active_king")
    assert "Endgame technique" in endgame
