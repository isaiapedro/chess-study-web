from __future__ import annotations

import re

from chess_coach.notation_dict import (
    OCR_ALIASES,
    normalize_notation_mark,
    normalize_position_eval,
)

_DIAGRAM_RE = re.compile(
    r"(?:[87654321lI|]\s+){2,}.*?a\s*b\s*c\s*d\s*e\s*f\s*g\s*h",
    re.I | re.S,
)
_RANK_ONLY_RE = re.compile(r"(?:^|\s)(?:[87654321]\s+){4,}(?:[87654321]\s*)")
_GLYPH_SALAD_RE = re.compile(r"[^\w\s\.\,\;\:\!\?\-\+\=#\(\)\'\"\/]{2,}")
_PAGE_HEADER_RE = re.compile(
    r"Chapter\s+\d+\s*[-–—]?\s*[A-Za-z][^\n]{0,40}\s+\d{1,3}",
    re.I,
)
_PROSE_START_RE = re.compile(
    r"(?:"
    r"The opening stage|White has |Black has |Threatening |Better was |"
    r"Precision is|This game|This example|We have reached|The best |"
    r"Learning objective|In Black's favour|In White's favour|Not only|"
    r"A better |An alternative|Instead |A simple |An interesting |"
    r"Something to note|There is nothing|Getting ready|Now the |"
    r"Followed by|Black is |White is |Black cannot|White can |"
    r"His original|In his analysis|After analyzing|The reader |"
    r"Not only|Ignoring the|Creating a|Preparing |"
    r"This prophylactic|Again,? White|And as I said|Black must |"
    r"It was preferable|Once again|The battle is|The only move|"
    r"We are close|The most accurate|Aiming for|Covering the |"
    r"And as usually|A better defence|Black missed|Weak is |"
    r"[!?]+\s*(?:A |The |This |White |Black |It |There )"
    r")",
    re.I,
)

_ENGLISH_HINT_RE = re.compile(
    r"\b(?:the|and|with|white|black|move|pawn|bishop|knight|rook|queen|king|"
    r"after|since|while|because|should|cannot|nothing|better|serious|"
    r"interesting|alternative|structure|position|prepare|weakness|support|"
    r"forced|equality|improve|tempo|plans?|camp|chain|remembered|imprecision|"
    r"allows|destroy|weakened|chances|slowly|space|trading|alleviates|"
    r"ready|create|continue|ignoring|prophylactic|protects|prepares|"
    r"crippling|strategically|advantage|defence|passive|accurate|"
    r"preferable|playable|counterplay|queenside|kingside|decision)\b",
    re.I,
)

_SAN_TOKEN_RE = re.compile(
    r"(?:O-O-O|O-O|[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#?!]*|"
    r"[NBRQK]x?[a-h][1-8](?:=[NBRQ])?[+#?!]*)",
    re.I,
)
_NUMBERED_MOVE_RE = re.compile(
    rf"(?P<num>\d+)\.(?P<dots>\.\.)?\s*(?P<san>{_SAN_TOKEN_RE.pattern})",
    re.I,
)

# Numbered move head: 31. / 31... / 31 ...
_MOVE_HEAD_RE = re.compile(r"\b(\d+)\s*(\.\.\.|\.\.(?!\.)|\.)\s*")
# Dirty OCR token right after a move head (one SAN-ish unit).
_MOVE_TOKEN_RE = re.compile(
    r"(?:"
    r"O-O-O|O-O|"
    r"[NBRQK]\s+[a-h][1-8][=NBRQ]?[+#?!]*|"
    r"[a-h]\s+x\s*[a-h][1-8][=NBRQ]?[+#?!]*|"
    r"[a-h]\s+[a-h][1-8][=NBRQ]?[+#?!]*|"
    r"[a-h]\s+[1-8][=NBRQ]?[+#?!]*|"
    r"[^\s,;:\[\]\(\){}]{1,18}"
    r")",
    re.I,
)
_PROSE_STOP_RE = re.compile(
    r"^(?:and|or|with|the|to|for|when|then|while|black|white|as|if|but|"
    r"after|before|since|because|followed|threatening|better|instead|"
    r"this|that|which|when|where|into|from|over|under|once|again|"
    r"preparing|creating|ignoring|covering|aiming|ready|counterplay|"
    r"excellent|compensation|pawn|position|counter)\b",
    re.I,
)
_JUNK_BEFORE_MOVE_RE = re.compile(r"(?:[•·∙⋅]+\s*|'+\s*\(!?\s*|\(\s*!\s*)+")
_SAN_LIKE_RE = re.compile(
    r"^(?:O-O-O|O-O|[NBRQK][a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#?!]*|"
    r"[a-h]x[a-h][1-8](?:=[NBRQ])?[+#?!]*|[a-h][1-8](?:=[NBRQ])?[+#?!]*)$",
    re.I,
)


