from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from chess_coach.analyze import find_critical_moments
from chess_coach.annotate import annotate_pgn_file
from chess_coach.comment import Commentary, explain
from chess_coach.config import load_config, resolve_path
from chess_coach.engine import StockfishEngine
from chess_coach.pgn_io import load_game
from chess_coach.rag.ingest import ingest_path, retag_patterns
from chess_coach.rag.preflight import format_preflight_report, run_preflight
from chess_coach.rag.retrieve import retrieve_passages
from chess_coach.report import write_report
from chess_coach.book_walkthrough import refresh_bookwalk_dir, walkthrough_chapter
from chess_coach.chapter import extract_citations, list_book_sections, load_chapter
from chess_coach.chessgames import ChessgamesClient
from chess_coach.master_fetch import fetch_master_game, masters_db_from_config
from chess_coach.masters_db import LocalMastersDB
from chess_coach.sections_init import init_sections_for_dir
from chess_coach.scrape import (
    scrape_chesscom_month,
    scrape_lichess_game_ids,
    scrape_lichess_user,
    scrape_masters_opening,
    scrape_pgn_url,
    summarize,
)
from chess_coach.lichess_study import push_annotated_pgns
from chess_coach.viewer import write_chapter_book, write_scid_import_readme, write_viewer


def _resolve_existing(path: Path) -> Path | None:
    if path.is_absolute() and path.exists():
        return path
    resolved = resolve_path(path)
    if resolved.exists():
        return resolved
    cwd_candidate = Path.cwd() / path
    if cwd_candidate.exists():
        return cwd_candidate
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chess-coach", description="Local PGN chess coaching CLI")
    parser.add_argument("--config", type=Path, default=None, help="Path to YAML config")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="Analyze a PGN and emit a coaching report")
    analyze.add_argument("pgn", type=Path, help="PGN file path")
    analyze.add_argument("--out", type=Path, default=Path("report.md"), help="Markdown output path")
    analyze.add_argument("--game-index", type=int, default=0)
    analyze.add_argument("--depth", type=int, default=None)
    analyze.add_argument("--threshold", type=int, default=None, help="Critical CP loss threshold")
    analyze.add_argument("--no-rag", action="store_true", help="Skip book retrieval")
    analyze.add_argument("--no-llm", action="store_true", help="Skip Ollama; use engine-only notes")
    analyze.add_argument("--json", action="store_true", help="Also write JSON beside the markdown")

    ingest = sub.add_parser("ingest", help="Ingest chess books into Chroma with real embeddings")
    ingest.add_argument("path", type=Path, help="Book file or directory")
    ingest.add_argument("--reset", action="store_true", help="Delete existing collection first")
    ingest.add_argument(
        "--allow-hash-fallback",
        action="store_true",
        help="Allow weak hash embeddings if Ollama unavailable (not recommended)",
    )

    retag = sub.add_parser(
        "retag-patterns",
        help="Tag existing Chroma chunks with ontology pattern IDs (no re-embed)",
    )
    retag.add_argument("--batch-size", type=int, default=64)

    preflight = sub.add_parser(
        "preflight",
        help="Test Ollama embeddings + PDF text extract BEFORE full ingest",
    )
    preflight.add_argument("path", type=Path, nargs="?", default=Path("data/books"))
    preflight.add_argument("--limit", type=int, default=None, help="Only check first N books")
    preflight.add_argument("--out", type=Path, default=None, help="Write report markdown")

    sections = sub.add_parser(
        "sections",
        help="Auto-detect section schemes and write .sections.yaml for books",
    )
    sections.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("data/books"),
        help="Book file or directory (default: data/books)",
    )
    sections.add_argument("--force", action="store_true", help="Overwrite existing sidecars")
    sections.add_argument("--min-body", type=int, default=800)

    masters_index = sub.add_parser(
        "masters-index",
        help="Build SQLite index over local master PGNs (Lumbra Gigabase OTB, etc.)",
    )
    masters_index.add_argument(
        "--pgn-dir",
        type=Path,
        default=None,
        help="Directory of .pgn files (default: config masters.pgn_dir)",
    )
    masters_index.add_argument(
        "--index",
        type=Path,
        default=None,
        help="SQLite index path (default: config masters.index_path)",
    )
    masters_index.add_argument(
        "--no-reset",
        action="store_true",
        help="Fail if index already exists instead of rebuilding",
    )
    masters_index.add_argument(
        "--fix-surnames",
        action="store_true",
        help="Repair white_last/black_last for Last, First PGN names (no full rebuild)",
    )

    chapter = sub.add_parser(
        "chapter",
        help="Book section → local masters (+ Chessgames fallback) → dual walkthrough",
    )
    chapter.add_argument("book", type=Path, help="Book PDF/TXT path")
    chapter.add_argument(
        "--chapter",
        default="1",
        help="Section number or title substring (default: 1). Meaning depends on book scheme (Game/Chapter/…)",
    )
    chapter.add_argument(
        "--scheme",
        choices=["auto", "family", "chapter", "game", "ending", "part", "lesson", "section"],
        default="auto",
        help="Heading scheme (default: auto). Chess Structures = family; Capablanca endings = game",
    )
    chapter.add_argument(
        "--min-body",
        type=int,
        default=800,
        help="Min chars after a heading to count as a real section (skips TOC stubs)",
    )
    chapter.add_argument(
        "--list-sections",
        action="store_true",
        help="List detected sections for this book and exit",
    )
    chapter.add_argument(
        "--max-games",
        type=int,
        default=3,
        help="Max games to fetch in book order (0 = all citations in the section)",
    )
    chapter.add_argument("--out", type=Path, default=Path("data/annotated/bookwalk"))
    chapter.add_argument("--html-dir", type=Path, default=Path("data/viewer_out/bookwalk"))
    chapter.add_argument("--depth", type=int, default=None)
    chapter.add_argument("--threshold", type=int, default=None)
    chapter.add_argument("--no-rag", action="store_true")
    chapter.add_argument("--no-llm", action="store_true")
    chapter.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list detected game citations (no fetch)",
    )

    scrape = sub.add_parser(
        "scrape",
        help="Fetch master PGNs (local index first, then Chessgames / legacy)",
    )
    scrape.add_argument("--out", type=Path, default=Path("data/pgn_archive"), help="Output directory")
    scrape.add_argument("--white", type=str, default=None, help="Chessgames: White player")
    scrape.add_argument("--black", type=str, default=None, help="Chessgames: Black player")
    scrape.add_argument("--year", type=int, default=None, help="Chessgames: year")
    scrape.add_argument("--event", type=str, default=None, help="Chessgames: event hint")
    scrape.add_argument("--gid", type=str, default=None, help="Chessgames game id")
    scrape.add_argument(
        "--lichess-user",
        type=str,
        default=None,
        help="Legacy: Lichess user games (not for book walkthrough)",
    )
    scrape.add_argument("--game-id", action="append", default=[], help="Legacy Lichess game id")
    scrape.add_argument("--chesscom-user", type=str, default=None, help="Legacy Chess.com user")
    scrape.add_argument("--month", type=int, default=None)
    scrape.add_argument("--masters-play", type=str, default=None, help="Legacy Lichess masters explorer")
    scrape.add_argument("--url", type=str, default=None, help="Raw PGN URL")
    scrape.add_argument("--max", type=int, default=20, help="Max games to fetch")

    annotate = sub.add_parser(
        "annotate",
        help="Stockfish + commentary → Scid-ready annotated PGN (+ optional HTML viewer)",
    )
    annotate.add_argument("pgn", type=Path)
    annotate.add_argument("--out", type=Path, default=None, help="Annotated PGN path")
    annotate.add_argument("--html", type=Path, default=None, help="HTML visualizer path")
    annotate.add_argument("--game-index", type=int, default=0)
    annotate.add_argument("--depth", type=int, default=None)
    annotate.add_argument("--threshold", type=int, default=None)
    annotate.add_argument("--no-rag", action="store_true")
    annotate.add_argument("--no-llm", action="store_true")

    visualize = sub.add_parser("visualize", help="Build HTML board visualizer from annotated PGN")
    visualize.add_argument("pgn", type=Path)
    visualize.add_argument("--out", type=Path, default=Path("data/viewer_out/game.html"))

    refresh = sub.add_parser(
        "refresh-notes",
        help="Rewrite Engine/RAG notes on bookwalk PGNs + rebuild chapter book (no re-fetch)",
    )
    refresh.add_argument(
        "--pgn-dir",
        type=Path,
        default=Path("data/annotated/bookwalk"),
        help="Directory with *_bookwalk.pgn",
    )
    refresh.add_argument(
        "--html-dir",
        type=Path,
        default=Path("data/viewer_out/bookwalk"),
        help="Directory with *_chapter_book.html",
    )
    refresh.add_argument(
        "--chapter-book",
        type=Path,
        default=None,
        help="Specific chapter book HTML (default: largest *_chapter_book.html)",
    )
    refresh.add_argument("--depth", type=int, default=None)
    refresh.add_argument("--rag", action="store_true", help="Allow filtered RAG (off by default)")
    refresh.add_argument("--llm", action="store_true", help="Use Ollama for notes (off by default)")
    refresh.add_argument(
        "--html-only",
        action="store_true",
        help="Only rebuild chapter HTML/UI + Stockfish assets (keep existing notes)",
    )

    ontology = sub.add_parser("ontology", help="List/detect pattern ontology nodes")
    ontology.add_argument(
        "--fen",
        type=str,
        default=None,
        help="Detect patterns for a FEN string",
    )
    ontology.add_argument("--eco", type=str, default="", help="ECO for detection")
    ontology.add_argument("--opening", type=str, default="", help="Opening name for detection")
    ontology.add_argument("--cards", action="store_true", help="Print rule cards for detected/listed patterns")

    study = sub.add_parser(
        "study-push",
        help="Upload annotated PGNs to a Lichess study (comments + move variations)",
    )
    study.add_argument(
        "paths",
        type=Path,
        nargs="+",
        help="Annotated .pgn file(s) and/or directories (skips **/raw/**)",
    )
    study.add_argument(
        "--name",
        type=str,
        default=None,
        help="Study title (default: derived from path / first game)",
    )
    study.add_argument(
        "--study-id",
        type=str,
        default=None,
        help="Existing study id (omit to create a new unlisted study)",
    )
    study.add_argument(
        "--visibility",
        choices=["public", "unlisted", "private"],
        default="unlisted",
        help="Visibility when creating a study (default: unlisted)",
    )
    study.add_argument(
        "--orientation",
        choices=["white", "black"],
        default=None,
        help="Fixed board orientation (default: auto)",
    )
    study.add_argument(
        "--batch",
        action="store_true",
        help="Import all games in one request (faster; only first chapter gets --name)",
    )
    study.add_argument(
        "--include-raw",
        action="store_true",
        help="Also include **/raw/** PGNs under directories",
    )
    study.add_argument(
        "--token",
        type=str,
        default=None,
        help="Lichess PAT with study:write (default: LICHESS_TOKEN env)",
    )
    study.add_argument(
        "--delay",
        type=float,
        default=0.35,
        help="Seconds between per-chapter imports (default: 0.35)",
    )
    study.add_argument(
        "--dry-run",
        action="store_true",
        help="List chapters that would be uploaded; no API calls",
    )

    return parser


