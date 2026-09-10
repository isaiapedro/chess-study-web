from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import chess
import chess.pgn

from chess_coach.analyze import CriticalMoment, analyze_game_plies, is_critical_moment
from chess_coach.annotate import export_annotated_pgn
from chess_coach.book_pgn import reconstruct_pgn_from_citation
from chess_coach.chapter import GameCitation, extract_citations, load_chapter, order_citations_book
from chess_coach.chessgames import ChessgamesClient, ChessgamesHit, FetchResult
from chess_coach.comment import engine_grounded_note, explain, pedagogical_fallback
from chess_coach.engine import StockfishEngine
from chess_coach.logutil import log
from chess_coach.master_fetch import fetch_master_game
from chess_coach.notes_align import align_notes_to_game, apply_book_mark_nags, collect_mainline_book_marks
from chess_coach.ocr_chess import clean_book_note
from chess_coach.rag.quality import filter_passages
from chess_coach.rag.retrieve import retrieve_passages
from chess_coach.variations import (
    inject_book_lines_at_ply,
    inject_engine_line,
    strip_auto_variations,
)
from chess_coach.viewer import (
    build_missing_payload,
    write_chapter_book,
    write_missing_viewer,
    write_viewer,
)


@dataclass
class WalkthroughResult:
    citation: GameCitation
    fetch: FetchResult | None
    annotated_pgn: Path | None
    html_path: Path | None
    moments: int
    book_notes_applied: int
    errors: list[str]
    chapter_book_html: Path | None = None
    missing_payload: dict | None = None
    attempts: list[str] = field(default_factory=list)


def _sanitize(text: str, *, curated: bool = False) -> str:
    raw = (text or "").replace("{", "(").replace("}", ")")
    if curated:
        return raw.strip()
    return clean_book_note(raw).strip()


def _var_already_in_prose(var: str, prose: str) -> bool:
    """True when variation text is already inline in the book note (avoid [Vars:] echo)."""

    def norm(s: str) -> str:
        s = re.sub(r"\s+", " ", (s or "").strip().lower())
        return re.sub(r"^or\s+", "", s)

    def fingerprint(s: str) -> str:
        # Move numbers + destinations only — survives Qxg3 vs Bxg3 legalize drift
        return " ".join(
            re.findall(
                r"\d+\.(?:\.\.)?|[a-h][1-8]|o-o-o|o-o|drawn\s+position",
                norm(s),
            )
        )

    nv, np_ = norm(var), norm(prose)
    if len(nv) < 12 or not np_:
        return False
    if nv in np_:
        return True
    cut = nv.split("]")[0]
    if len(cut) >= 20 and cut in np_:
        return True
    fv, fp = fingerprint(var), fingerprint(prose)
    return len(fv) >= 12 and fv in fp


def _try_add_variation_line(board: chess.Board, main_node: chess.pgn.GameNode, line: str) -> bool:
    """Best-effort: add book sideline as PGN variation from position before main move."""
    from chess_coach.variations import add_move_line, playable_lines_from_text

    parent = main_node.parent
    if parent is None:
        return False
    after = board.copy()
    after.push(main_node.move)
    for root, moves, chunk in playable_lines_from_text(board, line, also_after=after)[:1]:
        if root.fen() == board.fen():
            return add_move_line(parent, board, moves, comment=f"Book line: {chunk[:100]}")
        if root.fen() == after.fen():
            return add_move_line(main_node, after, moves, comment=f"Book line: {chunk[:100]}")
    return False


