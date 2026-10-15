"""Focused new quality packaging controls; external commands are mocked."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import zlib

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('quality_ci_tested',HERE/'ci.py')
ci=importlib.util.module_from_spec(spec);spec.loader.exec_module(ci)
TAG='visual-v1-a7df81f-12345-1'
DIGEST='sha256:'+'a'*64
CONFIG='sha256:'+'b'*64


def png(width=1080,height=1920):
    def chunk(name,body):return struct.pack('>I',len(body))+name+body+struct.pack('>I',zlib.crc32(name+body)&0xffffffff)
    raw=(b'\x00'+b'\x20\x40\x60'*width)*height
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')


class QualityCISafety(unittest.TestCase):
    def setUp(self):
        self.area=tempfile.TemporaryDirectory(prefix='quality-ci-test-');self.addCleanup(self.area.cleanup)
        self.root=Path(self.area.name)
        self.env={'RESULT_CI_STATE':str(self.root/'state.json'),'RUNNER_TEMP':str(self.root),
            'RUNNER_ENVIRONMENT':'github-hosted','GITHUB_REPOSITORY':'dimon3898-sys/yeonhwarok-free',
            'RESULT_REPOSITORY_PRIVATE':'false','RESULT_RUNNER_LABEL':'ubuntu-24.04','RESULT_PHASE':'build',
            'GITHUB_REF':'refs/heads/'+ci.BRANCH,'GITHUB_SHA':'c'*40,'GITHUB_RUN_ID':'12345','GITHUB_RUN_ATTEMPT':'1',
            'RESULT_PUBLISHED_TAG':TAG,'RESULT_PUBLISHED_DIGEST':DIGEST,'GITHUB_OUTPUT':str(self.root/'outputs')}
        self.addCleanup(patch.stopall);patch.dict(os.environ,self.env,clear=True).start()
        self.command=Mock(side_effect=AssertionError('unexpected external command'))
        patch.object(ci,'run',self.command).start();patch.object(ci.controls,'run',self.command).start()
        self.process=patch.object(ci.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='',stderr='')).start()
        self.base=SimpleNamespace(require_space=Mock(return_value={'freeBytes':22*1024**3}),check_image=Mock(return_value={'status':'PASS'}),login=Mock())
        patch.object(ci,'helpers',return_value=self.base).start();patch.object(ci.controls,'helpers',return_value=self.base).start()
        self.registry=Mock();self.registry.check_tag.return_value={'status':'TAG_UNUSED'}
        self.registry.inspect_digest.return_value={'digest':DIGEST,'configDigest':CONFIG}
        module=ModuleType('registry_guard');module.RegistryGuard=lambda:self.registry
        module.validate_tag=lambda value:value;module.validate_digest=lambda value:value
        patch.dict(sys.modules,{'registry_guard':module}).start()

    def seed(self,**overrides):
        value=ci.state();value.update(tag=TAG,image=ci.IMAGE+':'+TAG,configDigest=CONFIG,
            focusedTests={'status':'PASS'},softwareProbeBeforeBuild={'exitCode':0},verification='PASS',secretScan={'status':'PASS','findings':0})
        value.update(overrides);ci.save(value);return value

    def facts(self):
        return {'Id':CONFIG,'Size':100,'Os':'linux','Architecture':'amd64','Config':{
            'Env':['PATH=/usr/bin'],'Entrypoint':['/usr/bin/tini','-g','--','/usr/bin/python3','/opt/world-engine-storage-fix/launch.py'],
            'Labels':{'org.opencontainers.image.revision':'2f9158ba2df2a9f58362fb0b17118b8dc19f705a',
              'world-engine.astra-activation.source-revision':'7c4a0b6b4b0074bd06428dc11224a65f7f8fae58',
              'world-engine.visual-quality.source-revision':self.env['GITHUB_SHA'],
              'world-engine.visual-quality.parent-digest':ci.PARENT_DIGEST}}}

    def test_free_public_standard_exact_branch_only(self):
        for key,value in [('RUNNER_ENVIRONMENT','self-hosted'),('RESULT_REPOSITORY_PRIVATE','true'),
                          ('RESULT_RUNNER_LABEL','larger-runner'),('GITHUB_REF','refs/heads/main')]:
            with self.subTest(key=key),patch.dict(os.environ,{key:value}),self.assertRaises(RuntimeError):ci.preflight()
        self.command.assert_not_called();self.base.require_space.assert_not_called()

    def test_old_source_changes_are_forbidden_and_new_tag_is_task_scoped(self):
        self.assertEqual(ci.controls.PATCHES,{})
        def git(args,**kwargs):
            if args[1]=='rev-parse':return self.env['GITHUB_SHA']
            if args[1]=='diff':return changed
            return ''
        self.command.side_effect=git
        for changed in ['renderer.py',ci.PRIOR_NAMESPACE+'/astra_material.mjs']:
            with self.subTest(changed=changed),self.assertRaises(RuntimeError):ci.preflight()
        changed=ci.NAMESPACE+'/quality_material.mjs';ci.preflight();self.assertEqual(ci.state()['tag'],TAG)
        self.assertIsNotNone(ci.TAG_PATTERN.fullmatch(TAG));self.assertIsNone(ci.TAG_PATTERN.fullmatch('latest'))
        self.assertIsNone(ci.TAG_PATTERN.fullmatch('astra-v1-711b232-12345-1'))

    def test_original_astra_fourteen_file_closure_and_manifest_are_pinned(self):
        parent,closure=ci.parent_closure();self.assertEqual(len(closure),14)
        self.assertEqual(parent['sourceCommit'],'7c4a0b6b4b0074bd06428dc11224a65f7f8fae58')
        original=ci.sha
        with patch.object(ci,'sha',side_effect=lambda path:'0'*64 if Path(path).name=='ACTIVATION_FILES.json' else original(path)):
            with self.assertRaisesRegex(RuntimeError,'PINNED_ASTRA_PARENT_MANIFEST_REQUIRED'):ci.parent_closure()

    def test_manifest_selects_only_explicit_new_runtime_and_all_prior_additions(self):
        value=ci.generate_manifest();self.assertEqual(set(value['files']),set(ci.RUNTIME_FILES))
        self.assertNotIn('ci.py',value['files']);self.assertNotIn('audit_control_frontier.mjs',value['files'])
        self.assertNotIn('software_probe.mjs',value['files']);self.assertEqual(len(value['repoDependencies']),14)
        self.assertEqual(value['sourceCommit'],self.env['GITHUB_SHA']);self.assertEqual(value['parentImage'],ci.BASE)
        closure=ci.extensions();self.assertEqual(len(closure),14+len(ci.RUNTIME_FILES)+len(ci.TEST_FILES)+1)
        self.assertIn('repo/'+ci.NAMESPACE+'/QUALITY_FILES.json',closure)

    def test_focused_tests_and_actual_quality_probe_gate_staging(self):
        for updates in [{'focusedTests':{'status':'FAIL'}},{'softwareProbeBeforeBuild':{'exitCode':1}}]:
            self.seed(**updates)
            with self.assertRaisesRegex(RuntimeError,'FOCUSED_AND_ACTUAL_SOFTWARE_AB_PASS_REQUIRED'):ci.stage()
        self.process.assert_not_called()

    def test_context_is_explicit_and_unexpected_file_prevents_build(self):
        self.seed();ci.stage();root=Path(ci.state()['context']);self.assertFalse(root.is_relative_to(ci.REPO))
        self.assertEqual(set(path.name for path in root.iterdir()),{'quality','Dockerfile'})
        (root/'unexpected').write_text('unlisted')
        with self.assertRaisesRegex(RuntimeError,'EXPLICIT_BUILD_CONTEXT_REQUIRED'):ci.build()
        self.process.assert_not_called()

    def test_successful_software_probe_must_not_claim_nvidia_and_must_change_pixels(self):
        self.seed();good={'schema':'QUALITY_ACTUAL_SOFTWARE_PROBE_V1','softwareWebGLDrawExecuted':True,'status':'PASS','testOnly':True,'physicalNvidiaExecuted':False,'gpuRenderingVerified':False,
            'actualShaderCompile':True,'actualQualityABPixelsDiffer':True,'cameraAndGeometryEqual':True,'originalSourcesUnchanged':True}
        for update in [{'physicalNvidiaExecuted':True},{'gpuRenderingVerified':True},{'actualQualityABPixelsDiffer':False},
                       {'testOnly':False},{'actualShaderCompile':False}]:
            self.process.return_value=SimpleNamespace(returncode=0,stdout=json.dumps({**good,**update}),stderr='')
            with self.subTest(update=update),self.assertRaisesRegex(RuntimeError,'ACTUAL_QUALITY_SOFTWARE_AB_PROBE_REQUIRED'):
                ci.software_probe('synthetic',phase='synthetic')
        self.process.return_value=SimpleNamespace(returncode=0,stdout=json.dumps(good),stderr='')
        with patch.object(ci,'collect_pngs',return_value=[]),patch.object(ci,'validate_png_report'):
            self.assertEqual(ci.software_probe('synthetic',phase='synthetic'),good)
        args=self.process.call_args.args[0];self.assertIn('--network=none',args);self.assertNotIn('--gpus',args)

    def test_provenance_and_inherited_entrypoint_are_unchanged(self):
        self.command.side_effect=None;self.command.return_value=json.dumps([self.facts()]);ci.inspect_image('synthetic')
        for key in self.facts()['Config']['Labels']:
            bad=self.facts();bad['Config']['Labels'][key]='changed';self.command.return_value=json.dumps([bad])
            with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'PROVENANCE'):ci.inspect_image('synthetic')
        bad=self.facts();bad['Config']['Entrypoint']=['python3','autostart.py'];self.command.return_value=json.dumps([bad])
        with self.assertRaisesRegex(RuntimeError,'ENTRYPOINT'):ci.inspect_image('synthetic')

    def test_registry_publish_requires_zero_secrets(self):
        for updates in [{'verification':'FAIL'},{'secretScan':{'status':'PASS','findings':1}}]:
            self.seed(**updates)
            with self.assertRaises(RuntimeError):ci.publish()
        self.base.login.assert_not_called();self.registry.check_tag.assert_not_called()

    def test_tag_recheck_never_overwrites_and_only_own_auth_is_cleaned(self):
        self.seed();own=self.root/'own-auth';own.mkdir();(own/'config.json').write_text('synthetic')
        previous=self.root/'old-auth';previous.mkdir();(previous/'config.json').write_text('preserved')
        self.base.login.return_value=(own,{})
        self.registry.check_tag.side_effect=[{'status':'TAG_UNUSED'},RuntimeError('TAG_ALREADY_EXISTS')]
        with self.assertRaisesRegex(RuntimeError,'TAG_ALREADY_EXISTS'):ci.publish()
        self.assertFalse(own.exists());self.assertEqual((previous/'config.json').read_text(),'preserved');self.command.assert_not_called()

    def test_independent_pull_requires_union_and_profile_hashes(self):
        self.seed();own=self.root/'auth';own.mkdir();self.base.login.return_value=(own,{})
        self.command.side_effect=None
        with patch.object(ci.controls,'inspect_image',return_value=self.facts()),patch.object(ci.controls,'image_hashes',side_effect=RuntimeError('HASH_MISMATCH')):
            with self.assertRaisesRegex(RuntimeError,'HASH_MISMATCH'):ci.pull()
        self.assertIs(ci.state()['pullVerified'],False)
        self.base.check_image.assert_called_once_with(ci.IMAGE+'@'+DIGEST,hashes_only=True)

    def test_image_extension_hash_must_match_actual_source_manifest(self):
        self.command.side_effect=None;self.command.return_value=json.dumps({'status':'PASS','manifestSha256':'0'*64})
        with self.assertRaisesRegex(RuntimeError,'QUALITY_EXTENSION_HASH_MISMATCH'):ci.image_hashes('synthetic')

    def test_docker_preserves_parent_and_separate_profile_without_auto_render(self):
        text=(HERE/'Dockerfile').read_text();self.assertIn('FROM '+ci.BASE,text)
        for bad in ['ENTRYPOINT [','CMD [','HEALTHCHECK --','EXPOSE ','apt-get','npm ','pip ','ARG GH_TOKEN']:
            self.assertNotIn(bad,text)
        self.assertIn('test ! -e /var/lib/world-engine-private/engine/job-quality-v1',text)
        self.assertNotIn('/engine/job-astra-v1',text);self.assertNotIn('COPY repo',text)


class BoundedPngEvidence(unittest.TestCase):
    def setUp(self):
        self.area=tempfile.TemporaryDirectory(prefix='quality-evidence-test-');self.addCleanup(self.area.cleanup)
        self.root=Path(self.area.name);self.raw=png()
        for name in ci.PNG_NAMES:(self.root/name).write_bytes(self.raw)

    def test_exact_eight_software_pngs_have_dimensions_hashes_and_bounded_size(self):
        rows=ci.collect_pngs(self.root);self.assertEqual(len(rows),8)
        self.assertEqual({row['file'] for row in rows},ci.PNG_NAMES)
        self.assertTrue(all(row['width']==1080 and row['height']==1920 and len(row['sha256'])==64 for row in rows))

    def test_saved_png_hashes_bind_exactly_to_actual_browser_report(self):
        rows=ci.collect_pngs(self.root);reported={'files':[{**row,'scope':'CPU_SW_NOT_NVIDIA'} for row in rows]}
        ci.validate_png_report(reported,rows)
        reported['files'][0]['sha256']='0'*64
        with self.assertRaisesRegex(RuntimeError,'HASH_MISMATCH'):ci.validate_png_report(reported,rows)
        with self.assertRaisesRegex(RuntimeError,'BINDING_REQUIRED'):ci.validate_png_report({},rows)

    def test_missing_extra_and_non_png_files_are_rejected(self):
        path=self.root/'unexpected.json';path.write_text('{}')
        with self.assertRaisesRegex(RuntimeError,'EXACT_EIGHT'):ci.collect_pngs(self.root)
        path.unlink();(self.root/'A_075.png').unlink()
        with self.assertRaisesRegex(RuntimeError,'EXACT_EIGHT'):ci.collect_pngs(self.root)

    def test_symlink_hardlink_and_wrong_size_are_rejected(self):
        target=self.root/'A_075.png';target.unlink();target.symlink_to(self.root/'B_075.png')
        with self.assertRaisesRegex(RuntimeError,'UNSAFE'):ci.collect_pngs(self.root)
        target.unlink();os.link(self.root/'B_075.png',target)
        with self.assertRaisesRegex(RuntimeError,'UNSAFE'):ci.collect_pngs(self.root)
        target.unlink();target.write_bytes(png(16,16))
        with self.assertRaisesRegex(RuntimeError,'DIMENSIONS'):ci.collect_pngs(self.root)


class ComposedParentAndQualityInventory(unittest.TestCase):
    """New union-policy fixtures use real parent source bytes, without editing them."""
    def setUp(self):
        import hashlib
        self.area=tempfile.TemporaryDirectory(prefix='quality-union-test-');self.addCleanup(self.area.cleanup)
        self.root=Path(self.area.name)
        path=HERE.parent/'rtx-image-build-v1/image_checks.py'
        spec=importlib.util.spec_from_file_location('_quality_immutable_auditor_fixture',path)
        self.legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.legacy)
        def fixture_owner(path,*,directory=False):
            if path.is_symlink() or (not path.is_dir() if directory else not path.is_file()):
                raise self.legacy.ImageCheckError('STAGED_SOURCE_OWNERSHIP_OR_PERMISSIONS')
        # Workspace fixtures are UID1000; actual image runs retain the original
        # root-owner/read-only check in the unmodified inherited audit helper.
        self.legacy._root_owned_readonly=fixture_owner
        contract=json.dumps({'files':[{} for _ in range(140)]}).encode();(self.root/'source_contract.json').write_bytes(contract)
        self.legacy.SOURCE_CONTRACT_SHA256=hashlib.sha256(contract).hexdigest()
        copied=[]
        for number in range(160):
            relative='original/file_'+str(number)+'.bin';body=('original'+str(number)).encode()
            target=self.root/'repo'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
            copied.append({'repoPath':relative,'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)})
        (self.root/'STAGING_RECEIPT.json').write_text(json.dumps({'files':copied}))
        _,parent=ci.parent_closure();self.extra={}
        for relative,digest in parent.items():
            target=self.root/'repo'/relative;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((ci.REPO/relative).read_bytes());self.extra['repo/'+relative]=digest
        for name in ['quality_material.mjs','QUALITY_FILES.json']:
            relative='repo/'+ci.NAMESPACE+'/'+name;body=('new-fixture-'+name).encode()
            target=self.root/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
            self.extra[relative]=hashlib.sha256(body).hexdigest()

    def test_known_original_parent_astra_and_new_quality_inventory_is_accepted(self):
        report=ci.prior.composed_source_tree(self.root,self.legacy,self.extra)
        self.assertEqual(report['files'],160);self.assertEqual(report['additiveFiles'],16)
        self.assertEqual(report['unexpectedFiles'],0);self.assertEqual(report['composedInventoryFiles'],178)

    def test_unknown_quality_file_is_rejected_inside_known_namespace(self):
        (self.root/'repo'/ci.NAMESPACE/'unlisted.mjs').write_text('unlisted')
        with self.assertRaisesRegex(self.legacy.ImageCheckError,'UNEXPECTED_STAGED_FILE'):
            ci.prior.composed_source_tree(self.root,self.legacy,self.extra)

    def test_parent_astra_bytes_are_verified_in_additive_layer(self):
        relative='repo/'+ci.PRIOR_NAMESPACE+'/astra_runtime.mjs'
        (self.root/relative).write_bytes(b'parent source corruption')
        with self.assertRaisesRegex(self.legacy.ImageCheckError,'PACKAGED_SOURCE_VERIFICATION_FAILED'):
            ci.prior.composed_source_tree(self.root,self.legacy,self.extra)

    def test_original_auditor_bytes_remain_unchanged(self):
        self.assertEqual(ci.sha(HERE.parent/'rtx-image-build-v1/image_checks.py'),
            'c1ca60b64fe752cdc3b95c892718f4f18f25cb1bcc044f8f6269c017f976f51f')


if __name__=='__main__':unittest.main()
