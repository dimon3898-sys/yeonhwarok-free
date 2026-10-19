"""Real source-plan/closure checks. No GPU admission, jobs or private state."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from datetime import datetime,timedelta,timezone
import tempfile

ROOT=Path(__file__).resolve().parents[1]
def load(name,filename):
 spec=importlib.util.spec_from_file_location(name,ROOT/filename);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
bridge=load('_integration_test_bridge','runtime_bridge.py')
package=load('_integration_test_package','package_manifest.py')

class RuntimeBridgeTests(unittest.TestCase):
 def setUp(self):
  self.plan=json.loads((ROOT.parent/'verified-front-data-v4-recovery/VIDEO_PLAN_80S.json').read_bytes())
  self.sub={'videoPlan':self.plan,'profile':'V4_ARCHIVAL_80S','integration':{'schema':'WORLD_ENGINE_UNIVERSAL_INTEGRATION_V1','profile':'VISUAL_UNIFIED_V1',
   'visualProfile':{'territoryOpacity':.62,'frontCoreWidthPixels':4.8,'frontGlowRadiusPixels':10,'frontGlowGain':.42,'cameraApproachFrames':48}}}
  self.digest=package.BASE_IMAGE
 def test_real_closure_matches_sources(self):
  self.assertEqual(package.verify_sources()['status'],'PASS')
 def test_source_data_image_blocks_are_independent(self):
  before=json.dumps(self.sub,sort_keys=True)
  c=bridge.gate_context(self.sub,image_digest=self.digest)
  self.assertTrue(c['sourceClosureVerified']);self.assertFalse(c['imagePackageIncluded'])
  self.assertEqual(c['durationSeconds'],80);self.assertEqual(len(c['referenceSHA256']),64)
  self.assertEqual(len(c['dataBlockers']),3);self.assertIn('BLOCKED',c['requiredModules'].values())
  self.assertEqual(before,json.dumps(self.sub,sort_keys=True))
 def test_sidecar_identity_changes_with_visuals_without_plan_mutation(self):
  a=bridge.prepare_runtime_request(self.sub,image_digest=self.digest)
  old=a['videoPlanSHA256'];self.sub['integration']['visualProfile']['frontGlowGain']=.6
  b=bridge.prepare_runtime_request(self.sub,image_digest=self.digest)
  self.assertEqual(old,b['videoPlanSHA256']);self.assertNotEqual(a['captureSignature'],b['captureSignature'])
  self.assertFalse(b['oldCacheReuseAllowed'])
 def test_explicit_v2_required(self):
  with self.assertRaisesRegex(RuntimeError,'INTEGRATION_EXPLICIT_SUBMISSION_REQUIRED'):
   bridge.gate_context({'videoPlan':self.plan},image_digest=self.digest)
 def test_no_direct_start_or_recovery_can_launch_old_path(self):
  with self.assertRaisesRegex(RuntimeError,'INTEGRATION_REQUIRED_DATA_BLOCKED'):
   bridge.start_studio_job(self.sub,None,{},'synthetic-test',control_root=ROOT,export_root=ROOT,image_digest=self.digest)
  with self.assertRaisesRegex(RuntimeError,'INTEGRATION_JOB_ID_INVALID'):
   bridge.start_studio_recovery('synthetic',None,'synthetic-request',control_root=ROOT,export_root=ROOT,image_digest=self.digest)
 def test_preflight_is_honest_not_gpu_test(self):
  r=bridge.preflight(self.sub,control_root=ROOT,export_root=ROOT,image_digest=self.digest)
  self.assertFalse(r['renderAllowed']);self.assertFalse(r['gpuRenderingVerified'])
  self.assertEqual(sum(c['status']=='BLOCKED' for c in r['checks']),2)
 def test_existing_parent_policy_is_reused_without_rewrite(self):
  manager=bridge._load('_policy_test_manager','execution_manager.py');rt=manager.runtime()
  with tempfile.TemporaryDirectory(prefix='unified-policy-test-') as directory:
   base=Path(directory)
   policy={'schema':'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_V1','validUntil':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
    'maxWallSeconds':60,'maxRetries':0,'maxCostAmount':'1','currency':'USD','gpuHourlyRate':'1'}
   with rt._cache().PrivateTree(base) as root:
    root.write_json('operator_policy.json',policy)
    with root.child('universal-integration-v1',create=True) as new:control=new.path
   context=bridge.gate_context(self.sub,image_digest=self.digest)
   context.update(imagePackageIncluded=True,dataBlockers=[],requiredModules={'AREA':'READY'},candidateSHA256='a'*64)
   with patch.object(bridge,'gate_context',return_value=context),self.assertRaisesRegex(RuntimeError,'INTEGRATION_FULL_VIDEO_QUALITY_GATE_BLOCKED'):
    bridge._authorize_start(self.sub,control,self.digest)
   with rt._cache().PrivateTree(base) as root:self.assertEqual(root.json('operator_policy.json'),policy)
if __name__=='__main__':unittest.main()
