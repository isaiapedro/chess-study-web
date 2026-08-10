#!/usr/bin/env python3
"""Serve bookwalk HTML with correct WASM MIME (helps mobile Safari)."""
from __future__ import annotations

import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class BookwalkHandler(SimpleHTTPRequestHandler):
    extensions_map = {
        **getattr(SimpleHTTPRequestHandler, "extensions_map", {}),
        ".wasm": "application/wasm",
        ".js": "text/javascript",
        ".mjs": "text/javascript",
    }


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
    print(f"Serving {root}")
    print(f"Open http://192.168.1.19:{args.port}/ (or this machine's LAN IP)")
    print("WASM MIME=application/wasm")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
