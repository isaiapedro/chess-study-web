from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.I)
_GENERIC_RE = re.compile(
    r"compare forcing replies|keep pieces active|look at candidates|"
    r"weigh the engine alternative|hold the same standard",
    re.I,
)
CHECKPOINT_KINDS = {
    "opening_name",
    "opening_aggregate",
    "middlegame_aggregate",
    "endgame_advantage",
    "decisive_pawn_break",
}
TACTICAL_KEY = {
    "trapped_piece": "motif.trapped_piece",
    "hung_mate": "motif.mate_threat",
    "missed_mate": "motif.mate_threat",
    "gave_piece": "motif.hanging_piece",
    "missed_capture": "motif.hanging_piece",
    "missed_tactic": "motif.fork",
}

SYSTEM_PROMPT = """
You are a sharp, concise grandmaster chess coach.
Use ONLY the provided engine facts. Do not invent pieces, squares, or lines.

TASK:
- mistake: explain why the played move is wrong and what the engine move does.
- praise: explain why the played move is strong. Never call it a mistake.
- checkpoint: snapshot the plan from the facts. Do not invent a blunder.

STRICT CONSTRAINTS:
1. Maximum 2 sentences.
2. NEVER use generic advice like "compare forcing replies", "keep pieces active", or "look at candidates".
3. State the exact tactical consequence or piece interaction directly (name the piece, square, or line).
4. If a tactical_head is provided, use its concrete calculation.
5. Write concrete SAN and piece names, not placeholders.
""".strip()


def build_llm_moment_payload(moment_data: dict[str, Any]) -> dict[str, Any]:
    inputs = moment_data.get("inputs") or {}
    if not isinstance(inputs, dict):
        inputs = {}
    fact = moment_data.get("tacticalFact") or {}
    if not isinstance(fact, dict):
        fact = {}
    tactical_head = (
        inputs.get("tactical_head")
        or fact.get("head")
        or moment_data.get("tactical_head")
    )
    tactical_kind = (
        inputs.get("tactical_kind")
        or fact.get("kind")
        or moment_data.get("tactical_kind")
    )
    self_inflicted = inputs.get("tactical_self_inflicted")
    if self_inflicted is None:
        self_inflicted = fact.get("selfInflicted")
    payload = {
        "ply": moment_data.get("ply"),
        "played_move": moment_data.get("playedSan") or moment_data.get("played_san"),
        "best_move": moment_data.get("bestSan") or moment_data.get("best_san"),
        "mark": moment_data.get("severity") or moment_data.get("mark"),
        "drop_cp": moment_data.get("dropCp") or moment_data.get("drop_cp") or 0,
        "tactical_head": tactical_head,
        "tactical_kind": tactical_kind,
        "self_inflicted": bool(self_inflicted),
        "why_better": inputs.get("why_better") or moment_data.get("why_better"),
        "played_line": inputs.get("played_line") or moment_data.get("played_line"),
        "engine_line": inputs.get("engine_line") or moment_data.get("engine_line"),
        "played_impact": inputs.get("played_impact") or moment_data.get("played_impact"),
        "technical_rule": inputs.get("technical_rule") or moment_data.get("technical_rule"),
        "key_id": inputs.get("key_id") or moment_data.get("key_id"),
        "structural_kind": moment_data.get("structuralKind")
        or inputs.get("structural_kind"),
        "praise_mark": inputs.get("praise_mark"),
        "piece": fact.get("pieceLabel") or inputs.get("tactical_piece"),
        "square": fact.get("trapSquare") or inputs.get("tactical_square"),
    }
    kind = (event_kinds_for_payload(payload) or ["positional_error"])[0]
    payload["event_kind"] = kind
    if kind == "praise":
        payload["task"] = "praise"
    elif kind == "fixed_checkpoint":
        payload["task"] = "checkpoint"
    else:
        payload["task"] = "mistake"
    return payload


