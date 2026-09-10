from chess_coach.rag.retrieve import Passage, merge_retrieve_pools


def _p(text: str, source: str, quality: str = "") -> Passage:
    return Passage(
        text=text,
        book="book",
        chapter="ch",
        themes=[],
        score=0.9,
        source=source,
        quality=quality,
    )


TEACH = (
    "Count every flight square before a piece is attacked. "
    "Use prophylaxis and piece activity to close the net, then take with the cheapest attacker."
)
SUMMARY = (
    "In this structure keep piece activity high and use prophylaxis against hanging material "
    "before launching a kingside attack."
)
BOOK = (
    "Opening encyclopedia chunk about typical Sicilian development plans and pawn breaks "
    "on the queenside."
)


def test_merge_prefers_annotated_then_summaries():
    annotated = [
        _p("curated trap net. " + TEACH, "annotated_game", "curated"),
        _p("draft trap take. " + TEACH, "annotated_game", "draft"),
    ]
    summaries = [_p(SUMMARY, "knowledge_summary")]
    books = [_p(BOOK, "book")]
    merged = merge_retrieve_pools(
        annotated=annotated,
        summaries=summaries,
        books=books,
        top_k=3,
        allow_books=False,
    )
    assert [p.source for p in merged] == [
        "annotated_game",
        "annotated_game",
        "knowledge_summary",
    ]
    assert merged[0].quality == "curated"


def test_merge_skips_books_on_tactic():
    annotated = [_p("annotated trap. " + TEACH, "annotated_game", "curated")]
    summaries = [_p(SUMMARY, "knowledge_summary")]
    books = [_p(BOOK, "book")]
    merged = merge_retrieve_pools(
        annotated=annotated,
        summaries=summaries,
        books=books,
        top_k=4,
        allow_books=False,
    )
    assert all(p.source != "book" for p in merged)
    assert [p.source for p in merged] == ["annotated_game", "knowledge_summary"]


def test_merge_books_only_when_allowed_opening():
    annotated: list[Passage] = []
    summaries: list[Passage] = []
    books = [_p(BOOK, "book")]
    merged = merge_retrieve_pools(
        annotated=annotated,
        summaries=summaries,
        books=books,
        top_k=2,
        allow_books=True,
    )
    assert [p.source for p in merged] == ["book"]
