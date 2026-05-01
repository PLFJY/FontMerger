from __future__ import annotations

import re
import tempfile
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

from .models import FontFace, FontSource, InstanceMode, InstancePlan, OutputMode
from .naming import style_name


STANDARD_WEIGHTS = [100, 200, 300, 400, 500, 600, 700, 800, 900]


def plan_static_outputs(
    primary: FontSource,
    secondary: FontSource,
    out_dir: Path,
    output_mode: OutputMode,
    instance_mode: InstanceMode,
    family_name: str,
) -> list[InstancePlan]:
    if output_mode == "variable":
        _validate_variable_request(primary, secondary)
        raise NotImplementedError(
            "Experimental variable output is intentionally gated in this build. "
            "Use --output auto or --output static for safe fallback blending."
        )

    jobs: list[InstancePlan] = []
    for face, location, weight, italic, subfamily in _primary_instances(primary, instance_mode):
        sec_face = _choose_secondary_face(secondary, weight, italic)
        sec_location = _secondary_location(sec_face, weight, italic)
        label = f"{weight} {'Italic' if italic else 'Upright'}"
        file_name = _safe_file_name(f"{family_name} {subfamily}.ttf")
        jobs.append(
            InstancePlan(
                label=label,
                family_name=family_name,
                primary_face=face,
                secondary_face=sec_face,
                primary_location=location,
                secondary_location=sec_location,
                weight=weight,
                italic=italic,
                subfamily=subfamily,
                output_path=out_dir / file_name,
            )
        )
    return jobs


def materialize_instance(face: FontFace, location: dict[str, float], tmp_dir: Path) -> Path:
    if not face.is_variable:
        return face.path

    tmp_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".ttf" if face.path.suffix.lower() == ".ttf" else ".otf"
    handle = tempfile.NamedTemporaryFile(prefix="FontMerger-", suffix=suffix, dir=tmp_dir, delete=False)
    handle.close()

    # A variable font is a generator, not a bundle of finished static fonts.
    # We freeze only the requested axes and leave unspecified axes at default.
    font = TTFont(face.path, recalcTimestamp=False)
    try:
        static_font = instantiateVariableFont(font, location, inplace=False, optimize=True)
        static_font.save(handle.name)
    finally:
        font.close()
    return Path(handle.name)


def _primary_instances(
    source: FontSource,
    instance_mode: InstanceMode,
) -> list[tuple[FontFace, dict[str, float], int, bool, str]]:
    if source.kind != "variable":
        return [
            (face, {}, face.weight, face.italic, style_name(face.weight, face.italic))
            for face in sorted(source.faces, key=lambda f: (f.italic, f.weight, f.path.name))
        ]

    face = source.faces[0]
    axes = face.axes
    base = {tag: axis.default for tag, axis in axes.items()}
    locations: list[tuple[dict[str, float], str]] = []

    if instance_mode in {"auto", "named"} and face.named_instances:
        for inst in face.named_instances:
            loc = dict(base)
            loc.update({tag: _clamp(value, axes[tag]) for tag, value in inst.coordinates.items() if tag in axes})
            locations.append((loc, inst.subfamily))
    elif "wght" in axes:
        axis = axes["wght"]
        for weight in STANDARD_WEIGHTS:
            if axis.minimum <= weight <= axis.maximum:
                loc = dict(base)
                loc["wght"] = float(weight)
                locations.append((loc, style_name(weight, _location_is_italic(loc))))
    else:
        locations.append((base, style_name(face.weight, _location_is_italic(base))))

    # If the primary VF exposes an ital axis, produce upright/italic states
    # without expanding every possible axis combination. Other axes stay default.
    if "ital" in axes:
        expanded: list[tuple[dict[str, float], str]] = []
        for loc, label in locations:
            upright = dict(loc)
            upright["ital"] = _clamp(0, axes["ital"])
            expanded.append((upright, label.replace(" Italic", "")))
            if axes["ital"].maximum >= 1:
                italic = dict(loc)
                italic["ital"] = _clamp(1, axes["ital"])
                expanded.append((italic, f"{label.replace(' Italic', '')} Italic"))
        locations = expanded

    result = []
    for loc, label in locations:
        weight = int(round(loc.get("wght", face.weight)))
        italic = _location_is_italic(loc) or face.italic
        result.append((face, loc, weight, italic, style_name(weight, italic, label)))
    return result


def _choose_secondary_face(source: FontSource, weight: int, italic: bool) -> FontFace:
    faces = source.faces
    matching_style = [face for face in faces if face.italic == italic]
    pool = matching_style or [face for face in faces if not face.italic] or faces
    return min(pool, key=lambda face: abs(face.weight - weight))


def _secondary_location(face: FontFace, weight: int, italic: bool) -> dict[str, float]:
    if not face.is_variable:
        return {}
    loc = {tag: axis.default for tag, axis in face.axes.items()}
    if "wght" in face.axes:
        loc["wght"] = _clamp(weight, face.axes["wght"])
    if italic and "ital" in face.axes:
        loc["ital"] = _clamp(1, face.axes["ital"])
    return loc


def _validate_variable_request(primary: FontSource, secondary: FontSource) -> None:
    if primary.kind != "variable" or secondary.kind != "variable":
        raise ValueError("--output variable requires Primary VF + Secondary VF")
    primary_axes = set(primary.faces[0].axes)
    secondary_axes = set(secondary.faces[0].axes)
    if not primary_axes.issubset(secondary_axes) and not secondary_axes.issubset(primary_axes):
        raise ValueError(f"Incompatible VF axes: primary={sorted(primary_axes)}, secondary={sorted(secondary_axes)}")


def _location_is_italic(location: dict[str, float]) -> bool:
    return float(location.get("ital", 0)) >= 0.5


def _clamp(value: float, axis) -> float:
    return max(axis.minimum, min(axis.maximum, float(value)))


def _safe_file_name(name: str) -> str:
    return re.sub(r"[^\w.\- ]+", "", name).strip().replace(" ", "-")
