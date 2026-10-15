"""New ASTRA packaging controls; network, Docker and registry calls are mocked."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tested_astra_activation_ci',HERE/'ci.py')
ci=importlib.util.module_from_spec(spec); spec.loader.exec_module(ci)
TAG='astra-v1-711b232-12345-1'
DIGEST='sha256:'+'a'*64
CONFIG='sha256:'+'b'*64


class ActivationCISafety(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='astra-ci-test-'); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.env={'RESULT_CI_STATE':str(self.root/'state.json'),'RUNNER_TEMP':str(self.root),
            'RUNNER_ENVIRONMENT':'github-hosted','GITHUB_REPOSITORY':'dimon3898-sys/yeonhwarok-free',
            'RESULT_REPOSITORY_PRIVATE':'false','RESULT_RUNNER_LABEL':'ubuntu-24.04','RESULT_PHASE':'build',
            'GITHUB_REF':'refs/heads/'+ci.BRANCH,'GITHUB_SHA':'c'*40,'GITHUB_RUN_ID':'12345',
            'GITHUB_RUN_ATTEMPT':'1','RESULT_PUBLISHED_TAG':TAG,'RESULT_PUBLISHED_DIGEST':DIGEST,
            'GITHUB_OUTPUT':str(self.root/'outputs')}
        self.addCleanup(patch.stopall); patch.dict(os.environ,self.env,clear=True).start()
        self.command=Mock(side_effect=AssertionError('unexpected command'))
        patch.object(ci,'run',self.command).start(); patch.object(ci.controls,'run',self.command).start()
        self.process=patch.object(ci.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='',stderr='')).start()
        patch.object(ci.urllib.request,'urlopen',side_effect=AssertionError('network forbidden')).start()
        self.old=SimpleNamespace(require_space=Mock(return_value={'freeBytes':22*1024**3}),
            check_image=Mock(return_value={'status':'PASS'}),login=Mock())
        patch.object(ci,'helpers',return_value=self.old).start(); patch.object(ci.controls,'helpers',return_value=self.old).start()
        self.registry=Mock(); self.registry.check_tag.return_value={'status':'TAG_UNUSED'}
        self.registry.inspect_digest.return_value={'digest':DIGEST,'configDigest':CONFIG}
        registry_module=ModuleType('registry_guard'); registry_module.RegistryGuard=lambda:self.registry
        registry_module.validate_tag=lambda value:value; registry_module.validate_digest=lambda value:value
        patch.dict(sys.modules,{'registry_guard':registry_module}).start()

    def seed(self,**overrides):
        value=ci.state(); value.update(tag=TAG,image=ci.IMAGE+':'+TAG,configDigest=CONFIG,
            focusedTests={'status':'PASS','exitCode':0},softwareProbeBeforeBuild={'exitCode':0},
            verification='PASS',secretScan={'status':'PASS','findings':0})
        value.update(overrides);ci.save(value);return value

    def facts(self):
        return {'Id':CONFIG,'Size':100,'Os':'linux','Architecture':'amd64','Config':{
            'Entrypoint':['/usr/bin/tini','-g','--','/usr/bin/python3','/opt/world-engine-storage-fix/launch.py'],
            'Env':['PATH=/usr/bin'],'Labels':{
                'org.opencontainers.image.revision':'2f9158ba2df2a9f58362fb0b17118b8dc19f705a',
                'world-engine.astra-activation.source-revision':self.env['GITHUB_SHA'],
                'world-engine.astra-activation.parent-digest':ci.PARENT_DIGEST,
                'world-engine.detached-render.source-revision':'aaa9347bcb50eaa480dc83e135bc2ebca6f1f5f2'}}}

    def test_free_public_standard_exact_branch_required(self):
        for key,value in [('RUNNER_ENVIRONMENT','self-hosted'),('RESULT_REPOSITORY_PRIVATE','true'),
                ('RESULT_RUNNER_LABEL','larger-runner'),('GITHUB_REF','refs/heads/main')]:
            with self.subTest(key=key),patch.dict(os.environ,{key:value}),self.assertRaises(RuntimeError):ci.preflight()
        self.old.require_space.assert_not_called();self.command.assert_not_called()

    def test_existing_protected_changes_forbidden_and_unique_astra_tag(self):
        self.assertEqual(ci.controls.PATCHES,{})
        def git(args,**kwargs):
            if args[1]=='rev-parse':return self.env['GITHUB_SHA']
            if args[1]=='diff':return changed
            return ''
        self.command.side_effect=git
        for changed in ['renderer.py','world-simulation-shorts-engine/recovery/gcube-detached-render-v1/job_manager.py']:
            with self.subTest(changed=changed),self.assertRaises(RuntimeError):ci.preflight()
        changed=ci.NAMESPACE+'/astra_material.mjs';ci.preflight()
        self.assertEqual(ci.state()['tag'],TAG)
        self.assertIsNotNone(ci.TAG_PATTERN.fullmatch(TAG))
        self.assertIsNone(ci.TAG_PATTERN.fullmatch('latest'))
        self.assertIsNone(ci.TAG_PATTERN.fullmatch('rtx4080s-2f9158b-12345-1'))

    def test_manifest_preserves_new_runtime_and_pinned_upload_parent_sources(self):
        result=ci.generate_manifest()
        self.assertEqual(set(result['files']),set(ci.RUNTIME_FILES))
        self.assertEqual(result['sourceCommit'],self.env['GITHUB_SHA'])
        self.assertEqual(result['parentImage'],ci.BASE)
        self.assertEqual(len(result['repoDependencies']),2)
        self.assertEqual(len(result['inheritedFiles']),11)
        self.assertEqual(result['profileId'],'ASTRA_SOURCE_MATERIAL_V1')
        original=ci.sha
        with patch.object(ci,'sha',side_effect=lambda path:'0'*64 if Path(path).name=='gpu_upload.mjs' else original(path)):
            with self.assertRaisesRegex(RuntimeError,'PINNED_UPLOAD_SOURCE_REQUIRED'):ci.generate_manifest()

    def test_actual_software_probe_success_must_be_test_only_without_gpu_claim(self):
        self.seed()
        for report in [{},{'status':'PASS','testOnly':False,'gpuRenderingVerified':False},
                       {'status':'PASS','testOnly':True,'gpuRenderingVerified':True}]:
            self.process.return_value=SimpleNamespace(returncode=0,stdout=json.dumps(report),stderr='')
            with self.subTest(report=report),self.assertRaisesRegex(RuntimeError,'SOFTWARE_ACTIVATION_PROBE_REQUIRED'):
                ci.software_probe('synthetic',phase='synthetic')
        report={'schema':'ASTRA_ACTUAL_SOFTWARE_RENDER_PROBE_V1','status':'PASS','testOnly':True,
            'gpuRenderingVerified':False,'physicalNvidiaExecuted':False,'actualShaderCompile':True,
            'softwareWebGLDrawExecuted':True,'actualSoftwareABPixelsDiffer':True,'cameraAndGeometryEqual':True,
            'originalSourcesUnchanged':True}
        self.process.return_value=SimpleNamespace(returncode=0,stdout=json.dumps(report),stderr='')
        self.assertEqual(ci.software_probe('synthetic',phase='synthetic'),report)
        args=self.process.call_args.args[0]
        self.assertIn('--network=none',args);self.assertNotIn('--gpus',args)

    def test_stage_requires_focused_pass_and_real_software_probe(self):
        for updates in [{'focusedTests':{'status':'FAIL'}},{'softwareProbeBeforeBuild':{'exitCode':1}}]:
            self.seed(**updates)
            with self.assertRaisesRegex(RuntimeError,'TEST_AND_SOFTWARE_PROBE_REQUIRED'):ci.stage()
        self.process.assert_not_called()

    def test_context_allowlist_rejects_unexpected_file_before_docker_build(self):
        self.seed();ci.stage();context=Path(ci.state()['context'])
        self.assertFalse(context.is_relative_to(ci.REPO))
        self.assertEqual(set(path.name for path in context.iterdir()),{'activation','upload','Dockerfile'})
        (context/'unexpected').write_text('synthetic')
        with self.assertRaisesRegex(RuntimeError,'EXPLICIT_BUILD_CONTEXT_REQUIRED'):ci.build()
        self.process.assert_not_called()

    def test_image_provenance_entrypoint_and_credential_names_rejected(self):
        self.command.side_effect=None;self.command.return_value=json.dumps([self.facts()]);ci.inspect_image('synthetic')
        for key in self.facts()['Config']['Labels']:
            value=self.facts();value['Config']['Labels'][key]='wrong';self.command.return_value=json.dumps([value])
            with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'PROVENANCE'):ci.inspect_image('synthetic')
        value=self.facts();value['Config']['Entrypoint']=['python3','new-server.py'];self.command.return_value=json.dumps([value])
        with self.assertRaisesRegex(RuntimeError,'ENTRYPOINT'):ci.inspect_image('synthetic')
        value=self.facts();value['Config']['Env']=['GH_TOKEN=REDACTED_SYNTHETIC'];self.command.return_value=json.dumps([value])
        with self.assertRaisesRegex(RuntimeError,'CREDENTIAL_ENV'):ci.inspect_image('synthetic')

    def test_image_hash_manifest_must_match_current_source(self):
        self.command.side_effect=None;self.command.return_value=json.dumps({'status':'PASS','manifestSha256':'0'*64})
        with self.assertRaisesRegex(RuntimeError,'MANIFEST_SOURCE_MISMATCH'):ci.image_hashes('synthetic')

    def test_publish_requires_verification_and_zero_secrets(self):
        for updates in [{'verification':'FAIL'},{'secretScan':{'status':'PASS','findings':1}}]:
            self.seed(**updates)
            with self.assertRaises(RuntimeError):ci.publish()
        self.old.login.assert_not_called();self.registry.check_tag.assert_not_called()

    def test_unique_tag_rechecked_and_only_own_auth_removed(self):
        self.seed();own=self.root/'own-auth';own.mkdir();(own/'config.json').write_text('synthetic')
        other=self.root/'preserved-auth';other.mkdir();(other/'config.json').write_text('unchanged')
        self.old.login.return_value=(own,{})
        self.registry.check_tag.side_effect=[{'status':'TAG_UNUSED'},RuntimeError('TAG_ALREADY_EXISTS')]
        with self.assertRaisesRegex(RuntimeError,'TAG_ALREADY_EXISTS'):ci.publish()
        self.assertFalse(own.exists());self.assertEqual((other/'config.json').read_text(),'unchanged')
        self.command.assert_not_called()

    def test_independent_pull_not_ready_on_any_source_mismatch(self):
        self.seed();own=self.root/'auth';own.mkdir();self.old.login.return_value=(own,{})
        self.command.side_effect=None
        with patch.object(ci.controls,'inspect_image',return_value=self.facts()),patch.object(ci.controls,'image_hashes',side_effect=RuntimeError('HASH_MISMATCH')):
            with self.assertRaisesRegex(RuntimeError,'HASH_MISMATCH'):ci.pull()
        self.assertIs(ci.state()['pullVerified'],False)
        self.old.check_image.assert_called_once_with(ci.IMAGE+'@'+DIGEST,hashes_only=True)

    def test_docker_preserves_existing_paths_no_autostart_or_extra_dependencies(self):
        text=(HERE/'Dockerfile').read_text();self.assertIn('FROM '+ci.BASE,text)
        for forbidden in ['ENTRYPOINT [','CMD [','HEALTHCHECK --','EXPOSE ','apt-get','npm ','pip ','ARG GH_TOKEN']:
            self.assertNotIn(forbidden,text)
        self.assertIn('test ! -e /var/lib/world-engine-private/engine/job-astra-v1',text)
        self.assertNotIn('/engine/job-control-v1',text)
        self.assertIn('prepare_activation.py --verify-extension',text)


if __name__=='__main__':unittest.main()