def ocr_clean_move_token(token: str) -> str:
    """Apply piece/square OCR repairs to one move token only."""
    if not token:
        return ""
    out = token.strip().replace("\u2019", "'").replace("\u2018", "'").replace("\u02bc", "'")
    out = out.replace("\\", "").replace("×", "x")
    # Leading sequence junk: bullets, queen-figurine salad before SAN
    out = re.sub(r"^[•·∙⋅]+", "", out)
    out = re.sub(r"^'+\(!?(?=[a-h][1-8])", "Q", out)
    out = re.sub(r"^'+\(!?\s*(?=[NBRQK])", "", out)
    out = re.sub(r"^\(\s*!\s*(?=[NBRQKa-h])", "", out)
    out = out.strip()
    # Castling inside token
    out = re.sub(r"^0\s*-{1,3}\s*0\s*-{1,3}\s*0$", "O-O-O", out)
    out = re.sub(r"^0\s*-{1,3}\s*0$", "O-O", out)
    out = re.sub(r"^O\s*-{1,3}\s*O\s*-{1,3}\s*O$", "O-O-O", out)
    out = re.sub(r"^O\s*-{1,3}\s*O$", "O-O", out)
    # Check glyph on SAN
    out = re.sub(
        r"^([NBRQK][a-h]?[1-8]?x?[a-h][1-8]|[a-h]x[a-h][1-8]|[a-h][1-8]|O-O-O|O-O)t$",
        r"\1+",
        out,
    )
    # Queens / kings
    out = re.sub(
        r"^(?:°1W|'l!|1!f/|1!f|'!ti|'!t[ií]|'\(!i|'Wi|1W|lW)",
        "Q",
        out,
    )
    out = re.sub(r"^Wid(?=[a-h]?[1-8])", "Qd", out)
    out = re.sub(r"^W(?=x[gfh]|[gfh][1-8])", "K", out)
    out = re.sub(r"^W(?=x[a-e]|[a-e][1-8])", "Q", out)
    out = re.sub(r"^@(?=[a-h]|x)", "K", out)
    # Knights
    out = re.sub(r"^(?:ltJ|l/J|ll'l|lt'l|ltl'|lll|lil|liJ|llJ|llil|l2J|4J|0\.J)", "N", out)
    out = re.sub(r"^J'(?=k[1-8]|[a-h][1-8]|x[a-h])", "N", out)
    out = re.sub(r"^Nk([1-8])$", r"Nc\1", out)
    out = re.sub(r"^Nkx(?=[a-h])", "Ncx", out)
    out = re.sub(r"^l0(?=[a-h1-8x])", "N", out)
    out = re.sub(r"^ll\.(?=l?[a-h])", "N", out)
    out = re.sub(r"^N([a-h])\s+([1-8])$", r"N\1\2", out)
    out = re.sub(r"^([NBRQK])\s+([a-h][1-8])$", r"\1\2", out)
    # Bishops — "1'." / "i." / "&." figurines (common PDF OCR)
    out = re.sub(r"^1'\.?", "B", out)
    out = re.sub(r"^\.i\.|^i\.(?=[a-h])", "B", out)
    out = re.sub(r"^\.!L?i|^\.!Li|^&\.?(?=[a-h])", "B", out)
    out = re.sub(r"^i(?=[a-h][1-8]$|[a-h]x|x[a-h])", "B", out)
    out = re.sub(r"^J\.f[lI1]$", "Bf2", out)
    out = re.sub(r"^J\.£6$|^J\.f6$", "Bf6", out)
    out = re.sub(r"^J\.([a-h][1-8])$", r"B\1", out)
    out = re.sub(r"^J\.([a-h]{2}[1-8])$", r"R\1", out)
    out = re.sub(r"^J\.([1-8][a-h][1-8])$", r"R\1", out)
    # Rooks
    out = re.sub(r"^(?::§:|E:|§|El)(?=[a-hx])", "R", out)
    out = re.sub(r"^l'hcl$", "Rxc1", out)
    out = re.sub(r"^l'hc", "Rxc", out)
    out = re.sub(r"^l'kl$", "Rc1", out)
    out = re.sub(r"^l'k([1-8])$", r"Rc\1", out)
    out = re.sub(r"^(?:i'!|l\"k|l'k|l'h)", "R", out)
    out = re.sub(r"^ilx(?=[a-h][1-8])", "Rx", out, flags=re.I)
    out = re.sub(r"^llx(?=[a-h][1-8])", "Rx", out, flags=re.I)
    out = re.sub(r"^aa(?=[1-8]$)", "Ra", out)
    # Square / capture cleanup
    out = re.sub(r"^([NBRQK])x?c[lI]$", r"\1xc1", out)
    out = re.sub(r"^([NBRQK])([a-h])[lI]$", r"\1\g<2>1", out)
    out = re.sub(r"([a-h])[lI](?=[+#?!]*$)", r"\g<1>1", out)
    out = re.sub(r"\s+x\s+", "x", out)
    out = re.sub(r"^([a-h])\s+x\s*([a-h][1-8])", r"\1x\2", out)
    out = re.sub(r"^([NBRQK])\s+([a-h][1-8])$", r"\1\2", out)
    out = re.sub(r"^([a-h])\s+([a-h][1-8])$", r"\1\2", out)
    out = re.sub(r"^([a-h])\s+([1-8])$", r"\1\2", out)
    # Annotation + Informator OCR via notation_dict aliases
    for n in (3, 2):
        if len(out) < n:
            continue
        tail = out[-n:]
        mark = normalize_notation_mark(tail)
        if mark and tail != mark:
            out = out[:-n] + mark
            break
        ev = normalize_position_eval(tail)
        if ev and tail in OCR_ALIASES:
            out = out[:-n].rstrip() + " " + ev
            break
    out = re.sub(r"^([NBRQK][a-h])\s*\?(?=[!?]|$)", r"\g<1>7", out)
    # Drop leftover dots glued after piece OCR ("B.e3" → "Be3")
    out = re.sub(r"^([NBRQK])\.(?=[a-h])", r"\1", out)
    # Collapse spaces inside one SAN ("N b4", "B f2", "h g3")
    compact = re.sub(r"\s+", "", out)
    if compact != out and (_SAN_LIKE_RE.match(compact) or re.fullmatch(
        r"[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](=?[NBRQ])?[+#?!]*", compact, re.I
    )):
        out = compact
    else:
        out = out.strip()
    return out


