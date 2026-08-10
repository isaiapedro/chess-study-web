from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from chess_coach.analyze import CriticalMoment
from chess_coach.comment import Commentary


def _eval_str(cp: int | None, mate: int | None) -> str:
    if mate is not None:
        return f"M{mate:+d}"
    if cp is None:
        return "n/a"
    return f"{cp / 100:+.2f}"


def render_markdown(
    game_headers: dict[str, str],
    moments: list[CriticalMoment],
    commentaries: list[Commentary],
) -> str:
    white = game_headers.get("White", "?")
    black = game_headers.get("Black", "?")
    result = game_headers.get("Result", "*")
    lines = [
        f"# Chess Coach Report: {white} vs {black}",
        "",
        f"Result: {result}",
        f"ECO: {game_headers.get('ECO', 'n/a')}",
        f"Opening: {game_headers.get('Opening', 'n/a')}",
        "",
        "## Critical Moments",
        "",
    ]
    if not moments:
        lines.append("No critical moments above the configured threshold.")
        return "\n".join(lines) + "\n"

    lines.append("| Ply | Side | Played | Best | Loss (cp) | Eval before | Eval after |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for moment in moments:
        lines.append(
            "| {ply} | {side} | {played} | {best} | {loss} | {before} | {after} |".format(
                ply=moment.ply,
                side=moment.side,
                played=moment.played_san,
                best=moment.best_san or "n/a",
                loss=moment.delta_cp,
                before=_eval_str(moment.eval_before_cp, moment.mate_before),
                after=_eval_str(moment.eval_after_cp, moment.mate_after),
            )
        )
    lines.append("")

    for moment, commentary in zip(moments, commentaries):
        move_label = f"{moment.fullmove}{'.' if moment.side == 'white' else '...'}"
        lines.extend(
            [
                f"### {move_label} {moment.played_san}",
                "",
                f"- FEN: `{moment.fen_before}`",
                f"- Engine best: `{moment.best_san or 'n/a'}`",
                f"- PV: `{' '.join(moment.pv_san)}`",
                f"- Themes: {', '.join(moment.features.themes) or 'none'}",
                "",
                commentary.text,
                "",
            ]
        )
        if commentary.citations:
            lines.append("Sources: " + ", ".join(sorted(set(commentary.citations))))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(
    out_path: Path,
    game_headers: dict[str, str],
    moments: list[CriticalMoment],
    commentaries: list[Commentary],
    *,
    also_json: bool = False,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    markdown = render_markdown(game_headers, moments, commentaries)
    out_path.write_text(markdown, encoding="utf-8")
    if also_json:
        payload: dict[str, Any] = {
            "headers": game_headers,
            "moments": [m.to_dict() for m in moments],
            "commentaries": [
                {
                    "text": c.text,
                    "citations": c.citations,
                    "engine_only": c.engine_only,
                    "warnings": c.warnings,
                }
                for c in commentaries
            ],
        }
        out_path.with_suffix(".json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
