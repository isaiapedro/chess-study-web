from __future__ import annotations

import re

from chess_coach.chess_text_grammar import (
    MOVE_HEAD_RE,
    normalize_ellipsis_forms,
    normalize_move_head,
)
from chess_coach.notation_dict import (
    OCR_ALIASES,
    apply_piece_ocr_prefix,
    normalize_notation_mark,
    normalize_position_eval,
    replace_piece_ocr_glyphs,
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
    r"And as usually|And we have|A better defence|Black missed|Weak is |"
    r"Making things|This is the key|This is an |This is a |"
    r"Of course |It [a-z]+ |deserves |"
    r"The (?:knight|bishop|rook|queen|king|pawn|piece) |"
    r"But now|Suicidal is |"
    r"If |When |While |Although |Though |Should |"
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


def glue_spaced_san(text: str) -> str:
    """
    Collapse OCR spaces inside SAN fragments (universal, post piece-glyph).

    Nc 6 → Nc6, fx e4 → fxe4, Ra 1 → Ra1, fic e4 → fxe4,
    fg5 → fxg5 (adjacent missing-x, not leading h),
    hg3 / hc4 → Bxg3 / Bxc4 (Quality Chess bishop figurine OCR as h).
    """
    if not text:
        return ""
    out = text
    # Pawn capture OCR: "fic e4" (x→ic) / "fx e4"
    out = re.sub(r"\bfic\s*([a-h])\s*([1-8])\b", r"fx\1\2", out, flags=re.I)
    out = re.sub(r"\b([a-h])x\s+([a-h][1-8])\b", r"\1x\2", out, flags=re.I)
    out = re.sub(r"\b([a-h])\s+x\s+([a-h][1-8])\b", r"\1x\2", out, flags=re.I)
    # Pawn capture missing x on adjacent files — but NOT leading "h"
    # (Quality Chess bishop figurine often OCR's as "h" + square: hg3 → Bxg3).
    # Real h-pawn captures keep an "x" or space: "hxg3" / "h xg4".
    def _pawn_cap(m: re.Match[str]) -> str:
        a, dest = m.group(1), m.group(2).lower()
        # Case-sensitive: uppercase first letter is piece SAN (Ba7), not file b+a7
        if a != a.lower():
            return m.group(0)
        a = a.lower()
        if a == "h":
            return m.group(0)
        if abs(ord(a) - ord(dest[0])) != 1:
            return m.group(0)
        return f"{a}x{dest}"

    out = re.sub(r"\b([a-hA-H])([a-h][1-8])\b", _pawn_cap, out)
    # Bishop figurine OCR as "h" / ".h" before destination: hc4 → Bxc4, hg3 → Bxg3
    out = re.sub(r"\.h(?=[a-h][1-8])", "Bx", out)
    # Bishop-as-h with f OCR'd as i: hi7 → Bxf7 (before generic h+square)
    out = re.sub(r"\bh[iI]([1-8])\b", r"Bxf\1", out, flags=re.I)
    out = re.sub(r"\bh([a-h][1-8])\b", r"Bx\1", out, flags=re.I)
    # Bishop-as-h + file + OCR rank l/I (back-rank capture): hfl → Bxf1
    out = re.sub(r"\bh([a-h])[lI]\b", r"Bx\g<1>1", out, flags=re.I)
    # Piece + file + spaced rank: Nc 6, Ra 1, Bf 4
    out = re.sub(r"\b([NBRQK])([a-h])\s+([1-8])\b", r"\1\2\3", out)
    # Piece + spaced square: N b4
    out = re.sub(r"\b([NBRQK])\s+([a-h][1-8])\b", r"\1\2", out)
    # Piece + spaced capture: Q xa5 / Q x a5
    out = re.sub(r"\b([NBRQK])\s+x\s*([a-h][1-8])\b", r"\1x\2", out)
    # Disambiguation + spaced rank already covered; capture piece form N x e5 rare
    out = re.sub(r"\b([NBRQK][a-h]?[1-8]?)x\s+([a-h][1-8])\b", r"\1x\2", out)
    return out


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
    # Figurine OCR via notation_dict.PIECE_OCR_GLYPHS
    out = apply_piece_ocr_prefix(out)
    out = glue_spaced_san(out)
    # Context-sensitive leftovers (need lookahead / not dict-safe alone)
    out = re.sub(r"^W(?=x[gfh]|[gfh][1-8])", "K", out)
    out = re.sub(r"^W(?=x[a-e]|[a-e][1-8])", "Q", out)
    out = re.sub(r"^@(?=[a-h]|x)", "K", out)
    # Queen OCR Ye… as whole token (Yeal / Yea1 → Q + file + rank fix)
    out = re.sub(r"^Ye(?=[a-h][1-8lI])", "Q", out, flags=re.I)
    # Knights — leftover patterns
    out = re.sub(r"^J'(?=k[1-8]|[a-h][1-8]|x[a-h])", "N", out)
    out = re.sub(r"^Nk([1-8])$", r"Nc\1", out)
    out = re.sub(r"^Nkx(?=[a-h])", "Ncx", out)
    out = re.sub(r"^l0(?=[a-h1-8x])", "N", out)
    out = re.sub(r"^ll\.(?=l?[a-h])", "N", out)
    out = re.sub(r"^N([a-h])\s+([1-8])$", r"N\1\2", out)
    out = re.sub(r"^([NBRQK])\s+([a-h][1-8])$", r"\1\2", out)
    # Bishops — context leftovers
    out = re.sub(r"^\.!L?i|^\.!Li", "B", out)
    out = re.sub(r"^i(?=[a-h][1-8]$|[a-h]x|x[a-h])", "B", out)
    out = re.sub(r"^J\.([a-h][1-8])$", r"B\1", out)
    out = re.sub(r"^J\.([a-h]{2}[1-8])$", r"R\1", out)
    out = re.sub(r"^J\.([1-8][a-h][1-8])$", r"R\1", out)
    # Rooks leftovers
    out = re.sub(r"^(?:§|\.§)(?=[a-hx])", "R", out)
    out = re.sub(r"^aa(?=[1-8]$)", "Ra", out)
    # Square / capture cleanup
    out = re.sub(r"^([NBRQK])x?c[lI]$", r"\1xc1", out)
    # Piece+file+l/I rank OCR: R/Q → 1 (back rank); N → 7; B/K → 7;
    # captures Rxal → Rxa1 (back-rank trades).
    out = re.sub(r"^([NBRQK]x[a-h])[lI](?=[+#?!]*$)", r"\g<1>1", out)
    out = re.sub(r"^R([a-h])[lI](?=[+#?!]*$)", r"R\g<1>1", out)
    out = re.sub(r"^Q([a-h])[lI](?=[+#?!]*$)", r"Q\g<1>1", out)
    out = re.sub(r"^N([a-h])[lI](?=[+#?!]*$)", r"N\g<1>7", out)
    out = re.sub(r"^([BK][a-h])[lI](?=[+#?!]*$)", r"\g<1>7", out)
    # Rank letter OCR: s/S — Q/R often back-rank 8; N/B/K prefer 5 (S≈5)
    out = re.sub(r"^([QR][a-h])[sS](?=[+#?!]*$)", r"\g<1>8", out)
    out = re.sub(r"^([NBK][a-h])[sS](?=[+#?!]*$)", r"\g<1>5", out)
    # Bare file+l/I token = lost queen figurine (fl → Qf1)
    out = re.sub(r"^([a-h])[lI](?=[+#?!]*$)", r"Q\g<1>1", out)
    # Bare file+l → file+1 (a1); do not apply after piece letter
    out = re.sub(r"(?<![NBRQK])([a-h])[lI](?=[+#?!]*$)", r"\g<1>1", out)
    out = re.sub(r"\s+x\s+", "x", out)
    out = re.sub(r"^([a-h])\s+x\s*([a-h][1-8])", r"\1x\2", out)
    out = re.sub(r"^([NBRQK])\s+([a-h][1-8])$", r"\1\2", out)
    out = re.sub(r"^([a-h])\s+([a-h][1-8])$", r"\1\2", out)
    out = re.sub(r"^([a-h])\s+([1-8])$", r"\1\2", out)
    out = glue_spaced_san(out)
    # Annotation + Informator OCR via notation_dict aliases
    for n in (5, 4, 3, 2):
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
        alias = OCR_ALIASES.get(tail)
        if alias and alias != tail:
            out = out[:-n].rstrip() + (" " + alias if alias.startswith(("⩲", "⩱", "±")) or " " in alias else alias)
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


def ocr_clean_chess(text: str) -> str:
    """
    Clean chess text.

    Piece/square OCR repairs run only inside numbered move sequences
    (``31.`` / ``31...`` + move token). Prose stays untouched aside from
    safe global fixes.
    """
    if not text:
        return ""
    out = text.replace("\u00a0", " ")
    # Lost piece (FFFD) + OCR rank digit (3↔0/o): bootstrap f-file square.
    # Align matches same destination; Layer 5 fills piece when unique.
    def _fffd_rank_sq(m: re.Match[str]) -> str:
        rank = {"0": "3", "o": "3", "O": "3", "l": "1", "I": "1", "i": "1"}.get(
            m.group(2), m.group(2)
        )
        return f"{m.group(1)}. f{rank}"

    out = re.sub(r"\b(\d+)\s*\ufffd\s*([0oOlIi])\b", _fffd_rank_sq, out)
    out = out.replace("\u2019", "'").replace("\u2018", "'").replace("\u02bc", "'")
    out = out.replace("\\", "")
    # Leading OCR "I.d4" / "I...Nf6" (digit 1 as capital I)
    out = re.sub(r"(?<![A-Za-z0-9])I\s*\.\s*\.\.(?=\s*[NBRQKa-h\ufffd])", "1...", out)
    out = re.sub(r"(?<![A-Za-z0-9])I\s*\.(?=\s*[NBRQKa-h\ufffd])", "1.", out)
    # Queen figurine salad: Ye… / vti' / '!W / Wl… (Quality Chess); rank l→1 later
    out = re.sub(r"\bYe(?=[a-h][1-8lI])", "Q", out, flags=re.I)
    out = re.sub(r"\bvti['\u2019]?\s*(?=[a-h1-8])", "Q", out, flags=re.I)
    out = re.sub(r"\bWl(?=[a-h1-8])", "Q", out)
    out = re.sub(r"'!W(?=[a-h])", "Q", out)
    # Global castling (often appears mid-prose without repair elsewhere)
    out = re.sub(r"0\s*-{1,3}\s*0\s*-{1,3}\s*0", "O-O-O", out)
    out = re.sub(r"0\s*-{1,3}\s*0", "O-O", out)
    out = re.sub(r"O\s*-{1,3}\s*O\s*-{1,3}\s*O", "O-O-O", out)
    out = re.sub(r"O\s*-{1,3}\s*O", "O-O", out)
    # Glued castling + next move number: O-O6.Nf3 → O-O 6.Nf3
    out = re.sub(r"\b(O-O-O|O-O)(?=\d+\.)", r"\1 ", out)
    # Glued SAN + next move number: dxc47.Qc2 → dxc4 7.Qc2
    out = re.sub(
        r"\b((?:O-O-O|O-O|[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#?!]*))"
        r"(?=\d{1,3}\.)",
        r"\1 ",
        out,
        flags=re.I,
    )
    # Undo false + already baked into prose (correc+, protec+)
    out = re.sub(r"\b([a-z]{2,}[a-egh])\+", r"\1t", out)
    # Prose conditionals OCR'd as bishop / slash: "Bf 27." / "I/ 22." / "g4.If"
    out = re.sub(r"([a-h][1-8])\.(?=If\b)", r"\1. ", out)
    out = re.sub(r"\bBf\s+(?=\d)", "If ", out)
    out = re.sub(r"\bBf(?=\d{2}\.)", "If ", out)
    out = re.sub(r"\bI/(?=\s*(?:\d|\.\.\.|[A-Za-z]|$))", "If ", out)
    out = re.sub(r"\bIf(?=\d)", "If ", out)
    # Move-number OCR: "3 LNb4" / "3 Llilb4" → "31.Nb4", "23 .." → "23..."
    out = re.sub(r"\b(\d)[ \t]+[lI][ \t]*\.\s*", r"\g<1>1.", out)
    out = re.sub(r"\b(\d)[ \t]+L(?=[NBRQK1'lia-hlt/])", r"\g<1>1.", out)
    out = re.sub(r"\b(\d)[ \t]+L\.(?=[NBRQK1'lia-hlt/])", r"\g<1>1.", out)
    # Double-l as tens digit: ll.d5 / ll .d5 → 11.d5 (OCR 1→l)
    out = re.sub(r"\bll\s*\.(?=\s*[NBRQKa-h])", "11.", out)
    out = re.sub(r"\bl([1-9])\s*\.(?=\s*[NBRQKa-h])", r"1\1.", out)
    out = re.sub(r"\b2[sS](?=\s*\.)", "28", out)
    # Rule B: ellipsis normalize → White two-dot (chess_text_grammar)
    out = normalize_ellipsis_forms(out)
    # Knight salad: 6.�gf.3 / 6.gf.3 → Nf3 (Quality Chess N figurine + glued f3)
    out = re.sub(r"\ufffd\s*gf\.?\s*([1-8])\b", r"Nf\1", out, flags=re.I)
    out = re.sub(r"\b(\d+)\.\s*gf\.?\s*([1-8])\b", r"\1. Nf\2", out, flags=re.I)
    # Numbered Black ellipsis + FFFD → bare dest (Layer 5 + capture-hint fills Q/N/B).
    out = re.sub(r"(\d+\s*\.\.\.\s*)\ufffd\s*(?=x?[a-h][1-8])", r"\1", out)
    # Plan ellipsis (with… �d7) → bishop; numbered case already handled above.
    out = re.sub(r"(\.\.\.\s*)\ufffd\s*(?=x?[a-h][1-8])", r"\1B", out)
    # Remaining FFFD before square → Q (White queen figurine common case).
    out = re.sub(r"\ufffd\s*(?=x?[a-h][1-8])", "Q", out)
    out = re.sub(r"\ufffd\s*(?=f[l1I]\b)", "Q", out)
    out = re.sub(r"\ufffd(?=[a-h][l1I])", "Q", out)
    out = out.replace("\ufffd", "")
    # Spaced tens digit after FFFD→piece: "1 O.Qxd5" / "l 1.Bxd2" → 10. / 11.
    out = re.sub(r"\b(\d)\s+[O0o]\s*\.(?=\s*[NBRQKa-hx])", r"\g<1>0.", out)
    out = re.sub(r"\bl\s+([1-9])\s*\.(?=\s*[NBRQKa-hx])", r"1\1.", out)
    # After FFFD strip: lone OCR-digit before figurine capture-dot (&.sq)
    out = re.sub(
        r"\b(\d+)\s+([0oO])\s+(?=&\.)",
        lambda m: f"{m.group(1)}. f{'3' if m.group(2) in '0oO' else m.group(2)} ",
        out,
    )
    # After …, lost bishop figurine as i/t/h + square (.id8 / tds / .ih6)
    out = re.sub(
        r"(\.\.\.\s*)\.?([iht])(?=[a-h][1-8sS]\b)",
        r"\1B",
        out,
        flags=re.I,
    )
    # Bishop OCR rank letter s/S after that rewrite → 8 (.id8 / tds)
    out = re.sub(r"(\.\.\.\s*B[a-h])[sS]\b", r"\g<1>8", out)
    # Rook OCR: colon (+ optional junk letter) before square (:a7 / :ga7).
    # Do not steal ``!:ib7`` / ``E:b3`` (handled as rook figurines below).
    out = re.sub(r"(?<![A-Za-z0-9!E]):[a-z]?(?=[a-h][1-8])", "R", out, flags=re.I)
    out = re.sub(r"(?<![!'])\bl:(?=k|[a-h])", "R", out, flags=re.I)
    out = re.sub(r"\bRk(?=[a-h1-8lI])", "Rc", out)
    # Rook OCR "E:b3" / "E:5c7" — colon is excluded from move tokens, so normalize early
    out = re.sub(r"(?<![A-Za-z0-9])E:(?=[a-h1-8x])", "R", out)
    # Rook OCR section sign (Quality Chess)
    out = re.sub(r"\.§(?=[a-h])", "R", out)
    out = re.sub(r"(?<![A-Za-z0-9])§(?=[a-h])", "R", out)
    # Bishop OCR: lost-dot "ixb6" / "ia6" / "ia?!" (Quality Chess i. → i)
    out = re.sub(r"(?<![A-Za-z0-9])i(?=x[a-h][1-8])", "B", out)
    out = re.sub(r"(?<![A-Za-z0-9])i(?=a[1-8])", "B", out)
    # Spaced bishop figurine: "38.i a5!" → Ba5
    out = re.sub(r"(?<![A-Za-z0-9])i\s+([a-h][1-8])", r"B\1", out)
    # Bishop + file + marks, lost rank: ia?! → Ba?! (Layer 5 fills when unique)
    out = re.sub(r"(?<![A-Za-z0-9])i([a-h])(?=[!?]{1,3})", r"B\1", out)
    # Variation braces OCR'd as curly: {or 38... +-)
    out = re.sub(r"\{(?=\s*or\b)", "(", out, flags=re.I)
    out = re.sub(r"\{(?=\s*\d+\.)", "(", out)
    # Rook figurine → J: Jkb8 → Rcb8, Jb8 → Rb8
    out = re.sub(r"\bJk(?=[a-h][1-8])", "Rc", out)
    out = re.sub(r"\bJ(?=[a-h][1-8])", "R", out)
    # Rook lost letter: 39.gb3 → 39.Rb3 (g + square ≠ pawn g3)
    out = re.sub(r"\b(\d+)\.\s*[Gg](?=[a-h][1-8]\b)", r"\1. R", out)
    # Rook as g before non-adjacent capture (pawn g only takes f/h): gxb5 / gxbS → Rxb…
    out = re.sub(r"\bg(?=x[a-eg][1-8sS])", "R", out, flags=re.I)
    # Capture dest rank OCR: RxbS / xbS → …b5 (S looks like 5)
    out = re.sub(r"\b([NBRQK][a-h]?x[a-h]|x[a-h])[sS]\b", r"\g<1>5", out)
    # Score-line figurine bootstrap (Quality Chess): 32.ffe2 !:ib7 33.ttlc4:t:
    # Queen salad Wff/Yff/Yfif/Yfix/Wif (before bare ff→Q)
    out = re.sub(r"\b[WY]fi?xf?lt\b", "Qxf7+", out, flags=re.I)
    out = re.sub(r"\b[WY]fff?lt\b", "Qxf7+", out, flags=re.I)
    out = re.sub(r"\b[WY]fif[l1I]\b", "Qf7", out, flags=re.I)
    out = re.sub(r"\bWif(?=[1-8])", "Qf", out, flags=re.I)
    out = re.sub(r"\b[WY]ff(?=\s*[a-hx])", "Q", out, flags=re.I)
    out = re.sub(r"=\s*[WY]ff\b", "=Q", out, flags=re.I)
    out = re.sub(r"\bff(?=[a-h][1-8])", "Q", out)
    out = re.sub(r"\bttl(?=[a-h])", "N", out, flags=re.I)
    # Knight tee/tex spaced: tee 6 → Ne6, tex g7 → Nxg7
    out = re.sub(r"\btee\s*([1-8])\b", r"Ne\1", out, flags=re.I)
    out = re.sub(r"\btex\s*([a-h][1-8])\b", r"Nx\1", out, flags=re.I)
    out = re.sub(r"!:i(?=[a-h])", "R", out)
    out = re.sub(r"!:(?=[a-h][1-8])", "R", out)
    # Rook OCR :9' / l!b (Quality Chess)
    out = re.sub(r":9'\.?", "R", out)
    out = re.sub(r"\bl!b(?=[a-h1-8lI])", "Rb", out, flags=re.I)
    # Rook figurine J + OCR junk before square: J�b2 / JQb2 → Rb2
    out = re.sub(r"\bJ(?:[\ufffd]|Q)?(?=[a-h][1-8]\b)", "R", out)
    out = re.sub(r":t:", "±", out)
    out = re.sub(r"(?<=[NBRQKa-h1-8])\s*:t\b", "±", out)
    # King @ / file+i → rank 1: 35.@hi → 35.Kh1
    out = re.sub(r"@(?=[a-h])", "K", out)
    out = re.sub(r"\b(K[a-h])[iI]\b", r"\g<1>1", out)
    # King figurine 'it> / it> / 'tt> (Quality Chess > for l)
    out = re.sub(r"'it>(?=[a-h])", "K", out, flags=re.I)
    out = re.sub(r"(?<![A-Za-z0-9])it>(?=[a-h])", "K", out, flags=re.I)
    out = re.sub(r"'tt>(?=[a-h])", "K", out, flags=re.I)
    out = re.sub(r"(?<![A-Za-z0-9])tt>(?=[a-h])", "K", out, flags=re.I)
    # Lost bishop before e8 after move marks: ! �es / ! es → Be8
    out = re.sub(r"([!?]{1,3})\s*[\ufffd]?\s*es\b", r"\1 Be8", out)
    # Queen glyph f? / Q/R + file + S → rank 8; N/B/K + file + S → rank 5 (S≈5)
    out = re.sub(r"\b(f\?|[QR])([a-h])[sS]\b", r"\1\g<2>8", out)
    out = re.sub(r"\b([NBK])([a-h])[sS]\b", r"\1\g<2>5", out)
    # Diagram salad after White head (m:t etc.): drop junk, next SAN is Black reply
    # 34.m:t Kg7 → 34...Kg7 (do not invent Rf1)
    out = re.sub(
        r"\b(\d+)\.\s*[a-z]{1,2}:[a-z0-9]{1,2}\s+"
        r"(?=(?:O-O-O|O-O|[NBRQK][a-hx]|[a-h]x?[a-h]?[1-8]))",
        r"\1... ",
        out,
        flags=re.I,
    )
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
        head = MOVE_HEAD_RE.search(out, pos)
        if not head:
            chunks.append(out[pos:])
            break
        chunks.append(out[pos : head.start()])
        prefix = normalize_move_head(head.group("num"), head.group("dots"), head.group("bare"))
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
            if not MOVE_HEAD_RE.match(out, nxt_at):
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
    # Keep space before ".Bh6" / ".ih6" (figurine leftover), not before ".d5" pawn
    text = re.sub(r" +([,;:!?]|\.(?![NBRQK][a-hx]|i[a-h]))", r"\1", text)
    # Punct collapse can glue leftover ellipsis dots: 44... . → 44.... → 44...
    text = re.sub(r"\b(\d+)\.{3}\s*\.(?!\.)", r"\1...", text)
    text = re.sub(r"\b(\d+)\.{4,}", r"\1...", text)
    # Mid-prose figurine OCR first, then spaced-SAN glue (lilc 6 → Nc 6 → Nc6)
    text = replace_piece_ocr_glyphs(text)
    text = glue_spaced_san(text)
    # Rook salad mid-prose: E'.xf7 / E'xb6 (Quality Chess rook + apostrophe)
    text = re.sub(r"\bE'\.?(?=x)", "R", text)
    # Knight l0 mid-prose: l0 xb6 / l0h6 (token path already has ^l0)
    text = re.sub(r"\bl0\s*x\s*([a-h][1-8])", r"Nx\1", text)
    text = re.sub(r"\bl0\s+([a-h][1-8])", r"N\1", text)
    text = re.sub(r"\bl0(?=[a-h][1-8]|x)", "N", text)
    # King 'itl / 'it> / 'tt> / itl / lt> mid-prose: 'itlg7 → Kg7, 'tt>g7 → Kg7
    text = re.sub(r"'itl(?=[a-h])", "K", text, flags=re.I)
    text = re.sub(r"'it>(?=[a-h])", "K", text, flags=re.I)
    text = re.sub(r"'tt>(?=[a-h])", "K", text, flags=re.I)
    text = re.sub(r"(?<![A-Za-z0-9])itl(?=[a-h])", "K", text, flags=re.I)
    text = re.sub(r"(?<![A-Za-z0-9])it>(?=[a-h])", "K", text, flags=re.I)
    text = re.sub(r"(?<![A-Za-z0-9])tt>(?=[a-h])", "K", text, flags=re.I)
    text = re.sub(r"lt>K?(?=[a-h])", "K", text)
    # Queen salad mid-prose (Wff/Yfif/Yfix after soft-wrap)
    text = re.sub(r"\b[WY]fi?xf?lt\b", "Qxf7+", text, flags=re.I)
    text = re.sub(r"\b[WY]fff?lt\b", "Qxf7+", text, flags=re.I)
    text = re.sub(r"\b[WY]fif[l1I]\b", "Qf7", text, flags=re.I)
    text = re.sub(r"\bWif(?=[1-8])", "Qf", text, flags=re.I)
    text = re.sub(r"\b[WY]ff(?=\s*[a-hx])", "Q", text, flags=re.I)
    text = re.sub(r"=\s*[WY]ff\b", "=Q", text, flags=re.I)
    text = re.sub(r"\btee\s*([1-8])\b", r"Ne\1", text, flags=re.I)
    text = re.sub(r"\btex\s*([a-h][1-8])\b", r"Nx\1", text, flags=re.I)
    text = re.sub(r":9'\.?", "R", text)
    text = re.sub(r"\bl!b(?=[a-h1-8lI])", "Rb", text, flags=re.I)
    text = re.sub(r"\bJ(?:[\ufffd]|Q)?(?=[a-h][1-8]\b)", "R", text)
    text = re.sub(r"([!?]{1,3})\s*[\ufffd]?\s*es\b", r"\1 Be8", text)
    # Queen 'Ml'xg3
    text = re.sub(r"'Ml'?(?=x?[a-h])", "Q", text)
    # Bishop bare i before square mid-prose (ih4); Layer 5 fixes false Bg5→g5
    text = re.sub(r"(?<![A-Za-z0-9])i(?=[a-h][1-8](?:[+#!=]|\b))", "B", text)
    # Doubled bishop OCR: iBh4 / iBe3 (figurine i. left beside already-restored B)
    text = re.sub(r"\biB(?=[a-h])", "B", text)
    # Rook salad Elxa / Elxa1 / !'l:xb6 (Quality Chess rook junk)
    text = re.sub(r"\bEl(?=x[a-h])", "R", text)
    text = re.sub(r"!'l:", "R", text)
    text = re.sub(r"!'\s*l:", "R", text)
    # Glued SAN+SAN after figurine restore: Bb4Rd8 → Bb4 Rd8
    text = re.sub(
        r"\b([NBRQK][a-h]?[1-8]?x?[a-h][1-8][+#?!]*)(?=[NBRQK][a-hx])",
        r"\1 ",
        text,
    )
    # Pawn reply glued via leftover dot: h4.Bh6 → h4 Bh6
    text = re.sub(
        r"\b([a-h][1-8][+#?!]*)\.([NBRQK][a-hx])",
        r"\1 \2",
        text,
    )
    # Spaced leftover figurine dot after restore: h4 .Bh6 → h4 Bh6
    text = re.sub(
        r"(?<=[a-h1-8+#?!])\s+\.([NBRQK][a-hx])",
        r" \1",
        text,
    )
    # Rook-as-g capture + dest S→5 mid-prose (after token walk)
    text = re.sub(r"\bg(?=x[a-eg][1-8sS])", "R", text, flags=re.I)
    text = re.sub(r"\b([NBRQK][a-h]?x[a-h]|x[a-h])[sS]\b", r"\g<1>5", text)
    # Move-number OCR: 4o. → 40. (digit o/O as zero)
    text = re.sub(r"\b(\d)[oO]\.(?=\s*[NBRQKa-h])", r"\g<1>0.", text)
    # Check: trailing t after SAN → + (dict alias t→+; apply only on move shapes)
    text = re.sub(
        r"\b([NBRQK]?[a-h]?[1-8]?x?[a-h][1-8]|O-O-O|O-O)t(?=\s|$|[;,)\]}?!])",
        r"\1+",
        text,
    )
    # Space Informator +- / -+ glued after SAN: Bd4+- → Bd4 +-
    text = re.sub(
        r"\b([NBRQK]?[a-h]?[1-8]?x?[a-h][1-8]|O-O-O|O-O)([!?]?)\+-",
        r"\1\2 +-",
        text,
    )
    text = re.sub(
        r"\b([NBRQK]?[a-h]?[1-8]?x?[a-h][1-8]|O-O-O|O-O)([!?]?)-(?=\+)",
        r"\1\2 -",
        text,
    )
    # Informator ;t after move / king mark
    text = re.sub(r";t\b", " ⩲", text)
    # Piece+file+l mid-prose: R/Q→1, N→7, B/K→7; captures →1
    text = re.sub(r"\b([NBRQK]x[a-h])\s*[lI]\b", r"\g<1>1", text)
    text = re.sub(r"\b([NBRQK]x[a-h])[lI]\b", r"\g<1>1", text)
    text = re.sub(r"\bR([a-h])[lI]t(?=\+-)", r"R\g<1>1", text)
    text = re.sub(r"\bR([a-h])[lI]t(?=[+#?!]|\b)", r"R\g<1>1+", text)
    text = re.sub(r"\bR([a-h])[lI](?=[+#?!]|\b)", r"R\g<1>1", text)
    text = re.sub(r"\bQ([a-h])[lI](?=[+#?!]|\b)", r"Q\g<1>1", text)
    text = re.sub(r"\bN([a-h])[lI](?=[+#?!]|\b)", r"N\g<1>7", text)
    text = re.sub(r"\b([BK][a-h])[lI](?=[+#?!]|\b)", r"\g<1>7", text)
    # Rank letter OCR mid-prose: QdS → Qd8; NcS → Nc5
    text = re.sub(r"\b([QR][a-h])[sS]\b", r"\g<1>8", text)
    text = re.sub(r"\b([NBK][a-h])[sS]\b", r"\g<1>5", text)
    # White two-dot leftover after late piece OCR: 39..Bg1 → 39.Bg1
    text = re.sub(r"\b(\d+)\.\.(?!\.)(?=[NBRQK])", r"\1.", text)
    # Lost queen figurine: bare file+l/I after move head → Q + file + rank 1
    text = re.sub(r"\b(\d+)\.\s*([a-h])[lI](?=[+#?!]|\b)", r"\1. Q\g<2>1", text)
    # ; excluded from move tokens, so += OCR (;i; / ;!;) stays glued after SAN
    text = re.sub(
        r"((?:O-O-O|O-O|[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?|"
        r"[a-h]x[a-h][1-8]|[a-h][1-8])[!?]{0,3})"
        r"(?:;!;|!;!;|;[il1I]+;?)",
        r"\1 ⩲",
        text,
        flags=re.I,
    )
    # !? + Informator junk glued: Ra1!?;!; → Ra1!? ⩲
    text = re.sub(
        r"((?:O-O-O|O-O|[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?|"
        r"[a-h]x[a-h][1-8]|[a-h][1-8])!\?);!;?",
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
    # Common OCR: bur after → but after
    text = re.sub(r"\bbur\s+after\b", "but after", text, flags=re.I)
    # ASCII Informator → canonical Unicode
    text = re.sub(r"(?<=\S)\s*\+=\b", " ⩲", text)
    text = re.sub(r"(?<=\S)\s*=\+\b", " ⩱", text)
    return text


def _looks_like_move_token(token: str) -> bool:
    t = (token or "").strip()
    if not t or _PROSE_STOP_RE.match(t):
        return False
    t = _JUNK_BEFORE_MOVE_RE.sub("", t).strip() or t
    cleaned = ocr_clean_move_token(t)
    if cleaned and _SAN_LIKE_RE.match(cleaned):
        return True
    if re.match(
        r"^(?:O-O-O|O-O|[NBRQK]|[1lI]'|[iltJ@&§]|ll|il|aa|[a-h]x|[a-h][1-8])",
        t,
        re.I,
    ):
        return True
    if t[:1].islower() and not re.match(r"^[a-h](x[a-h])?[1-8]", t):
        return False
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
    cleaned = re.sub(r"^[?!+\s±∓+=\-−]+", "", cleaned)
    alpha = sum(1 for ch in cleaned if ch.isalpha())
    # Clear coaching openers win even when the note is short ("If 28... f4?! …").
    if _PROSE_START_RE.search(cleaned) or _PROSE_START_RE.search(text):
        return alpha >= 6
    if alpha < min_alpha:
        return False
    if alpha >= 55 and len(_ENGLISH_HINT_RE.findall(cleaned)) >= 3:
        return True
    if re.match(r"^[!?]+\s+\S", text.strip()) and alpha >= 40:
        return True
    return False


_DIAGRAM_SALAD_HEAD_RE = re.compile(
    r"(?:"
    r"\bnm\s+rn\b|"  # Quality Chess empty-board OCR row
    r"[\"']{2,}|"  # """ / ''' runs from diagram glyphs
    r",{3,}|"
    r"\b[1-8]\s+[a-z]{1,3}\s+[a-z]{1,3}\s+[1-8]\.|"  # 8 nm rn 7.
    r"[/\\]{2,}|"  # // -- glyph noise
    r"[·∙⋅]{2,}"
    r")",
    re.I,
)


def _is_diagram_salad_head(head: str) -> bool:
    """True when text before a prose opener is board-diagram OCR junk."""
    h = (head or "").strip()
    if len(h) < 8:
        return False
    if _DIAGRAM_SALAD_HEAD_RE.search(h):
        return True
    # Strip a leading SAN echo (Rxc5 …) then re-check density
    h2 = re.sub(
        r"^(?:\[Book:[^\]]*\]\s*)?(?:O-O-O|O-O|[NBRQK]?[a-h]?[1-8]?x?[a-h][1-8][+#?!]*)\s+",
        "",
        h,
        flags=re.I,
    ).strip()
    probe = h2 or h
    if _DIAGRAM_SALAD_HEAD_RE.search(probe):
        return True
    alpha = sum(1 for ch in probe if ch.isalpha())
    if len(probe) >= 24 and alpha / max(len(probe), 1) < 0.38:
        return True
    punct = sum(1 for ch in probe if ch in ",.'\"`;:|/\\·∙⋅%-")
    if len(probe) >= 20 and punct / max(len(probe), 1) >= 0.22:
        return True
    return False


def strip_leading_diagram_salad(text: str) -> str:
    """Cut Quality Chess diagram OCR that sits before coaching prose."""
    out = (text or "").strip()
    if not out:
        return ""
    match = _PROSE_START_RE.search(out)
    if match and match.start() > 0 and _is_diagram_salad_head(out[: match.start()]):
        return out[match.start() :].strip()
    return out


def strip_diagrams(text: str) -> str:
    out = _DIAGRAM_RE.sub(" ", text)
    out = _RANK_ONLY_RE.sub(" ", out)
    out = _PAGE_HEADER_RE.sub(" ", out)
    out = _GLYPH_SALAD_RE.sub(" ", out)
    out = normalize_prose_breaks(out)
    return strip_leading_diagram_salad(out)


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
        before = cleaned[: prose_match.start()].strip()
        after = cleaned[prose_match.start() :].strip()
        # Leading English before a later opener ("Making things easier… If 47…")
        # is prose, not a score fragment — keep it.
        if before and not _NUMBERED_MOVE_RE.search(before):
            return [], strip_diagrams(f"{before} {after}".strip())
        head = before
        prose_tail = after
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
        r"\b((?:Better was|Instead|The try|Not|"
        r"A different continuation(?:[^.!?]{0,40})?)\s+[^.]{8,220}\.)",
        prose_wo,
        re.I,
    ):
        variations.append(clean_book_note(match.group(1)))

    prose_wo = re.sub(r"\s+", " ", prose_wo).strip()
    return prose_wo, variations
