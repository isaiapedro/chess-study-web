from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from chess_coach.logutil import log
from chess_coach.names import normalize_player_name
from chess_coach.rag.chunking import extract_text, resolve_sidecar

MOVE_TOKEN = (
    r"(?:O-O-O|O-O|[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#?!]*|"
    r"[NBRQK]x?[a-h][1-8](?:=[NBRQ])?[+#?!]*)"
)
# 23.f3 / 23...Rac8 / OCR "23 .. Rac8"
MOVE_LABEL_RE = re.compile(
    rf"(?P<num>\d+)\.(?P<dots>\.\.\s*|\.\s*\.\s*|\s*\.\.\s*)?\s*(?P<move>{MOVE_TOKEN})",
    re.I,
)
# Prose !? sentence ends (require 2+ letters so SAN glyphs like Ba?! / a4? stay put).
_PROSE_BANG_RE = re.compile(r"(?<=[a-z]{2})[!?…]+[\"'”’)\]]*\s+")
# 2013 / 20 11 / 201 0 (OCR spacing)
YEAR_OCR = r"(?:1[89]|20)(?:\s*\d){2}"
CITATION_RE = re.compile(
    r"(?P<white>[A-Z][A-Za-z' \-]{1,40}?)\s+(?:vs\.?|versus|–|-|—)\s+"
    r"(?P<black>[A-Z][A-Za-z' \-]{1,40}?)"
    r"(?:,\s*(?P<event>[A-Za-z0-9' \-]{2,60}?))?"
    rf",?\s+(?P<year>{YEAR_OCR})",
    re.M,
)
# Quality Chess style: "Etienne Bacrot - Romain Edouard" / next line "Caen 20 11"
DASH_GAME_RE = re.compile(
    r"(?m)^(?P<white>[A-Z][A-Za-z.'\-]{1,35}(?:\s+[A-Z][A-Za-z.'\-]{1,35}){0,3})"
    r"\s*[-–—]\s*"
    r"(?P<black>[A-Z][A-Za-z.'\-]{1,35}(?:\s+[A-Z][A-Za-z.'\-]{1,35}){0,3})\s*$"
)
YEAR_IN_TEXT_RE = re.compile(rf"(?P<year>{YEAR_OCR})")

WORD_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}
WORD_NUM_ALT = "|".join(WORD_NUMBERS.keys())

# Built-in heading schemes. Books differ — auto-detect by which yields real bodies.
DEFAULT_SCHEMES = (
    "family",
    "chapter",
    "game",
    "ending",
    "part",
    "lesson",
    "section",
)

SCHEME_PATTERNS = {
    "family": r"family",
    "chapter": r"chapter",
    "game": r"game",
    "ending": r"ending",
    "part": r"part",
    "lesson": r"lesson",
    "section": r"section",
}


@dataclass
class BookMoveNote:
    fullmove: int
    side: str
    san_hint: str
    text: str


@dataclass
class GameCitation:
    white: str
    black: str
    year: int
    event: str = ""
    context: str = ""
    notes: list[BookMoveNote] = field(default_factory=list)
    preamble: str = ""
    source_book: str = ""
    chapter: str = ""
    offset: int = 0  # char offset in section text — book order


@dataclass
class Section:
    scheme: str
    number: int | None
    title: str
    body: str
    start: int
    end: int

    @property
    def label(self) -> str:
        if self.number is not None:
            return f"{self.scheme.title()} {self.number}"
        return self.title


def _ocr_digits(value: str) -> str:
    # common OCR: Game I3 → Game 13, Game l0 → Game 10
    return value.replace("I", "1").replace("l", "1").replace("O", "0")


def _parse_year(raw: str) -> int | None:
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 4:
        return None
    year = int(digits)
    if 1800 <= year <= 2030:
        return year
    return None


def _parse_section_number(raw: str | None) -> int | None:
    if raw is None:
        return None
    key = raw.strip().lower()
    if key in WORD_NUMBERS:
        return WORD_NUMBERS[key]
    digits = re.sub(r"\D", "", _ocr_digits(raw))
    return int(digits) if digits else None


