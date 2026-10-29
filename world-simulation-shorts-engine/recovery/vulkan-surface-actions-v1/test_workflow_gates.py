"""New preparation checks only; Docker/network/subprocess execution is forbidden."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import yaml

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('surface_actions_prep', HERE / 'actions_candidate.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
WORKFLOW = HERE.parents[2] / '.github/workflows/world-engine-vulkan-surface-candidate.yml'

def approved():
    env = {'GITHUB_ACTIONS':'true','GITHUB_EVENT_NAME':'workflow_dispatch',
        'GITHUB_REPOSITORY':module.REPO,'GITHUB_REF':module.BRANCH,'GITHUB_RUN_ATTEMPT':'1',
        'RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Linux','RUNNER_ARCH':'X64',
        'SIGNAL_APPROVAL':'BUILD_SURFACE_CANDIDATE_LOCAL_ONLY','ZERO_COST_CONFIRMED':'true',
        'APPROVED_HEAD_SHA':'a'*40,'GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'123'}
    cost = {'status':'SATISFIED_USER_ATTESTED','actionsBudgetUSD':0,'budgetScope':'ENTIRE_ACCOUNT',
        'stopUsageWhenBudgetLimitReached':True,'paymentMethodRegistered':False}
    return env, cost

class WorkflowPrepTests(unittest.TestCase):
    def setUp(self):
        self.block = patch.object(module.subprocess, 'run', side_effect=AssertionError('DOCKER_SUBPROCESS_FORBIDDEN_IN_PREP_TEST'))
        self.block.start()
    def tearDown(self): self.block.stop()
    def test_01_manual_only_no_write_or_artifact_permissions(self):
        flow = yaml.safe_load(WORKFLOW.read_text())
        self.assertEqual(set(flow['on']), {'workflow_dispatch'})
        self.assertEqual(flow['permissions'], {'contents':'read','packages':'read'})
        job = flow['jobs']['surface-candidate']
        self.assertEqual(job['runs-on'], 'ubuntu-24.04')
        self.assertFalse(flow['on']['workflow_dispatch']['inputs']['zero_cost_confirmed']['default'])
        self.assertEqual(job['steps'][0]['with']['persist-credentials'], False)
        self.assertNotIn('upload-artifact', WORKFLOW.read_text())
        self.assertNotIn('docker push', WORKFLOW.read_text())
        self.assertFalse(flow['concurrency']['cancel-in-progress'])
    def test_02_only_fresh_reviewed_manual_free_runner_context_is_accepted(self):
        env,cost=approved(); module.validate_dispatch(env,cost,'a'*40)
        for key,value in [('GITHUB_EVENT_NAME','push'),('GITHUB_RUN_ATTEMPT','2'),
            ('ZERO_COST_CONFIRMED','false'),('GITHUB_REF','refs/heads/main'),
            ('RUNNER_ENVIRONMENT','self-hosted'),('APPROVED_HEAD_SHA','b'*40),
            ('SIGNAL_APPROVAL',''),('RUNNER_OS','Windows')]:
            with self.subTest(key=key):
                changed=dict(env);changed[key]=value
                with self.assertRaises(RuntimeError): module.validate_dispatch(changed,cost,'a'*40)
    def test_03_historical_budget_failures_block_before_docker(self):
        env,cost=approved()
        for key,value in [('actionsBudgetUSD',1),('actionsBudgetUSD',False),
            ('budgetScope','OTHER'),('stopUsageWhenBudgetLimitReached',False),('paymentMethodRegistered',True)]:
            changed=dict(cost); changed[key]=value
            with self.assertRaises(RuntimeError): module.validate_dispatch(env,changed,'a'*40)
    def test_04_vfs_and_inadequate_capacity_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError,'VFS_FORBIDDEN'): module.capacity('vfs',1,10**15)
        with self.assertRaisesRegex(RuntimeError,'INSUFFICIENT'): module.capacity('overlay2',100,0)
        self.assertEqual(module.capacity('overlay2',100,module.RESERVE+400),module.RESERVE+400)
    def test_05_one_attempt_marker_prevents_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'evidence').mkdir();(root/'attempts').mkdir()
            module.claim(root,'pull')
            with self.assertRaises(FileExistsError): module.claim(root,'pull')
            module.write(root/'evidence/FAILURE.json',{'status':'BLOCKED'})
            with self.assertRaisesRegex(RuntimeError,'ALREADY_BLOCKED'): module.claim(root,'build')
    def test_06_failed_prerequisite_blocks_build_and_prepared_is_not_built(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'evidence').mkdir();(root/'attempts').mkdir()
            module.write(root/'evidence/STAGE_RECEIPT.json',{'status':'BLOCKED'})
            with self.assertRaisesRegex(RuntimeError,'PREVIOUS_STAGE'): module.claim(root,'build','STAGE_RECEIPT.json')
            module.write(root/'evidence/STAGE_RECEIPT.json',{'status':'PREPARED_NOT_BUILT'})
            module.claim(root,'build','STAGE_RECEIPT.json')
    def test_07_log_collection_excludes_private_config_and_raw_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'evidence').mkdir();(root/'private').mkdir()
            module.write(root/'evidence/BUILD.json',{'status':'PASS','candidateImageID':'sha256:'+'a'*64})
            (root/'evidence/raw-stderr.log').write_text('TEST_ONLY_SECRET_SENTINEL')
            (root/'private/parent-config.json').write_text('TEST_ONLY_SECRET_SENTINEL')
            output=io.StringIO()
            with contextlib.redirect_stdout(output): module.collect(root)
            self.assertNotIn('TEST_ONLY_SECRET_SENTINEL',output.getvalue())
            self.assertNotIn('raw-stderr',output.getvalue())
            self.assertIn('SURFACE_SAFE_EVIDENCE_FILES=1',output.getvalue())
    def test_08_evidence_bounds_and_symlink_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'evidence').mkdir()
            target=root/'target.json';target.write_text('{}')
            (root/'evidence/BUILD.json').symlink_to(target)
            with self.assertRaisesRegex(RuntimeError,'INVALID'): module.collect(root)
            (root/'evidence/BUILD.json').unlink()
            (root/'evidence/BUILD.json').write_bytes(b'x'*(256*1024+1))
            with self.assertRaisesRegex(RuntimeError,'INVALID'): module.collect(root)
    def test_09_stage_command_and_prepared_receipt_integration_without_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ['evidence','attempts','private','context-out']: (root/name).mkdir()
            module.write(root/'evidence/PULL.json',{'status':'PASS'})
            calls=[]
            def fake_run(args,**kwargs):
                calls.append(args)
                context=root/'context-out/context'; context.mkdir()
                module.write(context/'STAGE_RECEIPT.json',{'status':'PREPARED_NOT_BUILT'})
                return b'{}'
            with patch.dict(module.os.environ,{'GITHUB_WORKSPACE':str(root)}), patch.object(module,'run',side_effect=fake_run):
                module.stage(root)
            self.assertEqual(len(calls),1)
            args=calls[0]
            self.assertIn(str(module.os.getuid())+':'+str(module.os.getgid()),args)
            self.assertIn('--network=none',args);self.assertIn(module.PARENT,args)
            self.assertEqual(json.loads((root/'evidence/STAGE_RECEIPT.json').read_text())['status'],'PREPARED_NOT_BUILT')
    def test_10_verify_cli_output_and_four_layers_without_docker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ['evidence','attempts','private','context-out']: (root/name).mkdir()
            parent={'Id':'sha256:'+'a'*64,'Config':{'User':'0'},'RootFS':{'Layers':['p1','p2']}}
            child={'Id':'sha256:'+'b'*64,'Config':{'User':'0'},'RootFS':{'Layers':['p1','p2','c1','c2','c3','c4']}}
            module.write(root/'private/parent-inspect.json',parent)
            module.write(root/'private/candidate-inspect.json',child)
            module.write(root/'evidence/BUILD.json',{'status':'PASS','candidateImageID':child['Id']})
            calls=[]
            def fake_run(args,**kwargs):
                calls.append(args)
                if 'run' in args:
                    self.assertIn('--output',args);self.assertIn('1000:1000',args)
                    self.assertIn('/result/CONNECTION_VERIFY.json',args)
                    module.write(root/'verify-out/CONNECTION_VERIFY.json',{'status':'PASS','synthetic':True})
                    return b'{"status":"PASS"}'
                return json.dumps([parent]).encode()
            with patch.object(module,'run',side_effect=fake_run): module.verify(root)
            self.assertEqual(len(calls),2)
            self.assertTrue(json.loads((root/'evidence/IMAGE_SCOPE.json').read_text())['parentPreserved'])
            self.assertEqual(json.loads((root/'evidence/IMAGE_SCOPE.json').read_text())['additionalCopyLayers'],4)
    def test_11_prebuild_context_gate_rejects_extra_instruction_and_tampered_bytes(self):
        spec=importlib.util.spec_from_file_location('fixture_package',HERE/'package_candidate.py')
        package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
        with tempfile.TemporaryDirectory() as tmp:
            context=Path(tmp); overlay=context/'overlay'; rows={}
            for name in package.OVERLAY_FILES:
                path=overlay/name;path.parent.mkdir(parents=True,exist_ok=True)
                raw=b'new-synthetic-fixture';path.write_bytes(raw)
                rows[name]={'bytes':len(raw),'sha256':module.digest(raw)}
            entry=package.expected_entrypoint('a'*64,'b'*64)
            receipt={'status':'PREPARED_NOT_BUILT','parentImageDigest':module.PARENT_DIGEST,
                'sourceCommit':module.SOURCE_COMMIT,'entrypoint':entry,'overlayFiles':rows,
                'runtimeManifestSHA256':'a'*64,'startupManifestSHA256':'b'*64}
            module.write(context/'STAGE_RECEIPT.json',receipt)
            expected=package.expected_dockerfile(entry);(context/'Dockerfile').write_text(expected)
            with patch.object(module,'PROFILE_SHA',module.digest(b'new-synthetic-fixture')):
                module.validate_build_context(context)
                (context/'Dockerfile').write_text(expected+'RUN false\n')
                with self.assertRaisesRegex(RuntimeError,'INSTRUCTIONS_CHANGED'): module.validate_build_context(context)
                (context/'Dockerfile').write_text(expected)
                (overlay/module.PROFILE).write_bytes(b'tampered')
                with self.assertRaisesRegex(RuntimeError,'BYTES_CHANGED'): module.validate_build_context(context)

if __name__=='__main__': unittest.main(verbosity=2)
