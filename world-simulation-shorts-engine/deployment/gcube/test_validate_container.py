"""Local fixture preparation and real HTTP plan-only checks; no renderer/provider."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

APP = Path(__file__).resolve().parents[2]
if str(APP) in sys.path:
    sys.path.remove(str(APP))
sys.path.insert(0, str(APP))
from deployment.gcube.server import BoundedHTTPServer, GcubeApplication, GcubeHandler
from deployment.gcube.validate_container import Client, SOURCE, ValidationError, private_password, redact, run, seed, sha

PASSWORD = "controlled-container-check-password-2026"


class ValidationRunnerTests(unittest.TestCase):
    def test_seed_creates_unapproved_twelve_second_project_and_preserves_source(self):
        before = sha(SOURCE)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = seed(SOURCE, root / "runtime", root / "proof.json")
            folder = root / "runtime/projects" / result["project_id"] / "versions/v001"
            plan = json.loads((folder / "scene_plan.json").read_text())
            self.assertEqual(result["duration"], 12)
            self.assertEqual(result["scene_ids"], ["S001", "S002", "S003", "S004", "S005"])
            self.assertTrue(result["gate_passed"])
            self.assertFalse(result["approved"])
            self.assertFalse(result["render_started"])
            self.assertFalse((folder / "approval.json").exists())
            self.assertFalse(plan["options"]["tts"])
            self.assertFalse(plan["options"]["subtitles"])
            self.assertTrue(plan["options"]["bgm"])
            self.assertTrue(plan["options"]["sfx"])
            self.assertEqual(list((folder / "renders").iterdir()), [])
            self.assertFalse(plan.get("metadata", {}).get("rhythm_sample_render_authorization"))
        self.assertEqual(sha(SOURCE), before)

    def test_owner_file_requires_private_regular_file_and_supports_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "owner.json"
            path.write_text(json.dumps({"password": PASSWORD}))
            path.chmod(0o600)
            self.assertEqual(private_password(path), PASSWORD)
            path.chmod(0o644)
            with self.assertRaises(ValidationError):
                private_password(path)
            link = Path(directory) / "linked.json"
            link.symlink_to(path)
            with self.assertRaises(ValidationError):
                private_password(link)

    def test_invalid_origins_are_never_recorded_and_redaction_handles_nested_values(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "evidence"
            value = run("https://user:private-value@example.test", Path(directory) / "missing", output)
            self.assertFalse(value["passed"])
            self.assertIsNone(value["base"])
            self.assertNotIn("private-value", json.dumps(value))
            self.assertNotIn("private-value", (output / "REPORT.json").read_text())
        value = redact({"nested": ["prefix " + PASSWORD], "password": "anything", "secret_values_recorded": False}, PASSWORD)
        self.assertNotIn(PASSWORD, json.dumps(value))
        self.assertEqual(value["password"], "[redacted]")
        self.assertFalse(value["secret_values_recorded"])
        with self.assertRaises(ValidationError):
            Client("http://public.example.test")

    def test_real_http_login_natural_language_plan_and_short_project_reconnect_no_render(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"PATH": os.environ.get("PATH", "")}, clear=True):
            root = Path(directory)
            owner = root / "owner.txt"
            owner.write_text(PASSWORD)
            owner.chmod(0o600)
            fixture = seed(SOURCE, root / "runtime")
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                port = listener.getsockname()[1]
            origin = f"http://127.0.0.1:{port}"
            app = GcubeApplication(root / "runtime", "http://127.0.0.1:8001", owner,
                                   public_origin=origin, public_port=port, local_mode=True, disk_floor=0)
            server = BoundedHTTPServer(("127.0.0.1", port), GcubeHandler, app)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                output = root / "evidence"
                result = run(origin, owner, output, project=fixture["project_id"])
                self.assertTrue(result["passed"], result.get("failure"))
                self.assertEqual(result["project_id"], fixture["project_id"])
                self.assertTrue(result["real_http"])
                self.assertFalse(result["real_browser"])
                self.assertFalse(result["render_requested"])
                self.assertFalse(result["render_complete"])
                self.assertFalse(result["gpu_speedup_claimed"])
                self.assertEqual(result["planning"]["duration"], 20)
                self.assertFalse(result["planning"]["approved"])
                self.assertEqual(len(app.store.list()), 2)
                self.assertEqual(app.scheduler.tickets, {})
                self.assertNotIn(PASSWORD, (output / "REPORT.json").read_text())
                self.assertFalse((app.store.version_path(fixture["project_id"], "v001") / "approval.json").exists())
            finally:
                server.shutdown()
                server.server_close()
                thread.join(2)
                app.scheduler.close()


if __name__ == "__main__":
    unittest.main()