def _split_glued_move_token(token: str) -> list[str]:
    """Split OCR-glued moves: Bf2.Rg8 → [Bf2, Rg8]."""
    t = (token or "").strip()
    if not t:
        return []
    parts = re.split(r"\.(?=[NBRQK])", t)
    out: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        cleaned = ocr_clean_move_token(part) or part
        if cleaned:
            out.append(cleaned)
    return out or [t]


def _normalize_move_head(num: str, dots: str) -> str:
    if dots.startswith(".."):
        return f"{num}..."
    return f"{num}."


def ocr_clean_chess(text: str) -> str:
    """
    Clean chess text.

    Piece/square OCR repairs run only inside numbered move sequences
    (``31.`` / ``31...`` + move token). Prose stays untouched aside from
    safe global fixes.
    """
    if not text:
        return ""
    out = text.replace("\ufffd", "").replace("\u00a0", " ")
    out = out.replace("\u2019", "'").replace("\u2018", "'").replace("\u02bc", "'")
    out = out.replace("\\", "")
    # Global castling (often appears mid-prose without repair elsewhere)
    out = re.sub(r"0\s*-{1,3}\s*0\s*-{1,3}\s*0", "O-O-O", out)
    out = re.sub(r"0\s*-{1,3}\s*0", "O-O", out)
    out = re.sub(r"O\s*-{1,3}\s*O\s*-{1,3}\s*O", "O-O-O", out)
    out = re.sub(r"O\s*-{1,3}\s*O", "O-O", out)
    # Undo false + already baked into prose (correc+, protec+)
    out = re.sub(r"\b([a-z]{2,}[a-egh])\+", r"\1t", out)
    # Prose conditionals OCR'd as bishop: "Bf 27." / "g4.If"
    out = re.sub(r"([a-h][1-8])\.(?=If\b)", r"\1. ", out)
    out = re.sub(r"\bBf\s+(?=\d)", "If ", out)
    out = re.sub(r"\bBf(?=\d{2}\.)", "If ", out)
    out = re.sub(r"\bIf(?=\d)", "If ", out)
    # Move-number OCR: "3 LNb4" → "31.Nb4", "23 .." → "23..."
    out = re.sub(r"\b(\d)[ \t]+[lI][ \t]*\.\s*", r"\g<1>1.", out)
    out = re.sub(r"\b(\d)[ \t]+L(?=[NBRQK1'ia-h])", r"\g<1>1.", out)
    out = re.sub(r"\b(\d)[ \t]+L\.(?=[NBRQK1'ia-h])", r"\g<1>1.", out)
    out = re.sub(r"\b2[sS](?=\s*\.)", "28", out)
    # Bullets before ellipsis glue so "29 •••" becomes "29..." not "29 ..."
    out = re.sub(r"[•·∙⋅]{2,}", "...", out)
    out = re.sub(r"\b(\d+)\s*\.\s*\.\.\s*", r"\1...", out)
    out = re.sub(r"\b(\d+)\s+\.\.\.?\s*", r"\1...", out)
    out = re.sub(r"\b(\d+)\s*\.\s*\.\s+", r"\1... ", out)
    out = re.sub(r"\bint\s+eresting\b", "interesting", out, flags=re.I)
    out = re.sub(r"\bcoun\s+terplay\b", "counterplay", out, flags=re.I)
    out = re.sub(r"\bposi\s+tion\b", "position", out, flags=re.I)
    out = re.sub(r"(?m)^\s*a\s+b\s+c\s+d\s+e\s+f\s+g\s+h\s*$", "\n", out, flags=re.I)
    out = re.sub(r"(?m)^\d{2,3}\s+Family\s+[^\n]*$", "\n", out)
    out = _PAGE_HEADER_RE.sub("\n", out)
    out = _DIAGRAM_RE.sub("\n", out)

    # Piece OCR only on tokens that follow 12. / 12...
    chunks: list[str] = []
    pos = 0
    while True:
        head = _MOVE_HEAD_RE.search(out, pos)
        if not head:
            chunks.append(out[pos:])
            break
        chunks.append(out[pos : head.start()])
        prefix = _normalize_move_head(head.group(1), head.group(2))
        cursor = head.end()
        junk = _JUNK_BEFORE_MOVE_RE.match(out, cursor)
        if junk:
            cursor = junk.end()
        tok_m = _MOVE_TOKEN_RE.match(out, cursor)
        if not tok_m or _PROSE_STOP_RE.match(tok_m.group(0) or ""):
            chunks.append(out[head.start() : head.end()])
            pos = head.end()
            continue
        parts = _split_glued_move_token(tok_m.group(0))
        built = f"{prefix} {parts[0]}" if parts else prefix
        for extra in parts[1:]:
            built += f" {extra}"
        cursor = tok_m.end()
        gap = re.match(r"[ \t]+", out[cursor:] or "")
        if gap:
            nxt_at = cursor + gap.end()
            junk2 = _JUNK_BEFORE_MOVE_RE.match(out, nxt_at)
            if junk2:
                nxt_at = junk2.end()
            if not _MOVE_HEAD_RE.match(out, nxt_at):
                next_m = _MOVE_TOKEN_RE.match(out, nxt_at)
                if next_m and _looks_like_move_token(next_m.group(0)):
                    for reply in _split_glued_move_token(next_m.group(0)):
                        built += f" {reply}"
                    cursor = next_m.end()
        chunks.append(built)
        pos = cursor
    text = "".join(chunks)
    # Glued SAN.SAN left in prose tails of a sequence
    text = re.sub(
        r"\b([NBRQK][a-h]?[1-8]?x?[a-h][1-8][+#]?)\.([NBRQK][a-hx])",
        r"\1 \2",
        text,
    )
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +([,.;:!?])", r"\1", text)
    # ; excluded from move tokens, so += OCR (;i;) stays glued after SAN
    text = re.sub(
        r"((?:O-O-O|O-O|[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?|"
        r"[a-h]x[a-h][1-8]|[a-h][1-8])[!?]{0,3});[il1]+;?",
        r"\1 ⩲",
        text,
        flags=re.I,
    )
    # ! misread as f after annotation: fxe4?f → fxe4?!
    text = re.sub(
        r"((?:O-O-O|O-O|[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?|"
        r"[a-h]x[a-h][1-8]|[a-h][1-8])[!?]*)\?[fF](?=\s|$|[.;,)\]}])",
        r"\1?!",
        text,
        flags=re.I,
    )
    text = re.sub(
        r"((?:O-O-O|O-O|[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?|"
        r"[a-h]x[a-h][1-8]|[a-h][1-8])[!?]*)![fF](?=\s|$|[.;,)\]}])",
        r"\1!?",
        text,
        flags=re.I,
    )
    # ASCII Informator → canonical Unicode
    text = re.sub(r"(?<=\S)\s*\+=\b", " ⩲", text)
    text = re.sub(r"(?<=\S)\s*=\+\b", " ⩱", text)
    return text


