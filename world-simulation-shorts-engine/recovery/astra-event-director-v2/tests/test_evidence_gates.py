import importlib.util
from copy import deepcopy
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('director_evidence_gates', ROOT / 'evidence_gates.py')
gates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gates)


class EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.raw = (ROOT / 'fixtures/HISTORY_EVENT_PROFILE_V2.json').read_bytes()
        self.profile = json.loads(self.raw)
        self.marker, self.audio = gates.build_evidence_manifests(self.raw)
        self.request = {'sourcePlanSha256': self.profile['sourcePlanSHA256'], 'purpose': 'QUALIFIED_SOURCE_REVIEW'}
        self.docs = {'eventDirectorProfileRef': self.profile}

    def test_empty_source_bound_manifests_remain_blocked_not_completed_effects(self):
        self.assertEqual(self.marker['markers'], [])
        self.assertEqual(self.marker['historicalMarkerDrawCount'], 0)
        self.assertEqual(self.audio['enabled'], False)
        self.assertEqual(self.audio['gain'], 0)
        self.assertEqual(self.audio['cues'], [])
        self.assertFalse(self.audio['automaticCueGenerationAllowed'])
        for doc, validator in [(self.marker, gates.validate_marker_evidence), (self.audio, gates.validate_audio_manifest)]:
            receipt = validator(doc, self.request, self.docs)
            self.assertFalse(receipt['ready'])
            self.assertTrue(receipt['reviewReady'])
            self.assertEqual(receipt['activeGraphicsOrCues'], 0)
            self.assertFalse(receipt['nvidiaHardwareVerified'])

    def test_production_cannot_reuse_source_review_permission(self):
        for doc, validator in [(self.marker, gates.validate_marker_evidence), (self.audio, gates.validate_audio_manifest)]:
            request = {**self.request, 'purpose': 'PRODUCTION'}
            receipt = validator(doc, request, self.docs)
            self.assertFalse(receipt['ready'])
            self.assertFalse(receipt['reviewReady'])

    def test_city_context_or_fake_marker_cannot_be_promoted(self):
        for value in [{'position': self.profile['locations'][0]['anchor'], 'role': 'ARMY'}, {'id': 'fake', 'verified': True}]:
            profile = deepcopy(self.profile)
            profile['markerEvidence'] = [value]
            with self.assertRaisesRegex(ValueError, 'EVIDENCE_OWNER_REVIEW_REQUIRED'):
                gates.build_evidence_manifests(json.dumps(profile).encode())
        changed = deepcopy(self.marker)
        changed['markers'] = [{'id': 'fake'}]
        with self.assertRaisesRegex(ValueError, 'ACTUAL_BYTES_OR_SETTINGS_CHANGED'):
            gates.validate_marker_evidence(changed, self.request, self.docs)

    def test_explicit_silence_cannot_be_changed_to_default_sfx(self):
        for change in [{'enabled': True}, {'gain': .5}, {'cues': [{'frame': 600, 'kind': 'click'}]}]:
            doc = {**self.audio, **change}
            with self.assertRaisesRegex(ValueError, 'ACTUAL_BYTES_OR_SETTINGS_CHANGED'):
                gates.validate_audio_manifest(doc, self.request, self.docs)
            profile = deepcopy(self.profile)
            profile['audio'].update(change)
            with self.assertRaisesRegex(ValueError, 'AUDIO_CUE_UNVERIFIED'):
                gates.build_evidence_manifests(json.dumps(profile).encode())

    def test_another_profile_or_source_plan_is_rejected(self):
        changed = deepcopy(self.profile)
        changed['subjectId'] = 'OTHER_SUBJECT'
        with self.assertRaisesRegex(ValueError, 'SOURCE_PROFILE_MISMATCH'):
            gates.validate_audio_manifest(self.audio, self.request, {'eventDirectorProfileRef': changed})
        with self.assertRaisesRegex(ValueError, 'SOURCE_PROFILE_MISMATCH'):
            gates.validate_marker_evidence(self.marker, {**self.request, 'sourcePlanSha256': '0'*64}, self.docs)

    def test_fixture_hashes_are_original_byte_hashes_and_settings_are_exact(self):
        self.assertEqual(self.marker['eventProfileSHA256'], gates.sha(self.raw))
        self.assertEqual(self.audio['eventProfileSHA256'], gates.sha(self.raw))
        self.assertEqual(self.marker['version'], 2)
        self.assertEqual(self.audio['version'], 2)
        self.assertFalse(self.audio['uiMayOverride'])


if __name__ == '__main__':
    unittest.main()
