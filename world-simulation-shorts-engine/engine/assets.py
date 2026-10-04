"""Resolve the preserved V3 library and produce verifiable source records."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import hashlib
import json

APP_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = APP_ROOT.parent
V3_ROOT = REPOSITORY_ROOT / "cinematic-world-map"

CLIP_INFORMATIONAL_EVENTS = {
    "city_reveal", "country_reveal", "destination_preview", "region_reveal", "distance_reveal",
    "comparison_reveal", "milestone_reveal", "new_variable", "consequence_reveal", "response",
    "route_choice", "alternate_route_reveal", "connection_reveal", "escalation", "peak_reveal", "final_reveal",
}


def validate_clip_requirements(scene: dict, known_source_ids: set[str] | None = None,
                               claim_statuses: dict[str, str] | None = None) -> dict:
    """Require actual source-backed information overlays; never invent clip physics."""
    from .retention import MEANINGFUL
    if scene.get("scene_type") != "CINEMATIC_CLIP":
        return {"passed": True, "errors": [], "annotations": []}
    clip = scene.get("cinematic_clip", scene.get("clip", {}))
    annotations = clip.get("annotations", [])
    events = {event["id"]: event for event in scene.get("visual_events", [])
              if isinstance(event, dict) and event.get("meaningful", True) and event.get("kind") in MEANINGFUL}
    errors = []
    if not isinstance(annotations, list):
        return {"passed": False, "errors": [{"code": "CLIP_ANNOTATIONS_INVALID", "scene_id": scene["scene_id"]}], "annotations": []}
    seen = set()
    for annotation in annotations:
        if not isinstance(annotation, dict):
            errors.append({"code": "CLIP_ANNOTATION_INVALID", "scene_id": scene["scene_id"]})
            continue
        eid = annotation.get("event_id")
        event = events.get(eid)
        if eid in seen or event is None:
            errors.append({"code": "UNKNOWN_OR_DUPLICATE_CLIP_ANNOTATION", "event_id": eid})
            continue
        seen.add(eid)
        if event["kind"] not in CLIP_INFORMATIONAL_EVENTS:
            errors.append({"code": "UNSUPPORTED_CLIP_SEMANTIC_EVENT", "event_id": eid, "kind": event["kind"],
                           "message": "A physical map event requires actual route/entity/arrival evidence; select a compatible information scene or explicitly revise its events before approval"})
        try:
            start, length = float(annotation["time"]), float(annotation["duration"])
            valid_time = abs(start-float(event["time"])) < .001 and 0 <= start < scene["duration"] and length > .10
        except (KeyError, TypeError, ValueError):
            valid_time = False
        if not valid_time:
            errors.append({"code": "CLIP_ANNOTATION_TIMING_MISMATCH", "event_id": eid})
        if not str(annotation.get("text", "")).strip() or len(str(annotation.get("text", ""))) > 180:
            errors.append({"code": "CLIP_ANNOTATION_TEXT_INVALID", "event_id": eid})
        status = annotation.get("fact_status")
        if status not in {"FACT", "ASSUMPTION", "SIMULATION"}:
            errors.append({"code": "CLIP_ANNOTATION_FACT_STATUS_REQUIRED", "event_id": eid})
        claim_ids = annotation.get("claim_ids") or ([annotation["claim_id"]] if annotation.get("claim_id") else [])
        if claim_statuses is not None:
            if (not claim_ids or any(cid not in claim_statuses or cid not in scene.get("claim_ids", []) for cid in claim_ids)
                    or event.get("claim_id") and event["claim_id"] not in claim_ids):
                errors.append({"code": "CLIP_ANNOTATION_CLAIM_BINDING_REQUIRED", "event_id": eid})
            else:
                statuses = {claim_statuses[cid] for cid in claim_ids}
                actual_status = "SIMULATION" if "SIMULATION" in statuses else "ASSUMPTION" if "ASSUMPTION" in statuses else "FACT"
                if status != actual_status:
                    errors.append({"code": "CLIP_FACT_SIMULATION_CONFUSION", "event_id": eid,
                                   "annotation_status": status, "claim_status": actual_status})
        elif event.get("fact_status") and status != event["fact_status"]:
            errors.append({"code": "CLIP_FACT_SIMULATION_CONFUSION", "event_id": eid})
        sources = annotation.get("source_ids", [])
        if not isinstance(sources, list) or not sources:
            errors.append({"code": "CLIP_ANNOTATION_SOURCE_REQUIRED", "event_id": eid})
        elif known_source_ids is not None and any(source not in known_source_ids for source in sources):
            errors.append({"code": "CLIP_ANNOTATION_UNKNOWN_SOURCE", "event_id": eid})
    for eid, event in events.items():
        if event["kind"] not in CLIP_INFORMATIONAL_EVENTS and not any(error.get("event_id") == eid for error in errors):
            errors.append({"code": "UNSUPPORTED_CLIP_SEMANTIC_EVENT", "event_id": eid, "kind": event["kind"]})
        elif eid not in seen:
            errors.append({"code": "CLIP_EVENT_ANNOTATION_REQUIRED", "event_id": eid, "kind": event["kind"]})
    return {"passed": not errors, "errors": errors, "annotations": annotations,
            "scope": "Informational overlays only; no unverified physical movement or arrival claims"}


def resolve_user_asset(value: str | Path) -> Path:
    """Web uploads and preserved library files are allowed; arbitrary server files are not."""
    path = Path(value).expanduser().resolve()
    if not any(path == root or root in path.parents for root in [APP_ROOT.resolve(), V3_ROOT.resolve()]):
        raise ValueError("ASSET_PATH_OUTSIDE_LIBRARY: upload the asset through the application first")
    if not path.is_file():
        raise ValueError("USER_ASSET_MISSING: " + str(path))
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@lru_cache(maxsize=64)
def _checked_hash(path: str, size: int, modified_ns: int) -> str:
    return sha256_file(Path(path))


def asset_registry() -> list[dict]:
    earth = json.loads((V3_ROOT / "assets/v3/earth/SOURCES_V3.json").read_text())
    registry = []
    for item in earth:
        if item.get("selected_for_final"):
            registry.append({**item, "id": Path(item["file"]).stem,
                             "author": item.get("credit", "Solar System Scope"),
                             "attribution_required": True,
                             "license_url": "https://creativecommons.org/licenses/by/4.0/",
                             "download_date": "2026-10-04 (preserved V3 source record)",
                             "path": str(V3_ROOT / item["file"])})
    source = json.loads((V3_ROOT / "assets/v3/fonts/SOURCE.json").read_text())
    registry.append({"id": "open-sans-light", "file": "assets/v3/fonts/OpenSans-Light.ttf",
                     "path": str(V3_ROOT / "assets/v3/fonts/OpenSans-Light.ttf"),
                     "sha256": source["sha256"], "license": source["license"],
                     "url": "https://github.com/googlefonts/opensans", "author": "Open Sans authors",
                     "attribution_required": True, "license_url": "https://www.apache.org/licenses/LICENSE-2.0",
                     "download_date": "2026-10-04 (preserved V3 source record)"})
    korean_font = APP_ROOT / "web/fonts/NotoSansCJKkr-Regular.otf"
    korean_source = APP_ROOT / "web/fonts/SOURCE.json"
    if korean_font.is_file() and korean_source.is_file():
        korean = json.loads(korean_source.read_text())
        registry.append({"id": "noto-sans-cjk-kr", "file": "web/fonts/NotoSansCJKkr-Regular.otf",
                         "path": str(korean_font), "sha256": korean["sha256"],
                         "license": korean["license"], "author": korean["author"],
                         "url": korean["source"], "attribution_required": korean.get("attribution_required", False),
                         "download_date": "2026-10-04 (extracted from preinstalled licensed font collection)"})
    gis = json.loads((V3_ROOT / "assets/SOURCES.json").read_text())
    for item in gis:
        if Path(item["file"]).name in {"earth-topology.png", "countries_50m.geojson", "coastlines_50m.geojson"}:
            registry.append({**item, "id": Path(item["file"]).stem,
                             "path": str(V3_ROOT / item["file"]),
                             "author": "Natural Earth" if "geojson" in item["file"] else "three-globe contributors",
                             "attribution_required": "MIT" in item["license"],
                             "download_date": "2026-10-04 (preserved source record)"})
    sound = V3_ROOT / "tools/sound.py"
    registry.append({"id": "original-procedural-sound", "file": "tools/sound.py", "path": str(sound),
                     "sha256": sha256_file(sound), "url": "Repository original tools/sound.py",
                     "author": "Cinematic World Map project", "license": "CC0-1.0",
                     "license_url": "https://creativecommons.org/publicdomain/zero/1.0/",
                     "attribution_required": False, "download_date": "Not downloaded; original synthesis"})
    return registry


def validate_assets(plan: dict | None = None) -> dict:
    checked, errors, external = [], [], []
    for asset in asset_registry():
        path = Path(asset["path"])
        if not path.is_file():
            errors.append({"id": asset["id"], "code": "MISSING_ASSET", "path": str(path)})
            continue
        stat = path.stat()
        digest = _checked_hash(str(path), stat.st_size, stat.st_mtime_ns)
        if digest != asset["sha256"]:
            errors.append({"id": asset["id"], "code": "ASSET_HASH_MISMATCH"})
        checked.append({**asset, "actual_sha256": digest, "bytes": stat.st_size})
    for scene in (plan or {}).get("scenes", []):
        if scene.get("scene_type") == "CINEMATIC_CLIP":
            clip = scene.get("cinematic_clip", scene.get("clip", {}))
            try:
                path = resolve_user_asset(clip.get("path", scene.get("clip_path", "")))
            except (OSError, ValueError) as error:
                errors.append({"scene_id": scene["scene_id"], "code": "MISSING_OR_UNSCOPED_CINEMATIC_CLIP", "message": str(error)})
                continue
            if not clip.get("license") and not clip.get("user_owned"):
                errors.append({"scene_id": scene["scene_id"], "code": "CLIP_LICENSE_REQUIRED"})
            else:
                external.append({"id": "clip-" + scene["scene_id"], "scene_id": scene["scene_id"], "path": str(path),
                                 "url": clip.get("source", "User-uploaded media"), "author": clip.get("author", "User declared owner"),
                                 "license": clip.get("license", "USER_OWNED"), "attribution_required": clip.get("attribution_required", False),
                                 "download_date": clip.get("download_date", "User-uploaded; upload metadata retained"),
                                 "actual_sha256": sha256_file(path), "bytes": path.stat().st_size})
            check = validate_clip_requirements(scene, {source["id"] for source in (plan or {}).get("sources", [])},
                                               {claim["id"]: claim["status"] for claim in (plan or {}).get("story", {}).get("claims", [])})
            errors.extend(check["errors"])
    options = (plan or {}).get("options", {})
    request = (plan or {}).get("request", {})
    narration = options.get("narration_file") or request.get("narration_audio")
    if narration:
        try:
            path = resolve_user_asset(narration)
            external.append({"id": "user-narration", "path": str(path), "url": "User-uploaded narration",
                             "author": "User declared owner", "license": "USER_PROVIDED", "attribution_required": False,
                             "download_date": "User-uploaded; upload metadata retained", "actual_sha256": sha256_file(path),
                             "bytes": path.stat().st_size})
        except (OSError, ValueError) as error:
            errors.append({"code": "NARRATION_ASSET_UNSCOPED", "message": str(error)})
    return {"passed": not errors, "assets": checked, "external_assets": external, "errors": errors}


def renderer_version() -> str:
    files = [V3_ROOT / "src/renderer_v3.js", V3_ROOT / "src/aircraft_v3.js",
             V3_ROOT / "src/core_v1_preserved.js", V3_ROOT / "src/engine_v3.js",
             APP_ROOT / "web/earth_adapter.js", APP_ROOT / "web/render.html",
             APP_ROOT / "tools/render_scene.mjs"]
    digest = hashlib.sha256()
    for file in files:
        if file.is_file():
            digest.update(str(file.relative_to(REPOSITORY_ROOT)).encode())
            digest.update(bytes.fromhex(sha256_file(file)))
    return digest.hexdigest()


def write_source_report(directory: Path, plan: dict, assets: dict | None = None) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    report = assets or validate_assets(plan)
    report = {**report, "geographic_sources": plan.get("sources", []),
              "claims": plan.get("story", {}).get("claims", []),
              "renderer_version": renderer_version(),
              "license_notice": "Earth day/night/cloud textures: Solar System Scope, CC BY 4.0. "
              "Modified by cinematic lighting, geographic overlays and camera rendering. "
              "NASA-derived imagery does not remove the texture author's CC BY attribution requirement."}
    json_file = directory / "source_report.json"
    with json_file.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    lines = ["# Source report", "", report["license_notice"], "", "## Shared asset library", ""]
    for asset in report["assets"] + report.get("external_assets", []):
        lines += [f"- **{asset['id']}** — {asset['author']}; {asset['license']}",
                  f"  Source: {asset.get('url', '')}", f"  SHA-256: `{asset['actual_sha256']}`",
                  f"  Download: {asset['download_date']}; attribution required: {asset['attribution_required']}"]
    lines += ["", "## Geographic sources", "", json.dumps(plan.get("sources", []), ensure_ascii=False, indent=2),
              "", "## Claim classifications", "", json.dumps(report["claims"], ensure_ascii=False, indent=2), ""]
    with (directory / "source_report.md").open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines))
    return report
