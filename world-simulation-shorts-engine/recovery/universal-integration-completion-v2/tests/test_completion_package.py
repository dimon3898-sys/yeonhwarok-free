"""Packaging-only CPU tests; no Docker build, registry access, or rendering."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('_completion_package_unit',HERE/'ci_package.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
spec=importlib.util.spec_from_file_location('_completion_fixture_unit',HERE/'install_fixtures.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)


class PackageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='completion-package-')
  self.base=Path(self.tmp.name);self.root=self.base/'completion';self.prior=self.base/'prior'
  self.root.mkdir();self.prior.mkdir()
  self.names={'bootstrap.py','studio_entry.py','studio_controller.py','runtime_bridge.py','capture_runtime.mjs','package_manifest.py',
   'install_fixtures.py','PACKAGED_FIXTURES.json'}
  self.manifests()
 def tearDown(self):self.tmp.cleanup()
 def manifests(self):
  for root in [self.root,self.prior]:
   for name in self.names:(root/name).write_text('CPU packaging fixture '+name+'\n')
  old={'schema':'WORLD_ENGINE_UNIVERSAL_INTEGRATION_FILES_V1','baseOperatingImageDigest':package.ci.BASE_DIGEST,
   'files':{name:package.ci.sha(self.prior/name) for name in self.names}}
  (self.prior/'INTEGRATION_FILES.json').write_text(json.dumps(old));(self.prior/'RUNTIME_SOURCE_MANIFEST.json').write_text('{}')
  self.repo=self.base/'repo';relative=package.FIXTURE_PREFIX+'verified-front-data-v4-recovery/VIDEO_PLAN_80S.json'
  fixture=self.repo/relative;fixture.parent.mkdir(parents=True);fixture.write_bytes(b'{"fixture":true}\n')
  fixtures={'schema':'WORLD_ENGINE_PACKAGED_FIXTURES_V1','sourceCommit':package.FIXTURE_COMMIT,'files':[
   {'repoPath':relative,'target':'/opt/rtx-package/repo/'+relative,'sourceCommit':package.FIXTURE_COMMIT,
    'sha256':package.ci.sha(fixture),'bytes':fixture.stat().st_size}]}
  (self.root/'PACKAGED_FIXTURES.json').write_text(json.dumps(fixtures))
  new={'schema':'WORLD_ENGINE_COMPLETION_FILES_V2','baseOperatingImageDigest':package.ci.BASE_DIGEST,
   'previousManifestSHA256':package.ci.sha(self.prior/'INTEGRATION_FILES.json'),
   'files':{name:package.ci.sha(self.root/name) for name in self.names}}
  (self.root/'COMPLETION_FILES.json').write_text(json.dumps(new));(self.root/'Dockerfile').write_text('FROM immutable-fixture\n')
 def context(self):
  with patch.object(package,'location',return_value=self.base):
   return package.payload_context(root=self.root,prior=self.prior,repo_root=self.repo)
 def test_only_explicitly_manifested_source_enters_image_context(self):
  (self.root/'UNMANIFESTED_PRIVATE_NOTE.json').write_text('{"never":"copy"}')
  context=self.context()
  self.assertEqual({p.name for p in (context/'completion').iterdir()},self.names|{'COMPLETION_FILES.json'})
  self.assertEqual({p.name for p in (context/'integration').iterdir()},self.names|{'INTEGRATION_FILES.json','RUNTIME_SOURCE_MANIFEST.json'})
 def test_changed_source_hash_is_rejected(self):
  (self.root/'bootstrap.py').write_text('unexpected change')
  with self.assertRaisesRegex(RuntimeError,'SOURCE_SHA_MISMATCH'):self.context()
 def test_symlink_source_cannot_enter_payload(self):
  target=self.root/'bootstrap.py';target.unlink();target.symlink_to(self.prior/'bootstrap.py')
  with self.assertRaisesRegex(RuntimeError,'REGULAR_SOURCE_REQUIRED'):self.context()
 def test_path_traversal_manifest_is_rejected(self):
  path=self.root/'COMPLETION_FILES.json';value=json.loads(path.read_text());value['files']['../other.py']='a'*64;path.write_text(json.dumps(value))
  with self.assertRaisesRegex(RuntimeError,'PACKAGE_PATH_INVALID'):self.context()
 def test_prior_manifest_binding_is_immutable(self):
  path=self.root/'COMPLETION_FILES.json';value=json.loads(path.read_text());value['previousManifestSHA256']='0'*64;path.write_text(json.dumps(value))
  with self.assertRaisesRegex(RuntimeError,'PRIOR_MANIFEST_BINDING_CHANGED'):self.context()
 def test_immutable_base_must_match_both_manifests(self):
  path=self.root/'COMPLETION_FILES.json';value=json.loads(path.read_text());value['baseOperatingImageDigest']='sha256:'+'0'*64;path.write_text(json.dumps(value))
  with self.assertRaisesRegex(RuntimeError,'IMMUTABLE_BASE_CHANGED'):self.context()
 def test_free_public_runner_is_required_before_build(self):
  with patch.dict(os.environ,{'GITHUB_ACTIONS':'false'},clear=False):
   with self.assertRaisesRegex(RuntimeError,'FREE_PUBLIC_STANDARD_RUNNER_REQUIRED'):package.ci.require_free_runner()
 def test_tag_is_distinct_and_not_a_legacy_tag(self):
  self.assertIsNotNone(package.ci.TAG.fullmatch('completion-v2-0123456789-12345-1'))
  self.assertIsNone(package.ci.TAG.fullmatch('studio-proxy-v1-4589328-12345-1'))
  self.assertIsNone(package.ci.TAG.fullmatch('latest'))
 def test_container_is_cpu_only_and_network_isolated(self):
  command=package.container('immutable-fixture')
  self.assertIn('--network=none',command);self.assertIn('--restart=no',command)
  self.assertNotIn('--gpus',command);self.assertNotIn('--privileged',command)
  self.assertEqual(command[-3:],['--entrypoint=/usr/bin/python3','immutable-fixture','-B'])
 def test_actual_dockerfile_and_workflow_preserve_immutable_parent(self):
  docker=(HERE/'Dockerfile').read_text()
  self.assertIn('FROM '+package.ci.BASE,docker)
  self.assertIn('test ! -e '+package.PRIOR_DEST,docker)
  self.assertIn(package.ci.DEST+'/bootstrap.py',docker)
  self.assertNotIn('apt-get',docker);self.assertNotIn('pip install',docker)
  workflow=(package.ci.REPO/package.ci.WORKFLOW).read_text()
  self.assertIn('workflow_dispatch:',workflow)
  self.assertIn('branches: [development/universal-integration-completion-20261019]',workflow)
  self.assertNotIn('branches: [main]',workflow)
  self.assertNotIn('universal-integration-completion-v2/runs/**',workflow)
  self.assertIn('runs-on: ubuntu-24.04',workflow)
  self.assertNotIn('self-hosted',workflow);self.assertNotIn('gcube workload',workflow)
 def test_independent_pull_proof_requires_verified_image_and_sources(self):
  commit='a'*40;digest='sha256:'+'b'*64
  state={'pullVerified':True,'imageDigest':digest,'imageHashes':{'status':'PASS'},'imageConfiguration':{'status':'PASS'}}
  saved=[]
  with patch.object(package.ci,'pull'),patch.object(package.ci,'state',return_value=state),patch.object(package.ci,'save',side_effect=saved.append),\
   patch.object(package.ci,'sha',return_value='c'*64),patch.dict(os.environ,{'GITHUB_SHA':commit}):
   package.pull()
  proof=saved[-1]['imageProof']
  self.assertEqual(proof,{'schema':'WORLD_ENGINE_COMPLETION_IMAGE_PROOF_V1','imageDigest':digest,
   'sourceManifestSHA256':'c'*64,'sourceCommit':commit,'independentPullVerified':True,
   'sourceHashesVerified':True,'baseDigest':package.ci.BASE_DIGEST,'result':'PASS'})
 def test_failed_pull_cannot_issue_proof(self):
  with patch.object(package.ci,'pull'),patch.object(package.ci,'state',return_value={'pullVerified':False}):
   with self.assertRaisesRegex(RuntimeError,'INDEPENDENT_PULL_PROOF_REQUIRED'):package.pull()


class FixtureInstallTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='completion-fixture-install-')
  self.base=Path(self.tmp.name);self.payload=self.base/'payload';self.payload.mkdir();self.target=self.base/'target';self.target.mkdir()
  self.relative=package.FIXTURE_PREFIX+'verified-front-data-v4-recovery/VIDEO_PLAN_80S.json'
  self.source=self.payload/'repo'/self.relative;self.source.parent.mkdir(parents=True);self.raw=b'{"originalFixture":true}\n';self.source.write_bytes(self.raw)
  self.manifest=self.base/'PACKAGED_FIXTURES.json'
  self.value={'schema':'WORLD_ENGINE_PACKAGED_FIXTURES_V1','sourceCommit':package.FIXTURE_COMMIT,'files':[
   {'repoPath':self.relative,'target':'/opt/rtx-package/repo/'+self.relative,'sha256':hashlib.sha256(self.raw).hexdigest(),
    'sourceCommit':package.FIXTURE_COMMIT,'bytes':len(self.raw)}]}
  self.write_manifest()
 def tearDown(self):self.tmp.cleanup()
 def write_manifest(self):
  raw=json.dumps(self.value).encode();self.manifest.write_bytes(raw);(self.payload/'PACKAGED_FIXTURES.json').write_bytes(raw)
 def install(self):return installer.install(self.payload,target_root=self.target,manifest_file=self.manifest)
 def test_absent_file_installed_once_and_then_identical_file_is_untouched(self):
  proof=self.install();file=self.target/self.relative;self.assertEqual(file.read_bytes(),self.raw)
  self.assertEqual(proof['installedAbsentFiles'],1);self.assertEqual(stat.S_IMODE(file.stat().st_mode),0o444)
  file.chmod(0o600);before=file.stat();proof=self.install();after=file.stat()
  self.assertEqual(proof['installedAbsentFiles'],0);self.assertEqual(proof['existingIdenticalPreserved'],1)
  self.assertEqual((before.st_ino,before.st_mode,before.st_uid,before.st_gid,before.st_mtime_ns),
   (after.st_ino,after.st_mode,after.st_uid,after.st_gid,after.st_mtime_ns))
 def test_conflicting_existing_file_is_never_overwritten(self):
  file=self.target/self.relative;file.parent.mkdir(parents=True);file.write_bytes(b'KEEP EXISTING');before=file.stat()
  with self.assertRaisesRegex(RuntimeError,'EXISTING_CONFLICT'):self.install()
  self.assertEqual(file.read_bytes(),b'KEEP EXISTING');self.assertEqual(file.stat().st_mtime_ns,before.st_mtime_ns)
 def test_wrong_payload_hash_is_rejected_before_target_write(self):
  self.source.write_bytes(b'CORRUPTED')
  with self.assertRaisesRegex(RuntimeError,'SOURCE_SHA_MISMATCH'):self.install()
  self.assertEqual(list(self.target.iterdir()),[])
 def test_final_target_symlink_is_rejected(self):
  file=self.target/self.relative;file.parent.mkdir(parents=True);external=self.base/'external';external.write_bytes(b'KEEP');file.symlink_to(external)
  with self.assertRaises((OSError,RuntimeError)):self.install()
  self.assertEqual(external.read_bytes(),b'KEEP')
 def test_target_parent_symlink_is_rejected(self):
  external=self.base/'external';external.mkdir();(self.target/'world-simulation-shorts-engine').symlink_to(external,target_is_directory=True)
  with self.assertRaises((OSError,RuntimeError)):self.install()
  self.assertEqual(list(external.iterdir()),[])
 def test_source_symlink_is_rejected(self):
  external=self.base/'source';external.write_bytes(self.raw);self.source.unlink();self.source.symlink_to(external)
  with self.assertRaises((OSError,RuntimeError)):self.install()
  self.assertEqual(list(self.target.iterdir()),[])
 def test_unsafe_path_or_different_target_cannot_escape_scope(self):
  self.value['files'][0]['repoPath']='../escape.json';self.write_manifest()
  with self.assertRaisesRegex(RuntimeError,'PATH_UNSAFE'):self.install()
  self.assertFalse((self.base/'escape.json').exists())
 def test_fixed_saved_source_commit_is_required(self):
  self.value['files'][0]['sourceCommit']='0'*40;self.write_manifest()
  with self.assertRaisesRegex(RuntimeError,'RECORD_INVALID'):self.install()
  self.assertEqual(list(self.target.iterdir()),[])
 def test_later_conflict_is_detected_before_any_absent_file_is_installed(self):
  other=package.FIXTURE_PREFIX+'verified-front-data-v4-recovery/FRONT_PROFILE.json'
  source=self.payload/'repo'/other;source.write_bytes(self.raw)
  self.value['files'].append({'repoPath':other,'target':'/opt/rtx-package/repo/'+other,
   'sha256':hashlib.sha256(self.raw).hexdigest(),'sourceCommit':package.FIXTURE_COMMIT,'bytes':len(self.raw)})
  existing=self.target/other;existing.parent.mkdir(parents=True);existing.write_bytes(b'KEEP LATER FILE');self.write_manifest()
  with self.assertRaisesRegex(RuntimeError,'EXISTING_CONFLICT'):self.install()
  self.assertFalse((self.target/self.relative).exists());self.assertEqual(existing.read_bytes(),b'KEEP LATER FILE')
 def test_container_source_failure_keeps_bounded_first_error(self):
  saved=[]
  failed=SimpleNamespace(returncode=7,stdout='source probe failed',stderr='confirmed CPU first error')
  with patch.object(package.ci,'run',return_value=failed),patch.object(package.ci,'state',return_value={}),\
   patch.object(package.ci,'save',side_effect=saved.append):
   with self.assertRaisesRegex(RuntimeError,'CONTAINER_SOURCE_VERIFICATION_FAILED'):package.image_hashes('immutable-fixture')
  self.assertEqual(saved[-1]['sourceContainerFailure']['exitCode'],7)
  self.assertIn('confirmed CPU first error',saved[-1]['sourceContainerFailure']['stderr'])
  self.assertFalse(saved[-1]['sourceContainerFailure']['gpuExecuted'])


if __name__=='__main__':unittest.main()
