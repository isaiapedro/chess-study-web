from __future__ import annotations

import html
import json
import os
import re
import urllib.request
from pathlib import Path

import chess
import chess.pgn

from chess_coach.ocr_chess import clean_book_note

STOCKFISH_RELEASE = "https://github.com/nmrugg/stockfish.js/releases/download/v18.0.0"
STOCKFISH_JS = "stockfish-18-lite-single.js"
STOCKFISH_WASM = "stockfish-18-lite-single.wasm"
LIVE_DEPTH = 22

CHESS_JS_CDN = "https://cdnjs.cloudflare.com/ajax/libs/chess.js/0.10.3/chess.min.js"

_EXPLORE_CSS = """
    .moves .explore {
      display: inline-flex; align-items: center; gap: 0.12rem;
      margin: 0 0.15rem; padding: 0.1rem 0.28rem;
      border: 1.5px solid var(--explore);
      background: color-mix(in srgb, var(--explore) 16%, transparent);
      border-radius: 5px; vertical-align: middle;
    }
    .moves button.explore-move {
      background: transparent; border: none; color: var(--explore);
      padding: 0.08rem 0.2rem; font: inherit; cursor: pointer; font-weight: 700;
    }
    .moves button.explore-move:hover { color: var(--ink); }
    .moves button.explore-move.active {
      color: #041412; background: var(--explore); border-radius: 3px;
    }
    .moves .explore-mark { color: var(--explore); font-size: 0.8em; font-weight: 700; padding: 0 0.05rem; }
    .move-legend .lg.explore i {
      border-radius: 2px; border: 1.5px solid var(--explore);
      background: color-mix(in srgb, var(--explore) 35%, transparent);
    }
    .explore-select {
      box-shadow: inset 0 0 0 3px var(--explore) !important;
    }
    .legal-dot, .legal-capture { position: relative; }
    .legal-dot::after {
      content: "";
      position: absolute; left: 50%; top: 50%;
      width: 22%; height: 22%;
      margin: -11% 0 0 -11%;
      border-radius: 50%;
      background: color-mix(in srgb, var(--explore) 55%, transparent);
      pointer-events: none; z-index: 2;
    }
    .legal-capture::after {
      content: "";
      position: absolute; inset: 6%;
      border: 3px solid color-mix(in srgb, var(--explore) 70%, transparent);
      border-radius: 50%;
      pointer-events: none; z-index: 2;
    }
    #board { touch-action: manipulation; user-select: none; -webkit-user-select: none; }
    #board img { pointer-events: none; }
"""

_ICON_SVG = (
    '<svg class="ico" viewBox="0 0 24 24" width="1em" height="1em" '
    'aria-hidden="true" focusable="false">'
    '<path fill="currentColor" d="{d}"/></svg>'
)
_MOVE_ICONS = {
    "start": _ICON_SVG.format(
        d="M5 5h2.75v14H5V5zm4.25 7L19.5 5.2v13.6L9.25 12z"
    ),
    "prev": _ICON_SVG.format(d="M15.5 5.5 8 12l7.5 6.5 1.6-1.85L11.7 12l5.4-4.65L15.5 5.5z"),
    "next": _ICON_SVG.format(d="M8.5 5.5 6.9 7.35 12.3 12 6.9 16.65 8.5 18.5 16 12 8.5 5.5z"),
    "end": _ICON_SVG.format(
        d="M4.5 5.2 14.75 12 4.5 18.8V5.2zM16.25 5H19v14h-2.75V5z"
    ),
    "flip": _ICON_SVG.format(
        d="M7.2 4.8v2.3A5.9 5.9 0 0 0 4 12c0 2.5 1.5 4.7 3.7 5.6l1-2.15A3.7 3.7 0 0 1 6.2 12c0-1.7 1.1-3.1 2.7-3.6v2.2L12.5 7.2 7.2 4.8zm9.6 14.4v-2.3A5.9 5.9 0 0 0 20 12c0-2.5-1.5-4.7-3.7-5.6l-1 2.15A3.7 3.7 0 0 1 17.8 12c0 1.7-1.1 3.1-2.7 3.6v-2.2l-3.6 3.4 5.3 3.4z"
    ),
}


