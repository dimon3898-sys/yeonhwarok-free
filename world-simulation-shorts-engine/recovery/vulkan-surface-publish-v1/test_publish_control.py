"""New publication-control simulations only. All external effects are mocked."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import yaml

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('publish_controller',HERE/'publish_candidate.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
ROOT=HERE.parents[2]

def environment():
    return {'GITHUB_ACTIONS':'true','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_RUN_ATTEMPT':'1',
        'GITHUB_REPOSITORY':'dimon3898-sys/yeonhwarok-free',
        'GITHUB_REF':'refs/heads/recovery/g1-capture-diagnostic-contract-20261028',
        'RUNNER_ENVIRONMENT':'github-hosted','RUNNER_OS':'Linux','RUNNER_ARCH':'X64',
        'PUBLICATION_APPROVAL':'PUBLISH_VERIFIED_SURFACE_CANDIDATE_ONCE',
        'SIGNAL_APPROVAL':'BUILD_SURFACE_CANDIDATE_LOCAL_ONLY','ZERO_COST_CONFIRMED':'true',
        'APPROVED_HEAD_SHA':'a'*40,'GITHUB_SHA':'a'*40,'GITHUB_RUN_ID':'123'}

def approved_policy():
    return {'schema':'WORLD_ENGINE_SURFACE_PUBLISH_POLICY_V1','status':'APPROVED_FOR_SEPARATE_MANUAL_RUN',
        'publicationApprovalRecorded':True,'candidateRepository':module.CANDIDATE_REPO,
        'successfulRepository':module.SUCCESS_REPO,'parentDigest':module.PARENT_DIGEST,
        'publisherIdentity':'test-only-publisher','publisherCanWriteSuccessfulPackage':False,
        'publisherCanDeleteSuccessfulPackage':False,'credentialHasDeleteScope':False,
        'candidatePackageExclusiveWriterVerified':True,'aclEvidenceSHA256':'b'*64,
        'approvedSkopeoVersion':'skopeo version TEST_ONLY'}

class PublicationControlTests(unittest.TestCase):
    def setUp(self):
        self.block=patch.object(module.subprocess,'run',side_effect=AssertionError('EXTERNAL_COMMAND_FORBIDDEN'))
        self.block.start()
    def tearDown(self):self.block.stop()
    def test_01_original_build_steps_unchanged_and_only_publish_step_has_secret(self):
        old=yaml.safe_load((ROOT/'.github/workflows/world-engine-vulkan-surface-candidate.yml').read_text())
        new=yaml.safe_load((ROOT/'.github/workflows/world-engine-vulkan-surface-publish-candidate.yml').read_text())
        self.assertEqual(set(new['on']),{'workflow_dispatch'})
        self.assertEqual(new['permissions'],old['permissions'])
        self.assertEqual(new['permissions'],{'contents':'read','packages':'read'})
        oldsteps=old['jobs']['surface-candidate']['steps'];steps=new['jobs']['surface-candidate']['steps']
        for step in oldsteps:self.assertEqual(sum(x==step for x in steps),1)
        self.assertEqual(new['jobs']['surface-candidate']['runs-on'],'ubuntu-24.04')
        secretsteps=[s for s in steps if 'WORLD_ENGINE_SURFACE_GHCR_PUBLISHER_TOKEN' in json.dumps(s)]
        self.assertEqual(len(secretsteps),1)
        self.assertIn('publish --work',secretsteps[0]['run'])
        self.assertFalse(new['concurrency']['cancel-in-progress'])
    def test_02_checked_in_policy_is_disabled_before_any_tool_or_network(self):
        policy=json.loads((HERE/'PUBLISH_POLICY.json').read_text())
        with self.assertRaisesRegex(RuntimeError,'NOT_AUTHORIZED'):module.policy_gate(policy,environment())
    def test_03_acl_and_separate_manual_approval_are_required(self):
        policy=approved_policy();env=environment();module.policy_gate(policy,env)
        for k,v in [('publisherCanWriteSuccessfulPackage',True),('publisherCanDeleteSuccessfulPackage',True),
            ('credentialHasDeleteScope',True),('candidatePackageExclusiveWriterVerified',False),
            ('aclEvidenceSHA256',None),('candidateRepository',module.SUCCESS_REPO)]:
            changed=dict(policy);changed[k]=v
            with self.assertRaises(RuntimeError):module.policy_gate(changed,env)
        changed=dict(env);changed['PUBLICATION_APPROVAL']=''
        with self.assertRaises(RuntimeError):module.policy_gate(policy,changed)
    def test_04_registry_absence_is_not_inferred_from_auth_or_network_error(self):
        target=module.contract.candidate_destination('123',1,'a'*40)
        for stderr in [b'unauthorized',b'network timeout',b'permission denied',b'unknown error']:
            fake=subprocess.CompletedProcess([],1,b'',stderr)
            with patch.object(module,'command',return_value=fake):
                with self.assertRaisesRegex(RuntimeError,'ABSENCE_NOT_PROVEN'):module.inspect_raw('test-tool',target,'test-auth',absent_allowed=True)
        fake=subprocess.CompletedProcess([],1,b'',b'manifest unknown')
        with patch.object(module,'command',return_value=fake):self.assertIsNone(module.inspect_raw('test-tool',target,'test-auth',absent_allowed=True))
    def test_05_claim_and_failure_receipt_block_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);(work/'attempts').mkdir();(work/'evidence').mkdir()
            module.claim(work,'publish')
            with self.assertRaises(FileExistsError):module.claim(work,'publish')
            module.write(work/'evidence/PUBLISH_FAILURE.json',{'status':'BLOCKED'})
            with self.assertRaisesRegex(RuntimeError,'ALREADY_BLOCKED'):module.claim(work,'prepare')
    def _publish_fixture(self,tmp):
        root=Path(tmp);work=root/'work';build=root/'build';policy_dir=root/'tool'
        for p in [work/'evidence',work/'private',work/'attempts',build/'evidence',policy_dir]:p.mkdir(parents=True)
        policy=approved_policy();module.write(policy_dir/'PUBLISH_POLICY.json',policy)
        module.write(work/'evidence/PUBLICATION_PREFLIGHT.json',{'status':'PASS','policySHA256':module.digest((policy_dir/'PUBLISH_POLICY.json').read_bytes())})
        evidence={'new-synthetic-receipts':True}
        ready={'status':'PASS','destination':module.contract.candidate_destination('123',1,'a'*40),
            'candidateImageID':'sha256:'+'c'*64,'expectedRegistryDigest':'sha256:'+'d'*64,
            'evidenceSHA256':module.digest(json.dumps(evidence,sort_keys=True,separators=(',',':')).encode())}
        module.write(work/'evidence/REGISTRY_READY.json',ready)
        module.write(work/'private/expected-diffids.json',[])
        env=environment();env.update(SURFACE_CANDIDATE_GHCR_USER=policy['publisherIdentity'],SURFACE_CANDIDATE_GHCR_TOKEN='NON_SECRET_TEST_CREDENTIAL')
        return work,build,policy_dir,evidence,ready,env
    def _patch_publish(self,stack,policy_dir,evidence,ready):
        stack.enter_context(patch.object(module,'HERE',policy_dir))
        stack.enter_context(patch.object(module,'receipts',return_value=evidence))
        stack.enter_context(patch.object(module,'skopeo',return_value='synthetic-skopeo'))
        stack.enter_context(patch.object(module.contract,'validate_evidence',return_value={'status':'PASS'}))
        stack.enter_context(patch.object(module.contract,'validate_registry_ready',return_value={'expectedRegistryDigest':ready['expectedRegistryDigest']}))
        stack.enter_context(patch.object(module.contract,'validate_publish_preconditions',return_value={'status':'PASS'}))
        stack.enter_context(patch.object(module.contract,'validate_registry_readback',return_value={'status':'PASS'}))
    def test_06_successful_publication_uses_one_preserve_digest_transfer(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            work,build,policy_dir,evidence,ready,env=self._publish_fixture(tmp)
            self._patch_publish(stack,policy_dir,evidence,ready)
            stack.enter_context(patch.dict(os.environ,env,clear=True))
            stack.enter_context(patch.object(module,'inspect_raw',side_effect=[None,b'parent',b'tag',b'digest',b'parent']))
            calls=[]
            def fake(args,**kwargs):
                calls.append(args);Path(args[args.index('--digestfile')+1]).write_text(ready['expectedRegistryDigest'])
                self.assertNotIn('NON_SECRET_TEST_CREDENTIAL',' '.join(map(str,args)))
                self.assertIn('--preserve-digests',args);self.assertIn('--retry-times=0',args)
                return subprocess.CompletedProcess(args,0,b'',b'')
            stack.enter_context(patch.object(module,'command',side_effect=fake))
            module.publish(work,build)
            self.assertEqual(len(calls),1)
            self.assertEqual(list((work/'private').glob('publisher-auth-*')),[])
            receipt=module.load(work/'evidence/PUBLISH_RECEIPT.json')
            self.assertEqual(receipt['pushAttempts'],1);self.assertTrue(receipt['tagAndDigestBodyMatched'])
    def test_07_failed_transfer_is_not_retried_or_read_back_as_success(self):
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            work,build,policy_dir,evidence,ready,env=self._publish_fixture(tmp)
            self._patch_publish(stack,policy_dir,evidence,ready)
            stack.enter_context(patch.dict(os.environ,env,clear=True))
            reads=stack.enter_context(patch.object(module,'inspect_raw',side_effect=[None,b'parent']))
            transfer=stack.enter_context(patch.object(module,'command',side_effect=RuntimeError('PUBLICATION_COMMAND_FAILED')))
            with self.assertRaisesRegex(RuntimeError,'COMMAND_FAILED'):module.publish(work,build)
            self.assertEqual(transfer.call_count,1);self.assertEqual(reads.call_count,2)
            self.assertTrue((work/'private/mutation-intent.json').exists())
            self.assertEqual(module.load(work/'evidence/PUBLISH_INTENT.json')['status'],'MUTATION_PENDING_UNCONFIRMED')
            self.assertFalse((work/'evidence/PUBLISH_RECEIPT.json').exists())
            self.assertEqual(list((work/'private').glob('publisher-auth-*')),[])
    def test_08_collection_never_includes_authfile_or_raw_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'evidence').mkdir();(root/'private').mkdir()
            (root/'private/auth.json').write_text('SYNTHETIC_SECRET_SENTINEL')
            (root/'evidence/raw.stderr').write_text('SYNTHETIC_SECRET_SENTINEL')
            module.write(root/'evidence/PUBLISH_FAILURE.json',{'status':'BLOCKED','code':'PUBLICATION_COMMAND_FAILED'})
            output=io.StringIO()
            with contextlib.redirect_stdout(output):module.collect(root)
            self.assertNotIn('SYNTHETIC_SECRET_SENTINEL',output.getvalue())
            self.assertNotIn('raw.stderr',output.getvalue())
    def test_09_secret_environment_is_removed_from_child_process(self):
        with patch.dict(os.environ,{'SURFACE_CANDIDATE_GHCR_TOKEN':'NON_SECRET_TEST','SURFACE_CANDIDATE_GHCR_USER':'TEST','PATH':'SAFE'},clear=True):
            env=module.clean_env();self.assertNotIn('SURFACE_CANDIDATE_GHCR_TOKEN',env)
            self.assertNotIn('SURFACE_CANDIDATE_GHCR_USER',env);self.assertEqual(env['PATH'],'SAFE')

if __name__=='__main__':unittest.main(verbosity=2)
