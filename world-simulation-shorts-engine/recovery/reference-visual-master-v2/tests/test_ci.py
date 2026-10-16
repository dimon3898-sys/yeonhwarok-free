"""New V2 CI safety contract; commands/registry calls are explicitly mocked."""
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
spec=importlib.util.spec_from_file_location('reference_ci_tested',HERE/'ci.py')
ci=importlib.util.module_from_spec(spec);spec.loader.exec_module(ci)
TAG='reference-v2-233bca7-12345-1'
DIGEST='sha256:'+'a'*64
CONFIG='sha256:'+'b'*64


def png(width=1080,height=1920):
    def chunk(name,data):return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+b'\x20\x40\x60'*width)*height))+chunk(b'IEND',b'')


class ReferenceCISafety(unittest.TestCase):
    def setUp(self):
        self.area=tempfile.TemporaryDirectory(prefix='ref2-ci-test-');self.addCleanup(self.area.cleanup);self.root=Path(self.area.name)
        self.env={'RESULT_CI_STATE':str(self.root/'state.json'),'RUNNER_TEMP':str(self.root),
            'RUNNER_ENVIRONMENT':'github-hosted','GITHUB_REPOSITORY':'dimon3898-sys/yeonhwarok-free','RESULT_REPOSITORY_PRIVATE':'false',
            'RESULT_RUNNER_LABEL':'ubuntu-24.04','RESULT_PHASE':'build','GITHUB_REF':'refs/heads/'+ci.BRANCH,
            'GITHUB_SHA':'c'*40,'GITHUB_RUN_ID':'12345','GITHUB_RUN_ATTEMPT':'1','RESULT_PUBLISHED_TAG':TAG,
            'RESULT_PUBLISHED_DIGEST':DIGEST,'GITHUB_OUTPUT':str(self.root/'outputs')}
        self.addCleanup(patch.stopall);patch.dict(os.environ,self.env,clear=True).start()
        self.command=Mock(side_effect=AssertionError('unexpected command'));patch.object(ci,'run',self.command).start();patch.object(ci.controls,'run',self.command).start()
        self.process=patch.object(ci.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='',stderr='')).start()
        self.base=SimpleNamespace(require_space=Mock(return_value={'freeBytes':22*1024**3}),check_image=Mock(return_value={'status':'PASS'}),login=Mock())
        patch.object(ci,'helpers',return_value=self.base).start();patch.object(ci.controls,'helpers',return_value=self.base).start()
        self.registry=Mock();self.registry.check_tag.return_value={'status':'TAG_UNUSED'};self.registry.inspect_digest.return_value={'digest':DIGEST,'configDigest':CONFIG}
        module=ModuleType('registry_guard');module.RegistryGuard=lambda:self.registry;module.validate_tag=lambda value:value;module.validate_digest=lambda value:value
        patch.dict(sys.modules,{'registry_guard':module}).start()

    def seed(self,**changes):
        value=ci.state();value.update(tag=TAG,image=ci.IMAGE+':'+TAG,configDigest=CONFIG,
            focusedTests={'status':'PASS'},softwareProbeBeforeBuild={'exitCode':0},verification='PASS',secretScan={'status':'PASS','findings':0})
        value.update(changes);ci.save(value);return value

    def facts(self):
        return {'Id':CONFIG,'Size':1,'Os':'linux','Architecture':'amd64','Config':{
            'Entrypoint':['/usr/bin/tini','-g','--','/usr/bin/python3','/opt/world-engine-storage-fix/launch.py'],'Env':['PATH=/usr/bin'],
            'Labels':{'org.opencontainers.image.revision':'2f9158ba2df2a9f58362fb0b17118b8dc19f705a',
              'world-engine.visual-quality.source-revision':'17393dd6a017a06de542a1484686cd8f8f598e60',
              'world-engine.reference-v2.source-revision':self.env['GITHUB_SHA'],'world-engine.reference-v2.parent-digest':ci.PARENT_DIGEST}}}

    def test_free_public_runner_exact_branch_and_no_paid_runner(self):
        for key,value in [('RUNNER_ENVIRONMENT','self-hosted'),('RESULT_REPOSITORY_PRIVATE','true'),('RESULT_RUNNER_LABEL','larger-runner'),('GITHUB_REF','refs/heads/main')]:
            with self.subTest(key=key),patch.dict(os.environ,{key:value}),self.assertRaises(RuntimeError):ci.preflight()
        self.command.assert_not_called();self.base.require_space.assert_not_called()

    def test_only_new_namespace_and_workflow_changes_are_permitted(self):
        self.assertEqual(ci.controls.PATCHES,{})
        def git(args,**kwargs):
            if args[1]=='rev-parse':return self.env['GITHUB_SHA']
            if args[1]=='diff':return changed
            return ''
        self.command.side_effect=git
        for changed in [ci.PARENT_NAMESPACE+'/QUALITY_FILES.json','renderer.py']:
            with self.subTest(path=changed),self.assertRaises(RuntimeError):ci.preflight()
        changed=ci.NAMESPACE+'/ref2_profiles.mjs';ci.preflight();self.assertEqual(ci.state()['tag'],TAG)
        self.assertIsNotNone(ci.TAG_PATTERN.fullmatch(TAG));self.assertIsNone(ci.TAG_PATTERN.fullmatch('latest'))

    def test_parent_manifest_is_frozen_not_regenerated_with_current_commit(self):
        with patch.object(ci.parent,'generate_manifest',side_effect=AssertionError('parent regeneration forbidden')):
            manifest,files=ci.parent_closure()
        self.assertEqual(manifest['sourceCommit'],'17393dd6a017a06de542a1484686cd8f8f598e60')
        self.assertEqual(len(files),31);self.assertEqual(files[ci.PARENT_NAMESPACE+'/QUALITY_FILES.json'],ci.PARENT_MANIFEST_SHA)
        self.assertEqual(ci.sha(ci.REPO/ci.PARENT_NAMESPACE/'QUALITY_FILES.json'),ci.PARENT_MANIFEST_SHA)

    def test_parent_byte_change_is_rejected_without_relaxing_old_contract(self):
        original=ci.sha
        with patch.object(ci,'sha',side_effect=lambda path:'0'*64 if Path(path).name=='quality_material.mjs' else original(path)):
            with self.assertRaisesRegex(RuntimeError,'FROZEN_PARENT_SOURCE_CHANGED'):ci.parent_closure()

    def test_manifest_contains_only_declared_runtime_and_test_tools_not_reference_media(self):
        value=ci.generate_manifest()
        self.assertEqual(set(value['files']),set(ci.RUNTIME_FILES));self.assertEqual(set(value['testFiles']),set(ci.TEST_FILES))
        self.assertEqual(value['sourceCommit'],self.env['GITHUB_SHA']);self.assertEqual(len(value['repoDependencies']),31)
        self.assertIn('PROTECTED_BASELINE.json',value['files'])
        self.assertTrue(all(not name.endswith(('.mp4','.png')) and '/' not in name for name in [*value['files'],*value['testFiles']]))
        self.assertEqual(value['parentQualityManifestSha256'],ci.PARENT_MANIFEST_SHA)
        self.assertEqual(value['family'],value['profileId']);self.assertEqual(value['family'],'REFERENCE_VISUAL_MASTER_V2')

    def test_stage_requires_actual_prebuild_software_comparison_and_focused_tests(self):
        for values in [{'focusedTests':{'status':'FAIL'}},{'softwareProbeBeforeBuild':{'exitCode':1}}]:
            self.seed(**values)
            with self.assertRaisesRegex(RuntimeError,'FOCUSED_AND_ACTUAL_REF2_AB_PASS_REQUIRED'):ci.stage()
        self.process.assert_not_called()

    def test_context_unknown_file_and_raw_media_are_never_accepted(self):
        self.seed();ci.stage();folder=Path(ci.state()['context']);self.assertFalse(folder.is_relative_to(ci.REPO))
        self.assertEqual(set(path.name for path in folder.iterdir()),{'reference','Dockerfile'})
        (folder/'reference'/'uploaded-reference.mp4').write_bytes(b'not actual media')
        with self.assertRaisesRegex(RuntimeError,'EXPLICIT_REFERENCE_BUILD_CONTEXT_REQUIRED'):ci.build()
        self.process.assert_not_called()

    def test_software_probe_cannot_claim_nvidia_and_parent_regression_is_mandatory(self):
        self.seed();good={'schema':'REFERENCE_V2_ACTUAL_SOFTWARE_PROBE_V1','status':'PASS','testOnly':True,'physicalNvidiaExecuted':False,'gpuRenderingVerified':False,
            'actualShaderCompile':True,'softwareWebGLDrawExecuted':True,'actualReferenceABPixelsDiffer':True,
            'parentSoftwareBaselineBitExact':True,'originalSourcesUnchanged':True}
        for change in [{'physicalNvidiaExecuted':True},{'testOnly':False},{'parentSoftwareBaselineBitExact':False},{'actualReferenceABPixelsDiffer':False}]:
            self.process.return_value=SimpleNamespace(returncode=0,stdout=json.dumps({**good,**change}),stderr='')
            with self.subTest(change=change),self.assertRaisesRegex(RuntimeError,'ACTUAL_REFERENCE_SOFTWARE_AB_REQUIRED'):ci.software_probe('synthetic',phase='synthetic')
        self.process.return_value=SimpleNamespace(returncode=0,stdout=json.dumps(good),stderr='')
        with patch.object(ci,'collect_pngs',return_value=[]),patch.object(ci,'validate_png_report'):ci.software_probe('synthetic',phase='synthetic')
        args=self.process.call_args.args[0];self.assertIn('--network=none',args);self.assertNotIn('--gpus',args)

    def test_image_parent_labels_and_entrypoint_are_immutable(self):
        self.command.side_effect=None;self.command.return_value=json.dumps([self.facts()]);ci.inspect_image('synthetic')
        for key in self.facts()['Config']['Labels']:
            value=self.facts();value['Config']['Labels'][key]='wrong';self.command.return_value=json.dumps([value])
            with self.subTest(key=key),self.assertRaisesRegex(RuntimeError,'PROVENANCE'):ci.inspect_image('synthetic')

    def test_push_is_forbidden_without_verification_and_secret_scan(self):
        for values in [{'verification':'FAIL'},{'secretScan':{'status':'PASS','findings':1}}]:
            self.seed(**values)
            with self.assertRaises(RuntimeError):ci.publish()
        self.base.login.assert_not_called();self.registry.check_tag.assert_not_called()

    def test_second_tag_check_refuses_overwrite_and_preserves_old_auth(self):
        self.seed();own=self.root/'own';own.mkdir();(own/'config.json').write_text('synthetic')
        old=self.root/'old';old.mkdir();(old/'config.json').write_text('preserved');self.base.login.return_value=(own,{})
        self.registry.check_tag.side_effect=[{'status':'TAG_UNUSED'},RuntimeError('TAG_ALREADY_EXISTS')]
        with self.assertRaisesRegex(RuntimeError,'TAG_ALREADY_EXISTS'):ci.publish()
        self.assertFalse(own.exists());self.assertEqual((old/'config.json').read_text(),'preserved')

    def test_independent_pull_rejects_any_new_or_parent_hash_mismatch(self):
        self.seed();own=self.root/'auth';own.mkdir();self.base.login.return_value=(own,{});self.command.side_effect=None
        with patch.object(ci.controls,'inspect_image',return_value=self.facts()),patch.object(ci.controls,'image_hashes',side_effect=RuntimeError('HASH_MISMATCH')):
            with self.assertRaisesRegex(RuntimeError,'HASH_MISMATCH'):ci.pull()
        self.assertIs(ci.state()['pullVerified'],False)

    def test_new_docker_does_not_autostart_or_copy_parent_or_reference_media(self):
        text=(HERE/'Dockerfile').read_text();self.assertIn('FROM '+ci.BASE,text)
        for forbidden in ['ENTRYPOINT [','CMD [','HEALTHCHECK --','EXPOSE ','apt-get','COPY repo','ARG GH_TOKEN']:
            self.assertNotIn(forbidden,text)
        self.assertIn('/engine/job-reference-v2-v1',text);self.assertNotIn('COPY quality/',text)


