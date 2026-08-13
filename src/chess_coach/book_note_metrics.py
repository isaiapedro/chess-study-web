"""Book-note recall / Family-4 density report (library entry for CLI + scripts)."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from chess_coach.chapter import extract_move_notes

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "pdf_notes"
BOOKWALK = ROOT / "data" / "annotated" / "bookwalk"
BOOK_RE = re.compile(r"\[Book:", re.I)


def fixture_metrics() -> list[dict]:
    rows: list[dict] = []
    for anchors_path in sorted(FIXTURES.glob("*_anchors.yaml")):
        stem = anchors_path.name.replace("_anchors.yaml", "")
        excerpt = FIXTURES / f"{stem}_excerpt.txt"
        if not excerpt.is_file():
            continue
        spec = yaml.safe_load(anchors_path.read_text(encoding="utf-8")) or {}
        expect = spec.get("expect") or []
        _pre, notes = extract_move_notes(excerpt.read_text(encoding="utf-8"))
        hits = 0
        text_hits = 0
        text_need = 0
        for exp in expect:
            fm = exp["fullmove"]
            side = exp["side"]
            needle = (exp.get("san_contains") or exp.get("san") or "").lower()
            prefix = exp.get("text_prefix") or ""
            matched = [
                n
                for n in notes
                if n.fullmove == fm
                and n.side == side
                and (not needle or needle in (n.san_hint or "").lower())
            ]
            if matched:
                hits += 1
                blob = " ".join(matched[0].text.split())
                if prefix and (prefix in blob or blob.startswith(prefix)):
                    text_hits += 1
                if prefix:
                    text_need += 1
            elif prefix:
                text_need += 1
        for exp in spec.get("text_contains") or []:
            fm = exp["fullmove"]
            side = exp["side"]
            matched = [n for n in notes if n.fullmove == fm and n.side == side]
            for needle in exp.get("needles") or []:
                text_need += 1
                if matched and (
                    needle in matched[0].text
                    or needle.replace(" ", "") in matched[0].text.replace(" ", "")
                ):
                    text_hits += 1
        n_exp = max(len(expect), 1)
        rows.append(
            {
                "stem": stem,
                "expect": len(expect),
                "extracted": len(notes),
                "ply_recall": hits / n_exp,
                "text_precision": (text_hits / text_need) if text_need else 1.0,
            }
        )
    return rows


def family4_density() -> list[dict]:
    rows: list[dict] = []
    for pgn in sorted(BOOKWALK.glob("*_bookwalk.pgn")):
        text = pgn.read_text(encoding="utf-8", errors="replace")
        if not re.search(r'\[BookChapter\s+"?Family 4"?\]', text):
            continue
        book_n = len(BOOK_RE.findall(text))
        sidecar = pgn.with_name(pgn.stem + ".book_notes.yaml")
        rows.append(
            {
                "pgn": pgn.name,
                "book_tags": book_n,
                "sidecar": sidecar.is_file(),
            }
        )
    return rows


def format_report(fix: list[dict], fam: list[dict]) -> str:
    lines: list[str] = ["# Book-note metrics", ""]
    lines.append("## Fixture extract (PDF draft path)")
    lines.append("")
    lines.append("| fixture | expect | extracted | ply recall | text hit rate |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for r in fix:
        lines.append(
            f"| {r['stem']} | {r['expect']} | {r['extracted']} | "
            f"{r['ply_recall']:.0%} | {r['text_precision']:.0%} |"
        )
    if fix:
        avg_r = sum(r["ply_recall"] for r in fix) / len(fix)
        avg_t = sum(r["text_precision"] for r in fix) / len(fix)
        lines.append("")
        lines.append(
            f"Average ply recall **{avg_r:.0%}**, text hit **{avg_t:.0%}** (fixtures only)."
        )
    lines.append("")
    lines.append("## Family 4 bookwalk `[Book:]` density")
    lines.append("")
    lines.append("| game | Book tags | curated sidecar |")
    lines.append("| --- | ---: | --- |")
    for r in fam:
        lines.append(
            f"| `{r['pgn']}` | {r['book_tags']} | {'yes' if r['sidecar'] else 'no'} |"
        )
    if fam:
        zero = sum(1 for r in fam if r["book_tags"] == 0)
        lines.append("")
        lines.append(
            f"{len(fam)} Family 4 PGNs; {zero} with zero `[Book:]` tags; "
            f"{sum(1 for r in fam if r['sidecar'])} curated sidecars."
        )
    lines.append("")
    lines.append(
        "These numbers measure draft extract + current PGN density — "
        "not a 90/95 production SLA. Prefer curated sidecars."
    )
    return "\n".join(lines) + "\n"


def run_report(out: Path) -> Path:
    report = format_report(fixture_metrics(), family4_density())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    return out
