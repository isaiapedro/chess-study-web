"""Human-readable ECO labels (common codes + family fallback)."""

from __future__ import annotations

import re

from chess_coach.features import ECO_FAMILY

# Compact map — prefer opening header when it is already a real name.
ECO_NAMES: dict[str, str] = {
    "A00": "Irregular / uncommon first moves",
    "A04": "Reti Opening",
    "A10": "English Opening",
    "A13": "English Opening (Agincourt)",
    "A15": "English Opening (Anglo-Indian)",
    "A20": "English Opening (Reversed Sicilian)",
    "A40": "Queen's Pawn (unusual replies)",
    "A45": "Trompowsky / Indian systems",
    "A50": "Indian Defence (without …d5)",
    "A56": "Benoni Defence",
    "A57": "Benko / Volga Gambit",
    "A60": "Modern Benoni",
    "A80": "Dutch Defence",
    "B06": "Modern Defence",
    "B07": "Pirc Defence",
    "B10": "Caro-Kann Defence",
    "B12": "Caro-Kann (Advance)",
    "B20": "Sicilian Defence",
    "B22": "Sicilian (Alapin)",
    "B27": "Sicilian (early …g6 / Hyper-Accelerated)",
    "B30": "Sicilian (Rossolimo / …Nc6)",
    "B33": "Sicilian Sveshnikov",
    "B40": "Sicilian (…e6)",
    "B70": "Sicilian Dragon",
    "B80": "Sicilian Scheveningen",
    "B90": "Sicilian Najdorf",
    "C00": "French Defence",
    "C02": "French (Advance)",
    "C10": "French (Rubinstein / Classical)",
    "C11": "French (Classical)",
    "C15": "French (Winawer)",
    "C20": "King's Pawn Game",
    "C42": "Petroff Defence",
    "C44": "King's Pawn (Scotch / Ponziani ideas)",
    "C45": "Scotch Game",
    "C50": "Italian Game",
    "C55": "Two Knights Defence",
    "C60": "Ruy Lopez (Spanish)",
    "C65": "Ruy Lopez (Berlin)",
    "C78": "Ruy Lopez (Archangel / Open ideas)",
    "C88": "Ruy Lopez (Closed)",
    "C89": "Ruy Lopez (Marshall)",
    "D00": "Queen's Pawn Game",
    "D02": "London System / Queen's Pawn",
    "D06": "Queen's Gambit (rare defences)",
    "D10": "Slav Defence",
    "D20": "Queen's Gambit Accepted",
    "D30": "Queen's Gambit Declined",
    "D35": "Queen's Gambit Declined (Exchange)",
    "D37": "Queen's Gambit Declined (Classical)",
    "D43": "Semi-Slav Defence",
    "D45": "Semi-Slav (main lines)",
    "D47": "Semi-Slav (Meran)",
    "D70": "Grünfeld / Neo-Grünfeld ideas",
    "D80": "Grünfeld Defence",
    "D85": "Grünfeld (Exchange)",
    "D90": "Grünfeld (Russian / Fianchetto)",
    "E00": "Catalan / Queen's Indian / Indian systems",
    "E01": "Catalan Opening",
    "E04": "Catalan (Open)",
    "E06": "Catalan (Closed)",
    "E10": "Indian Defence (…e6)",
    "E12": "Queen's Indian Defence",
    "E15": "Queen's Indian (main lines)",
    "E20": "Nimzo-Indian Defence",
    "E21": "Nimzo-Indian (…c5 / Classical ideas)",
    "E32": "Nimzo-Indian (Classical)",
    "E46": "Nimzo-Indian (Rubinstein)",
    "E60": "King's Indian Defence",
    "E61": "King's Indian (early systems)",
    "E70": "King's Indian (Classical without Nf3)",
    "E90": "King's Indian (Classical)",
    "E92": "King's Indian (Gligoric / Petrosian)",
    "E94": "King's Indian (Classical main)",
    "E97": "King's Indian (Bayonet / Classical)",
}

_ECO_RE = re.compile(r"^[A-E]\d{2}$", re.I)


def normalize_eco(eco: str | None) -> str:
    code = (eco or "").strip().upper()
    return code if _ECO_RE.match(code) else ""


def eco_name(eco: str | None) -> str:
    code = normalize_eco(eco)
    if not code:
        return ""
    if code in ECO_NAMES:
        return ECO_NAMES[code]
    # nearest lower known code in same letter (E03 → E01 family feel)
    letter = code[0]
    num = int(code[1:])
    for n in range(num, -1, -1):
        key = f"{letter}{n:02d}"
        if key in ECO_NAMES:
            return ECO_NAMES[key]
    return ECO_FAMILY.get(letter, "opening system")


def format_eco_phrase(eco: str | None, opening: str | None = None) -> str:
    """
    Plain-language opening label.

    Example: ``Catalan Opening (ECO E01 — Indian defences)``
    """
    code = normalize_eco(eco)
    opening = (opening or "").strip()
    if opening and not _ECO_RE.match(opening):
        name = opening
    else:
        name = eco_name(code) if code else ""
    if not name and not code:
        return ""
    family = ECO_FAMILY.get(code[:1], "") if code else ""
    if family:
        family = family[:1].upper() + family[1:]
    if name and code:
        if family:
            return f"{name} (ECO {code} — {family})"
        return f"{name} (ECO {code})"
    if name:
        return name
    if family:
        return f"ECO {code} ({family})"
    return f"ECO {code}"