def ensure_stockfish_assets(assets_dir: Path) -> Path:
    """Download Stockfish 18 lite-single WASM next to viewer pages (once)."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    for name in (STOCKFISH_JS, STOCKFISH_WASM):
        dest = assets_dir / name
        if dest.exists() and dest.stat().st_size > 10_000:
            continue
        url = f"{STOCKFISH_RELEASE}/{name}"
        tmp = dest.with_suffix(dest.suffix + ".part")
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(dest)
    return assets_dir


def ensure_textbook_badge(out_html: Path) -> Path:
    """Copy textbook-chess.gif beside chapter HTML for book-move badge."""
    dest = out_html.parent / "textbook-chess.gif"
    src = Path(__file__).with_name("assets") / "textbook-chess.gif"
    if src.exists() and (
        not dest.exists() or dest.stat().st_size != src.stat().st_size
    ):
        dest.write_bytes(src.read_bytes())
    return dest


def ensure_book_mark_badges(out_html: Path) -> None:
    """Copy Tenor-style ! / ?! / ? / ?? badge GIFs beside the HTML."""
    assets = Path(__file__).with_name("assets")
    for name in (
        "chess-great-move.gif",
        "chess-inaccuracy.gif",
        "chess-mistake.gif",
        "chess-blunder.gif",
    ):
        src = assets / name
        dest = out_html.parent / name
        if src.exists() and (
            not dest.exists() or dest.stat().st_size != src.stat().st_size
        ):
            dest.write_bytes(src.read_bytes())


def _worker_url_for(out_html: Path, assets_dir: Path | None = None) -> str:
    """
    Always place engine assets beside the HTML (…/bookwalk/stockfish/) so
    Worker URL is stockfish/….js regardless of which folder hosts http.server.
    """
    local_dir = out_html.parent / "stockfish"
    ensure_stockfish_assets(local_dir)
    # Also keep shared copy under viewer_out/stockfish for older links
    if assets_dir is not None and assets_dir.resolve() != local_dir.resolve():
        try:
            ensure_stockfish_assets(assets_dir)
        except OSError:
            pass
    return f"stockfish/{STOCKFISH_JS}"


def _extract_vars_blocks(comment: str) -> tuple[str, list[str]]:
    """Pull [Vars:…] blocks with nested brackets; return (comment_without_vars, vars)."""
    variations: list[str] = []
    if not comment:
        return "", variations
    out = comment
    built: list[str] = []
    i = 0
    lower = out.lower()
    while i < len(out):
        at = lower.find("[vars:", i)
        if at < 0:
            built.append(out[i:])
            break
        built.append(out[i:at])
        depth = 0
        j = at
        while j < len(out):
            if out[j] == "[":
                depth += 1
            elif out[j] == "]":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        block = out[at:j]
        if block.lower().startswith("[vars:") and block.endswith("]"):
            inner = block[len("[Vars:") : -1].strip()
            if inner:
                variations.extend(
                    clean_book_note(v) for v in inner.split(";") if clean_book_note(v)
                )
        i = j
    cleaned = re.sub(r"\s+", " ", "".join(built)).strip()
    return cleaned, variations


def _split_layers(comment: str) -> tuple[str, str, list[str]]:
    comment, variations = _extract_vars_blocks(comment)
    book = engine = ""
    if " | " in comment and ("[Book" in comment or "[Engine" in comment):
        parts = comment.split(" | ")
        book = " ".join(p for p in parts if p.startswith("[Book"))
        engine = " ".join(p for p in parts if p.startswith("[Engine"))
    elif comment.startswith("[Book"):
        book = comment
    elif comment.startswith("[Engine"):
        engine = comment
    book = clean_book_note(book)
    engine = clean_book_note(engine)
    return book, engine, variations


def _nag_glyphs(nags: list[int]) -> str:
    mapping = {
        1: "!",
        2: "?",
        3: "!!",
        4: "??",
        5: "!?",
        6: "?!",
    }
    return "".join(mapping.get(n, "") for n in nags)


def _variation_sans(parent: chess.pgn.GameNode, board_before: chess.Board) -> list[str]:
    """Serialize non-mainline children as SAN lines for the sidebar."""
    lines: list[str] = []
    if not parent.variations:
        return lines
    main = parent.variation(0)
    for var in parent.variations[1:]:
        work = board_before.copy()
        bits: list[str] = []
        cur: chess.pgn.GameNode | None = var
        steps = 0
        while cur is not None and cur.move is not None and steps < 10:
            try:
                bits.append(work.san(cur.move))
                work.push(cur.move)
            except ValueError:
                break
            cur = cur.variation(0) if cur.variations else None
            steps += 1
        if bits:
            lines.append(" ".join(bits))
    _ = main
    return lines


def _collect_plies(game: chess.pgn.Game) -> list[dict]:
    from chess_coach.variations import serialize_forks_from_parent

    plies: list[dict] = []
    board = game.board()
    node: chess.pgn.GameNode = game
    ply = 0
    while node.variations:
        forks = serialize_forks_from_parent(node, board)
        next_node = node.variation(0)
        ply += 1
        san = board.san(next_node.move)
        fen_before = board.fen()
        uci = next_node.move.uci()
        fullmove = board.fullmove_number
        side = "white" if board.turn == chess.WHITE else "black"
        pgn_vars = _variation_sans(node, board)
        board.push(next_node.move)
        comment = next_node.comment or ""
        book, engine, text_vars = _split_layers(comment)
        variations = list(dict.fromkeys([*pgn_vars, *text_vars]))
        nags = sorted(int(n) for n in next_node.nags)
        plies.append(
            {
                "ply": ply,
                "san": san,
                "uci": uci,
                "fen_before": fen_before,
                "fen": board.fen(),
                "comment": clean_book_note(comment),
                "book": book,
                "engine": engine,
                "variations": variations,
                "forks": forks,
                "nags": nags,
                "glyphs": _nag_glyphs(nags),
                "side": side,
                "fullmove": fullmove,
            }
        )
        node = next_node
    return plies


def _pretty_book(raw: str) -> str:
    """Turn a slug/filename-ish book name into a readable title."""
    name = (raw or "").strip()
    name = re.sub(r"\.(pdf|epub|txt)$", "", name, flags=re.I)
    if "_" in name or "-" in name:
        name = name.replace("_", " ").replace("-", " ")
    name = re.sub(r"\s+", " ", name).strip()
    if name and name == name.lower():
        name = name.title()
    return name


def _book_from_headers(game: chess.pgn.Game) -> tuple[str, str]:
    """(book title, chapter) from PGN headers written by book_walkthrough."""
    book = game.headers.get("Book", "")
    annotator = game.headers.get("Annotator", "")
    if not book and annotator.startswith("Book:"):
        book = annotator[len("Book:") :].split(" + ")[0]
    chapter = game.headers.get("BookChapter", "")
    return _pretty_book(book), chapter.strip()


def _start_book_comment(game: chess.pgn.Game) -> str:
    book, _engine, _vars = _split_layers(game.comment or "")
    return book


def build_game_payload(game: chess.pgn.Game, title: str | None = None) -> dict:
    white = game.headers.get("White", "?")
    black = game.headers.get("Black", "?")
    result = game.headers.get("Result", "*")
    eco = game.headers.get("ECO", "")
    opening = game.headers.get("Opening", "")
    event = game.headers.get("Event", "")
    date = game.headers.get("Date", "")
    annotator = game.headers.get("Annotator", "")
    book, chapter = _book_from_headers(game)
    matchup = f"{white} vs {black}"
    if book and chapter:
        heading = f"{book} — {chapter}"
    elif book:
        heading = book
    else:
        heading = title or matchup
    sub_bits = [matchup]
    year = (date or "").split(".")[0]
    if year and year not in {"?", "????"}:
        sub_bits.append(year)
    if event and event not in {"?", "-"}:
        sub_bits.append(event)
    if result and result != "*":
        sub_bits.append(result)
    if eco or opening:
        sub_bits.append(" ".join(b for b in (eco, opening) if b))
    return {
        "title": heading,
        "subtitle": " · ".join(sub_bits),
        "matchup": matchup,
        "white": white,
        "black": black,
        "result": result,
        "eco": eco,
        "opening": opening,
        "event": event,
        "date": date,
        "annotator": annotator,
        "book": book,
        "chapter": chapter,
        "startFen": game.board().fen(),
        "startBook": _start_book_comment(game),
        "plies": _collect_plies(game),
    }


def render_html(
    game: chess.pgn.Game,
    title: str | None = None,
    *,
    engine_worker_url: str = STOCKFISH_JS,
    live_depth: int = LIVE_DEPTH,
) -> str:
    payload = build_game_payload(game, title=title)
    heading = payload["title"]
    matchup = payload["matchup"]
    subtitle = payload["subtitle"]
    data_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    doc_title = f"{heading} · {matchup}" if payload.get("book") else heading

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(doc_title)}</title>
  <link rel="stylesheet"
    href="https://cdn.jsdelivr.net/npm/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.css" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link rel="stylesheet"
    href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" />
  <style>
    /* Chess Wrapped tokens — design/identity/chess-wrapped/README.md */
    :root {{
      --bg: #000000;
      --panel: #121212;
      --panel-soft: #181818;
      --ink: #ffffff;
      --muted: #a1a1a1;
      --accent: #D32531;
      --accent-dim: #a0000f;
      --line: rgba(255, 255, 255, 0.07);
      --rim: rgba(255, 255, 255, 0.14);
      --book: #ede7d3;
      --book-fill: rgba(237, 231, 211, 0.16);
      --other-fill: rgba(0, 132, 210, 0.20);
      --explore: #34C759;
      --engine: #0084d2;
      --good: #34C759;
      --bad: #D32531;
      --board-light: #C7C7C7;
      --board-dark: #71828F;
      --board: min(70vh, 640px);
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ height: 100%; }}
    html {{ background: var(--bg); font-size: 18px; }}
    body {{
      margin: 0;
      font-family: Inter, system-ui, -apple-system, "Segoe UI", sans-serif;
      background: radial-gradient(120% 78% at 50% 0%, #101010 0%, #000000 60%) no-repeat var(--bg);
      color: var(--ink);
      line-height: 1.5;
      -webkit-font-smoothing: antialiased;
    }}
    #board .white-1e1d7 {{ background-color: var(--board-light); color: var(--board-dark); }}
    #board .black-3c85d {{ background-color: var(--board-dark); color: var(--board-light); }}
    #board .board-b72b1 {{ border: none; }}
    #board .notation-322f9 {{
      font-family: Inter, sans-serif; font-size: 0.625rem; font-weight: 500; opacity: 0.85;
    }}
    .shell {{ max-width: 1320px; margin: 0 auto; padding: 1.4rem 1.4rem 2rem; }}

    /* ---- header: book + chapter as title, players as subtitle ---- */
    header {{ margin-bottom: 1.1rem; }}
    .brand {{
      display: inline-flex; align-items: center; gap: 0.45rem;
      font-family: ui-monospace, Menlo, monospace;
      font-size: 0.72rem; letter-spacing: 0.18em; text-transform: uppercase;
      color: var(--accent); opacity: 0.9; margin-bottom: 0.35rem;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(1.4rem, 2.6vw, 2.1rem);
      letter-spacing: -0.02em;
      line-height: 1.15;
    }}
    .sub {{
      margin: 0.3rem 0 0;
      color: var(--muted);
      font-size: 0.95rem;
      font-family: ui-monospace, Menlo, monospace;
      letter-spacing: 0.01em;
    }}

    /* ---- stage ---- */
    .stage {{
      display: grid;
      grid-template-columns: min-content minmax(320px, 1fr);
      gap: 1.6rem;
      align-items: start;
    }}
    @media (max-width: 1040px) {{
      :root {{ --board: min(calc(100vw - 2.5rem), 560px); }}
      .stage {{ grid-template-columns: 1fr; }}
      .shell {{ padding: 1rem 0.9rem 1.5rem; }}
    }}
    @media (max-width: 560px) {{
      :root {{ --board: min(calc(100vw - 1.6rem), 100vw); }}
      .shell {{ padding: 0.7rem 0.65rem 1.2rem; }}
      .board-frame {{ gap: 0.4rem; }}
      .eval-bar {{ width: 12px; }}
      .deck {{
        display: flex; flex-direction: column; align-items: stretch;
        gap: 0.55rem; margin-top: 0.9rem; width: 100%;
      }}
      .deck .spacer {{ display: none; }}
      .deck .eval-chip {{
        justify-content: center; width: 100%;
      }}
      .move-keys {{
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        width: 100%;
        gap: 0.4rem;
        margin: 0 auto;
      }}
      .move-keys button {{
        width: 100%;
        min-height: 3.5rem;
        padding: 0.7rem 0.2rem;
        border-radius: 12px;
        font-size: 1.25rem;
      }}
      .move-keys button.primary {{
        font-size: 1.35rem;
      }}
      .move-keys .ico {{
        width: 1.7em; height: 1.7em;
      }}
      .move-keys button.primary .ico {{
        width: 1.9em; height: 1.9em;
      }}
      .coach-actions button {{
        min-height: 2.75rem;
        padding: 0.65rem 0.9rem;
        font-size: 1.05rem;
      }}
    }}

    .board-frame {{
      display: flex;
      gap: 0.6rem;
      align-items: stretch;
      max-width: 100%;
    }}
    #board {{
      width: var(--board);
      max-width: 100%;
      border-radius: 10px;
      overflow: hidden;
      box-shadow: 0 22px 48px rgba(0,0,0,0.55);
      cursor: ns-resize;
    }}
    #board .highlight {{ box-shadow: inset 0 0 0 4px rgba(224,139,60,0.75); }}

    .eval-bar {{
      width: 14px; border-radius: 7px;
      background: #0e0c0a; border: 1px solid var(--line);
      position: relative; overflow: hidden; flex-shrink: 0;
    }}
    .eval-white {{
      position: absolute; left: 0; right: 0; bottom: 0;
      height: 50%; background: linear-gradient(180deg, #fffaf0, #ded4c2);
      transition: height 0.25s ease;
    }}

    /* ---- deck under board ---- */
    .deck {{
      margin-top: 0.75rem;
      display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;
    }}
    .move-keys {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      width: 100%;
      max-width: calc(var(--board) + 20px);
      gap: 0.4rem;
      align-items: stretch;
    }}
    .move-keys button {{
      display: inline-flex; align-items: center; justify-content: center;
      line-height: 1; width: 100%; min-width: 0;
    }}
    .move-keys .ico {{
      width: 1.35em; height: 1.35em; display: block; flex-shrink: 0;
    }}
    button {{
      font: inherit; cursor: pointer;
      background: var(--panel-soft); color: var(--ink);
      border: 1px solid var(--line); border-radius: 8px;
      padding: 0.4rem 0.75rem;
      transition: transform 0.08s ease, border-color 0.15s ease, background 0.15s ease;
    }}
    button:hover:not(:disabled) {{ border-color: var(--accent); transform: translateY(-1px); }}
    button:active:not(:disabled) {{ transform: translateY(0); }}
    button:disabled {{ opacity: 0.35; cursor: default; }}
    button.primary {{
      background: linear-gradient(180deg, #e79a4f, #c06f26);
      border-color: #b06a26; color: #201408; font-weight: 700;
    }}
    .spacer {{ flex: 1; }}
    .eval-chip {{
      font-family: ui-monospace, Menlo, monospace;
      font-variant-numeric: tabular-nums;
      display: inline-flex; align-items: baseline; gap: 0.5rem;
      padding: 0.32rem 0.6rem; border-radius: 8px;
      background: var(--panel); border: 1px solid var(--line);
    }}
    .eval-chip b {{ font-size: 1.05rem; color: var(--accent); }}
    .eval-chip #evalDetail {{ font-size: 0.75rem; color: var(--muted); }}
    .book-hint {{
      display: none;
      width: 0.55rem; height: 0.55rem;
      border-radius: 2px;
      background: var(--book-fill);
      box-shadow: 0 0 0 1px color-mix(in srgb, #f4ecff 35%, var(--book-fill));
      flex-shrink: 0; align-self: center;
    }}
    .book-hint.on {{ display: inline-block; }}
    .dot {{ width: 7px; height: 7px; border-radius: 50%; background: var(--muted); }}
    .dot.ok {{ background: var(--good); }}
    .dot.warn {{ background: var(--bad); }}

    /* ---- move strip ---- */
    .moves {{
      margin-top: 0.6rem;
      max-width: calc(var(--board) + 20px);
      display: flex; gap: 0.15rem; align-items: center;
      overflow-x: auto; overflow-y: hidden;
      padding: 0.35rem 0.2rem 0.6rem;
      scrollbar-width: thin;
      font-family: ui-monospace, "Cascadia Code", Menlo, monospace;
      font-size: 0.85rem;
      white-space: nowrap;
    }}
    .moves .num {{ color: var(--muted); padding-left: 0.35rem; }}
    .moves button.move {{
      background: transparent; border: 1px solid transparent; border-radius: 4px;
      color: var(--ink); padding: 0.12rem 0.32rem; position: relative;
    }}
    .moves button.move.has-book {{
      background: var(--book-fill);
      color: #f4ecff; font-weight: 700; border-color: transparent;
    }}
    .moves button.move.has-other {{
      background: var(--other-fill);
      color: #1a1005; font-weight: 700; border-color: transparent;
    }}
    .moves button.move.active {{
      outline: 2px solid var(--accent); outline-offset: 1px;
      background: var(--accent); color: #1d1206; font-weight: 700;
    }}
    .moves .fork {{
      display: inline-flex; align-items: center; gap: 0.12rem;
      margin: 0 0.15rem; padding: 0.1rem 0.25rem;
      border: 1px dashed color-mix(in srgb, var(--muted) 55%, transparent);
      border-radius: 4px; vertical-align: middle;
    }}
    .moves button.fork-move {{
      background: transparent; border: none; color: var(--muted);
      padding: 0.08rem 0.2rem; font: inherit; cursor: pointer;
    }}
    .moves button.fork-move:hover {{ color: var(--ink); }}
    .moves button.fork-move.active {{
      color: #1d1206; background: var(--accent); border-radius: 3px; font-weight: 700;
    }}
    .moves .fork-mark {{ color: var(--muted); font-size: 0.75em; padding: 0 0.1rem; }}
{_EXPLORE_CSS}
    button.play-line {{
      display: block; width: 100%; text-align: left; cursor: pointer;
      background: transparent; border: 1px solid var(--line); border-radius: 6px;
      color: var(--ink); padding: 0.35rem 0.5rem; margin: 0.25rem 0;
      font-family: ui-monospace, Menlo, monospace; font-size: 0.86rem;
    }}
    button.play-line:hover {{ border-color: var(--accent); }}
    button.play-line .kind {{ color: var(--accent); font-size: 0.72rem; margin-right: 0.4rem; }}
    .move-legend {{
      display: flex; gap: 0.9rem; align-items: center; flex-wrap: wrap;
      color: var(--muted); font-size: 0.75rem; margin: 0.15rem 0 0;
      font-family: ui-monospace, Menlo, monospace;
    }}
    .move-legend .lg {{ display: inline-flex; align-items: center; gap: 0.35rem; }}
    .move-legend .lg i {{ display: inline-block; width: 10px; height: 10px; }}
    .move-legend .lg.book i {{
      border-radius: 2px; background: var(--book-fill);
    }}
    .move-legend .lg.engine i {{
      border-radius: 2px; background: var(--other-fill); transform: none;
      width: 10px; height: 10px;
    }}
    .hint {{ color: var(--muted); font-size: 0.78rem; margin: 0.25rem 0 0; }}

    /* ---- coach panel ---- */
    .coach {{ position: sticky; top: 1rem; display: flex; flex-direction: column; gap: 0.8rem; }}
    .coach-head {{ display: flex; align-items: center; gap: 0.7rem; }}
    .avatar {{
      width: 46px; height: 46px; flex-shrink: 0; border-radius: 50%;
      display: grid; place-items: center; font-size: 1.5rem;
      background: linear-gradient(145deg, #3a2c1c, #211a13);
      border: 1px solid var(--line);
    }}
    .coach-who {{ line-height: 1.2; }}
    .coach-who strong {{ display: block; font-size: 1rem; }}
    .coach-who span {{ color: var(--muted); font-size: 0.85rem; font-family: ui-monospace, Menlo, monospace; }}

    .bubble {{
      position: relative;
      background: linear-gradient(180deg, #2e2519, #241d15);
      border: 1px solid #5a462b;
      border-left: 5px solid var(--book);
      border-radius: 14px;
      padding: 1rem 1.15rem;
      box-shadow: 0 14px 30px rgba(0,0,0,0.35);
      font-size: 1.2rem;
      line-height: 1.55;
      animation: pop 0.22s ease;
    }}
    .bubble::before {{
      content: ""; position: absolute; left: -11px; top: 20px;
      border: 7px solid transparent; border-right-color: var(--book);
    }}
    @keyframes pop {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
    .bubble .tag {{
      display: inline-block; margin-bottom: 0.45rem;
      font-family: ui-monospace, Menlo, monospace;
      font-size: 0.72rem; letter-spacing: 0.12em; text-transform: uppercase;
      color: #1d1206; background: var(--book);
      padding: 0.12rem 0.5rem; border-radius: 999px;
    }}
    .bubble.quiet {{
      border-color: var(--line); border-left-color: var(--line);
      background: var(--panel); color: var(--muted); font-style: italic; font-size: 1.05rem;
    }}
    .bubble.quiet::before {{ border-right-color: var(--line); }}

    details.aside-note {{
      background: var(--panel); border: 1px solid var(--line);
      border-radius: 10px; padding: 0.5rem 0.75rem;
    }}
    details.aside-note summary {{
      cursor: pointer; list-style: none;
      font-family: ui-monospace, Menlo, monospace;
      font-size: 0.76rem; letter-spacing: 0.08em; text-transform: uppercase;
      color: var(--engine);
    }}
    details.aside-note summary::-webkit-details-marker {{ display: none; }}
    details.aside-note[open] > summary {{ margin-bottom: 0.45rem; }}
    details.aside-note .body {{ font-size: 1.05rem; line-height: 1.5; color: var(--ink); }}
    .vars-list {{ margin: 0; padding-left: 1.1rem; }}
    .vars-list li {{ margin: 0.2rem 0; font-family: ui-monospace, Menlo, monospace; font-size: 0.95rem; }}
    .coach-actions {{ display: flex; gap: 0.5rem; flex-wrap: wrap; }}
    .noteprog {{
      font-family: ui-monospace, Menlo, monospace; font-size: 0.76rem;
      color: var(--muted); align-self: center;
    }}
    .note .para {{ display: block; margin: 0 0 0.65em; }}
    .note .para:last-child {{ margin-bottom: 0; }}
    .note .san {{
      font-family: ui-monospace, Menlo, monospace; font-weight: 600; letter-spacing: 0.01em;
    }}
    .note .fig {{
      display: inline-block; width: 1.1em; height: 1.1em;
      vertical-align: -0.2em; margin: 0 0.04em 0 0.02em;
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header>
      <div class="brand">♟ chess coach</div>
      <h1>{html.escape(heading)}</h1>
      <p class="sub">{html.escape(subtitle)}</p>
    </header>

    <main class="stage">
      <section>
        <div class="board-frame">
          <div class="eval-bar" title="White-POV eval"><div class="eval-white" id="evalWhite"></div></div>
          <div id="board"></div>
        </div>
        <div class="deck">
          <div class="move-keys" role="group" aria-label="Move controls">
            <button type="button" id="btnStart" aria-label="First move">{_MOVE_ICONS["start"]}</button>
            <button type="button" id="btnPrev" aria-label="Previous move">{_MOVE_ICONS["prev"]}</button>
            <button type="button" id="btnNext" class="primary" aria-label="Next move">{_MOVE_ICONS["next"]}</button>
            <button type="button" id="btnEnd" aria-label="Last move">{_MOVE_ICONS["end"]}</button>
            <button type="button" id="btnFlip" aria-label="Flip board">{_MOVE_ICONS["flip"]}</button>
          </div>
          <span class="spacer"></span>
          <span class="eval-chip"><i class="dot" id="engineDot"></i><b id="evalScore">—</b><span class="book-hint" id="bookHint" aria-hidden="true"></span><span id="evalDetail">warming up</span></span>
        </div>
        <div class="moves" id="moveList"></div>
        <p class="move-legend">
          <span class="lg book"><i></i> this book</span>
          <span class="lg engine"><i></i> engine / variants</span>
          <span class="lg explore"><i></i> your line</span>
        </p>
        <p class="hint">Tap a piece, then a square · tree moves stay on the line until you deviate · Esc exits</p>
      </section>

      <aside class="coach">
        <div class="coach-head">
          <div class="avatar">🧠</div>
          <div class="coach-who">
            <strong>Coach</strong>
            <span id="coachMove">Start position</span>
          </div>
        </div>
        <div id="notes"></div>
        <div class="coach-actions">
          <button type="button" id="btnPrevNote">↞ prev note</button>
          <button type="button" id="btnNextNote">next note ↠</button>
          <span class="noteprog" id="noteProg"></span>
        </div>
      </aside>
    </main>
  </div>

  <script type="application/json" id="game-data">{data_json}</script>
  <script src="https://cdn.jsdelivr.net/npm/jquery@3.7.1/dist/jquery.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/@chrisoakman/chessboardjs@1.0.0/dist/chessboard-1.0.0.min.js"></script>
  <script src="{CHESS_JS_CDN}"></script>
  <script>
(function () {{
  const game = JSON.parse(document.getElementById("game-data").textContent);
  const plies = game.plies || [];
  let idx = -1;
  let fork = null;
  let explore = null;
  let pendingFrom = null;
  let orientation = "white";
  let engine = null;
  let engineReady = false;
  let analyzeToken = 0;
  const LIVE_DEPTH = {live_depth};
  const ENGINE_WORKER_URL = {json.dumps(engine_worker_url)};

  const PIECE_THEME =
    "https://chessboardjs.com/img/chesspieces/wikipedia/{{piece}}.png";

  const board = Chessboard("board", {{
    position: game.startFen,
    orientation: orientation,
    pieceTheme: PIECE_THEME,
    showNotation: true,
    draggable: false,
  }});
  window.addEventListener("resize", () => {{ board.resize(); highlightLastMove(); }});

  const elScore = document.getElementById("evalScore");
  const elDetail = document.getElementById("evalDetail");
  const elWhite = document.getElementById("evalWhite");
  const elMove = document.getElementById("coachMove");
  const elNotes = document.getElementById("notes");
  const elList = document.getElementById("moveList");
  const elDot = document.getElementById("engineDot");
  const elProg = document.getElementById("noteProg");
  const elBoard = document.getElementById("board");
  const elBookHint = document.getElementById("bookHint");

  const noteIdx = [];
  for (let i = 0; i < plies.length; i++) {{
    if (hasNote(plies[i])) noteIdx.push(i);
  }}

  function hasNote(p) {{
    return Boolean(p && (p.book || p.engine || (p.forks && p.forks.length) || (p.variations && p.variations.length) || p.comment));
  }}

  function forkMoves() {{
    if (!fork) return null;
    const p = plies[fork.ply];
    return (p && p.forks && p.forks[fork.fi] && p.forks[fork.fi].moves) || null;
  }}

  function fenNow() {{
    if (explore) {{
      if (explore.depth < 0) return explore.baseFen;
      return explore.moves[Math.min(explore.depth, explore.moves.length - 1)].fen;
    }}
    const moves = forkMoves();
    if (moves) {{
      if (fork.depth < 0) return plies[fork.ply].fen_before;
      return moves[Math.min(fork.depth, moves.length - 1)].fen;
    }}
    return idx < 0 ? game.startFen : plies[idx].fen;
  }}

  function escapeHtml(s) {{
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }}

  function stripTag(text) {{
    let out = String(text || "");
    out = out.replace(/^\\[Book:[^\\]]*\\]\\s*/i, "");
    out = out.replace(/^\\[Engine\\/RAG\\]\\s*/i, "");
    let built = "";
    let i = 0;
    while (i < out.length) {{
      const lower = out.slice(i).toLowerCase();
      const at = lower.indexOf("[vars:");
      if (at < 0) {{
        built += out.slice(i);
        break;
      }}
      built += out.slice(i, i + at);
      let depth = 0;
      let j = i + at;
      for (; j < out.length; j++) {{
        if (out[j] === "[") depth++;
        else if (out[j] === "]") {{
          depth--;
          if (depth === 0) {{
            j++;
            break;
          }}
        }}
      }}
      i = j;
      built = built.replace(/\\s+$/, " ");
    }}
    return built.replace(/\\s+/g, " ").trim();
  }}


  function ocrCleanClient(text) {{
    let out = String(text || "").replace(/\u00a0/g, " ").replace(/[\u2018\u2019\u02bc]/g, "'").replace(/\\/g, "");
    out = out.replace(/0\s*-{1,3}\s*0\s*-{1,3}\s*0/g, "O-O-O").replace(/0\s*-{1,3}\s*0/g, "O-O");
    out = out.replace(/\b([NBRQK][a-h]?[1-8]?x?[a-h][1-8]|[a-h]x[a-h][1-8]|[a-h][1-8]|O-O-O|O-O)t\b/g, "$1+");
    out = out.replace(/\b([a-z]{2,}[a-egh])\+/g, "$1t");
    out = out.replace(/°1W|'l!|1!f\/|1!f|'!ti|'!t[ií]|'\(!i|'Wi|1W|lW|Yf\s*|f\?(?=[a-h])/g, "Q");
    out = out.replace(/(^|[^A-Za-z])W(?=x[gfh]|[gfh][1-8])/g, "$1K");
    out = out.replace(/(^|[^A-Za-z])W(?=x[a-e]|[a-e][1-8])/g, "$1Q");
    out = out.replace(/ltJ|l\/J|ll'l|lt'l|ltl'|lll|lil|liJ|llJ|l2J|4J|0\.J/g, "N");
    out = out.replace(/(^|[^A-Za-z0-9])J'(?=k[1-8]\b|[a-h][1-8]\b|x[a-h])/g, "$1N");
    out = out.replace(/\bNk([1-8])\b/g, "Nc$1");
    out = out.replace(/\bNkx(?=[a-h])/g, "Ncx");
    out = out.replace(/([!?]{{1,3}});[il1!]+;?/g, "$1");
    out = out.replace(/\b([NBRQK][a-h])\s*\?(?=[!?]|\s|$|[.;,)])/g, "$17");
    out = out.replace(/\bl0(?=[a-h1-8x])/g, "N");
    out = out.replace(/(^|[^A-Za-z0-9])ll\.(?=l?[a-h])/g, "$1N");
    out = out.replace(/\bN([a-h])\s+([1-8])\b/g, "N$1$2");
    out = out.replace(/\b([NBRQK])\s+([a-h][1-8])\b/g, "$1$2");
    out = out.replace(/\.!L?i/g, "B");
    out = out.replace(/&\.(?=[a-h])/g, "B");
    out = out.replace(/(^|[^A-Za-z0-9])&(?=[a-h])/g, "$1B");
    out = out.replace(/(\d+)\s*\.\s*\.?\s*i(?=[a-hx])/g, "$1.B");
    out = out.replace(/([a-h][1-8])\.(?=If\b)/g, "$1. ");
    out = out.replace(/\bBf\s+(?=\d)/g, "If ");
    out = out.replace(/\bBf(?=\d{{2}}\.)/g, "If ");
    out = out.replace(/\bI\/(?=\s*(?:\d|\.\.\.|[A-Za-z]|$))/g, "If ");
    out = out.replace(/\bIf(?=\d)/g, "If ");
    out = out.replace(/(^|[^A-Za-z0-9])\.?i(?=[a-h][1-8]\b|[a-h]x|x[a-h])/g, "$1B");
    out = out.replace(/:§:|El(?=[a-hx])/g, "R");
    out = out.replace(/l'hcl\b/g, "Rxc1").replace(/l'hc/g, "Rxc");
    out = out.replace(/l'kl\b/g, "Rc1").replace(/l'k([1-8])\b/g, "Rc$1");
    out = out.replace(/i'!|l"k|l'k|l'h/g, "R");
    out = out.replace(/(^|[^A-Za-z0-9])aa(?=[1-8]\b)/g, "$1Ra");
    out = out.replace(/\b([NBRQK])x?c[lI]\b/g, "$1xc1");
    out = out.replace(/\b([NBRQK])([a-h])[lI]\b/g, function (_m, p, f) {{ return p + f + "1"; }});
    out = out.replace(/(\d+\.)([NBRQK])/g, "$1 $2");
    out = out.replace(/([NBRQK][a-hx1-8+#=]+)(?=[NBRQK])/g, "$1 ");
    out = out.replace(/([NBRQK][a-hx1-8+#=]+)\.(?=[NBRQK])/g, "$1. ");
    return out.replace(/[ \t]+/g, " ").trim();
  }}

  function pieceFig(letter) {{
    const L = String(letter || "").toUpperCase();
    if ("KQRBN".indexOf(L) < 0) return escapeHtml(L);
    return '<img class="fig" src="' + PIECE_THEME.replace("{{piece}}", "w" + L) + '" alt="' + L + '">';
  }}

  function formatNoteHtml(raw) {{
    let text = ocrCleanClient(stripTag(raw));
    if (!text) return "";
    text = text.replace(/\\r\\n?/g, "\\n").replace(/[ \\t]+\\n/g, "\\n").replace(/\\n[ \\t]+/g, "\\n");
    text = text.replace(/\\b(Final\\s+remarks)\\s+(?=\\d+\\.\\s)/gi, "$1\\n\\n");
    if (!/\\n/.test(text)) {{
      text = text.replace(
        /(?:\\.(?!\\.)|(?<=[a-z]{{2}})[!?]+)\\s+(?=(?:The |This |White |Black |Better |Threatening |Followed |An interesting |A better |Not |Once |Again |His |In |After |Precision |Learning |Something |Creating |Preparing |Ignoring |Covering |Aiming |We |It |And as |For example))/g,
        function (m) {{ return m.replace(/\\s+$/, "") + "\\n\\n"; }}
      );
    }}
    text = text.replace(/\\n{{3,}}/g, "\\n\\n").trim();
    const blocks = text.split(/\\n\\n+/);
    const re = /(\d+\.(?:\.\.)?\s*)?(O-O-O|O-O|[NBRQK][a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#?!]*|[a-h]x[a-h][1-8](?:=[NBRQ])?[+#?!]*|[a-h][1-8](?:=[NBRQ])?[+#?!]*)/g;
    function formatInline(chunk) {{
      let out = "";
      let last = 0;
      let m;
      re.lastIndex = 0;
      const line = chunk.replace(/\\n/g, " ");
      while ((m = re.exec(line)) !== null) {{
        out += escapeHtml(line.slice(last, m.index));
        out += escapeHtml(m[1] || "");
        const san = m[2];
        if (san.indexOf("O-O") === 0) {{
          out += '<span class="san">' + escapeHtml(san) + "</span>";
        }} else if (/^[NBRQK]/.test(san)) {{
          out += pieceFig(san[0]) + '<span class="san">' + escapeHtml(san.slice(1)) + "</span>";
        }} else {{
          out += '<span class="san">' + escapeHtml(san) + "</span>";
        }}
        last = m.index + m[0].length;
      }}
      out += escapeHtml(line.slice(last));
      return out;
    }}
    if (blocks.length <= 1) return formatInline(text.replace(/\\n/g, " "));
    return blocks.map(function (b) {{
      return '<span class="para">' + formatInline(b) + "</span>";
    }}).join("");
  }}

  function moveLabel(p) {{
    return p.fullmove + (p.side === "white" ? "." : "...") + " " + p.san + (p.glyphs || "");
  }}

  function forkMoveLabel(m) {{
    return m.fullmove + (m.side === "white" ? "." : "...") + " " + m.san;
  }}

  function clearPending() {{
    pendingFrom = null;
    elBoard.querySelectorAll(".explore-select, .legal-dot, .legal-capture").forEach((el) => {{
      el.classList.remove("explore-select", "legal-dot", "legal-capture");
    }});
  }}

  function matchesUci(stored, from, to, promotion) {{
    if (!stored) return false;
    const u = String(stored).toLowerCase();
    const base = (from + to).toLowerCase();
    if (u.slice(0, 4) === base) {{
      if (u.length <= 4) return true;
      return u[4] === (promotion || "q");
    }}
    return false;
  }}

  function tryChessMove(fen, from, to) {{
    if (typeof Chess === "undefined" || from === to) return null;
    const ch = new Chess(fen);
    const fromPiece = ch.get(from);
    if (!fromPiece) return null;
    let legal = null;
    if (fromPiece.type === "k") {{
      const dest = ch.get(to);
      if (dest && dest.type === "r" && dest.color === fromPiece.color) {{
        const castles = ch.moves({{ square: from, verbose: true }}).filter((m) => m.flags.indexOf("k") >= 0 || m.flags.indexOf("q") >= 0);
        const castle = castles.find((m) => (m.flags.indexOf("q") >= 0 ? to[0] === "a" : to[0] === "h"));
        if (castle) legal = ch.move({{ from: castle.from, to: castle.to }});
      }}
    }}
    if (!legal) {{
      const isPromo = fromPiece.type === "p" && ((fromPiece.color === "w" && to[1] === "8") || (fromPiece.color === "b" && to[1] === "1"));
      legal = ch.move({{ from: from, to: to, promotion: isPromo ? "q" : undefined }});
    }}
    if (!legal) return null;
    return {{
      san: legal.san,
      uci: legal.from + legal.to + (legal.promotion || ""),
      fen: ch.fen(),
      fullmove: parseInt(fen.split(" ")[5], 10) || 1,
      side: legal.color === "w" ? "white" : "black",
      from: legal.from,
      to: legal.to,
      promotion: legal.promotion || "",
    }};
  }}

  function legalTargets(from) {{
    const ch = new Chess(fenNow());
    const targets = new Set();
    if (!ch.get(from)) return targets;
    const moves = ch.moves({{ square: from, verbose: true }});
    moves.forEach((m) => targets.add(m.to));
    const piece = ch.get(from);
    if (piece && piece.type === "k") {{
      moves.filter((m) => m.flags.indexOf("k") >= 0 || m.flags.indexOf("q") >= 0).forEach((castle) => {{
        targets.add((castle.flags.indexOf("q") >= 0 ? "a" : "h") + from[1]);
      }});
    }}
    return targets;
  }}

  function paintSelection(from) {{
    clearPending();
    pendingFrom = from;
    const cell = elBoard.querySelector(".square-" + from);
    if (cell) cell.classList.add("explore-select");
    legalTargets(from).forEach((sq) => {{
      const el = elBoard.querySelector(".square-" + sq);
      if (!el) return;
      el.classList.add(el.querySelector("img") ? "legal-capture" : "legal-dot");
    }});
  }}

  function followTreeMove(from, to, promotion) {{
    if (explore) {{
      const next = explore.moves[explore.depth + 1];
      if (next && matchesUci(next.uci, from, to, promotion)) {{
        stepExplore(1);
        return true;
      }}
      if (explore.depth >= 0) return false;
      const baseIdx = explore.baseIdx;
      explore = null;
      idx = baseIdx;
      const followed = followTreeMove(from, to, promotion);
      if (followed) return true;
      explore = {{ baseIdx: baseIdx, baseFen: (baseIdx < 0 ? game.startFen : plies[baseIdx].fen), moves: [], depth: -1 }};
      return false;
    }}
    if (fork) {{
      const moves = forkMoves() || [];
      const next = moves[fork.depth + 1];
      if (next && matchesUci(next.uci, from, to, promotion)) {{
        stepFork(1);
        return true;
      }}
      return false;
    }}
    const next = plies[idx + 1];
    if (next && matchesUci(next.uci, from, to, promotion)) {{
      goTo(idx + 1);
      return true;
    }}
    if (next) {{
      const forks = next.forks || [];
      for (let fi = 0; fi < forks.length; fi++) {{
        const first = (forks[fi].moves || [])[0];
        if (first && matchesUci(first.uci, from, to, promotion)) {{
          enterFork(idx + 1, fi, 0);
          return true;
        }}
      }}
    }}
    return false;
  }}

  function tryUserMove(from, to) {{
    const fen = fenNow();
    const record = tryChessMove(fen, from, to);
    if (!record) return false;
    clearPending();
    if (followTreeMove(record.from, record.to, record.promotion)) return true;
    if (!explore) {{
      explore = {{ baseIdx: idx, baseFen: fen, moves: [], depth: -1 }};
      fork = null;
    }} else if (explore.depth < explore.moves.length - 1) {{
      explore.moves = explore.moves.slice(0, explore.depth + 1);
    }}
    explore.moves.push(record);
    explore.depth = explore.moves.length - 1;
    board.position(record.fen, false);
    highlightLastMove();
    renderNotes();
    renderMoveList();
    setButtons();
    updateBookHint();
    requestEval();
    return true;
  }}

  function squareFromEvent(e) {{
    let el = e.target;
    while (el && el !== elBoard) {{
      const m = String(el.className || "").match(/square-([a-h][1-8])/);
      if (m) return m[1];
      el = el.parentElement;
    }}
    return null;
  }}

  function handleBoardPointer(e) {{
    if (e.type === "pointerdown" && e.pointerType === "mouse" && e.button !== 0) return;
    const sq = squareFromEvent(e);
    if (!sq || typeof Chess === "undefined") return;
    e.preventDefault();
    const ch = new Chess(fenNow());
    const piece = ch.get(sq);
    if (!pendingFrom) {{
      if (piece && piece.color === ch.turn()) paintSelection(sq);
      return;
    }}
    if (pendingFrom === sq) {{ clearPending(); return; }}
    const selPiece = ch.get(pendingFrom);
    const targets = legalTargets(pendingFrom);
    if (
      piece && piece.color === ch.turn() &&
      !(selPiece && selPiece.type === "k" && piece.type === "r" && targets.has(sq))
    ) {{
      paintSelection(sq);
      return;
    }}
    tryUserMove(pendingFrom, sq) || clearPending();
  }}

  function exitExplore() {{
    if (!explore) return;
    const base = explore.baseIdx;
    explore = null;
    clearPending();
    goTo(base);
  }}

  function stepExplore(dir) {{
    if (!explore) return false;
    const next = explore.depth + dir;
    if (next < -1) return true;
    if (next >= explore.moves.length) return true;
    explore.depth = next;
    board.position(fenNow(), false);
    highlightLastMove();
    renderNotes();
    renderMoveList();
    setButtons();
    updateBookHint();
    requestEval();
    return true;
  }}

  function highlightLastMove() {{
    const squares = elBoard.querySelectorAll(".highlight");
    squares.forEach((el) => el.classList.remove("highlight"));
    let uci = "";
    if (explore && explore.depth >= 0) uci = explore.moves[explore.depth].uci || "";
    else {{
      const moves = forkMoves();
      if (moves && fork.depth >= 0) uci = moves[Math.min(fork.depth, moves.length - 1)].uci || "";
      else if (idx >= 0) uci = plies[idx].uci || "";
    }}
    if (uci.length < 4) return;
    [uci.slice(0, 2), uci.slice(2, 4)].forEach((sq) => {{
      const el = elBoard.querySelector(".square-" + sq);
      if (el) el.classList.add("highlight");
    }});
  }}

  function enterFork(ply, fi, depth) {{
    if (!plies[ply] || !(plies[ply].forks || [])[fi]) return;
    explore = null;
    clearPending();
    fork = {{ ply: ply, fi: fi, depth: depth == null ? 0 : depth }};
    idx = ply;
    board.position(fenNow(), false);
    highlightLastMove();
    renderNotes();
    renderMoveList();
    setButtons();
    updateBookHint();
    requestEval();
  }}

  function exitFork() {{
    if (!fork) return;
    const ply = fork.ply;
    fork = null;
    goTo(ply);
  }}

  function stepFork(dir) {{
    const moves = forkMoves();
    if (!moves) return false;
    const next = fork.depth + dir;
    if (next < 0) {{ exitFork(); return true; }}
    if (next >= moves.length) return true;
    fork = {{ ply: fork.ply, fi: fork.fi, depth: next }};
    board.position(fenNow(), true);
    setTimeout(highlightLastMove, 210);
    renderNotes();
    renderMoveList();
    setButtons();
    updateBookHint();
    requestEval();
    return true;
  }}

  function updateBookHint() {{
    const on = !fork && !explore && idx >= 0 && Boolean(plies[idx] && plies[idx].book);
    elBookHint.classList.toggle("on", on);
    elBookHint.setAttribute("aria-hidden", on ? "false" : "true");
    elBookHint.setAttribute("aria-label", on ? "Book note on this move" : "");
  }}

  function finishNotes() {{
    if (elBookScroll) elBookScroll.scrollTop = 0;
  }}
  function renderNotes() {{
    if (isMissing()) {{
      elMove.textContent = "";
      const info = game().missingInfo || {{}};
      elNotes.innerHTML = '<div class="note engine">' + escapeHtml(info.reason || "PGN unavailable.") + "</div>";
      finishNotes();
      return;
    }}
    if (explore) {{
      const cur = explore.depth < 0 ? null : explore.moves[explore.depth];
      elMove.textContent = cur ? ("your line · " + cur.san) : "your line";
      elNotes.innerHTML = '<div class="note book" style="border-color:var(--explore)">Try moves freely — not saved.</div>'
        + '<button type="button" class="play-line" id="btnExitExplore"><span class="kind">main</span>back to book line</button>';
      document.getElementById("btnExitExplore").onclick = () => exitExplore();
      finishNotes();
      return;
    }}
    if (fork) {{
      const p = plies()[fork.ply];
      const fk = p.forks[fork.fi];
      const moves = fk.moves || [];
      const cur = moves[Math.min(Math.max(fork.depth, 0), moves.length - 1)];
      elMove.textContent = (fk.kind || "line") + " · " + (cur ? cur.san : "?");
      elNotes.innerHTML = '<div class="note book">' + escapeHtml(fk.label || "Playable fork") + "</div>"
        + '<button type="button" class="play-line" id="btnExitFork"><span class="kind">main</span>back to '
        + escapeHtml(moveLabel(p)) + "</button>";
      document.getElementById("btnExitFork").onclick = () => exitFork();
      finishNotes();
      return;
    }}
    const p = idx < 0 ? null : plies()[idx];
    if (!p) {{
      elMove.textContent = "";
      elNotes.innerHTML = '<p class="empty">Tap a piece, then a square.</p>';
      finishNotes();
      return;
    }}
    const dots = p.side === "white" ? "." : "...";
    elMove.textContent = p.fullmove + dots + " " + p.san + (p.glyphs || "");
    let html = "";
    if (p.book) html += '<div class="note book">' + formatNoteHtml(p.book) + "</div>";
    if (p.engine) html += '<div class="note engine"><span class="tag">Engine</span>' + formatNoteHtml(p.engine) + "</div>";
    const forks = p.forks || [];
    if (forks.length) {{
      html += '<div class="note vars"><span class="tag">Forks</span>';
      forks.forEach((fk, fi) => {{
        const line = (fk.moves || []).map((m) => m.san).join(" ");
        html += '<button type="button" class="play-line" data-fi="' + fi + '"><span class="kind">'
          + escapeHtml(fk.kind || "line") + "</span>" + escapeHtml(line) + "</button>";
      }});
      html += "</div>";
    }}
    if (!html) html = '<p class="empty">No book note on this move.</p>';
    elNotes.innerHTML = html;
    elNotes.querySelectorAll("button.play-line[data-fi]").forEach((btn) => {{
      btn.addEventListener("click", () => enterFork(idx, Number(btn.dataset.fi), 0));
    }});
    finishNotes();
  }}

  function renderMoveList() {{
    let out = "";
    for (let i = 0; i < plies.length; i++) {{
      const p = plies[i];
      if (p.side === "white") out += '<span class="num">' + p.fullmove + ".</span>";
      const cls = ["move"];
      if (!fork && !explore && i === idx) cls.push("active");
      if ((fork && fork.ply === i) || (explore && explore.baseIdx === i)) cls.push("active");
      if (p.book) cls.push("has-book");
      else if (p.engine || (p.forks && p.forks.length) || (p.variations && p.variations.length) || (p.comment && !p.book)) cls.push("has-other");
      out += '<button type="button" class="' + cls.join(" ") + '" data-i="' + i + '">' +
        escapeHtml(p.san + (p.glyphs || "")) + "</button>";
      const forks = p.forks || [];
      forks.forEach((fk, fi) => {{
        out += '<span class="fork ' + escapeHtml(fk.kind || "") + '"><span class="fork-mark">(</span>';
        (fk.moves || []).forEach((m, di) => {{
          const fcls = ["fork-move"];
          if (fork && fork.ply === i && fork.fi === fi && fork.depth === di) fcls.push("active");
          out += '<button type="button" class="' + fcls.join(" ") + '" data-i="' + i +
            '" data-fi="' + fi + '" data-d="' + di + '">' + escapeHtml(m.san) + "</button>";
        }});
        out += '<span class="fork-mark">)</span></span>';
      }});
      if (explore && explore.baseIdx === i) {{
        out += '<span class="explore"><span class="explore-mark">[</span>';
        explore.moves.forEach((m, di) => {{
          const fcls = ["explore-move"];
          if (explore.depth === di) fcls.push("active");
          out += '<button type="button" class="' + fcls.join(" ") + '" data-d="' + di + '">' +
            escapeHtml(m.san) + "</button>";
        }});
        out += '<span class="explore-mark">]</span></span>';
      }}
    }}
    if (explore && explore.baseIdx < 0) {{
      out = '<span class="explore"><span class="explore-mark">[</span>';
      explore.moves.forEach((m, di) => {{
        const fcls = ["explore-move"];
        if (explore.depth === di) fcls.push("active");
        out += '<button type="button" class="' + fcls.join(" ") + '" data-d="' + di + '">' +
          escapeHtml(m.san) + "</button>";
      }});
      out += '<span class="explore-mark">]</span></span>' + out;
    }}
    elList.innerHTML = out || '<span class="num">no moves</span>';
    elList.querySelectorAll("button.move").forEach((btn) => {{
      btn.addEventListener("click", () => {{ explore = null; fork = null; clearPending(); goTo(Number(btn.dataset.i)); }});
    }});
    elList.querySelectorAll("button.fork-move").forEach((btn) => {{
      btn.addEventListener("click", () => enterFork(Number(btn.dataset.i), Number(btn.dataset.fi), Number(btn.dataset.d)));
    }});
    elList.querySelectorAll("button.explore-move").forEach((btn) => {{
      btn.addEventListener("click", () => {{
        if (!explore) return;
        explore.depth = Number(btn.dataset.d);
        board.position(fenNow(), false);
        highlightLastMove();
        renderNotes();
        renderMoveList();
        setButtons();
        updateBookHint();
        requestEval();
      }});
    }});
    const active = elList.querySelector("button.move.active, button.fork-move.active, button.explore-move.active");
    if (active) active.scrollIntoView({{ block: "nearest", inline: "center" }});
  }}

  function setButtons() {{
    if (explore) {{
      document.getElementById("btnStart").disabled = explore.depth < 0;
      document.getElementById("btnPrev").disabled = explore.depth < 0;
      document.getElementById("btnNext").disabled = explore.depth >= explore.moves.length - 1;
      document.getElementById("btnEnd").disabled = explore.depth >= explore.moves.length - 1;
    }} else {{
      const moves = forkMoves();
      if (moves) {{
        document.getElementById("btnStart").disabled = false;
        document.getElementById("btnPrev").disabled = false;
        document.getElementById("btnNext").disabled = fork.depth >= moves.length - 1;
        document.getElementById("btnEnd").disabled = fork.depth >= moves.length - 1;
      }} else {{
        document.getElementById("btnStart").disabled = idx < 0;
        document.getElementById("btnPrev").disabled = idx < 0;
        document.getElementById("btnNext").disabled = idx >= plies.length - 1;
        document.getElementById("btnEnd").disabled = idx >= plies.length - 1;
      }}
    }}
    document.getElementById("btnNextNote").disabled = !noteIdx.some((i) => i > idx);
    document.getElementById("btnPrevNote").disabled = !noteIdx.some((i) => i < idx);
  }}

  function goTo(next) {{
    explore = null;
    fork = null;
    clearPending();
    const target = Math.max(-1, Math.min(plies.length - 1, next));
    const animate = Math.abs(target - idx) === 1;
    idx = target;
    board.position(fenNow(), animate);
    setTimeout(highlightLastMove, animate ? 210 : 0);
    renderNotes();
    renderMoveList();
    setButtons();
    updateBookHint();
    requestEval();
  }}

  function step(dir) {{
    if (explore && stepExplore(dir)) return;
    if (fork && stepFork(dir)) return;
    goTo(idx + dir);
  }}

  function jumpNote(dir) {{
    explore = null;
    fork = null;
    clearPending();
    const pool = dir > 0 ? noteIdx.filter((i) => i > idx) : noteIdx.filter((i) => i < idx).reverse();
    if (pool.length) goTo(pool[0]);
  }}

  function cpToBar(cp) {{
    const clamped = Math.max(-800, Math.min(800, cp));
    return Math.max(2, Math.min(98, 50 + (clamped / 800) * 50));
  }}

  function showEval(info) {{
    if (info.mate !== null && info.mate !== undefined) {{
      const m = info.mate;
      elScore.textContent = (m > 0 ? "M" : "-M") + Math.abs(m);
      elWhite.style.height = m > 0 ? "96%" : "4%";
    }} else if (info.cp !== null && info.cp !== undefined) {{
      const pawns = info.cp / 100;
      elScore.textContent = (pawns >= 0 ? "+" : "") + pawns.toFixed(2);
      elWhite.style.height = cpToBar(info.cp) + "%";
    }} else {{
      elScore.textContent = "—";
      elWhite.style.height = "50%";
    }}
    elDetail.textContent = "depth " + (info.depth || "?");
  }}

  function requestEval() {{
    if (!engine || !engineReady) return;
    const token = ++analyzeToken;
    const fen = fenNow();
    const depthGo = window.__sfDepth || LIVE_DEPTH;
    engine.postMessage("stop");
    engine.postMessage("position fen " + fen);
    engine.postMessage("go depth " + depthGo);
    engine.onmessage = function (ev) {{
      if (token !== analyzeToken) return;
      const line = typeof ev.data === "string" ? ev.data : "";
      if (!line.startsWith("info") || line.indexOf(" score ") === -1) return;
      if (line.indexOf(" multipv ") !== -1 && line.indexOf(" multipv 1") === -1) return;
      const depthM = / depth (\\d+)/.exec(line);
      const mateM = / score mate (-?\\d+)/.exec(line);
      const cpM = / score cp (-?\\d+)/.exec(line);
      const depth = depthM ? Number(depthM[1]) : 0;
      if (depth < Math.min(10, depthGo)) return;
      let cp = null;
      let mate = null;
      if (mateM) mate = Number(mateM[1]);
      else if (cpM) cp = Number(cpM[1]);
      if (fen.split(" ")[1] === "b") {{
        if (cp !== null) cp = -cp;
        if (mate !== null) mate = -mate;
      }}
      showEval({{ cp: cp, mate: mate, depth: depth }});
    }};
  }}

  function bootEngine() {{
    if (!ENGINE_WORKER_URL) return;
    const mobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent)
      || (navigator.maxTouchPoints > 1 && Math.min(window.innerWidth, window.innerHeight) < 900);
    const hashMb = mobile ? 16 : 64;
    const depthCap = mobile ? Math.min(LIVE_DEPTH, 14) : LIVE_DEPTH;
    try {{
      const jsUrl = new URL(ENGINE_WORKER_URL, window.location.href).href;
      const wasmUrl = jsUrl.replace(/\\.js(\\?.*)?$/i, ".wasm$1");
      engine = new Worker(jsUrl + "#" + encodeURIComponent(wasmUrl));
    }} catch (e) {{
      return;
    }}
    engine.onmessage = function (ev) {{
      const line = typeof ev.data === "string" ? ev.data : "";
      if (line.indexOf("uciok") !== -1) {{
        engine.postMessage("setoption name Hash value " + hashMb);
        engine.postMessage("isready");
      }} else if (line.indexOf("readyok") !== -1) {{
        engineReady = true;
        window.__sfDepth = depthCap;
        requestEval();
      }}
    }};
    engine.onerror = function (ev) {{
      console.error("Stockfish worker error", ev);
    }};
    setTimeout(function () {{ engine.postMessage("uci"); }}, 0);
  }}

  document.querySelectorAll(".toc-item").forEach((b) => b.classList.toggle("active", Number(b.dataset.g) === gIdx));
    const tocActive = document.querySelector('.toc-item[data-g="' + gIdx + '"]');
    if (tocActive) tocActive.scrollIntoView({{ behavior: "smooth", block: "nearest" }});
    board.position(fenNow(), false);
    try {{ board.resize(); miniBoard.resize(); }} catch (e) {{}}
    renderNotes(); renderMoveList(); setButtons(); updateBookHint();
    if (miss) {{
      elScore.textContent = "—";
      elDetail.textContent = "";
      elWhite.style.height = "50%";
      if (engineReady) {{}}
    }} else {{
      requestEval();
    }}
  }}

  function renderNotes() {{
    if (isMissing()) {{
      const info = game().missingInfo || {{}};
      elMove.textContent = "Missing PGN · " + game().matchup;
      let html = '<div class="note engine"><span class="tag">Unavailable</span>'
        + escapeHtml(info.reason || "No method could supply a playable PGN.") + "</div>";
      const tries = info.attempts || [];
      if (tries.length) {{
        html += '<div class="note vars"><span class="tag">Tried</span><ul class="vars-list">';
        tries.forEach((t) => {{ html += "<li>" + escapeHtml(t) + "</li>"; }});
        html += "</ul></div>";
      }}
      html += '<p class="empty">Book notes detected: ' + (info.notes_count || 0) + "</p>";
      if (info.context_preview) {{
        html += '<div class="note book"><span class="tag">Book context preview</span>'
          + escapeHtml(info.context_preview) + "</div>";
      }}
      elNotes.innerHTML = html;
      return;
    }}
    if (explore) {{
      const cur = explore.depth < 0 ? null : explore.moves[explore.depth];
      elMove.textContent = cur ? ("your line · " + cur.san) : "your line · branch point";
      let html = '<div class="note book" style="border-color:var(--explore)"><span class="tag" style="background:var(--explore);color:#041412">Your line</span>';
      html += "Ephemeral — not saved. Teal solid = your tries; dashed gray = PGN forks.</div>";
      html += '<button type="button" class="play-line" id="btnExitExplore"><span class="kind">main</span>back to book line</button>';
      elNotes.innerHTML = html;
      document.getElementById("btnExitExplore").onclick = () => exitExplore();
      return;
    }}
    if (fork) {{
      const p = plies()[fork.ply];
      const fk = p.forks[fork.fi];
      const moves = fk.moves || [];
      const cur = moves[Math.min(Math.max(fork.depth, 0), moves.length - 1)];
      elMove.textContent = (fk.kind || "line") + " fork · " + (cur ? cur.san : "?");
      let html = '<div class="note book"><span class="tag">Playable ' + escapeHtml(fk.kind || "line") + "</span>"
        + escapeHtml(fk.label || "") + "</div>";
      html += '<p class="empty">← → walk fork · Esc back to main line</p>';
      html += '<button type="button" class="play-line" id="btnExitFork"><span class="kind">main</span>back to '
        + escapeHtml(moveLabel(p)) + "</button>";
      elNotes.innerHTML = html;
      document.getElementById("btnExitFork").onclick = () => exitFork();
      return;
    }}
    const p = idx < 0 ? null : plies()[idx];
    if (!p) {{
      elMove.textContent = "Start position · " + game().matchup;
      elNotes.innerHTML = '<p class="empty">Tap a piece, then a square. Tree moves stay on the line until you deviate.</p>';
      return;
    }}
    const dots = p.side === "white" ? "." : "...";
    elMove.innerHTML = p.fullmove + dots + " " + escapeHtml(p.san) + (p.glyphs ? ' <span style="color:var(--accent)">' + escapeHtml(p.glyphs) + "</span>" : "");
    let html = "";
    if (p.book) html += '<div class="note book">' + formatNoteHtml(p.book) + "</div>";
    if (p.engine) html += '<div class="note engine"><span class="tag">Engine / RAG</span>' + formatNoteHtml(p.engine) + "</div>";
    const forks = p.forks || [];
    if (forks.length) {{
      html += '<div class="note vars"><span class="tag">Playable forks</span>';
      forks.forEach((fk, fi) => {{
        const line = (fk.moves || []).map((m) => m.san).join(" ");
        html += '<button type="button" class="play-line" data-fi="' + fi + '"><span class="kind">'
          + escapeHtml(fk.kind || "line") + "</span>" + escapeHtml(line) + "</button>";
      }});
      html += "</div>";
    }}
    if (!html) html = '<p class="empty">No stored annotation — drag a piece to try your own line.</p>';
    elNotes.innerHTML = html;
    elNotes.querySelectorAll("button.play-line[data-fi]").forEach((btn) => {{
      btn.addEventListener("click", () => enterFork(idx, Number(btn.dataset.fi), 0));
    }});
  }}

  function renderMoveList() {{
    if (isMissing()) {{
      elList.innerHTML = '<span class="empty">No moves — PGN missing</span>';
      return;
    }}
    let html = "";
    plies().forEach((p, i) => {{
      if (p.side === "white") html += p.fullmove + ".";
      const cls = ["move"];
      if ((!fork && !explore && i === idx) || (fork && fork.ply === i) || (explore && explore.baseIdx === i)) cls.push("active");
      if (p.book) cls.push("has-book");
      else if (p.engine || (p.forks && p.forks.length) || (p.variations && p.variations.length) || (p.comment && !p.book)) cls.push("has-other");
      html += '<button type="button" class="' + cls.join(" ") + '" data-i="' + i + '">' + escapeHtml(p.san + (p.glyphs||"")) + "</button> ";
      (p.forks || []).forEach((fk, fi) => {{
        html += '<span class="fork ' + escapeHtml(fk.kind || "") + '"><span class="fork-mark">(</span>';
        (fk.moves || []).forEach((m, di) => {{
          const fcls = ["fork-move"];
          if (fork && fork.ply === i && fork.fi === fi && fork.depth === di) fcls.push("active");
          html += '<button type="button" class="' + fcls.join(" ") + '" data-i="' + i + '" data-fi="' + fi + '" data-d="' + di + '">' + escapeHtml(m.san) + "</button>";
        }});
        html += '<span class="fork-mark">)</span></span> ';
      }});
      if (explore && explore.baseIdx === i) {{
        html += '<span class="explore"><span class="explore-mark">[</span>';
        explore.moves.forEach((m, di) => {{
          const fcls = ["explore-move"];
          if (explore.depth === di) fcls.push("active");
          html += '<button type="button" class="' + fcls.join(" ") + '" data-d="' + di + '">' + escapeHtml(m.san) + "</button>";
        }});
        html += '<span class="explore-mark">]</span></span> ';
      }}
    }});
    if (explore && explore.baseIdx < 0) {{
      let head = '<span class="explore"><span class="explore-mark">[</span>';
      explore.moves.forEach((m, di) => {{
        const fcls = ["explore-move"];
        if (explore.depth === di) fcls.push("active");
        head += '<button type="button" class="' + fcls.join(" ") + '" data-d="' + di + '">' + escapeHtml(m.san) + "</button>";
      }});
      head += '<span class="explore-mark">]</span></span> ';
      html = head + html;
    }}
    elList.innerHTML = html || '<span class="empty">No moves</span>';
    elList.querySelectorAll("button.move").forEach((btn) => btn.addEventListener("click", () => {{ explore = null; fork = null; clearPending(); goTo(Number(btn.dataset.i)); }}));
    elList.querySelectorAll("button.fork-move").forEach((btn) => btn.addEventListener("click", () => enterFork(Number(btn.dataset.i), Number(btn.dataset.fi), Number(btn.dataset.d))));
    elList.querySelectorAll("button.explore-move").forEach((btn) => btn.addEventListener("click", () => {{
      if (!explore) return;
      explore.depth = Number(btn.dataset.d);
      board.position(fenNow(), false);
      renderNotes(); renderMoveList(); setButtons(); updateBookHint(); requestEval();
    }}));
  }}

  function setButtons() {{
    const miss = isMissing();
    if (explore) {{
      document.getElementById("btnStart").disabled = explore.depth < 0;
      document.getElementById("btnPrev").disabled = explore.depth < 0;
      document.getElementById("btnNext").disabled = explore.depth >= explore.moves.length - 1;
      document.getElementById("btnEnd").disabled = explore.depth >= explore.moves.length - 1;
      return;
    }}
    const moves = forkMoves();
    if (moves) {{
      document.getElementById("btnStart").disabled = false;
      document.getElementById("btnPrev").disabled = false;
      document.getElementById("btnNext").disabled = fork.depth >= moves.length - 1;
      document.getElementById("btnEnd").disabled = fork.depth >= moves.length - 1;
    }} else {{
      document.getElementById("btnStart").disabled = miss || idx < 0;
      document.getElementById("btnPrev").disabled = miss || idx < 0;
      document.getElementById("btnNext").disabled = miss || idx >= plies().length - 1;
      document.getElementById("btnEnd").disabled = miss || idx >= plies().length - 1;
    }}
  }}

  function goTo(next) {{
    if (isMissing()) return;
    explore = null;
    fork = null;
    clearPending();
    idx = Math.max(-1, Math.min(plies().length - 1, next));
    board.position(fenNow(), false);
    renderNotes(); renderMoveList(); setButtons(); updateBookHint(); requestEval();
  }}

  function jumpNote(dir) {{
    if (isMissing()) return;
    explore = null;
    fork = null;
    clearPending();
    const list = plies();
    if (!list.length) return;
    let i = idx;
    while (true) {{
      i += dir;
      if (i < 0 || i >= list.length) break;
      const p = list[i];
      if (p.book || p.engine || (p.forks && p.forks.length) || p.comment) {{ goTo(i); return; }}
    }}
  }}

  function cpToBar(cp) {{
    const clamped = Math.max(-800, Math.min(800, cp));
    return Math.max(2, Math.min(98, 50 + (clamped / 800) * 50));
  }}
  function showEval(info) {{
    if (info.mate != null) {{
      elScore.textContent = (info.mate > 0 ? "M" : "-M") + Math.abs(info.mate);
      elWhite.style.height = info.mate > 0 ? "96%" : "4%";
    }} else if (info.cp != null) {{
      const pawns = info.cp / 100;
      elScore.textContent = (pawns >= 0 ? "+" : "") + pawns.toFixed(2);
      elWhite.style.height = cpToBar(info.cp) + "%";
    }} else {{
      elScore.textContent = "—"; elWhite.style.height = "50%";
    }}
    elDetail.textContent = "d" + (info.depth || "?") + (info.pv ? " · " + info.pv : "");
  }}

  function requestEval() {{
    if (isMissing()) return;
    if (!engine || !engineReady) return;
    const token = ++analyzeToken;
    const fen = fenNow();
    const depthGo = window.__sfDepth || LIVE_DEPTH;
    engine.postMessage("stop");
    engine.postMessage("position fen " + fen);
    engine.postMessage("go depth " + depthGo);
    engine.onmessage = function (ev) {{
      if (token !== analyzeToken) return;
      const line = typeof ev.data === "string" ? ev.data : "";
      if (!line.startsWith("info") || line.indexOf(" score ") === -1) return;
      if (line.indexOf(" multipv ") !== -1 && line.indexOf(" multipv 1") === -1) return;
      const depthM = / depth (\\d+)/.exec(line);
      const mateM = / score mate (-?\\d+)/.exec(line);
      const cpM = / score cp (-?\\d+)/.exec(line);
      const pvM = / pv (.+)$/.exec(line);
      const depth = depthM ? Number(depthM[1]) : 0;
      if (depth < Math.min(10, depthGo)) return;
      let cp = mateM ? null : (cpM ? Number(cpM[1]) : null);
      let mate = mateM ? Number(mateM[1]) : null;
      if (fen.split(" ")[1] === "b") {{ if (cp!=null) cp=-cp; if (mate!=null) mate=-mate; }}
      showEval({{ cp, mate, depth, pv: pvM ? pvM[1].split(/\\s+/).slice(0,6).join(" ") : "" }});
    }};
  }}

  function bootEngine() {{
    if (!ENGINE_WORKER_URL) {{

      return;
    }}
    const mobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent)
      || (navigator.maxTouchPoints > 1 && Math.min(window.innerWidth, window.innerHeight) < 900);
    const hashMb = mobile ? 16 : 64;
    const depthCap = mobile ? Math.min(LIVE_DEPTH, 14) : LIVE_DEPTH;

    try {{
      const jsUrl = new URL(ENGINE_WORKER_URL, window.location.href).href;
      const wasmUrl = jsUrl.replace(/\\.js(\\?.*)?$/i, ".wasm$1");
      engine = new Worker(jsUrl + "#" + encodeURIComponent(wasmUrl));
    }} catch (e) {{

      return;
    }}
    let gotAny = false;
    engine.onmessage = function (ev) {{
      gotAny = true;
      const line = typeof ev.data === "string" ? ev.data : "";
      if (line.indexOf("uciok") !== -1) {{
        engine.postMessage("setoption name Hash value " + hashMb);
        engine.postMessage("isready");
      }} else if (line.indexOf("readyok") !== -1) {{
        engineReady = true;
        window.__sfDepth = depthCap;

        requestEval();
      }}
    }};
    engine.onerror = function (ev) {{
      const hint = ENGINE_WORKER_URL + " (wasm next to .js; serve from bookwalk/)";

      console.error("Stockfish worker error", ev);
    }};
    setTimeout(function () {{
      if (!engineReady && !gotAny) {{

      }}
    }}, 12000);
    setTimeout(function () {{ engine.postMessage("uci"); }}, 0);
  }}

  document.querySelectorAll(".toc-item").forEach((b) => b.addEventListener("click", () => setGame(Number(b.dataset.g))));
  document.getElementById("btnStart").onclick = () => {{
    if (explore) {{
      explore.depth = -1; board.position(fenNow(), false);
      renderNotes(); renderMoveList(); setButtons(); updateBookHint(); requestEval(); return;
    }}
    explore = null; fork = null; clearPending(); goTo(-1);
  }};
  document.getElementById("btnPrev").onclick = () => step(-1);
  document.getElementById("btnNext").onclick = () => step(1);
  document.getElementById("btnEnd").onclick = () => {{
    if (explore) {{
      explore.depth = explore.moves.length - 1; board.position(fenNow(), false);
      renderNotes(); renderMoveList(); setButtons(); updateBookHint(); requestEval(); return;
    }}
    if (fork) {{
      const moves = forkMoves() || [];
      enterFork(fork.ply, fork.fi, moves.length - 1);
    }} else goTo(plies().length - 1);
  }};
  document.getElementById("btnFlip").onclick = () => {{ orientation = orientation === "white" ? "black" : "white"; board.orientation(orientation); }};

  let wheelAcc = 0;
  let wheelLock = 0;
  const elDock = document.getElementById("boardDock");
  function onWheelMoves(e) {{
    if (isMissing()) return;
    e.preventDefault();
    const now = Date.now();
    if (now - wheelLock < 90) return;
    wheelAcc += e.deltaY;
    if (Math.abs(wheelAcc) < 24) return;
    step(wheelAcc > 0 ? 1 : -1);
    wheelAcc = 0;
    wheelLock = now;
  }}
  elBoard.addEventListener("wheel", onWheelMoves, {{ passive: false }});
  elDock.addEventListener("wheel", onWheelMoves, {{ passive: false }});
  elBoard.addEventListener("pointerup", handleBoardPointer);

  if (window.IntersectionObserver && elBoardRow) {{
    const io = new IntersectionObserver((entries) => {{
      const entry = entries[0];
      const show = entry && !entry.isIntersecting;
      elMiniWrap.classList.toggle("on", show);
      elMiniWrap.setAttribute("aria-hidden", show ? "false" : "true");
      if (show) {{
        try {{
          miniBoard.position(fenNow(), false);
          miniBoard.resize();
        }} catch (e) {{}}
      }}
    }}, {{ threshold: 0.12, rootMargin: "-8px 0px 0px 0px" }});
    io.observe(elBoardRow);
  }}
  elMiniWrap.addEventListener("click", () => {{
    elDock.scrollIntoView({{ behavior: "smooth", block: "start" }});
  }});

  document.addEventListener("keydown", (e) => {{
    if (e.key === "ArrowLeft") {{ e.preventDefault(); step(-1); }}
    else if (e.key === "ArrowRight") {{ e.preventDefault(); step(1); }}
    else if (e.key === "Escape") {{
      e.preventDefault();
      if (pendingFrom) clearPending();
      else if (explore) exitExplore();
      else if (fork) exitFork();
    }}
    else if (e.key === "Home") {{ e.preventDefault(); explore = null; fork = null; clearPending(); goTo(-1); }}
    else if (e.key === "End") {{ e.preventDefault(); explore = null; fork = null; clearPending(); goTo(plies().length - 1); }}
    else if (e.key === "PageDown" || e.key === "]") {{ e.preventDefault(); setGame(gIdx + 1); }}
    else if (e.key === "PageUp" || e.key === "[") {{ e.preventDefault(); setGame(gIdx - 1); }}
    else if (e.key === "f" || e.key === "F") {{ document.getElementById("btnFlip").click(); }}
    else if (e.key === "n" || e.key === "N") {{ jumpNote(1); }}
  }});

  setGame(0);
  bootEngine();
}})();
  </script>
</body>
</html>
"""
    out_html.write_text(html_doc, encoding="utf-8")
    return out_html


