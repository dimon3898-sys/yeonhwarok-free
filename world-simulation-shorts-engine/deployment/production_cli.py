#!/usr/bin/env python3
"""Small production CLI over preserved planning, approval and render contracts.

Planning never approves or renders. Rendering only submits an authenticated
background request to the separately running mobile wrapper. Export performs
read-only completed-evidence/media checks before creating an exclusive folder.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from fractions import Fraction
import hashlib
from http.cookiejar import CookieJar
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib import error, parse, request as http

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from engine.storage import EngineError, ProjectStore
from tools.deliverable_evidence import (CHUNK, EvidenceError, inside_file,
                                       load_completed_version, sha256)

PRODUCTION_SHORTS = "PRODUCTION_SHORTS"
PROFILE = PRODUCTION_SHORTS
DEFAULT_STATE_ROOT = APP_ROOT / "deployment" / "runtime"
PACE_CHOICES = ("FAST_PLUS", "FASTPLUS", "FAST", "NORMAL", "CINEMATIC")
PROJECT_PATTERN = r"project_[a-z0-9_]{6,64}"
VERSION_PATTERN = r"v\d{3,}"


class CLIError(RuntimeError):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details

    def as_dict(self):
        return {"code": self.code, "message": self.message, "details": self.details}


def production_request(topic, duration, *, quality="HIGH", pace="FAST_PLUS",
                       tts=False, subtitles=False, bgm=True, sfx=True):
    """Bounded defaults; source certification remains the engine's authority."""
    pace = "FAST_PLUS" if pace.upper() == "FASTPLUS" else pace.upper()
    return {"topic": topic, "duration": duration, "quality": quality,
            "production_preset": "PRODUCTION_DEFAULT", "pace": pace,
            "tts": tts, "subtitles": subtitles, "bgm": bgm, "sfx": sfx}


def _store(args):
    from deployment.mobile_server import checked_state_root
    from deployment.security import SecurityError
    try:
        root = checked_state_root(Path(args.state_root).expanduser())
    except SecurityError as exc:
        raise CLIError(exc.code, exc.message) from None
    return ProjectStore(root / "projects")


def _ids(project, version):
    if not re.fullmatch(PROJECT_PATTERN, project or ""):
        raise CLIError("INVALID_PROJECT", "잘못된 프로젝트 ID입니다.")
    if version is not None and not re.fullmatch(VERSION_PATTERN, version):
        raise CLIError("INVALID_VERSION", "잘못된 버전입니다.")


def _version_path(store, project, version=None):
    _ids(project, version)
    path = store.version_path(project, version).resolve()
    if not path.is_relative_to(store.root) or path.parent.parent.name != project:
        raise CLIError("PROJECT_PATH_ESCAPE", "프로젝트 저장 범위를 벗어난 경로입니다.")
    return path


def _plan_summary(plan):
    story = plan.get("story", {})
    lines = [f"{PROFILE} · {plan['duration']:g}초",
             f"훅: {story.get('hook', '')}"]
    for scene in plan["scenes"]:
        kinds = ", ".join(e["kind"] for e in scene["visual_events"] if e.get("meaningful", True))
        lines.append(f"{scene['scene_id']} {scene['start_time']:g}–"
                     f"{scene['start_time'] + scene['duration']:g}s · "
                     f"{scene['location']} · {kinds}")
    lines.append("검수: " + ("PASS" if plan["gate"]["passed"] else "BLOCKED"))
    return "\n".join(lines)


def plan_command(args):
    from engine.planner import generate_plan
    raw = production_request(args.topic, args.duration, quality=args.quality,
                             pace=args.pace, tts=args.tts, subtitles=args.subtitles,
                             bgm=args.bgm, sfx=args.sfx)
    plan = generate_plan(raw)
    record = _store(args).create(deepcopy(raw), deepcopy(plan))
    saved = record["plan"]
    version = _version_path(_store(args), record["project"]["id"], record["version"])
    return {"profile": PROFILE, "project_id": saved["project_id"],
            "version": saved["version"], "plan_hash": saved["plan_hash"],
            "gate_passed": saved["gate"]["passed"], "errors": saved["gate"]["errors"],
            "readable_plan": _plan_summary(saved),
            "scene_plan": str(version / "scene_plan.json"),
            "scene_plan_readable": str(version / "scene_plan_readable.md"),
            "approval_created": False, "render_started": False}


def status_command(args):
    store = _store(args)
    _version_path(store, args.project, args.version)
    return {"project_id": args.project, **store.status(args.project, args.version)}


