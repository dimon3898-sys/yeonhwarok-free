from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('director_control_contract', ROOT / 'control_contract.py')
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)


def raw(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode()


class ActualQualifiedControlTests(unittest.TestCase):
    def setUp(self):
        self.profile_bytes = (ROOT / 'fixtures/HISTORY_EVENT_PROFILE_V2.json').read_bytes()
        self.catalog_bytes = (ROOT / 'fixtures/HISTORY_SOURCE_CATALOG.json').read_bytes()
        self.profile = json.loads(self.profile_bytes)
        self.catalog = json.loads(self.catalog_bytes)

    def build(self, profile=None, catalog=None):
        return owner.build_control_timeline(raw(profile) if profile is not None else self.profile_bytes,
            raw(catalog) if catalog is not None else self.catalog_bytes)

    def test_actual_sources_all_frames_have_unknown_complete_control(self):
        timeline = self.build()
        self.assertFalse(timeline['productionReady'])
        self.assertEqual(timeline['ownerFields'], [])
        self.assertEqual(timeline['transitions'], [])
        self.assertEqual(sum(x['endFrame']-x['startFrame'] for x in timeline['states']), 2400)
        self.assertTrue(all(x['ownerMasks'] == [] and x['sharedFront'] is None and x['truthKind'] == 'unknown'
            for x in timeline['states']))
        self.assertEqual(timeline['eventProfileSHA256'], owner.sha(self.profile_bytes))
        self.assertEqual(timeline['sourceCatalogSHA256'], owner.sha(self.catalog_bytes))

    def test_partial_front_and_schematic_observations_preserved_separately_not_closed(self):
        timeline = self.build()
        actual = self.profile['sourceSchedule']
        for row, source in zip(timeline['sourceObservations'], actual):
            self.assertEqual(row, {key: source.get(key) for key in row})
        self.assertTrue(any(x['truthKind'] == 'observed' for x in timeline['sourceObservations']))
        self.assertTrue(any(x['truthKind'] == 'schematic' for x in timeline['sourceObservations']))
        self.assertTrue(timeline['noPartialFrontClosure'])
        self.assertFalse(timeline['scalarEngineReused'])

    def test_actual_p1_callback_keeps_production_blocked_review_explicit(self):
        timeline = self.build()
        docs = {'eventDirectorProfileRef': self.profile, 'sourceCatalogRef': self.catalog}
        request = {'sourcePlanSha256': self.profile['sourcePlanSHA256'], 'purpose': 'QUALIFIED_SOURCE_REVIEW'}
        receipt = owner.validate_control_timeline(timeline, request, docs)
        self.assertFalse(receipt['ready'])
        self.assertTrue(receipt['reviewReady'])
        self.assertEqual({x['code'] for x in receipt['blockers']}, set(owner.BLOCKERS))
        request['purpose'] = 'PRODUCTION'
        self.assertFalse(owner.validate_control_timeline(timeline, request, docs)['reviewReady'])

    def test_changed_source_bytes_invalidate_timeline(self):
        timeline = self.build()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'fixtures').mkdir()
            (root / 'fixtures/HISTORY_EVENT_PROFILE_V2.json').write_bytes(self.profile_bytes+b' ')
            (root / 'fixtures/HISTORY_SOURCE_CATALOG.json').write_bytes(self.catalog_bytes)
            with patch.object(owner, 'HERE', root), self.assertRaisesRegex(ValueError, 'ACTUAL_SOURCE_BINDING_CHANGED'):
                owner.validate_control_timeline(timeline, {'sourcePlanSha256': self.profile['sourcePlanSHA256']}, {})

    def test_reject_invented_complete_state_and_transition_even_if_marked_approved(self):
        for field in ['fullControlStates', 'controlTransitions']:
            profile = deepcopy(self.profile)
            profile[field] = [{'approved': True, 'truthKind': 'observed', 'sourceId': 'invented'}]
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'FULL_OWNER_SOURCE_ADAPTER_REQUIRED'):
                self.build(profile)

    def test_reject_previous_state_fallback_and_invented_endpoint(self):
        profile = deepcopy(self.profile)
        row = next(x for x in profile['sourceSchedule'] if x['truthKind'] == 'unknown')
        row['stateId'] = 'PREVIOUS_STATE'
        with self.assertRaisesRegex(ValueError, 'UNKNOWN_CANNOT_REUSE_PREVIOUS_STATE'):
            self.build(profile)
        profile = deepcopy(self.profile)
        profile['chapters'][0]['controlEndState'] = 'FAKE_COMPLETE_CONTROL'
        with self.assertRaisesRegex(ValueError, 'UNVERIFIED_ENDPOINT_NOT_NULL'):
            self.build(profile)

    def test_reject_timeline_gap_wrong_catalog_and_missing_evidence(self):
        profile = deepcopy(self.profile)
        profile['sourceSchedule'][1]['startFrame'] += 1
        with self.assertRaisesRegex(ValueError, 'CONTIGUOUS_SOURCE_PARTITION_REQUIRED'):
            self.build(profile)
        catalog = deepcopy(self.catalog)
        catalog['sourcePlanSHA256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'QUALIFIED_PROFILE_CATALOG_REQUIRED'):
            self.build(catalog=catalog)
        catalog = deepcopy(self.catalog)
        catalog['sources'] = {}
        with self.assertRaisesRegex(ValueError, 'SOURCE_REFERENCE_UNAVAILABLE'):
            self.build(catalog=catalog)

    def test_generic_subject_chapter_and_source_ids_no_country_algorithm(self):
        profile = deepcopy(self.profile)
        profile['subjectId'] = 'ARBITRARY_WESTERN_HEMISPHERE_SOURCE_REVIEW'
        mapping = {c['chapterId']: 'arbitrary-'+str(i) for i, c in enumerate(profile['chapters'])}
        for chapter in profile['chapters']:
            chapter['chapterId'] = mapping[chapter['chapterId']]
            chapter['eventId'] = 'GENERIC_EVENT'
        for row in profile['sourceSchedule']:
            row['chapterId'] = mapping[row['chapterId']]
        timeline = self.build(profile)
        self.assertEqual(timeline['states'][0]['chapterId'], 'arbitrary-0')
        self.assertEqual(timeline['states'][0]['eventId'], 'GENERIC_EVENT')
        self.assertFalse(timeline['productionReady'])

    def test_duplicate_or_nonfinite_json_rejected(self):
        with self.assertRaisesRegex(ValueError, 'DUPLICATE_JSON_KEY'):
            owner.build_control_timeline(b'{"schema":1,"schema":2}', self.catalog_bytes)
        with self.assertRaisesRegex(ValueError, 'FINITE_JSON_REQUIRED'):
            owner.build_control_timeline(b'{"schema":NaN}', self.catalog_bytes)


if __name__ == '__main__':
    unittest.main()