def iter_moments(data: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    coach = data.get("coach") or {}
    by_ply = coach.get("momentsByPly") or {}
    if isinstance(by_ply, dict):
        for ply, moment in by_ply.items():
            if not isinstance(moment, dict):
                continue
            row = dict(moment)
            row.setdefault("ply", int(ply) if str(ply).isdigit() else ply)
            out.append(row)
    for row in data.get("moments") or []:
        if isinstance(row, dict):
            out.append(row)
    return out


def payload_worth_comment(payload: dict[str, Any]) -> bool:
    mark = str(payload.get("mark") or "")
    drop = int(payload.get("drop_cp") or 0)
    praise = str(payload.get("praise_mark") or mark)
    if mark in {"blunder", "mistake", "missed"}:
        return True
    if praise in {"brilliant", "excellent"}:
        return True
    if payload.get("tactical_kind") or payload.get("tactical_head"):
        return True
    if payload.get("structural_kind") in CHECKPOINT_KINDS:
        return True
    return drop >= 100


def event_kinds_for_payload(payload: dict[str, Any]) -> list[str]:
    mark = str(payload.get("mark") or "")
    drop = int(payload.get("drop_cp") or 0)
    praise = str(payload.get("praise_mark") or mark)
    mute = mark in {"inaccuracy", "important"}
    if not mute and (
        payload.get("tactical_kind") or mark in {"blunder", "missed"} or drop >= 200
    ):
        return ["tactical_blunder"]
    if not mute and (mark == "mistake" or drop >= 100):
        return ["positional_error"]
    structural = str(payload.get("structural_kind") or "")
    if structural in CHECKPOINT_KINDS:
        return ["fixed_checkpoint"]
    if praise == "brilliant" or mark == "brilliant":
        return ["praise"]
    if praise == "excellent" or mark == "excellent":
        return ["praise"]
    return ["positional_error"]


def key_id_for_payload(payload: dict[str, Any]) -> str:
    existing = str(payload.get("key_id") or "").strip()
    if existing:
        return existing
    kind = str(payload.get("tactical_kind") or "")
    if kind in TACTICAL_KEY:
        return TACTICAL_KEY[kind]
    structural = str(payload.get("structural_kind") or "")
    if structural in CHECKPOINT_KINDS:
        return f"checkpoint.{structural}"
    praise = str(payload.get("praise_mark") or payload.get("mark") or "")
    if praise == "brilliant":
        return "praise.brilliant"
    if praise == "excellent":
        return "praise.great_find"
    return "methodology.comparison_and_elimination"


def guards_for_payload(payload: dict[str, Any], *, game_specific: bool) -> dict[str, Any]:
    guards: dict[str, Any] = {}
    kind = payload.get("tactical_kind")
    if kind:
        guards["tactical_kind"] = str(kind)
        guards["self_inflicted"] = bool(payload.get("self_inflicted"))
    structural = payload.get("structural_kind")
    if structural in CHECKPOINT_KINDS:
        guards["structural_kind"] = structural
    praise = str(payload.get("praise_mark") or payload.get("mark") or "")
    if praise == "brilliant":
        guards["praise_kind"] = "brilliant"
    elif praise == "excellent":
        guards["praise_kind"] = "great_find"
    if game_specific:
        played = payload.get("played_move")
        ply = payload.get("ply")
        if played:
            guards["played_san"] = str(played)
        if ply is not None and str(ply).isdigit():
            guards["ply"] = int(ply)
    return guards


def stitch_fallback(payload: dict[str, Any]) -> str:
    played = payload.get("played_move") or "{playedSan}"
    best = payload.get("best_move") or "{bestSan}"
    head = str(payload.get("tactical_head") or "").strip().rstrip(".")
    why = str(payload.get("why_better") or "").strip().rstrip(".")
    impact = str(payload.get("played_impact") or "").strip().rstrip(".")
    task = str(payload.get("task") or "")
    parts: list[str] = []
    if task == "praise":
        parts.append(f"{played} is the right idea.")
        if best and best != played:
            parts.append(f"Engine agrees with {best}.")
        return _clip_sentences(" ".join(parts))
    if head:
        parts.append(f"{played} — {head}.")
    elif impact:
        parts.append(f"{played} {impact[0].lower() + impact[1:]}.")
    elif why:
        parts.append(f"{played} conceded the better idea ({why}).")
    else:
        parts.append(f"{played} dropped the evaluation.")
    if best:
        parts.append(f"Best was {best}.")
    return _clip_sentences(" ".join(parts))


def _clip_sentences(text: str, limit: int = 2) -> str:
    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    if not raw:
        return ""
    bits = re.split(r"(?<=[.!?])\s+", raw)
    keep = [b.strip() for b in bits if b.strip()][:limit]
    out = " ".join(keep).strip()
    if out and out[-1] not in ".!?":
        out += "."
    return out


def comment_is_concrete(text: str) -> bool:
    t = str(text or "").strip()
    if len(t) < 24:
        return False
    if _GENERIC_RE.search(t):
        return False
    return True


def _llm_model_name(config: dict[str, Any]) -> str:
    return str(
        config.get("coach_comment_model")
        or config.get("ideas_chat_model")
        or config.get("chat_model")
        or "llama3.2:latest"
    )


def _user_prompt(payload: dict[str, Any]) -> str:
    return (
        f"Task: {payload.get('task') or 'mistake'}\n"
        f"Event: {payload.get('event_kind') or ''}\n"
        f"Played Move: {payload.get('played_move')}\n"
        f"Engine Best Move: {payload.get('best_move')}\n"
        f"Evaluation Drop: {payload.get('drop_cp')} centipawns\n"
        f"Tactical Fact: {payload.get('tactical_head')}\n"
        f"Engine Reason: {payload.get('why_better')}\n"
        f"Played Impact: {payload.get('played_impact')}\n"
        f"Strategic Rule: {payload.get('technical_rule')}\n"
        f"Engine Line: {payload.get('engine_line')}\n"
        f"Played Line: {payload.get('played_line')}\n"
        f"Piece: {payload.get('piece')} Square: {payload.get('square')}\n\n"
        "Write the coaching comment:"
    )


def generate_coach_comment(
    payload: dict[str, Any],
    config: dict[str, Any],
    *,
    use_llm: bool = True,
    client: httpx.Client | None = None,
) -> str:
    if not use_llm:
        return stitch_fallback(payload)
    host = str(config.get("ollama_host") or "http://localhost:11434").rstrip("/")
    model = _llm_model_name(config)
    own_client = client is None
    http = client or httpx.Client(timeout=90.0)
    try:
        response = http.post(
            f"{host}/api/chat",
            json={
                "model": model,
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0.2,
                    "num_predict": 180,
                    "num_ctx": 2048,
                },
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _user_prompt(payload)},
                ],
            },
        )
        response.raise_for_status()
        message = response.json().get("message") or {}
        content = str(message.get("content") or "").strip()
        content = _THINK_RE.sub("", content).strip()
        content = _clip_sentences(content)
        if comment_is_concrete(content):
            return content
    except Exception as exc:
        print(f"    llm comment failed (ply={payload.get('ply')}): {exc}", flush=True)
    finally:
        if own_client:
            http.close()
    return stitch_fallback(payload)


