from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from chess_coach.config import ROOT

DEFAULT_ONTOLOGY_DIR = ROOT / "data" / "ontology" / "patterns"


@dataclass(frozen=True)
class Pattern:
    id: str
    label: str
    phase: str = "any"
    family: str = ""
    aliases: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    rules_of_thumb: tuple[str, ...] = ()
    plans: tuple[str, ...] = ()
    related: tuple[str, ...] = ()
    detect: str = ""
    eco_prefixes: tuple[str, ...] = ()
    opening_tokens: tuple[str, ...] = ()
    exemplars: tuple[str, ...] = ()


def _as_tuple(value: Any) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(v) for v in value)


def _parse_pattern(data: dict[str, Any]) -> Pattern | None:
    pid = str(data.get("id") or "").strip()
    if not pid:
        return None
    return Pattern(
        id=pid,
        label=str(data.get("label") or pid),
        phase=str(data.get("phase") or "any"),
        family=str(data.get("family") or ""),
        aliases=_as_tuple(data.get("aliases")),
        keywords=_as_tuple(data.get("keywords")),
        rules_of_thumb=_as_tuple(data.get("rules_of_thumb")),
        plans=_as_tuple(data.get("plans")),
        related=_as_tuple(data.get("related")),
        detect=str(data.get("detect") or ""),
        eco_prefixes=_as_tuple(data.get("eco_prefixes")),
        opening_tokens=_as_tuple(data.get("opening_tokens")),
        exemplars=_as_tuple(data.get("exemplars")),
    )


@lru_cache(maxsize=4)
def load_ontology(ontology_dir: str | None = None) -> dict[str, Pattern]:
    root = Path(ontology_dir) if ontology_dir else DEFAULT_ONTOLOGY_DIR
    if not root.is_absolute():
        root = ROOT / root
    patterns: dict[str, Pattern] = {}
    if not root.exists():
        return patterns
    for path in sorted(root.glob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            continue
        pattern = _parse_pattern(data)
        if pattern:
            patterns[pattern.id] = pattern
    return patterns


def get_pattern(pattern_id: str, ontology_dir: str | None = None) -> Pattern | None:
    return load_ontology(ontology_dir).get(pattern_id)


def expand_related(
    pattern_ids: list[str] | tuple[str, ...],
    *,
    hops: int = 1,
    ontology_dir: str | None = None,
    limit: int = 8,
) -> list[str]:
    catalog = load_ontology(ontology_dir)
    seen: list[str] = []
    frontier = list(pattern_ids)
    for _ in range(max(0, hops) + 1):
        nxt: list[str] = []
        for pid in frontier:
            if pid in seen or pid not in catalog:
                continue
            seen.append(pid)
            if len(seen) >= limit:
                return seen
            for rel in catalog[pid].related:
                if rel not in seen:
                    nxt.append(rel)
        frontier = nxt
    return seen
