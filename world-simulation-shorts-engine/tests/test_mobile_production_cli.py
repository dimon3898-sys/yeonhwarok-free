"""Production CLI contracts without video generation or real deployment.

Planning uses the actual certified engine once. Authentication uses a synthetic
loopback HTTP server. Export uses explicitly synthetic evidence and mocked
ffprobe metadata; its bytes are not footage or a production-quality claim.
"""
from contextlib import redirect_stdout
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from deployment import production_cli as cli
from engine.planner import generate_plan
from engine.storage import ProjectStore
from tools.deliverable_evidence import sha256
from tools.test_deliverable_tools import fixture, write


TOPIC = "서울에서 도쿄를 거쳐 타이베이로 이동하는 민간 항공 연결"


def invoke(*args):
    out = io.StringIO()
    with redirect_stdout(out):
        code = cli.main(list(args))
    return code, json.loads(out.getvalue())


class PlanningCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = generate_plan(cli.production_request(TOPIC, 20))
        if not cls.plan["gate"]["passed"]:
            raise AssertionError(cls.plan["gate"]["errors"])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wss-mobile-cli-plan-")
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "state"

    def plan_once(self):
        with patch("engine.planner.generate_plan", return_value=deepcopy(self.plan)) as generate:
            code, result = invoke("--state-root", str(self.state), "plan", "--topic", TOPIC, "--duration", "20")
        self.assertEqual(code, 0)
        return result, generate.call_args.args[0]

    def test_actual_engine_default_and_cli_saved_contract_agree(self):
        result, request = self.plan_once()
        self.assertEqual(cli.PRODUCTION_SHORTS, result["profile"])
        self.assertEqual(request["production_preset"], "PRODUCTION_DEFAULT")
        self.assertEqual(request["quality"], "HIGH")
        self.assertEqual(request["pace"], "FAST_PLUS")
        self.assertFalse(request["tts"])
        self.assertFalse(request["subtitles"])
        self.assertTrue(request["bgm"] and request["sfx"])
        self.assertEqual(self.plan["options"]["pace"], request["pace"])
        self.assertEqual(self.plan["options"]["quality"], request["quality"])
        self.assertFalse(self.plan["options"]["tts"])
        self.assertTrue(result["gate_passed"])
        self.assertIn("서울", TOPIC)
        self.assertIn("S001", result["readable_plan"])
        self.assertFalse(result["approval_created"] or result["render_started"])
        path = Path(result["scene_plan"])
        self.assertFalse((path.parent / "approval.json").exists())
        self.assertFalse((path.parent / "renders/checkpoint.json").exists())
        stored = json.loads(path.read_text())
        self.assertTrue(stored["gate"]["passed"])
        self.assertEqual(stored["plan_hash"], result["plan_hash"])
        self.assertTrue(all(s["coordinates"]["source_id"] == "natural_earth_places" for s in stored["scenes"]))

    def test_each_plan_is_new_uuid_and_preserves_older_exact_bytes(self):
        first, _ = self.plan_once()
        p = Path(first["scene_plan"])
        before = p.read_bytes()
        second, _ = self.plan_once()
        self.assertNotEqual(first["project_id"], second["project_id"])
        self.assertEqual(p.read_bytes(), before)

    def test_explicit_approval_requires_current_hash_and_never_renders(self):
        record, _ = self.plan_once()
        p = Path(record["scene_plan"])
        before = p.read_bytes()
        base = ("--state-root", str(self.state), "approve", "--project", record["project_id"], "--version", record["version"], "--plan-hash")
        code, error = invoke(*base, "0" * 64)
        self.assertEqual(code, 2)
        self.assertEqual(error["error"]["code"], "PLAN_CHANGED")
        self.assertFalse((p.parent / "approval.json").exists())
        code, result = invoke(*base, record["plan_hash"])
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "approved")
        self.assertFalse(result["render_started"])
        self.assertEqual(p.read_bytes(), before)
        store = ProjectStore(self.state / "projects")
        self.assertEqual(store.require_approved(record["project_id"], record["version"])["plan_hash"], record["plan_hash"])

    def test_blocked_plan_is_saved_for_review_without_approval(self):
        bad = deepcopy(self.plan)
        bad["scenes"][0]["coordinates"]["lon"] = 999
        with patch("engine.planner.generate_plan", return_value=bad):
            code, result = invoke("--state-root", str(self.state), "plan", "--topic", TOPIC, "--duration", "20")
        self.assertEqual(code, 2)
        self.assertFalse(result["gate_passed"])
        self.assertTrue(result["errors"])
        self.assertTrue(Path(result["scene_plan"]).is_file())
        self.assertFalse((Path(result["scene_plan"]).parent / "approval.json").exists())

    def test_unknown_plugin_and_failed_job_status_remain_explicit(self):
        code, result = invoke("--state-root", str(self.state), "plan", "--topic", "판게아 대륙을 분리해 이동시켜", "--duration", "20")
        self.assertEqual(code, 2)
        self.assertIn("UNSUPPORTED_VISUAL_REQUIREMENT", json.dumps(result))
        record, _ = self.plan_once()
        ProjectStore(self.state / "projects").set_status(record["project_id"], record["version"], status="failed", error={"code": "SCENE_RENDER_FAILED"})
        code, result = invoke("--state-root", str(self.state), "status", "--project", record["project_id"])
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"]["code"], "SCENE_RENDER_FAILED")

    def test_quality_pace_and_audio_controls_are_independent(self):
        args = cli.build_parser().parse_args(["plan", "--topic", TOPIC, "--duration", "40", "--quality", "CINEMA", "--pace", "CINEMATIC", "--tts", "--subtitles", "--no-bgm", "--no-sfx"])
        value = cli.production_request(args.topic, args.duration, quality=args.quality, pace=args.pace, tts=args.tts, subtitles=args.subtitles, bgm=args.bgm, sfx=args.sfx)
        self.assertEqual(value["quality"], "CINEMA")
        self.assertEqual(value["pace"], "CINEMATIC")
        self.assertTrue(value["tts"] and value["subtitles"])
        self.assertFalse(value["bgm"] or value["sfx"])
        self.assertEqual(cli.production_request(TOPIC, 20, pace="FASTPLUS")["pace"], "FAST_PLUS")


class AuthenticationCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wss-mobile-cli-auth-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.secret = "synthetic-secret-no-real-credential"
        self.calls = []
        self.mode = "success"
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.calls.append((self.path, body, self.headers.get("Cookie"), self.headers.get("Origin")))
                if self.path == "/auth/login":
                    if owner.mode == "redirect":
                        self.send_response(302)
                        self.send_header("Location", "/credential-leak")
                        self.end_headers()
                        return
                    if owner.mode == "reject":
                        self.send_response(401)
                        payload = {"error": {"message": owner.secret}}
                    else:
                        self.send_response(200)
                        payload = {"authenticated": owner.mode != "false-auth", "password": owner.secret}
                        self.send_header("Set-Cookie", "world_owner_session=synthetic-session-secret; Path=/; HttpOnly")
                elif self.path.endswith("/render"):
                    self.send_response(202)
                    payload = {"job_id": "job_fixture", "status": "queued", "password": owner.secret, "cookie": "synthetic-session-secret"}
                else:
                    self.send_response(404)
                    payload = {}
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def invoke_render(self, content):
        access = self.root / "access-file"
        access.write_text(content)
        return invoke("render", "--base", self.base, "--access-file", str(access), "--project", "project_abcdef123456", "--version", "v001")

    def test_plaintext_and_json_auth_cookie_origin_and_background_contract(self):
        for content in (self.secret + "\n", json.dumps({"password": self.secret})):
            with self.subTest(format=content.startswith("{")):
                self.calls.clear()
                code, result = self.invoke_render(content)
                self.assertEqual(code, 0)
                self.assertEqual(result["http_status"], 202)
                self.assertEqual(result["job_id"], "job_fixture")
                self.assertFalse(result["waited_for_render"] or result["credentials_written"])
                self.assertEqual(len(self.calls), 2)
                self.assertEqual(self.calls[0][1], {"password": self.secret})
                self.assertEqual(self.calls[1][1], {"version": "v001"})
                self.assertIn("world_owner_session=synthetic-session-secret", self.calls[1][2])
                self.assertTrue(all(call[3] == self.base for call in self.calls))
                self.assertNotIn(self.secret, json.dumps(result))
                self.assertNotIn("synthetic-session-secret", json.dumps(result))
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), ["access-file"])

    def test_rejected_false_or_redirected_auth_never_submits_render_or_echoes_secret(self):
        for mode in ("reject", "false-auth", "redirect"):
            with self.subTest(mode=mode):
                self.mode = mode
                self.calls.clear()
                code, result = self.invoke_render(self.secret)
                self.assertEqual(code, 2)
                self.assertEqual(result["error"]["code"], "MOBILE_AUTH_FAILED")
                self.assertEqual([c[0] for c in self.calls], ["/auth/login"])
                self.assertNotIn(self.secret, json.dumps(result))

    def test_remote_plain_http_url_credentials_and_bad_access_fail_before_network(self):
        access = self.root / "access-file"
        access.write_text(self.secret)
        for base in ("http://example.com", "https://owner:secret@example.com", "file:///tmp/example", "https://example.com/?token=secret"):
            with self.subTest(base=base):
                code, result = invoke("render", "--base", base, "--access-file", str(access), "--project", "project_abcdef123456", "--version", "v001")
                self.assertEqual(code, 2)
        code, result = self.invoke_render('{"password": ""}')
        self.assertEqual(code, 2)
        self.assertEqual(result["error"]["code"], "INVALID_ACCESS_FILE")
        self.assertFalse(self.calls)


