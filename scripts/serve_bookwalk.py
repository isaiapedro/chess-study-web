#!/usr/bin/env python3
"""Serve bookwalk HTML with correct WASM MIME (helps mobile Safari)."""
from __future__ import annotations

import argparse
import functools
import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class BookwalkHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **getattr(SimpleHTTPRequestHandler, "extensions_map", {}),
        ".wasm": "application/wasm",
        ".js": "text/javascript",
        ".mjs": "text/javascript",
    }


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
        default=Path(__file__).resolve().parents[2] / "data" / "viewer_out" / "bookwalk",
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
    print("WASM MIME=application/wasm")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
