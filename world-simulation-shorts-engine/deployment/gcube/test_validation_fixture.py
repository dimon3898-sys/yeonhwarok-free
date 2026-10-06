"""Local first-boot fixture checks. No approval, renderer, container, or provider."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest

APP = Path(__file__).resolve().parents[2]
if str(APP) in sys.path:
    sys.path.remove(str(APP))
sys.path.insert(0, str(APP))
from deployment.gcube.validate_container import SOURCE, sha
from deployment.gcube.validation_fixture import FixtureError, seed_once
from engine.storage import ProjectStore

CERTIFIED = APP.parent / "deliverables/WORLD_SIMULATION_ENGINE/PRODUCTION_DEFAULT_INTEGRATION_v1/scene_plan.json"


class FirstBootFixtureTests(unittest.TestCase):
    def test_bundle_is_exact_certified_source_bytecopy_and_keeps_actual_fast_pace(self):
        self.assertEqual(SOURCE.read_bytes(), CERTIFIED.read_bytes())
        value = json.loads(SOURCE.read_text())
        self.assertEqual(value["options"]["pace"], "FAST")
        self.assertEqual(value["duration"], 12)
        self.assertEqual(len(value["scenes"]), 5)

    def test_seed_is_idempotent_private_and_never_approves_or_renders(self):
        before = sha(SOURCE)
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "runtime"
            first = seed_once(runtime)
            marker = runtime / "gcube-validation-project.json"
            marker_bytes = marker.read_bytes()
            folder = runtime / "projects" / first["project_id"] / "versions/v001"
            plan_bytes = (folder / "scene_plan.json").read_bytes()
            second = seed_once(runtime)
            self.assertEqual(first, second)
            self.assertEqual(marker.read_bytes(), marker_bytes)
            self.assertEqual((folder / "scene_plan.json").read_bytes(), plan_bytes)
            self.assertEqual(stat.S_IMODE(marker.stat().st_mode), 0o600)
            self.assertEqual(len(ProjectStore(runtime / "projects").list()), 1)
            self.assertFalse((folder / "approval.json").exists())
            self.assertEqual(list((folder / "renders").iterdir()), [])
            self.assertEqual(json.loads(plan_bytes)["options"]["pace"], "FAST")
            self.assertFalse(json.loads(plan_bytes)["options"]["tts"])
            self.assertFalse(first["approved_at_initialization"])
            self.assertFalse(first["render_started_at_initialization"])
        self.assertEqual(sha(SOURCE), before)

    def test_marker_corruption_or_changed_plan_never_creates_a_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "runtime"
            first = seed_once(runtime)
            marker = runtime / "gcube-validation-project.json"
            good_marker = marker.read_bytes()
            marker.write_text("[]")
            with self.assertRaises(FixtureError):
                seed_once(runtime)
            self.assertEqual(marker.read_text(), "[]")
            self.assertEqual(len(ProjectStore(runtime / "projects").list()), 1)
            marker.write_bytes(good_marker)
            plan_path = runtime / "projects" / first["project_id"] / "versions/v001/scene_plan.json"
            plan = json.loads(plan_path.read_text())
            plan["options"]["bgm"] = False
            plan_path.write_text(json.dumps(plan))
            with self.assertRaises(FixtureError):
                seed_once(runtime)
            self.assertEqual(len(ProjectStore(runtime / "projects").list()), 1)
            self.assertEqual(marker.read_bytes(), good_marker)

    def test_missing_project_and_incomplete_initialization_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "runtime"
            first = seed_once(runtime)
            plan = runtime / "projects" / first["project_id"] / "versions/v001/scene_plan.json"
            plan.unlink()
            with self.assertRaises(FixtureError):
                seed_once(runtime)
            self.assertEqual(len(ProjectStore(runtime / "projects").list()), 1)
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "runtime"
            runtime.mkdir()
            pending = runtime / "gcube-validation-project.pending.json"
            pending.write_text('{"state":"initializing"}')
            pending.chmod(0o600)
            with self.assertRaises(FixtureError):
                seed_once(runtime)
            self.assertEqual(list((runtime / "projects").glob("project_*") if (runtime / "projects").exists() else []), [])

    def test_owner_approval_and_status_are_preserved_on_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "runtime"
            first = seed_once(runtime)
            store = ProjectStore(runtime / "projects")
            store.approve(first["project_id"], first["version"], first["plan_hash"])
            folder = store.version_path(first["project_id"], first["version"])
            approval_before = (folder / "approval.json").read_bytes()
            status_before = (folder / "status.json").read_bytes()
            self.assertEqual(seed_once(runtime), first)
            self.assertEqual((folder / "approval.json").read_bytes(), approval_before)
            self.assertEqual((folder / "status.json").read_bytes(), status_before)

    def test_concurrent_first_boot_seeds_only_one_project(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / "runtime"
            # Create the deployment marker before concurrent boot workers enter.
            from deployment.mobile_server import checked_state_root
            checked_state_root(runtime)
            with ThreadPoolExecutor(max_workers=2) as executor:
                records = list(executor.map(lambda _: seed_once(runtime), range(2)))
            self.assertEqual(records[0], records[1])
            self.assertEqual(len(ProjectStore(runtime / "projects").list()), 1)


if __name__ == "__main__":
    unittest.main()
