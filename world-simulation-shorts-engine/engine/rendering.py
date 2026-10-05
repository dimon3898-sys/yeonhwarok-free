"""Approved, resumable independent-scene rendering using the preserved V3 engine."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode
import hashlib
import ast
import copy
import json
import shutil
import subprocess
import time
import textwrap
import numpy as np

from .assets import APP_ROOT, sha256_file, renderer_version, validate_assets, write_source_report, resolve_user_asset, validate_clip_requirements, asset_registry, project_renderer_version
from .audio import create_audio, create_subtitles, finish_video, _ass_time
from .backends import CPULocalBackend, quality_settings
from .qc import probe_video, run_qc, valid_scene_file
from .storage import atomic_json, canonical, plan_hash
from .presets import scene_render_mode
from .flat_subtitles import adapt_flat_subtitles


def legacy_clip_source_hash(current_source: str | None = None) -> str:
    """Retain old clip caches only for the byte-identical preserved clip code.

    The compatibility value is the SHA of an actual read-only pre-flat source
    file. Future changes to the clip function, referenced local helpers/constants
    or imported symbol bindings fall back to the current module's actual SHA.
    New, unrelated map dispatch cannot force an unchanged clip to rerender.
    """
    source = Path(__file__).read_text() if current_source is None else current_source
    current_digest = hashlib.sha256(source.encode()).hexdigest()
    preserved = Path(__file__).with_name('rendering_before_flat_preserved.py')
    try:
        original = preserved.read_text()
        old_tree, new_tree = ast.parse(original), ast.parse(source)
        def declarations(tree):
            result = {}
            bindings = {}
            for node in tree.body:
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                    result[node.name] = node
                elif isinstance(node,(ast.Assign,ast.AnnAssign)):
                    targets = node.targets if isinstance(node,ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target,ast.Name):result[target.id] = node
                elif isinstance(node,ast.Import):
                    for alias in node.names:bindings[alias.asname or alias.name.split('.')[0]] = ('import',alias.name)
                elif isinstance(node,ast.ImportFrom):
                    for alias in node.names:bindings[alias.asname or alias.name] = ('from',node.level,node.module,alias.name)
            return result,bindings
        old, old_bindings = declarations(old_tree)
        new, new_bindings = declarations(new_tree)
        pending, checked = ['_render_clip'], set()
        while pending:
            name=pending.pop()
            if name in checked:continue
            checked.add(name)
            if name not in old or name not in new:return current_digest
            if (ast.dump(old[name],include_attributes=False)!=ast.dump(new[name],include_attributes=False)
                    or ast.get_source_segment(original,old[name])!=ast.get_source_segment(source,new[name])):
                return current_digest
            references={node.id for node in ast.walk(old[name]) if isinstance(node,ast.Name) and isinstance(node.ctx,ast.Load)}
            for reference in references:
                if reference in old:pending.append(reference)
                if reference in old_bindings and old_bindings[reference]!=new_bindings.get(reference):return current_digest
        return sha256_file(preserved)
    except (OSError,SyntaxError,ValueError):
        return current_digest


def scene_cache_key(scene: dict, assets: dict, quality: dict, renderer: str, render_context: dict | None = None) -> str:
    visual_scene = copy.deepcopy(scene)
    if "render_time_offset" in visual_scene:
        # Modern scene deletion can retime assembly without changing a frame.
        # Its immutable shader clock and geographic/camera state remain hashed.
        visual_scene.pop("start_time", None)
        if visual_scene.get("era") in {None, "modern"} and visual_scene.get("year") is None and visual_scene.get("date") is None:
            visual_scene.pop("timeline_position", None)
            for field in ["entry_state", "exit_state"]:
                timeline = visual_scene.get(field, {}).get("timeline", {})
                if timeline.get("era") in {None, "modern"} and timeline.get("year") is None and timeline.get("date") is None:
                    timeline.pop("timeline_position", None)
        for event in visual_scene.get("visual_events", []):
            event.pop("caused_by", None)  # Plan causality metadata does not shade pixels.
    value = {"scene_json": visual_scene, "assets": {a["id"]: a["actual_sha256"] for a in assets["assets"]},
             "renderer_version": renderer, "quality_preset": quality}
    if render_context is not None:
        value["scene_render_context"] = render_context
    if scene.get("scene_type") == "CINEMATIC_CLIP":
        clip = scene.get("cinematic_clip", scene.get("clip", {}))
        path = resolve_user_asset(clip.get("path", scene.get("clip_path", "")))
        if path.is_file():
            value["external_clip_sha256"] = sha256_file(path)
        value["clip_renderer_version"] = legacy_clip_source_hash()
    return hashlib.sha256(canonical(value)).hexdigest()


def _copy_new(source: Path, destination: Path) -> None:
    if destination.exists():
        if sha256_file(source) != sha256_file(destination):
            raise FileExistsError(f"Conflicting existing preserved result: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Independent copies avoid later accidental mutation of a hard-linked cache.
    with source.open("rb") as original, destination.open("xb") as target:
        shutil.copyfileobj(original, target, 1024*1024)


def _next_attempt(directory: Path, stem: str) -> Path:
    candidate = directory / (stem + ".mp4")
    attempt = 1
    while any(candidate.with_suffix(suffix).exists() for suffix in [".mp4", ".audit.json", ".checkpoint.json", ".manifest.json",
                                                                   ".clip_base.mp4", ".clip_annotations.ass", ".clip_annotation_proof.json", ".clip_ffmpeg.log"]):
        attempt += 1
        candidate = directory / (stem + f"_attempt{attempt:03}.mp4")
    return candidate


def _cached_scene(cache: Path, duration: float, settings: dict) -> dict | None:
    candidates = [cache, *sorted(cache.parent.glob(cache.name+"_recovery_*"), reverse=True)]
    for candidate in candidates:
        manifest = candidate / "cache.json"
        if not manifest.is_file():
            continue
        try:
            entry = json.loads(manifest.read_text())
            movie, audit = candidate / "scene.mp4", candidate / "scene.audit.json"
            if (entry.get("complete") is True and movie.is_file() and audit.is_file()
                    and sha256_file(movie) == entry["video_sha256"]
                    and sha256_file(audit) == entry["audit_sha256"]
                    and valid_scene_file(movie, duration, settings["output_width"], settings["output_height"], settings["fps"])):
                return {**entry, "movie": str(movie), "audit": str(audit)}
        except (ValueError, KeyError, OSError):
            pass
    return None


def _render_clip(scene: dict, output: Path, audit_path: Path, settings: dict, plan: dict | None = None) -> dict:
    clip = scene.get("cinematic_clip", scene.get("clip", {}))
    source = resolve_user_asset(clip.get("path", scene.get("clip_path", "")))
    if not clip.get("license") and not clip.get("user_owned"):
        raise RuntimeError("CLIP_LICENSE_REQUIRED")
    requirements = validate_clip_requirements(scene, {source["id"] for source in plan.get("sources", [])} if plan else None,
                                               {claim["id"]: claim["status"] for claim in plan.get("story", {}).get("claims", [])} if plan else None)
    if not requirements["passed"]:
        raise RuntimeError("CLIP_REQUIREMENT_FAILED: " + json.dumps(requirements["errors"], ensure_ascii=False))
    duration, start = float(scene["duration"]), float(clip.get("trim_start", 0))
    meta = probe_video(source)
    if start < 0 or start+duration > float(meta["format"]["duration"])+.03:
        raise RuntimeError("CLIP_TOO_SHORT: choose a longer clip or shorten Scene; no artificial freeze filling")
    width, height = settings["output_width"], settings["output_height"]
    filters = [f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos",
               f"crop={width}:{height}", f"fps={settings['fps']}", "setsar=1", "format=yuv420p"]
    transition = scene.get("transition_in", "MATCH_CUT")
    if isinstance(transition, dict):
        transition = transition.get("type", "MATCH_CUT")
    transition = str(transition).upper()
    # A match cut keeps the full image readable. The optional atmospheric entry
    # exposes a short graded haze, rather than mislabeling a plain fade as a zoom.
    if transition in {"ATMOSPHERIC", "ATMOSPHERIC_TRANSITION"}:
        filters.append("eq=brightness='0.035*max(0,1-t/0.32)':contrast=1.03:eval=frame")
    elif transition in {"MOTION_BLUR", "MOTION_BLUR_TRANSITION"}:
        filters.append("gblur=sigma=0.65:enable='lt(t,0.16)'")
    elif transition in {"ZOOM", "ZOOM_TRANSITION"}:
        filters.append(f"zoompan=z='1.025-0.025*min(on/{max(1, round(.32*settings['fps']))},1)':"
                       f"x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={width}x{height}:fps={settings['fps']}")
    elif transition not in {"MATCH_CUT", "MATCH", "NONE", "CUT", "ATMOSPHERIC_PASS", "CAMERA_CONTINUITY"}:
        raise RuntimeError("UNSUPPORTED_CLIP_TRANSITION: " + transition)
    annotations = sorted(requirements["annotations"], key=lambda item: item["time"])
    first = scene.get("start_time") == 0
    hook = scene.get("hook") or (plan or {}).get("story", {}).get("hook") if first else None
    overlays = []
    for index, annotation in enumerate(annotations):
        end = min(duration, float(annotation["time"])+float(annotation["duration"]))
        if index+1 < len(annotations):
            end = min(end, float(annotations[index+1]["time"]))
        if end-float(annotation["time"]) <= .10:
            raise RuntimeError("CLIP_ANNOTATION_TOO_SHORT_OR_OVERLAPPING")
        overlays.append({**annotation, "end": end, "kind": next(event["kind"] for event in scene["visual_events"]
                                                                if event["id"] == annotation["event_id"]), "style": "Information"})
    if hook:
        overlays.append({"event_id": None, "time": 0., "end": min(3., duration), "text": hook,
                         "kind": "hook_reveal", "style": "Hook"})
    base = output.with_suffix(".clip_base.mp4") if overlays else output
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-ss", str(start), "-i", str(source),
               "-t", str(duration), "-vf", ",".join(filters), "-an", "-c:v", "libx264", "-preset", "slow",
               "-crf", "15", "-threads", "4", "-color_range", "tv", "-color_primaries", "bt709",
               "-color_trc", "bt709", "-colorspace", "bt709", "-movflags", "+faststart", str(base)]
    begin = time.monotonic()
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("CINEMATIC_CLIP_FAILED: " + result.stderr[-2000:])
    proof = None
    if overlays:
        ass = output.with_suffix(".clip_annotations.ass")
        lines = ["[Script Info]", "ScriptType: v4.00+", "PlayResX: 1080", "PlayResY: 1920", "WrapStyle: 0", "",
                 "[V4+ Styles]", "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
                 "Style: Information,Noto Sans CJK KR,42,&H00EDEDEC,&H000000FF,&H60081018,&H90081018,0,0,0,0,100,100,0.4,0,1,2,0,7,150,160,520,1",
                 "Style: Hook,Noto Sans CJK KR,54,&H00EDEDEC,&H000000FF,&H60081018,&H90081018,0,0,0,0,100,100,0.4,0,1,2,0,7,150,160,205,1", "",
                 "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
        for annotation in overlays:
            text = str(annotation["text"]).replace("{", "").replace("}", "").replace("\\", "/")
            korean = any("\uac00" <= character <= "\ud7a3" for character in text)
            wrapped = textwrap.wrap(text, width=25 if korean else 37)
            if len(wrapped) > 3:
                raise RuntimeError("CLIP_ANNOTATION_EXCEEDS_MOBILE_SAFE_LINES")
            caption = r"\N".join(wrapped)
            lines.append(f"Dialogue: 0,{_ass_time(annotation['time'])},{_ass_time(annotation['end'])},"
                         f"{annotation['style']},,0,0,0,,{{\\fad(90,100)}}{caption}")
        with ass.open("x", encoding="utf-8") as stream:
            stream.write("\n".join(lines)+"\n")
        escape = lambda value: str(value).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        filt = f"ass=filename='{escape(ass)}':fontsdir='{escape(APP_ROOT / 'web/fonts')}'"
        encoded = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "info", "-n", "-i", str(base),
                                  "-vf", filt, "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "15",
                                  "-threads", "4", "-pix_fmt", "yuv420p", "-color_range", "tv", "-color_primaries", "bt709",
                                  "-color_trc", "bt709", "-colorspace", "bt709", "-movflags", "+faststart", str(output)],
                                 capture_output=True, text=True)
        selected_fonts = [line.strip() for line in encoded.stderr.splitlines() if "fontselect:" in line]
        with output.with_suffix(".clip_ffmpeg.log").open("x", encoding="utf-8") as stream:
            stream.write(encoded.stderr)
        if encoded.returncode or not selected_fonts:
            raise RuntimeError("CLIP_ANNOTATION_FILTER_FAILED: " + encoded.stderr[-2000:])
        pixel_proofs = []
        for annotation in overlays:
            midpoint = (float(annotation["time"])+float(annotation["end"]))/2
            images = []
            for movie in [base, output]:
                decoded = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(midpoint),
                                          "-i", str(movie), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                         capture_output=True)
                if decoded.returncode or len(decoded.stdout) != width*height*3:
                    raise RuntimeError("CLIP_ANNOTATION_FRAME_PROOF_FAILED")
                images.append(np.frombuffer(decoded.stdout, np.uint8).reshape(height, width, 3).astype(np.int16))
            # Text occupies the known safe overlay region. Comparing the encoded
            # base/final at the same timestamp verifies an actual picture change,
            # in addition to successful libass filter execution and font loading.
            top, bottom = (.095, .235) if annotation["style"] == "Hook" else (.255, .425)
            roi = np.abs(images[1]-images[0])[round(height*top):round(height*bottom), round(width*.12):round(width*.88)]
            changed = int((roi.max(axis=2)>32).sum())
            if changed < (25 if width < 1080 else 100):
                raise RuntimeError("CLIP_ANNOTATION_NOT_VISIBLE_IN_ENCODED_PICTURE")
            pixel_proofs.append({"event_id": annotation["event_id"], "time": midpoint,
                                 "safe_roi_pixels_changed_above_32": changed, "passed": True})
        proof = {"ass_sha256": sha256_file(ass), "base_video_sha256": sha256_file(base),
                 "encoded_video_sha256": sha256_file(output), "font_selection": selected_fonts,
                 "ffmpeg_log": str(output.with_suffix(".clip_ffmpeg.log")),
                 "pixel_proofs": pixel_proofs, "scope": "Executed libass information overlays and encoded-frame differences; not inferred physical events"}
        atomic_json(output.with_suffix(".clip_annotation_proof.json"), proof, exclusive=True)
    audits = [{"t": i/settings["fps"], "scene_id": scene["scene_id"], "source_type": "EXTERNAL_CLIP",
               "textClipped": [], "webglError": 0, "clip_source": str(source),
               "transition": transition, "external_clip": True, "labels": [], "meaningfulEventsRendered": []}
              for i in range(round(duration*settings["fps"]))]
    for audit in audits:
        for annotation in overlays:
            local = audit["t"]
            opacity = max(0., min(1., (local-float(annotation["time"]))/ .09, (float(annotation["end"])-local)/.10))
            if opacity <= .1:
                continue
            audit["labels"].append({"text": annotation["text"], "kind": annotation["kind"], "opacity": opacity,
                                    "event_id": annotation["event_id"]})
            if annotation["event_id"]:
                audit["meaningfulEventsRendered"].append({"event_id": annotation["event_id"], "kind": annotation["kind"],
                                                          "rendered_primitive": "clip_information", "visible": True,
                                                          "actual_time": local, "scheduled_time": annotation["time"],
                                                          "text": annotation["text"], "opacity": opacity,
                                                          "source_ids": annotation["source_ids"], "fact_status": annotation["fact_status"],
                                                          "evidence": "executed_ass_filter_and_encoded_frame_comparison"})
    atomic_json(audit_path, audits, exclusive=True)
    return {"complete": True, "source_type": "EXTERNAL_CLIP", "source_sha256": sha256_file(source),
            "elapsedSeconds": time.monotonic()-begin, "transition": transition,
            "annotation_proof": proof,
            "color_matching": "BT.709 normalization; source luminance/camera match still requires visual review"}


def _concat(scenes: list[Path], destination: Path, settings: dict) -> None:
    if destination.exists():
        raise FileExistsError(destination)
    listing = destination.with_suffix(".concat.txt")
    with listing.open("x", encoding="utf-8") as stream:
        for movie in scenes:
            # Concat's single-quoted file argument has its own escape convention.
            escaped = str(movie.resolve()).replace("'", "'\\''")
            stream.write(f"file '{escaped}'\n")
    result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-f", "concat", "-safe", "0",
                             "-i", str(listing), "-map", "0:v:0", "-c:v", "copy", "-an",
                             "-movflags", "+faststart", str(destination)], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError("SCENE_ASSEMBLY_FAILED: " + result.stderr[-2000:])


def render_project(project_dir: Path, plan: dict, base_url: str, progress=None,
                   scene_filter: list[str] | None = None) -> dict:
    """Render an approved immutable version; cached unchanged scenes are reused.

    project_dir is projects/PROJECT/versions/VERSION, not the project parent.
    Root jobs provide a progress callback and durable UI status updates.
    """
    project_dir = Path(project_dir).resolve()
    progress = progress or (lambda record: None)
    started = time.monotonic()
    from .schema import validate_plan
    validation = validate_plan(plan)
    if not validation["passed"]:
        raise RuntimeError("PLAN_GATE_FAILED: " + json.dumps(validation["errors"], ensure_ascii=False))
    approval_path = project_dir / "approval.json"
    if not approval_path.is_file():
        raise RuntimeError("APPROVAL_REQUIRED")
    approval = json.loads(approval_path.read_text())
    if (approval.get("user_approval") is not True or approval.get("plan_hash") != plan_hash(plan)
            or plan.get("plan_hash") != plan_hash(plan)):
        raise RuntimeError("PLAN_CHANGED_AFTER_APPROVAL")
    immutable_plan = project_dir / "scene_plan.json"
    if not immutable_plan.is_file() or plan_hash(json.loads(immutable_plan.read_text())) != plan_hash(plan):
        raise RuntimeError("SCENE_PLAN_STORAGE_MISMATCH")
    previous_result = project_dir / "renders/project_result.json"
    if previous_result.is_file():
        result = json.loads(previous_result.read_text())
        if result.get("qc", {}).get("passed"):
            for name in ["final", "muted"]:
                path = Path(result["outputs"][name])
                if not path.is_file() or sha256_file(path) != result.get("final_sha256", {}).get(name):
                    raise RuntimeError("FINAL_RESULT_CHANGED_OR_MISSING: " + name)
            progress({"stage": "complete", "message": "Existing approved final reused", "reused_final": True})
            return {**result, "reused_final": True}
        raise RuntimeError("EXISTING_FINAL_FAILED_QC: preserve this version and approve a corrected new version")
    assets = validate_assets(plan)
    if not assets["passed"]:
        raise RuntimeError("ASSET_RESOLUTION_FAILED: " + json.dumps(assets["errors"]))
    progress({"stage": "asset_resolution", "message": "GIS plan and preserved V3 asset SHA/license checks passed"})
    if plan.get("options", {}).get("quality", "HIGH").upper() != "FAST":
        for scene in plan["scenes"]:
            quality = scene.get("render_quality", "HIGH")
            if isinstance(quality, dict):
                quality = quality.get("preset", quality.get("mode", "HIGH"))
            if str(quality).upper() == "FAST":
                raise RuntimeError("FAST_SCENE_IN_PUBLICATION_PLAN: use an all-FAST preview or HIGH/CINEMA publication scenes")
    directories = {name: project_dir / name for name in ["renders", "audio", "qc", "final", "assets", "previews", "scene_json"]}
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)
    source_report_path = directories["assets"] / "source_report.json"
    source_report = json.loads(source_report_path.read_text()) if source_report_path.is_file() else write_source_report(directories["assets"], plan, assets)
    # TTS duration is measured before expensive graphics work, so an overlong
    # script cannot waste a complete render. The final audio order remains exact.
    audio_started = time.monotonic()
    audio_file = directories["audio"] / "audio_report.json"
    if audio_file.is_file():
        audio = json.loads(audio_file.read_text())
        if not Path(audio["file"]).is_file():
            raise RuntimeError("AUDIO_CHECKPOINT_MISSING: preserve failed version and regenerate in a new one")
        audio_reused = True
    else:
        progress({"stage": "narration_preflight", "message": "Measuring optional narration and preparing exact sound-event timeline"})
        audio = create_audio(plan, directories["audio"])
        audio_reused = False
    subtitle_manifest = directories["audio"] / "subtitle_report.json"
    if subtitle_manifest.is_file():
        subtitles = json.loads(subtitle_manifest.read_text())
    else:
        subtitles = create_subtitles(plan, directories["audio"], audio.get("narration_cues", []))
        atomic_json(subtitle_manifest, subtitles, exclusive=True)
    audio_seconds = time.monotonic()-audio_started
    renderer = project_renderer_version(plan)
    backend = CPULocalBackend()
    selected = set(scene_filter) if scene_filter is not None else None
    ids = {scene["scene_id"] for scene in plan["scenes"]}
    if selected is not None and not selected.issubset(ids):
        raise RuntimeError("UNKNOWN_SCENE_FILTER")
    cache_root = APP_ROOT / "cache/scenes"
    cache_root.mkdir(parents=True, exist_ok=True)
    entries, movies, audits = [], [], []
    checkpoint = directories["renders"] / "checkpoint.json"
    manifest_path = directories["renders"] / "scene_results.json"
    existing = {}
    if manifest_path.is_file():
        for entry in json.loads(manifest_path.read_text()).get("scenes", []):
            existing[entry["scene_id"]] = entry
    total = len(plan["scenes"])
    render_seconds = 0.
    for index, scene in enumerate(plan["scenes"]):
        sid = scene["scene_id"]
        quality = scene.get("render_quality", plan.get("options", {}).get("quality", "HIGH"))
        if isinstance(quality, dict):
            quality = quality.get("preset", quality.get("mode", "HIGH"))
        # Mixed FAST/publication scenes would make stream-copy assembly resize
        # abruptly; previews therefore use FAST consistently across all scenes.
        if plan.get("options", {}).get("quality", "HIGH").upper() == "FAST":
            quality = "FAST"
        settings = quality_settings(str(quality), scene)
        context = dict(plan.get("render_context", {}))
        if not context and not scene.get("lighting", {}).get("sun_coordinates"):
            context["lighting_anchor"] = plan["scenes"][0]["coordinates"]
            context["hero_anchor"] = next((s["coordinates"] for s in plan["scenes"] if s.get("lighting_preset") == "HERO"),
                                          plan["scenes"][0]["coordinates"])
        context["is_opening_scene"] = scene["start_time"] == 0
        if context["is_opening_scene"]:
            context["opening_hook"] = (scene.get("hook") or plan.get("story_plan", {}).get("hook") or
                                       plan.get("story", {}).get("hook") or plan.get("hook"))
        mode = scene_render_mode(scene)
        scene_renderer = renderer_version(scene)
        scene_assets = assets
        if mode == 'MASTER_V3_EARTH':
            # A mixed project may resolve derived flat tiles too. They must never
            # invalidate the cache of an unchanged Earth scene.
            original_ids = {item['id'] for item in asset_registry()}
            scene_assets = {**assets, 'assets': [item for item in assets['assets'] if item['id'] in original_ids]}
        key = scene_cache_key(scene, scene_assets, settings, scene_renderer, context)
        cache = cache_root / key
        hit = _cached_scene(cache, scene["duration"], settings)
        scene_dir = directories["renders"] / sid
        scene_dir.mkdir(parents=True, exist_ok=True)
        stem = f"scene_{sid}_{plan['version']}"
        saved = existing.get(sid)
        if saved and saved.get("cache_key") == key and Path(saved["movie"]).is_file() and Path(saved["audit"]).is_file():
            if (sha256_file(Path(saved["movie"])) == saved["video_sha256"] and
                    sha256_file(Path(saved["audit"])) == saved["audit_sha256"] and
                    valid_scene_file(Path(saved["movie"]), scene["duration"], settings["output_width"], settings["output_height"], settings["fps"])):
                entry = {**saved, "reused": True, "reuse_reason": "version_checkpoint"}
                movies.append(Path(entry["movie"]))
                audits.append(Path(entry["audit"]))
                entries.append(entry)
                progress({"stage": "scene_cache", "scene_id": sid, "completed": index+1, "total": total,
                          "message": "Completed scene checkpoint reused"})
                continue
        if hit:
            output = _next_attempt(scene_dir, stem)
            audit_path = output.with_suffix(".audit.json")
            _copy_new(Path(hit["movie"]), output)
            _copy_new(Path(hit["audit"]), audit_path)
            entry = {**hit, "scene_id": sid, "cache_key": key, "movie": str(output), "audit": str(audit_path),
                     "reused": True, "reuse_reason": "scene_hash_asset_renderer_quality_cache", "current_render_seconds": 0.,
                     "cached_render_scene_json_sha256": hit.get("scene_json_sha256"),
                     "scene_json_sha256": hashlib.sha256(canonical(scene)).hexdigest(), "render_context": context}
            atomic_json(output.with_suffix(".reuse.json"), {"cache_key": key, "renderer_version": scene_renderer,
                         "current_scene_json_sha256": entry["scene_json_sha256"],
                         "cached_render_scene_json_sha256": entry["cached_render_scene_json_sha256"],
                         "cached_video_sha256": hit["video_sha256"], "cached_audit_sha256": hit["audit_sha256"],
                         "normalization": "Only modern assembly time/timeline and causal metadata excluded when an immutable render_time_offset is present",
                         "render_context": context}, exclusive=True)
            progress({"stage": "scene_cache", "scene_id": sid, "completed": index+1, "total": total,
                      "message": "Unchanged scene reused without rendering"})
        else:
            if selected is not None and sid not in selected:
                raise RuntimeError(f"UNCHANGED_SCENE_CACHE_MISSING: {sid}; initial render or resume is required before partial rerender")
            output = _next_attempt(scene_dir, stem)
            audit_path = output.with_suffix(".audit.json")
            scene_json = directories["scene_json"] / (sid + ".json")
            if not scene_json.is_file():
                atomic_json(scene_json, scene, exclusive=True)
            progress({"stage": "scene_start", "scene_id": sid, "completed": index, "total": total,
                      "message": f"Rendering Scene {index+1}/{total}; {quality}; {mode}"})
            atomic_json(checkpoint, {"complete": False, "scene_id": sid, "completed_scenes": len(entries),
                                     "total_scenes": total, "scene_cache_key": key, "partial_video": str(output),
                                     "plan_hash": plan["plan_hash"]})
            scene_started = time.monotonic()
            if scene["scene_type"] == "CINEMATIC_CLIP":
                native_manifest = _render_clip(scene, output, audit_path, settings, plan)
            else:
                query = urlencode({"project": plan["project_id"], "version": plan["version"], "scene": sid})
                earth_handoff = mode == 'MASTER_V3_EARTH' and any(scene.get(k) in {'FLAT_TO_EARTH','EARTH_TO_FLAT'} for k in ['transition_in','transition_out'])
                page_name = 'render_flat.html' if mode == 'FLAT_MAP_PREMIUM' else 'render_transition.html' if earth_handoff else 'render.html'
                tool_name = 'render_flat_scene.mjs' if mode == 'FLAT_MAP_PREMIUM' else 'render_transition_scene.mjs' if earth_handoff else 'render_scene.mjs'
                url = base_url.rstrip("/") + '/' + page_name + '?' + query
                command = ["node", str(APP_ROOT / "tools" / tool_name), "--url", url,
                           "--output", str(output), "--audit", str(audit_path),
                           "--scene-json", str(scene_json), "--width", str(settings["internal_width"]),
                           "--height", str(round(settings["internal_width"]*16/9)),
                           "--output-width", str(settings["output_width"]), "--output-height", str(settings["output_height"]),
                           "--fps", str(settings["fps"]), "--duration", str(scene["duration"]), "--quality", settings["quality"],
                           "--samples", str(settings.get("temporal_samples", 1))]
                backend.run(command, APP_ROOT, lambda value: progress({**value, "scene_id": sid, "total_scenes": total,
                                                                       "scene_index": index+1}))
                native_manifest = json.loads(output.with_suffix(".manifest.json").read_text())
            seconds = time.monotonic()-scene_started
            render_seconds += seconds
            if not valid_scene_file(output, scene["duration"], settings["output_width"], settings["output_height"], settings["fps"]):
                raise RuntimeError("SCENE_MEDIA_METADATA_FAILED: " + sid)
            audit_records = json.loads(audit_path.read_text())
            if len(audit_records) != round(scene["duration"]*settings["fps"]):
                raise RuntimeError("SCENE_AUDIT_FRAME_COUNT_FAILED: " + sid)
            if any(record.get("webglError") or record.get("textClipped") for record in audit_records):
                raise RuntimeError("SCENE_RENDER_AUDIT_FAILED: " + sid)
            entry = {"scene_id": sid, "cache_key": key, "complete": True, "quality": settings,
                     "movie": str(output), "audit": str(audit_path), "renderer_version": scene_renderer, "render_mode": mode,
                     "video_sha256": sha256_file(output), "audit_sha256": sha256_file(audit_path),
                     "elapsed_seconds": seconds, "current_render_seconds": seconds, "reused": False,
                     "scene_json_sha256": hashlib.sha256(canonical(scene)).hexdigest(), "render_context": context,
                     "native_manifest": native_manifest}
            if cache.exists() and any(cache.iterdir()):
                # Corrupt cache is retained for diagnosis, never overwritten.
                cache = cache_root / (key + "_recovery_" + str(time.time_ns()))
            cache.mkdir(parents=True, exist_ok=True)
            _copy_new(output, cache / "scene.mp4")
            _copy_new(audit_path, cache / "scene.audit.json")
            atomic_json(cache / "cache.json", entry, exclusive=True)
        movies.append(Path(entry["movie"]))
        audits.append(Path(entry["audit"]))
        entries.append(entry)
        atomic_json(manifest_path, {"plan_hash": plan["plan_hash"], "renderer_version": renderer, "scenes": entries})
        atomic_json(checkpoint, {"complete": False, "completed_scenes": len(entries), "total_scenes": total,
                                 "plan_hash": plan["plan_hash"], "last_completed_scene": sid})
    # Post-draw map labels/entities/focus boxes decide caption placement. OFF and
    # old Earth plans are exact pass-throughs, keeping their original ASS files.
    subtitles = adapt_flat_subtitles(plan, subtitles, audits, directories['audio'])
    progress({"stage": "scene_assembly", "completed": total, "total": total, "message": "Assembling validated independent scenes"})
    assembly_started = time.monotonic()
    assembled = directories["renders"] / "assembled_muted.mp4"
    expected = entries[0]["quality"]
    if assembled.is_file() and not valid_scene_file(assembled, plan["duration"], expected["output_width"], expected["output_height"], expected["fps"]):
        assembled = _next_attempt(directories["renders"], "assembled_muted")
    if not assembled.is_file():
        _concat(movies, assembled, entries[0]["quality"])
    if not valid_scene_file(assembled, plan["duration"], expected["output_width"], expected["output_height"], expected["fps"]):
        raise RuntimeError("ASSEMBLY_METADATA_FAILED")
    final_dir = directories["final"]
    complete_final = all(valid_scene_file(final_dir / name, plan["duration"], expected["output_width"],
                                          expected["output_height"], expected["fps"])
                         for name in ["final.mp4", "final_muted.mp4"])
    if complete_final:
        # An interrupted QC stage may resume decoding these immutable finals.
        outputs = {"final": str(directories["final"] / "final.mp4"),
                   "muted": str(directories["final"] / "final_muted.mp4"), "subtitles": subtitles}
    else:
        if any((final_dir / name).exists() for name in ["final.mp4", "final_muted.mp4"]):
            index = 2
            while (final_dir / f"attempt{index:03}").exists():
                index += 1
            final_dir = final_dir / f"attempt{index:03}"
        outputs = finish_video(assembled, final_dir, plan, audio, subtitles)
    assembly_seconds = time.monotonic()-assembly_started
    progress({"stage": "automatic_qc", "message": "Decoding every final frame and auditing geography, motion, sound and retention"})
    qc_started = time.monotonic()
    qc_dir = directories["qc"]
    qc_file = qc_dir / "qc_report.json"
    if not qc_file.is_file() and any((qc_dir / name).exists() for name in ["contact_sheet.png", "qc_report.md"]):
        index = 2
        while (qc_dir / f"attempt{index:03}").exists():
            index += 1
        qc_dir = qc_dir / f"attempt{index:03}"
        qc_dir.mkdir()
    qc = json.loads(qc_file.read_text()) if qc_file.is_file() else run_qc(Path(outputs["final"]), plan, audits, qc_dir, subtitles=subtitles)
    qc_seconds = time.monotonic()-qc_started
    metrics = {"scene_render_seconds": render_seconds, "scene_count": total,
               "rendered_scene_count": sum(not entry.get("reused", False) for entry in entries),
               "cached_scene_count": sum(entry.get("reused", False) for entry in entries),
               "audio_preparation_seconds": audio_seconds, "audio_reused": audio_reused,
               "assembly_audio_mux_subtitles_seconds": assembly_seconds, "qc_seconds": qc_seconds,
               "total_seconds": time.monotonic()-started, "measured": True, "backend": "CPU_LOCAL",
               "benchmark_scope": "This version's actual execution only; cached prior rendering time is not included"}
    outputs.update({"qc_report": str(qc_dir / "qc_report.md"),
                    "contact_sheet": str(qc_dir / "contact_sheet.png"),
                    "source_report": str(directories["assets"] / "source_report.md"),
                    "scene_plan": str(immutable_plan), "scene_plan_readable": str(project_dir / "scene_plan_readable.md"),
                    "script": str(project_dir / "script.txt")})
    result = {"outputs": outputs, "metrics": metrics, "qc": qc, "scenes": entries,
              "assets": source_report, "plan_hash": plan["plan_hash"], "renderer_version": renderer,
              "final_sha256": {name: sha256_file(Path(outputs[name])) for name in ["final", "muted"]},
              "aesthetic_review_required": True, "publication_quality": qc.get("publication_quality", False)}
    atomic_json(previous_result, result, exclusive=True)
    atomic_json(checkpoint, {"complete": qc["passed"], "plan_hash": plan["plan_hash"],
                             "completed_scenes": total, "total_scenes": total, "metrics": metrics,
                             "qc_passed": qc["passed"]})
    if not qc["passed"]:
        raise RuntimeError("FINAL_QC_FAILED: " + ", ".join(qc["failures"]))
    progress({"stage": "complete", "completed": total, "total": total,
              "message": "Final MP4 and muted version passed automatic QC; full visual playback review remains required"})
    return result


class RenderManager:
    render_project = staticmethod(render_project)
