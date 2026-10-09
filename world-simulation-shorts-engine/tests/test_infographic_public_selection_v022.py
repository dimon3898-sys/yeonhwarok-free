"""Actual public selection and saved-plan handoff; no GPU/render claims.

HTTP requests use the real owner authentication, public validator, planners,
ProjectStore and checked renderer command mapper. The only UI code evaluated
outside a browser is the exact exported creation/selection helper used by the
form; the separate browser suite verifies control persistence in the DOM.
"""
from copy import deepcopy
import hashlib
import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from types import FunctionType
import unittest
from unittest.mock import patch

from deployment.mobile_server import BoundedHTTPServer, MobileApplication, MobileHandler
from deployment.security import RequestPolicy, private_json
from engine import infographic_contract as infographic
from engine.storage import atomic_json, plan_hash


ROOT = Path(__file__).resolve().parents[1]
QA_PROFILE = 'MAP_INFOGRAPHIC_QA_V022'
PRODUCTION_PROFILE = 'MAP_INFOGRAPHIC_PRODUCTION_V022'
OWNER_FIXTURE = 'isolated-public-selection-test-owner-2026'
IMAGE_SELECTION_ENV = {
    'WORLD_ENGINE_DIRECTION_VERSION': 'v013',
    'WORLD_ENGINE_SINGLE_EVENT_CAMERA_TEST': '1',
    'WORLD_ENGINE_RETURN_WIDE_TEST': '1',
    'WORLD_ENGINE_SECOND_EVENT_TEST': '1',
    'WORLD_ENGINE_VISUAL_QUALITY_VERSION': 'v018',
    'WORLD_ENGINE_EVENT_QUALITY_VERSION': 'v019',
    'WORLD_ENGINE_REFERENCE_EFFECTS_VERSION': 'v020',
    'WORLD_ENGINE_STORY_PROGRESSION_VERSION': 'v021',
    'WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION': 'v022',
}


def _exported_function(source, name):
    """Extract the actual pure UI function, respecting strings/comments."""
    marker = 'export function ' + name + '('
    start = source.index(marker)
    opening = source.index('{', start)
    depth, quote, comment, escape, index = 0, None, None, False, opening
    while index < len(source):
        char = source[index]
        pair = source[index:index + 2]
        if comment == 'line':
            if char == '\n':
                comment = None
        elif comment == 'block':
            if pair == '*/':
                comment = None
                index += 1
        elif quote:
            if escape:
                escape = False
            elif char == '\\':
                escape = True
            elif char == quote:
                quote = None
        elif pair in {'//', '/*'}:
            comment = 'line' if pair == '//' else 'block'
            index += 1
        elif char in {'\"', "'", '`'}:
            quote = char
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return source[start:index + 1].removeprefix('export ')
        index += 1
    raise AssertionError('Incomplete actual exported UI function: ' + name)


def ui_helper(name, *arguments):
    source = (ROOT / 'web/app.js').read_text()
    functions = '\n'.join(_exported_function(source, item) for item in
                          ('buildCreationRequest', 'infographicPlanSelection'))
    program = functions + '\nprocess.stdout.write(JSON.stringify(' + name + '(...JSON.parse(process.argv[1]))));'
    result = subprocess.run(['node', '-e', program, json.dumps(arguments, ensure_ascii=False)],
                            cwd=ROOT, text=True, capture_output=True, check=True, timeout=15)
    return json.loads(result.stdout)


def _runtime_backend_probe(*args, **kwargs):
    # Resolved from the real rendering namespace after pipeline selection.
    # The callback never initializes a renderer or supplies synthetic pixels.
    return CPULocalBackend


