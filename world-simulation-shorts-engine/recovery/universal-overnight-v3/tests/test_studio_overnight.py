"""Focused CPU proof. Real parser/private store/HTTP auth; no GPU worker runs."""
from copy import deepcopy
from datetime import datetime,timedelta,timezone
import importlib.util
import json
from pathlib import Path
import secrets
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parents[1]
ORIGINAL=HERE.parent/'production-studio-mvp-v1'
sys.path.insert(0,str(ORIGINAL))
import studio_contracts

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module);return module

contract=load('_overnight_contract_test',HERE/'contract_v3.py')
controller=load('_overnight_controller_test',HERE/'studio_controller.py')
bridge=load('_overnight_bridge_test',HERE/'runtime_bridge.py')
manager=load('_overnight_manager_test',HERE/'execution_manager.py')
entry=load('_overnight_entry_test',HERE/'studio_entry.py')
legacy=load('_overnight_http_helpers',HERE.parent/'universal-integration-v1/tests/test_studio_entry.py')
fixture=load('_overnight_contract_fixture',ORIGINAL/'tests/test_studio_contracts.py')
DIGEST='sha256:'+'b'*64


def value(**overnight):
    inner={'schema':'WORLD_ENGINE_STUDIO_PROMPT_V2','preset':'VERIFIED_FRONT_V4_80S','durationSeconds':80,
        'completion':{'schema':'WORLD_ENGINE_UNIVERSAL_COMPLETION_V2','profile':'VISUAL_UNIFIED_COMPLETION_V2'},
        'overnight':{'schema':contract.SCHEMA,'profile':contract.PROFILE,**overnight}}
    return {'prompt':json.dumps(inner),'durationSeconds':80,'profile':'V4_ARCHIVAL_80S','sfx':{'enabled':False}}


def policy(instance):
    record={'schema':'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_V1','validUntil':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
        'maxWallSeconds':60,'maxRetries':0,'maxCostAmount':'1','currency':'USD','gpuHourlyRate':'1'}
    with instance._cache.PrivateTree(instance.control_root) as root:root.write_json('operator_policy.json',record)


class ContractTests(unittest.TestCase):
    def normalize(self,raw):
        return contract.normalize_submission(raw,image_digest=DIGEST,backend=fixture.FakeBackend(),parent_normalize=studio_contracts.normalize_submission)
    def error(self,raw,code):
        with self.assertRaises(studio_contracts.StudioContractError) as error:self.normalize(raw)
        self.assertEqual(error.exception.code,code)
    def test_metadata_sibling_preserves_parent_plan_and_source(self):
        raw=value();before=deepcopy(raw);actual=self.normalize(raw)
        parent_raw=deepcopy(raw);inner=json.loads(parent_raw['prompt']);inner.pop('overnight');parent_raw['prompt']=json.dumps(inner)
        parent=contract.load('_overnight_parent_compare',HERE.parent/'universal-integration-completion-v2/contract_v2.py')
        old=parent.normalize_submission(parent_raw,image_digest=DIGEST,backend=fixture.FakeBackend(),parent_normalize=studio_contracts.normalize_submission)
        for key in ('videoPlan','integration','completionV2','sfx'):self.assertEqual(actual[key],old[key])
        self.assertEqual(raw,before);self.assertEqual(actual['overnightV3']['operation'],'PREVIEW_5S')
    def test_full80_cannot_be_selected(self):self.error(value(operation='FULL_80S'),'STUDIO_OVERNIGHT_FULL_VIDEO_REQUIRES_REVIEW')
    def test_software_user_knob_rejected(self):self.error(value(softwareProbe=True),'STUDIO_OVERNIGHT_FIELD_UNSUPPORTED')
    def test_explicit_unknown_field_not_ignored(self):self.error(value(roll=15),'STUDIO_OVERNIGHT_FIELD_UNSUPPORTED')
    def test_preview_start_exact_nonnegative_integer(self):
        for bad in (True,-1,1.5,None):self.error(value(startFrame=bad),'STUDIO_OVERNIGHT_PREVIEW_RANGE_INVALID')
        self.assertEqual(self.normalize(value(startFrame=400))['overnightV3']['startFrame'],400)
    def test_old_plain_prompt_not_silently_downgraded(self):
        raw=value();inner=json.loads(raw['prompt']);inner.pop('overnight');raw['prompt']=json.dumps(inner)
        self.error(raw,'STUDIO_OVERNIGHT_PROFILE_REQUIRED')
    def test_no_completion_rejected(self):
        raw=value();inner=json.loads(raw['prompt']);inner.pop('completion');raw['prompt']=json.dumps(inner)
        self.error(raw,'STUDIO_OVERNIGHT_COMPLETION_REQUIRED')
    def test_real_js_visual_normalization_defaults(self):
        actual=self.normalize(value())['overnightV3']['visualExtensions']
        self.assertIsNone(actual['scalarTerritory']);self.assertIsNone(actual['nationalUnits'])
    def test_visual_unsupported_options_reported(self):
        self.error(value(visualExtensions={'schema':'WORLD_ENGINE_OVERNIGHT_VISUAL_V1','bogus':True}),
            'STUDIO_OVERNIGHT_VISUAL_INVALID')


class RealStudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='overnight-studio-',dir=HERE.parents[2]);self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.controller=controller.StudioController(control_root=root/'production',export_root=root/'exports',image_digest=DIGEST)
        policy(self.controller)
    def test_real_normalizer_private_submit_blocked_before_hardware_and_worker(self):
        with patch.object(self.controller.backend.parent_backend,'_health',side_effect=AssertionError('No GPU probe allowed')) as gpu:
            result=self.controller.submit(value());gpu.assert_not_called()
        self.assertFalse(result['preflight']['ready'])
        self.assertTrue(str(self.controller.control_root).endswith('universal-overnight-v3/universal-integration-v1'))
        with self.controller._cache.PrivateTree(self.controller.control_root) as root:
            actual=self.controller._read_submission(root,result['submissionId'])['submission']
        self.assertEqual(actual['videoPlan']['totalFrames'],2400);self.assertEqual(len(actual['videoPlan']['scenes']),12)
        self.assertEqual(actual['overnightV3']['operation'],'PREVIEW_5S')
    def test_direct_start_cannot_bypass_preflight(self):
        result=self.controller.submit(value())
        with patch.object(self.controller.backend.bridge,'start_studio_job',side_effect=AssertionError('No worker')) as worker:
            with self.assertRaises(controller.StudioError) as error:
                self.controller.start(result['submissionId'],'negative-overnight-start',consent=True)
            worker.assert_not_called()
        self.assertEqual(error.exception.code,'STUDIO_PREFLIGHT_BLOCKED')
        for name in ('requests','runs','jobs'):self.assertEqual(list((self.controller.control_root/name).iterdir()),[])
    def test_resume_never_automatically_retries_or_resets_claims(self):
        with self.assertRaises(controller.StudioError) as error:self.controller.resume('studio-'+'a'*32,'retry-key',consent=True)
        self.assertEqual(error.exception.code,'STUDIO_OVERNIGHT_PREVIEW_RETRY_REQUIRES_NEW_APPROVAL')
    def test_revise_cannot_bypass_preview_scope(self):
        with self.assertRaises(controller.StudioError):self.controller.revise('studio-'+'a'*32,{})


