from __future__ import annotations

import copy
import os
import tempfile
from pathlib import Path
from typing import Callable

from fontTools import subset
from fontTools.merge import Merger
from fontTools.ttLib import TTFont
from fontTools.ttLib.scaleUpem import scale_upem

from .models import InstancePlan
from .naming import apply_names


LAYOUT_TABLES = {"GDEF", "GSUB", "GPOS", "BASE", "JSTF"}
CORE_MERGE_TABLES = {
    "head",
    "hhea",
    "maxp",
    "OS/2",
    "hmtx",
    "cmap",
    "glyf",
    "loca",
    "CFF ",
    "CFF2",
    "name",
    "post",
}
SECONDARY_TABLES_TO_DROP = LAYOUT_TABLES | {
    "STAT",
    "fvar",
    "gvar",
    "avar",
    "MVAR",
    "HVAR",
    "VVAR",
    "COLR",
    "CPAL",
    "CBDT",
    "CBLC",
    "sbix",
    "SVG ",
    "meta",
}


def blend_static_instance(
    plan: InstancePlan,
    primary_path: Path,
    secondary_path: Path,
    progress: Callable[[str], None] | None = None,
) -> tuple[Path, int]:
    primary = TTFont(primary_path, recalcTimestamp=False)
    secondary = TTFont(secondary_path, recalcTimestamp=False)
    try:
        missing_unicodes = sorted(_secondary_only_unicodes(primary, secondary))
        _notify(progress, f"Found {len(missing_unicodes)} missing Unicode mappings")
        if not missing_unicodes:
            merged = primary
            added_count = 0
            _notify(progress, "No fallback glyphs needed")
            _notify(progress, "Skipped merge; primary already covers secondary cmap")
        else:
            primary_for_merge = _keep_only_tables(primary, CORE_MERGE_TABLES)
            secondary_subset = _subset_secondary(secondary, missing_unicodes)
            _match_units_per_em(secondary_subset, primary)
            secondary_subset = _keep_only_tables(secondary_subset, CORE_MERGE_TABLES)
            added_count = len(missing_unicodes)
            _notify(progress, "Prepared secondary fallback subset")

            # Merger is used only after the secondary font has been reduced to
            # glyphs that primary cannot map from cmap. This keeps the blend a
            # fallback operation, not a replacement operation.
            primary_tmp = _save_temp_font(primary_for_merge, primary_path.suffix)
            secondary_tmp = _save_temp_font(secondary_subset, secondary_path.suffix)
            try:
                merged = Merger().merge([primary_tmp, secondary_tmp])
            finally:
                _remove_quietly(primary_tmp)
                _remove_quietly(secondary_tmp)
            _notify(progress, "Merged fallback outlines and cmap")

        _restore_primary_behavior(merged, primary)
        _notify(progress, "Restored primary glyphs, metrics, and layout")
        apply_names(merged, plan.family_name, plan.subfamily)
        _set_style_bits(merged, plan.weight, plan.italic)
        _notify(progress, "Applied output names and style flags")

        plan.output_path.parent.mkdir(parents=True, exist_ok=True)
        merged.save(plan.output_path)
        _notify(progress, "Saved output font")
        return plan.output_path, added_count
    finally:
        secondary.close()
        if primary is not locals().get("merged"):
            primary.close()


def _notify(progress: Callable[[str], None] | None, message: str) -> None:
    if progress:
        progress(message)


def _secondary_only_unicodes(primary: TTFont, secondary: TTFont) -> set[int]:
    primary_cmap = set(_best_cmap(primary))
    secondary_cmap = set(_best_cmap(secondary))
    return secondary_cmap - primary_cmap


def _best_cmap(font: TTFont) -> dict[int, str]:
    cmap = font.getBestCmap()
    if cmap:
        return cmap
    return {}


def _subset_secondary(font: TTFont, unicodes: list[int]) -> TTFont:
    working = copy.deepcopy(font)

    # Secondary layout logic is deliberately discarded. The primary font owns
    # shaping, features, metrics, and user-visible identity; secondary supplies
    # only fallback outlines and advance widths for missing Unicode values.
    for tag in SECONDARY_TABLES_TO_DROP:
        if tag in working:
            del working[tag]

    options = subset.Options()
    options.set(layout_features=[])
    options.name_IDs = []
    options.name_legacy = False
    options.name_languages = []
    options.notdef_outline = True
    options.recalc_bounds = True
    options.recalc_timestamp = False
    options.ignore_missing_glyphs = True
    options.ignore_missing_unicodes = True

    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=unicodes)
    subsetter.subset(working)
    return working


def _without_tables(font: TTFont, tags: set[str]) -> TTFont:
    working = copy.deepcopy(font)
    for tag in tags:
        if tag in working:
            del working[tag]
    return working


def _keep_only_tables(font: TTFont, tags: set[str]) -> TTFont:
    working = copy.deepcopy(font)
    for tag in list(working.keys()):
        if tag not in tags:
            del working[tag]
    return working


def _match_units_per_em(font: TTFont, primary: TTFont) -> None:
    if "head" not in font or "head" not in primary:
        return
    target_upem = primary["head"].unitsPerEm
    if font["head"].unitsPerEm != target_upem:
        scale_upem(font, target_upem)


def _save_temp_font(font: TTFont, suffix: str) -> str:
    tmp = tempfile.NamedTemporaryFile(prefix="FontMerger-merge-", suffix=suffix, delete=False)
    path = tmp.name
    tmp.close()
    font.save(path)
    return path