class ReferencePngEvidence(unittest.TestCase):
    def setUp(self):
        self.area=tempfile.TemporaryDirectory(prefix='ref2-png-test-');self.addCleanup(self.area.cleanup);self.root=Path(self.area.name)
        raw=png()
        for name in ci.PNG_NAMES:(self.root/name).write_bytes(raw)

    def test_exact_ten_own_full_resolution_software_png_hashes(self):
        rows=ci.collect_pngs(self.root);self.assertEqual(len(rows),10)
        report={'files':[{**row,'scope':'CPU_SW_NOT_NVIDIA'} for row in rows]};ci.validate_png_report(report,rows)
        report['files'][0]['sha256']='0'*64
        with self.assertRaisesRegex(RuntimeError,'SHA_MISMATCH'):ci.validate_png_report(report,rows)

    def test_extra_source_diagnostic_or_media_is_rejected(self):
        (self.root/'uploaded-reference.mp4').write_bytes(b'fixture')
        with self.assertRaisesRegex(RuntimeError,'EXACT_TEN_REFERENCE'):ci.collect_pngs(self.root)

    def test_old_eight_file_set_is_insufficient_and_symlinks_fail(self):
        (self.root/'F_038.png').unlink()
        with self.assertRaisesRegex(RuntimeError,'EXACT_TEN_REFERENCE'):ci.collect_pngs(self.root)
        (self.root/'F_038.png').symlink_to(self.root/'F_075.png')
        with self.assertRaisesRegex(RuntimeError,'UNSAFE'):ci.collect_pngs(self.root)