class BridgeTests(unittest.TestCase):
    def test_no_optional_historical_actor_requirement_in_base_preview(self):
        plan={'fps':30,'totalFrames':2400}
        admission=bridge._visual_admission(contract.VISUAL_DEFAULT,{'trustedSources':[]},plan)
        self.assertEqual(admission['status'],'CPU_ADMITTED')
        self.assertFalse(admission['scalarControlSelected']);self.assertFalse(admission['nationalUnitsSelected'])
    def test_selected_missing_historical_actor_blocked(self):
        request={**contract.VISUAL_DEFAULT,'nationalUnits':{'sourceId':'missing','sha256':'a'*64,'markerScale':1.1}}
        with self.assertRaisesRegex(RuntimeError,'SELECTED_VISUAL_SOURCE_BLOCKED'):
            bridge._visual_admission(request,{'trustedSources':[]},{'fps':30,'totalFrames':2400})
    def test_preflight_failure_never_authorizes_or_raises_private_errors(self):
        with patch.object(bridge,'gate_context',side_effect=RuntimeError('/private/token/example')):
            result=bridge.preflight({},control_root=None,export_root=None,image_digest=DIGEST)
        self.assertFalse(result['renderAllowed']);self.assertFalse(result['gpuRenderingVerified'])
        self.assertNotIn('/private/',json.dumps(result))
    def test_fullvideo_recovery_unconditionally_refused(self):
        with self.assertRaisesRegex(RuntimeError,'RETRY_REQUIRES_NEW_APPROVAL'):bridge.start_studio_recovery()


class HTTPTests(unittest.TestCase):
    request=legacy.HTTPTests.request;login=legacy.HTTPTests.login;tearDown=legacy.HTTPTests.tearDown
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='overnight-http-',dir=HERE.parents[2]);self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)/'private';root.mkdir(mode=0o700)
        self.owner=root/'owner-code';self.password=secrets.token_urlsafe(32)
        self.owner.write_text(self.password);self.owner.chmod(0o600)
        self.backend,self.bridge=legacy.FakeParentBackend(),legacy.FakeBridge();test=self
        def factory(**kwargs):
            test.controller=controller.StudioController(**kwargs,backend=test.backend,bridge_module=test.bridge)
            policy(test.controller);return test.controller
        self.app=entry.Application(root,self.owner,Path(self.tmp.name)/'exports',DIGEST,
            controller_factory=factory,gpu_check=lambda:False,initial_origin=legacy.ORIGIN)
        self.server=entry.prior.proxy.original.StudioHTTPServer(('127.0.0.1',0),self.app.handler())
        self.port=self.server.server_address[1];self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def test_profile_requires_owner_auth_and_declares_preview_only(self):
        self.assertEqual(self.request('/api/integration/profile')[0],401)
        cookie,_=self.login();code,facts,_=self.request('/api/integration/profile',cookie=cookie)
        self.assertEqual(code,200);self.assertEqual(facts['profile'],'OVERNIGHT_SAFE_V3');self.assertFalse(facts['full80Allowed'])
    def test_submission_csrf_and_overnight_metadata(self):
        cookie,csrf=self.login()
        self.assertEqual(self.request('/api/submissions','POST',value(),cookie)[0],403)
        code,result,_=self.request('/api/submissions','POST',value(),cookie,csrf)
        self.assertEqual(code,201,str(result))
        with self.controller._cache.PrivateTree(self.controller.control_root) as root:
            actual=self.controller._read_submission(root,result['submissionId'])['submission']
        self.assertEqual(actual['overnightV3']['profile'],'OVERNIGHT_SAFE_V3')
    def test_origin_host_protection_and_browser_namespace(self):
        cookie,_=self.login()
        self.assertGreaterEqual(self.request('/api/integration/profile',cookie=cookie,host='bad.invalid')[0],400)
        self.assertEqual(self.request('/api/integration/profile',cookie=cookie,origin='https://bad.invalid')[0],403)
        code,body,_=self.request('/app.js',cookie=cookie);self.assertEqual(code,200)
        self.assertIn(b'world-studio-overnight-v3-job',body)



class RealSourcePreviewBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='overnight-source-',dir=HERE.parents[2]);self.addCleanup(self.tmp.cleanup)
        root=Path(self.tmp.name)
        self.controller=controller.StudioController(control_root=root/'production',export_root=root/'exports',image_digest=DIGEST)
        self.submission=self.controller._normal(value())
        module=bridge._manifest()
        self.facts=SimpleNamespace(canonical=module.canonical,sha=module.sha,read_regular=module.read_regular,
            read_image_proof=lambda *a,**k:None,verify_sources=lambda:{'status':'PASS','manifestSHA256':'1'*64,'sourceCommit':'2'*40})
    def test_real_qualified_history_and_default_range_do_not_require_unselected_actors(self):
        with patch.object(bridge,'_manifest',return_value=self.facts):
            report=bridge.gate_context(self.submission,image_digest=DIGEST,control_root=None)
        self.assertTrue(report['dataAdmitted']);self.assertEqual(report['dataBlockers'],[])
        self.assertEqual(report['preview']['range']['frameCount'],150)
        self.assertFalse(report['imagePackageIncluded']);self.assertFalse(report['full80Allowed'])
        self.assertNotIn('HISTORICAL_NATIONAL_UNIT_POSITIONS',report['requiredModules'])
    def test_binding_changes_with_preview_range_but_source_plan_is_identical(self):
        before=deepcopy(self.submission)
        with patch.object(bridge,'_manifest',return_value=self.facts):
            a=bridge.gate_context(self.submission,image_digest=DIGEST)
            child=deepcopy(self.submission);child['overnightV3']['startFrame']=400
            b=bridge.gate_context(child,image_digest=DIGEST)
        self.assertEqual(self.submission,before);self.assertEqual(child['videoPlan'],self.submission['videoPlan'])
        self.assertNotEqual(a['preview']['requestSHA256'],b['preview']['requestSHA256'])
    def test_out_of_source_range_cannot_replan_or_render_full_video(self):
        self.submission['overnightV3']['startFrame']=2300
        with patch.object(bridge,'_manifest',return_value=self.facts):
            result=bridge.preflight(self.submission,image_digest=DIGEST,control_root=None,export_root=None)
        self.assertFalse(result['renderAllowed']);self.assertIn('PREVIEW_',str(result))


