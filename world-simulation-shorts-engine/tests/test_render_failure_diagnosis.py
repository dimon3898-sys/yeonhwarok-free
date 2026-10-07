"""Real failing child processes and preparation-only job/cache fixtures; no GPU render."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import os
from unittest.mock import patch

from engine.backends import CPULocalBackend
from engine.failures import RenderProcessError, failure_record, safe_tail
from engine.planner import generate_plan, PlanningInputError
from engine.qa_planner import generate_deployment_plan, configure_qa_schema
from engine.storage import ProjectStore
from deployment.mobile_server import worker

ROOT = Path(__file__).resolve().parents[1]
REQUEST = dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=20,
               pace='FAST_PLUS', quality='HIGH', tts=False, subtitles=False, bgm=True, sfx=True)


class ProcessEvidenceTests(unittest.TestCase):
    def test_production_legacy_flags_resolve_to_the_verified_hardware_profile(self):
        from deployment.gcube.chromium_wrapper import browser_arguments
        import re
        source = (ROOT/'tools/render_production_scene.mjs').read_text()
        raw = re.search(r'headless:true,args:(\[[^\]]+\])', source).group(1)
        arguments = json.loads(raw.replace("'", '"'))
        for profile in ('vulkan', 'egl'):
            env = dict(WORLD_ENGINE_RENDER_MODE='gpu-required', WORLD_ENGINE_GPU_PROFILE=profile,
                       CHROMIUM_PATH=str(ROOT/'deployment/gcube/chromium_wrapper.py'))
            expected = browser_arguments(arguments, env)
            self.assertNotIn('--use-angle=swiftshader', expected)
            self.assertIn('--disable-software-rasterizer', expected)
            events = []
            command = [sys.executable, '-c',
                       "import json,os;print(json.dumps({k:os.environ[k] for k in ['WORLD_ENGINE_RENDER_MODE','WORLD_ENGINE_GPU_PROFILE','CHROMIUM_PATH']}))"]
            with patch.dict(os.environ, env):
                CPULocalBackend().run(command, ROOT, events.append)
            self.assertEqual(events, [env])

    def test_actual_exit_separate_pipes_and_safe_evidence(self):
        command = [sys.executable, '-c',
                   "import sys;print('preparing');print('ENOENT /opt/private/missing.otf',file=sys.stderr);sys.exit(7)"]
        with self.assertRaises(RenderProcessError) as failed:
            CPULocalBackend().run(command, ROOT, lambda event: None)
        record = failure_record(failed.exception, stage='scene_start', scene_id='S001')
        self.assertEqual(record['code'], 'SCENE_RENDERER_EXIT')
        self.assertEqual(record['subprocess']['return_code'], 7)
        self.assertEqual(record['subprocess']['stdout_tail'], ['preparing'])
        self.assertIn('ENOENT', record['subprocess']['stderr_tail'][0])
        self.assertNotIn('/opt/private', json.dumps(record))
        self.assertGreaterEqual(record['subprocess']['duration_seconds'], 0)
        self.assertEqual(record['failed_stage'], 'scene_start')

    def test_large_stderr_cannot_block_stdout_progress(self):
        events = []
        command = [sys.executable, '-c',
                   "import sys;[print('noise'*300,file=sys.stderr) for _ in range(300)];print('{\"stage\":\"scene_render\",\"completed_frames\":1}');sys.exit(8)"]
        with self.assertRaises(RenderProcessError) as failed:
            CPULocalBackend().run(command, ROOT, events.append)
        self.assertEqual(events[0]['completed_frames'], 1)
        self.assertEqual(len(failed.exception.diagnostics['stderr_tail']), 25)

    def test_no_command_or_sensitive_query_or_body_in_evidence(self):
        inputs = ['https://service.example/scene?pass=abc', 'Cookie: protected',
                  'Authorization: protected', 'password=protected', 'token=protected',
                  'owner_code=protected', 'request.body: protected', '/data/private/tmp/file.json']
        text = json.dumps(safe_tail(inputs))
        self.assertNotIn('protected', text)
        self.assertNotIn('pass=abc', text)
        self.assertNotIn('/data/private', text)
        record = failure_record(RuntimeError('password=protected'), stage='scene_start')
        self.assertNotIn('protected', json.dumps(record))

    def test_missing_executable_records_start_failure_without_command(self):
        with self.assertRaises(RenderProcessError) as failed:
            CPULocalBackend().run(['/nonexistent/private-executable'], ROOT, lambda event: None)
        self.assertEqual(failed.exception.code, 'SCENE_RENDERER_START_FAILED')
        self.assertIsNone(failed.exception.diagnostics['return_code'])


class PlanningAndWorkerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = generate_plan(REQUEST)

    def test_qa12_passes_full_plan_gate_normal20_stays_identical(self):
        from engine.schema import validate_plan
        from engine.production import production_default_status
        original_request = generate_plan.__globals__['_request']
        qa = generate_deployment_plan({**REQUEST, 'duration': 12, 'qa_mode': True})
        self.assertTrue(qa['gate']['passed'], qa['gate']['errors'])
        self.assertTrue(validate_plan(qa)['passed'])
        self.assertEqual(sum(s['duration'] for s in qa['scenes']), 12)
        self.assertEqual(qa['options']['quality'], 'HIGH')
        self.assertTrue(production_default_status()['active'])
        self.assertIs(generate_plan.__globals__['_request'], original_request)
        normal = generate_deployment_plan(REQUEST)
        # Certificate cache-hit metadata may change between identical invocations.
        for field in ('scenes', 'request', 'options', 'story', 'sources'):
            self.assertEqual(normal[field], self.plan[field], field)
        for value in (9, 16, 20, float('nan'), float('inf')):
            with self.assertRaises(PlanningInputError):
                generate_deployment_plan({**REQUEST, 'duration': value, 'qa_mode': True})
        with self.assertRaises(PlanningInputError):
            generate_deployment_plan({**REQUEST, 'duration': 12})
        invalid = copy.deepcopy(qa)
        invalid['request']['qa_mode'] = False
        self.assertFalse(validate_plan(invalid)['passed'])
        invalid = copy.deepcopy(qa)
        invalid['scenes'][0]['coordinates']['lat'] = 800
        self.assertFalse(validate_plan(invalid)['passed'])

    def test_worker_retains_scene_exit_code_and_failed_stage(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = ProjectStore(root/'projects')
            data = store.create(REQUEST, copy.deepcopy(self.plan))
            pid = data['project']['id']
            store.approve(pid, 'v001', data['plan']['plan_hash'])
            ticket = dict(job_id='job_012345abcdef', project_id=pid, version='v001',
                          plan_hash=data['plan']['plan_hash'], internal_url='http://127.0.0.1:8001')
            (root/'jobs').mkdir()
            ticket_path = root/'jobs'/('job_012345abcdef.json')
            ticket_path.write_text(json.dumps(ticket))
            def fail(project_dir, plan, base_url, progress, **kwargs):
                progress(dict(stage='scene_start', scene_id='S001', total=5))
                CPULocalBackend().run([sys.executable, '-c', "import sys;print('preparation failed',file=sys.stderr);sys.exit(7)"], ROOT, progress)
            with patch('engine.rendering.render_project', side_effect=fail):
                self.assertEqual(worker(ticket_path, root), 1)
            state = store.status(pid, 'v001')
            self.assertEqual(state['error']['code'], 'SCENE_RENDERER_EXIT')
            self.assertEqual(state['error']['diagnostics']['return_code'], 7)
            self.assertEqual(state['error']['failed_stage'], 'scene_start')
            self.assertEqual(state['error']['scene_id'], 'S001')
            private = json.loads((root/'jobs'/'job_012345abcdef.failure.json').read_text())
            self.assertEqual(private['subprocess']['return_code'], 7)
            self.assertEqual(state['status'], 'failed')
            self.assertIn('failed_at', state)

    def test_scene_preparation_and_resume_preserve_completed_scene_bytes(self):
        from engine.rendering import render_project
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = ProjectStore(root/'projects')
            data = store.create(REQUEST, copy.deepcopy(self.plan))
            pid, plan = data['project']['id'], data['plan']
            store.approve(pid, 'v001', plan['plan_hash'])
            version = store.version_path(pid, 'v001')
            calls = []
            def prepare(backend, command, cwd, progress):
                options = dict(zip(command[2::2], command[3::2]))
                scene = json.loads(Path(options['--scene-json']).read_text())
                calls.append(scene['scene_id'])
                if scene['scene_id'] == 'S003':
                    raise RenderProcessError(returncode=7, duration=.02, stderr=['fixture stop'])
                output = Path(options['--output'])
                output.write_bytes(b'FAKE_UNIT_TEST_MEDIA_NO_RENDER')
                output.with_suffix('.manifest.json').write_text('{}')
                Path(options['--audit']).write_text(json.dumps([{} for _ in range(round(scene['duration']*30))]))
                return {'exit_code': 0}
            with patch('engine.rendering.APP_ROOT', root), patch('engine.rendering.create_audio', return_value={'file':'unused','narration_cues':[]}), patch('engine.rendering.create_subtitles', return_value={}), patch('engine.rendering.valid_scene_file', return_value=True), patch.object(CPULocalBackend, 'run', prepare):
                with self.assertRaises(RenderProcessError):
                    render_project(version, plan, 'http://127.0.0.1:8001')
                completed = {path: path.read_bytes() for sid in ('S001','S002') for path in (version/'renders'/sid).iterdir() if path.is_file()}
                checkpoint = json.loads((version/'renders'/'checkpoint.json').read_text())
                self.assertEqual(checkpoint['scene_id'], 'S003')
                self.assertEqual(checkpoint['completed_scenes'], 2)
                calls.clear()
                with self.assertRaises(RenderProcessError):
                    render_project(version, plan, 'http://127.0.0.1:8001')
                self.assertEqual(calls, ['S003'])
                self.assertEqual(completed, {path: path.read_bytes() for path in completed})

    def test_minimal_summary_preserves_internal_provenance_in_json(self):
        program = """import {sceneEventSummary, failureSummary} from './web/plan_presentation.js';
const scene={visual_events:[{kind:'milestone_reveal',description:'내부 검수 거리 계산 문구'}]};
console.log(JSON.stringify({summary:sceneEventSummary(scene,{milestone_reveal:'항로 진행률 공개'}),scene,error:failureSummary({code:'SCENE_RENDERER_EXIT',failed_stage:'scene_start',scene_id:'S001',message:'오류',diagnostics:{return_code:7}})}));"""
        result = subprocess.run(['node','--input-type=module','-e',program],cwd=ROOT,capture_output=True,text=True,check=True)
        data = json.loads(result.stdout)
        self.assertEqual(data['summary'], '항로 진행률 공개')
        self.assertIn('내부 검수', data['scene']['visual_events'][0]['description'])
        self.assertIn('exit 7', data['error'])


if __name__ == '__main__':
    unittest.main()