def _looks_like_move_token(token: str) -> bool:
    t = (token or "").strip()
    if not t or _PROSE_STOP_RE.match(t):
        return False
    t = _JUNK_BEFORE_MOVE_RE.sub("", t).strip() or t
    if t[:1].islower() and not re.match(r"^[a-h](x[a-h])?[1-8]", t):
        return False
    if re.match(
        r"^(?:O-O-O|O-O|[NBRQK]|[1lI]'|[iltJ@&§]|ll|aa|[a-h]x|[a-h][1-8])",
        t,
        re.I,
    ):
        return True
    return bool(re.search(r"[a-h][1-8lI][+#?!]*$", t, re.I))


def normalize_prose_breaks(text: str) -> str:
    """Keep real paragraph breaks; flatten PDF soft-wrap newlines to spaces."""
    if not text:
        return ""
    out = text.replace("\r\n", "\n").replace("\r", "\n")
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n[ \t]+", "\n", out)
    out = re.sub(r"(?<=[a-z,;:])\n(?=[a-z])", " ", out)
    out = re.sub(r"(?<=[A-Za-z])\n(?=[a-z])", " ", out)
    out = re.sub(r"(?<=[.!?])\n(?=[A-Z\[\"'])", "\n\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"(?<!\n)\n(?!\n)", " ", out)
    out = re.sub(r"[ \t]+", " ", out)
    out = re.sub(r" *\n\n *", "\n\n", out)
    return out.strip()


def prose_is_usable(text: str, *, min_alpha: int = 40) -> bool:
    """True when text looks like coaching prose (not OCR move-salad)."""
    if not text:
        return False
    cleaned = strip_diagrams(ocr_clean_chess(text)).strip()
    cleaned = re.sub(r"^[?!+\s]+", "", cleaned)
    alpha = sum(1 for ch in cleaned if ch.isalpha())
    if alpha < min_alpha:
        return False
    if _PROSE_START_RE.search(cleaned) or _PROSE_START_RE.search(text):
        return True
    if alpha >= 55 and len(_ENGLISH_HINT_RE.findall(cleaned)) >= 3:
        return True
    if re.match(r"^[!?]+\s+\S", text.strip()) and alpha >= 40:
        return True
    return False


def strip_diagrams(text: str) -> str:
    out = _DIAGRAM_RE.sub(" ", text)
    out = _RANK_ONLY_RE.sub(" ", out)
    out = _PAGE_HEADER_RE.sub(" ", out)
    out = _GLYPH_SALAD_RE.sub(" ", out)
    return normalize_prose_breaks(out)


def clean_book_note(text: str) -> str:
    return strip_diagrams(ocr_clean_chess(text))


def san_tokens(text: str) -> list[str]:
    return _SAN_TOKEN_RE.findall(clean_book_note(text))


def split_movelist_and_prose(text: str) -> tuple[list[tuple[int | None, str | None, str]], str]:
    """
    Split leading score fragment into moves + trailing prose.

    Returns ([(fullmove|None, side|None, san), ...], prose).
    """
    cleaned = ocr_clean_chess(text)
    if not cleaned:
        return [], ""

    prose_match = _PROSE_START_RE.search(cleaned)
    head = cleaned
    prose_tail = ""
    if prose_match and prose_match.start() > 0:
        head = cleaned[: prose_match.start()]
        prose_tail = cleaned[prose_match.start() :].strip()
    elif prose_match and prose_match.start() == 0:
        return [], strip_diagrams(cleaned)

    moves: list[tuple[int | None, str | None, str]] = []
    pos = 0
    for match in _NUMBERED_MOVE_RE.finditer(head):
        gap = head[pos : match.start()].strip()
        if gap:
            for san_m in _SAN_TOKEN_RE.finditer(gap):
                token = san_m.group(0)
                if token[0].isupper() or token.startswith("O") or re.fullmatch(r"[a-h][1-8]", token):
                    moves.append((None, None, token))
        side = "black" if match.group("dots") else "white"
        moves.append((int(match.group("num")), side, match.group("san")))
        pos = match.end()

    rest = head[pos:].strip()
    for san_m in _SAN_TOKEN_RE.finditer(rest):
        token = san_m.group(0)
        if token[0].isupper() or token.startswith("O") or re.fullmatch(r"[a-h][1-8]", token):
            moves.append((None, None, token))

    prose = strip_diagrams(prose_tail or rest)
    prose_match = _PROSE_START_RE.search(prose)
    if prose_match and prose_match.start() > 0:
        prose = prose[prose_match.start() :].strip()
    return moves, prose


def extract_variation_snippets(prose: str) -> tuple[str, list[str]]:
    """Pull parenthetical / 'Better was' sidelines out of prose."""
    variations: list[str] = []
    if not prose:
        return "", variations

    def _keep(chunk: str) -> bool:
        chunk = chunk.strip(" ;,.")
        if len(chunk) < 8:
            return False
        return len(_SAN_TOKEN_RE.findall(chunk)) >= 1

    for match in re.finditer(r"\(([^)]{8,220})\)", prose):
        inner = clean_book_note(match.group(1))
        if _keep(inner):
            variations.append(inner)

    prose_wo = prose
    for match in re.finditer(
        r"\b((?:Better was|Instead|The try|Not)\s+[^.]{8,180}\.)",
        prose_wo,
        re.I,
    ):
        variations.append(clean_book_note(match.group(1)))

    prose_wo = re.sub(r"\s+", " ", prose_wo).strip()
    return prose_wo, variations
