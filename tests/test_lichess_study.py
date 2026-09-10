from __future__ import annotations

import io
from urllib.parse import parse_qs

import chess.pgn
import httpx
import pytest

from chess_coach.lichess_study import LichessStudyClient, normalize_pgn_for_lichess


def _game(pgn: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(io.StringIO(pgn))
    assert game is not None
    assert not game.errors
    return game


def test_normalize_pgn_preserves_the_complete_nested_variation_tree() -> None:
    raw = """[Event \"Variation tree\"]
[Result \"*\"]

1. e4 e5 2. Nf3 Nc6 (2... Nf6 3. Nxe5 (3. Bc4 Bc5) 3... d6) 3. Bb5 a6
(3... Nf6 4. O-O Nxe4 (4... Be7 5. Re1)) 4. Ba4 Nf6 *
"""

    normalized = normalize_pgn_for_lichess(raw)
    game = _game(normalized)

    assert "2... Nf6 3. Nxe5 ( 3. Bc4 Bc5 ) 3... d6" in normalized
    assert "3... Nf6 4. O-O Nxe4 ( 4... Be7 5. Re1 )" in normalized

    e4 = game.variation(0)
    e5 = e4.variation(0)
    nf3 = e5.variation(0)
    assert [child.san() for child in nf3.variations] == ["Nc6", "Nf6"]

    nc6 = nf3.variation(0)
    bb5 = nc6.variation(0)
    assert [child.san() for child in bb5.variations] == ["a6", "Nf6"]
    o_o = bb5.variation(1).variation(0)
    assert [child.san() for child in o_o.variations] == ["Nxe4", "Be7"]


def test_normalize_pgn_rejects_a_tree_that_would_be_truncated_by_lichess() -> None:
    raw = """[Event \"Broken variation\"]

1. e4 e5 (1... e6 2. e4) 2. Nf3 *
"""

    with pytest.raises(ValueError, match="invalid move or variation"):
        normalize_pgn_for_lichess(raw)


def test_study_upload_sends_the_canonical_full_tree() -> None:
    raw = """[Event \"Canonical upload\"]

1. e4 e5 2. Nf3 Nc6 (2... Nf6 3. Nxe5 (3. Bc4 Bc5) 3... d6) 3. Bb5 *
"""
    seen: dict[str, str] = {}

    def respond(request: httpx.Request) -> httpx.Response:
        seen.update({key: values[-1] for key, values in parse_qs(request.content.decode()).items()})
        return httpx.Response(200, json={"chapters": [{"id": "chapter", "name": "Canonical upload"}]})

    client = LichessStudyClient("token")
    client._client.close()
    client._client = httpx.Client(transport=httpx.MockTransport(respond), base_url="https://lichess.org")
    try:
        chapters, error = client.import_pgn("study-id", raw, name="Canonical upload")
    finally:
        client.close()

    assert error is None
    assert chapters[0].id == "chapter"
    uploaded = _game(seen["pgn"])
    nf3 = uploaded.variation(0).variation(0).variation(0)
    assert [child.san() for child in nf3.variations] == ["Nc6", "Nf6"]
