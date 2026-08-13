#!/usr/bin/env python3
"""CLI wrapper — prefer ``chess-coach book-note-metrics``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from chess_coach.book_note_metrics import run_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "viewer_out" / "book_note_metrics.md",
    )
    args = parser.parse_args(argv)
    path = run_report(args.out)
    print(path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
