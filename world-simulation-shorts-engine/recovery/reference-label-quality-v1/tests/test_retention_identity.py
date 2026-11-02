"""New containerd archive identity semantics; synthetic archives, no image builds."""
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

MODULE=None

def encoded(value):return json.dumps(value,separators=(',',':')).encode()
def digest(raw):return 'sha256:'+hashlib.sha256(raw).hexdigest()

class RetentionIdentityTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  global MODULE
  cls.tmp=tempfile.TemporaryDirectory()
  os.environ.setdefault('RUNNER_TEMP',cls.tmp.name);os.environ.setdefault('GITHUB_RUN_ID','mock-retention-identity')
  path=Path(__file__).resolve().parents[1]/'retain_quality_image.py'
  spec=importlib.util.spec_from_file_location('quality_retention',path);MODULE=importlib.util.module_from_spec(spec);spec.loader.exec_module(MODULE)
 @classmethod
 def tearDownClass(cls):cls.tmp.cleanup()
 def fixture(self,index=False,classic=False,missing_layer=False,wrong_config=False,wrong_root=False,corrupt_layer=False,swapped_layers=False):
  layers=[b'fixture-layer-content']+([b'second-layer-content'] if swapped_layers else [])
  desc=[{'digest':digest(raw),'size':len(raw)} for raw in layers]
  config=encoded({'architecture':'amd64','os':'linux','rootfs':{'type':'layers','diff_ids':[r['digest'] for r in desc]}});cd=digest(config)
  manifest=encoded({'schemaVersion':2,'mediaType':'application/vnd.oci.image.manifest.v1+json','config':{'digest':digest(b'wrong') if wrong_config else cd,'size':len(config)},'layers':desc});md=digest(manifest)
  target=md
  blobs={'blobs/sha256/'+cd[7:]:config,'blobs/sha256/'+md[7:]:manifest}
  if not missing_layer:
   for row,raw in zip(desc,layers,strict=True):blobs['blobs/sha256/'+row['digest'][7:]]=raw
  if corrupt_layer:blobs['blobs/sha256/'+desc[0]['digest'][7:]]=b'X'+layers[0][1:]
  if index:
   ind=encoded({'schemaVersion':2,'manifests':[{'digest':md,'size':len(manifest),'platform':{'os':'linux','architecture':'amd64'}}]});target=digest(ind);blobs['blobs/sha256/'+target[7:]]=ind
  compatible=['blobs/sha256/'+r['digest'][7:] for r in desc]
  if swapped_layers:compatible.reverse()
  blobs['manifest.json']=encoded([{'Config':'blobs/sha256/'+cd[7:],'RepoTags':['test:quality'],'Layers':compatible}])
  blobs['index.json']=encoded({'schemaVersion':2,'manifests':[{'digest':digest(b'wrong-root') if wrong_root else target}]})
  out=io.BytesIO()
  with tarfile.open(fileobj=out,mode='w') as tar:
   for name,raw in blobs.items():
    member=tarfile.TarInfo(name);member.size=len(raw);tar.addfile(member,io.BytesIO(raw))
  out.seek(0)
  return out,cd if classic else target,cd,md
 def check(self,**options):
  out,image_id,cd,md=self.fixture(**options)
  with tarfile.open(fileobj=out) as archive:result=MODULE.archive_identity(archive,image_id)
  return result,cd,md
 def test_single_platform_oci_manifest_id_is_not_config_id(self):
  result,cd,md=self.check();self.assertEqual(result['imageID'],md);self.assertNotEqual(cd,md);self.assertEqual(result['configDigest'],cd)
 def test_one_platform_index_descriptor_identity(self):
  result,cd,md=self.check(index=True);self.assertEqual(result['configDigest'],cd);self.assertEqual(result['imageManifestDigest'],md);self.assertNotEqual(result['archiveRootDigest'],md)
 def test_wrong_config_descriptor_rejected(self):
  with self.assertRaisesRegex(RuntimeError,'ARCHIVED_CONFIG_DESCRIPTOR_IDENTITY'):self.check(wrong_config=True)
 def test_missing_layer_rejected(self):
  with self.assertRaises(KeyError):self.check(missing_layer=True)
 def test_wrong_archive_root_rejected(self):
  with self.assertRaisesRegex(RuntimeError,'ARCHIVE_ROOT_DESCRIPTOR_IDENTITY'):self.check(wrong_root=True)
 def test_legacy_config_identity_compatible(self):
  result,cd,_=self.check(classic=True);self.assertEqual(result['identityMode'],'CLASSIC_CONFIG_ID');self.assertEqual(result['imageID'],cd)


 def test_same_size_layer_corruption_rejected(self):
  with self.assertRaisesRegex(RuntimeError,'ARCHIVE_LAYER_BLOB_IDENTITY'):self.check(corrupt_layer=True)
 def test_swapped_compatible_layers_rejected(self):
  with self.assertRaisesRegex(RuntimeError,'ARCHIVE_COMPATIBLE_LAYER_ORDER'):self.check(swapped_layers=True)
 def test_unknown_archive_identity_is_preserved_then_blocked(self):
  out,image_id,_,_=self.fixture(wrong_root=True)
  with tempfile.TemporaryDirectory() as directory:
   MODULE.ROOT=Path(directory);MODULE.write('RESERVATION_RESULT.json',{'status':'PASS'});MODULE.write('RELEASE.json',{'html_url':'https://example.invalid/reviewed-release'})
   uploaded=[]; original_run=MODULE.subprocess.run
   def run(args,**kwargs):
    if args[:4]==['docker','--host=unix:///var/run/docker.sock','image','save']:
     Path(args[args.index('--output')+1]).write_bytes(out.getvalue());return None
    return original_run(args,**kwargs)
   def upload(release,path):
    uploaded.append(path.name);return {'name':path.name,'size':path.stat().st_size,'digest':'sha256:'+MODULE.sha(path)}
   with patch.dict(os.environ,{'TAG':'test:quality'}),patch.object(MODULE.subprocess,'check_output',return_value=image_id),patch.object(MODULE.subprocess,'run',side_effect=run),patch.object(MODULE,'upload',side_effect=upload):
    with self.assertRaisesRegex(RuntimeError,'ARCHIVE_IDENTITY_FAILED_CANDIDATE_QUARANTINED'):MODULE.archive()
   self.assertIn('candidate-image.tar.gz.part-000',uploaded)
   self.assertIn('RETENTION_RESULT.json',uploaded)
   self.assertEqual(MODULE.read('RETENTION_RESULT.json')['status'],'BLOCKED_ARCHIVE_IDENTITY')

if __name__=='__main__':unittest.main()
