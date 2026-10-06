"""Prepare and verify an isolated short gCube QA project; never launches containers.

seed writes an unapproved twelve-second fixture into a new deployment runtime.
run checks the real HTTP gateway; --render explicitly approves/enqueues the
selected short plan once. No provider account, GPU or speedup is fabricated.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import build_opener, HTTPCookieProcessor, HTTPRedirectHandler, ProxyHandler, Request

APP = Path(__file__).resolve().parents[2]
if str(APP) in sys.path:
    sys.path.remove(str(APP))
sys.path.insert(0, str(APP))
SOURCE = Path(__file__).resolve().with_name("validation_scene_plan.json")
TOPIC = "서울에서 도쿄를 거쳐 타이베이로 이어지는 민간 항공 연결"
PROJECT = re.compile(r"project_[a-z0-9_]{6,64}")
VERSION = re.compile(r"v\d{3,}")


class ValidationError(Exception):
    """Only fixed diagnostic codes are emitted, never HTTP bodies or secrets."""


def require(condition, code):
    if not condition:
        raise ValidationError(code)


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save(path, data):
    path = Path(path)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(data, output, ensure_ascii=False, indent=2)
        output.write("\n")


def redact(value, password=None):
    if isinstance(value, str):
        for secret in (password, quote(password, safe="") if password else None):
            if secret:
                value = value.replace(secret, "[redacted]")
        return value
    if isinstance(value, list):
        return [redact(item, password) for item in value]
    if isinstance(value, dict):
        sensitive = {"password", "owner_password", "world_owner_password", "authorization", "cookie", "cookies", "token", "session_secret", "session_key"}
        return {key: "[redacted]" if key.lower() in sensitive else redact(item, password) for key, item in value.items()}
    return value


def seed(source_plan, state_root, output=None):
    from deployment.mobile_server import checked_state_root
    from engine.schema import validate_plan
    from engine.storage import ProjectStore
    source = Path(source_plan)
    require(source.is_file() and not source.is_symlink(), "SOURCE_PLAN_REQUIRED")
    before = sha(source)
    plan = json.loads(source.read_text(encoding="utf-8"))
    require(isinstance(plan, dict) and float(plan.get("duration", 0)) == 12
            and len(plan.get("scenes", [])) == 5, "CERTIFIED_TWELVE_SECOND_SOURCE_REQUIRED")
    require(not plan.get("metadata", {}).get("rhythm_sample_render_authorization"), "PARTIAL_OR_CACHE_ONLY_SOURCE_REJECTED")
    require(validate_plan(plan).get("passed") is True, "SOURCE_PLAN_GATE_FAILED")
    plan = deepcopy(plan)
    for field in ("project_id", "version", "plan_hash", "gate", "validation", "approval"):
        plan.pop(field, None)
    plan["request"].update(duration=12, quality="HIGH", tts=False, subtitles=False, bgm=True, sfx=True)
    plan["options"].update(quality="HIGH", tts=False, subtitles=False, bgm=True, sfx=True)
    metadata = plan.setdefault("metadata", {})
    metadata.pop("estimates", None)
    metadata["gcube_container_validation"] = {
        "scope": "New twelve-second deployment QA copy; five native Scenes are allowed.",
        "source_plan_sha256": before, "source_modified": False,
        "render_started": False, "gpu_speedup_claimed": False, "long_render_authorized": False,
    }
    require(validate_plan(plan).get("passed") is True, "QA_PLAN_GATE_FAILED")
    runtime = checked_state_root(state_root)
    store = ProjectStore(runtime / "projects")
    result = store.create(plan["request"], plan)
    require(result["plan"]["gate"]["passed"] is True, "STORED_QA_PLAN_GATE_FAILED")
    require(sha(source) == before, "SOURCE_PLAN_CHANGED")
    proof = {"schema_version": 1, "created_at_utc": utc(), "project_id": result["project"]["id"],
             "version": result["version"], "duration": result["plan"]["duration"],
             "scene_ids": [item["scene_id"] for item in result["plan"]["scenes"]],
             "plan_hash": result["plan"]["plan_hash"], "gate_passed": True,
             "source_plan_sha256": before, "source_bytes_unchanged": True,
             "approved": False, "render_started": False, "gpu_speedup_claimed": False}
    if output:
        save(output, proof)
    return proof


def private_password(path):
    path = Path(path)
    require(not path.is_symlink(), "UNSAFE_ACCESS_FILE")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "r", encoding="utf-8") as source:
        info = os.fstat(source.fileno())
        require(stat.S_ISREG(info.st_mode) and not stat.S_IMODE(info.st_mode) & 0o077
                and info.st_size <= 4096, "UNSAFE_ACCESS_FILE")
        raw = source.read().strip()
    value = json.loads(raw).get("password") if raw.startswith("{") else raw
    require(isinstance(value, str) and 16 <= len(value) <= 512, "INVALID_ACCESS_FILE")
    return value


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        return None


class Client:
    def __init__(self, base):
        parsed = urlsplit(base)
        require(parsed.scheme in {"http", "https"} and parsed.hostname and parsed.username is None
                and parsed.password is None and parsed.path in {"", "/"} and not parsed.query
                and not parsed.fragment, "INVALID_BASE_ORIGIN")
        require(parsed.scheme == "https" or parsed.hostname in {"localhost", "127.0.0.1"}, "HTTPS_REQUIRED")
        self.base = f"{parsed.scheme}://{parsed.netloc}"
        self.opener = build_opener(ProxyHandler({}), NoRedirects(), HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def open(self, method, route, data=None, headers=None):
        parsed = urlsplit(route)
        require(route.startswith("/") and not route.startswith("//") and not parsed.scheme
                and not parsed.netloc and not parsed.fragment and not any(part in {".", ".."} for part in parsed.path.split("/")), "INVALID_API_ROUTE")
        values = {"Accept": "application/json", **(headers or {})}
        body = None
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            values["Content-Type"] = "application/json"
        request = Request(self.base + route, data=body, method=method, headers=values)
        try:
            return self.opener.open(request, timeout=45)
        except HTTPError as response:
            return response

    def call(self, method, route, data=None, headers=None):
        with self.open(method, route, data, headers) as response:
            body = response.read(2 * 1024**2 + 1)
            require(len(body) <= 2 * 1024**2, "HTTP_BODY_TOO_LARGE")
            return response.status, {key.lower(): value for key, value in response.headers.items()}, body

    def json(self, method, route, data=None, *, expected=200, headers=None):
        status, _headers, body = self.call(method, route, data, headers)
        require(status == expected, f"HTTP_STATUS_UNEXPECTED_{status}")
        try:
            value = json.loads(body)
        except (ValueError, UnicodeError):
            raise ValidationError("INVALID_HTTP_JSON") from None
        require(isinstance(value, dict), "INVALID_HTTP_JSON")
        return value

    def login(self, password):
        value = self.json("POST", "/auth/login", {"password": password}, headers={"Origin": self.base})
        require(value.get("authenticated") is True, "LOGIN_FAILED")
        require(self.json("GET", "/auth/session").get("authenticated") is True, "SESSION_NOT_ESTABLISHED")


def run(base, access_file, output, *, project=None, version="v001", render=False, timeout=3600, poll=2):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    downloads = output / "downloads"
    downloads.mkdir()
    evidence = {"schema_version": 1, "started_at_utc": utc(), "base": None,
                "real_http": True, "real_browser": False, "physical_phone_tested": False,
                "container_started_by_this_runner": False, "provider_api_calls": 0,
                "secret_values_recorded": False, "gpu_speedup_claimed": False,
                "render_requested": False, "render_complete": False,
                "checks": [], "downloads": [], "failure": None}
    password = None
    try:
        client = Client(base)
        evidence["base"] = client.base
        password = private_password(access_file)
        for route, expected in (("/", 303), ("/auth/login", 200), ("/api/health", 200), ("/api/projects", 401)):
            status, _headers, _body = client.call("GET", route)
            require(status == expected, "UNAUTHENTICATED_ROUTE_POLICY_FAILED")
            evidence["checks"].append({"check": "unauthenticated_route", "route": route, "status": status})
        client.login(password)
        evidence["checks"].append({"check": "owner_login", "passed": True})
        for origin in (None, "https://foreign-origin.invalid"):
            headers = {"Origin": origin} if origin else {}
            status, _headers, _body = client.call("POST", "/api/projects", {}, headers)
            require(status == 403, "MUTATION_ORIGIN_POLICY_FAILED")
        status, _headers, body = client.call("GET", "/")
        require(status == 200 and b'id="brief-form"' in body and b"/static/app.js" in body, "AUTHENTICATED_UI_FAILED")
        evidence["checks"].append({"check": "authenticated_ui", "passed": True})
        health = client.json("GET", "/api/health")
        evidence["runtime_health"] = {key: health.get(key) for key in ("provider", "render_backend", "gpu", "storage", "limits")}
        request = {"topic": TOPIC, "duration": 20, "style": "긴장감 있는 세계 시뮬레이션",
                   "quality": "HIGH", "pace": "FAST_PLUS", "tts": False, "subtitles": False, "bgm": True, "sfx": True}
        started = time.monotonic()
        created = client.json("POST", "/api/projects", request, expected=201, headers={"Origin": client.base})
        require(created.get("plan", {}).get("gate", {}).get("passed") is True and created["plan"].get("plan_hash"), "NATURAL_LANGUAGE_PLAN_GATE_FAILED")
        planned_id = created.get("project", {}).get("id")
        require(PROJECT.fullmatch(planned_id or ""), "INVALID_PROJECT_ID")
        evidence["planning"] = {"project_id": planned_id, "duration": created["plan"]["duration"],
                                "plan_hash": created["plan"]["plan_hash"], "gate_passed": True,
                                "elapsed_seconds": time.monotonic() - started, "approved": False, "render_started": False}
        save(output / "unapproved_twenty_second_plan.json", redact(created["plan"], password))
        if not project:
            require(not render, "SHORT_QA_PROJECT_REQUIRED")
            evidence["passed"] = True
            evidence["validation_scope"] = "Authentication, origin policy, existing UI and natural-language planning only."
            return evidence
        require(PROJECT.fullmatch(project or "") and VERSION.fullmatch(version or ""), "INVALID_SELECTED_PROJECT")
        route = f"/api/projects/{project}"
        query = "?" + urlencode({"version": version})
        stored = client.json("GET", route + query)
        plan = stored.get("plan", {})
        require(float(plan.get("duration", 0)) == 12 and len(plan.get("scenes", [])) == 5
                and plan.get("gate", {}).get("passed") is True, "SELECTED_SHORT_PLAN_INVALID")
        plan_hash = plan.get("plan_hash")
        require(re.fullmatch(r"[a-f0-9]{64}", plan_hash or ""), "INVALID_PLAN_HASH")
        evidence.update(project_id=project, version=version, plan_hash=plan_hash, duration=plan["duration"])
        save(output / "selected_twelve_second_plan.json", redact(plan, password))
        status = client.json("GET", route + "/status" + query)
        if render:
            require(status.get("status") in {"planned", "approved", "failed", "interrupted"}, "SELECTED_JOB_ALREADY_ACTIVE_OR_COMPLETE")
            approved = client.json("POST", route + "/approve", {"version": version, "plan_hash": plan_hash}, headers={"Origin": client.base})
            require(approved.get("plan", {}).get("plan_hash") == plan_hash, "APPROVAL_HASH_CHANGED")
            job = client.json("POST", route + "/render", {"version": version}, expected=202, headers={"Origin": client.base})
            require(re.fullmatch(r"job_[a-f0-9]{12}", job.get("job_id", "")), "BACKGROUND_JOB_NOT_ESTABLISHED")
            evidence.update(render_requested=True, job_id=job["job_id"], enqueued_at_utc=utc())
        # A fresh cookie jar represents closing the client and returning later.
        client = Client(base)
        client.login(password)
        evidence["checks"].append({"check": "relogin_with_new_cookie_jar", "passed": True})
        restored = client.json("GET", route + query)
        require(restored.get("plan", {}).get("plan_hash") == plan_hash, "PLAN_NOT_RESTORED")
        status = client.json("GET", route + "/status" + query)
        if evidence.get("job_id"):
            require(status.get("job_id") == evidence["job_id"], "BACKGROUND_JOB_NOT_RESTORED")
        if not render and status.get("status") != "complete":
            evidence["passed"] = True
            evidence["validation_scope"] = "Owner reconnect and selected unrendered short-plan scaffolding only."
            evidence["observed_status"] = status.get("status")
            return evidence
        deadline = time.monotonic() + timeout
        observed = []
        evidence["observed_phases"] = observed
        while status.get("status") != "complete":
            value = status.get("status")
            progress = status.get("progress") if isinstance(status.get("progress"), dict) else {}
            evidence["last_status"] = {"status": value, "job_id": status.get("job_id"),
                                       "progress": {key: progress.get(key) for key in ("stage", "completed", "total", "completed_frames", "total_frames")}}
            error = status.get("error")
            if isinstance(error, dict) and re.fullmatch(r"[A-Z0-9_]{1,80}", error.get("code", "")):
                evidence["backend_error_code"] = error["code"]
            if not observed or observed[-1]["status"] != value:
                observed.append({"status": value, "at_utc": utc()})
            require(value not in {"failed", "interrupted", "qc_failed"}, "BACKGROUND_RENDER_FAILED")
            require(time.monotonic() < deadline, "BACKGROUND_RENDER_TIMEOUT")
            time.sleep(poll)
            status = client.json("GET", route + "/status" + query)
        evidence["observed_phases"] = observed + [{"status": "complete", "at_utc": utc()}]
        result = status.get("result", {})
        qc = result.get("qc", {})
        require(qc.get("passed") is True, "AUTOMATIC_QC_FAILED")
        require(result.get("plan_hash") == plan_hash, "RENDERED_PLAN_HASH_MISMATCH")
        require(abs(float(qc.get("duration", 0)) - 12) <= .075 and qc.get("decoded_frames") == 360
                and qc.get("dimensions") == [1080, 1920] and abs(float(qc.get("fps", 0)) - 30) < .01
                and qc.get("codec") == "h264", "FINAL_MEDIA_SPEC_MISMATCH")
        evidence["automatic_qc"] = {key: qc.get(key) for key in ("passed", "duration", "decoded_frames", "dimensions", "fps", "codec", "failures", "publication_quality")}
        metrics = result.get("metrics", {})
        evidence["actual_execution_metrics"] = metrics
        evidence["all_scenes_native_this_run"] = metrics.get("rendered_scene_count") == 5 and metrics.get("cached_scene_count") == 0
        evidence["metrics_backend_label_preserved"] = metrics.get("backend")
        assets = status.get("outputs", [])
        for name, result_key in (("final.mp4", "final"), ("final_muted.mp4", "muted")):
            asset = next((item for item in assets if item.get("name") == name), None)
            require(asset and isinstance(asset.get("url"), str), "FINAL_DOWNLOAD_NOT_PUBLISHED")
            download_route = asset["url"]
            require(download_route.startswith(f"/download/{project}/{version}/"), "UNTRUSTED_DOWNLOAD_ROUTE")
            destination = downloads / name
            with client.open("GET", download_route, headers={"Accept": "video/mp4"}) as response:
                require(response.status == 200, "FINAL_DOWNLOAD_FAILED")
                with destination.open("xb") as target:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        target.write(chunk)
            expected_sha = result.get("final_sha256", {}).get(result_key)
            actual_sha = sha(destination)
            require(re.fullmatch(r"[a-f0-9]{64}", expected_sha or "") and actual_sha == expected_sha, "FINAL_DOWNLOAD_SHA_MISMATCH")
            size = destination.stat().st_size
            require(size == asset.get("bytes") and size > 1024, "FINAL_DOWNLOAD_SIZE_MISMATCH")
            with client.open("GET", download_route, headers={"Range": "bytes=0-1023"}) as response:
                require(response.status == 206 and response.headers.get("Content-Range") == f"bytes 0-1023/{size}", "HTTP_RANGE_FAILED")
                ranged = response.read(1025)
            with destination.open("rb") as target:
                require(ranged == target.read(1024), "HTTP_RANGE_BYTES_MISMATCH")
            head_status, head_headers, head_body = client.call("HEAD", download_route)
            require(head_status == 200 and head_body == b"" and int(head_headers.get("content-length", -1)) == size, "HTTP_HEAD_FAILED")
            evidence["downloads"].append({"name": name, "bytes": size, "sha256": actual_sha, "server_sha256_verified": True, "http_range_verified": True, "http_head_verified": True})
        require(len(evidence["downloads"]) == 2, "FINAL_DOWNLOADS_INCOMPLETE")
        evidence.update(passed=True, render_complete=True, completed_at_utc=utc(),
                        validation_scope="Real HTTP short render, independent client reconnect, backend QC, final/muted SHA, Range and HEAD.")
        return evidence
    except ValidationError as error:
        evidence.update(passed=False, failure=str(error))
        return evidence
    except (OSError, ValueError, TypeError, KeyError, URLError):
        evidence.update(passed=False, failure="VALIDATION_RUNTIME_FAILED")
        return evidence
    finally:
        evidence["finished_at_utc"] = utc()
        safe = redact(evidence, password)
        evidence.clear()
        evidence.update(safe)
        save(output / "REPORT.json", evidence)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("seed", help="Create one new unapproved short QA project; no rendering")
    prepare.add_argument("--source-plan", type=Path, default=SOURCE)
    prepare.add_argument("--state-root", type=Path, required=True)
    prepare.add_argument("--output", type=Path)
    check = commands.add_parser("run", help="Check an already running gateway; --render explicitly enqueues selected QA")
    check.add_argument("--base", default="http://127.0.0.1:18100")
    check.add_argument("--access-file", type=Path, required=True)
    check.add_argument("--output", type=Path, required=True)
    check.add_argument("--project")
    check.add_argument("--version", default="v001")
    check.add_argument("--render", action="store_true")
    check.add_argument("--timeout", type=int, default=3600)
    check.add_argument("--poll", type=float, default=2)
    args = parser.parse_args(argv)
    if args.command == "seed":
        try:
            value = seed(args.source_plan, args.state_root, args.output)
        except Exception:
            print(json.dumps({"passed": False, "failure": "QA_SEED_FAILED", "render_started": False}))
            return 1
    else:
        if not 1 <= args.timeout <= 13800 or not .1 <= args.poll <= 30:
            parser.error("Choose a positive bounded timeout and polling interval")
        try:
            value = run(args.base, args.access_file, args.output, project=args.project,
                        version=args.version, render=args.render, timeout=args.timeout, poll=args.poll)
        except (ValidationError, OSError, ValueError, KeyError, TypeError):
            value = {"passed": False, "failure": "VALIDATION_SETUP_FAILED", "secret_values_recorded": False}
    print(json.dumps(value, ensure_ascii=False))
    return 0 if value.get("passed", value.get("gate_passed", False)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