class StateRootCLI(unittest.TestCase):
    def test_existing_protected_roots_rejected_before_store_creation(self):
        protected = [cli.APP_ROOT, cli.APP_ROOT / "projects", cli.APP_ROOT / "cache",
                     cli.APP_ROOT / "engine", cli.APP_ROOT / "web", cli.APP_ROOT / "data",
                     cli.APP_ROOT / "assets", cli.APP_ROOT / "library",
                     cli.APP_ROOT.parent / "deliverables", cli.APP_ROOT.parent / "cinematic-world-map"]
        protected += list(cli.APP_ROOT.glob("projects-*"))
        for root in protected:
            with self.subTest(root=root.name), patch.object(cli, "ProjectStore") as store:
                code, result = invoke("--state-root", str(root), "status", "--project", "project_abcdef123456", "--version", "v001")
                self.assertEqual(code, 2)
                self.assertEqual(result["error"]["code"], "UNSAFE_STATE_ROOT")
                store.assert_not_called()

    def test_old_project_directory_and_symlink_are_not_claimed_as_runtime(self):
        with tempfile.TemporaryDirectory(prefix="wss-mobile-cli-guard-") as temporary:
            root = Path(temporary)
            old = root / "preserved-project"
            old.mkdir()
            (old / "project.json").write_bytes(b"preserved old project bytes")
            alias = root / "symlink-runtime"
            alias.symlink_to(old, target_is_directory=True)
            for selected in (old, alias):
                with self.subTest(symlink=selected.is_symlink()), patch.object(cli, "ProjectStore") as store:
                    code, result = invoke("--state-root", str(selected), "status", "--project", "project_abcdef123456")
                    self.assertEqual(code, 2)
                    self.assertEqual(result["error"]["code"], "UNSAFE_STATE_ROOT")
                    store.assert_not_called()
                    self.assertEqual((old / "project.json").read_bytes(), b"preserved old project bytes")
                    self.assertFalse((old / "mobile-state.json").exists())
                    self.assertFalse((old / "projects").exists())


class ExportCLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wss-mobile-cli-export-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "state"
        self.version, self.plan, self.result = fixture(self.state / "projects")
        self.destination = self.root / "new-download"

    @staticmethod
    def probe(path):
        duration = 10 if path.name.startswith("scene_") else 20
        return {"streams": [{"codec_type": "video", "codec_name": "h264", "pix_fmt": "yuv420p", "width": 1080, "height": 1920, "avg_frame_rate": "30/1"}], "format": {"duration": str(duration)}}

    def run_export(self, destination=None):
        return invoke("--state-root", str(self.state), "export", "--project", self.plan["project_id"], "--version", "v001", "--destination", str(destination or self.destination))

    def test_complete_recovery_outputs_export_exclusively_with_scene_media_and_no_secrets(self):
        before = {str(p): sha256(p) for p in self.version.rglob("*") if p.is_file()}
        write(self.version / "auth/password.json", {"password": "excluded-secret"})
        with patch.object(cli, "probe_video", side_effect=self.probe) as probe:
            code, result = self.run_export()
        self.assertEqual(code, 0)
        self.assertEqual(probe.call_count, 4)
        self.assertTrue(result["automatic_qc_passed"])
        self.assertFalse(result["render_started"] or result["auth_files_included"])
        self.assertEqual((self.destination / "final.mp4").read_bytes(), Path(self.result["outputs"]["final"]).read_bytes())
        names = {str(p.relative_to(self.destination)) for p in self.destination.rglob("*") if p.is_file()}
        self.assertTrue({"final.mp4", "final_muted.mp4", "scene_plan.json", "scene_plan_readable.md", "script.txt", "qc_report.json", "qc_report.md", "contact_sheet.png", "source_report.md", "source_report.json", "scene_results.json", "scenes/S001.mp4", "scenes/S002.mp4"}.issubset(names))
        self.assertFalse(any("auth" in name or "partial" in name or "texture" in name or "cache" in name for name in names))
        manifest = json.loads((self.destination / "EXPORT_MANIFEST.json").read_text())
        for item in manifest["files"]:
            self.assertEqual(sha256(self.destination / item["file"]), item["sha256"])
        self.assertEqual(before, {str(p): sha256(p) for p in self.version.rglob("*") if p.is_file() and "auth" not in p.parts})
        code, result = self.run_export()
        self.assertEqual(code, 2)
        self.assertEqual(result["error"]["code"], "OUTPUT_EXISTS_PRESERVED")

    def test_qc_hash_and_scene_results_fail_before_any_output_creation(self):
        for index, change in enumerate((
            lambda v, p, r: r["qc"].update(passed=False),
            lambda v, p, r: write(Path(r["outputs"]["final"]), b"changed media"),
            lambda v, p, r: write(v / "renders/scene_results.json", {"plan_hash": p["plan_hash"], "scenes": []}),
        )):
            with self.subTest(case=index):
                self.version, self.plan, self.result = fixture(self.root / f"case{index}/projects")
                self.state = self.root / f"case{index}"
                change(self.version, self.plan, self.result)
                write(self.version / "renders/project_result.json", self.result)
                output = self.root / f"rejected{index}"
                code, result = self.run_export(output)
                self.assertEqual(code, 2)
                self.assertEqual(result["error"]["code"], "EXPORT_EVIDENCE_FAILED")
                self.assertFalse(output.exists())

    def test_real_probe_failure_bad_spec_or_muted_audio_reject_before_copy(self):
        args = ("--state-root", str(self.state), "export", "--project", self.plan["project_id"], "--version", "v001", "--destination", str(self.destination))
        # Fixture bytes are intentionally not MP4: the real ffprobe must reject.
        code, result = invoke(*args)
        self.assertEqual(code, 2)
        self.assertEqual(result["error"]["code"], "MEDIA_PROBE_FAILED")
        self.assertFalse(self.destination.exists())
        for failure in ("wrong width", "muted audio"):
            with self.subTest(failure=failure):
                def bad(path):
                    meta = self.probe(path)
                    if failure == "wrong width":
                        meta["streams"][0]["width"] = 1920
                    elif "muted" in path.name:
                        meta["streams"].append({"codec_type": "audio"})
                    return meta
                with patch.object(cli, "probe_video", side_effect=bad):
                    code, result = invoke(*args)
                self.assertEqual(code, 2)
                self.assertEqual(result["error"]["code"], "MEDIA_SPEC_MISMATCH")
                self.assertFalse(self.destination.exists())

    def test_scene_json_drift_is_blocked_before_output_creation(self):
        write(self.version / "scene_json/S001.json", {"scene_id": "S001", "duration": 9})
        with patch.object(cli, "probe_video", side_effect=self.probe):
            code, result = self.run_export()
        self.assertEqual(code, 2)
        self.assertEqual(result["error"]["code"], "SCENE_JSON_MISMATCH")
        self.assertFalse(self.destination.exists())

    def test_path_escape_cross_project_symlink_and_traversal_are_not_exported(self):
        output = self.state / "projects/project_other00000/new-download"
        code, result = self.run_export(output)
        self.assertEqual(code, 2)
        self.assertEqual(result["error"]["code"], "EXPORT_MUST_NOT_WRITE_IN_PROJECTS")
        code, result = self.run_export(self.root / "new/../ambiguous")
        self.assertEqual(code, 2)
        self.assertEqual(result["error"]["code"], "INVALID_EXPORT_DESTINATION")
        outside = self.root / "outside.mp4"
        outside.write_bytes(b"outside synthetic bytes")
        alias = self.version / "final/attempt002/alias.mp4"
        alias.symlink_to(outside)
        self.result["outputs"]["final"] = str(alias)
        self.result["final_sha256"]["final"] = sha256(outside)
        write(self.version / "renders/project_result.json", self.result)
        code, result = self.run_export()
        self.assertEqual(code, 2)
        self.assertEqual(result["error"]["code"], "EXPORT_EVIDENCE_FAILED")
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