def write_viewer(pgn_path: Path, out_html: Path) -> Path:
    with pgn_path.open(encoding="utf-8", errors="replace") as handle:
        game = chess.pgn.read_game(handle)
    if game is None:
        raise ValueError(f"No game in {pgn_path}")
    out_html.parent.mkdir(parents=True, exist_ok=True)
    # Shared stockfish assets under data/viewer_out/stockfish/
    viewer_root = out_html.parent
    if viewer_root.name == "bookwalk":
        viewer_root = viewer_root.parent
    assets_dir = ensure_stockfish_assets(viewer_root / "stockfish")
    worker_url = _worker_url_for(out_html, assets_dir)
    ensure_textbook_badge(out_html)
    ensure_book_mark_badges(out_html)
    white = game.headers.get("White", "White")
    black = game.headers.get("Black", "Black")
    out_html.write_text(
        render_html(
            game,
            title=f"{white} vs {black}",
            engine_worker_url=worker_url,
            live_depth=LIVE_DEPTH,
        ),
        encoding="utf-8",
    )
    return out_html


def write_scid_import_readme(archive_dir: Path) -> Path:
    path = archive_dir / "SCID_IMPORT.md"
    path.write_text(
        """# View annotated games

## Interactive HTML (board + live Stockfish + notes)

```bash
chess-coach visualize path/to/game_bookwalk.pgn
# or open the HTML already written next to chapter runs:
xdg-open ../viewer_out/bookwalk/*_bookwalk.html
```

If the in-browser engine does not start from `file://`, serve the folder:

```bash
cd data/viewer_out && python -m http.server 8765
# open http://127.0.0.1:8765/bookwalk/<file>.html
```

Scroll the mouse wheel over the board (or use arrow keys) to step moves.
Book notes appear in the coach panel beside the board.

## Scid vs PC

1. Install Scid vs PC (`scid-vs-pc` on Debian/Ubuntu).
2. Open Scid → File → Open / New database.
3. Tools → Import PGN → select `*_bookwalk.pgn` / `*_annotated.pgn` here.
4. Engine window optional — comments already on moves.
""",
        encoding="utf-8",
    )
    return path