def _is_running_header(title: str) -> bool:
    """Page headers like 'Chapter 1 - The Isolani 25' (trailing page number)."""
    cleaned = re.sub(r"\s+", " ", title).strip()
    if re.search(r"[-–—:].+\s+\d{1,3}$", cleaned):
        return True
    if re.search(r"(?i)^(chapter|game|family|part|lesson|section)\s+\S+\s+\S.+\s+\d{1,3}$", cleaned):
        return True
    return False


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _resolve_sections_sidecar(book_path: Path) -> Path | None:
    direct = [
        book_path.with_suffix(book_path.suffix + ".sections.yaml"),
        book_path.with_suffix(".sections.yaml"),
    ]
    for path in direct:
        if path.exists():
            return path
    stem_slug = _slug(book_path.stem)
    candidates: list[tuple[int, Path]] = []
    for sidecar in book_path.parent.glob("*.sections.yaml"):
        key = sidecar.name[: -len(".sections.yaml")]
        key_slug = _slug(key)
        if stem_slug == key_slug or stem_slug.startswith(key_slug) or key_slug in stem_slug:
            candidates.append((len(key_slug), sidecar))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _load_book_section_config(book_path: Path) -> dict:
    """Optional sidecar: book.sections.yaml (exact or slug-matched)."""
    path = _resolve_sections_sidecar(book_path)
    if path and path.exists():
        with path.open(encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    theme_sidecar = resolve_sidecar(book_path)
    if theme_sidecar and theme_sidecar.exists():
        with theme_sidecar.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if "sections" in data or "section_scheme" in data:
            return data
    return {}


def _heading_regex(scheme: str, custom_pattern: str | None = None) -> re.Pattern:
    if custom_pattern:
        return re.compile(custom_pattern, re.I | re.M)
    token = SCHEME_PATTERNS.get(scheme, re.escape(scheme))
    if scheme == "family":
        num = rf"(?P<num>{WORD_NUM_ALT}|\d+)"
    else:
        num = r"(?P<num>[I0-9]+)"
    # Match line like "GAME 1" / "Family One:" / "Chapter 3: Foo"
    return re.compile(
        rf"(?im)^(?P<title>{token}\s+{num}(?:\s*[:.\-–—].*)?)\s*$"
    )


def _sections_from_heading_matches(
    text: str,
    scheme: str,
    matches: list[re.Match[str]],
    *,
    min_body_chars: int,
) -> list[Section]:
    """
    Build sections from heading hits.

    Skip running page headers. For each section number, take the earliest
    real heading and cut body at the next number's earliest heading — so
    'Chapter 1' is not truncated by repeated 'Chapter 1 - Title 25' headers.
    """
    earliest: dict[int, tuple[int, int, str]] = {}
    for match in matches:
        title = re.sub(r"\s+", " ", match.group("title")).strip()
        if _is_running_header(title):
            continue
        number = _parse_section_number(match.groupdict().get("num"))
        if number is None:
            continue
        prev = earliest.get(number)
        if prev is None or match.start() < prev[0]:
            earliest[number] = (match.start(), match.end(), title)

    sections: list[Section] = []
    nums = sorted(earliest)
    for idx, number in enumerate(nums):
        start, title_end, title = earliest[number]
        end = earliest[nums[idx + 1]][0] if idx + 1 < len(nums) else len(text)
        body = text[title_end:end].strip()
        if len(body) < min_body_chars:
            continue
        sections.append(
            Section(
                scheme=scheme,
                number=number,
                title=title,
                body=body,
                start=start,
                end=end,
            )
        )
    return sections


def _detect_family_ranges(text: str) -> list[tuple[int, str, int, int]]:
    """
    Detect Family N → chapter span from overview prose / TOC.
    Returns (family_number, title, chapter_lo, chapter_hi).
    """
    head = text[:80000]
    found: dict[int, tuple[str, int, int]] = {}

    prose = re.compile(
        rf"Family\s+(?P<w>{WORD_NUM_ALT}|\d+)\s*[:.\-–—]?\s*(?P<title>[^\n]{{0,60}})"
        rf".{{0,600}}?Chapters?\s+(?P<a>\d+)\s+(?:through|to|[-–—])\s+(?P<b>\d+)",
        re.I | re.S,
    )
    for match in prose.finditer(head):
        num = _parse_section_number(match.group("w"))
        if num is None:
            continue
        title = f"Family {match.group('w').title()}".strip()
        extra = re.sub(r"\s+", " ", match.group("title")).strip(" :-–—")
        if extra and len(extra) > 2:
            title = f"{title}: {extra}"
        a, b = int(match.group("a")), int(match.group("b"))
        if a > b:
            a, b = b, a
        found[num] = (title, a, b)

    # TOC fallback: Family One - Title / numbered lines / next Family
    toc = re.compile(
        rf"(?im)^(Family\s+(?P<w>{WORD_NUM_ALT}|\d+)\s*[-–—:]\s*(?P<title>[^\n]+))\s*$"
    )
    toc_hits = list(toc.finditer(head))
    for idx, match in enumerate(toc_hits):
        num = _parse_section_number(match.group("w"))
        if num is None or num in found:
            continue
        title = re.sub(r"\s+", " ", match.group(1)).strip()
        block_end = toc_hits[idx + 1].start() if idx + 1 < len(toc_hits) else min(len(head), match.end() + 800)
        block = head[match.end() : block_end]
        nums = [int(n) for n in re.findall(r"(?m)^(\d{1,2})\s+\S+", block)]
        if len(nums) < 1:
            continue
        found[num] = (title, min(nums), max(nums))

    return [(n, found[n][0], found[n][1], found[n][2]) for n in sorted(found)]


def _find_family_sections(text: str, *, min_body_chars: int) -> list[Section]:
    ranges = _detect_family_ranges(text)
    if not ranges:
        return []
    chapters = find_sections(text, scheme="chapter", min_body_chars=min_body_chars)
    by_num = {c.number: c for c in chapters if c.number is not None}
    if not by_num:
        return []
    sections: list[Section] = []
    for fam_num, title, lo, hi in ranges:
        parts: list[str] = []
        start = end = None
        for chapter_n in range(lo, hi + 1):
            chapter = by_num.get(chapter_n)
            if chapter is None:
                continue
            parts.append(f"{chapter.title}\n\n{chapter.body}")
            if start is None:
                start = chapter.start
            end = chapter.end
        body = "\n\n".join(parts).strip()
        if len(body) < min_body_chars:
            continue
        sections.append(
            Section(
                scheme="family",
                number=fam_num,
                title=title,
                body=body,
                start=start or 0,
                end=end or 0,
            )
        )
    return sections


def find_sections(
    text: str,
    *,
    scheme: str | None = None,
    custom_pattern: str | None = None,
    min_body_chars: int = 800,
) -> list[Section]:
    """
    Split book text into sections.

    Prefer headings whose following body is long enough — skips TOC stubs.
    Family scheme stitches chapter spans (Chess Structures: Family One = ch 1–7).
    """
    if scheme == "family" or scheme is None:
        family_sections = _find_family_sections(text, min_body_chars=min_body_chars)
        if scheme == "family":
            return family_sections
        if len(family_sections) >= 3:
            return family_sections

    schemes = [scheme] if scheme else [s for s in DEFAULT_SCHEMES if s != "family"]
    best: list[Section] = []
    for sch in schemes:
        if sch == "family":
            sections = _find_family_sections(text, min_body_chars=min_body_chars)
        else:
            pattern = _heading_regex(sch, custom_pattern if sch == scheme else None)
            matches = list(pattern.finditer(text))
            if not matches:
                continue
            sections = _sections_from_heading_matches(
                text,
                sch,
                matches,
                min_body_chars=min_body_chars,
            )
        if len(sections) > len(best):
            best = sections
        if scheme:
            return sections
    return best


def split_chapters(text: str) -> list[tuple[str, str]]:
    sections = find_sections(text)
    if not sections:
        return [("body", text.strip())]
    return [(s.label, s.body) for s in sections]


def select_chapter(
    text: str,
    chapter: str | int | None,
    *,
    scheme: str | None = None,
    custom_pattern: str | None = None,
    min_body_chars: int = 800,
) -> tuple[str, str]:
    sections = find_sections(
        text,
        scheme=scheme,
        custom_pattern=custom_pattern,
        min_body_chars=min_body_chars,
    )
    if not sections:
        if chapter is None or chapter in {"", "all", "body"}:
            return "body", text.strip()
        raise ValueError(
            "No sections found. Try --list-sections, lower --min-body, "
            "or set section_scheme/pattern in a .sections.yaml sidecar."
        )

    if chapter is None or chapter in {"", "all"}:
        return sections[0].label, sections[0].body

    if isinstance(chapter, int) or (isinstance(chapter, str) and str(chapter).isdigit()):
        idx = int(chapter)
        for section in sections:
            if section.number == idx:
                return section.label, section.body
        # positional fallback among detected sections
        if 1 <= idx <= len(sections):
            section = sections[idx - 1]
            return section.label, section.body
        available = ", ".join(
            f"{s.number}" for s in sections if s.number is not None
        ) or "none"
        raise ValueError(
            f"{sections[0].scheme.title()} {idx} not found. "
            f"Detected scheme={sections[0].scheme!r}, numbers: {available}. "
            f"Run with --list-sections."
        )

    needle = str(chapter).lower()
    for section in sections:
        if needle in section.title.lower() or needle in section.label.lower():
            return section.label, section.body
        if needle in section.body[:500].lower():
            return section.label, section.body
    raise ValueError(f"Section matching {chapter!r} not found. Run --list-sections.")


def _inside_parens(text: str, pos: int) -> bool:
    """True when pos sits inside an unclosed '(' since the last prose sentence."""
    start = _last_prose_sentence_end(text[:pos]) or 0
    depth = 0
    for ch in text[start:pos]:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
    return depth > 0


def _last_prose_sentence_end(before: str) -> int | None:
    """
    Index just after the last prose sentence terminator in `before`.

    Ignores move-number dots (26.) and annotation glyphs (a4?), but treats
    SAN stops like 'Qd2.' / 'Rac8.' as sentence ends when followed by space.
    """
    ends: list[int] = []
    for m in re.finditer(r"\.", before):
        i = m.start()
        if i + 1 < len(before) and not before[i + 1].isspace() and before[i + 1] not in "\"'”’)":
            continue
        j = i - 1
        while j >= 0 and before[j].isdigit():
            j -= 1
        if j < i - 1:
            # digits before dot — count as sentence only when SAN (...Qd2.)
            if j < 0 or not before[j].isalpha():
                continue
        elif j < 0 or not (before[j].islower() or before[j] in ") ]\"'"):
            continue
        k = m.end()
        while k < len(before) and before[k] in "\"'”’)]":
            k += 1
        while k < len(before) and before[k].isspace():
            k += 1
        ends.append(k)
    for m in _PROSE_BANG_RE.finditer(before):
        ends.append(m.end())
    return max(ends) if ends else None


def _trailing_is_score_only(before: str) -> bool:
    """
    True when text after the last prose sentence is empty or only move notation.

    Lets mainline headers like '…chances.\\n23...Rac8 24.Bd3' open a new note,
    while PDF-wrapped variation lines ('…continuation is 26.Rc1\\n28.Qd2') stay
    inside the previous note.
    """
    end = _last_prose_sentence_end(before)
    tail = before[end:] if end is not None else before
    tail = re.sub(r"\ba\s+b\s+c\s+d\s+e\s+f\s+g\s+h\b", " ", tail, flags=re.I)
    tail = re.sub(r"\d{2,3}\s+Family\b[^\n]*", " ", tail)
    if not tail.strip():
        return True
    rest = MOVE_LABEL_RE.sub(" ", tail)
    rest = re.sub(rf"\b{MOVE_TOKEN}\b", " ", rest, flags=re.I)
    rest = re.sub(r"[0-9.!?\s\-–—,;:]+", " ", rest)
    rest = re.sub(r"\s+", " ", rest).strip()
    # Any leftover letters ("If", "and") mean variation / prose, not bare score.
    return not re.search(r"[A-Za-z]", rest)


def _is_mainline_label(text: str, match: re.Match[str]) -> bool:
    """Delegate to score-line grammar (kept for tests / callers)."""
    from chess_coach.chess_text_grammar import can_open_score_line

    return can_open_score_line(text, match)


def _next_game_boundary(text: str, after: int) -> int | None:
    """
    Earliest start of the next cited game after `after`.

    Used so heavily annotated games keep their full coaching prose instead of a
    fixed 2.5–4k character slice that cuts mid-middlegame.
    """
    search_from = after + 40
    if search_from >= len(text):
        return None
    candidates: list[int] = []
    for regex in (DASH_GAME_RE, CITATION_RE):
        m = regex.search(text, search_from)
        if m:
            candidates.append(m.start())
    header_re = re.compile(
        r"(?mi)^White\s+[A-Z].+\n\s*Black\s+[A-Z]",
    )
    m = header_re.search(text, search_from)
    if m:
        candidates.append(m.start())
    # Quality Chess often starts the next illustrative game with a fresh objective
    # only when paired with a name header — still useful as soft boundary.
    return min(candidates) if candidates else None


def _citation_context(
    text: str,
    start: int,
    *,
    header_end: int | None = None,
    default_span: int = 4000,
    max_span: int = 16000,
) -> str:
    """Slice from start through next game (or max_span), never shorter than default when alone."""
    after = header_end if header_end is not None else start + 80
    boundary = _next_game_boundary(text, after)
    if boundary is not None:
        end = min(boundary, start + max_span)
        if end - start < min(default_span, 1500) and boundary - start < 1500:
            end = min(len(text), start + default_span, boundary)
    else:
        end = min(len(text), start + max_span)
    if end - start < default_span:
        end = min(len(text), start + default_span)
        if boundary is not None:
            end = min(end, boundary)
    return text[start:end]


def _clean_preamble(head: str) -> str:
    """Keep learning-objective / intro prose; drop name/event header lines."""
    from chess_coach.ocr_chess import clean_book_note, prose_is_usable

    lines: list[str] = []
    for raw in head.splitlines():
        ln = raw.strip()
        if not ln:
            continue
        if DASH_GAME_RE.match(ln):
            continue
        if CITATION_RE.match(ln):
            continue
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9' \-]{2,40}\s+(?:1[89]|20)\d{2}", ln):
            continue
        if re.fullmatch(rf"{YEAR_OCR}", ln):
            continue
        lines.append(ln)
    text = clean_book_note(" ".join(lines))
    text = re.sub(r"\s+", " ", text).strip()
    # Drop trailing opening-score salad that never opened a score line (I.d4 …)
    text = re.sub(
        rf"(?i)(?:\s+\d+\.(?:\.\.)?\s*{MOVE_TOKEN}){{3,}}\s*$",
        "",
        text,
    ).strip()
    if not prose_is_usable(text, min_alpha=40):
        return ""
    return text[:2500]


def _overview_window_start(text: str, header_start: int) -> int:
    """
    Rule E: include overview prose above the game header when present.

    Many Quality Chess games put Learning objective *after* the name line — then
    return ``header_start``. Only look back for overview cues immediately above
    the header (section question / learning objective before a dash citation).
    """
    near = min(900, header_start)
    near_text = text[header_start - near : header_start]
    near_cues = list(
        re.finditer(
            r"(?im)(?:^|\n)\s*(?:"
            r"Learning\s+objective|"
            r"How\s+should\b|"
            r"(?:Black|White)'s\s+(?:\w+\s+){0,4}(?:plan|chances|prospects)\b"
            r")",
            near_text,
        )
    )
    if near_cues:
        return header_start - near + near_cues[-1].start()
    return header_start


def _previous_fullmove_side(fullmove: int, side: str) -> tuple[int, str] | None:
    """Ply immediately before (fullmove, side). None at game start."""
    if side == "black":
        return fullmove, "white"
    if fullmove <= 1:
        return None
    return fullmove - 1, "black"


def _split_midgame_preamble(raw_preamble: str) -> tuple[str, str]:
    """
    Rule F: last prose paragraph before the first scored move vs remaining overview.

    Returns (overview_for_start, last_paragraph_for_previous_ply).
    """
    from chess_coach.ocr_chess import clean_book_note, prose_is_usable

    text = (raw_preamble or "").strip()
    if not text:
        return "", ""
    # Prefer blank-line paragraphs; else last sentence cluster after a period.
    parts = [p.strip() for p in re.split(r"(?:\n\s*){2,}", text) if p.strip()]
    if len(parts) >= 2:
        last = clean_book_note(parts[-1])
        overview = clean_book_note(" ".join(parts[:-1]))
    else:
        # Split on last ". " that leaves a usable final sentence (>= 40 alpha).
        last = ""
        overview = text
        for m in reversed(list(re.finditer(r"\.\s+", text))):
            cand = text[m.end() :].strip()
            head = text[: m.end()].strip()
            if prose_is_usable(cand, min_alpha=40) and prose_is_usable(head, min_alpha=40):
                last = clean_book_note(cand)
                overview = clean_book_note(head)
                break
        if not last:
            # Single block: use all as previous-ply note when mid-game; overview empty.
            last = clean_book_note(text)
            overview = ""
    last = re.sub(r"\s+", " ", last).strip()
    overview = re.sub(r"\s+", " ", overview).strip()
    if not prose_is_usable(last, min_alpha=40):
        return _clean_preamble(text), ""
    if overview and not prose_is_usable(overview, min_alpha=40):
        overview = ""
    return overview[:2500], last[:2500]


def _retarget_early_score_note(note: BookMoveNote) -> BookMoveNote:
    """
    Opening score dumps (1.d4 … 21.bxc5 Nxb5) often carry the first real coaching
    on a later move. Retarget the note to that later label and keep only the prose.
    """
    if note.fullmove > 8:
        return note
    from chess_coach.ocr_chess import prose_is_usable, split_movelist_and_prose

    _prefix, prose = split_movelist_and_prose(note.text)
    if not prose_is_usable(prose, min_alpha=40):
        return note
    late: re.Match[str] | None = None
    for m in MOVE_LABEL_RE.finditer(prose):
        num = int(m.group("num"))
        if num >= max(10, note.fullmove + 8):
            late = m
            break
    if late is None:
        return note
    return BookMoveNote(
        fullmove=int(late.group("num")),
        side="black" if late.group("dots") else "white",
        san_hint="",  # trust move number + side; SAN may be the book alternative
        text=prose[:4000],
    )


def _retarget_through_leading_score(note: BookMoveNote) -> BookMoveNote:
    """
    Books print a short score then the comment on the last move, e.g.
    ``27...Bf6 28.Qd2`` / ``Preparing a4-a5…``, or labeled ``21.bxc5`` with
    body ``Nxb5`` then coaching. Commentary belongs on the last score move.

    Walks labeled plies and bare replies (including OCR leftover ``.Bh6``)
    until coaching prose starts.
    """
    from chess_coach.ocr_chess import _PROSE_START_RE, prose_is_usable, strip_diagrams

    text = (note.text or "").lstrip()
    if not text:
        return note

    fm = note.fullmove
    side = note.side
    san = note.san_hint
    pos = 0
    moved = False
    bare_san = re.compile(rf"(?P<move>{MOVE_TOKEN})", re.I)

    def _accept_white_to_black() -> None:
        nonlocal side, fm
        if side == "white":
            side = "black"
        else:
            side = "white"
            fm += 1

    while pos < len(text):
        ws = re.match(r"\s+", text[pos:])
        if ws:
            pos += ws.end()
            continue
        if _PROSE_START_RE.match(strip_diagrams(text[pos:]).lstrip()):
            break

        m = MOVE_LABEL_RE.match(text, pos)
        if m:
            num = int(m.group("num"))
            if not moved:
                if num < note.fullmove or num > note.fullmove + 1:
                    break
            elif num < fm or num > fm + 1:
                break
            fm = num
            side = "black" if m.group("dots") else "white"
            san = m.group("move")
            pos = m.end()
            moved = True
            continue

        # OCR leftover figurine dot before reply SAN: ".Bh6 The knight…"
        if text[pos : pos + 1] == "." and pos + 1 < len(text) and text[pos + 1].isalpha():
            pos += 1
        m = bare_san.match(text, pos)
        if not m:
            break
        after = text[m.end() :]
        probe = strip_diagrams(after).lstrip()
        next_move = bool(
            _PROSE_START_RE.match(probe)
            or MOVE_LABEL_RE.match(probe)
            or bare_san.match(probe)
        )
        if not next_move:
            break
        _accept_white_to_black()
        san = m.group("move")
        pos = m.end()
        moved = True
        if _PROSE_START_RE.match(strip_diagrams(text[pos:]).lstrip()):
            break

    if not moved:
        return note
    rest = strip_diagrams(text[pos:]).strip()
    if not prose_is_usable(rest, min_alpha=20):
        return note
    if fm == note.fullmove and side == note.side:
        return note
    return BookMoveNote(
        fullmove=fm,
        side=side,
        san_hint=san,
        text=rest[:4000],
    )


# Trailing next-move OCR crumbs with missing file/piece: "aiming…. 25... 5"
_TRAILING_BROKEN_MOVE_RE = re.compile(
    r"(?:\s+\d+\.(?:\.\.)?\s*(?:[1-8])?\s*)+$"
)


def extract_move_notes(text: str) -> tuple[str, list[BookMoveNote]]:
    from chess_coach.chess_text_grammar import (
        MOVE_LABEL_RE,
        can_open_score_line,
        segment_score_lines,
    )
    from chess_coach.ocr_chess import clean_book_note, normalize_prose_breaks, ocr_clean_chess

    cleaned = ocr_clean_chess(text)
    raw_preamble, segments = segment_score_lines(cleaned)
    preamble = _clean_preamble(raw_preamble) if raw_preamble else ""
    notes: list[BookMoveNote] = []

    # Rule F — mid-game start: gate on the *first open* fullmove (not the last
    # ply of the first score-line group, which can be 5.Qd2 after 1.d4…).
    first_open_fm: int | None = None
    first_open_side: str | None = None
    for m in MOVE_LABEL_RE.finditer(cleaned):
        if can_open_score_line(cleaned, m):
            first_open_fm = int(m.group("num"))
            first_open_side = "black" if m.group("dots") else "white"
            break

    if (
        first_open_fm is not None
        and first_open_fm > 1
        and first_open_side
        and (raw_preamble or "").strip()
    ):
        overview, last_para = _split_midgame_preamble(raw_preamble)
        prev = _previous_fullmove_side(first_open_fm, first_open_side)
        if last_para and prev is not None:
            notes.append(
                BookMoveNote(
                    fullmove=prev[0],
                    side=prev[1],
                    san_hint="",
                    text=last_para[:4000],
                )
            )
            preamble = overview if overview else ""
        elif overview:
            preamble = overview

    for seg in segments:
        prose = normalize_prose_breaks(seg.text)
        prose = _TRAILING_BROKEN_MOVE_RE.sub("", prose).strip()
        prose = re.sub(r"^(?:\+-|-\+|±|∓)\s*", "", prose)
        short_ok = bool(
            re.match(
                r"(?i)(?:but now|threatening |covering the |suicidal is |"
                r"deserves\b|of course\b)",
                prose,
            )
        )
        if len(prose) < 12 and not short_ok:
            continue
        if MOVE_LABEL_RE.fullmatch(prose.strip()):
            continue
        if re.fullmatch(r"(?i)(?:and now:?\s*)+", prose.strip()):
            continue
        if (
            len(clean_book_note(prose)) < 12
            and not short_ok
            and not re.search(
                r"\b(?:The|White|Black|Better|Threatening|Precision|If|Getting|Preparing|Something|But|Of course|It took)\b",
                prose,
            )
        ):
            continue
        # Score crumbs + "And now:" with no real coaching
        if re.match(r"(?i)(?:\d+\.(?:\.\.)?\s*\S+\s*)+and now:?\s*$", prose.strip()):
            continue
        note = BookMoveNote(
            fullmove=seg.fullmove,
            side=seg.side,
            san_hint=seg.san,
            text=prose[:8000],
        )
        note = _retarget_through_leading_score(note)
        notes.append(_retarget_early_score_note(note))
    return preamble, notes


def _clean_player_name(raw: str) -> str | None:
    junk = {
        "the",
        "this",
        "after",
        "white",
        "black",
        "later",
        "see",
        "also",
        "from",
        "in",
        "and",
        "game",
        "learning",
        "objective",
        "objectives",
        "family",
        "chapter",
        "was",
        "better",
        "best",
        "move",
        "with",
        "without",
        "after",
        "before",
        "then",
        "when",
        "where",
        "which",
        "that",
        "this",
        "than",
        "into",
        "over",
        "under",
        "here",
        "there",
    }
    name = re.sub(r"\s+", " ", raw).strip(" -–—")
    parts = [p for p in name.split() if p.lower() not in junk and len(p) > 1]
    name = " ".join(parts).strip()
    if not name or name.lower() in junk:
        return None
    if len(name.split()) > 5 or len(name.split()) < 1:
        return None
    # require at least one capitalized token that looks like a surname/forename
    if not any(p[0].isupper() and p.isalpha() for p in name.split()):
        return None
    return normalize_player_name(name)


def extract_citations(chapter_text: str, *, book: str = "", chapter: str = "") -> list[GameCitation]:
    log("Parsing game citations from section text...")
    citations: list[GameCitation] = []
    for match in CITATION_RE.finditer(chapter_text):
        white = _clean_player_name(match.group("white"))
        black = _clean_player_name(match.group("black"))
        year = _parse_year(match.group("year"))
        if not white or not black or year is None:
            continue
        event = (match.group("event") or "").strip(" ,")
        window_start = _overview_window_start(chapter_text, match.start())
        context = _citation_context(
            chapter_text,
            window_start,
            header_end=match.end(),
            default_span=4500,
            max_span=16000,
        )
        preamble, notes = extract_move_notes(context)
        citations.append(
            GameCitation(
                white=white,
                black=black,
                year=year,
                event=event,
                context=context.strip(),
                notes=notes,
                preamble=preamble,
                source_book=book,
                chapter=chapter,
                offset=match.start(),
            )
        )
    # Capablanca-style headers: White X / Black Y / City, 1901
    citations.extend(_citations_from_game_headers(chapter_text, book=book, chapter=chapter))
    # Quality Chess style: Name - Name \n Event YEAR
    citations.extend(_citations_from_dash_headers(chapter_text, book=book, chapter=chapter))
    citations = order_citations_book(_dedupe_citations(citations))
    log("Citations parsed: %d (book order)", len(citations))
    return citations


def is_footnote_citation(cite: GameCitation) -> bool:
    """Parenthetical DB asides: surname-only + almost no move notes."""
    w_n = len(cite.white.split())
    b_n = len(cite.black.split())
    return w_n == 1 and b_n == 1 and len(cite.notes) < 3


def order_citations_book(citations: list[GameCitation]) -> list[GameCitation]:
    """
    Keep games in section text order (first in book = first).

    Footnote-style citations sink to the end but stay ordered among themselves.
    """
    items = sorted(citations, key=lambda c: (c.offset, c.white, c.black))
    primary = [c for c in items if not is_footnote_citation(c)]
    footnotes = [c for c in items if is_footnote_citation(c)]
    return primary + footnotes


def rank_citations(citations: list[GameCitation]) -> list[GameCitation]:
    """
    Legacy quality rank (full names + note count). Prefer order_citations_book
    for chapter walkthroughs.
    """
    bad_event = re.compile(
        r"(?i)\b(problem|objective|learning|standard|isolani|structure|desired)\b"
    )

    def sort_key(cite: GameCitation) -> tuple:
        w_n = len(cite.white.split())
        b_n = len(cite.black.split())
        full_names = (1 if w_n >= 2 else 0) + (1 if b_n >= 2 else 0)
        notes = len(cite.notes)
        footnote = 1 if is_footnote_citation(cite) else 0
        event_penalty = 1 if bad_event.search(cite.event or "") else 0
        return (full_names, notes, -footnote, -event_penalty, -cite.offset)

    return sorted(citations, key=sort_key, reverse=True)


def _citations_from_dash_headers(
    text: str,
    *,
    book: str,
    chapter: str,
) -> list[GameCitation]:
    out: list[GameCitation] = []
    for match in DASH_GAME_RE.finditer(text):
        white = _clean_player_name(match.group("white"))
        black = _clean_player_name(match.group("black"))
        if not white or not black:
            continue
        tail = text[match.end() : match.end() + 160]
        year_match = YEAR_IN_TEXT_RE.search(tail)
        if not year_match:
            continue
        year = _parse_year(year_match.group("year"))
        if year is None:
            continue
        event = re.sub(r"\s+", " ", tail[: year_match.start()]).strip(" ,.")
        window_start = _overview_window_start(text, match.start())
        context = _citation_context(
            text,
            window_start,
            header_end=match.end() + year_match.end(),
            default_span=5000,
            max_span=16000,
        )
        preamble, notes = extract_move_notes(context)
        out.append(
            GameCitation(
                white=white,
                black=black,
                year=year,
                event=event,
                context=context,
                notes=notes,
                preamble=preamble,
                source_book=book,
                chapter=chapter,
                offset=match.start(),
            )
        )
    return out


def _citations_from_game_headers(
    text: str,
    *,
    book: str,
    chapter: str,
) -> list[GameCitation]:
    """Parse 'White J. R. Capablanca / Black J. Corzo / Havana, 1901' blocks."""
    header_re = re.compile(
        r"White\s+(?P<white>[^\n]+)\n\s*Black\s+(?P<black>[^\n]+)\n"
        rf"(?P<meta>[^\n]{{0,120}}?(?P<year>{YEAR_OCR})[^\n]*)",
        re.I,
    )
    out: list[GameCitation] = []
    for match in header_re.finditer(text):
        white = _clean_player_name(match.group("white"))
        black = _clean_player_name(match.group("black"))
        year = _parse_year(match.group("year"))
        if not white or not black or year is None:
            continue
        meta = re.sub(r"\s+", " ", match.group("meta")).strip()
        # keep opening name in event hint for ranking (Dutch Defence etc.)
        event = re.sub(rf",?\s*{re.escape(match.group('year'))}", "", meta).strip(" ,")
        window_start = _overview_window_start(text, match.start())
        context = _citation_context(
            text,
            window_start,
            header_end=match.end(),
            default_span=5000,
            max_span=16000,
        )
        preamble, notes = extract_move_notes(context)
        out.append(
            GameCitation(
                white=white,
                black=black,
                year=year,
                event=event,
                context=context,
                notes=notes,
                preamble=preamble,
                source_book=book,
                chapter=chapter,
                offset=match.start(),
            )
        )
    return out


def _dedupe_citations(citations: list[GameCitation]) -> list[GameCitation]:
    # earliest offset wins; merge notes from duplicates
    ordered = sorted(citations, key=lambda c: c.offset)
    seen: set[tuple[str, str, int, str]] = set()
    out: list[GameCitation] = []
    for cite in ordered:
        event_key = re.sub(r"\s+", " ", cite.event.lower()).strip()
        key = (cite.white.lower(), cite.black.lower(), cite.year, event_key)
        rev = (cite.black.lower(), cite.white.lower(), cite.year, event_key)
        if key in seen or rev in seen:
            for existing in out:
                ek = (
                    existing.white.lower(),
                    existing.black.lower(),
                    existing.year,
                    re.sub(r"\s+", " ", existing.event.lower()).strip(),
                )
                if ek in {key, rev}:
                    existing.notes.extend(cite.notes)
                    if cite.preamble and not existing.preamble:
                        existing.preamble = cite.preamble
                    break
            continue
        seen.add(key)
        out.append(cite)
    return out


def load_chapter(
    book_path: Path,
    chapter: str | int | None = None,
    *,
    scheme: str | None = None,
    min_body_chars: int = 800,
) -> tuple[str, str, str]:
    log("PDF extract: %s...", book_path.name)
    text = extract_text(book_path)
    log("PDF extract done: %d chars", len(text))
    cfg = _load_book_section_config(book_path)
    scheme = scheme or cfg.get("section_scheme") or cfg.get("sections", {}).get("scheme")
    custom = None
    sections_cfg = cfg.get("sections") if isinstance(cfg.get("sections"), dict) else {}
    if isinstance(sections_cfg, dict):
        custom = sections_cfg.get("pattern")
        min_body_chars = int(sections_cfg.get("min_body_chars", min_body_chars))
        scheme = scheme or sections_cfg.get("scheme")
    custom = custom or cfg.get("section_pattern")
    log("Section select: chapter=%s scheme=%s...", chapter, scheme or "auto")
    title, body = select_chapter(
        text,
        chapter,
        scheme=scheme,
        custom_pattern=custom,
        min_body_chars=min_body_chars,
    )
    book_name = cfg.get("book") or book_path.stem.split("(")[0].strip()
    log("Section ready: %s (%d chars)", title, len(body))
    return book_name, title, body


def list_book_sections(
    book_path: Path,
    *,
    scheme: str | None = None,
    min_body_chars: int = 800,
) -> list[Section]:
    log("PDF extract: %s...", book_path.name)
    text = extract_text(book_path)
    log("PDF extract done: %d chars", len(text))
    cfg = _load_book_section_config(book_path)
    scheme = scheme or cfg.get("section_scheme")
    sections_cfg = cfg.get("sections") if isinstance(cfg.get("sections"), dict) else {}
    custom = None
    if isinstance(sections_cfg, dict):
        custom = sections_cfg.get("pattern")
        min_body_chars = int(sections_cfg.get("min_body_chars", min_body_chars))
        scheme = scheme or sections_cfg.get("scheme")
    log("Detecting sections (scheme=%s)...", scheme or "auto")
    sections = find_sections(
        text,
        scheme=scheme,
        custom_pattern=custom or cfg.get("section_pattern"),
        min_body_chars=min_body_chars,
    )
    log("Sections found: %d", len(sections))
    return sections
