"""Rule A/B unit tests for chess_text_grammar (PDF-wide token heads)."""

from __future__ import annotations

from chess_coach.chess_text_grammar import MOVE_HEAD_RE, normalize_ellipsis_forms, move_head_matches
from chess_coach.ocr_chess import ocr_clean_chess


def test_rule_a_pawn_advance_not_move_head():
    text = "a4-a5. 26...J.5c7"
    heads = list(MOVE_HEAD_RE.finditer(text))
    assert not any(m.group("num") == "5" for m in heads)
    cleaned = ocr_clean_chess(text)
    assert "R5c7" in cleaned
    assert "26..." in cleaned
    heads2 = move_head_matches(cleaned)
    assert len(heads2) == 1
    assert heads2[0].group("num") == "26"


def test_rule_a_exd5_sentence_dot():
    text = "after exd5. Black is fine."
    assert not any(m.group("num") == "5" for m in MOVE_HEAD_RE.finditer(text))


def test_rule_a_real_move_still_matches():
    text = "24.Bd3 Something. 24...Qf8 There is nothing."
    nums = [m.group("num") for m in MOVE_HEAD_RE.finditer(text)]
    assert "24" in nums


def test_rule_b_bullet_ellipsis_to_black():
    raw = "2s .• .1'.g5 \nIf 28 ... f4?!"
    cleaned = ocr_clean_chess(raw)
    assert "28...Bg5" in cleaned.replace(" ", "") or "28... Bg5" in cleaned


def test_normalize_ellipsis_forms_order():
    out = normalize_ellipsis_forms("24..Bd3 28 .• .Bg5")
    assert "24.Bd3" in out.replace(" ", "") or "24. Bd3" in out or out.startswith("24.")
    assert "..." in normalize_ellipsis_forms("29 ••• Nf6") or "29..." in normalize_ellipsis_forms(
        "29 ••• Nf6"
    )