def cmd_preflight(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    path = _resolve_existing(args.path)
    if path is None:
        print(f"Path not found: {args.path}", file=sys.stderr)
        return 1
    ollama_notes, checks = run_preflight(path, config, limit=args.limit)
    report = format_preflight_report(ollama_notes, checks)
    if args.out:
        out = args.out if args.out.is_absolute() else Path.cwd() / args.out
        out.write_text(report, encoding="utf-8")
        print(f"Wrote {out}")
    print(report)
    embed_fail = any(n.startswith("FAIL") for n in ollama_notes)
    bad_books = sum(1 for c in checks if not c.ok)
    if embed_fail:
        return 2
    if bad_books:
        return 1
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    path = _resolve_existing(args.path)
    if path is None:
        print(f"Path not found: {args.path}", file=sys.stderr)
        return 1
    try:
        count = ingest_path(
            path,
            config,
            reset=args.reset,
            allow_hash_fallback=args.allow_hash_fallback,
        )
    except Exception as exc:
        print(f"Ingest failed (need Ollama embed model?): {exc}", file=sys.stderr)
        return 2
    print(f"Ingested {count} chunks into {config['rag']['persist_dir']}")
    return 0


def cmd_retag_patterns(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    try:
        tagged, total = retag_patterns(config, batch_size=args.batch_size)
    except Exception as exc:
        print(f"Retag failed: {exc}", file=sys.stderr)
        return 2
    print(f"Pattern tags on {tagged}/{total} chunks (metadata only; embeddings unchanged)")
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    pgn_path = _resolve_existing(args.pgn)
    if pgn_path is None:
        print(f"PGN not found: {args.pgn}", file=sys.stderr)
        return 1

    depth = args.depth or int(config.get("analyze_depth", 18))
    threshold = args.threshold or int(config.get("critical_cp_threshold", 120))
    game = load_game(path=pgn_path, game_index=args.game_index)

    try:
        with StockfishEngine(path=config.get("stockfish_path", "stockfish"), depth=depth) as engine:
            moments = find_critical_moments(game, engine, threshold_cp=threshold)
    except FileNotFoundError:
        print(
            "Stockfish not found. Install stockfish and/or set stockfish_path in configs/default.yaml",
            file=sys.stderr,
        )
        return 2
    except Exception as exc:
        print(f"Engine error: {exc}", file=sys.stderr)
        return 2

    commentaries: list[Commentary] = []
    for moment in moments:
        passages = []
        if not args.no_rag:
            try:
                passages = retrieve_passages(moment.features, config)
            except Exception as exc:
                print(f"RAG warning: {exc}", file=sys.stderr)
                passages = []
        if args.no_llm:
            from chess_coach.comment import engine_only_fallback

            commentaries.append(engine_only_fallback(moment, passages))
        else:
            commentaries.append(explain(moment, passages, config, allow_fallback=True))

    out_path = args.out if args.out.is_absolute() else Path.cwd() / args.out
    headers = {key: game.headers.get(key, "") for key in game.headers.keys()}
    write_report(out_path, headers, moments, commentaries, also_json=args.json)
    print(f"Wrote {out_path} ({len(moments)} critical moments)")
    return 0


def cmd_sections(args: argparse.Namespace) -> int:
    path = _resolve_existing(args.path)
    if path is None:
        print(f"Path not found: {args.path}", file=sys.stderr)
        return 1
    if path.is_file():
        from chess_coach.sections_init import detect_and_write_sections_yaml

        written = detect_and_write_sections_yaml(
            path,
            force=args.force,
            min_body_chars=args.min_body,
        )
        if written is None:
            print(f"No sections detected for {path.name}")
            return 1
        print(f"Wrote {written}")
        return 0
    results = init_sections_for_dir(path, force=args.force, min_body_chars=args.min_body)
    ok = 0
    for book, sidecar, status in results:
        if sidecar is None:
            print(f"SKIP {book.name}: {status}")
        else:
            ok += 1
            print(f"OK   {book.name} -> {sidecar.name} ({status})")
    print(f"Wrote/kept {ok}/{len(results)} section sidecars")
    return 0 if ok else 1


def cmd_chapter(args: argparse.Namespace) -> int:
    from chess_coach.logutil import log

    config = load_config(args.config)
    book_path = _resolve_existing(args.book)
    if book_path is None:
        print(f"Book not found: {args.book}", file=sys.stderr)
        return 1
    scheme = None if args.scheme == "auto" else args.scheme
    log("chapter cmd: book=%s", book_path.name)
    if args.list_sections:
        sections = list_book_sections(
            book_path,
            scheme=scheme,
            min_body_chars=args.min_body,
        )
        if not sections:
            print("No sections detected. Try --scheme game or lower --min-body.")
            return 1
        print(f"Detected scheme: {sections[0].scheme} ({len(sections)} sections)")
        for section in sections:
            preview = re.sub(r"\s+", " ", section.body[:120]).strip()
            print(f"  [{section.number}] {section.title}  ({len(section.body)} chars)  {preview}...")
        return 0

    chapter_key: str | int = args.chapter
    if isinstance(chapter_key, str) and chapter_key.isdigit():
        chapter_key = int(chapter_key)
    try:
        book_name, title, body = load_chapter(
            book_path,
            chapter_key,
            scheme=scheme,
            min_body_chars=args.min_body,
        )
    except Exception as exc:
        print(f"Chapter load failed: {exc}", file=sys.stderr)
        return 1
    citations = extract_citations(body, book=book_name, chapter=title)
    print(f"Book: {book_name}")
    print(f"Section: {title}")
    print(f"Citations found: {len(citations)} (book order — first listed = first in section)")
    for i, cite in enumerate(citations[:20], start=1):
        print(
            f"  {i}. {cite.white} vs {cite.black}, {cite.year}"
            f"{(' / ' + cite.event) if cite.event else ''} "
            f"[{len(cite.notes)} book move notes]"
        )
    if len(citations) > 20:
        print(f"  ... +{len(citations) - 20} more")
    if args.dry_run:
        return 0 if citations else 1

    out_dir = args.out if args.out.is_absolute() else resolve_path(args.out)
    html_dir = args.html_dir if args.html_dir.is_absolute() else resolve_path(args.html_dir)
    log(
        "Starting walkthrough max_games=%d rag=%s llm=%s depth=%s",
        args.max_games,
        not args.no_rag,
        not args.no_llm,
        args.depth,
    )
    results = walkthrough_chapter(
        book_path,
        config,
        chapter=chapter_key,
        out_dir=out_dir,
        viewer_dir=html_dir,
        max_games=args.max_games,
        use_rag=not args.no_rag,
        use_llm=not args.no_llm,
        depth=args.depth,
        threshold=args.threshold,
        scheme=scheme,
        min_body_chars=args.min_body,
        citations=citations,
    )
    ok = 0
    missing = 0
    chapter_book = None
    for result in results:
        cite = result.citation
        if result.chapter_book_html:
            chapter_book = result.chapter_book_html
        if result.missing_payload is not None:
            missing += 1
            print(f"MISSING {cite.white} vs {cite.black} {cite.year}: {'; '.join(result.errors)}")
            if result.attempts:
                print(f"  tried: {', '.join(result.attempts)}")
            print(f"  HTML: {result.html_path}")
            continue
        if result.errors:
            print(f"FAIL {cite.white} vs {cite.black} {cite.year}: {'; '.join(result.errors)}")
            continue
        ok += 1
        src = ""
        if result.fetch and result.fetch.hit:
            src = f" gid={result.fetch.hit.gid}"
        print(
            f"OK {cite.white} vs {cite.black} {cite.year}{src} "
            f"book_notes={result.book_notes_applied} critical={result.moments}"
        )
        print(f"  PGN: {result.annotated_pgn}")
        print(f"  HTML: {result.html_path}")
    if chapter_book:
        print(f"CHAPTER BOOK: {chapter_book}")
    write_scid_import_readme(out_dir)
    return 0 if (ok or missing) else 1


def cmd_masters_index(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    masters = config.get("masters") or {}
    pgn_dir = args.pgn_dir or Path(masters.get("pgn_dir", "data/masters/pgn"))
    index_path = args.index or Path(masters.get("index_path", "data/masters/index.sqlite"))
    if not pgn_dir.is_absolute():
        pgn_dir = resolve_path(pgn_dir)
    if not index_path.is_absolute():
        index_path = resolve_path(index_path)
    db = LocalMastersDB(index_path=index_path, pgn_dir=pgn_dir)
    if args.fix_surnames:
        try:
            n = db.fix_surnames()
        except Exception as exc:
            print(f"masters-index --fix-surnames failed: {exc}", file=sys.stderr)
            return 2
        print(f"Repaired surnames on {n} rows → {index_path}")
        return 0
    if args.no_reset and index_path.exists():
        print(f"Index already exists: {index_path}", file=sys.stderr)
        return 1
    try:
        total = db.build_index(pgn_dir, reset=not args.no_reset)
    except Exception as exc:
        print(f"masters-index failed: {exc}", file=sys.stderr)
        return 2
    print(f"Indexed {total} games → {index_path}")
    return 0 if total else 1


def cmd_scrape(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    out_dir = args.out if args.out.is_absolute() else resolve_path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []

    if args.gid or args.white or args.black:
        if args.gid:
            with ChessgamesClient() as client:
                try:
                    pgn = client.fetch_pgn(args.gid)
                    path = out_dir / f"cg_{args.gid}.pgn"
                    path.write_text(pgn if pgn.endswith("\n") else pgn + "\n", encoding="utf-8")
                    print(f"Saved {path}")
                    write_scid_import_readme(out_dir)
                    return 0
                except Exception as exc:
                    print(f"Chessgames gid fetch failed: {exc}", file=sys.stderr)
                    return 2
        if not args.white or not args.black:
            print("Master search needs --white and --black (optional --year)", file=sys.stderr)
            return 1
        fetch = fetch_master_game(
            args.white,
            args.black,
            year=args.year,
            event_hint=args.event,
            config=config,
            out_dir=out_dir,
        )
        if fetch is None:
            print("No master hit (local + Chessgames)", file=sys.stderr)
            return 1
        print(f"Saved {fetch.path} (gid={fetch.hit.gid} event={fetch.hit.event})")
        write_scid_import_readme(out_dir)
        return 0

    if args.lichess_user:
        results.append(scrape_lichess_user(args.lichess_user, out_dir, max_games=args.max))
    if args.game_id:
        results.append(scrape_lichess_game_ids(args.game_id, out_dir))
    if args.chesscom_user:
        if args.year is None or args.month is None:
            print("--chesscom-user requires --year and --month", file=sys.stderr)
            return 1
        results.append(
            scrape_chesscom_month(
                args.chesscom_user,
                args.year,
                args.month,
                out_dir,
                max_games=args.max,
            )
        )
    if args.masters_play:
        results.append(scrape_masters_opening(args.masters_play, out_dir, max_games=args.max))
    if args.url:
        results.append(scrape_pgn_url(args.url, out_dir))
    if not results:
        db = masters_db_from_config(config)
        local_note = ""
        if db is not None:
            local_note = f" Local index: {db.game_count()} games @ {db.index_path}."
        print(
            "Prefer: --white/--black/--year (local masters, then Chessgames)."
            f"{local_note} "
            "Legacy: --lichess-user, --game-id, --chesscom-user, --masters-play, --url",
            file=sys.stderr,
        )
        return 1
    total = 0
    for result in results:
        print(summarize(result))
        total += len(result.saved)
    write_scid_import_readme(out_dir)
    print(f"Archive dir: {out_dir} ({total} new files)")
    return 0 if total else 1


def cmd_annotate(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    pgn_path = _resolve_existing(args.pgn)
    if pgn_path is None:
        print(f"PGN not found: {args.pgn}", file=sys.stderr)
        return 1
    out_pgn = args.out
    if out_pgn is None:
        out_pgn = resolve_path(Path("data/annotated") / f"{pgn_path.stem}_annotated.pgn")
    elif not out_pgn.is_absolute():
        out_pgn = Path.cwd() / out_pgn
    try:
        game, moments, _ = annotate_pgn_file(
            pgn_path,
            config,
            out_pgn,
            game_index=args.game_index,
            use_rag=not args.no_rag,
            use_llm=not args.no_llm,
            depth=args.depth,
            threshold=args.threshold,
        )
    except Exception as exc:
        print(f"Annotate failed: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote annotated PGN {out_pgn} ({len(moments)} critical moments)")
    html_path = args.html
    if html_path is None:
        html_path = resolve_path(Path("data/viewer_out") / f"{pgn_path.stem}.html")
    elif not html_path.is_absolute():
        html_path = Path.cwd() / html_path
    write_viewer(out_pgn, html_path)
    write_scid_import_readme(out_pgn.parent)
    print(f"Wrote HTML visualizer {html_path}")
    print("Open annotated PGN in Scid vs PC to browse with board GUI.")
    _ = game
    return 0


def cmd_visualize(args: argparse.Namespace) -> int:
    pgn_path = _resolve_existing(args.pgn)
    if pgn_path is None:
        print(f"PGN not found: {args.pgn}", file=sys.stderr)
        return 1
    out = args.out if args.out.is_absolute() else Path.cwd() / args.out
    try:
        write_viewer(pgn_path, out)
    except Exception as exc:
        print(f"Visualize failed: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {out}")
    return 0


def cmd_ontology(args: argparse.Namespace) -> int:
    from chess_coach.ontology.cards import format_pattern_cards
    from chess_coach.ontology.detect import detect_pattern_ids
    from chess_coach.ontology.load import load_ontology

    config = load_config(args.config)
    ont_dir = (config.get("ontology") or {}).get("dir")
    catalog = load_ontology(ont_dir)
    if args.fen:
        ids = detect_pattern_ids(args.fen, eco=args.eco, opening=args.opening, ontology_dir=ont_dir)
        print(f"Detected ({len(ids)}): {', '.join(ids) or '(none)'}")
        if args.cards and ids:
            print(format_pattern_cards(ids, ontology_dir=ont_dir))
        return 0
    print(f"{len(catalog)} patterns in {ont_dir or 'data/ontology/patterns'}")
    for pid in sorted(catalog):
        p = catalog[pid]
        print(f"  {pid:40}  {p.label}  [{p.phase}/{p.family}]")
    if args.cards:
        print()
        print(format_pattern_cards(sorted(catalog), hops=0, limit=len(catalog), ontology_dir=ont_dir))
    return 0


def cmd_refresh_notes(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    pgn_dir = args.pgn_dir if args.pgn_dir.is_absolute() else resolve_path(args.pgn_dir)
    html_dir = args.html_dir if args.html_dir.is_absolute() else resolve_path(args.html_dir)
    chapter_book = args.chapter_book
    if chapter_book is not None and not chapter_book.is_absolute():
        chapter_book = resolve_path(chapter_book)
    use_rag = bool(args.rag)
    use_llm = bool(args.llm)

    if args.html_only:
        from chess_coach.book_walkthrough import _load_chapter_book_meta
        import chess

        if chapter_book is None:
            cands = list(html_dir.glob("*_chapter_book.html"))
            if not cands:
                print(f"No chapter book in {html_dir}", file=sys.stderr)
                return 1
            chapter_book = max(cands, key=lambda p: p.stat().st_size)
        meta = _load_chapter_book_meta(chapter_book)
        if not meta:
            print(f"Could not parse {chapter_book}", file=sys.stderr)
            return 1
        entries: list = []
        for g in meta["games"]:
            if g.get("missing"):
                entries.append(
                    {
                        "missing": True,
                        "matchup": g.get("matchup") or "Unknown",
                        "subtitle": g.get("subtitle") or "",
                        "date": g.get("date") or "",
                        "book": g.get("book") or meta.get("book") or "",
                        "chapter": g.get("chapter") or meta.get("chapter") or "",
                        "plies": [],
                        "startFen": g.get("startFen") or chess.STARTING_FEN,
                        "missingInfo": g.get("missingInfo") or {},
                    }
                )
                continue
            src = g.get("sourcePgn") or ""
            path = pgn_dir / src
            if path.exists():
                entries.append(path)
        write_chapter_book(
            entries,
            chapter_book,
            book=str(meta.get("book") or ""),
            chapter=str(meta.get("chapter") or ""),
        )
        print(f"Rebuilt UI/engine assets: {chapter_book}")
        print("Serve from data/viewer_out/bookwalk (hard refresh).")
        return 0

    out = refresh_bookwalk_dir(
        pgn_dir,
        html_dir,
        config,
        use_rag=use_rag,
        use_llm=use_llm,
        depth=args.depth,
        chapter_html=chapter_book,
    )
    if out is None:
        print("Refresh failed", file=sys.stderr)
        return 1
    print(f"Refreshed notes + chapter book: {out}")
    print("Serve from data/viewer_out/bookwalk and hard-refresh the page.")
    return 0


def cmd_study_push(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    lichess = config.get("lichess") or {}
    resolved: list[Path] = []
    for raw in args.paths:
        path = _resolve_existing(raw)
        if path is None:
            print(f"Path not found: {raw}", file=sys.stderr)
            return 1
        resolved.append(path)
    visibility = args.visibility or str(lichess.get("visibility") or "unlisted")
    delay = args.delay if args.delay is not None else float(lichess.get("delay_s") or 0.35)
    try:
        result = push_annotated_pgns(
            resolved,
            token=args.token,
            study_name=args.name,
            study_id=args.study_id,
            visibility=visibility,
            orientation=args.orientation,
            per_chapter=not args.batch,
            delay_s=delay,
            include_raw=args.include_raw,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"study-push failed: {exc}", file=sys.stderr)
        return 1
    if args.dry_run:
        print(f"Would push {len(result.chapters)} chapter(s) to study {result.study_id}:")
        for chapter in result.chapters:
            print(f"  - {chapter.name}")
        return 0
    print(f"Study: {result.url}")
    print(f"Chapters imported: {len(result.chapters)}")
    for chapter in result.chapters:
        print(f"  - {chapter.name} ({chapter.id})")
    if result.errors:
        for err in result.errors:
            print(f"warning: {err}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "preflight":
        return cmd_preflight(args)
    if args.command == "ingest":
        return cmd_ingest(args)
    if args.command == "retag-patterns":
        return cmd_retag_patterns(args)
    if args.command == "analyze":
        return cmd_analyze(args)
    if args.command == "sections":
        return cmd_sections(args)
    if args.command == "masters-index":
        return cmd_masters_index(args)
    if args.command == "chapter":
        return cmd_chapter(args)
    if args.command == "scrape":
        return cmd_scrape(args)
    if args.command == "annotate":
        return cmd_annotate(args)
    if args.command == "visualize":
        return cmd_visualize(args)
    if args.command == "refresh-notes":
        return cmd_refresh_notes(args)
    if args.command == "ontology":
        return cmd_ontology(args)
    if args.command == "study-push":
        return cmd_study_push(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
