#!/usr/bin/env python3
"""Read-only inventory of saved OSM GIS; never grants positional accuracy.

Assemble native water rings by identical node IDs only. No interpolation,
simplification, gap closure, replacement of the navigation axis, or Renderer work.
"""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from osgeo import ogr


HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[3]
SOURCE = ENGINE / "recovery/event-data/suez-full-canal-20261012"
INPUTS = [
    "relation-1410016-full.osm",
    "relation-1691290-full.osm",
    "port-said-mouth-map.osm",
    "suez-mouth-map.osm",
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tags(element):
    return {tag.attrib["k"]: tag.attrib["v"] for tag in element.findall("tag")}


def write(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def assemble_rings(member_ids, ways, nodes):
    """Require each native member and every native vertex. Fail on open ring."""
    remaining = [[int(n.attrib["ref"]) for n in ways[mid].findall("nd")]
                 for mid in member_ids]
    rings = []
    while remaining:
        ring = remaining.pop(0)
        while ring[-1] != ring[0]:
            matches = [(i, piece) for i, piece in enumerate(remaining)
                       if piece[0] == ring[-1] or piece[-1] == ring[-1]]
            if len(matches) != 1:
                raise ValueError("Native ring is open or ambiguous; no gap closure")
            i, piece = matches[0]
            remaining.pop(i)
            if piece[-1] == ring[-1]:
                piece = list(reversed(piece))
            ring.extend(piece[1:])
        rings.append((ring, [nodes[n] for n in ring]))
    return rings


def run():
    nodes, ways, relations = {}, {}, {}
    inventories = []
    for filename in INPUTS:
        path = SOURCE / "sources/osm" / filename
        root = ET.parse(path).getroot()
        for node in root.findall("node"):
            key = int(node.attrib["id"])
            value = [float(node.attrib["lon"]), float(node.attrib["lat"])]
            if key in nodes and nodes[key] != value:
                raise ValueError("Saved snapshots disagree on native coordinates")
            nodes[key] = value
        for kind, target in [("way", ways), ("relation", relations)]:
            for element in root.findall(kind):
                key = int(element.attrib["id"])
                if key in target and ET.tostring(target[key]) != ET.tostring(element):
                    # Full XML may vary in whitespace only; geometry/tags must agree.
                    previous = target[key]
                    if tags(previous) != tags(element) or [x.attrib for x in previous.findall("nd")] != [x.attrib for x in element.findall("nd")]:
                        raise ValueError("Saved snapshots disagree on native objects")
                target[key] = element
        inventories.append({
            "file": str(path.relative_to(ENGINE)), "sha256": digest(path),
            "native_nodes": len(root.findall("node")),
            "native_ways": len(root.findall("way")),
            "native_relations": len(root.findall("relation")),
            "retrieval_reference": str(path.with_suffix(".retrieval.json").relative_to(ENGINE)),
        })

    features, water_audits = [], []
    for relation_id, relation in sorted(relations.items()):
        t = tags(relation)
        if t.get("type") != "multipolygon" or not (t.get("natural") == "water" or t.get("water")):
            continue
        members = relation.findall("member")
        missing = [m.attrib["ref"] for m in members if m.attrib["type"] != "way" or int(m.attrib["ref"]) not in ways]
        row = {"osm_relation": relation_id, "version": int(relation.attrib["version"]),
               "tags": t, "missing_native_members": missing,
               "positional_error_metres": None,
               "accuracy_status": "UNVERIFIED_SOURCE_POSITIONAL_ACCURACY"}
        if missing:
            row["assembly"] = "NOT_ASSEMBLED_MISSING_NATIVE_MEMBERS"
            water_audits.append(row)
            continue
        outers = [int(m.attrib["ref"]) for m in members if m.attrib.get("role") in ["outer", ""]]
        inners = [int(m.attrib["ref"]) for m in members if m.attrib.get("role") == "inner"]
        try:
            outer_rings = assemble_rings(outers, ways, nodes)
            inner_rings = assemble_rings(inners, ways, nodes)
            polygons = [[outer[1]] for outer in outer_rings]
            for _, inner in inner_rings:
                inner_geometry = ogr.CreateGeometryFromJson(json.dumps({"type": "Polygon", "coordinates": [inner]}))
                owners = [i for i, p in enumerate(polygons) if ogr.CreateGeometryFromJson(json.dumps({"type": "Polygon", "coordinates": p})).Contains(inner_geometry)]
                if len(owners) != 1:
                    raise ValueError("Native inner ring has ambiguous/no outer owner")
                polygons[owners[0]].append(inner)
            geometry = {"type": "MultiPolygon", "coordinates": polygons}
            native = ogr.CreateGeometryFromJson(json.dumps(geometry))
            if not native.IsValid():
                raise ValueError("Native water polygon is invalid; repair prohibited")
            points = [p for polygon in polygons for ring in polygon for p in ring]
            row.update(assembly="EXACT_NATIVE_NODE_ID_JOIN_ONLY",
                       native_geometry_valid=True, outer_rings=len(outer_rings),
                       inner_rings=len(inner_rings), coordinate_count=len(points),
                       source_relative_simplification_error_metres=0,
                       generated_coordinates=0, interpolated_coordinates=0,
                       changed_source_coordinates=0,
                       all_derivative_coordinates_match_source_node_ids=True,
                       outer_ring_native_node_ids=[ring[0] for ring in outer_rings],
                       inner_ring_native_node_ids=[ring[0] for ring in inner_rings],
                       member_way_versions={str(int(m.attrib["ref"])): int(ways[int(m.attrib["ref"])].attrib["version"]) for m in members},
                       bounds=[min(p[0] for p in points), min(p[1] for p in points),
                               max(p[0] for p in points), max(p[1] for p in points)])
            feature = {"type": "Feature", "id": f"osm:relation:{relation_id}",
                       "properties": {"osm_relation": relation_id,
                                      "version": row["version"], "name": t.get("name:en", t.get("name")),
                                      "source_native_tags": t,
                                      "positional_error_metres": None,
                                      "source_relative_simplification_error_metres": 0,
                                      "admission_status": "NOT_ADMITTED_UNVERIFIED_POSITIONAL_ACCURACY"},
                       "geometry": geometry}
            features.append(feature)
        except ValueError as error:
            row.update(assembly="NOT_ASSEMBLED_FAIL_CLOSED", error=str(error))
        water_audits.append(row)

    axis_path = SOURCE / "FULL_CANAL_MAIN_AXIS.geojson"
    axis_document = json.loads(axis_path.read_text())
    axis = axis_document.get("geometry")
    if axis is None:
        axis = axis_document["features"][0]["geometry"]
    points = axis["coordinates"]
    for row in water_audits:
        feature = next((f for f in features if f["properties"]["osm_relation"] == row["osm_relation"]), None)
        if feature:
            geometry = ogr.CreateGeometryFromJson(json.dumps(feature["geometry"]))
            row["unchanged_axis_native_vertices_in_or_on_water"] = sum(
                geometry.Intersects(ogr.CreateGeometryFromJson(json.dumps({"type": "Point", "coordinates": p})))
                for p in points)

    coastline = []
    for key, way in sorted(ways.items()):
        t = tags(way)
        if t.get("natural") == "coastline":
            refs = [int(n.attrib["ref"]) for n in way.findall("nd")]
            coastline.append({"way": key, "version": int(way.attrib["version"]),
                              "native_node_count": len(refs), "closed": refs[0] == refs[-1],
                              "all_native_coordinates_available": all(n in nodes for n in refs),
                              "source_tag": t.get("source"),
                              "positional_error_metres": None})

    write("SAVED_NATIVE_WATER_COMPARISON.geojson", {
        "type": "FeatureCollection", "features": features,
        "purpose": "Comparison GIS only. Does not replace locked Canal axis or native country GIS.",
        "crs_description": "EPSG:4326 longitude/latitude",
        "license": "ODbL 1.0", "attribution": "© OpenStreetMap contributors",
    })
    write("SAVED_OSM_GIS_AUDIT.json", {
        "status": "COMPARISON_ONLY_NOT_DETAIL_ADMITTED",
        "source_inputs": inventories,
        "source_license_reference": "recovery/event-data/suez-full-canal-20261012/sources/osm/OSM_LICENSE.json",
        "water_relations": water_audits, "coastline_ways": coastline,
        "locked_axis": {"file": str(axis_path.relative_to(ENGINE)), "sha256": digest(axis_path),
                        "coordinate_count": len(points), "segment_count": len(points)-1,
                        "modified": False, "metric_value_or_source_modified": False},
        "admission_limits": [
            "Detailed native vertices prove preservation, not absolute positional accuracy.",
            "Bing/Landsat source tags have no acquisition/product/registration/error-bound provenance.",
            "Stored entrance and lake extracts do not prove continuous full-extent coastline/water coverage.",
            "Water polygons are not complete primary/relevant country Polygon GIS required by LocalDetailAdmission.",
            "Current LocalDetailAdmission supports Point events only; locked Canal LineString is unsupported.",
        ],
    })


if __name__ == "__main__":
    run()