def approve_command(args):
    if not re.fullmatch(r"[a-f0-9]{64}", args.plan_hash or ""):
        raise CLIError("EXACT_PLAN_HASH_REQUIRED", "현재 계획의 정확한 SHA-256 해시가 필요합니다.")
    store = _store(args)
    _version_path(store, args.project, args.version)
    state = store.approve(args.project, args.version, args.plan_hash)
    return {"project_id": args.project, "version": args.version,
            "plan_hash": args.plan_hash, "status": state["status"],
            "render_started": False}


def _access_password(path):
    try:
        with Path(path).expanduser().open("rb") as stream:
            data = stream.read(65537)
        if len(data) > 65536:
            raise ValueError("too large")
        text = data.decode("utf-8")
        if text.lstrip().startswith("{"):
            value = json.loads(text)
            password = value.get("password") if isinstance(value, dict) else None
        else:
            password = text.rstrip("\r\n")
        if not isinstance(password, str) or not password.strip():
            raise ValueError("missing password")
        return password
    except (OSError, ValueError, UnicodeError):
        raise CLIError("INVALID_ACCESS_FILE", "인증 파일은 비어 있지 않은 비밀번호 또는 password JSON이어야 합니다.") from None


def _base_url(value):
    try:
        url = parse.urlsplit(value)
        url.port
    except ValueError:
        raise CLIError("INVALID_BASE_URL", "유효한 HTTP(S) base URL이 필요합니다.") from None
    if url.scheme not in {"http", "https"} or not url.hostname or url.username is not None or url.password is not None or url.query or url.fragment:
        raise CLIError("INVALID_BASE_URL", "인증 정보 없는 HTTP(S) base URL이 필요합니다.")
    try:
        local = url.hostname.lower() == "localhost" or ipaddress.ip_address(url.hostname).is_loopback
    except ValueError:
        local = url.hostname.lower() == "localhost"
    if url.scheme == "http" and not local:
        raise CLIError("HTTPS_REQUIRED", "외부 호스트 인증에는 HTTPS를 사용하세요. 로컬 HTTP는 허용됩니다.")
    return value.rstrip("/")


class _NoRedirect(http.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the submitted password or authenticated job to a redirect.
        return None


def render_command(args):
    _ids(args.project, args.version)
    base = _base_url(args.base)
    password = _access_password(args.access_file)
    jar = CookieJar()
    opener = http.build_opener(http.HTTPCookieProcessor(jar), _NoRedirect())
    origin_parts = parse.urlsplit(base)
    origin = parse.urlunsplit((origin_parts.scheme, origin_parts.netloc, "", "", ""))

    def post(path, payload, *, auth=False):
        req = http.Request(base + path, data=json.dumps(payload).encode(),
                           headers={"Content-Type": "application/json", "Accept": "application/json", "Origin": origin},
                           method="POST")
        try:
            with opener.open(req, timeout=30) as response:
                status = response.status
                body = response.read(1048577)
            if len(body) > 1048576:
                raise ValueError("response too large")
            value = json.loads(body)
            if not isinstance(value, dict):
                raise ValueError("object required")
            return status, value
        except error.HTTPError as exc:
            exc.close()
            raise CLIError("MOBILE_AUTH_FAILED" if auth else "RENDER_REQUEST_REJECTED",
                           "인증에 실패했습니다." if auth else "렌더 요청이 거부되었습니다.",
                           {"http_status": exc.code}) from None
        except (error.URLError, OSError, ValueError):
            raise CLIError("MOBILE_AUTH_UNAVAILABLE" if auth else "RENDER_REQUEST_UNAVAILABLE",
                           "모바일 서버 응답을 확인할 수 없습니다.") from None

    status, login = post("/auth/login", {"password": password}, auth=True)
    if status != 200 or login.get("authenticated") is not True or not any(cookie.name == "world_owner_session" for cookie in jar):
        raise CLIError("MOBILE_AUTH_FAILED", "인증 세션을 확인할 수 없습니다.")
    status, result = post("/api/projects/" + args.project + "/render", {"version": args.version})
    if status != 202:
        raise CLIError("RENDER_NOT_ACCEPTED", "백그라운드 렌더 접수를 확인할 수 없습니다.", {"http_status": status})
    # Only bounded public job identifiers are returned. Passwords/cookies/server
    # response bodies are never printed, persisted, or copied into an export.
    job = result.get("job", result)
    job = job if isinstance(job, dict) else {}
    safe = lambda value: value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value) and value != password else None
    return {"accepted": True, "http_status": 202, "project_id": args.project,
            "version": args.version, "job_id": safe(job.get("id", job.get("job_id"))),
            "status": safe(job.get("status", result.get("status"))) or "accepted",
            "waited_for_render": False, "credentials_written": False}


