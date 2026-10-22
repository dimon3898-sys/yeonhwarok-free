"""Focused contracts for new glue; no browser, render, source authoring or launch."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract = load("_test_recovery_contract", HERE / "source_contract.py")
controller = load("_test_recovery_controller", HERE / "studio_controller.py")
worker = load("_test_recovery_worker", HERE / "software_worker.py")
BASELINE = json.loads((HERE.parent / "universal-source-pipeline-v2/fixtures/DEMO_SOURCE_SCENE.json").read_bytes())


def receipt():
    return {"schema": "WORLD_ENGINE_G2_MAP_STYLE_RECEIPT_V1", "styleId": "NE1_SOURCE_NATIVE_COVERAGE",
        "terrainAsset": {"path": "unit-fixture.png", "url": "/recovery-assets/unit-fixture.png",
            "sha256": "a" * 64, "bytes": 100, "bounds": [90, -6, 126, 46], "dimensions": [2160, 3120],
            "pixelSpacing": [1 / 60, 1 / 60], "CRS": "EPSG:4326", "classification": "BAKED HILLSHADE"}}


def normalized(style):
    terrain = style["terrainAsset"]
    native = {left: deepcopy(terrain[right]) for left, right in {"file": "path", "url": "url",
        "sha256": "sha256", "bounds": "bounds", "dimensions": "dimensions", "pixelSpacing": "pixelSpacing",
        "classification": "classification"}.items()}
    return {"schema": contract.SCHEMA, "sourcePipeline": {"mode": "SYNTHETIC_TEST",
        "scope": "SYNTHETIC_TECHNICAL_DEMO", "ready": True, "totalFrames": 180, "startFrame": 0,
        "runtimePayload": {"nativePlan": {"assets": {"terrain": native}},
            "cameraSchedule": [{"frame": 0, "flatBounds": [93, -3, 123, 43]}]}, "blockers": []}}


class ContractTests(unittest.TestCase):
    def run_normalizer(self, value, *, mode="SYNTHETIC_TEST", terrain_mutation=None, ready=True):
        style = receipt()
        result = normalized(style)
        result["sourcePipeline"]["mode"] = mode
        if terrain_mutation:
            result["sourcePipeline"]["runtimePayload"]["nativePlan"]["assets"]["terrain"].update(terrain_mutation)
        validator = SimpleNamespace(validate_style=lambda *args, **kwargs: {"ready": ready})
        original_read = contract._read_json
        def read(file):
            return deepcopy(style) if file.name == "RECOVERY_STYLE_RECEIPT.json" else original_read(file)
        # Style-file hashing is a real read in production, with an explicit
        # in-memory fixture only for this wrapper contract unit test.
        raw = json.dumps(style).encode()
        original_bytes = Path.read_bytes
        def read_bytes(file):
            return raw if file == HERE / "fixtures/RECOVERY_STYLE_RECEIPT.json" else original_bytes(file)
        with patch.object(contract, "_read_json", side_effect=read), \
             patch.object(contract.original, "normalize_submission", return_value=result), \
             patch.object(contract, "load", return_value=validator), \
             patch.object(contract, "recovery_bindings", return_value=[]), \
             patch.object(Path, "read_bytes", read_bytes):
            return contract.normalize_submission(value, source_root="/unit-explicit-fake", expected_index_sha256="b" * 64)

    def test_same_registered_scene_is_only_selected_input(self):
        out = self.run_normalizer(deepcopy(BASELINE))
        self.assertEqual(out["sourcePipeline"]["sourceStyle"]["styleId"], "NE1_SOURCE_NATIVE_COVERAGE")
        self.assertFalse(out["sourcePipeline"]["recoveryScope"]["historicalRenderAllowed"])
        self.assertFalse(out["sourcePipeline"]["recoveryScope"]["paidGpuAllowed"])

    def test_browser_numeric_lexical_difference_keeps_same_scene(self):
        value = deepcopy(BASELINE)
        value["durationSeconds"] = 6
        value["event_location"]["coordinates"][1] = 18
        self.assertTrue(self.run_normalizer(value)["sourcePipeline"]["recoveryScope"]["sameSceneAsBaseline"])

    def test_camera_actor_and_frame_changes_reject_before_reusing_normalizer(self):
        for path, replacement in [("startFrame", 600), ("title", "Different event"), ("durationSeconds", 80)]:
            with self.subTest(path=path):
                value = deepcopy(BASELINE)
                value[path] = replacement
                with patch.object(contract.original, "normalize_submission") as called:
                    with self.assertRaisesRegex(ValueError, "G2_RECOVERY_UNCHANGED_DEMO_SCENE_REQUIRED"):
                        contract.normalize_submission(value, source_root="/unit", expected_index_sha256="b" * 64)
                    called.assert_not_called()
        value = deepcopy(BASELINE)
        value["actors"][0]["actor_color"][0] += .1
        with self.assertRaisesRegex(ValueError, "G2_RECOVERY_UNCHANGED_DEMO_SCENE_REQUIRED"):
            contract.normalize_submission(value, source_root="/unit", expected_index_sha256="b" * 64)

    def test_production_mode_is_never_admitted_by_recovery(self):
        with self.assertRaisesRegex(ValueError, "G2_RECOVERY_SYNTHETIC_SIX_SECONDS_ONLY"):
            self.run_normalizer(deepcopy(BASELINE), mode="PRODUCTION")

    def test_style_validator_cannot_be_skipped(self):
        with self.assertRaisesRegex(ValueError, "G2_RECOVERY_SOURCE_STYLE_NOT_READY"):
            self.run_normalizer(deepcopy(BASELINE), ready=False)

    def test_native_plan_must_equal_actual_style_metadata(self):
        for replacement in [{"sha256": "0" * 64}, {"bounds": [-180, -90, 180, 90]}, {"url": "/other.png"}]:
            with self.subTest(replacement=replacement):
                with self.assertRaisesRegex(ValueError, "G2_RECOVERY_NATIVE_STYLE_BINDING_MISMATCH"):
                    self.run_normalizer(deepcopy(BASELINE), terrain_mutation=replacement)


class GateTests(unittest.TestCase):
    def test_all_three_gates_are_required_and_history_stays_blocked(self):
        gates = {f"phase{i}": {"status": "PASS"} for i in range(3)}
        gates["historicalG3"] = "BLOCKED"
        self.assertTrue(all(row["status"] == "PASS" for row in controller.recovery_gate_checks(gates)))
        for phase in range(3):
            value = deepcopy(gates)
            value[f"phase{phase}"]["status"] = "IN_PROGRESS"
            self.assertEqual(controller.recovery_gate_checks(value)[phase]["status"], "BLOCKED")
        gates["historicalG3"] = "PASS"
        self.assertEqual(controller.recovery_gate_checks(gates)[-1]["status"], "BLOCKED")

    def test_missing_or_boolean_gate_flags_do_not_authorize_render(self):
        for value in (None, {}, {"phase0": True}, {"phase0": {"status": True}}):
            with self.subTest(value=value):
                self.assertFalse(all(row["status"] == "PASS" for row in controller.recovery_gate_checks(value)))

    def test_actual_start_gate_error_is_explicit(self):
        with patch.object(controller, "current_gate_checks", return_value=[{
                "name": "G2_RECOVERY_PHASE_2", "status": "BLOCKED", "code": "G2_RECOVERY_PHASE_2_NOT_PASSED"}]):
            with self.assertRaisesRegex(controller.StudioError, "G2_RECOVERY_PHASE_2_NOT_PASSED"):
                controller.require_recovery_gates()

    def test_preflight_adds_gate_without_changing_non_source_family(self):
        instance = object.__new__(controller.StudioController)
        original = {"checks": [{"name": "ORIGINAL", "status": "PASS"}], "ready": True,
            "historicalRenderAllowed": False, "paidRenderAllowed": False}
        with patch.object(controller.reused.StudioController, "_preflight_record", return_value=deepcopy(original)), \
             patch.object(controller, "current_gate_checks", return_value=[{"name": "G2_RECOVERY_PHASE_2", "status": "BLOCKED"}]):
            result = instance._preflight_record(None, {"submission": {"schema": contract.SCHEMA}})
            self.assertFalse(result["ready"])
            delegated = instance._preflight_record(None, {"submission": {"schema": "OTHER_EXISTING_FAMILY"}})
            self.assertEqual(delegated, original)

    def test_reused_bodies_and_separate_entrypoint_root(self):
        self.assertIs(worker.validate_package, worker.reused.validate_package)
        self.assertIs(worker.validate_capture, worker.reused.validate_capture)
        self.assertEqual(worker.reused.HERE, HERE)
        self.assertEqual(controller.reused.HERE, HERE)
        self.assertTrue(sys.dont_write_bytecode)
        old = HERE.parent / "universal-source-pipeline-v2"
        self.assertEqual(Path(controller.reused.StudioController.start.__code__.co_filename),
            old / "studio_controller.py")
        self.assertEqual(Path(worker.reused.run.__code__.co_filename), old / "software_worker.py")

    def test_old_private_state_path_is_rejected_before_initialization(self):
        with self.assertRaisesRegex(controller.StudioError, "G2_RECOVERY_SEPARATE_PRIVATE_STATE_REQUIRED"):
            controller.StudioController(control_root=Path("/workspace/source-studio-private-20261022-d/state/control"))


if __name__ == "__main__":
    unittest.main()
