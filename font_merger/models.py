from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


SourceKind = Literal["static", "family", "variable"]
OutputMode = Literal["auto", "static", "variable"]
InstanceMode = Literal["auto", "named", "custom"]


@dataclass(frozen=True)
class AxisInfo:
    tag: str
    minimum: float
    default: float
    maximum: float


@dataclass(frozen=True)
class NamedInstance:
    subfamily: str
    coordinates: dict[str, float]


@dataclass(frozen=True)
class FontFace:
    path: Path
    is_variable: bool
    family: str
    subfamily: str
    full_name: str
    postscript_name: str
    weight: int
    italic: bool
    axes: dict[str, AxisInfo] = field(default_factory=dict)
    named_instances: list[NamedInstance] = field(default_factory=list)


@dataclass(frozen=True)
class FontSource:
    path: Path
    kind: SourceKind
    faces: list[FontFace]


@dataclass(frozen=True)
class InstancePlan:
    label: str
    family_name: str
    primary_face: FontFace
    secondary_face: FontFace
    primary_location: dict[str, float]
    secondary_location: dict[str, float]
    weight: int
    italic: bool
    subfamily: str
    output_path: Path
