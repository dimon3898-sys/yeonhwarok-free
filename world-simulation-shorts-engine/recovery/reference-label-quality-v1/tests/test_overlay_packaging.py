"""New quality-overlay boundaries only; no Docker, registry, GPU or old suites."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('quality_build_once',HERE/'build_once.py')
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)

class QualityOverlayTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.repo=Path(self.tmp.name)/'repo';self.repo.mkdir()
  self.plan=json.loads((ROOT/build.HERE/'SEALED_OVERLAY.json').read_bytes())
  files={r['path'] for r in self.plan['overlay']} | {self.plan['scene']['path'],build.CAPTURE,build.PROFILE,build.HERE+'SEALED_OVERLAY.json'}
  for path in {**build.BASE_PINS,**build.CAPTURE_BASE_PINS}:files.add(build.HERE+'baseline/'+Path(path).name)
  generated=json.loads((ROOT/build.GENERATED).read_bytes())
  for row in generated['variants']:files.update((row['original'],build.HANDOFF+row['variant']))
  for path in files:
   target=self.repo/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/path,target)
 def write_plan(self):
  (self.repo/build.HERE/'SEALED_OVERLAY.json').write_bytes(build.encoded(self.plan))
 def repin(self,path):
  raw=(self.repo/path).read_bytes()
  next(r for r in self.plan['overlay'] if r['path']==path).update(bytes=len(raw),sha256=build.sha(raw));self.write_plan()
 def prepare(self):return build.prepare(self.repo,Path(self.tmp.name)/'context')
 def test_overlay_only_and_preserved_startup(self):
  result=self.prepare();docker=(Path(self.tmp.name)/'context/Dockerfile').read_text()
  self.assertEqual(docker.splitlines()[0],'FROM '+build.PARENT)
  self.assertEqual(docker.count('\nCOPY '),len(self.plan['overlay']))
  self.assertNotIn('\nRUN ',docker)
  self.assertEqual(result['runtimeSourceRows'],355+len(self.plan['addedRuntimeSources']))
  self.assertEqual(result['entrypoint'][:7],['/usr/bin/tini','-g','--','/usr/bin/python3','-I','-B',build.IMAGE_ROOT+'/'+build.BOOTSTRAP])
 def test_source_tamper_blocks_before_context(self):
  path=self.plan['changedSources'][0];file=self.repo/path;file.write_bytes(file.read_bytes()+b'\n')
  with self.assertRaisesRegex(RuntimeError,'SEALED_OVERLAY_BYTES_CHANGED'):self.prepare()
  self.assertFalse((Path(self.tmp.name)/'context').exists())
 def test_inherited_row_removal_cannot_be_resealed(self):
  file=self.repo/build.RUNTIME;runtime=json.loads(file.read_bytes());runtime['files'].pop()
  file.write_bytes(build.encoded(runtime));self.repin(build.RUNTIME)
  with self.assertRaisesRegex(RuntimeError,'SOURCE_COUNT_OR_DUPLICATE'):self.prepare()
 def test_bootstrap_change_beyond_hash_cannot_be_resealed(self):
  file=self.repo/build.BOOTSTRAP;file.write_bytes(file.read_bytes()+b'\n# unexpected logic delta\n');self.repin(build.BOOTSTRAP)
  with self.assertRaisesRegex(RuntimeError,'BOOTSTRAP_ONLY_RUNTIME_PIN_CHANGED'):self.prepare()
 def test_capture_cannot_change_beyond_file_alias(self):
  file=self.repo/build.CAPTURE;file.write_bytes(file.read_bytes()+b'\n');self.repin(build.CAPTURE)
  with self.assertRaisesRegex(RuntimeError,'CAPTURE_EXACT_FILE_ALIAS_ONLY'):self.prepare()

 def test_browser_profile_unchanged(self):
  file=self.repo/build.PROFILE;file.write_bytes(file.read_bytes()+b'\n')
  with self.assertRaisesRegex(RuntimeError,'UNCHANGED_BROWSER_PROFILE_CHANGED'):self.prepare()

if __name__=='__main__':unittest.main()
