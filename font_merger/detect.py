from __future__ import annotations

from pathlib import Path

from fontTools.ttLib import TTFont

from .models import AxisInfo, FontFace, FontSource, NamedInstance


FONT_EXTENSIONS = {".ttf", ".otf"}


def detect_source(path: Path) -> FontSource:
    path = path.expanduser().resolve()
    if path.is_dir():
        faces = [_read_face(p) for p in _font_files(path)]
        if not faces:
            raise ValueError(f"No .ttf/.otf files found in directory: {path}")
        kind = "variable" if len(faces) == 1 and faces[0].is_variable else "family"
        return FontSource(path=path, kind=kind, faces=faces)

    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() not in FONT_EXTENSIONS:
        raise ValueError(f"Unsupported font extension: {path.suffix}")

    face = _read_face(path)
    return FontSource(path=path, kind="variable" if face.is_variable else "static", faces=[face])


def describe_source(source: FontSource) -> str:
    if source.kind == "variable":
        face = source.faces[0]
        axes = ", ".join(face.axes) or "none"
        return f"Variable Font: {face.family} ({axes})"
    if source.kind == "family":
        return f"Static Family: {len(source.faces)} files"
    return f"Static Font: {source.faces[0].full_name}"


def _font_files(path: Path) -> list[Path]:
    return sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() in FONT_EXTENSIONS)


def _read_face(path: Path) -> FontFace:
    font = TTFont(path, lazy=False)
    try:
        is_variable = "fvar" in font
        family = _name(font, 16) or _name(font, 1) or path.stem
        subfamily = _name(font, 17) or _name(font, 2) or "Regular"
        full_name = _name(font, 4) or f"{family} {subfamily}".strip()
        ps_name = _name(font, 6) or _ps_name(family, subfamily)
        weight = _weight(font, subfamily)
        italic = _is_italic(font, subfamily)
        axes = _axes(font) if is_variable else {}
        instances = _named_instances(font) if is_variable else []
        return FontFace(
            path=path,
            is_variable=is_variable,
            family=family,
            subfamily=subfamily,
            full_name=full_name,
            postscript_name=ps_name,
            weight=weight,
            italic=italic,
            axes=axes,
            named_instances=instances,
        )
    finally:
        font.close()


def _name(font: TTFont, name_id: int) -> str | None:
    table = font["name"]
    for platform_id, encoding_id, lang_id in ((3, 1, 0x409), (3, 10, 0x409), (1, 0, 0)):
        record = table.getName(name_id, platform_id, encoding_id, lang_id)
        if record:
            return str(record.toUnicode()).strip()
    records = table.names
    for record in records:
        if record.nameID == name_id:
            value = str(record.toUnicode()).strip()
            if value:
                return value
    return None


def _axes(font: TTFont) -> dict[str, AxisInfo]:
    return {
        axis.axisTag: AxisInfo(
            tag=axis.axisTag,
            minimum=float(axis.minValue),
            default=float(axis.defaultValue),
            maximum=float(axis.maxValue),
        )
        for axis in font["fvar"].axes
    }


def _named_instances(font: TTFont) -> list[NamedInstance]:
    result: list[NamedInstance] = []
    for inst in font["fvar"].instances:
        subfamily = _name_by_id(font, inst.subfamilyNameID) or "Instance"
        result.append(NamedInstance(subfamily=subfamily, coordinates=dict(inst.coordinates)))
    return result


def _name_by_id(font: TTFont, name_id: int) -> str | None:
    for record in font["name"].names:
        if record.nameID == name_id:
            value = str(record.toUnicode()).strip()
            if value:
                return value
    return None


def _weight(font: TTFont, subfamily: str) -> int:
    if "OS/2" in font:
        return int(getattr(font["OS/2"], "usWeightClass", 400))
    text = subfamily.lower()
    names = {
        "thin": 100,
        "extralight": 200,
        "ultralight": 200,
        "light": 300,
        "regular": 400,
        "book": 400,
        "medium": 500,
        "semibold": 600,
        "demibold": 600,
        "bold": 700,
        "extrabold": 800,
        "ultrabold": 800,
        "black": 900,
        "heavy": 900,
    }
    for marker, value in names.items():
        if marker in text.replace(" ", ""):
            return value
    return 400


def _is_italic(font: TTFont, subfamily: str) -> bool:
    text = subfamily.lower()
    if "italic" in text or "oblique" in text:
        return True
    if "head" in font and bool(getattr(font["head"], "macStyle", 0) & 0b10):
        return True
    if "post" in font and float(getattr(font["post"], "italicAngle", 0)) != 0:
        return True
    return False


def _ps_name(family: str, subfamily: str) -> str:
    raw = f"{family}-{subfamily}"
    return "".join(ch for ch in raw if ch.isalnum() or ch == "-")