def probe_video(path):
    """Metadata only; no encoding, frame render, or new media is started."""
    try:
        completed = subprocess.run(["ffprobe", "-v", "error", "-show_streams",
                                    "-show_format", "-of", "json", str(path)],
                                   check=True, capture_output=True, timeout=20)
        return json.loads(completed.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        raise CLIError("MEDIA_PROBE_FAILED", "완성 영상의 실제 미디어 규격을 확인할 수 없습니다.") from None


def _verify_media(path, duration, quality, *, muted=False, audio_required=False):
    from engine.backends import quality_settings
    settings = quality_settings(quality)
    meta = probe_video(path)
    try:
        video = next(row for row in meta["streams"] if row.get("codec_type") == "video")
        fps = float(Fraction(video["avg_frame_rate"]))
        seconds = float(meta["format"]["duration"])
        if (video.get("codec_name") != "h264" or video.get("pix_fmt") != "yuv420p"
            or video.get("width") != settings["output_width"] or video.get("height") != settings["output_height"]
            or not math.isfinite(fps) or abs(fps - settings["fps"]) > .001
            or not math.isfinite(seconds) or abs(seconds - float(duration)) > .075):
            raise ValueError("video mismatch")
        audio = any(row.get("codec_type") == "audio" for row in meta["streams"])
        if (muted and audio) or (audio_required and not audio):
            raise ValueError("audio mismatch")
    except (KeyError, StopIteration, ValueError, ZeroDivisionError, TypeError):
        raise CLIError("MEDIA_SPEC_MISMATCH", "실제 코덱·크기·FPS·길이·오디오가 저장된 렌더 설정과 다릅니다.") from None
    return {"codec": "h264", "width": video["width"], "height": video["height"],
            "fps": fps, "duration": seconds, "audio": audio,
            "preview_only": settings["preview_only"]}


def export_command(args):
    store = _store(args)
    version = _version_path(store, args.project, args.version)
    destination = Path(args.destination).expanduser().absolute()
    if ".." in Path(args.destination).parts:
        raise CLIError("INVALID_EXPORT_DESTINATION", "상위 경로 이동이 없는 명시적인 새 폴더를 지정하세요.")
    target = destination.resolve()
    if os.path.lexists(destination):
        raise CLIError("OUTPUT_EXISTS_PRESERVED", "기존 내보내기 경로는 보존합니다. 새 폴더를 지정하세요.")
    if target.is_relative_to(store.root) or target.is_relative_to(version.parent.parent):
        raise CLIError("EXPORT_MUST_NOT_WRITE_IN_PROJECTS", "프로젝트 저장 범위 밖의 새 내보내기 폴더가 필요합니다.")
    # Every failure check runs before mkdir/copy. The preserved recovery result
    # paths and recorded hashes, not guessed first-attempt paths, are authoritative.
    completed = load_completed_version(version)
    plan, result = completed["plan"], completed["result"]
    entries = []

    def add(source, name):
        path = inside_file(version, source)
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise CLIError("INVALID_EXPORT_MEMBER", "내보내기 파일 경로가 잘못되었습니다.")
        entries.append({"file": name, "source": str(path), "bytes": path.stat().st_size, "sha256": sha256(path)})

    for name in ("scene_plan.json", "scene_plan_readable.md", "script.txt"):
        add(name, name)
    add(completed["final_paths"]["final"], "final.mp4")
    add(completed["final_paths"]["muted"], "final_muted.mp4")
    add(completed["qc_md"], "qc_report.md")
    add(completed["qc_json"], "qc_report.json")
    add(result["outputs"]["source_report"], "source_report.md")
    add("assets/source_report.json", "source_report.json")
    add(result["outputs"]["contact_sheet"], "contact_sheet.png")
    add("renders/scene_results.json", "scene_results.json")
    quality = plan.get("options", {}).get("quality", plan.get("request", {}).get("quality", "HIGH"))
    options = {**plan.get("request", {}), **plan.get("options", {})}
    media = {"final": _verify_media(completed["final_paths"]["final"], plan["duration"], quality,
                                   audio_required=any(options.get(k, False) for k in ("tts", "bgm", "sfx"))),
             "muted": _verify_media(completed["final_paths"]["muted"], plan["duration"], quality, muted=True)}
    ids = [scene["scene_id"] for scene in plan["scenes"]]
    if len(set(ids)) != len(ids) or not all(re.fullmatch(r"S\d{3,}", sid) for sid in ids):
        raise CLIError("INVALID_SCENE_IDS", "장면 식별자가 중복되거나 잘못되었습니다.")
    for scene, entry in zip(plan["scenes"], result["scenes"]):
        sid = scene["scene_id"]
        try:
            scene_document = json.loads(inside_file(version, "scene_json/" + sid + ".json").read_text())
        except (ValueError, UnicodeError):
            raise CLIError("SCENE_JSON_MISMATCH", "저장된 장면 JSON을 확인할 수 없습니다.") from None
        if scene_document != scene:
            raise CLIError("SCENE_JSON_MISMATCH", "장면 JSON이 승인된 Scene Plan과 다릅니다.")
        add(entry["movie"], "scenes/" + sid + ".mp4")
        add(entry["audit"], "scenes/" + sid + ".audit.json")
        add("scene_json/" + sid + ".json", "scene_json/" + sid + ".json")
        scene_quality = entry.get("quality", {})
        if not isinstance(scene_quality, dict):
            scene_quality = {}
        _verify_media(inside_file(version, entry["movie"]), scene["duration"],
                      scene_quality.get("quality", scene.get("render_quality", quality)), muted=True)
    # Nothing from approval/auth/runtime/upload/texture/cache directories is
    # discovered recursively. Only this explicit validated inventory is copied.
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    for item in entries:
        out = destination / item["file"]
        out.parent.mkdir(parents=True, exist_ok=True)
        digest, count = hashlib.sha256(), 0
        with Path(item["source"]).open("rb") as source, out.open("xb") as target_stream:
            for block in iter(lambda: source.read(CHUNK), b""):
                target_stream.write(block)
                digest.update(block)
                count += len(block)
        if digest.hexdigest() != item["sha256"] or count != item["bytes"]:
            raise CLIError("SOURCE_CHANGED_DURING_EXPORT", "복사 중 원본이 바뀌었습니다. 새 미완성 폴더를 보존합니다.")
    manifest = {"schema_version": 1, "profile": PROFILE, "project_id": plan["project_id"],
                "version": plan["version"], "plan_hash": completed["plan_hash"],
                "automatic_qc_passed": True, "media": media,
                "publication_quality": result.get("publication_quality", False),
                "aesthetic_review_required": result.get("aesthetic_review_required", True),
                "files": [{k: v for k, v in item.items() if k != "source"} for item in entries],
                "auth_files_included": False, "private_assets_included": False,
                "partial_or_cache_files_included": False}
    with (destination / "EXPORT_MANIFEST.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return {"destination": str(destination), "project_id": plan["project_id"],
            "version": plan["version"], "plan_hash": completed["plan_hash"],
            "file_count": len(entries), "automatic_qc_passed": True, "media": media,
            "aesthetic_review_required": manifest["aesthetic_review_required"],
            "auth_files_included": False, "render_started": False}


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE_ROOT,
                        help="Wrapper state directory; projects are stored in its projects/ child.")
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="Generate and save a reviewable plan; never approve/render.")
    plan.add_argument("--topic", required=True)
    plan.add_argument("--duration", required=True, type=float)
    plan.add_argument("--quality", choices=("FAST", "HIGH", "CINEMA"), default="HIGH")
    plan.add_argument("--pace", choices=PACE_CHOICES, default="FAST_PLUS")
    plan.add_argument("--tts", action="store_true")
    plan.add_argument("--subtitles", action="store_true")
    plan.add_argument("--no-bgm", dest="bgm", action="store_false", default=True)
    plan.add_argument("--no-sfx", dest="sfx", action="store_false", default=True)
    plan.set_defaults(handler=plan_command)
    for name, handler in (("status", status_command), ("approve", approve_command), ("export", export_command)):
        command = commands.add_parser(name)
        command.add_argument("--project", required=True)
        command.add_argument("--version", required=name != "status")
        if name == "approve":
            command.add_argument("--plan-hash", required=True)
        if name == "export":
            command.add_argument("--destination", type=Path, required=True)
        command.set_defaults(handler=handler)
    render = commands.add_parser("render", help="Authenticate and submit a background render; do not wait.")
    render.add_argument("--base", required=True)
    render.add_argument("--access-file", type=Path, required=True)
    render.add_argument("--project", required=True)
    render.add_argument("--version", required=True)
    render.set_defaults(handler=render_command)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = args.handler(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("gate_passed", True) else 2
    except (CLIError, EngineError) as exc:
        print(json.dumps({"error": exc.as_dict()}, ensure_ascii=False, indent=2))
        return 2
    except EvidenceError as exc:
        print(json.dumps({"error": {"code": "EXPORT_EVIDENCE_FAILED", "message": str(exc)}}, ensure_ascii=False, indent=2))
        return 2
    except ValueError as exc:
        # Bounded planner errors retain required-plugin details and never fall
        # back to a cheaper, unsupported map or start a render.
        details = getattr(exc, "details", None)
        print(json.dumps({"error": {"code": getattr(exc, "code", "PLANNING_INPUT_FAILED"),
                                    "message": str(exc), "details": details}}, ensure_ascii=False, indent=2))
        return 2
    except OSError:
        print(json.dumps({"error": {"code": "LOCAL_IO_FAILED", "message": "로컬 파일 작업에 실패했습니다. 기존 파일은 보존합니다."}}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
