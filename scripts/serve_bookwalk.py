#!/usr/bin/env python3
"""Serve bookwalk HTML + local Lichess study push API (uses LICHESS_TOKEN)."""
from __future__ import annotations

import argparse
import functools
import json
import socket
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class BookwalkHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **getattr(SimpleHTTPRequestHandler, "extensions_map", {}),
        ".wasm": "application/wasm",
        ".js": "text/javascript",
        ".mjs": "text/javascript",
    }

    def _send_json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        if urlparse(self.path).path == "/api/lichess-study":
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/api/lichess-study":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._send_json(400, {"ok": False, "error": "invalid JSON"})
            return
        pgn = (data.get("pgn") or "").strip()
        if not pgn or "[" not in pgn:
            self._send_json(400, {"ok": False, "error": "missing pgn"})
            return
        name = (data.get("name") or "").strip() or None
        study_id = (data.get("studyId") or data.get("study_id") or "").strip() or None
        visibility = (data.get("visibility") or "unlisted").strip()
        orientation = data.get("orientation")
        if orientation not in ("white", "black", None):
            orientation = None
        try:
            from chess_coach.lichess_study import (
                LichessStudyClient,
                chapter_name_from_pgn,
                resolve_token,
            )

            token = resolve_token(data.get("token"))
            hint = name or chapter_name_from_pgn(pgn)
            with LichessStudyClient(token) as client:
                sid = study_id
                created = False
                if not sid:
                    sid = client.create_study(hint[:100], visibility=visibility)
                    created = True
                chapters, err = client.import_pgn(
                    sid,
                    pgn,
                    name=hint,
                    orientation=orientation,
                    initial=created,
                    is_default_name=False,
                )
            payload = {
                "ok": not bool(err),
                "studyId": sid,
                "url": f"https://lichess.org/study/{sid}",
                "chapters": [{"id": c.id, "name": c.name} for c in chapters],
                "error": err,
            }
            self._send_json(200 if not err else 502, payload)
        except Exception as exc:
            self._send_json(500, {"ok": False, "error": str(exc)})

    def end_headers(self) -> None:
        if urlparse(self.path).path == "/api/lichess-study":
            self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


def lan_ipv4() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                return ip
    except OSError:
        pass
    return "127.0.0.1"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument(
        "--dir",
        type=Path,
        default=ROOT / "data" / "viewer_out" / "bookwalk",
    )
    args = parser.parse_args()
    root = args.dir.resolve()
    if not root.is_dir():
        raise SystemExit(f"Missing directory: {root}")
    handler = functools.partial(BookwalkHandler, directory=str(root))
    httpd = ThreadingHTTPServer((args.bind, args.port), handler)
    host = lan_ipv4()
    print(f"Serving {root}")
    print(f"Open http://{host}:{args.port}/")
    chapter = sorted(root.glob("*_chapter_book.html"), key=lambda p: p.stat().st_size, reverse=True)
    if chapter:
        print(f"Chapter: http://{host}:{args.port}/{chapter[0].name}")
    print("POST /api/lichess-study  (needs LICHESS_TOKEN in env or .env)")
    print("WASM MIME=application/wasm")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
