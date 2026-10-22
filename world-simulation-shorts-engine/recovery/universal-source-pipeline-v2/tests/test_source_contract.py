import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("_test_actual_source_contract",HERE/"source_contract.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
store_spec=importlib.util.spec_from_file_location('_test_source_fixture_store',HERE/'tools/source_fixture_store.py')
store=importlib.util.module_from_spec(store_spec);store_spec.loader.exec_module(store)
ROOT=store.restore()[0]


class SourceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pin=hashlib.sha256((ROOT/'INDEX.json').read_bytes()).hexdigest()
        cls.scene=json.loads((HERE/'fixtures/DEMO_SOURCE_SCENE.json').read_bytes())
        cls.actual=module.normalize_submission(cls.scene,source_root=ROOT,expected_index_sha256=cls.pin)

    def test_actual_sampled_source_pipeline_is_ready_synthetic_only(self):
        p=self.actual['sourcePipeline']
        self.assertTrue(p['ready']);self.assertEqual(p['mode'],'SYNTHETIC_TEST')
        self.assertEqual(p['scope'],'SYNTHETIC_TECHNICAL_DEMO')
        self.assertEqual(len(p['runtimePayload']['frames']),180)
        self.assertFalse(p['gpuVerified']);self.assertFalse(p['userApproved'])

    def test_one_field_owns_each_frame_fill_and_front(self):
        frames=self.actual['sourcePipeline']['runtimePayload']['frames']
        self.assertEqual([f['frame'] for f in frames],list(range(180)))
        for f in frames:
            self.assertTrue(f['completeExplicitDomainPartition'])
            for m in [*f['ownerMasks'],f['unknownMask'],f['contestedMask'],f['sharedFront']]:
                self.assertEqual(m['fieldId'],f['fieldId']);self.assertEqual(m['frame'],f['frame'])
        self.assertNotEqual(frames[0]['ownerMasks'][0]['geometry'],frames[-1]['ownerMasks'][0]['geometry'])

    def test_original_v5_camera_clock_uses_same_native_plan(self):
        p=self.actual['sourcePipeline']['runtimePayload']
        self.assertEqual(p['cameraPlan']['directorVersion'],'CAMERA_DIRECTOR_V5')
        self.assertEqual(p['cameraSchedule'][0]['sourceFrame'],p['cameraSchedule'][-1]['sourceFrame'])
        self.assertEqual(p['nativePlan']['primary'],'COUNTRY_VNM')

    def test_unknown_fields_are_never_silently_ignored(self):
        for key in ['approved','rendererPath','arbitraryCamera','gpu','localAdmission']:
            with self.assertRaisesRegex(ValueError,'SOURCE_SCENE_UNKNOWN_OR_MISSING_FIELDS'):
                module.normalize_submission({**self.scene,key:True},source_root=ROOT,expected_index_sha256=self.pin)

    def test_source_index_hash_is_server_authority(self):
        with self.assertRaisesRegex(ValueError,'SOURCE_SERVER_INDEX_HASH_MISMATCH'):
            module.normalize_submission(self.scene,source_root=ROOT,expected_index_sha256='0'*64)

    def test_actor_ids_dates_frames_and_camera_cannot_replace_bound_data(self):
        for field,value in [('startFrame',600),('control_states',[]),('source_refs',[]),('camera',{}),('geometry',{'crs':'EPSG:3857'})]:
            request={**copy.deepcopy(self.scene),field:value}
            with self.assertRaisesRegex(ValueError,'SOURCE_SCENE_BINDING_MISMATCH'):
                module.normalize_submission(request,source_root=ROOT,expected_index_sha256=self.pin)

    def test_historical_pdf_geometry_is_connected_but_geographic_render_blocked(self):
        value=json.loads((HERE/'fixtures/INCHEON_SOURCE_SCENE_BLOCKED.json').read_bytes())
        p=module.normalize_submission(value,source_root=ROOT,expected_index_sha256=self.pin)['sourcePipeline']
        self.assertFalse(p['ready']);self.assertEqual(p['fullControlAreaStatus'],'BLOCKED')
        self.assertEqual(p['sourceObservations'][0]['positionPaths'],8)
        self.assertEqual(p['sourceObservations'][0]['crs'],'PDF_PAGE_POINTS_TOP_LEFT')
        self.assertIn('SOURCE_GEOGRAPHIC_REGISTRATION_UNVERIFIED',p['blockers'])
        self.assertEqual(p['startFrame'],600)
        self.assertEqual(p['runtimePayload']['frames'],[])


if __name__=='__main__':unittest.main()
