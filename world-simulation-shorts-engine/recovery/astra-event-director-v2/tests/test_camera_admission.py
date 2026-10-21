"""Actual retained source descriptors and explicit-purpose admission checks.

These are CPU contract checks, never a source-quality or NVIDIA approval.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('astra_camera_owner', ROOT / 'camera_admission.py')
camera = importlib.util.module_from_spec(spec)
spec.loader.exec_module(camera)


class CameraAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.profile_raw = (ROOT / 'fixtures/CAMERA_REVIEW_PROFILE.json').read_bytes()
        self.profile = json.loads(self.profile_raw)
        self.event = json.loads((ROOT / 'fixtures/HISTORY_EVENT_PROFILE_V2.json').read_bytes())
        self.admission = json.loads((ROOT / 'fixtures/CAMERA_ADMISSION.json').read_bytes())
        self.request = {'sourcePlanSha256': self.profile['sourcePlanSHA256'], 'purpose': 'QUALIFIED_SOURCE_REVIEW'}

    def test_actual_native_sources_preserve_original_resolution_and_accuracy_unknown(self):
        actual = camera.actual_source_descriptors()
        self.assertEqual(actual['nativeMinimumBounds'], self.admission['regionalSourceReview']['minimumBounds'])
        self.assertEqual(len(actual['sources']), 4)
        bmng = next(x for x in actual['sources'] if x['role'] == 'land_surface_texture')
        self.assertEqual(bmng['pixelSpacing'], [0.005, 0.005])
        self.assertEqual(actual['geometry']['positionalErrorMeters'], None)
        self.assertFalse(actual['geometry']['absoluteAccuracyCertified'])

    def test_requested_local_sampling_fails_without_upsampling_or_substitute_bounds(self):
        local = next(x for x in self.admission['requestedCamera']['requests'] if x['chapterId'] == 'chapter-04')
        bmng = next(x for x in local['sourceAssessments'] if x['nativePixelSpacing'] == [0.005, 0.005])
        self.assertEqual(bmng['minimumExtentFromNativeSampling'], [5.4, 9.6])
        self.assertGreater(max(bmng['outputPixelsPerNativeTexel']), 1)
        self.assertFalse(bmng['nativeDensitySufficient'])
        self.assertEqual(local['substituteBounds'], None)
        self.assertFalse(local['admitted'])
        self.assertFalse(self.admission['requestedCamera']['automaticWideningAllowed'])

    def test_real_source_bound_callback_allows_only_separate_review_not_production(self):
        receipt = camera.validate_camera_admission(self.admission, self.request, {'eventDirectorProfileRef': self.event})
        self.assertFalse(receipt['ready'])
        self.assertTrue(receipt['reviewReady'])
        self.assertEqual(receipt['reviewCameraPurpose'], 'REGIONAL_SOURCE_REVIEW')
        self.assertFalse(receipt['localCertificate'])
        self.request['purpose'] = 'PRODUCTION'
        receipt = camera.validate_camera_admission(self.admission, self.request, {'eventDirectorProfileRef': self.event})
        self.assertFalse(receipt['reviewReady'])
        self.assertFalse(receipt['ready'])
        self.assertIsNone(receipt['reviewCameraPurpose'])

    def test_self_certified_local_or_changed_source_plan_is_rejected(self):
        for key, value in [('localCertificate', True), ('originalRegionalFloorPreserved', False)]:
            changed = copy.deepcopy(self.admission)
            changed['regionalSourceReview'][key] = value
            with self.assertRaisesRegex(ValueError, 'SOURCE_OR_POLICY_CHANGED'):
                camera.validate_camera_admission(changed, self.request, {'eventDirectorProfileRef': self.event})
        bad = dict(self.request, sourcePlanSha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'SOURCE_PLAN_MISMATCH'):
            camera.validate_camera_admission(self.admission, bad, {'eventDirectorProfileRef': self.event})
        changed_event = copy.deepcopy(self.event)
        changed_event['subjectId'] = 'SYNTHETIC_FORGED_PROFILE'
        with self.assertRaisesRegex(ValueError, 'EVENT_PROFILE_SOURCE_MISMATCH'):
            camera.validate_camera_admission(self.admission, self.request, {'eventDirectorProfileRef': changed_event})

    def test_geographic_domain_and_coverage_are_explicit_not_unsupported_extrapolation(self):
        source = {'sourceId': 'SYNTHETIC_ONLY', 'bounds': [-80, -50, -60, -20], 'pixelSpacing': [.01, .01]}
        western_south = camera.source_resolution_assessment(source, [-78, -48, -64, -24])
        self.assertTrue(western_south['completeSourceFootprint'])
        self.assertTrue(western_south['strictSamplingReady'])
        outside = camera.source_resolution_assessment(source, [10, -48, 24, -24])
        self.assertFalse(outside['completeSourceFootprint'])
        self.assertFalse(outside['strictSamplingReady'])
        for extent in ([170, -10, -170, 10], [-5, -91, 5, -80], [-181, 0, -170, 10]):
            with self.assertRaisesRegex(ValueError, 'GEOGRAPHIC_BOUNDS_REQUIRED'):
                camera.source_resolution_assessment(source, extent)


if __name__ == '__main__':
    unittest.main()
