from __future__ import annotations

from fontTools.ttLib import TTFont

from .models import FontFace


def family_from_primary(face: FontFace) -> str:
    return face.family


def default_blend_family(primary: FontFace, secondary: FontFace) -> str:
    if primary.family == secondary.family:
        return primary.family
    return f"{primary.family} {secondary.family}"


def style_name(weight: int, italic: bool, preferred: str | None = None) -> str:
    if preferred and preferred.lower() not in {"instance", "regular"}:
        base = _normalize_style(preferred)
        if italic and "Italic" not in base:
            base = f"{base} Italic"
        return base

    names = {
        100: "Thin",
        200: "ExtraLight",
        300: "Light",
        400: "Regular",
        500: "Medium",
        600: "SemiBold",
        700: "Bold",
        800: "ExtraBold",
        900: "Black",
    }
    nearest = min(names, key=lambda value: abs(value - weight))
    base = names[nearest]
    if italic:
        return "Italic" if base == "Regular" else f"{base} Italic"
    return base


def apply_names(font: TTFont, family: str, subfamily: str) -> None:
    full_name = f"{family} {subfamily}".strip()
    ps_name = "".join(ch for ch in f"{family}-{subfamily}" if ch.isalnum() or ch == "-")
    name_table = font["name"]

    _set_name(name_table, 1, family)
    _set_name(name_table, 2, subfamily)
    _set_name(name_table, 4, full_name)
    _set_name(name_table, 6, ps_name)
    _set_name(name_table, 16, family)
    _set_name(name_table, 17, subfamily)


def _set_name(name_table, name_id: int, value: str) -> None:
    for platform_id, encoding_id, lang_id in ((3, 1, 0x409), (1, 0, 0)):
        name_table.setName(value, name_id, platform_id, encoding_id, lang_id)


def _normalize_style(style: str) -> str:
    return " ".join(part for part in style.replace("-", " ").split() if part)
