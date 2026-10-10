"""A reviewed child release cannot replace any original source/test/asset gate."""
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import inspect
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from deployment.gcube import terrain_preflight as terrain


class TerrainReleaseHarnessV024(unittest.TestCase):
    def setUp(self):
        self.value = json.loads(terrain.MANIFEST.read_bytes())

    def test_original_1200_exact_identities_and_v023_sources_are_frozen(self):
        value, receipt = terrain.verify_sources()
        self.assertEqual(receipt['original_unique_tests'], 1200)
        self.assertEqual(receipt['protected_runtime_files'], 67)
        self.assertEqual(len(value['inherited_core_ids']), 963)
        self.assertEqual(len(value['proxy_ids']), 206)
        self.assertEqual(len(value['diagnostic_ids']), 31)
        self.assertEqual(receipt['exact_published_parent'], terrain.PARENT_DIGEST)
        self.assertEqual(receipt['physical_gpu'], 'NOT_RUN')

    def test_parent_projection_changes_only_the_three_sealed_selector_rows(self):
        before = terrain.parent_value()
        after = terrain.translated_parent_manifest(self.value)
        self.assertEqual({key: val for key, val in before.items() if key != 'parent_deltas'},
                         {key: val for key, val in after.items() if key != 'parent_deltas'})
        changed = {left['path'] for left, right in zip(before['parent_deltas'], after['parent_deltas']) if left != right}
        self.assertEqual(changed, {row['path'] for row in self.value['parent_deltas']})
        self.assertLessEqual(changed, terrain.AUTHORIZED_PARENT_DELTAS)
        self.assertEqual(hashlib.sha256(terrain.physical_bytes(terrain.PARENT_MANIFEST)).hexdigest(), terrain.PARENT_MANIFEST_SHA256)

    def test_tampered_current_selector_bytes_fail_before_parent_admission(self):
        original = Path.read_bytes
        target = terrain.APP / 'web/app.js'
        def changed(path):
            raw = original(path)
            return raw + b'\nUNSEALED_SOURCE' if path == target else raw
        with patch.object(Path, 'read_bytes', changed):
            with self.assertRaisesRegex(AssertionError, 'BOLD_SOURCE_CHANGED:web/app.js'):
                terrain.verify_sources()

    def test_old_bold_renderer_cannot_be_replaced_by_a_child_runtime_record(self):
        forged = deepcopy(self.value)
        forged['runtime_records'].append(dict(path='web/bold_infographic_adapter.js', size=1, sha256='0' * 64))
        original = Path.read_bytes
        def changed(path):
            return json.dumps(forged).encode() if path == terrain.MANIFEST else original(path)
        with patch.object(Path, 'read_bytes', changed):
            with self.assertRaisesRegex(AssertionError, 'TERRAIN_PARENT_RUNTIME_REPLACED'):
                terrain.verify_sources()

    def test_parent_receipt_cannot_authorize_a_geometry_or_camera_delta(self):
        forged = deepcopy(self.value)
        forged['parent_deltas'].append(dict(path='engine/infographic_contract.py', size=1, sha256='0' * 64))
        original = Path.read_bytes
        def changed(path):
            return json.dumps(forged).encode() if path == terrain.MANIFEST else original(path)
        with patch.object(Path, 'read_bytes', changed):
            with self.assertRaisesRegex(AssertionError, 'TERRAIN_PARENT_SCOPE_CHANGED'):
                terrain.verify_sources()

    def test_pending_preview_cannot_freeze_or_publish_a_release(self):
        with self.assertRaisesRegex(AssertionError, 'TERRAIN_APPROVED_PREVIEW_REQUIRED'):
            terrain.validate_preview_receipt(dict(status='PENDING', passed=True), [])
        with self.assertRaisesRegex(AssertionError, 'TERRAIN_APPROVED_PREVIEW_REQUIRED'):
            terrain.freeze([], [], None)
        forged = deepcopy(self.value)
        forged['status'] = 'AWAITING_APPROVED_PREVIEW'
        original = Path.read_bytes
        with patch.object(Path, 'read_bytes', lambda path: json.dumps(forged).encode() if path == terrain.MANIFEST else original(path)):
            with self.assertRaisesRegex(AssertionError, 'TERRAIN_MANIFEST_NOT_FROZEN'):
                terrain.verify_sources()

    def test_preview_receipt_cannot_drop_representatives_stress_or_executed_sources(self):
        # This synthetic admission payload never freezes or approves a release.
        pins = [terrain.record(terrain.APP / path, terrain.APP)
                for path in sorted(terrain.REQUIRED_PREVIEW_SOURCES)]
        receipt = dict(status='APPROVED', passed=True, physical_gpu='NOT_RUN',
                       source_records=pins, mandatory_pixel_checks=['TEST_PIXEL_PROOF'],
                       case_names=list(terrain.REQUIRED_PREVIEW_CASES))
        for name in terrain.REQUIRED_PREVIEW_CASES:
            with self.subTest(missing_case=name):
                forged = deepcopy(receipt)
                forged['case_names'].remove(name)
                with self.assertRaisesRegex(AssertionError, 'TERRAIN_PREVIEW_CASE_INVENTORY_MISSING'):
                    terrain.validate_preview_receipt(forged, pins)
        for name in terrain.REQUIRED_PREVIEW_SOURCES:
            with self.subTest(missing_source=name):
                forged = deepcopy(receipt)
                forged['source_records'] = [row for row in pins if row['path'] != name]
                with self.assertRaisesRegex(AssertionError, 'TERRAIN_PREVIEW_REQUIRED_SOURCE_UNPINNED'):
                    terrain.validate_preview_receipt(forged, pins)

    def test_nested_admission_restores_reads_auditors_and_process_calls(self):
        from deployment.gcube import asset_audit, bold_preflight
        original_read, original_run = Path.read_bytes, subprocess.run
        original_auditor, original_cache = asset_audit.audit_assets, bold_preflight._real_asset_audit
        raw_manifest = terrain.physical_bytes(terrain.PARENT_MANIFEST)
        with self.assertRaisesRegex(RuntimeError, 'TERRAIN_CONTEXT_TEST_EXIT'):
            with terrain.parent_admission_view():
                self.assertEqual(json.loads(terrain.PARENT_MANIFEST.read_bytes()), terrain.translated_parent_manifest(self.value))
                self.assertEqual(terrain.physical_bytes(terrain.PARENT_MANIFEST), raw_manifest)
                raise RuntimeError('TERRAIN_CONTEXT_TEST_EXIT')
        self.assertIs(Path.read_bytes, original_read)
        self.assertIs(subprocess.run, original_run)
        self.assertIs(asset_audit.audit_assets, original_auditor)
        self.assertIs(bold_preflight._real_asset_audit, original_cache)

    def test_child_cli_rejects_any_unadmitted_script_before_execution(self):
        with self.assertRaisesRegex(AssertionError, 'TERRAIN_CHILD_SCRIPT_CHANGED'):
            terrain.child_entrypoint("raise RuntimeError('MUST_NOT_EXECUTE')")

    def test_cli_and_canonical_cache_share_the_real_parent_asset_admission(self):
        script = """
import importlib, json, runpy, sys, unittest
sys.argv = ['deployment.gcube.terrain_preflight', '--manifest-only']
runpy.run_module('deployment.gcube.terrain_preflight', run_name='__main__', alter_sys=True)
terrain = importlib.import_module('deployment.gcube.terrain_preflight')
package = importlib.import_module('deployment.gcube')
assert package.terrain_preflight is terrain
assert terrain.sha.__module__ == '__main__'
sys.path.insert(0, str(terrain.APP / 'tests'))
with terrain.parent_admission_view():
    module = importlib.import_module('test_bold_release_harness_v023')
    suite = unittest.TestSuite([module.BoldReleaseHarnessV023('test_context_restores_original_file_reads_and_subprocess_on_exception')])
    result = unittest.TextTestRunner().run(suite)
    assert result.testsRun == 1 and result.wasSuccessful() and not result.skipped
print(json.dumps({'cli_shared_module': True, 'nested_original_harness': 1, 'passed': True}))
"""
        result = subprocess.run([sys.executable, '-c', script], cwd=terrain.APP, capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        self.assertEqual(json.loads(result.stdout.splitlines()[-1]),
                         dict(cli_shared_module=True, nested_original_harness=1, passed=True))

    def test_numeric_notices_are_bounded_and_keep_gpu_separate(self):
        output = io.StringIO()
        with redirect_stdout(output):
            terrain.notice('Terrain regression proof', dict(tests=31, failures=0, errors=0, skipped=0, physical_gpu='NOT_RUN'))
        self.assertIn('"tests":31', output.getvalue())
        self.assertIn('NOT_RUN', output.getvalue())
        with self.assertRaisesRegex(AssertionError, 'TERRAIN_PUBLIC_NOTICE_TOO_LARGE'):
            terrain.notice('Terrain excessive proof', dict(unbounded='X' * 4000))

    def test_cold_pixel_preflight_composes_native_parent_before_real_node_boundary(self):
        # Execute the real release planner in a fresh interpreter.  The only
        # test substitute is at the exact Node draw boundary, after the actual
        # admitted plan is written; it never invents a pixel/result receipt.
        script = """
import json, subprocess, tempfile
from pathlib import Path
from unittest.mock import patch
from deployment.gcube import terrain_preflight as release
from deployment.gcube import selection_preflight as selection
from engine import infographic_contract as parent
from engine import terrain_infographic as child
from engine.infographic_planner import parent_qa_plan

class NodeBoundaryReached(Exception):
    pass

original_run = subprocess.run
observed = []
def at_actual_node_boundary(command, *args, **kwargs):
    if isinstance(command, list) and command[:2] == ['node', 'tools/terrain_canvas_preview_v024.mjs']:
        assert command[2] == '--plan' and command[4] == '--output' and len(command) == 6
        assert kwargs['cwd'] == release.APP and kwargs['capture_output'] is True
        assert kwargs['text'] is True and kwargs['timeout'] == 360
        plan = json.loads(Path(command[3]).read_text())
        assert child.validate_terrain_infographic(plan)['passed'] is True
        for key, version in [('infographic', 'v022'), ('bold_infographic', 'v023'), ('terrain_infographic', 'v024')]:
            assert plan['metadata'][key]['version'] == version
            assert all(scene[key]['version'] == version for scene in plan['scenes'])
        assert plan['duration'] == 24 and plan['metadata']['frame_grid']['fps'] == '30'
        assert plan['metadata']['frame_grid']['total_frames'] == 720
        assert sum(scene['frame_count'] for scene in plan['scenes']) == 720
        baseline = parent_qa_plan(dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=24,
            quality='HIGH', pace='FAST_PLUS', direction_profile='REFERENCE_MASTER', qa_mode=False,
            tts=False, subtitles=False, bgm=True, sfx=True))
        assert len(plan['scenes']) == len(baseline['scenes'])
        for scene, expected in zip(plan['scenes'], baseline['scenes']):
            # Every original scene field, including camera, quality, event,
            # marker and text timing, is compared to the actual native fixture.
            assert all(scene[key] == value for key, value in expected.items())
            assert parent._camera_snapshot(scene) == parent._camera_snapshot(expected)
            assert parent._quality_snapshot(scene) == parent._quality_snapshot(expected)
        assert not Path(command[5]).exists(), 'No Canvas execution/result is simulated'
        observed.append(dict(node_boundary_reached=True, admitted_frames=720,
            native_camera_and_quality='UNCHANGED', pixel_render='NOT_RUN', physical_gpu='NOT_RUN'))
        raise NodeBoundaryReached()
    return original_run(command, *args, **kwargs)

with tempfile.TemporaryDirectory(prefix='terrain-cold-pixel-plan-') as folder:
    with selection.environment(WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION='v022',
            WORLD_ENGINE_INFOGRAPHIC_VISUAL_PROFILE='BOLD_INFOGRAPHIC_V023',
            WORLD_ENGINE_TERRAIN_INFOGRAPHIC_PROFILE='VISUAL_TARGET_MAP_V024'):
        with patch.object(subprocess, 'run', at_actual_node_boundary):
            try:
                release.pixel_preflight(folder)
            except NodeBoundaryReached:
                pass
            else:
                raise AssertionError('ACTUAL_NODE_BOUNDARY_NOT_REACHED')
    assert len(observed) == 1
    assert not (Path(folder)/'TERRAIN_PIXEL_PREFLIGHT.json').exists()
print(json.dumps(observed[0], sort_keys=True))
"""
        result = subprocess.run([sys.executable, '-c', script], cwd=terrain.APP,
                                capture_output=True, text=True, timeout=240)
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])
        self.assertEqual(json.loads(result.stdout.splitlines()[-1]), dict(
            node_boundary_reached=True, admitted_frames=720,
            native_camera_and_quality='UNCHANGED', pixel_render='NOT_RUN', physical_gpu='NOT_RUN'))

    def test_immutable_child_workflow_requires_approval_and_keeps_parent_checks(self):
        workflow = (terrain.ROOT / '.github/workflows/gcube-terrain-v024.yml').read_text()
        self.assertIn('push: false', workflow)
        self.assertIn('--manifest-only --checkout', workflow)
        self.assertIn('--pixels-only', workflow)
        self.assertIn('--regressions-only', workflow)
        self.assertIn('WORLD_ENGINE_TERRAIN_INFOGRAPHIC_PROFILE=OFF', workflow)
        self.assertIn('Anonymous public pull', workflow)
        self.assertNotIn('--gpus', workflow)
        self.assertIn('GPU_HARDWARE_UNAVAILABLE', workflow)
        self.assertIn('gcube-bold-v023.yml', workflow)
        dockerfile = (terrain.APP / 'deployment/gcube/Dockerfile.terrain-v024').read_text()
        self.assertIn('@' + terrain.PARENT_DIGEST, dockerfile)
        self.assertIn('WORLD_ENGINE_TERRAIN_INFOGRAPHIC_PROFILE=VISUAL_TARGET_MAP_V024', dockerfile)
        self.assertNotIn('NVIDIA_DRIVER_CAPABILITIES=', dockerfile)
        self.assertIs(inspect.signature(terrain.regressions).parameters['container'].default, True)
        self.assertNotIn('--native', workflow)


if __name__ == '__main__':
    unittest.main()
