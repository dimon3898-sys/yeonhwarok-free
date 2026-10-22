"""Author bounded nonhistorical probe sources through unchanged CPU providers.

No renderer, material, coastline, historical control area or old fixture is
modified. Each field is persisted with real SHA receipts before compilation.
The recovery material owner must separately admit a real sourceStyle descriptor;
this output alone does not grant pixel capture or a Studio render.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]
ENGINE = HERE.parents[1]
REPO = HERE.parents[2]
OLD = HERE.parent / "universal-source-pipeline-v2"
spec = importlib.util.spec_from_file_location("_recovery_probe_control", HERE.parent / "studio-integration-gates-v1/control_provider.py")
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def put(root, relative, value):
    file = root / relative
    file.parent.mkdir(parents=True, exist_ok=True)
    if file.exists():
        raise ValueError("GENERIC_PROBE_REFUSE_OVERWRITE")
    raw = canonical(value)
    file.write_bytes(raw)
    return {"path": relative, "sha256": sha(raw), "bytes": len(raw)}


def points(value):
    if isinstance(value, list) and len(value) == 2 and all(type(v) in (int, float) for v in value):
        return [value]
    return [point for item in value for point in points(item)]


def extent(geometry):
    values = points(geometry["coordinates"])
    return [min(v[0] for v in values), min(v[1] for v in values), max(v[0] for v in values), max(v[1] for v in values)]


def author_grid_domain(primary):
    """The grid is an explicit synthetic observation region, not a coastline."""
    modern = {"type": primary["geometry_type"], "coordinates": primary["coordinates"]}
    control.validate_area_geometries([modern])
    west, south, east, north = extent(modern)
    step = .25
    with control._Geos() as geos:
        land = geos.geometry(modern)
        combined = None
        cells = 0
        for ix in range(math.floor(west / step), math.ceil(east / step)):
            for iy in range(math.floor(south / step), math.ceil(north / step)):
                x, y = ix * step, iy * step
                cell = geos.geometry({"type": "Polygon", "coordinates": [[[x, y], [x+step, y], [x+step, y+step], [x, y+step], [x, y]]]})
                if geos.area(geos.operation("difference", cell, land)) == 0:
                    combined = cell if combined is None else geos.operation("union", combined, cell)
                    cells += 1
        if combined is None:
            raise ValueError("GENERIC_PROBE_NO_LAND_CONTAINED_GRID")
        union = geos.json(combined)
        polygons = [union["coordinates"]] if union["type"] == "Polygon" else union["coordinates"]
        chosen = max(polygons, key=lambda p: geos.area(geos.geometry({"type": "Polygon", "coordinates": p})))
        result = {"type": "Polygon", "coordinates": chosen}
        if geos.area(geos.operation("difference", geos.geometry(result), land)) != 0:
            raise ValueError("GENERIC_PROBE_DOMAIN_OUTSIDE_MODERN_SOURCE")
    control.validate_area_geometries([result])
    return result, cells


def prepare_native(seed, config, source_frames):
    """Invoke the immutable preparer and actual V5 evaluator; no new camera math."""
    bridge = r"""
import {prepareNative} from './world-simulation-shorts-engine/recovery/universal-source-pipeline-v2/tools/prepare_native.mjs';
import {evaluateMinimumContextCameraFrame} from './world-simulation-shorts-engine/web/map_infographic_v1/camera_director_v5.mjs';
import {readFileSync} from 'node:fs';
const input=JSON.parse(readFileSync(0,'utf8'));
const native=await prepareNative({seedPlanFile:input.seed,config:input.config});
native.probeOriginalScheduleFrames=[0,90,179].map(frame=>native.cameraSchedule[frame]);
native.cameraSchedule=input.sourceFrames.map((sourceFrame,frame)=>({frame,sourceFrame,
 clockDirection:frame===0?'FORWARD':frame===1?'HOLD':'REVERSE',
 flatBounds:evaluateMinimumContextCameraFrame(native.cameraPlan,sourceFrame).camera.flatBounds}));