def _select_comment_plies(
    all_moments: list[CriticalMoment],
    *,
    threshold: int,
    book_plies: set[int],
    opening_plies: int,
    sample_every: int,
) -> list[CriticalMoment]:
    """Critical + book anchors + light sampling (opening denser than middlegame)."""
    by_ply = {m.ply: m for m in all_moments}
    chosen: dict[int, CriticalMoment] = {}
    open_every = max(2, sample_every // 2) if sample_every > 0 else 2
    for moment in all_moments:
        if is_critical_moment(moment, threshold) or moment.ply in book_plies:
            chosen[moment.ply] = moment
        elif moment.ply <= opening_plies and moment.ply % open_every == 0:
            chosen[moment.ply] = moment
        elif sample_every > 0 and moment.ply > opening_plies and moment.ply % sample_every == 0:
            chosen[moment.ply] = moment
    return [by_ply[p] for p in sorted(chosen) if p in by_ply]


def _strip_engine_layer(comment: str) -> str:
    """Keep [Book:…] / vars; drop [Engine/RAG] chunks."""
    if not comment:
        return ""
    parts = [p.strip() for p in comment.split(" | ")]
    kept = [p for p in parts if p.startswith("[Book") or p.startswith("[Vars")]
    if kept:
        return " | ".join(kept)
    # Unlabeled legacy comments: drop anything that looks like engine spam
    if "[Engine" in comment or "FCO:" in comment:
        return ""
    return comment.strip()


def _secondary_for_moment(
    moment: CriticalMoment,
    config: dict[str, Any],
    *,
    use_rag: bool,
    use_llm: bool,
    exclude_book: str,
    used_fingerprints: set[str],
    min_delta: int,
    book_ply: bool,
) -> str | None:
    """Return engine/RAG note, or None to skip (avoid spam on quiet opening plies)."""
    passages = []
    if use_rag:
        log("  RAG retrieve ply %d (%s)...", moment.ply, moment.features.phase)
        try:
            passages = retrieve_passages(moment.features, config)
            passages = [p for p in passages if exclude_book.lower() not in p.book.lower()]
            passages = filter_passages(
                passages, moment, used_fingerprints=set(used_fingerprints), limit=3
            )
            log("  RAG concrete: %d passage(s)", len(passages))
        except Exception as exc:
            log("  RAG failed: %s", exc)
            passages = []

    # Passages enrich notes; they must not create spam on quiet opening plies.
    interesting = (
        is_critical_moment(moment, max(min_delta, 80))
        or moment.delta_cp >= min_delta
        or book_ply
    )
    if not interesting:
        return None

    if use_llm:
        log("  LLM comment ply %d (%s)...", moment.ply, moment.played_san)
        commentary = explain(
            moment,
            passages,
            config,
            allow_fallback=True,
            used_fingerprints=used_fingerprints,
        )
    else:
        # No raw book dumps in --no-llm mode (was repeating FCO intros).
        commentary = pedagogical_fallback(
            moment,
            passages,
            used_fingerprints=used_fingerprints,
            allow_book_quote=False,
        )

    text = commentary.text.strip()
    if not text:
        text = engine_grounded_note(moment, used_fingerprints=used_fingerprints)
    # Engine/RAG prose is already clean — OCR sanitize mangles evals like +0.58.
    return text.replace("{", "(").replace("}", ")").strip()


def _book_prefix(source_book: str, *, kind: str = "draft") -> str:
    from chess_coach.book_notes_sidecar import book_tag_prefix

    return book_tag_prefix(source_book, kind=kind)


def apply_dual_annotations(
    game: chess.pgn.Game,
    citation: GameCitation,
    config: dict[str, Any],
    *,
    use_rag: bool = True,
    use_llm: bool = True,
    depth: int | None = None,
    threshold: int | None = None,
    book_kind: str = "draft",
    pgn_path: Path | None = None,
) -> tuple[chess.pgn.Game, int, int]:
    depth = depth or int(config.get("analyze_depth", 12))
    threshold = threshold or int(config.get("critical_cp_threshold", 120))
    ann = config.get("annotate") or {}
    opening_plies = int(ann.get("opening_plies", 18))
    sample_every = int(ann.get("sample_every_ply", 4))
    min_delta = int(ann.get("min_delta_for_note", 35))

    # Prefer curated/draft sidecar over live PDF citation notes.
    if pgn_path is not None:
        from chess_coach.book_notes_sidecar import merge_citation_with_sidecar, resolve_sidecar, load_sidecar

        side_path = resolve_sidecar(pgn_path)
        if side_path is not None:
            citation, book_kind = merge_citation_with_sidecar(citation, load_sidecar(side_path))
    # Production policy: PDF extract alone is draft-only (never pretend curated).
    if book_kind == "extract":
        book_kind = "draft"

    aligned = align_notes_to_game(
        game, citation.notes, context=citation.context, curated=(book_kind == "curated")
    )
    book_marks = collect_mainline_book_marks(
        game, citation.notes, context=citation.context
    )
    book_by_ply: dict[int, str] = {}
    variations_by_ply: dict[int, list[str]] = {}
    curated = book_kind == "curated"
    for note in aligned:
        prefix = _book_prefix(citation.source_book, kind=book_kind)
        chunk = _sanitize(note.text, curated=curated)
        if not chunk:
            continue
        book_by_ply[note.ply] = prefix + chunk
        if note.variations:
            variations_by_ply[note.ply] = note.variations
            unique_vars = [
                _sanitize(v, curated=curated)
                for v in note.variations[:4]
                if _sanitize(v, curated=curated) and not _var_already_in_prose(v, chunk)
            ]
            if unique_vars:
                book_by_ply[note.ply] += " [Vars: " + "; ".join(unique_vars) + "]"

    strip_auto_variations(game)

    log(
        "Annotate start: depth=%d threshold=%scp raw_notes=%d aligned=%d rag=%s llm=%s "
        "opening_plies=%d sample_every=%d book_kind=%s",
        depth,
        threshold,
        len(citation.notes),
        len(book_by_ply),
        use_rag,
        use_llm,
        opening_plies,
        sample_every,
        book_kind,
    )
    for note in aligned[:8]:
        log(
            "  book @ %d%s %s (%d chars, %d vars)",
            note.fullmove,
            "." if note.side == "white" else "...",
            note.san,
            len(note.text),
            len(note.variations),
        )
    with StockfishEngine(path=config.get("stockfish_path", "stockfish"), depth=depth) as engine:
        all_moments = analyze_game_plies(game, engine)
    critical = [m for m in all_moments if is_critical_moment(m, threshold)]
    to_comment = _select_comment_plies(
        all_moments,
        threshold=threshold,
        book_plies=set(book_by_ply),
        opening_plies=opening_plies,
        sample_every=sample_every,
    )
    log(
        "Secondary targets: %d (critical=%d book=%d dense/sample=%d)",
        len(to_comment),
        len(critical),
        len(book_by_ply),
        len(to_comment) - len({m.ply for m in critical} | set(book_by_ply)),
    )

    secondary_by_ply: dict[int, str] = {}
    used_fingerprints: set[str] = set()
    log("Building secondary notes for %d candidate ply(s)...", len(to_comment))
    for idx, moment in enumerate(to_comment, start=1):
        log("  moment %d/%d ply %d", idx, len(to_comment), moment.ply)
        note = _secondary_for_moment(
            moment,
            config,
            use_rag=use_rag,
            use_llm=use_llm,
            exclude_book=citation.source_book,
            used_fingerprints=used_fingerprints,
            min_delta=min_delta,
            book_ply=moment.ply in book_by_ply,
        )
        if note:
            secondary_by_ply[moment.ply] = note
    log("Secondary notes kept: %d / %d candidates", len(secondary_by_ply), len(to_comment))

    board = game.board()
    node = game
    ply = 0
    book_applied = 0
    fork_count = 0
    moments_by_ply = {m.ply: m for m in all_moments}
    comment_plies = set(secondary_by_ply) | set(book_by_ply) | {m.ply for m in critical}
    preamble = (citation.preamble or "").strip()
    if preamble:
        game.comment = _book_prefix(citation.source_book, kind=book_kind) + preamble
        book_applied += 1
    while node.variations:
        next_node = node.variation(0)
        ply += 1
        parts: list[str] = []
        if ply in book_by_ply:
            parts.append(book_by_ply[ply])
            book_applied += 1
            fork_count += inject_book_lines_at_ply(game, ply, book_by_ply[ply], max_lines=4)
            for var_line in variations_by_ply.get(ply, [])[:3]:
                if _try_add_variation_line(board, next_node, var_line):
                    fork_count += 1
        if ply in secondary_by_ply:
            parts.append("[Engine/RAG] " + secondary_by_ply[ply])
        if parts:
            next_node.comment = " | ".join(parts)
        moment = moments_by_ply.get(ply)
        if moment is not None:
            if ply in comment_plies and inject_engine_line(
                node,
                board,
                best_uci=moment.best_uci,
                played_uci=moment.played_uci,
                pv_san=moment.pv_san,
                depth=moment.depth,
            ):
                fork_count += 1
            if moment.delta_cp >= 80:
                if moment.delta_cp >= 300:
                    next_node.nags.add(chess.pgn.NAG_BLUNDER)
                elif moment.delta_cp >= 150:
                    next_node.nags.add(chess.pgn.NAG_MISTAKE)
                else:
                    next_node.nags.add(chess.pgn.NAG_DUBIOUS_MOVE)
        board.push(next_node.move)
        node = next_node

    game.headers["Annotator"] = f"Book:{citation.source_book} + Stockfish/RAG"
    game.headers["BookChapter"] = citation.chapter
    mark_n = apply_book_mark_nags(game, book_marks)
    log(
        "Annotate done: book_notes=%d critical=%d forks=%d marks=%d kind=%s",
        book_applied,
        len(critical),
        fork_count,
        mark_n,
        book_kind,
    )
    return game, book_applied, len(critical)


def _strip_book_layer(comment: str) -> str:
    """Drop [Book:…] / [Vars:…] chunks; keep [Engine/RAG] and other text."""
    if not comment:
        return ""
    parts = [p.strip() for p in comment.split(" | ")]
    kept: list[str] = []
    for part in parts:
        if part.startswith("[Book:") or part.startswith("[Vars:"):
            continue
        # Vars sometimes glued onto Book without separator — already dropped via Book
        kept.append(part)
    return " | ".join(kept).strip()


def reapply_book_layer(
    game: chess.pgn.Game,
    citation: GameCitation,
    *,
    book_kind: str = "draft",
    pgn_path: Path | None = None,
) -> tuple[chess.pgn.Game, int]:
    """
    Replace [Book:…] comments from citation or curated sidecar; keep [Engine/RAG].
    """
    if pgn_path is not None:
        from chess_coach.book_notes_sidecar import load_sidecar, merge_citation_with_sidecar, resolve_sidecar

        side_path = resolve_sidecar(pgn_path)
        if side_path is not None:
            citation, book_kind = merge_citation_with_sidecar(citation, load_sidecar(side_path))
    if book_kind == "extract":
        book_kind = "draft"

    aligned = align_notes_to_game(
        game, citation.notes, context=citation.context, curated=(book_kind == "curated")
    )
    book_marks = collect_mainline_book_marks(
        game, citation.notes, context=citation.context
    )
    book_by_ply: dict[int, str] = {}
    variations_by_ply: dict[int, list[str]] = {}
    curated = book_kind == "curated"
    for note in aligned:
        chunk = _sanitize(note.text, curated=curated)
        if not chunk:
            continue
        prefix = _book_prefix(citation.source_book, kind=book_kind)
        book_by_ply[note.ply] = prefix + chunk
        if note.variations:
            variations_by_ply[note.ply] = note.variations
            unique_vars = [
                _sanitize(v, curated=curated)
                for v in note.variations[:4]
                if _sanitize(v, curated=curated) and not _var_already_in_prose(v, chunk)
            ]
            if unique_vars:
                book_by_ply[note.ply] += " [Vars: " + "; ".join(unique_vars) + "]"

    strip_auto_variations(game, book=True, engine=False)

    # Intro / learning-objective text before the first scored move.
    preamble = (citation.preamble or "").strip()
    rest_start = _strip_book_layer(game.comment or "")
    if preamble:
        game.comment = _book_prefix(citation.source_book, kind=book_kind) + preamble
        if rest_start:
            game.comment += " | " + rest_start
    else:
        game.comment = rest_start

    board = game.board()
    node = game
    ply = 0
    applied = 0
    forks = 0
    while node.variations:
        next_node = node.variation(0)
        ply += 1
        rest = _strip_book_layer(next_node.comment or "")
        parts: list[str] = []
        if ply in book_by_ply:
            parts.append(book_by_ply[ply])
            applied += 1
            forks += inject_book_lines_at_ply(game, ply, book_by_ply[ply], max_lines=4)
            for var_line in variations_by_ply.get(ply, [])[:3]:
                if _try_add_variation_line(board, next_node, var_line):
                    forks += 1
        if rest:
            parts.append(rest)
        next_node.comment = " | ".join(parts) if parts else ""
        board.push(next_node.move)
        node = next_node

    game.headers["Annotator"] = f"Book:{citation.source_book} + Stockfish/RAG"
    if citation.chapter:
        game.headers["BookChapter"] = citation.chapter
    if preamble:
        applied += 1
    mark_n = apply_book_mark_nags(game, book_marks)
    log(
        "Reapplied book notes: %d (raw=%d forks=%d preamble=%s marks=%d kind=%s)",
        applied,
        len(citation.notes),
        forks,
        bool(preamble),
        mark_n,
        book_kind,
    )
    return game, applied


def refresh_secondary_on_game(
    game: chess.pgn.Game,
    config: dict[str, Any],
    *,
    use_rag: bool = False,
    use_llm: bool = False,
    depth: int | None = None,
    threshold: int | None = None,
) -> tuple[chess.pgn.Game, int]:
    """
    Keep existing [Book:…] comments; rewrite [Engine/RAG] with position-specific notes.
    Does not need chapter citations (operates on already-annotated PGNs).
    """
    depth = depth or int(config.get("analyze_depth", 12))
    threshold = threshold or int(config.get("critical_cp_threshold", 120))
    ann = config.get("annotate") or {}
    opening_plies = int(ann.get("opening_plies", 12))
    sample_every = int(ann.get("sample_every_ply", 4))
    min_delta = int(ann.get("min_delta_for_note", 40))

    book_plies: set[int] = set()
    node = game
    ply = 0
    while node.variations:
        next_node = node.variation(0)
        ply += 1
        kept = _strip_engine_layer(next_node.comment or "")
        next_node.comment = kept
        if kept:
            book_plies.add(ply)
        node = next_node

    strip_auto_variations(game, book=False, engine=True)

    with StockfishEngine(path=config.get("stockfish_path", "stockfish"), depth=depth) as engine:
        all_moments = analyze_game_plies(game, engine)
    critical = [m for m in all_moments if is_critical_moment(m, threshold)]
    to_comment = _select_comment_plies(
        all_moments,
        threshold=threshold,
        book_plies=book_plies,
        opening_plies=opening_plies,
        sample_every=sample_every,
    )
    secondary_by_ply: dict[int, str] = {}
    used_fingerprints: set[str] = set()
    exclude_book = game.headers.get("BookChapter", "") or game.headers.get("Annotator", "")
    for moment in to_comment:
        # LLM path benefits from tagged RAG; keep engine-only path quiet unless --rag.
        note = _secondary_for_moment(
            moment,
            config,
            use_rag=use_rag or use_llm,
            use_llm=use_llm,
            exclude_book=exclude_book,
            used_fingerprints=used_fingerprints,
            min_delta=min_delta,
            book_ply=moment.ply in book_plies,
        )
        if note:
            secondary_by_ply[moment.ply] = note

    node = game
    ply = 0
    board = game.board()
    moments_by_ply = {m.ply: m for m in all_moments}
    comment_plies = set(secondary_by_ply) | book_plies | {m.ply for m in critical}
    forks = 0
    while node.variations:
        next_node = node.variation(0)
        ply += 1
        parts: list[str] = []
        if next_node.comment:
            parts.append(next_node.comment)
        if ply in secondary_by_ply:
            parts.append("[Engine/RAG] " + secondary_by_ply[ply])
        next_node.comment = " | ".join(parts) if parts else ""
        moment = moments_by_ply.get(ply)
        if moment is not None and ply in comment_plies:
            if inject_engine_line(
                node,
                board,
                best_uci=moment.best_uci,
                played_uci=moment.played_uci,
                pv_san=moment.pv_san,
                depth=moment.depth,
            ):
                forks += 1
            if moment.delta_cp >= 80:
                if moment.delta_cp >= 300:
                    next_node.nags.add(chess.pgn.NAG_BLUNDER)
                elif moment.delta_cp >= 150:
                    next_node.nags.add(chess.pgn.NAG_MISTAKE)
                else:
                    next_node.nags.add(chess.pgn.NAG_DUBIOUS_MOVE)
        board.push(next_node.move)
        node = next_node

    game.headers["Annotator"] = "Book + Stockfish (position notes)"
    log("Refresh secondary: %d engine notes, %d engine forks", len(secondary_by_ply), forks)
    return game, len(secondary_by_ply)


def _load_chapter_book_meta(chapter_html: Path) -> dict[str, Any] | None:
    import json

    text = chapter_html.read_text(encoding="utf-8", errors="replace")
    match = re.search(r'id="book-data">(.*?)</script>', text, re.S)
    if not match:
        return None
    raw = match.group(1).replace("<\\/", "</")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def refresh_bookwalk_dir(
    pgn_dir: Path,
    viewer_dir: Path,
    config: dict[str, Any],
    *,
    use_rag: bool = False,
    use_llm: bool = False,
    depth: int | None = None,
    chapter_html: Path | None = None,
) -> Path | None:
    """
    Refresh secondary notes on PGNs listed in an existing chapter book (book order),
    keep missing pages, rewrite chapter HTML (TOC-only UI + local Stockfish).
    """
    if chapter_html is None:
        candidates = list(viewer_dir.glob("*_chapter_book.html"))
        if not candidates:
            log("No *_chapter_book.html in %s", viewer_dir)
            return None
        chapter_html = max(candidates, key=lambda p: p.stat().st_size)
    meta = _load_chapter_book_meta(chapter_html)
    if not meta or not meta.get("games"):
        log("Could not parse chapter book data from %s", chapter_html)
        return None

    book = str(meta.get("book") or "Chapter")
    chapter = str(meta.get("chapter") or "")
    entries: list[Path | dict] = []
    games = meta["games"]
    log("Refresh chapter book: %d page(s) → %s", len(games), chapter_html.name)

    for i, g in enumerate(games):
        if g.get("missing"):
            payload = {
                "missing": True,
                "matchup": g.get("matchup") or "Unknown",
                "subtitle": g.get("subtitle") or "",
                "date": g.get("date") or "",
                "book": g.get("book") or book,
                "chapter": g.get("chapter") or chapter,
                "plies": [],
                "startFen": g.get("startFen") or chess.STARTING_FEN,
                "missingInfo": g.get("missingInfo") or {},
            }
            entries.append(payload)
            log("  [%d] keep missing: %s", i + 1, payload["matchup"])
            continue
        src = g.get("sourcePgn") or ""
        path = pgn_dir / src if src else None
        if path is None or not path.exists():
            # fallback by matchup slug
            matchup = (g.get("matchup") or "").replace(" vs ", "_vs_").replace(" ", "_")
            year = (g.get("date") or "")[:4]
            guess = pgn_dir / f"{matchup}_{year}_bookwalk.pgn"
            path = guess if guess.exists() else None
        if path is None or not path.exists():
            log("  [%d] PGN missing for %s — skip", i + 1, g.get("matchup"))
            continue
        with path.open(encoding="utf-8", errors="replace") as handle:
            game = chess.pgn.read_game(handle)
        if game is None:
            continue
        log("  [%d] refresh %s", i + 1, path.name)
        game, n = refresh_secondary_on_game(
            game, config, use_rag=use_rag, use_llm=use_llm, depth=depth
        )
        export_annotated_pgn(game, path)
        write_viewer(path, viewer_dir / path.name.replace("_bookwalk.pgn", "_bookwalk.html"))
        entries.append(path)
        log("    → %d secondary notes", n)

    if not entries:
        return None
    write_chapter_book(entries, chapter_html, book=book, chapter=chapter)
    log("Chapter book rebuilt: %s", chapter_html)
    return chapter_html


def _missing_result(
    citation: GameCitation,
    *,
    attempts: list[str],
    reason: str,
    viewer_dir: Path,
) -> WalkthroughResult:
    payload = build_missing_payload(
        white=citation.white,
        black=citation.black,
        year=citation.year,
        event=citation.event or "",
        book=citation.source_book,
        chapter=citation.chapter,
        attempts=attempts,
        reason=reason,
        notes_count=len(citation.notes),
        context_preview=citation.context or "",
    )
    viewer_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{citation.white}_vs_{citation.black}_{citation.year}".replace(" ", "_")
    html_path = viewer_dir / f"{stem}_missing.html"
    write_missing_viewer(payload, html_path)
    log("Missing game page: %s", html_path.name)
    return WalkthroughResult(
        citation=citation,
        fetch=None,
        annotated_pgn=None,
        html_path=html_path,
        moments=0,
        book_notes_applied=0,
        errors=[reason],
        missing_payload=payload,
        attempts=attempts,
    )


def walkthrough_citation(
    citation: GameCitation,
    config: dict[str, Any],
    *,
    out_dir: Path,
    viewer_dir: Path,
    use_rag: bool = True,
    use_llm: bool = True,
    depth: int | None = None,
    threshold: int | None = None,
    client: ChessgamesClient | None = None,
) -> WalkthroughResult:
    attempts: list[str] = []
    log(
        "Game: %s vs %s %s (%s)",
        citation.white,
        citation.black,
        citation.year,
        citation.event or "no event",
    )
    fetch: FetchResult | None = None
    try:
        attempts.append("local masters index")
        attempts.append("chessgames.com")
        fetch = fetch_master_game(
            citation.white,
            citation.black,
            year=citation.year,
            event_hint=citation.event or None,
            config=config,
            out_dir=out_dir / "raw",
            client=client,
        )
    except Exception as exc:
        log("Master fetch failed: %s", exc)
        fetch = None

    if fetch is None:
        log("No master match — trying book PDF/text reconstruction")
        attempts.append("book PDF/text move reconstruction")
        book_pgn = reconstruct_pgn_from_citation(citation)
        if book_pgn:
            raw_dir = out_dir / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            raw_path = raw_dir / (
                f"book_{citation.white}_vs_{citation.black}_{citation.year}.pgn".replace(" ", "_")
            )
            raw_path.write_text(book_pgn if book_pgn.endswith("\n") else book_pgn + "\n", encoding="utf-8")
            fetch = FetchResult(
                pgn=book_pgn,
                hit=ChessgamesHit(
                    gid="book-text",
                    white=citation.white,
                    black=citation.black,
                    year=str(citation.year),
                    result="*",
                    event=citation.event or "Book score (reconstructed)",
                    eco="",
                    url="book://text",
                ),
                path=raw_path,
            )
        else:
            return _missing_result(
                citation,
                attempts=attempts,
                reason=(
                    f"No PGN for {citation.white} vs {citation.black} {citation.year}: "
                    "local masters miss, Chessgames miss, book text had too few legal moves"
                ),
                viewer_dir=viewer_dir,
            )

    if str(fetch.hit.gid).startswith("local-"):
        source = "local masters"
    elif fetch.hit.gid == "book-text":
        source = "book PDF/text"
    else:
        source = "chessgames.com"
    log("PGN loaded gid=%s source=%s — starting dual annotate", fetch.hit.gid, source)
    game = chess.pgn.read_game(io.StringIO(fetch.pgn))
    if game is None:
        return _missing_result(
            citation,
            attempts=attempts + ["PGN parse"],
            reason=f"Fetched PGN unreadable for {citation.white} vs {citation.black} {citation.year}",
            viewer_dir=viewer_dir,
        )

    try:
        stem = f"{citation.white}_vs_{citation.black}_{citation.year}".replace(" ", "_")
        pgn_path = out_dir / f"{stem}_bookwalk.pgn"
        annotated, book_n, crit_n = apply_dual_annotations(
            game,
            citation,
            config,
            use_rag=use_rag,
            use_llm=use_llm,
            depth=depth,
            threshold=threshold,
            pgn_path=pgn_path,
        )
    except Exception as exc:
        log("Annotate failed: %s", exc)
        return _missing_result(
            citation,
            attempts=attempts + [f"annotate ({source})"],
            reason=f"Annotate failed for {citation.white} vs {citation.black}: {exc}",
            viewer_dir=viewer_dir,
        )

    annotated.headers["Source"] = source
    out_dir.mkdir(parents=True, exist_ok=True)
    viewer_dir.mkdir(parents=True, exist_ok=True)
    html_path = viewer_dir / f"{stem}_bookwalk.html"
    log("Writing PGN + HTML viewer...")
    export_annotated_pgn(annotated, pgn_path)
    write_viewer(pgn_path, html_path)
    log("Done: %s", pgn_path.name)
    return WalkthroughResult(
        citation=citation,
        fetch=fetch,
        annotated_pgn=pgn_path,
        html_path=html_path,
        moments=crit_n,
        book_notes_applied=book_n,
        errors=[],
        attempts=attempts,
    )


def walkthrough_citations(
    citations: list[GameCitation],
    config: dict[str, Any],
    *,
    out_dir: Path,
    viewer_dir: Path,
    max_games: int = 5,
    use_rag: bool = True,
    use_llm: bool = True,
    depth: int | None = None,
    threshold: int | None = None,
    section_label: str = "",
) -> list[WalkthroughResult]:
    """Fetch/annotate in book order until max_games successes (0 = all)."""
    ordered = order_citations_book(citations)
    want = len(ordered) if max_games <= 0 else max_games
    log(
        "Walkthrough%s: want %d ok game(s) from %d citation(s) [book order]",
        f" {section_label}" if section_label else "",
        want,
        len(ordered),
    )
    results: list[WalkthroughResult] = []
    book_entries: list[Path | dict] = []
    ok = 0
    missing = 0
    with ChessgamesClient(delay_s=1.8) as client:
        for idx, citation in enumerate(ordered, start=1):
            if ok >= want:
                break
            log(
                "--- book game %d/%d (ok %d/%d) %s vs %s ---",
                idx,
                len(ordered),
                ok,
                want,
                citation.white,
                citation.black,
            )
            result = walkthrough_citation(
                citation,
                config,
                out_dir=out_dir,
                viewer_dir=viewer_dir,
                use_rag=use_rag,
                use_llm=use_llm,
                depth=depth,
                threshold=threshold,
                client=client,
            )
            results.append(result)
            if result.missing_payload is not None:
                book_entries.append(result.missing_payload)
                missing += 1
                log("candidate missing — page kept in chapter book")
                continue
            if result.errors or not result.annotated_pgn:
                log("candidate failed — trying next in book order")
                continue
            book_entries.append(result.annotated_pgn)
            ok += 1
    chapter_html: Path | None = None
    if book_entries:
        book = ordered[0].source_book if ordered else "chapter"
        chapter = ordered[0].chapter if ordered else section_label
        slug = re.sub(r"[^a-z0-9]+", "_", f"{book}_{chapter}".lower()).strip("_")[:80]
        chapter_html = viewer_dir / f"{slug}_chapter_book.html"
        try:
            write_chapter_book(
                book_entries,
                chapter_html,
                book=book,
                chapter=chapter,
            )
            log(
                "Chapter book HTML: %s (%d pages, %d missing)",
                chapter_html,
                len(book_entries),
                missing,
            )
            for result in results:
                result.chapter_book_html = chapter_html
        except Exception as exc:
            log("Chapter book HTML failed: %s", exc)
    log("Walkthrough finished: %d ok / %d missing / %d tried", ok, missing, len(results))
    return results


def walkthrough_chapter(
    book_path: Path,
    config: dict[str, Any],
    *,
    chapter: str | int | None,
    out_dir: Path,
    viewer_dir: Path,
    max_games: int = 5,
    use_rag: bool = True,
    use_llm: bool = True,
    depth: int | None = None,
    threshold: int | None = None,
    scheme: str | None = None,
    min_body_chars: int = 800,
    citations: list[GameCitation] | None = None,
) -> list[WalkthroughResult]:
    if citations is None:
        book_name, title, body = load_chapter(
            book_path,
            chapter,
            scheme=scheme,
            min_body_chars=min_body_chars,
        )
        citations = extract_citations(body, book=book_name, chapter=title)
        section_label = f"{book_name} / {title}"
    else:
        section_label = citations[0].chapter if citations else ""
    return walkthrough_citations(
        citations,
        config,
        out_dir=out_dir,
        viewer_dir=viewer_dir,
        max_games=max_games,
        use_rag=use_rag,
        use_llm=use_llm,
        depth=depth,
        threshold=threshold,
        section_label=section_label,
    )
