"""Actual public v024 selection and immutable saved-plan admission.

Real HTTP, planners, measured Production speech, persistence and backend
selection run here. No renderer, physical GPU or gcube worker is started.
The mobile DOM check serves actual app.js with previously generated real plans.
"""
from copy import deepcopy
import hashlib
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
from engine.public_infographic_selection import QA_PROFILE, PRODUCTION_PROFILE
from engine.storage import EngineError, plan_hash


ROOT = Path(__file__).resolve().parents[1]
TERRAIN = 'VISUAL_TARGET_MAP_V024'
BOLD = 'BOLD_INFOGRAPHIC_V023'
LEGACY = 'V022_LEGACY'
FROZEN = runpy.run_path(str(ROOT / 'tests/test_bold_public_selection_v023.py'))
IMAGE_ENV = {**FROZEN['IMAGE_ENV'],
             'WORLD_ENGINE_TERRAIN_INFOGRAPHIC_PROFILE': TERRAIN}
OWNER = 'isolated-v024-public-test-owner-value'
ui_helper = FROZEN['ui_helper']


MOBILE_DOM = r'''
import fs from 'node:fs';
import http from 'node:http';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const root=process.cwd(),input=JSON.parse(fs.readFileSync(0,'utf8'));
const require=createRequire(path.resolve(root,'../cinematic-world-map/package.json'));
const {chromium}=require('playwright');
const TARGET='VISUAL_TARGET_MAP_V024';
let selected=structuredClone(input.terrain),posts=[];
const errors=[];
const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml','.png':'image/png','.webmanifest':'application/manifest+json'};
function payload(){return {project:{id:'terrain-ui-project',current_version:'v001',title:'Terrain UI fixture'},version:'v001',plan:structuredClone(selected)};}
const server=http.createServer(async(req,res)=>{
 if(req.url.startsWith('/api/')){
  const chunks=[];for await(const chunk of req)chunks.push(chunk);
  const body=chunks.length?JSON.parse(Buffer.concat(chunks).toString()):null;
  if(req.method==='POST')posts.push({path:req.url,body});
  let response={};
  if(req.url==='/api/health')response={status:'ok'};
  else if(req.url==='/api/projects'&&req.method==='POST')response=payload();
  else if(req.url==='/api/projects')response={projects:[]};
  else if(req.url.endsWith('/versions'))response={versions:['v001']};
  else if(req.url.endsWith('/status'))response={status:'planned',outputs:[]};
  else if(req.url==='/api/projects/terrain-ui-project')response=payload();
  else response={status:'planned'};
  res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify(response));return;
 }
 const pathname=new URL(req.url,'http://127.0.0.1').pathname;
 const file=path.resolve(root,'web',pathname==='/'?'index.html':`.${pathname.replace(/^\/static\//,'/')}`);
 if(!file.startsWith(path.resolve(root,'web')+path.sep)){res.writeHead(403);res.end();return;}
 try{const content=fs.readFileSync(file);res.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream'});res.end(content);}
 catch{res.writeHead(404);res.end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--disable-gpu']});
async function open(){
 const context=await browser.newContext({viewport:{width:393,height:851},isMobile:true,hasTouch:true});
 const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
 await page.goto(origin);await page.waitForFunction(()=>document.getElementById('connection').textContent==='연결됨');
 return {context,page};
}
async function submit(page){
 const count=posts.filter(row=>row.path==='/api/projects').length;
 await page.locator('#create-plan').click();
 await page.waitForFunction(()=>!document.getElementById('plan-panel').hidden&&!document.getElementById('create-plan').disabled);
 assert.equal(posts.filter(row=>row.path==='/api/projects').length,count+1);
 return posts.filter(row=>row.path==='/api/projects').at(-1).body;
}
const checks=[];
try{
 {
  const {context,page}=await open();
  await page.locator('#topic').fill('Authored terrain UI topic');
  await page.locator('#infographic-mode').selectOption('QA');
  await page.locator('#infographic-visual-profile').selectOption(TARGET);
  const first=await submit(page);assert.equal(first.infographic_visual_profile,TARGET);
  assert.equal(first.direction_profile,'MAP_INFOGRAPHIC_QA_V022');
  assert.equal(await page.locator('#infographic-plan-badge').textContent(),'INFOGRAPHIC v024 · TERRAIN INFOGRAPHIC · QA');
  assert.equal(await page.locator('#approve-render').isDisabled(),false);
  assert.equal((await submit(page)).infographic_visual_profile,TARGET);
  await page.reload();await page.waitForFunction(()=>document.getElementById('connection').textContent==='연결됨');
  assert.equal(await page.locator('#infographic-visual-profile').inputValue(),TARGET);
  assert.equal(await page.locator('#infographic-mode').inputValue(),'QA');
  checks.push('actual_v024_option_submission_badge_repeat_reload');await context.close();
 }
 {
  selected=structuredClone(input.terrain);const {context,page}=await open();
  await page.locator('#topic').fill('Actual default terrain UI topic');
  await page.locator('#duration').fill('24');
  assert.equal(await page.locator('#infographic-visual-profile').inputValue(),'AUTO');
  const request=await submit(page);assert.equal('infographic_visual_profile'in request,false);
  assert.equal(request.duration,24);assert.equal(request.direction_profile,'REFERENCE_MASTER');
  assert.equal(await page.locator('#infographic-plan-badge').textContent(),'INFOGRAPHIC v024 · TERRAIN INFOGRAPHIC · QA');
  checks.push('auto_uses_actual_contract_without_fabricating_request_profile');await context.close();
 }
 {
  selected=structuredClone(input.terrain);delete selected.scenes[0].terrain_infographic;
  const {context,page}=await open();posts=[];
  await page.locator('#topic').fill('Actual partial terrain contract');
  await page.locator('#infographic-mode').selectOption('QA');await submit(page);
  assert.equal(await page.locator('#infographic-plan-badge').getAttribute('data-infographic-kind'),'MISMATCH');
  assert.equal(await page.locator('#approve-render').isDisabled(),true);
  await page.evaluate(()=>document.getElementById('resume-render').click());
  await page.waitForFunction(()=>!document.getElementById('resume-render').disabled);
  assert.equal(posts.some(row=>/\/(approve|render)$/.test(row.path)),false);
  checks.push('actual_partial_contract_blocks_render_controls');await context.close();
 }
 assert.deepEqual(errors,[]);
 process.stdout.write(JSON.stringify({passed:true,checks,transport:'ACTUAL_LOCAL_HTTP',gpu_draw:'NOT_RUN',video_render:'NOT_RUN'})+'\n');
}finally{await browser.close();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));http.globalAgent.destroy();}
'''