process.stdout.write(JSON.stringify(native));
"""
    result = subprocess.run(["node", "--input-type=module", "-e", bridge], cwd=REPO,
        input=canonical({"seed": str(seed), "config": config, "sourceFrames": source_frames}), capture_output=True, timeout=60)
    if result.returncode:
        raise ValueError("GENERIC_PROBE_NATIVE_PREPARE_FAILED:" + result.stderr.decode(errors="replace")[-1000:])
    return json.loads(result.stdout)


def build_case(config, native, root):
    primary = next(g for g in native["nativePlan"]["geometries"] if g["id"] == native["nativePlan"]["primary"])
    domain, cells = author_grid_domain(primary)
    domain_binding = put(root, "DOMAIN.geojson", domain)
    bounds = extent(domain)
    recipe = {"schema": "GENERIC_SYNTHETIC_PROBE_RECIPE_V1", "purpose": "NONHISTORICAL_TECHNICAL_PROBE_ONLY",
        "modernDomainSource": {k: primary[k] for k in ("id", "source_id", "source_version", "source_file_sha256")},
        "domainQualification": "AUTHORED_0.25_DEGREE_GRID_INSIDE_MODERN_LAND_LARGEST_CONNECTED_PART_NOT_ACTUAL_CONTROL_OR_COASTLINE",
        "candidateCells": cells, "sourceSamples": [0, 90, 179], "localFrames": [0, 1, 2],
        "fractions": [.70, .50, .30], "frontAmplitudeDegrees": .20,
        "license": "CC0-1.0 authored synthetic observation zones; Natural Earth modern GIS Public Domain",
        "historicalEventClaimed": False}
    recipe_binding = put(root, "RECIPE.json", recipe)
    states, compiled = [], []
    with control._Geos() as geos:
        base = geos.geometry(domain)
        west, south, east, north = bounds
        for frame, fraction in enumerate(recipe["fractions"]):
            y = south + (north-south)*fraction
            xs = [west-1+(east-west+2)*i/12 for i in range(13)]
            front = [[x, y+.20*math.sin(i*1.25)] for i, x in enumerate(xs)]
            low = {"type": "Polygon", "coordinates": [[[west-1, south-1], [east+1, south-1], *reversed(front), [west-1, south-1]]]}
            high = {"type": "Polygon", "coordinates": [[*front, [east+1, north+1], [west-1, north+1], front[0]]]}
            owners = [geos.json(geos.operation("intersection", base, geos.geometry(value))) for value in (low, high)]
            folder = root / f"samples/{frame:03d}"
            sample_recipe = put(folder, "RECIPE.json", recipe)
            sample_domain = put(folder, "DOMAIN.geojson", domain)
            receipts, owner_rows = [], []
            for actor, geometry in zip(("ZONE_A", "ZONE_B"), owners):
                binding = put(folder, actor+".geojson", geometry)
                receipts.append({"id": actor, "sourcePath": "RECIPE.json", "sourceSHA256": sample_recipe["sha256"],
                    "sourceURL": "urn:world-engine:authored-generic-recovery-probe", "geometryPath": actor+".geojson",
                    "geometryFileSHA256": binding["sha256"], "geometrySHA256": sha(canonical(geometry)),
                    "qualification": "SYNTHETIC_TEST", "asOfDate": "2000-01-01", "timeQualifier": "DATE_ONLY",
                    "factions": [actor], "crs": "EPSG:4326", "license": recipe["license"], "licenseStatus": "REVIEWED_FOR_THIS_GEOMETRY"})
                owner_rows.append({"factionId": actor, "geometry": geometry, "sourceRef": actor})
            receipts.append({"id": "DOMAIN", "sourcePath": "RECIPE.json", "sourceSHA256": sample_recipe["sha256"],
                "sourceURL": "urn:world-engine:authored-generic-recovery-probe", "geometryPath": "DOMAIN.geojson",
                "geometryFileSHA256": sample_domain["sha256"], "geometrySHA256": sha(canonical(domain)),
                "qualification": "SYNTHETIC_TEST", "asOfDate": "2000-01-01", "timeQualifier": "DATE_ONLY",
                "factions": [], "crs": "EPSG:4326", "license": recipe["license"], "licenseStatus": "REVIEWED_FOR_THIS_GEOMETRY"})
            receipt_binding = put(folder, "RECEIPTS.json", {"schema": control.RECEIPT_SCHEMA, "mode": "SYNTHETIC_TEST", "receipts": receipts})
            state = {"schema": control.SCHEMA, "mode": "SYNTHETIC_TEST", "stateId": config["id"]+f"_PROBE_{frame}",
                "frame": frame, "asOfDate": "2000-01-01", "timeQualifier": "DATE_ONLY", "bbox": bounds, "crs": "EPSG:4326",
                "classification": "schematic", "factions": ["ZONE_A", "ZONE_B"], "domain": {"geometry": domain, "sourceRef": "DOMAIN"},
                "ownerMasks": owner_rows, "unknownMasks": [], "contestedMasks": []}
            put(folder, "STATE.json", state)
            registry = control.SourceRegistry.from_manifest(folder/"RECEIPTS.json", expected_sha256=receipt_binding["sha256"], mode="SYNTHETIC_TEST")
            field = control.compile_control_state(state, registry)
            if not field.source_binding_valid() or not field["completeExplicitDomainPartition"] or not field["sharedFront"]["geometry"]["coordinates"]:
                raise ValueError("GENERIC_PROBE_EXACT_CONTROL_PARTITION_REQUIRED")
            states.append({"frame": frame, "state": f"samples/{frame:03d}/STATE.json", "receipts": f"samples/{frame:03d}/RECEIPTS.json"})
            compiled.append(dict(field))
    payload = {**{k: native[k] for k in ("nativePlan", "cameraPlan", "cameraSchedule", "sourceBindings")},
        "frames": compiled, "actors": [{"actor_id": "ZONE_A", "actor_color": [.08, .75, .85]}, {"actor_id": "ZONE_B", "actor_color": [.95, .36, .10]}],
        "eventLocation": deepcopy(config["event_location"]), "profile": {}, "annotations": []}
    binding = put(root, "RUNTIME.json", payload)
    manifest = {"schema": "WORLD_ENGINE_GENERIC_RECOVERY_PROBE_SOURCE_V1", "id": config["id"],
        "terrainCondition": config["terrain_condition"], "classification": "SYNTHETIC_TECHNICAL_PROBE_NOT_HISTORY",
        "frameCount": 3, "localFrameRange": [0, 3], "sourceSamples": [0, 90, 179], "cameraSourceFrames": [0, 54, 0],
        "runtime": binding, "recipe": recipe_binding, "domain": domain_binding, "states": states,
        "sourceGeometryUnchanged": True, "materialStyleAdmitted": False, "rendererExecuted": False,
        "historicalG3Allowed": False, "nvidiaVerified": False}
    put(root, "PROBE_MANIFEST.json", manifest)
    return manifest


def build(output, *, seed=None):
    output = Path(output)
    if output.exists():
        raise ValueError("GENERIC_PROBE_OUTPUT_MUST_BE_NEW")
    document = json.loads((HERE/"fixtures/GENERIC_PROBE_CONFIGS.json").read_bytes())
    if document["sourceFrames"] != [0, 54, 0] or len(document["cases"]) != 2:
        raise ValueError("GENERIC_PROBE_REGISTERED_CASES_REQUIRED")
    seed = Path(seed or "/workspace/exact-65422-capsule-20261020/world-simulation-shorts-engine/recovery/reference-reproduction-v1/fixtures/REGIONAL-plan.json")
    defaults = json.loads((OLD/"fixtures/NATIVE_DEMO_CONFIG.json").read_bytes())
    output.mkdir(parents=True)
    cases = []
    for item in document["cases"]:
        config = {k: deepcopy(item[k]) for k in ("primary_id", "event_location", "final_bounds", "start_bounds")}
        config.update(total_frames=180, fps=30, camera_profile=defaults["camera_profile"])
        native = prepare_native(seed, config, document["sourceFrames"])
        cases.append(build_case(item, native, output/item["id"]))
    manifest = {"schema": "WORLD_ENGINE_GENERIC_PROBE_SET_V1", "qualification": document["qualification"],
        "cases": cases, "materialsAndActualPixelsPending": True, "historicalG3Allowed": False}
    put(output, "PROBES.json", manifest)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser();parser.add_argument("--output", type=Path, required=True);parser.add_argument("--seed", type=Path)
    args = parser.parse_args();result = build(args.output, seed=args.seed)
    print(json.dumps({"output": str(args.output), "cases": [v["id"] for v in result["cases"]], "sourceFrames": 6, "rendererExecuted": False}))
