"""Actual frozen validator + new real bridge/controller; no GPU/job starts."""
from datetime import datetime,timedelta,timezone
import importlib.util,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('_actual_unified_controller',ROOT/'studio_controller.py')
m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
DIGEST='sha256:8ef393d3ed96db57f4b82b3c092c0393e7c1a2d8cdf01c88d8f56b9d24eba5da'
class RealStudioPathTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='world-integration-real-test-')
  root=Path(self.tmp.name);self.c=m.StudioController(control_root=root/'studio',export_root=root/'exports',image_digest=DIGEST)
  # Synthetic test policy never approves a real GPU: data/image/quality remain blocked.
  policy={'schema':'WORLD_ENGINE_STUDIO_OPERATOR_POLICY_V1','validUntil':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),
   'maxWallSeconds':60,'maxRetries':0,'maxCostAmount':'1','currency':'USD','gpuHourlyRate':'1'}
  with self.c._cache.PrivateTree(self.c.control_root) as tree:tree.write_json('operator_policy.json',policy)
 def tearDown(self):self.tmp.cleanup()
 def input(self,schema='WORLD_ENGINE_STUDIO_PROMPT_V2'):
  return {'prompt':json.dumps({'schema':schema,'preset':'VERIFIED_FRONT_V4_80S','durationSeconds':80}),
   'profile':'V4_ARCHIVAL_80S','durationSeconds':80,'sfx':{'enabled':False}}
 def test_real_normalizer_plan_bridge_and_gate(self):
  original=json.loads((ROOT.parent/'verified-front-data-v4-recovery/VIDEO_PLAN_80S.json').read_bytes())
  normalized=self.c._normal(self.input());self.assertEqual(normalized['videoPlan']['totalFrames'],2400)
  self.assertEqual(normalized['videoPlan']['legacyScenePlan'],original['legacyScenePlan'])
  with patch.object(self.c.backend.parent_backend,'_health',side_effect=AssertionError('Native hardware must not be queried')) as health:
   result=self.c.preflight(self.input());health.assert_not_called()
  self.assertFalse(result['ready']);codes={r.get('code') for r in result['checks']}
  self.assertIn('INTEGRATION_CANDIDATE_NOT_INCLUDED_IN_IMAGE',codes)
  self.assertIn('INTEGRATION_REQUIRED_DATA_BLOCKED',codes)
 def test_real_submission_start_blocked_without_worker(self):
  record=self.c.submit(self.input())
  with self.assertRaises(m.StudioError) as error:self.c.start(record['submissionId'],'real-path-negative-test',consent=True)
  self.assertEqual(error.exception.code,'STUDIO_PREFLIGHT_BLOCKED')
  self.assertEqual(list((self.c.control_root/'jobs').iterdir()),[])
 def test_legacy_input_cannot_bypass_new_long_gate(self):
  result=self.c.preflight(self.input('WORLD_ENGINE_STUDIO_PROMPT_V1'))
  self.assertFalse(result['ready']);self.assertEqual(result['checks'][0]['code'],'INTEGRATION_PROFILE_REQUIRED_BEFORE_80S')
if __name__=='__main__':unittest.main()
