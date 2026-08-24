"""Parse ingredient lines like "1 1/2 cups plain flour, sifted".

Used by the recipe form (one ingredient per line) and by the offline recipe
importer. The parser is deliberately forgiving: anything it can't read as a
quantity or unit ends up in the name, and nothing is ever dropped.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import units

UNICODE_FRACTIONS = {
    "½": 0.5,
    "⅓": 1 / 3,
    "⅔": 2 / 3,
    "¼": 0.25,
    "¾": 0.75,
    "⅕": 0.2,
    "⅛": 0.125,
    "⅜": 0.375,
    "⅝": 0.625,
    "⅞": 0.875,
}

_FRACTION_CHARS = "".join(UNICODE_FRACTIONS)
_NUMBER = rf"(?:\d+(?:[.,]\d+)?(?:\s*[{_FRACTION_CHARS}])?|[{_FRACTION_CHARS}])"
_QTY_RE = re.compile(
    rf"^(?P<qty>\d+\s+\d+/\d+|\d+/\d+|{_NUMBER})"
    rf"(?:\s*(?:-|–|to)\s*(?P<qty2>\d+/\d+|{_NUMBER}))?"
)
_BULLET_RE = re.compile(r"^\s*(?:[-*•·▪]+|\d+[.)](?=\s))\s*")
_TO_TASTE_RE = re.compile(r"\b(to taste|as needed|optional|for serving|for garnish)\b", re.I)


@dataclass
class IngredientLine:
    name: str
    quantity: float | None = None
    unit: str = ""
    note: str = ""

    def as_text(self) -> str:
        """Render back to the "qty unit name, note" form used in the editor."""
        parts = []
        if self.quantity is not None:
            parts.append(units.format_quantity(self.quantity))
            if self.unit and units.normalize_unit(self.unit) != "pc":
                parts.append(units.normalize_unit(self.unit))
        parts.append(self.name)
        text = " ".join(parts)
        if self.note:
            text += f", {self.note}"
        return text


def _number(token: str) -> float:
    token = token.strip().replace(",", ".")
    total = 0.0
    for piece in token.split():
        if "/" in piece:
            num, den = piece.split("/", 1)
            total += float(num) / float(den) if float(den) else 0.0
            continue
        frac = 0.0
        if piece and piece[-1] in UNICODE_FRACTIONS:
            frac = UNICODE_FRACTIONS[piece[-1]]
            piece = piece[:-1]
        total += (float(piece) if piece else 0.0) + frac
    return total


def parse_quantity(text: str) -> tuple[float | None, str]:
    """Read a leading quantity. Returns (quantity, rest_of_text)."""
    s = text.strip()
    lowered = s.lower()
    for article in ("a ", "an "):
        if lowered.startswith(article):
            return 1.0, s[len(article) :].strip()
    m = _QTY_RE.match(s)
    if not m:
        return None, s
    qty = _number(m.group("qty"))
    if m.group("qty2"):
        # "2-3 carrots": plan for the larger amount so the shopping list is safe.
        qty = max(qty, _number(m.group("qty2")))
    return qty, s[m.end() :].strip()


def _split_unit(rest: str) -> tuple[str, str]:
    """Pull a unit off the front of the text, if there is one."""
    # "200g flour" has the unit glued to the number; the quantity regex
    # leaves "g flour" behind, so this also handles that case.
    words = rest.split()
    if not words:
        return "", rest
    if len(words) >= 2 and units.is_known_unit(f"{words[0]} {words[1]}"):
        unit = units.normalize_unit(f"{words[0]} {words[1]}")
        remaining = words[2:]
    elif units.is_known_unit(words[0]):
        unit = units.normalize_unit(words[0])
        remaining = words[1:]
    else:
        return "", rest
    if remaining and remaining[0].lower() == "of":
        remaining = remaining[1:]
    return unit, " ".join(remaining)


def parse_ingredient_line(line: str) -> IngredientLine | None:
    text = _BULLET_RE.sub("", line).strip()
    if not text:
        return None

    note_parts: list[str] = []
    for paren in re.findall(r"\(([^)]*)\)", text):
        note_parts.append(paren.strip())
    text = re.sub(r"\s*\([^)]*\)", "", text).strip()

    qty, rest = parse_quantity(text)
    unit = ""
    if qty is not None:
        unit, rest = _split_unit(rest)

    if "," in rest:
        rest, after = rest.split(",", 1)
        note_parts.insert(0, after.strip())
    m = _TO_TASTE_RE.search(rest)
    if m:
        note_parts.append(m.group(1).lower())
        rest = (rest[: m.start()] + rest[m.end() :]).strip(" ,-")

    name = re.sub(r"\s+", " ", rest).strip(" .-")
    if not name:
        return None
    note = "; ".join(p for p in note_parts if p)
    return IngredientLine(name=name, quantity=qty, unit=unit, note=note[:160])


def parse_ingredient_block(text: str) -> list[IngredientLine]:
    out = []
    for line in text.splitlines():
        parsed = parse_ingredient_line(line)
        if parsed:
            out.append(parsed)
    return out