def _remove_quietly(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _restore_primary_behavior(merged: TTFont, primary: TTFont) -> None:
    for tag in LAYOUT_TABLES:
        if tag in primary:
            merged[tag] = copy.deepcopy(primary[tag])
        elif tag in merged:
            del merged[tag]

    _restore_primary_mapped_glyphs(merged, primary)
    _restore_post_identity(merged, primary)
    _copy_hhea_metrics(merged, primary)
    _copy_os2_metrics(merged, primary)


def _restore_primary_mapped_glyphs(merged: TTFont, primary: TTFont) -> None:
    primary_cmap = _best_cmap(primary)
    if not primary_cmap:
        return

    if "glyf" in merged and "glyf" in primary:
        glyph_order = list(merged.getGlyphOrder())
        glyph_set = set(glyph_order)
        primary_glyf = primary["glyf"]
        merged_glyf = merged["glyf"]

        for glyph_name in sorted(set(primary_cmap.values())):
            _copy_primary_glyf(glyph_name, merged, primary, glyph_order, glyph_set, merged_glyf, primary_glyf)
        merged.setGlyphOrder(glyph_order)

    if "hmtx" in merged and "hmtx" in primary:
        for glyph_name in set(primary_cmap.values()):
            if glyph_name in primary["hmtx"].metrics:
                merged["hmtx"].metrics[glyph_name] = primary["hmtx"].metrics[glyph_name]

    if "cmap" in merged:
        for table in merged["cmap"].tables:
            if table.isUnicode():
                table.cmap.update(primary_cmap)
        _sanitize_cmap_tables(merged)


def _copy_primary_glyf(
    glyph_name: str,
    merged: TTFont,
    primary: TTFont,
    glyph_order: list[str],
    glyph_set: set[str],
    merged_glyf,
    primary_glyf,
) -> None:
    if glyph_name not in primary_glyf.glyphs:
        return

    glyph = copy.deepcopy(primary_glyf[glyph_name])
    if glyph.isComposite():
        for component in glyph.components:
            _copy_primary_glyf(component.glyphName, merged, primary, glyph_order, glyph_set, merged_glyf, primary_glyf)

    merged_glyf.glyphs[glyph_name] = glyph
    if glyph_name not in glyph_set:
        glyph_order.append(glyph_name)
        glyph_set.add(glyph_name)


def _sanitize_cmap_tables(font: TTFont) -> None:
    if "cmap" not in font:
        return
    for table in font["cmap"].tables:
        if table.isUnicode() and table.format in {0, 2, 4, 6}:
            table.cmap = {codepoint: name for codepoint, name in table.cmap.items() if codepoint <= 0xFFFF}


def _restore_post_identity(merged: TTFont, primary: TTFont) -> None:
    if "post" not in merged:
        return
    if "post" in primary:
        merged["post"].italicAngle = primary["post"].italicAngle
        merged["post"].underlinePosition = primary["post"].underlinePosition
        merged["post"].underlineThickness = primary["post"].underlineThickness
        merged["post"].isFixedPitch = primary["post"].isFixedPitch

    # Keep glyph names serializable. Format 3 discards names on save, which is
    # especially confusing for Nerd Font / PUA glyphs even when outlines are
    # preserved correctly.
    merged["post"].formatType = 2.0
    if not hasattr(merged["post"], "extraNames"):
        merged["post"].extraNames = []
    if not hasattr(merged["post"], "mapping"):
        merged["post"].mapping = {}


def _copy_hhea_metrics(merged: TTFont, primary: TTFont) -> None:
    if "hhea" not in merged or "hhea" not in primary:
        return
    keep = [
        "ascent",
        "descent",
        "lineGap",
        "caretSlopeRise",
        "caretSlopeRun",
        "caretOffset",
        "advanceWidthMax",
        "minLeftSideBearing",
        "minRightSideBearing",
        "xMaxExtent",
    ]
    for attr in keep:
        if hasattr(primary["hhea"], attr):
            setattr(merged["hhea"], attr, getattr(primary["hhea"], attr))


def _copy_os2_metrics(merged: TTFont, primary: TTFont) -> None:
    if "OS/2" not in merged or "OS/2" not in primary:
        return
    keep = [
        "sTypoAscender",
        "sTypoDescender",
        "sTypoLineGap",
        "usWinAscent",
        "usWinDescent",
        "sxHeight",
        "sCapHeight",
        "ySubscriptXSize",
        "ySubscriptYSize",
        "ySubscriptXOffset",
        "ySubscriptYOffset",
        "ySuperscriptXSize",
        "ySuperscriptYSize",
        "ySuperscriptXOffset",
        "ySuperscriptYOffset",
        "yStrikeoutSize",
        "yStrikeoutPosition",
    ]
    for attr in keep:
        if hasattr(primary["OS/2"], attr):
            setattr(merged["OS/2"], attr, getattr(primary["OS/2"], attr))


def _set_style_bits(font: TTFont, weight: int, italic: bool) -> None:
    if "OS/2" in font:
        font["OS/2"].usWeightClass = int(weight)
        if hasattr(font["OS/2"], "fsSelection"):
            if italic:
                font["OS/2"].fsSelection |= 0x01
                font["OS/2"].fsSelection &= ~0x40
            else:
                font["OS/2"].fsSelection &= ~0x01
                if weight == 400:
                    font["OS/2"].fsSelection |= 0x40
    if "head" in font:
        if italic:
            font["head"].macStyle |= 0b10
        else:
            font["head"].macStyle &= ~0b10
        if weight >= 700:
            font["head"].macStyle |= 0b1
        else:
            font["head"].macStyle &= ~0b1
    if "post" in font and not italic:
        font["post"].italicAngle = 0
