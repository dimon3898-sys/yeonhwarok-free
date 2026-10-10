"""Public BOLD selection, saved-plan handoff and actual mobile DOM integration.

The real HTTP gateway, geographic planners, persistence gates, renderer backend
selector and command mapper run here. Neither a video renderer nor gcube is
started. Browser checks use local protocol responses only for presentation.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import http.client
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import threading
from types import FunctionType
import unittest
from unittest.mock import patch

from deployment.mobile_server import BoundedHTTPServer, MobileApplication, MobileHandler
from deployment.security import RequestPolicy
from engine import infographic_contract
from engine.public_infographic_selection import QA_PROFILE, PRODUCTION_PROFILE
from engine.storage import EngineError, atomic_json, plan_hash


ROOT = Path(__file__).resolve().parents[1]
BOLD = 'BOLD_INFOGRAPHIC_V023'
LEGACY = 'V022_LEGACY'
FROZEN_HELPERS = runpy.run_path(str(ROOT / 'tests/test_infographic_public_selection_v022.py'))
IMAGE_ENV = {**FROZEN_HELPERS['IMAGE_SELECTION_ENV'],
             'WORLD_ENGINE_INFOGRAPHIC_VISUAL_PROFILE': BOLD}
OWNER = 'isolated-v023-public-test-owner-value'


def ui_helper(name, *arguments):
    # Real native MultiPolygon data can exceed Linux's per-argument limit.
    # Feed the unchanged actual exported UI functions via stdin rather than
    # replacing the plan with a smaller synthetic metadata-only fixture.
    source = (ROOT / 'web/app.js').read_text()
    functions = '\n'.join(FROZEN_HELPERS['_exported_function'](source, item) for item in
                          ('buildCreationRequest', 'infographicPlanSelection'))
    program = functions + '\nprocess.stdout.write(JSON.stringify(' + name + \
        "(...JSON.parse(require('node:fs').readFileSync(0, 'utf8')))));"
    result = subprocess.run(['node', '-e', program],
                            input=json.dumps(arguments, ensure_ascii=False), cwd=ROOT,
                            text=True, capture_output=True, check=True, timeout=30)
    return json.loads(result.stdout)


def _selected_backend_without_render(*args, **kwargs):
    return CPULocalBackend


class BoldPublicSelectionV023(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from engine import schema, gpu_preflight, visibility
        previous = schema.validate_plan, gpu_preflight.validate_plan, schema.SCHEMA_PATH, visibility.TOOL
        def restore():
            schema.validate_plan, gpu_preflight.validate_plan, schema.SCHEMA_PATH, visibility.TOOL = previous
        cls.addClassCleanup(restore)
        environment = patch.dict(os.environ, IMAGE_ENV)
        environment.start()
        cls.addClassCleanup(environment.stop)
        cls.temporary = tempfile.TemporaryDirectory(prefix='bold-public-v023-')
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        cls.access = cls.root / 'test-owner.txt'
        cls.access.write_text(OWNER)
        cls.access.chmod(0o600)
        cls.app = MobileApplication(cls.root / 'runtime', 'http://127.0.0.1:1',
                                    cls.access, disk_floor=0, maximum_duration=180)
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
        status, headers, result = cls.call('POST', '/auth/login', {'password': OWNER})
        if status != 200:
            raise AssertionError('Actual BOLD test owner login failed: ' + str(result))
        cls.cookie = headers['Set-Cookie'].split(';')[0]
        cls.raw = dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=24,
                       quality='HIGH', pace='FAST_PLUS', style='tension', qa_mode=False,
                       direction_profile='REFERENCE_MASTER', tts=False,
                       subtitles=False, bgm=True, sfx=True)
        cls.selected = cls.create(cls.raw)
        cls.off = cls.create({**cls.raw, 'infographic_visual_profile': LEGACY})

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
            raise AssertionError('Actual BOLD public creation failed: ' + json.dumps(result, ensure_ascii=False))
        return result

    def assert_bold(self, project, family='story-progression-v021'):
        from engine.bold_infographic import validate_bold_infographic
        plan = project['plan']
        self.assertTrue(plan['gate']['passed'], plan['gate'])
        self.assertTrue(infographic_contract.validate_infographic(plan)['passed'])
        self.assertTrue(validate_bold_infographic(plan)['passed'])
        self.assertEqual(plan['metadata']['infographic']['version'], 'v022')
        self.assertEqual(plan['metadata']['infographic']['parent_renderer_family'], family)
        metadata = plan['metadata']['bold_infographic']
        self.assertEqual((metadata['version'], metadata['profile_id']), ('v023', BOLD))
        for scene in plan['scenes']:
            self.assertEqual(scene['infographic']['parent_renderer_family'], family)
            child = scene['bold_infographic']
            self.assertEqual((child['version'], child['profile_id']), ('v023', BOLD))
            self.assertEqual(child['profile_sha256'], metadata['profile_sha256'])
            self.assertEqual(child['registry_sha256'], metadata['registry_sha256'])
        self.assertEqual(plan['plan_hash'], plan_hash(plan))
        persisted = self.app.store.get(project['project']['id'], project['version'])['plan']
        self.assertEqual(persisted, plan)
        return plan

    def mapped_page(self, plan, index=0):
        from engine.infographic_backend import infographic_command
        with tempfile.TemporaryDirectory(prefix='bold-command-v023-') as directory:
            path = Path(directory) / 'actual-scene.json'
            path.write_text(json.dumps(plan['scenes'][index]))
            command = ['node', 'unchanged-renderer', '--scene-json', str(path), '--url',
                       'http://127.0.0.1/static/render_production_earth.html?project=CHECKED',
                       '--browser', '/unchanged/chromium-wrapper', '--gpu-profile', 'nvidia-vulkan']
            mapped = infographic_command(command)
            offset = command.index('--url') + 1
            self.assertEqual(mapped[:offset], command[:offset])
            self.assertEqual(mapped[offset + 1:], command[offset + 1:])
            return mapped[offset]

    def approve(self, project):
        pid, version, plan = project['project']['id'], project['version'], project['plan']
        status, _, result = self.call('POST', '/api/projects/' + pid + '/approve',
                                      {'version': version, 'plan_hash': plan['plan_hash']})
        self.assertEqual(status, 200, result)
        return pid, version

    @contextmanager
    def saved_plan_variant(self, project, mutation):
        path = self.app.store.version_path(project['project']['id'], project['version']) / 'scene_plan.json'
        original = path.read_bytes()
        candidate = deepcopy(project['plan'])
        mutation(candidate)
        atomic_json(path, candidate)
        try:
            yield candidate
        finally:
            path.write_bytes(original)

    def test_image_default_selects_bold_from_real_24_second_reference_plan(self):
        plan = self.assert_bold(self.selected)
        self.assertEqual(plan['duration'], 24)
        self.assertEqual(plan['metadata']['frame_grid']['total_frames'], 720)
        self.assertNotIn('infographic_visual_profile', plan['request'])
        self.assertIn('/static/render_bold_infographic_earth.html?', self.mapped_page(plan))

    def test_explicit_ui_bold_option_reaches_real_http_scene_contract(self):
        request = ui_helper('buildCreationRequest', {**self.raw, 'infographic_mode': 'QA',
                            'infographic_visual_profile': BOLD})
        self.assertEqual(request['direction_profile'], QA_PROFILE)
        self.assertEqual(request['infographic_visual_profile'], BOLD)
        plan = self.assert_bold(self.create(request))
        self.assertEqual(plan['metadata']['frame_grid']['total_frames'], 720)

    def test_actual_ui_badge_uses_scene_and_metadata_contract_not_request_profile(self):
        plan = self.assert_bold(self.selected)
        self.assertEqual(plan['request']['direction_profile'], 'SECOND_EVENT_ADAPTIVE_WIDE_TEST')
        presentation = ui_helper('infographicPlanSelection', plan)
        self.assertTrue(presentation['valid'])
        self.assertEqual(presentation['label'], 'INFOGRAPHIC v023 · BOLD INFOGRAPHIC · QA')
        self.assertEqual(presentation['kind'], 'QA')

    def test_legacy_visual_option_keeps_frozen_v022_overlay_contract_and_page(self):
        plan = self.off['plan']
        self.assertTrue(plan['gate']['passed'], plan['gate'])
        self.assertTrue(infographic_contract.validate_infographic(plan)['passed'])
        self.assertNotIn('bold_infographic', plan['metadata'])
        self.assertTrue(all('bold_infographic' not in scene for scene in plan['scenes']))
        self.assertIn('/static/render_infographic_earth.html?', self.mapped_page(plan))
        self.assertEqual(ui_helper('infographicPlanSelection', plan)['label'], 'INFOGRAPHIC v022 · QA')

    def test_complete_scene_inputs_except_additive_child_match_off_baseline(self):
        # Full unchanged Scene data includes the frozen 720-frame camera/timing
        # contract, regional LOD, lighting, marker/state/text and audio options.
        bold = self.assert_bold(self.selected)
        off = self.off['plan']
        self.assertEqual(len(bold['scenes']), len(off['scenes']))
        for after, before in zip(bold['scenes'], off['scenes']):
            stripped = {key: value for key, value in after.items() if key != 'bold_infographic'}
            self.assertEqual(stripped, before)
        self.assertEqual(bold['metadata']['infographic'], off['metadata']['infographic'])
        self.assertEqual(bold['options'], off['options'])
        self.assertEqual(bold['metadata']['frame_grid'], off['metadata']['frame_grid'])

    def test_bold_geometry_records_are_actual_registered_polygons(self):
        plan = self.assert_bold(self.selected)
        registry = {item['id']: item for item in infographic_contract.load_registry()['geometries']}
        for scene in plan['scenes']:
            child = scene['bold_infographic']
            self.assertTrue(child['geometries'])
            self.assertEqual(set(child['geometry_ids']), {item['id'] for item in child['geometries']})
            for item in child['geometries']:
                self.assertEqual(item, registry[item['id']])
                self.assertIn(item['geometry_type'], {'Polygon', 'MultiPolygon'})
        self.assertIn('COUNTRY_EGY', plan['scenes'][0]['bold_infographic']['geometry_ids'])

    def test_default_bold_does_not_promote_explicit_legacy_director(self):
        legacy = self.create({**self.raw, 'direction_profile': 'FAST_PLUS_LEGACY'})['plan']
        self.assertNotIn('infographic', legacy['metadata'])
        self.assertNotIn('bold_infographic', legacy['metadata'])
        self.assertTrue(all('infographic' not in scene and 'bold_infographic' not in scene
                            for scene in legacy['scenes']))
        self.assertEqual(legacy['request']['direction_profile'], 'FAST_PLUS_LEGACY')

    def test_explicit_bold_cannot_silently_fall_back_to_legacy_planning(self):
        status, _, result = self.call('POST', '/api/projects',
            {**self.raw, 'direction_profile': 'FAST_PLUS_LEGACY', 'infographic_visual_profile': BOLD})
        self.assertEqual(status, 400, result)
        self.assertEqual(result['error']['code'], 'BOLD_INFOGRAPHIC_REQUIRES_V022')

    def test_invalid_visual_profile_is_rejected_before_any_planning(self):
        from engine.qa_planner import generate_deployment_plan
        with patch('engine.qa_planner.generate_deployment_plan', wraps=generate_deployment_plan) as planner:
            for value in ('UNKNOWN', 'AUTO', [], {}, 1, None):
                with self.subTest(value=value):
                    status, _, result = self.call('POST', '/api/projects',
                        {**self.raw, 'infographic_visual_profile': value})
                    self.assertEqual(status, 400, result)
                    self.assertEqual(result['error']['code'], 'INVALID_OPTION')
            planner.assert_not_called()

    def test_short_qa_presets_do_not_gain_bold_or_change_timing(self):
        for duration, preset in ((12, 'SINGLE_EVENT_CAMERA_TEST'),
                                 (15, 'SINGLE_EVENT_RETURN_TO_WIDE_TEST')):
            with self.subTest(duration=duration):
                plan = self.create({**self.raw, 'duration': duration, 'qa_mode': True})['plan']
                self.assertTrue(plan['gate']['passed'], plan['gate'])
                self.assertEqual(plan['metadata']['camera_test_preset'], preset)
                self.assertEqual(plan['metadata']['frame_grid']['total_frames'], duration * 30)
                self.assertNotIn('bold_infographic', plan['metadata'])

    def test_approve_render_retry_keep_exact_saved_bold_and_selection_receipt(self):
        project = self.create({**self.raw, 'infographic_visual_profile': BOLD})
        self.assert_bold(project)
        pid, version = self.approve(project)
        directory = self.app.store.version_path(pid, version)
        original = (directory / 'scene_plan.json').read_bytes()
        receipt = json.loads((directory / 'public-selection.json').read_text())
        self.assertEqual(receipt['visual_profile'], BOLD)
        from engine.qa_planner import generate_deployment_plan
        with patch('engine.qa_planner.generate_deployment_plan', wraps=generate_deployment_plan) as planner:
            first = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
            second = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
            planner.assert_not_called()
        self.assertEqual((first[0], second[0]), (202, 202))
        self.assertEqual(first[2]['job_id'], second[2]['job_id'])
        self.assertEqual(first[2]['plan_hash'], project['plan']['plan_hash'])
        self.assertEqual((directory / 'scene_plan.json').read_bytes(), original)
        # The durable worker rechecks this exact saved contract before invoking
        # any runner. The worker is deliberately not started in this test.
        admitted = self.app.scheduler._plan(first[2])
        self.assertEqual(admitted, project['plan'])
        self.assertIsNone(self.app.scheduler.thread)
        self.app.scheduler.cancel(first[2]['job_id'])

    def test_saved_v022_off_project_is_not_promoted_on_approval_or_retry(self):
        project = self.create({**self.raw, 'infographic_visual_profile': LEGACY})
        pid, version = self.approve(project)
        directory = self.app.store.version_path(pid, version)
        before = (directory / 'scene_plan.json').read_bytes()
        first = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
        self.assertEqual(first[0], 202, first[2])
        admitted = self.app.scheduler._plan(first[2])
        self.assertNotIn('bold_infographic', admitted['metadata'])
        self.assertEqual((directory / 'scene_plan.json').read_bytes(), before)
        self.assertIn('/static/render_infographic_earth.html?', self.mapped_page(admitted))
        self.app.scheduler.cancel(first[2]['job_id'])

    def test_historical_v022_input_without_visual_field_stays_legacy_in_new_image(self):
        # Reproduce the persisted input/receipt shape that predated visual
        # selection. New image ENV affects creation, never this saved project.
        project = self.create({**self.raw, 'infographic_visual_profile': LEGACY})
        pid, version = project['project']['id'], project['version']
        input_path = self.app.store.path(pid) / 'prompt/request_v001.json'
        original_input = json.loads(input_path.read_text())
        original_input.pop('infographic_visual_profile')
        atomic_json(input_path, original_input)
        directory = self.app.store.version_path(pid, version)
        receipt = json.loads((directory / 'public-selection.json').read_text())
        self.assertNotIn('visual_profile', receipt)
        before = (directory / 'scene_plan.json').read_bytes()
        self.assertEqual(self.app.check_profile_selection(pid, version), QA_PROFILE)
        self.approve(project)
        status, _, ticket = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
        self.assertEqual(status, 202, ticket)
        admitted = self.app.scheduler._plan(ticket)
        self.assertNotIn('bold_infographic', admitted['metadata'])
        self.assertEqual((directory / 'scene_plan.json').read_bytes(), before)
        self.app.scheduler.cancel(ticket['job_id'])

    def test_partial_bold_source_contract_blocks_approval_and_render_queue(self):
        project = self.create({**self.raw, 'infographic_visual_profile': BOLD})
        pid, version = project['project']['id'], project['version']
        with self.saved_plan_variant(project, lambda plan: plan['scenes'][0].pop('bold_infographic')):
            with patch.object(self.app.scheduler, 'submit') as submit:
                approved = self.call('POST', '/api/projects/' + pid + '/approve',
                    {'version': version, 'plan_hash': project['plan']['plan_hash']})
                queued = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
                submit.assert_not_called()
            self.assertEqual((approved[0], queued[0]), (409, 409))
            self.assertEqual(approved[2]['error']['code'], 'BOLD_INFOGRAPHIC_PLAN_INVALID')
            self.assertEqual(queued[2]['error']['code'], 'BOLD_INFOGRAPHIC_PLAN_INVALID')

    def test_saved_bold_receipt_prevents_stripping_entire_child_to_legacy(self):
        def strip(plan):
            plan['metadata'].pop('bold_infographic')
            for scene in plan['scenes']:
                scene.pop('bold_infographic')
        project = self.create({**self.raw, 'infographic_visual_profile': BOLD})
        with self.saved_plan_variant(project, strip):
            with self.assertRaises(EngineError) as caught:
                self.app.check_profile_selection(project['project']['id'], project['version'])
        self.assertEqual(caught.exception.code, 'BOLD_INFOGRAPHIC_SELECTION_MISMATCH')

    def test_source_pin_tampering_cannot_select_bold_page(self):
        from engine.infographic_backend import infographic_command
        plan = deepcopy(self.selected['plan'])
        plan['scenes'][0]['bold_infographic']['profile_sha256'] = '0' * 64
        with tempfile.TemporaryDirectory(prefix='bold-forged-command-v023-') as directory:
            scene = Path(directory) / 'scene.json'
            scene.write_text(json.dumps(plan['scenes'][0]))
            with self.assertRaises(RuntimeError) as caught:
                infographic_command(['node', 'renderer', '--scene-json', str(scene), '--url',
                    'http://127.0.0.1/static/render_production_earth.html'])
            self.assertEqual(str(caught.exception), 'BOLD_INFOGRAPHIC_SCENE_SOURCE_MISMATCH')

    def test_orphan_or_null_child_contract_never_bypasses_public_admission(self):
        from engine.public_infographic_selection import require_infographic_selection
        plain = dict(metadata={}, scenes=[dict(scene_id='S001')], request={})
        for placement in ('metadata', 'scene'):
            for value in (None, {}, {'version': 'v023', 'profile_id': BOLD}):
                with self.subTest(placement=placement, value=value):
                    plan = deepcopy(plain)
                    target = plan['metadata'] if placement == 'metadata' else plan['scenes'][0]
                    target['bold_infographic'] = value
                    with self.assertRaises(EngineError) as caught:
                        require_infographic_selection(plan)
                    self.assertEqual(caught.exception.code, 'INFOGRAPHIC_SELECTION_MISMATCH')
                    self.assertFalse(ui_helper('infographicPlanSelection', plan)['valid'])
        for placement in ('metadata', 'scene'):
            with self.subTest(null_child=placement):
                plan = deepcopy(self.selected['plan'])
                target = plan['metadata'] if placement == 'metadata' else plan['scenes'][0]
                target['bold_infographic'] = None
                with self.assertRaises(EngineError) as caught:
                    require_infographic_selection(plan)
                self.assertEqual(caught.exception.code, 'BOLD_INFOGRAPHIC_PLAN_INVALID')
                self.assertFalse(ui_helper('infographicPlanSelection', plan)['valid'])

    def test_actual_pipeline_backend_remains_infographic_and_maps_bold_child(self):
        from engine import rendering, pipeline_stability
        from engine.infographic_backend import InfographicBackend
        pid, version = self.approve(self.selected)
        approved = self.app.store.require_approved(pid, version)
        probe = FunctionType(_selected_backend_without_render.__code__, dict(rendering.render_project.__globals__))
        with patch.object(rendering, 'render_project', probe):
            backend = pipeline_stability.render_project(
                self.app.store.version_path(pid, version), approved, 'http://127.0.0.1:1')
        self.assertIs(backend, InfographicBackend)
        self.assertIn('/static/render_bold_infographic_earth.html?', self.mapped_page(approved))

    def test_actual_production_ui_api_planner_uses_bold_without_replacing_measured_timeline(self):
        from engine.infographic_planner import generate_production_infographic
        script = json.loads((ROOT / 'deployment/gcube/fixtures/infographic_production_v022.json').read_text())
        request = ui_helper('buildCreationRequest', {'infographic_mode': 'PRODUCTION',
            'infographic_visual_profile': BOLD}, script)
        self.assertEqual(request, {'direction_profile': PRODUCTION_PROFILE,
                                 'script_record': script, 'infographic_visual_profile': BOLD})
        with patch('engine.infographic_planner.generate_production_infographic',
                   wraps=generate_production_infographic) as planner:
            project = self.create(request)
        planner.assert_called_once()
        plan = self.assert_bold(project, family='production-earth-v1')
        timeline = plan['metadata']['semantic_timeline']
        self.assertTrue(timeline['passed'])
        self.assertEqual(plan['duration'], timeline['total_frames'] / 30)
        self.assertNotEqual(timeline['total_frames'], 720)
        self.assertEqual(plan['metadata']['authored_script'], script)
        self.assertEqual(timeline['script_sha256'], hashlib.sha256(script['text'].encode()).hexdigest())
        voice = Path(plan['metadata']['semantic_timeline_directory']) / timeline['voice']['file']
        self.assertTrue(voice.is_relative_to(self.app.store.root))
        self.assertEqual(hashlib.sha256(voice.read_bytes()).hexdigest(), timeline['voice']['sha256'])
        self.assertIn('/static/render_bold_infographic_earth.html?', self.mapped_page(plan))
        self.assertEqual(ui_helper('infographicPlanSelection', plan)['kind'], 'PRODUCTION')
        from engine import schema, semantic_timeline
        direct_gate = semantic_timeline.validate_production_plan(plan)
        self.assertTrue(direct_gate['passed'], direct_gate)
        self.assertTrue(schema.validate_plan(plan)['passed'])
        pid, version = self.approve(project)
        directory = self.app.store.version_path(pid, version)
        before = (directory / 'scene_plan.json').read_bytes()
        status, _, ticket = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
        self.assertEqual(status, 202, ticket)
        admitted = self.app.scheduler._plan(ticket)
        self.assertEqual(admitted, plan)
        self.assertTrue(semantic_timeline.validate_production_plan(admitted)['passed'])
        self.assertEqual((directory / 'scene_plan.json').read_bytes(), before)
        self.assertIsNone(self.app.scheduler.thread)
        self.app.scheduler.cancel(ticket['job_id'])
        # Strict old Production schema does not know the new visual field.
        # The additive runtime must admit a proved child before presenting an
        # unchanged parent view; it cannot merely ignore every child field.
        with self.saved_plan_variant(project, lambda value: value['scenes'][0].pop('bold_infographic')) as broken:
            self.assertFalse(semantic_timeline.validate_production_plan(broken)['passed'])
            rejected = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
            self.assertEqual(rejected[0], 409, rejected[2])
            self.assertEqual(rejected[2]['error']['code'], 'BOLD_INFOGRAPHIC_PLAN_INVALID')

    def test_cold_process_admits_saved_bold_without_default_creation_setting(self):
        project = self.selected
        source = r'''
import json,sys
from unittest.mock import patch
from deployment.mobile_server import MobileApplication
from engine import schema
from engine.infographic_backend import infographic_command
args=json.loads(sys.argv[1])
with patch('engine.qa_planner.generate_deployment_plan',side_effect=AssertionError('No replan')) as planner:
 app=MobileApplication(args['state'],'http://127.0.0.1:1',args['access'],disk_floor=0)
 try:
  saved=app.store.get(args['pid'],args['version'])['plan']
  profile=app.check_profile_selection(args['pid'],args['version'],saved)
  gate=schema.validate_plan(saved)
  scene=app.store.version_path(args['pid'],args['version'])/'scene_json/S001.json'
  # Import after the checked cold handoff installs the additive runtime mapper.
  from engine.infographic_backend import infographic_command
  mapped=infographic_command(['node','renderer','--scene-json',str(scene),'--url','http://127.0.0.1/static/render_production_earth.html'])
  planner.assert_not_called()
  print(json.dumps(dict(profile=profile,passed=gate['passed'],url=mapped[-1],bold=saved['metadata']['bold_infographic']['version'])))
 finally:app.scheduler.close()
'''
        environment = dict(os.environ)
        environment['WORLD_ENGINE_INFOGRAPHIC_VISUAL_PROFILE'] = LEGACY
        arguments = dict(state=str(self.app.state_root), access=str(self.access),
                         pid=project['project']['id'], version=project['version'])
        process = subprocess.run([sys.executable, '-c', source, json.dumps(arguments)],
                                 cwd=ROOT, env=environment, text=True, capture_output=True, timeout=180)
        self.assertEqual(process.returncode, 0, process.stderr[-6000:])
        result = json.loads(process.stdout)
        self.assertTrue(result['passed'])
        self.assertEqual((result['profile'], result['bold']), (QA_PROFILE, 'v023'))
        self.assertIn('/static/render_bold_infographic_earth.html', result['url'])


class BoldMobileBrowserV023(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(['node', str(ROOT / 'tests/bold_ui_v023.mjs')],
                                cwd=ROOT, capture_output=True, text=True, timeout=180)
        if result.returncode:
            raise AssertionError(result.stderr[-8000:])
        cls.report = json.loads(result.stdout)
        if cls.report.get('gpu_draw') != 'NOT_RUN' or cls.report.get('video_render') != 'NOT_RUN':
            raise AssertionError('Browser selection checks must not invoke a renderer or GPU')

    def check(self, name):
        self.assertTrue(self.report['passed'])
        self.assertEqual(self.report['transport'], 'ACTUAL_LOCAL_HTTP')
        self.assertEqual(self.report['checks'][name], 'PASS')

    def test_auto_omits_visual_field_and_actual_metadata_drives_badge(self):
        self.check('auto_request_omits_visual_field_and_actual_bold_badge')

    def test_explicit_bold_persists_display_repeat_and_reload(self):
        self.check('explicit_bold_persists_display_repeat_and_reload')

    def test_actual_saved_plan_display_does_not_mutate_explicit_off_choice(self):
        self.check('saved_bold_badge_does_not_mutate_explicit_off_choice')

    def test_saved_v022_stays_v022_even_when_bold_form_is_selected(self):
        self.check('saved_v022_badge_does_not_migrate_or_override_bold_form')

    def test_partial_child_blocks_approve_and_render_buttons(self):
        self.check('partial_bold_child_blocks_approve_and_render')

    def test_production_bold_submission_has_only_authored_inputs_and_profile(self):
        self.check('production_bold_submission_preserves_authored_only_payload')

    def test_explicit_off_submission_uses_v022_plan_without_child(self):
        self.check('explicit_off_submission_uses_v022_plan')

    def test_high_level_api_allowlist_matches_actual_ui_helper(self):
        self.check('actual_helper_rejects_unknown_visual_profile_and_mismatched_pins')


if __name__ == '__main__':
    unittest.main()
