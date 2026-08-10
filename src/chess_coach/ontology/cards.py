from __future__ import annotations

from chess_coach.ontology.load import Pattern, expand_related, load_ontology


def format_pattern_cards(
    pattern_ids: list[str] | tuple[str, ...],
    *,
    hops: int = 1,
    ontology_dir: str | None = None,
    limit: int = 4,
) -> str:
    """Compact rule cards for Ollama / fallback notes."""
    catalog = load_ontology(ontology_dir)
    ordered = expand_related(list(pattern_ids), hops=hops, ontology_dir=ontology_dir, limit=limit)
    blocks: list[str] = []
    for pid in ordered:
        pattern = catalog.get(pid)
        if not pattern:
            continue
        rules = " ".join(pattern.rules_of_thumb[:2])
        plans = " ".join(pattern.plans[:2])
        line = f"- {pattern.id} ({pattern.label})"
        if rules:
            line += f": {rules}"
        if plans:
            line += f" Plans: {plans}"
        if pattern.exemplars:
            line += " Exemplars: " + "; ".join(pattern.exemplars[:2])
        blocks.append(line)
    return "\n".join(blocks)


def format_exemplars(
    pattern_ids: list[str] | tuple[str, ...],
    *,
    ontology_dir: str | None = None,
    limit: int = 4,
) -> str:
    """Deduped exemplar game lines for prompts / notes."""
    catalog = load_ontology(ontology_dir)
    seen: list[str] = []
    for pid in expand_related(list(pattern_ids), hops=0, ontology_dir=ontology_dir, limit=8):
        pattern = catalog.get(pid)
        if not pattern:
            continue
        for ex in pattern.exemplars:
            if ex and ex not in seen:
                seen.append(ex)
            if len(seen) >= limit:
                return "\n".join(f"- {s}" for s in seen)
    return "\n".join(f"- {s}" for s in seen)


def pattern_query_text(
    pattern_ids: list[str] | tuple[str, ...],
    *,
    ontology_dir: str | None = None,
    limit: int = 4,
) -> str:
    """Embedding query seeded by ontology keywords + rules (not vague 'opening theory')."""
    catalog = load_ontology(ontology_dir)
    ordered = expand_related(list(pattern_ids), hops=1, ontology_dir=ontology_dir, limit=limit)
    parts: list[str] = []
    for pid in ordered:
        pattern = catalog.get(pid)
        if not pattern:
            continue
        parts.append(pattern.label)
        parts.extend(list(pattern.keywords[:4]))
        if pattern.rules_of_thumb:
            parts.append(pattern.rules_of_thumb[0])
    return ". ".join(parts)


def pattern_keyword_set(
    pattern_ids: list[str] | tuple[str, ...],
    *,
    ontology_dir: str | None = None,
) -> set[str]:
    catalog = load_ontology(ontology_dir)
    keys: set[str] = set()
    for pid in expand_related(list(pattern_ids), hops=1, ontology_dir=ontology_dir, limit=8):
        pattern = catalog.get(pid)
        if not pattern:
            continue
        for k in pattern.keywords:
            keys.add(k.lower())
        for a in pattern.aliases:
            keys.add(a.lower())
        keys.add(pattern.label.lower())
    return keys


def patterns_for_prompt(pattern_ids: list[str]) -> list[Pattern]:
    catalog = load_ontology()
    return [catalog[p] for p in pattern_ids if p in catalog]
