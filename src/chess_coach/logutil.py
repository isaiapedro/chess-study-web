from __future__ import annotations

import sys
import time
from typing import Any


def log(msg: str, *args: Any) -> None:
    if args:
        msg = msg % args
    stamp = time.strftime("%H:%M:%S")
    print(f"[{stamp}] {msg}", file=sys.stderr, flush=True)
