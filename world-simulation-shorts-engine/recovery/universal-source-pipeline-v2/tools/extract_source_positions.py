"""Lossless evidence adapter for original, dated cartographic PDF vector paths.

This creates source-coordinate observations, never geographic control polygons.
The selection receipt is specific source data; it does not change any renderer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import fitz

SOURCE_SHA256 = "34d1bf77b29304711cef0ca41a9fcbddec0f04bc14ec11d3088f6373b238f41b"
SOURCE_URL = "https://www.govinfo.gov/content/pkg/GOVPUB-D114-PURL-gpo126577/pdf/GOVPUB-D114-PURL-gpo126577.pdf"
BLUE = (0.15272754430770874, 0.3145647346973419, 0.6107118129730225)
# All are path indices in PyMuPDF's source page drawing list, zero-based. The
# paired hachure decoration is omitted, preserving the actual source centerline.
SELECTIONS = ((69, "1950-09-15", "[] 0"), (71, "1950-09-15", "[] 0"),
              (73, "1950-09-15", "[] 0"), (75, "1950-09-15", "[] 0"),
              (77, "1950-09-15", "[] 0"), (79, "1950-09-15", "[] 0"),
              (63, "1950-09-16", "[ 12 3.5 0 0 0 0 ] 0"),
              (67, "1950-09-16", "[ 12 3.5 0 0 0 0 ] 0"))


def _commands(items):
    result = []
    for item in items:
        if item[0] not in {"l", "c"}:
            raise ValueError("SOURCE_PATH_COMMAND_UNSUPPORTED")
        points = [[p.x, p.y] for p in item[1:]]
        result.append({"op": item[0], "points": points})
    return result


def extract(source_path):
    source_path = Path(source_path)
    raw = source_path.read_bytes()
    if source_path.is_symlink() or hashlib.sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("SOURCE_ORIGINAL_HASH_MISMATCH")
    doc = fitz.open(stream=raw, filetype="pdf")
    page = doc[7]
    paths = page.get_drawings()
    if len(paths) != 126 or len(page.get_images()) != 0 or list(page.rect) != [0., 0., 396., 612.]:
        raise ValueError("SOURCE_PAGE_VECTOR_CONTRACT_CHANGED")
    # Legend samples are source observations as well. These checks prevent a
    # different same-colored line (e.g. planned BHL) being accepted by color.
    if (paths[125]["dashes"] != "[ 12 3.5 0 0 0 0 ] 0"
            or abs(paths[125]["width"] - 1.44) > 1e-6
            or paths[123]["dashes"] != "[ .5 2.43 0 0 0 0 ] 0"
            or paths[124]["dashes"] != "[] 0"):
        raise ValueError("SOURCE_LEGEND_STYLE_CHANGED")
    positions = []
    for index, date, dashes in SELECTIONS:
        path = paths[index]
        if (path["type"] != "s" or tuple(path["color"]) != BLUE
                or abs(path["width"] - 1.44) > 1e-6 or path["dashes"] != dashes
                or path["closePath"] is not False or path["rect"].y1 > 212):
            raise ValueError("SOURCE_SELECTED_POSITION_PATH_CHANGED")
        commands = _commands(path["items"])
        positions.append({"id": "cmh19-7-pdf008-path-" + str(index),
            "source_path_index_zero_based": index, "source_sequence_number": path["seqno"],
            "as_of_date": date, "time_qualifier": "NIGHT", "actor_id": "US_MARINE_POSITION",
            "classification": "OBSERVED_SOURCE_CARTOGRAPHY_NOT_GEOREGISTERED",
            "source_legend": "Marine Positions, Night, " + ("15 Sep" if date.endswith("15") else "16 Sep"),
            "geometry": {"type": "PDF_VECTOR_PATH", "commands": commands, "closed": False,
                "source_bounds": list(path["rect"])},
            "source_style": {"color_rgb": list(path["color"]), "stroke_width_points": path["width"], "dashes": path["dashes"]},
            "represents_complete_owner_mask": False, "geographic_render_allowed": False})
    return {"schema": "WORLD_ENGINE_SOURCE_COORDINATE_OBSERVATIONS_V1", "source_id": "GOVINFO_CMH_19_7_UN_OFFENSIVE",
        "source_url": SOURCE_URL, "source_sha256": SOURCE_SHA256, "source_bytes": len(raw),
        "title": "The Korean War: The UN Offensive, 16 September–2 November 1950",
        "author": "Stephen L. Y. Gammons", "publication_year": 2000,
        "pdf_page_1_based": 8, "printed_page": "8", "map_caption": "THE INCH'ON LANDING, 15–18 September 1950",
        "page_coordinates": {"crs": "PDF_PAGE_POINTS_TOP_LEFT", "units": "1/72 inch", "axis_order": ["x_right", "y_down"],
            "page_size_points": [396, 612], "geographic_crs": None, "geographic_datum": None,
            "coordinate_transform": {"to": "EPSG:4326", "status": "UNVERIFIED", "coefficients": None}},
        "selection_evidence": {"method": "Native original PDF drawing commands selected by inspected source legend/date/style and path receipts, not an image trace",
            "source_path_count": len(paths), "source_embedded_images": 0, "selected_path_count": len(positions),
            "legend_path_indices": [123, 124, 125], "excluded_bhl_path_index": 80,
            "excluded_bhl_reason": "Planned/prearranged Beachhead Line has a different source stroke width (1.0 point) and BHL label; not a generic observed control boundary",
            "duplicate_background_and_hachure_components_excluded": [56, 58, 60, 62, 68, 70, 72, 74, 76, 78],
            "landing_arrows_unit_symbols_shoreline_and_urban_fill_excluded": True,
            "curve_commands_preserved_without_resampling": True, "coordinates_generated_or_interpolated": 0},
        "positions": positions, "owner_masks": [], "unknown_geographic_extent": True,
        "registration": {"status": "BLOCKED", "independent_geographic_gcps": 0, "residual_meters": None,
            "held_out_residual_meters": None, "total_spatial_accuracy_meters": None,
            "reason": "No source-qualified PDF-page-to-geographic transformation. The date labels and page paths do not establish geolocation or total control."},
        "license": {"scope": "Federal-authored historical cartography only", "basis": "U.S. Army Center of Military History authorship; U.S. government work under 17 USC 105",
            "photos_and_third_party_material_included": False},
        "extraction_runtime": {"library": "PyMuPDF", "version": fitz.VersionBind},
        "render_allowed": False, "g2_full_area": "BLOCKED", "user_approved": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-pdf", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = extract(args.source_pdf)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        raise ValueError("REFUSE_REPLACE_SOURCE_EVIDENCE")
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"output": args.output.name, "paths": len(result["positions"]), "status": result["registration"]["status"]}))