class InfographicPublicSelectionV022(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine import schema, gpu_preflight, visibility
        previous = (schema.validate_plan, gpu_preflight.validate_plan,
                    schema.SCHEMA_PATH, visibility.TOOL)
        def restore():
            schema.validate_plan, gpu_preflight.validate_plan, schema.SCHEMA_PATH, visibility.TOOL = previous
        cls.addClassCleanup(restore)
        env = patch.dict(os.environ, IMAGE_SELECTION_ENV)
        env.start()
        cls.addClassCleanup(env.stop)
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        access = cls.root / 'test-owner.txt'
        access.write_text(OWNER_FIXTURE)
        access.chmod(0o600)
        cls.app = MobileApplication(cls.root / 'runtime', 'http://127.0.0.1:1',
                                    access, disk_floor=0, maximum_duration=180)
        cls.server = BoundedHTTPServer(('127.0.0.1', 0), MobileHandler, cls.app)
        cls.port = cls.server.server_port
        cls.origin = 'http://127.0.0.1:' + str(cls.port)
        cls.app.policy = RequestPolicy(local_port=cls.port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        def stop():
            cls.app.scheduler.close()
            cls.server.shutdown()
            cls.server.server_close()
            cls.thread.join(3)
        cls.addClassCleanup(stop)
        cls.cookie = None
        status, headers, _ = cls.call('POST', '/auth/login', {'password': OWNER_FIXTURE})
        if status != 200:
            raise AssertionError('Actual owner login failed')
        cls.cookie = headers['Set-Cookie'].split(';')[0]
        cls.raw = dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=24,
                       quality='HIGH', pace='FAST_PLUS', style='tension', qa_mode=False,
                       direction_profile='REFERENCE_MASTER', tts=False,
                       subtitles=False, bgm=True, sfx=True)
        cls.selected = cls.create(cls.raw)
        from engine.infographic_planner import parent_qa_plan
        cls.parent = parent_qa_plan(cls.raw)

    @classmethod
    def call(cls, method, path, body=None, *, authenticated=True):
        headers = {'Origin': cls.origin} if method == 'POST' else {}
        if authenticated and cls.cookie:
            headers['Cookie'] = cls.cookie
        if body is not None:
            headers['Content-Type'] = 'application/json'
            body = json.dumps(body, ensure_ascii=False).encode('utf-8')
        connection = http.client.HTTPConnection('127.0.0.1', cls.port, timeout=180)
        try:
            connection.request(method, path, body, headers)
            response = connection.getresponse()
            status, returned, content = response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()
        return status, returned, json.loads(content) if content else {}

    @classmethod
    def create(cls, request):
        status, _, result = cls.call('POST', '/api/projects', deepcopy(request))
        if status != 201:
            raise AssertionError('Actual public project creation failed: ' + json.dumps(result))
        return result

    def approve(self, project):
        pid, version, plan = project['project']['id'], project['version'], project['plan']
        status, _, result = self.call('POST', '/api/projects/' + pid + '/approve',
                                      dict(version=version, plan_hash=plan['plan_hash']))
        self.assertEqual(status, 200, result)
        return pid, version

    def mapped_page(self, plan, scene_index=0):
        from engine.infographic_backend import infographic_command
        from engine.story_progression_backend import story_progression_command
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'actual-scene.json'
            path.write_text(json.dumps(plan['scenes'][scene_index]))
            command = ['node', 'unchanged-renderer', '--scene-json', str(path), '--url',
                       'http://127.0.0.1/static/render_production_earth.html?project=CHECKED',
                       '--browser', '/unchanged/chromium-wrapper', '--gpu-profile', 'nvidia-vulkan']
            mapper = infographic_command if plan['scenes'][scene_index].get('infographic') else story_progression_command
            mapped = mapper(command)
            url_index = command.index('--url') + 1
            self.assertEqual(mapped[:url_index], command[:url_index])
            self.assertEqual(mapped[url_index + 1:], command[url_index + 1:])
            return mapped[url_index]

    def assert_selected(self, project, family='story-progression-v021'):
        plan = project['plan']
        self.assertTrue(plan['gate']['passed'], plan['gate'])
        self.assertTrue(infographic.validate_infographic(plan)['passed'])
        self.assertEqual(plan['metadata']['infographic']['version'], 'v022')
        self.assertEqual(plan['metadata']['infographic']['parent_renderer_family'], family)
        self.assertTrue(all(s['infographic']['version'] == 'v022' and
                            s['infographic']['parent_renderer_family'] == family for s in plan['scenes']))
        self.assertIn('/static/render_infographic_earth.html?', self.mapped_page(plan))
        persisted = self.app.store.get(project['project']['id'], project['version'])['plan']
        self.assertEqual(persisted, plan)
        self.assertEqual(plan['plan_hash'], plan_hash(plan))
        return plan

    def assert_actual_pipeline_backend(self, pid, version):
        from engine import rendering, pipeline_stability
        from engine.infographic_backend import InfographicBackend
        approved = self.app.store.require_approved(pid, version)
        namespace = dict(rendering.render_project.__globals__)
        probe = FunctionType(_runtime_backend_probe.__code__, namespace)
        with patch.object(rendering, 'render_project', probe):
            backend = pipeline_stability.render_project(
                self.app.store.version_path(pid, version), approved, 'http://127.0.0.1:1')
        self.assertIs(backend, InfographicBackend)

    def test_reference_24_http_selects_real_geometry_marker_and_state_contract(self):
        plan = self.assert_selected(self.selected)
        self.assertEqual(plan['duration'], 24)
        self.assertEqual(plan['metadata']['frame_grid']['total_frames'], 720)
        scene = plan['scenes'][0]
        selection = scene['infographic']
        registry = {g['id']: g for g in infographic.load_registry()['geometries']}
        for geometry in selection['geometries']:
            self.assertEqual(geometry, registry[geometry['id']])
        layers = selection['geometry_layers']
        country = [layer for layer in layers if layer['geometry_ref'] == 'COUNTRY_EGY']
        self.assertEqual(len(country), 1)
        self.assertEqual((country[0]['start_frame'], country[0]['end_frame']), (60, 450))
        self.assertIn(registry['COUNTRY_EGY']['geometry_type'], {'Polygon', 'MultiPolygon'})
        for state, start, end in [('CLOSED', 180, 330), ('OPEN', 330, 450)]:
            canal = [layer for layer in layers if layer['state_after'] == state]
            self.assertEqual({l['geometry_ref'] for l in canal},
                             {'CANAL_SUEZ_RIVER_NE10M', 'CANAL_SUEZ_LAKE_NE10M'})
            self.assertEqual({(l['start_frame'], l['end_frame']) for l in canal}, {(start, end)})
        marker = next(m for m in selection['markers'] if m['geometry_ref'] == 'LOCATION_SUEZ_CANAL')
        self.assertEqual((marker['start_frame'], marker['end_frame']), (60, 450))
        self.assertEqual({event['text']['event_title'] for event in selection['events']
                          if event['primary_role'] == 'EVENT_TITLE'}, {'CANAL CLOSED', 'CANAL OPEN'})
        self.assertTrue(all(event['watermark'] == '가정 시나리오' for event in selection['events']
                            if event['state_after'] in {'CLOSED', 'OPEN'}))
        self.assertFalse(plan['options']['tts'])
        self.assert_actual_pipeline_backend(*self.approve(self.selected))

    def test_actual_ui_qa_builder_can_create_again_after_v022_display(self):
        selection = ui_helper('infographicPlanSelection', self.selected['plan'])
        self.assertTrue(selection['valid'])
        self.assertEqual(selection['kind'], 'QA')
        self.assertIn('v022', selection['label'])
        mismatched = deepcopy(self.selected['plan'])
        mismatched['scenes'][0].pop('infographic')
        self.assertFalse(ui_helper('infographicPlanSelection', mismatched)['valid'])
        values = dict(self.raw, infographic_mode='QA')
        request = ui_helper('buildCreationRequest', values)
        self.assertEqual(request['direction_profile'], QA_PROFILE)
        self.assertEqual(request['duration'], 24)
        self.assertTrue(request['qa_mode'])
        self.assertNotIn('script_record', request)
        self.assert_selected(self.create(request))

    def test_explicit_legacy_http_request_keeps_existing_renderer_family(self):
        project = self.create({**self.raw, 'direction_profile': 'FAST_PLUS_LEGACY'})
        plan = project['plan']
        self.assertTrue(plan['gate']['passed'], plan['gate'])
        self.assertNotIn('infographic', plan['metadata'])
        self.assertTrue(all('infographic' not in scene for scene in plan['scenes']))
        self.assertEqual(plan['request']['direction_profile'], 'FAST_PLUS_LEGACY')
        self.assertTrue(all(scene['direction']['preset'] == 'FAST_PLUS_DIRECTOR' for scene in plan['scenes']))

    def test_stored_v021_approval_and_retry_do_not_replan_or_add_v022(self):
        project = self.create({**self.raw, 'direction_profile': 'SECOND_EVENT_ADAPTIVE_WIDE_TEST'})
        plan = project['plan']
        self.assertNotIn('infographic', plan['metadata'])
        self.assertIn('/static/render_story_progression_earth.html?', self.mapped_page(plan))
        pid, version = self.approve(project)
        directory = self.app.store.version_path(pid, version)
        before = (directory / 'scene_plan.json').read_bytes()
        from engine.qa_planner import generate_deployment_plan
        with patch('engine.qa_planner.generate_deployment_plan', wraps=generate_deployment_plan) as planner:
            first = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
            second = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
            planner.assert_not_called()
        self.assertEqual((first[0], second[0]), (202, 202))
        self.assertEqual(first[2]['job_id'], second[2]['job_id'])
        self.assertEqual(first[2]['plan_hash'], plan['plan_hash'])
        self.assertEqual((directory / 'scene_plan.json').read_bytes(), before)
        self.app.scheduler.cancel(first[2]['job_id'])

    def test_existing_short_qa_12_and_15_keep_their_exact_camera_presets(self):
        for duration, preset in [(12, 'SINGLE_EVENT_CAMERA_TEST'),
                                 (15, 'SINGLE_EVENT_RETURN_TO_WIDE_TEST')]:
            with self.subTest(duration=duration):
                project = self.create({**self.raw, 'duration': duration, 'qa_mode': True})
                plan = project['plan']
                self.assertEqual(plan['request']['direction_profile'], preset)
                self.assertEqual(plan['metadata']['camera_test_preset'], preset)
                self.assertNotIn('infographic', plan['metadata'])
                self.assertEqual(plan['metadata']['frame_grid']['total_frames'], duration * 30)
                self.assertTrue(plan['gate']['passed'], plan['gate'])

    def test_actual_production_ui_request_uses_measured_planner_saved_plan_and_new_page(self):
        from engine.infographic_planner import generate_production_infographic
        script = json.loads((ROOT / 'deployment/gcube/fixtures/infographic_production_v022.json').read_text())
        request = ui_helper('buildCreationRequest', {**self.raw, 'infographic_mode': 'PRODUCTION'}, script)
        self.assertEqual(request['direction_profile'], PRODUCTION_PROFILE)
        self.assertEqual(request['script_record'], script)
        self.assertNotIn('directory', request)
        self.assertNotIn('provider', request)
        with patch('engine.infographic_planner.generate_production_infographic',
                   wraps=generate_production_infographic) as planner:
            project = self.create(request)
        planner.assert_called_once()
        plan = self.assert_selected(project, 'production-earth-v1')
        timeline = plan['metadata']['semantic_timeline']
        self.assertTrue(timeline['passed'])
        self.assertFalse(timeline['word_alignment'])
        self.assertEqual(len(plan['scenes']), len(timeline['segments']))
        self.assertEqual(plan['metadata']['authored_script'], script)
        self.assertEqual(timeline['script_sha256'], hashlib.sha256(script['text'].encode()).hexdigest())
        self.assertEqual(plan['duration'], timeline['total_frames'] / 30)
        self.assertNotEqual(timeline['total_frames'], 720)
        for segment, scene in zip(timeline['segments'], plan['scenes']):
            self.assertGreater(segment['sample_count'], 0)
            self.assertEqual(scene['frame_count'], segment['visual_window']['frame_count'])
            self.assertEqual(scene['infographic']['events'][0]['semantic_segment_ref'], segment['id'])
            self.assertEqual(scene['infographic']['events'][0]['claim_id'], segment['claim_ids'][0])
        voice = Path(plan['metadata']['semantic_timeline_directory']) / timeline['voice']['file']
        self.assertTrue(voice.is_file())
        self.assertEqual(hashlib.sha256(voice.read_bytes()).hexdigest(), timeline['voice']['sha256'])
        self.assertTrue(voice.is_relative_to(self.app.store.root))
        # A cold process must admit the saved measured plan independently of
        # default creation ENV, without synthesizing or regenerating it.
        child = r'''
import hashlib,json,sys
from pathlib import Path
from unittest.mock import patch
from deployment.mobile_server import MobileApplication
from engine import schema
args=json.loads(sys.argv[1])
with patch('engine.infographic_planner.generate_production_infographic',side_effect=AssertionError('No restart synthesis')) as measured, patch('engine.qa_planner.generate_deployment_plan',side_effect=AssertionError('No restart planning')) as planner:
 app=MobileApplication(args['state'],'http://127.0.0.1:1',args['access'],disk_floor=0)
 try:
  saved=app.store.get(args['pid'],args['version'])['plan']
  selected=app.check_profile_selection(args['pid'],args['version'],saved)
  gate=schema.validate_plan(saved)
  voice=Path(saved['metadata']['semantic_timeline_directory'])/saved['metadata']['semantic_timeline']['voice']['file']
  measured.assert_not_called();planner.assert_not_called()
  print(json.dumps(dict(profile=selected,gate_passed=gate['passed'],voice_sha256=hashlib.sha256(voice.read_bytes()).hexdigest())))
 finally:app.scheduler.close()
'''
        environment = dict(os.environ)
        environment.pop('WORLD_ENGINE_MAP_INFOGRAPHIC_VERSION', None)
        arguments = dict(state=str(self.app.state_root), access=str(self.root / 'test-owner.txt'),
                         pid=project['project']['id'], version=project['version'])
        restart = subprocess.run([sys.executable, '-c', child, json.dumps(arguments)],
                                 cwd=ROOT, env=environment, text=True, capture_output=True,
                                 check=True, timeout=180)
        cold = json.loads(restart.stdout)
        self.assertEqual(cold['profile'], PRODUCTION_PROFILE)
        self.assertTrue(cold['gate_passed'])
        self.assertEqual(cold['voice_sha256'], timeline['voice']['sha256'])
        pid, version = self.approve(project)
        self.assert_actual_pipeline_backend(pid, version)
        before = plan_hash(plan)
        status, _, ticket = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
        self.assertEqual(status, 202, ticket)
        self.assertEqual(ticket['plan_hash'], before)
        self.assertTrue(voice.is_file())
        self.app.scheduler.cancel(ticket['job_id'])

    def test_actual_pre_fix_v022_fixture_stays_source_valid_and_hash_stable_on_retry(self):
        # Exact planner output captured before any selection fix, not a plan
        # rebuilt by today's planner. ProjectStore normalizes the project,
        # version and render offsets once on installation into the test store.
        path = ROOT / 'tests/fixtures/infographic_public_selection_v022/approved_before_selection_fix.json'
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         '2b35f188bf9690d67d7e396b7f316fbdf8a15b2605aad928479c6ccf801afbf0')
        frozen = json.loads(raw)
        source_pins = deepcopy(frozen['metadata']['infographic']['source_hashes'])
        self.assertTrue(infographic.validate_infographic(frozen)['passed'])
        project = self.app.store.create(deepcopy(self.raw), deepcopy(frozen))
        plan = self.assert_selected(project)
        self.assertEqual(plan['metadata']['infographic']['source_hashes'], source_pins)
        pid, version = self.approve(project)
        directory = self.app.store.version_path(pid, version)
        self.assertFalse((directory / 'public-selection.json').exists())
        before = (directory / 'scene_plan.json').read_bytes()
        digest = plan['plan_hash']
        from engine.qa_planner import generate_deployment_plan
        with patch('engine.qa_planner.generate_deployment_plan', wraps=generate_deployment_plan) as planner:
            first = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
            self.assertEqual(first[0], 202, first[2])
            self.app.scheduler.cancel(first[2]['job_id'])
            retry = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
            planner.assert_not_called()
        self.assertEqual(retry[0], 202, retry[2])
        self.assertNotEqual(first[2]['job_id'], retry[2]['job_id'])
        self.assertEqual((first[2]['plan_hash'], retry[2]['plan_hash']), (digest, digest))
        self.assertEqual((directory / 'scene_plan.json').read_bytes(), before)
        self.assertEqual(self.app.store.require_approved(pid, version)['plan_hash'], digest)
        self.assertEqual(path.read_bytes(), raw)
        self.app.scheduler.cancel(retry[2]['job_id'])

    def test_metadata_scene_and_receipt_mismatches_reject_active_approval_and_render(self):
        project = self.create(ui_helper('buildCreationRequest', {**self.raw, 'infographic_mode': 'QA'}))
        pid, version = self.approve(project)
        status, _, ticket = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
        self.assertEqual(status, 202, ticket)
        directory = self.app.store.version_path(pid, version)
        plan_file, approval_file = directory / 'scene_plan.json', directory / 'approval.json'
        receipt_file = directory / 'public-selection.json'
        original_files = {p: p.read_bytes() for p in (plan_file, approval_file, receipt_file)}
        original_ticket = deepcopy(self.app.scheduler.tickets[ticket['job_id']])
        original = json.loads(original_files[plan_file])
        def missing_scene(plan):
            plan['scenes'][0].pop('infographic')
        def wrong_metadata_version(plan):
            plan['metadata']['infographic']['version'] = 'v021'
        cases = [('missing scene', missing_scene), ('wrong metadata version', wrong_metadata_version)]
        try:
            for description, mutate in cases:
                with self.subTest(mismatch=description):
                    bad = deepcopy(original)
                    mutate(bad)
                    bad['plan_hash'] = plan_hash(bad)
                    atomic_json(plan_file, bad)
                    approval = json.loads(original_files[approval_file])
                    approval['plan_hash'] = bad['plan_hash']
                    atomic_json(approval_file, approval)
                    # Matching hashes deliberately remove hash-only rejection
                    # and exercise active idempotent approval admission.
                    self.app.scheduler.tickets[ticket['job_id']]['plan_hash'] = bad['plan_hash']
                    for endpoint, data in [('approve', dict(version=version, plan_hash=bad['plan_hash'])),
                                           ('render', dict(version=version))]:
                        result = self.call('POST', '/api/projects/' + pid + '/' + endpoint, data)
                        self.assertEqual(result[0], 409, result[2])
                        self.assertEqual(result[2]['error']['code'], 'INFOGRAPHIC_SELECTION_MISMATCH')
            plan_file.write_bytes(original_files[plan_file])
            approval_file.write_bytes(original_files[approval_file])
            self.app.scheduler.tickets[ticket['job_id']] = deepcopy(original_ticket)
            receipt = json.loads(original_files[receipt_file])
            receipt['effective_profile'] = PRODUCTION_PROFILE
            private_json(receipt_file, receipt)
            for endpoint, data in [('approve', dict(version=version, plan_hash=original['plan_hash'])),
                                   ('render', dict(version=version))]:
                result = self.call('POST', '/api/projects/' + pid + '/' + endpoint, data)
                self.assertEqual(result[0], 409, result[2])
                self.assertEqual(result[2]['error']['code'], 'INFOGRAPHIC_SELECTION_MISMATCH')
        finally:
            for path, raw in original_files.items():
                path.write_bytes(raw)
            self.app.scheduler.tickets[ticket['job_id']] = original_ticket
            self.app.scheduler.cancel(ticket['job_id'])

    def test_unauthenticated_production_is_rejected_before_measured_provider(self):
        from engine.infographic_planner import generate_production_infographic
        with patch('engine.infographic_planner.generate_production_infographic',
                   wraps=generate_production_infographic) as planner:
            status, _, result = self.call('POST', '/api/projects',
                {'direction_profile': PRODUCTION_PROFILE, 'script_record': {}}, authenticated=False)
        self.assertEqual(status, 401, result)
        self.assertEqual(result['error']['code'], 'AUTH_REQUIRED')
        planner.assert_not_called()

    def test_public_production_never_accepts_caller_paths_provider_or_render_controls(self):
        script = json.loads((ROOT / 'deployment/gcube/fixtures/infographic_production_v022.json').read_text())
        for field, value in [('directory', '/tmp/forged-output'), ('provider', 'forged'),
                             ('fps', 60), ('scene_json', '/tmp/forged-scene'), ('render_command', 'forged')]:
            with self.subTest(field=field):
                status, _, result = self.call('POST', '/api/projects', dict(
                    direction_profile=PRODUCTION_PROFILE, script_record=script, **{field: value}))
                self.assertEqual(status, 400, result)
                self.assertEqual(result['error']['code'], 'UNSUPPORTED_INPUT')

    def test_selected_qa_keeps_all_720_camera_values_and_parent_material_inputs(self):
        selected = self.selected['plan']
        for old, scene in zip(self.parent['scenes'], selected['scenes']):
            self.assertEqual(infographic.parent._camera_snapshot(scene), infographic.parent._camera_snapshot(old))
            self.assertEqual(infographic.parent._quality_snapshot(scene), infographic.parent._quality_snapshot(old))
            self.assertEqual(infographic.parent._source_snapshot(scene), infographic.parent._source_snapshot(old))
        self.assertEqual(selected['metadata']['frame_grid'], self.parent['metadata']['frame_grid'])
        with tempfile.TemporaryDirectory() as directory:
            outputs = []
            for name, plan in [('parent', self.parent), ('selected', selected)]:
                path = Path(directory) / (name + '.json')
                path.write_text(json.dumps(plan))
                result = subprocess.run(['node', 'tools/test_second_event_camera.mjs', str(path)],
                    cwd=ROOT, text=True, capture_output=True, check=True, timeout=45)
                outputs.append(json.loads(result.stdout)['audits'])
        self.assertEqual([len(rows) for rows in outputs], [720, 720])
        for frame, (before, after) in enumerate(zip(*outputs)):
            with self.subTest(frame=frame):
                for key in ('cameraPosition', 'cameraQuaternion', 'cameraFov', 'cameraState'):
                    self.assertEqual(before[key], after[key])

    def test_all_frozen_parent_files_and_native_source_bindings_remain_exact(self):
        manifest = json.loads((ROOT / 'deployment/gcube/infographic_release_manifest.json').read_text())
        records = manifest['frozen_parent_records']
        self.assertEqual(len(records), 27)
        for record in records:
            with self.subTest(path=record['path']):
                path = ROOT / record['path']
                self.assertEqual(path.stat().st_size, record['size'])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record['sha256'])
        registry = infographic.load_registry()
        self.assertTrue(infographic.validate_registry(registry)['passed'])
        for name in ('registry.json', 'SOURCES.json', 'profile.json'):
            self.assertEqual((ROOT / 'data/infographic/v022' / name).read_bytes(),
                             (ROOT / 'web/infographic/v022' / name).read_bytes())


if __name__ == '__main__':
    unittest.main()
