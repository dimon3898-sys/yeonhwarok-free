"""Author explicit nonhistorical fixture samples; never digitize historical areas.

The selected source-country polygon is a modern GIS domain only. A synthetic
split is intersected with that domain using the existing GEOS binding. Every
sample is persisted and pinned before Studio can select it. No renderer infers
this split, changes source precision, or interprets it as an actual event.
"""
import argparse
from copy import deepcopy
import importlib.util
import json
import math
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("_build_source_contract", HERE / "source_contract.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)
c = contract.control


def put(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = contract.canonical(value)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError("SOURCE_FIXTURE_REFUSE_OVERWRITE")
    if not path.exists():
        path.write_bytes(raw)
    return {"path": relative, "sha256": contract.sha(raw)}


def build(native_file, root):
    if root.exists():
        raise ValueError("SOURCE_PACKAGE_ROOT_MUST_BE_NEW")
    root.mkdir(parents=True)
    native = json.loads(native_file.read_bytes())
    plan = native["nativePlan"]
    primary = next(g for g in plan["geometries"] if g["id"] == plan["primary"])
    modern_domain = {"type": primary["geometry_type"], "coordinates": primary["coordinates"]}
    c.validate_area_geometries([modern_domain])
    points = []
    def collect(x):
        if len(x) == 2 and all(type(y) in (int, float) for y in x):
            points.append(x)
        else:
            for part in x:
                collect(part)
    collect(modern_domain["coordinates"])
    bounds = [min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)]
    # Author a conservative synthetic observation-grid domain. The unchanged
    # source coastline is NOT substituted as a precise observed control area.
    # Binary-exact cells avoid GEOS intersection roundoff slivers in the strict
    # original source validator, without relaxing it or changing source values.
    with c._Geos() as g:
        modern = g.geometry(modern_domain)
        combined = None
        step = .25
        w,s,e,n=bounds
        for ix in range(math.floor(w/step),math.ceil(e/step)):
            for iy in range(math.floor(s/step),math.ceil(n/step)):
                x,y=ix*step,iy*step
                cell=g.geometry({"type":"Polygon","coordinates":[[[x,y],[x+step,y],[x+step,y+step],[x,y+step],[x,y]]]})
                if g.area(g.operation("difference",cell,modern)) == 0:
                    combined=cell if combined is None else g.operation("union",combined,cell)
        if combined is None:
            raise ValueError("SYNTHETIC_LAND_CONTAINED_GRID_DOMAIN_UNAVAILABLE")
        grid=g.json(combined)
        pieces=[grid["coordinates"]] if grid["type"]=="Polygon" else grid["coordinates"]
        selected=max(pieces,key=lambda p:g.area(g.geometry({"type":"Polygon","coordinates":p})))
        domain={"type":"Polygon","coordinates":selected}
        assert g.area(g.operation("difference",g.geometry(domain),modern))==0
    c.validate_area_geometries([domain])
    points.clear()
    collect(domain["coordinates"])
    bounds = [min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)]
    total = len(native["cameraSchedule"])
    recipe = {"schema": "SYNTHETIC_ZONE_PARTITION_RECIPE_V2", "purpose": "NONHISTORICAL_TECHNICAL_TEST_ONLY",
        "modernDomainSource": {k: primary[k] for k in ("id", "source_id", "source_version", "source_file_sha256")},
        "domainQualification": "AUTHORED_0.25_DEGREE_BINARY_GRID_CELLS_FULLY_INSIDE_UNCHANGED_MODERN_GIS_LARGEST_CONNECTED_POLYGON_NOT_OBSERVED_TERRITORY_OR_COASTLINE",
        "frames": total, "method": "GEOS intersection of current authored jagged halfplane with unchanged modern source domain; opponent is separately authored halfplane intersection, not inferred historical complement",
        "transitionStartFrame": 25, "transitionEndFrame": 130, "progressFractions": [.70, .30],
        "periodicFrontAmplitudeDegrees": .20, "historicalEventClaimed": False, "license": "CC0-1.0 authored synthetic partition; Natural Earth modern GIS Public Domain"}
    recipe_binding = put(root, "demo/RECIPE.json", recipe)
    native_binding = put(root, "demo/NATIVE.json", native)
    domain_binding = put(root, "demo/DOMAIN.geojson", domain)
    states = []
    with c._Geos() as geos:
        base = geos.geometry(domain)
        w, s, e, n = bounds
        margin = 1
        for frame in range(total):
            t = max(0, min(1, (frame - 25) / (130 - 25)))
            eased = t*t*(3-2*t)
            y = s + (n - s) * (.70 - .40 * eased)
            xs = [w-margin+(e-w+2*margin)*i/12 for i in range(13)]
            front = [[x, y + .20 * math.sin(i*1.25)] for i,x in enumerate(xs)]
            low = {"type": "Polygon", "coordinates": [[[w-margin,s-margin],[e+margin,s-margin],*reversed(front),[w-margin,s-margin]]]}
            high = {"type": "Polygon", "coordinates": [[*front,[e+margin,n+margin],[w-margin,n+margin],front[0]]]}
            masks = [geos.json(geos.operation("intersection", base, geos.geometry(g))) for g in (low, high)]
            receipts, owner_rows = [], []
            for actor, geometry in zip(("ZONE_A", "ZONE_B"), masks):
                binding = put(root, f"demo/frames/{frame:03d}_{actor}.geojson", geometry)
                receipts.append({"id": actor, "sourcePath": "../RECIPE.json", "sourceSHA256": recipe_binding["sha256"],
                    "sourceURL": "urn:world-engine:synthetic-zone-fixture-v2", "geometryPath": Path(binding["path"]).name,
                    "geometryFileSHA256": binding["sha256"], "geometrySHA256": contract.sha(contract.canonical(geometry)),
                    "qualification": "SYNTHETIC_TEST", "asOfDate": "2000-01-01", "timeQualifier": "DATE_ONLY", "factions": [actor],
                    "crs": "EPSG:4326", "license": "CC0-1.0 synthetic fixture over Natural Earth Public Domain", "licenseStatus": "REVIEWED_FOR_THIS_GEOMETRY"})
                owner_rows.append({"factionId": actor, "geometry": geometry, "sourceRef": actor})
            # Per-frame manifest has its own contained files; no '..' escape.
            put(root, f"demo/frames/{frame:03d}_RECIPE.json", recipe)
            put(root, f"demo/frames/{frame:03d}_DOMAIN.geojson", domain)
            for receipt in receipts:
                receipt["sourcePath"] = f"{frame:03d}_RECIPE.json"
            receipts.append({"id": "DOMAIN", "sourcePath": f"{frame:03d}_RECIPE.json", "sourceSHA256": recipe_binding["sha256"],
                "sourceURL": "urn:world-engine:synthetic-zone-fixture-v2", "geometryPath": f"{frame:03d}_DOMAIN.geojson",
                "geometryFileSHA256": domain_binding["sha256"], "geometrySHA256": contract.sha(contract.canonical(domain)),
                "qualification": "SYNTHETIC_TEST", "asOfDate": "2000-01-01", "timeQualifier": "DATE_ONLY", "factions": [],
                "crs": "EPSG:4326", "license": "Natural Earth Public Domain; synthetic fixture receipt", "licenseStatus": "REVIEWED_FOR_THIS_GEOMETRY"})
            receipt_binding = put(root, f"demo/frames/{frame:03d}_RECEIPTS.json", {"schema": c.RECEIPT_SCHEMA, "mode": "SYNTHETIC_TEST", "receipts": receipts})
            document = {"schema": c.SCHEMA, "mode": "SYNTHETIC_TEST", "stateId": f"SYNTHETIC_STATE_{frame:03d}", "frame": frame,
                "asOfDate": "2000-01-01", "timeQualifier": "DATE_ONLY", "bbox": bounds, "crs": "EPSG:4326", "classification": "schematic",
                "factions": ["ZONE_A", "ZONE_B"], "domain": {"geometry": domain, "sourceRef": "DOMAIN"}, "ownerMasks": owner_rows,
                "unknownMasks": [], "contestedMasks": []}
            state_binding = put(root, f"demo/frames/{frame:03d}_STATE.json", document)
            states.append({"state": state_binding, "receipts": receipt_binding})
    scene = {"schema": contract.SCHEMA, "scenario_id": "synthetic_observation_zones", "event_id": "AUTHORED_ZONE_REALLOCATION",
        "title": "SYNTHETIC DEMO - observation zones", "durationSeconds": total/30, "fps": 30, "resolution": [1080,1920], "startFrame": 0,
        "time_interval": {"simulation_date": "2000-01-01", "historical_start": None, "historical_end": None, "presentation_frames": [0,total]},
        "source_bundle_id": "synthetic_zones_v2", "source_refs": ["SYNTHETIC_ZONE_PARTITION_RECIPE_V2"],
        "geometry": {"crs": "EPSG:4326", "coordinate_transform": {"kind": "IDENTITY", "status": "VERIFIED", "axis_order": "longitude_latitude"}},
        "actors": [{"actor_id": "ZONE_A", "actor_color": [.08,.75,.85]}, {"actor_id": "ZONE_B", "actor_color": [.95,.36,.10]}],
        "control_states": [{"frame": f, "state_ref": f"SYNTHETIC_STATE_{f:03d}"} for f in range(total)],
        "frontline_geometries": {"mode": "DERIVED_FROM_THIS_FRAME_OWNER_BOUNDARIES", "standalone_input": False},
        "event_location": {"coordinates": [106.5,18.0], "source_ref": "SYNTHETIC_ZONE_PARTITION_RECIPE_V2", "qualification": "SYNTHETIC_ONLY"},
        "camera": {"profile_id": "NATIVE_V5_SOURCE_CLOCK", "keyframes": [{"frame": row["frame"], "sourceFrame": row["sourceFrame"]} for row in native["cameraSchedule"]]},
        "transition": {"mode": "SOURCE_SAMPLED", "easing": "RECORDED_IN_SOURCE_SAMPLES"},
        "confidence": {"level": "SYNTHETIC_TEST_NOT_HISTORICAL_FACT", "provenance": "AUTHOR_GENERATED_EXPLICIT_FRAME_SAMPLES"},
        "visual_annotations": [], "audio_cue_slots": []}
    bundle = {"schema": "WORLD_ENGINE_PINNED_SOURCE_BUNDLE_V2", "mode": "SYNTHETIC_TEST", "scene": scene, "states": states,
        "native": native_binding, "blockers": [], "full_control_area_status": "SYNTHETIC_DOMAIN_PARTITION_ONLY",
        "geographic_registration": {"status": "SOURCE_MODERN_GIS_IDENTITY_ONLY", "historicalAccuracyClaimed": False}}
    bundle_binding = put(root, "demo/BUNDLE.json", bundle)
    put(root, "INDEX.json", {"schema": "WORLD_ENGINE_SERVER_SOURCE_PACKAGES_V2", "packages": {"synthetic_zones_v2": bundle_binding}})
    put(HERE, "fixtures/DEMO_SOURCE_SCENE.json", scene)
    print(json.dumps({"root": str(root), "sourceIndexSHA256": contract.sha((root/"INDEX.json").read_bytes()), "frames":total}))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--native",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    build(args.native,args.output)