class TerrainPublicSelectionV024(unittest.TestCase):
    # Reuse the established transport/storage helpers without inheriting old
    # tests or changing their discovery count. Their cls/self is this fixture.
    call = classmethod(FROZEN['BoldPublicSelectionV023'].call.__func__)
    create = classmethod(FROZEN['BoldPublicSelectionV023'].create.__func__)
    approve = FROZEN['BoldPublicSelectionV023'].approve
    mapped_page = FROZEN['BoldPublicSelectionV023'].mapped_page
    saved_plan_variant = FROZEN['BoldPublicSelectionV023'].saved_plan_variant

    @classmethod
    def setUpClass(cls):
        from engine import (schema, gpu_preflight, visibility, infographic_backend,
                            semantic_timeline, infographic_contract, bold_infographic)
        touched = [(schema, 'validate_plan'), (gpu_preflight, 'validate_plan'),
                   (schema, 'SCHEMA_PATH'), (visibility, 'TOOL'),
                   (semantic_timeline, 'validate_production_plan'),
                   (infographic_backend, 'infographic_command'),
                   (infographic_contract, 'renderer_version'),
                   (infographic_contract, 'diagnostic_record'),
                   (bold_infographic, 'diagnostic_record')]
        original = [(module, name, getattr(module, name)) for module, name in touched]
        def restore():
            for module, name, value in original:
                setattr(module, name, value)
        cls.addClassCleanup(restore)
        environment = patch.dict(os.environ, IMAGE_ENV)
        environment.start()
        cls.addClassCleanup(environment.stop)
        cls.temporary = tempfile.TemporaryDirectory(prefix='terrain-public-v024-')
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
            raise AssertionError('Actual terrain test owner login failed: ' + str(result))
        cls.cookie = headers['Set-Cookie'].split(';')[0]
        cls.raw = dict(topic='만약 수에즈 운하가 7일 동안 막힌다면?', duration=24,
                       quality='HIGH', pace='FAST_PLUS', style='tension', qa_mode=False,
                       direction_profile='REFERENCE_MASTER', tts=False,
                       subtitles=False, bgm=True, sfx=True)
        cls.selected = cls.create(cls.raw)
        cls.bold = cls.create({**cls.raw, 'infographic_visual_profile': BOLD})
        cls.off = cls.create({**cls.raw, 'infographic_visual_profile': LEGACY})

    def assert_terrain(self, project, family='story-progression-v021'):
        from engine.terrain_infographic import validate_terrain_infographic
        plan = project['plan']
        self.assertTrue(plan['gate']['passed'], plan['gate'])
        report = validate_terrain_infographic(plan)
        self.assertTrue(report['passed'], report)
        self.assertEqual(plan['metadata']['infographic']['parent_renderer_family'], family)
        metadata = plan['metadata']['terrain_infographic']
        self.assertEqual((metadata['version'], metadata['profile_id']), ('v024', TERRAIN))
        for scene in plan['scenes']:
            own = scene['terrain_infographic']
            self.assertEqual((own['version'], own['profile_id']), ('v024', TERRAIN))
            self.assertEqual(own['profile_sha256'], metadata['profile_sha256'])
            self.assertEqual(own['registry_sha256'], metadata['registry_sha256'])
            self.assertEqual(scene['infographic']['version'], 'v022')
            self.assertEqual(scene['bold_infographic']['version'], 'v023')
        self.assertEqual(plan['plan_hash'], plan_hash(plan))
        saved = self.app.store.get(project['project']['id'], project['version'])['plan']
        self.assertEqual(saved, plan)
        return plan

    def test_image_default_actual_qa_plan_has_v024_child_and_renderer_page(self):
        plan = self.assert_terrain(self.selected)
        self.assertEqual(plan['metadata']['frame_grid']['total_frames'], 720)
        self.assertEqual(plan['duration'], 24)
        self.assertNotIn('infographic_visual_profile', plan['request'])
        self.assertIn('/static/render_terrain_infographic_earth.html?', self.mapped_page(plan))

    def test_explicit_actual_ui_request_reaches_public_qa_planner(self):
        request = ui_helper('buildCreationRequest', {**self.raw, 'infographic_mode': 'QA',
                            'infographic_visual_profile': TERRAIN})
        self.assertEqual(request['direction_profile'], QA_PROFILE)
        self.assertEqual(request['infographic_visual_profile'], TERRAIN)
        from engine.qa_planner import generate_deployment_plan
        with patch('engine.qa_planner.generate_deployment_plan', wraps=generate_deployment_plan) as planner:
            project = self.create(request)
        planner.assert_called_once()
        self.assert_terrain(project)

    def test_badge_uses_actual_all_scene_pins_and_rejects_missing_both_pins(self):
        plan = self.selected['plan']
        selection = ui_helper('infographicPlanSelection', plan)
        self.assertTrue(selection['valid'])
        self.assertEqual(selection['label'], 'INFOGRAPHIC v024 · TERRAIN INFOGRAPHIC · QA')
        self.assertEqual(plan['request']['direction_profile'], 'SECOND_EVENT_ADAPTIVE_WIDE_TEST')
        for pin in ('profile_sha256', 'registry_sha256'):
            with self.subTest(pin=pin):
                broken = deepcopy(plan)
                broken['metadata']['terrain_infographic'].pop(pin)
                for scene in broken['scenes']:
                    scene['terrain_infographic'].pop(pin)
                self.assertFalse(ui_helper('infographicPlanSelection', broken)['valid'])

    def test_complete_v023_scene_camera_material_and_event_contract_unchanged(self):
        before = self.bold['plan']
        after = self.selected['plan']
        self.assertEqual(len(after['scenes']), len(before['scenes']))
        for actual, legacy in zip(after['scenes'], before['scenes']):
            self.assertEqual({k: v for k, v in actual.items() if k != 'terrain_infographic'}, legacy)
        self.assertEqual(after['metadata']['bold_infographic'], before['metadata']['bold_infographic'])
        self.assertEqual(after['metadata']['infographic'], before['metadata']['infographic'])
        self.assertEqual(after['metadata']['frame_grid'], before['metadata']['frame_grid'])
        self.assertEqual(after['options'], before['options'])

    def test_explicit_v023_preserves_original_child_mapper_and_badge(self):
        plan = self.bold['plan']
        self.assertNotIn('terrain_infographic', plan['metadata'])
        self.assertTrue(all('terrain_infographic' not in scene for scene in plan['scenes']))
        self.assertEqual(plan['metadata']['bold_infographic']['version'], 'v023')
        self.assertIn('/static/render_bold_infographic_earth.html?', self.mapped_page(plan))
        self.assertEqual(ui_helper('infographicPlanSelection', plan)['label'],
                         'INFOGRAPHIC v023 · BOLD INFOGRAPHIC · QA')

    def test_explicit_v022_legacy_preserves_original_overlay(self):
        plan = self.off['plan']
        for key in ('terrain_infographic', 'bold_infographic'):
            self.assertNotIn(key, plan['metadata'])
            self.assertTrue(all(key not in scene for scene in plan['scenes']))
        self.assertIn('/static/render_infographic_earth.html?', self.mapped_page(plan))
        self.assertEqual(ui_helper('infographicPlanSelection', plan)['label'], 'INFOGRAPHIC v022 · QA')

    def test_explicit_terrain_cannot_silently_fall_back_to_legacy_director(self):
        status, _, result = self.call('POST', '/api/projects',
            {**self.raw, 'direction_profile': 'FAST_PLUS_LEGACY',
             'infographic_visual_profile': TERRAIN})
        self.assertEqual(status, 400, result)
        self.assertEqual(result['error']['code'], 'TERRAIN_INFOGRAPHIC_REQUIRES_V022')

    def test_absent_new_image_env_keeps_native_v023_selection(self):
        with patch.dict(os.environ):
            os.environ.pop('WORLD_ENGINE_TERRAIN_INFOGRAPHIC_PROFILE', None)
            project = self.create(self.raw)
        plan = project['plan']
        self.assertNotIn('terrain_infographic', plan['metadata'])
        self.assertEqual(plan['metadata']['bold_infographic']['version'], 'v023')
        self.assertIn('/static/render_bold_infographic_earth.html?', self.mapped_page(plan))

    def test_actual_mobile_dom_selects_persists_and_blocks_partial_v024(self):
        result = subprocess.run(['node', '--input-type=module', '-e', MOBILE_DOM],
            cwd=ROOT, input=json.dumps({'terrain': self.selected['plan']}),
            capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, 0, result.stderr[-8000:])
        report = json.loads(result.stdout)
        self.assertTrue(report['passed'])
        self.assertEqual(len(report['checks']), 3)
        self.assertEqual(report['transport'], 'ACTUAL_LOCAL_HTTP')
        self.assertEqual((report['gpu_draw'], report['video_render']), ('NOT_RUN', 'NOT_RUN'))

    def test_approval_retry_and_worker_use_exact_saved_terrain_contract(self):
        project = self.selected
        pid, version = self.approve(project)
        directory = self.app.store.version_path(pid, version)
        original = (directory / 'scene_plan.json').read_bytes()
        receipt = json.loads((directory / 'public-selection.json').read_text())
        self.assertEqual(receipt['visual_profile'], TERRAIN)
        with patch('engine.qa_planner.generate_deployment_plan', side_effect=AssertionError('No replan')) as planner:
            first = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
            second = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
            planner.assert_not_called()
        self.assertEqual((first[0], second[0]), (202, 202))
        self.assertEqual(first[2]['job_id'], second[2]['job_id'])
        admitted = self.app.scheduler._plan(first[2])
        self.assertEqual(admitted, project['plan'])
        self.assertEqual((directory / 'scene_plan.json').read_bytes(), original)
        self.assertIsNone(self.app.scheduler.thread)
        self.app.scheduler.cancel(first[2]['job_id'])

    def test_partial_child_rejected_before_approval_or_render_submission(self):
        project = self.selected
        pid, version = project['project']['id'], project['version']
        with self.saved_plan_variant(project, lambda plan: plan['scenes'][0].pop('terrain_infographic')):
            with patch.object(self.app.scheduler, 'submit') as submit:
                approved = self.call('POST', '/api/projects/' + pid + '/approve',
                    {'version': version, 'plan_hash': project['plan']['plan_hash']})
                queued = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
                submit.assert_not_called()
            self.assertEqual((approved[0], queued[0]), (409, 409))
            self.assertEqual(approved[2]['error']['code'], 'TERRAIN_INFOGRAPHIC_PLAN_INVALID')
            self.assertEqual(queued[2]['error']['code'], 'TERRAIN_INFOGRAPHIC_PLAN_INVALID')

    def test_receipt_cannot_downgrade_whole_child_to_v023(self):
        def remove(plan):
            plan['metadata'].pop('terrain_infographic')
            for scene in plan['scenes']:
                scene.pop('terrain_infographic')
        with self.saved_plan_variant(self.selected, remove):
            with self.assertRaises(EngineError) as caught:
                self.app.check_profile_selection(self.selected['project']['id'], self.selected['version'])
        self.assertEqual(caught.exception.code, 'TERRAIN_INFOGRAPHIC_SELECTION_MISMATCH')

    def test_orphan_and_null_terrain_never_fall_back_in_ui_or_public_gate(self):
        from engine.public_infographic_selection import require_infographic_selection
        for placement in ('metadata', 'scene'):
            for payload in (None, {}, {'version': 'v024', 'profile_id': TERRAIN}):
                with self.subTest(placement=placement, payload=payload):
                    plan = dict(metadata={}, scenes=[dict(scene_id='S001')], request={})
                    target = plan['metadata'] if placement == 'metadata' else plan['scenes'][0]
                    target['terrain_infographic'] = payload
                    with self.assertRaises(EngineError):
                        require_infographic_selection(plan)
                    self.assertFalse(ui_helper('infographicPlanSelection', plan)['valid'])
        for placement in ('metadata', 'scene'):
            plan = deepcopy(self.selected['plan'])
            target = plan['metadata'] if placement == 'metadata' else plan['scenes'][0]
            target['terrain_infographic'] = None
            with self.assertRaises(EngineError) as caught:
                require_infographic_selection(plan)
            self.assertEqual(caught.exception.code, 'TERRAIN_INFOGRAPHIC_PLAN_INVALID')
            self.assertFalse(ui_helper('infographicPlanSelection', plan)['valid'])

    def test_source_pin_tampering_cannot_select_terrain_page(self):
        from engine.infographic_backend import infographic_command
        for field in ('profile_sha256', 'parent_bold_sha256'):
            with self.subTest(field=field), tempfile.TemporaryDirectory(prefix='terrain-forged-v024-') as directory:
                scene = deepcopy(self.selected['plan']['scenes'][0])
                scene['terrain_infographic'][field] = '0' * 64
                path = Path(directory) / 'scene.json'
                path.write_text(json.dumps(scene))
                with self.assertRaises(RuntimeError) as caught:
                    infographic_command(['node', 'renderer', '--scene-json', str(path), '--url',
                        'http://127.0.0.1/static/render_production_earth.html'])
                self.assertEqual(str(caught.exception), 'TERRAIN_INFOGRAPHIC_SCENE_SOURCE_MISMATCH')

    def test_saved_explicit_v023_is_not_migrated_on_approval_or_worker_retry(self):
        project = self.bold
        pid, version = self.approve(project)
        directory = self.app.store.version_path(pid, version)
        original = (directory / 'scene_plan.json').read_bytes()
        status, _, ticket = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
        self.assertEqual(status, 202, ticket)
        admitted = self.app.scheduler._plan(ticket)
        self.assertNotIn('terrain_infographic', admitted['metadata'])
        self.assertEqual(admitted, project['plan'])
        self.assertEqual((directory / 'scene_plan.json').read_bytes(), original)
        self.assertIn('/static/render_bold_infographic_earth.html?', self.mapped_page(admitted))
        self.app.scheduler.cancel(ticket['job_id'])

    def test_actual_pipeline_keeps_infographic_backend_with_terrain_page(self):
        from engine import rendering, pipeline_stability
        from engine.infographic_backend import InfographicBackend
        pid, version = self.approve(self.selected)
        approved = self.app.store.require_approved(pid, version)
        probe = FunctionType(FROZEN['_selected_backend_without_render'].__code__,
                             dict(rendering.render_project.__globals__))
        with patch.object(rendering, 'render_project', probe):
            backend = pipeline_stability.render_project(
                self.app.store.version_path(pid, version), approved, 'http://127.0.0.1:1')
        self.assertIs(backend, InfographicBackend)
        self.assertIn('/static/render_terrain_infographic_earth.html?', self.mapped_page(approved))

    def test_actual_production_ui_api_measurement_and_worker_handoff(self):
        from engine.infographic_planner import generate_production_infographic
        from engine import schema, semantic_timeline
        script = json.loads((ROOT / 'deployment/gcube/fixtures/infographic_production_v022.json').read_text())
        request = ui_helper('buildCreationRequest', {'infographic_mode': 'PRODUCTION',
                            'infographic_visual_profile': TERRAIN}, script)
        self.assertEqual(request, {'direction_profile': PRODUCTION_PROFILE,
                                 'script_record': script, 'infographic_visual_profile': TERRAIN})
        with patch('engine.infographic_planner.generate_production_infographic',
                   wraps=generate_production_infographic) as planner:
            project = self.create(request)
        planner.assert_called_once()
        plan = self.assert_terrain(project, family='production-earth-v1')
        timeline = plan['metadata']['semantic_timeline']
        self.assertTrue(timeline['passed'])
        self.assertEqual(plan['duration'], timeline['total_frames'] / 30)
        self.assertNotEqual(timeline['total_frames'], 720)
        self.assertEqual(plan['metadata']['authored_script'], script)
        self.assertEqual(timeline['script_sha256'], hashlib.sha256(script['text'].encode()).hexdigest())
        voice = Path(plan['metadata']['semantic_timeline_directory']) / timeline['voice']['file']
        self.assertTrue(voice.is_relative_to(self.app.store.root))
        self.assertEqual(hashlib.sha256(voice.read_bytes()).hexdigest(), timeline['voice']['sha256'])
        self.assertTrue(schema.validate_plan(plan)['passed'])
        report = semantic_timeline.validate_production_plan(plan)
        self.assertTrue(report['passed'], report)
        self.assertEqual(ui_helper('infographicPlanSelection', plan)['label'],
                         'INFOGRAPHIC v024 · TERRAIN INFOGRAPHIC · PRODUCTION')
        pid, version = self.approve(project)
        directory = self.app.store.version_path(pid, version)
        original = (directory / 'scene_plan.json').read_bytes()
        status, _, ticket = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
        self.assertEqual(status, 202, ticket)
        admitted = self.app.scheduler._plan(ticket)
        self.assertEqual(admitted, plan)
        self.assertTrue(semantic_timeline.validate_production_plan(admitted)['passed'])
        self.assertEqual((directory / 'scene_plan.json').read_bytes(), original)
        self.assertIn('/static/render_terrain_infographic_earth.html?', self.mapped_page(admitted))
        self.assertIsNone(self.app.scheduler.thread)
        self.app.scheduler.cancel(ticket['job_id'])
        with self.saved_plan_variant(project, lambda value: value['scenes'][0].pop('terrain_infographic')) as broken:
            self.assertFalse(semantic_timeline.validate_production_plan(broken)['passed'])
            rejected = self.call('POST', '/api/projects/' + pid + '/render', {'version': version})
            self.assertEqual(rejected[0], 409, rejected[2])
            self.assertEqual(rejected[2]['error']['code'], 'TERRAIN_INFOGRAPHIC_PLAN_INVALID')

    def test_cold_worker_admits_saved_terrain_with_new_profile_default_off(self):
        project = self.selected
        source = r'''
import json,sys
from unittest.mock import patch
from deployment.mobile_server import MobileApplication
from engine import schema
args=json.loads(sys.argv[1])
with patch('engine.qa_planner.generate_deployment_plan',side_effect=AssertionError('No replan')) as planner:
 app=MobileApplication(args['state'],'http://127.0.0.1:1',args['access'],disk_floor=0)
 try:
  saved=app.store.get(args['pid'],args['version'])['plan']
  profile=app.check_profile_selection(args['pid'],args['version'],saved)
  gate=schema.validate_plan(saved)
  scene=app.store.version_path(args['pid'],args['version'])/'scene_json/S001.json'
  from engine.infographic_backend import infographic_command
  mapped=infographic_command(['node','renderer','--scene-json',str(scene),'--url','http://127.0.0.1/static/render_production_earth.html'])
  planner.assert_not_called()
  print(json.dumps(dict(profile=profile,passed=gate['passed'],url=mapped[-1],terrain=saved['metadata']['terrain_infographic']['version'])))
 finally:app.scheduler.close()
'''
        environment = dict(os.environ)
        environment.pop('WORLD_ENGINE_TERRAIN_INFOGRAPHIC_PROFILE', None)
        environment['WORLD_ENGINE_INFOGRAPHIC_VISUAL_PROFILE'] = LEGACY
        arguments = dict(state=str(self.app.state_root), access=str(self.access),
                         pid=project['project']['id'], version=project['version'])
        process = subprocess.run([sys.executable, '-c', source, json.dumps(arguments)],
            cwd=ROOT, env=environment, text=True, capture_output=True, timeout=180)
        self.assertEqual(process.returncode, 0, process.stderr[-6000:])
        result = json.loads(process.stdout)
        self.assertTrue(result['passed'])
        self.assertEqual((result['profile'], result['terrain']), (QA_PROFILE, 'v024'))
        self.assertIn('/static/render_terrain_infographic_earth.html', result['url'])


if __name__ == '__main__':
    unittest.main()
