from __future__ import annotations

import re

# OCR / common book mangling → Chessgames-friendly surnames
OCR_NAME_FIXES = {
    "corro": "Corzo",
    "corro,": "Corzo",
    "durarbeyli": "Durarbayli",
    "durarbayli": "Durarbayli",
    "lasker": "Lasker",
    "aljechin": "Alekhine",
    "alechine": "Alekhine",
    "alechin": "Alekhine",
    "nimzowitch": "Nimzowitsch",
    "nimzovich": "Nimzowitsch",
    "botwinnik": "Botvinnik",
    "botvinnik": "Botvinnik",
    "reshewsky": "Reshevsky",
    "reshwsky": "Reshevsky",
    "tartakover": "Tartakower",
    "tartakower": "Tartakower",
    "janowsky": "Janowski",
    "janowski": "Janowski",
    "teichman": "Teichmann",
    "kreyrnbourg": "Kreymbourg",
    "kupchik": "Kupchik",
    "capabtanca": "Capablanca",
    "capablanka": "Capablanca",
    "wojwzek": "Wojtaszek",
    "wojtaszek": "Wojtaszek",
    "swiera": "Swiercz",
    "swiercz": "Swiercz",
    "peraon": "Persson",
    "persson": "Persson",
    "marcco": "Mareco",
    "mareco": "Mareco",
    "efunenko": "Efimenko",
    "efimenko": "Efimenko",
    "krintian": "Krisztian",
    "krisztian": "Krisztian",
    "volke": "Volke",
}

# Multi-token OCR scraps (applied before tokenization)
OCR_PHRASE_FIXES = (
    (r"(?i)\bhillarp\s+peraon\b", "Hillarp Persson"),
    (r"(?i)\bkarsten\s+vol(?:\s+vol)*\s*kc\b", "Karsten Volke"),
    (r"(?i)\bvol(?:\s+vol)*\s*kc\b", "Volke"),
    (r"(?i)\bvol\s+volke\b", "Volke"),
    (r"(?i)\btiger\s+hillarp(?!\s+persson)\b", "Tiger Hillarp Persson"),
)

NOISE_TOKENS = {
    "white",
    "black",
    "jr",
    "sr",
    "dr",
    "gm",
    "im",
    "fm",
    "blindfold",
    "and",
    "allies",
    "consultation",
    "now",
    "then",
    "was",
    "later",
    "see",
}


def normalize_player_name(raw: str) -> str:
    text = re.sub(r"\s+", " ", (raw or "").strip())
    text = text.replace("’", "'")
    # drop parenthetical junk
    text = re.sub(r"\([^)]*\)", " ", text)
    for pat, repl in OCR_PHRASE_FIXES:
        text = re.sub(pat, repl, text)
    text = re.sub(r"\s+", " ", text).strip(" ,.-")
    # strip leading prose crumbs: "now Brkic"
    text = re.sub(r"^(now|then|was|see|later)\s+", "", text, flags=re.I)
    lowered = text.lower().rstrip(",")
    if lowered in OCR_NAME_FIXES:
        return OCR_NAME_FIXES[lowered]
    parts = []
    for part in re.split(r"[\s.]+", text):
        if not part:
            continue
        key = part.lower().rstrip(",")
        if key in NOISE_TOKENS:
            continue
        if key in OCR_NAME_FIXES:
            parts.append(OCR_NAME_FIXES[key])
        else:
            parts.append(part)
    if not parts:
        return text
    # single-token OCR fix on last surname
    last = parts[-1].lower()
    if last in OCR_NAME_FIXES:
        parts[-1] = OCR_NAME_FIXES[last]
    # collapse OCR double "Vol Volke"
    cleaned: list[str] = []
    for part in parts:
        if (
            cleaned
            and cleaned[-1].lower() == "vol"
            and part.lower() == "volke"
        ):
            cleaned[-1] = "Volke"
            continue
        cleaned.append(part)
    return " ".join(cleaned)


def search_name_variants(raw: str) -> list[str]:
    """Ordered variants to try against Chessgames search."""
    full = normalize_player_name(raw)
    variants: list[str] = []
    if full:
        variants.append(full)
    # surname only
    parts = full.split()
    if parts:
        surname = parts[-1]
        if surname not in variants:
            variants.append(surname)
    # drop initials-only middle forms: "J. R. Capablanca" already surname-handled
    # OCR letter swaps on surname
    if parts:
        surname = parts[-1]
        swaps = {
            "Corro": "Corzo",
            "Corzo": "Corzo",
            "Reshwsky": "Reshevsky",
            "Tartakover": "Tartakower",
            "Wojwzek": "Wojtaszek",
            "Swiera": "Swiercz",
            "Peraon": "Persson",
            "Marcco": "Mareco",
            "Efunenko": "Efimenko",
            "Krintian": "Krisztian",
        }
        for bad, good in swaps.items():
            if surname.lower() == bad.lower() and good not in variants:
                variants.append(good)
    # unique preserve order
    seen: set[str] = set()
    out: list[str] = []
    for item in variants:
        key = item.lower()
        if key in seen or not item:
            continue
        seen.add(key)
        out.append(item)
    return out