def build_missing_payload(
    *,
    white: str,
    black: str,
    year: int | str,
    event: str = "",
    book: str = "",
    chapter: str = "",
    attempts: list[str] | None = None,
    reason: str = "",
    notes_count: int = 0,
    context_preview: str = "",
) -> dict:
    matchup = f"{white} vs {black}"
    year_s = str(year)
    attempts = attempts or []
    subtitle_bits = [matchup, year_s]
    if event:
        subtitle_bits.append(event)
    return {
        "missing": True,
        "title": _pretty_book(book) or matchup,
        "subtitle": " · ".join(subtitle_bits),
        "matchup": matchup,
        "white": white,
        "black": black,
        "date": year_s,
        "event": event,
        "book": _pretty_book(book),
        "chapter": chapter,
        "plies": [],
        "startFen": chess.STARTING_FEN,
        "missingInfo": {
            "reason": reason,
            "attempts": attempts,
            "notes_count": notes_count,
            "context_preview": (context_preview or "")[:1200],
        },
    }


def write_missing_viewer(payload: dict, out_html: Path) -> Path:
    matchup = html.escape(str(payload.get("matchup") or "Unknown"))
    subtitle = html.escape(str(payload.get("subtitle") or ""))
    info = payload.get("missingInfo") or {}
    reason = html.escape(str(info.get("reason") or "PGN unavailable"))
    attempts = info.get("attempts") or []
    lis = "".join(f"<li>{html.escape(str(a))}</li>" for a in attempts)
    preview = html.escape(str(info.get("context_preview") or ""))
    notes_count = int(info.get("notes_count") or 0)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(
        f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8" /><meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Missing — {matchup}</title>
<style>
body {{ font-family: Inter, system-ui, -apple-system, "Segoe UI", sans-serif; background:#000; color:#fff; margin:0; padding:2rem; max-width:42rem; }}
h1 {{ margin:0 0 .4rem; font-size:1.5rem; font-weight:600; letter-spacing:-.4px; }} .meta {{ color:#a1a1a1; margin-bottom:1.2rem; font-size:.875rem; }}
.banner {{ border-left:3px solid #D32531; border-radius:12px; background:#121212; padding:.9rem 1rem; margin:1rem 0; }}
ul {{ padding-left:1.2rem; color:#e6e6e6; }} .preview {{ white-space:pre-wrap; background:#121212; border:1px solid rgba(255,255,255,.07); border-radius:12px; padding:.75rem; color:#a1a1a1; font-size:.8125rem; }}
</style></head><body>
<h1>{matchup}</h1>
<p class="meta">{subtitle}</p>
<div class="banner"><strong>PGN unavailable</strong><p>{reason}</p></div>
{"<h2>Tried</h2><ul>" + lis + "</ul>" if lis else ""}
<p>Book notes detected: {notes_count}</p>
{"<pre class='preview'>" + preview + "</pre>" if preview else ""}
</body></html>
""",
        encoding="utf-8",
    )
    return out_html


def write_chapter_book(
    entries: list[Path | dict],
    out_html: Path,
    *,
    book: str = "",
    chapter: str = "",
) -> Path:
    """Multi-game chapter book HTML from template + game payloads."""
    games: list[dict] = []
    for entry in entries:
        if isinstance(entry, dict):
            payload = dict(entry)
            payload.setdefault("missing", True)
            payload.setdefault("plies", [])
            payload.setdefault("startFen", chess.STARTING_FEN)
            games.append(payload)
            continue
        path = Path(entry)
        with path.open(encoding="utf-8", errors="replace") as handle:
            game = chess.pgn.read_game(handle)
        if game is None:
            continue
        payload = build_game_payload(game)
        payload["sourcePgn"] = path.name
        payload["missing"] = False
        games.append(payload)
    if not games:
        raise ValueError("No games to build chapter book")

    book = _pretty_book(book or games[0].get("book") or "Chapter")
    chapter = chapter or games[0].get("chapter") or ""
    heading = f"{book} — {chapter}" if chapter else book
    out_html.parent.mkdir(parents=True, exist_ok=True)
    viewer_root = out_html.parent
    if viewer_root.name == "bookwalk":
        viewer_root = viewer_root.parent
    assets_dir = ensure_stockfish_assets(viewer_root / "stockfish")
    worker_url = _worker_url_for(out_html, assets_dir)
    ensure_textbook_badge(out_html)
    ensure_book_mark_badges(out_html)
    data_json = json.dumps(
        {
            "book": book,
            "chapter": chapter,
            "heading": heading,
            "games": games,
            "liveDepth": LIVE_DEPTH,
            "engineWorkerUrl": worker_url,
        },
        ensure_ascii=False,
    ).replace("</", "<\\/")

    toc_items: list[str] = []
    for i, g in enumerate(games):
        missing = bool(g.get("missing"))
        toc_cls = "toc-item missing" if missing else "toc-item"
        toc_mark = "✗" if missing else str(i + 1)
        toc_items.append(
            f'<button type="button" class="{toc_cls}" data-g="{i}">'
            f'<span class="toc-n">{toc_mark}</span>'
            f'<span class="toc-t">{html.escape(g.get("matchup") or f"Game {i+1}")}</span>'
            f'<span class="toc-y">{html.escape((g.get("date") or "")[:4])}</span>'
            f"</button>"
        )

    template = (Path(__file__).with_name("chapter_book.template.html")).read_text(encoding="utf-8")
    doc = (
        template.replace("@@HEADING@@", html.escape(heading))
        .replace("@@TOC@@", "".join(toc_items))
        .replace("@@DATA_JSON@@", data_json)
    )
    out_html.write_text(doc, encoding="utf-8")
    return out_html