class StrictFrozenParentUnion(unittest.TestCase):
    """Real source bytes in a temp inventory; only root ownership uses a fixture seam."""
    def setUp(self):
        import hashlib
        self.area=tempfile.TemporaryDirectory(prefix='ref2-union-test-');self.addCleanup(self.area.cleanup);self.root=Path(self.area.name)
        file=HERE.parent/'rtx-image-build-v1/image_checks.py'
        spec=importlib.util.spec_from_file_location('_ref2_original_audit_fixture',file)
        self.legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.legacy)
        def owner(path,*,directory=False):
            if path.is_symlink() or (not path.is_dir() if directory else not path.is_file()):
                raise self.legacy.ImageCheckError('STAGED_SOURCE_OWNERSHIP_OR_PERMISSIONS')
        self.legacy._root_owned_readonly=owner
        raw=json.dumps({'files':[{} for _ in range(140)]}).encode();(self.root/'source_contract.json').write_bytes(raw)
        self.legacy.SOURCE_CONTRACT_SHA256=hashlib.sha256(raw).hexdigest();records=[]
        for i in range(160):
            relative='original/source_'+str(i)+'.bin';body=('original'+str(i)).encode();target=self.root/'repo'/relative
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
            records.append({'repoPath':relative,'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)})
        (self.root/'STAGING_RECEIPT.json').write_text(json.dumps({'files':records}))
        _,sources=ci.parent_closure();self.extra={}
        for relative,digest in sources.items():
            target=self.root/'repo'/relative;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes((ci.REPO/relative).read_bytes());self.extra['repo/'+relative]=digest
        for name in ['ref2_profiles.mjs','REFERENCE_FILES.json']:
            relative='repo/'+ci.NAMESPACE+'/'+name;body=('new-'+name).encode();target=self.root/relative
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body);self.extra[relative]=hashlib.sha256(body).hexdigest()

    def test_known_frozen_parent_and_new_reference_union_accepted(self):
        value=ci.parent.prior.composed_source_tree(self.root,self.legacy,self.extra)
        self.assertEqual(value['files'],160);self.assertEqual(value['additiveFiles'],33)
        self.assertEqual(value['composedInventoryFiles'],195);self.assertEqual(value['unexpectedFiles'],0)

    def test_unknown_file_inside_reference_namespace_remains_rejected(self):
        (self.root/'repo'/ci.NAMESPACE/'unlisted.mjs').write_text('not whitelisted')
        with self.assertRaisesRegex(self.legacy.ImageCheckError,'UNEXPECTED_STAGED_FILE'):
            ci.parent.prior.composed_source_tree(self.root,self.legacy,self.extra)

    def test_frozen_quality_manifest_bytes_must_match_old_sha(self):
        (self.root/'repo'/ci.PARENT_NAMESPACE/'QUALITY_FILES.json').write_bytes(b'new source commit forbidden')
        with self.assertRaisesRegex(self.legacy.ImageCheckError,'PACKAGED_SOURCE_VERIFICATION_FAILED'):
            ci.parent.prior.composed_source_tree(self.root,self.legacy,self.extra)


if __name__=='__main__':unittest.main()
