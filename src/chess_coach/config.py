from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / "configs" / "default.yaml"


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or DEFAULT_CONFIG
    with config_path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    rag = data.setdefault("rag", {})
    persist = Path(rag.get("persist_dir", "data/chroma"))
    if not persist.is_absolute():
        rag["persist_dir"] = str((ROOT / persist).resolve())
    masters = data.setdefault("masters", {})
    for key in ("pgn_dir", "index_path"):
        value = masters.get(key)
        if value and not Path(value).is_absolute():
            masters[key] = str((ROOT / value).resolve())
    sf = Path(data.get("stockfish_path", "stockfish"))
    if not sf.is_absolute():
        candidate = ROOT / sf
        if candidate.exists():
            data["stockfish_path"] = str(candidate.resolve())
    ont = data.setdefault("ontology", {})
    ont_dir = Path(ont.get("dir", "data/ontology/patterns"))
    if not ont_dir.is_absolute():
        ont["dir"] = str((ROOT / ont_dir).resolve())
    return data


def resolve_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (ROOT / path).resolve()