class DetachedManagerSpyTests(unittest.TestCase):
    """No child starts: Popen/native identity are explicit CPU spy fixtures."""
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='overnight-manager-',dir=HERE.parents[2]);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'private';self.root.mkdir(mode=0o700)
        self.cache=manager.runtime()._cache()
        self.plan={'renderProfile':{'imageDigest':DIGEST}}
        with self.cache.PrivateTree(self.root) as root:
            root.write_json('approval.json',{'schema':'WORLD_ENGINE_UNIVERSAL_GPU_AUTHORIZATION_V1','approved':True,
                'planSHA256':self.cache.canonical_sha256(self.plan),'imageDigest':DIGEST,
                'validUntil':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),'maxWallSeconds':60,
                'maxRetries':0,'maxCostAmount':'1','currency':'USD','gpuHourlyRate':'1'})
    def test_original_approval_parser_rejects_expired_or_wrong_plan(self):
        actual=manager._read_approval(self.root/'approval.json',self.plan)
        self.assertEqual(actual['maxRetries'],0)
        with self.assertRaisesRegex(Exception,'APPROVAL_PLAN_MISMATCH'):
            manager._read_approval(self.root/'approval.json',{'wrong':'plan'})
        with self.cache.PrivateTree(self.root) as root,root.lock():
            expired=root.json('approval.json');expired['validUntil']=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()
            root.write_json('approval.json',expired,replace=True)
        with self.assertRaisesRegex(Exception,'GPU_APPROVAL_EXPIRED'):
            manager._read_approval(self.root/'approval.json',self.plan)
    def test_start_source_denial_happens_before_worker(self):
        denied=SimpleNamespace(_authorize_start=lambda *a:(_ for _ in ()).throw(RuntimeError('STUDIO_OVERNIGHT_IMAGE_PROOF_REQUIRED')))
        with patch.object(manager,'_bridge',return_value=denied),patch.object(manager.subprocess,'Popen') as child:
            with self.assertRaisesRegex(RuntimeError,'IMAGE_PROOF_REQUIRED'):
                manager.start({'videoPlan':self.plan},self.root/'approval.json',{},'x',control_root=self.root,
                    export_root=self.root/'exports',image_digest=DIGEST)
            child.assert_not_called()
    def test_duplicate_detached_start_preserves_files_and_spawns_once(self):
        request={'captureSignature':'a'*64,'parentCaptureRequest':{'fixture':'parent'},
            'preview':{'sceneSlices':[{'sceneId':'source-1'}]},'imageDigest':DIGEST}
        authority=SimpleNamespace(_authorize_start=lambda *a:None,prepare_runtime_request=lambda *a,**k:deepcopy(request))
        subprocess_identity={'pid':123456,'bootId':'CPU_TEST_ONLY','startTime':'1'}
        runtime=manager.runtime()
        with patch.object(manager,'_bridge',return_value=authority),patch.object(manager.subprocess,'Popen',return_value=SimpleNamespace(pid=123456)) as child, \
             patch.object(runtime,'_manager',return_value=SimpleNamespace(process_identity=lambda pid:subprocess_identity)):
            first=manager.start({'videoPlan':self.plan},self.root/'approval.json',{},'owner-fixture',
                control_root=self.root,export_root=self.root/'exports',image_digest=DIGEST)
            second=manager.start({'videoPlan':self.plan},self.root/'approval.json',{},'owner-fixture',
                control_root=self.root,export_root=self.root/'exports',image_digest=DIGEST)
        self.assertEqual(first['jobId'],second['jobId']);self.assertEqual(child.call_count,1)
        self.assertTrue(child.call_args.kwargs['start_new_session']);self.assertTrue(child.call_args.kwargs['close_fds'])
        with self.cache.PrivateTree(self.root) as root,root.child('overnight_jobs') as jobs,jobs.child(first['jobId']) as job:
            self.assertEqual(job.json('PLAN.json'),self.plan)
            self.assertEqual(job.json('OVERNIGHT_REQUEST.json'),request)
            self.assertEqual(job.json('PID.json'),subprocess_identity)


class PublishedSchemaTests(unittest.TestCase):
    def validator(self):
        from jsonschema import Draft202012Validator
        from referencing import Registry,Resource
        schema=json.loads((HERE/'STUDIO_OVERNIGHT_PROMPT.schema.json').read_text())
        visual=json.loads((HERE/'VISUAL_EXTENSIONS.schema.json').read_text())
        Draft202012Validator.check_schema(schema);Draft202012Validator.check_schema(visual)
        registry=Registry().with_resource(visual['$id'],Resource.from_contents(visual))
        return Draft202012Validator(schema,registry=registry)
    def test_published_fixture_schema_and_real_normalizer_agree(self):
        prompt=json.loads((HERE/'fixtures/STUDIO_OVERNIGHT_5S_PROMPT.json').read_text())
        self.validator().validate(prompt)
        normalized=contract.normalize_submission({'prompt':json.dumps(prompt)},image_digest=DIGEST,
            backend=fixture.FakeBackend(),parent_normalize=studio_contracts.normalize_submission)
        self.assertEqual(normalized['overnightV3']['operation'],'PREVIEW_5S')
    def test_schema_rejects_full80_and_ignored_options_without_network(self):
        from jsonschema import ValidationError
        prompt=json.loads((HERE/'fixtures/STUDIO_OVERNIGHT_5S_PROMPT.json').read_text())
        validator=self.validator()
        for key,value in [('operation','FULL_80S'),('softwareProbe',True),('roll',20)]:
            bad=deepcopy(prompt);bad['overnight'][key]=value
            with self.assertRaises(ValidationError):validator.validate(bad)

if __name__=='__main__':unittest.main()