def generate_coach_comments(
    payloads: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    use_llm: bool = True,
) -> list[str]:
    if not payloads:
        return []
    if not use_llm:
        return [stitch_fallback(p) for p in payloads]
    with httpx.Client(timeout=90.0) as client:
        return [
            generate_coach_comment(p, config, use_llm=True, client=client)
            for p in payloads
        ]


def generalize_comment(text: str, payload: dict[str, Any]) -> str:
    out = str(text or "")
    played = str(payload.get("played_move") or "")
    best = str(payload.get("best_move") or "")
    piece = str(payload.get("piece") or "")
    square = str(payload.get("square") or "")
    if played:
        out = out.replace(played, "{playedSan}")
    if best and best != played:
        out = out.replace(best, "{bestSan}")
    if piece:
        out = re.sub(rf"\b{re.escape(piece)}\b", "{piece}", out, count=1, flags=re.I)
    if square:
        out = out.replace(square, "{square}")
    return out


def note_entry(
    payload: dict[str, Any],
    text: str,
    *,
    game_specific: bool,
    suffix: str,
) -> dict[str, Any]:
    key_id = key_id_for_payload(payload)
    ply = payload.get("ply")
    nid = f"generated:{key_id}#{suffix}"
    if ply is not None:
        nid = f"generated:{key_id}#ply_{ply}_{suffix}"
    return {
        "id": nid,
        "keyId": key_id,
        "eventKinds": event_kinds_for_payload(payload),
        "guards": guards_for_payload(payload, game_specific=game_specific),
        "text": text,
        "template": {"attention": text},
        "source": "offline-llm",
    }


def generate_offline_comment_notes(
    data: dict[str, Any],
    config: dict[str, Any],
    *,
    use_llm: bool = True,
    game_specific: bool = True,
) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    seen: set[str] = set()
    cluster_seen: set[str] = set()
    for moment in iter_moments(data):
        payload = build_llm_moment_payload(moment)
        if not payload_worth_comment(payload):
            continue
        cluster_key = (
            str(
                payload.get("tactical_kind")
                or payload.get("structural_kind")
                or payload.get("praise_mark")
                or "x"
            )
            + "|"
            + str(bool(payload.get("self_inflicted")))
        )
        if not game_specific and cluster_key in cluster_seen:
            continue
        text = generate_coach_comment(payload, config, use_llm=use_llm)
        if not text:
            continue
        if game_specific:
            specific = note_entry(payload, text, game_specific=True, suffix="exact")
            if specific["id"] not in seen:
                notes.append(specific)
                seen.add(specific["id"])
        if cluster_key in cluster_seen:
            continue
        cluster_seen.add(cluster_key)
        generalized = generalize_comment(text, payload)
        reusable = note_entry(
            payload,
            generalized,
            game_specific=False,
            suffix="pattern",
        )
        reusable["id"] = f"generated:{reusable['keyId']}#{cluster_key.replace('|', '-')}"
        if reusable["id"] not in seen:
            notes.append(reusable)
            seen.add(reusable["id"])
    return notes


def merge_notes_schema(
    schema: dict[str, Any],
    generated: list[dict[str, Any]],
) -> dict[str, Any]:
    existing = [
        n
        for n in (schema.get("notes") or [])
        if isinstance(n, dict) and not str(n.get("id") or "").startswith("generated:")
    ]
    return {
        "version": int(schema.get("version") or 1) + (1 if generated else 0),
        "notes": existing + generated,
    }


def load_metrics_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_notes_schema(schema: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
