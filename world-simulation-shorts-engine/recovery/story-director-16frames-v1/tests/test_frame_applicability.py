"""Synthetic contract tests; these do not claim a renderer or GPU execution."""
import copy
import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('director_frame_applicability', ROOT / 'tools/build_frame_applicability.py')
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)


class FrameApplicabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='director-applicability-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        png = self.root / 'SYNTHETIC_CONTRACT_ONLY.png'
        Image.new('RGB', (1080, 1920), '#152535').save(png)
        self.row = {'globalFrame': 0, 'directRendererOutput': True, 'raw_rgba_sha256': 'e' * 64,
                    'file': str(png), 'png_sha256': hashlib.sha256(png.read_bytes()).hexdigest(),
                    'diagnostic': {'frame': 0, 'glError': 0, 'universalVideo': {'testOnly': True},
                                   'camera': {'gpu': {'nativeRedrawn': True, 'glError': 0}}}}
        self.report = self.root / 'FRAME_RENDER_REPORT.json'

    def write(self, row=None):
        self.report.write_text(json.dumps({'frames': [self.row if row is None else row]}))

    def test_original_151_and_53_identities_are_preserved(self):
        catalog, old = m.read_inputs()
        self.assertEqual(151, len(old))
        self.assertEqual(53, sum(f['classification'] == 'NOT_WIRED' for f in catalog['features']))
        summary = m.build(self.root / 'does-not-exist.json', self.root / 'review')
        self.assertEqual(2416, summary['featureFrameRows'])
        self.assertEqual(0, summary['featuresWithAtLeastOneSoftwareConsumerObservation'])

    def test_only_exact_hash_matching_direct_frame_is_accepted(self):
        self.write()
        rows, proof, _ = m.verified_rows(self.report)
        self.assertEqual([0], list(rows)); self.assertEqual(1, proof['verifiedFrameCount'])
        changed = copy.deepcopy(self.row); changed['png_sha256'] = '0' * 64
        self.write(changed)
        with self.assertRaisesRegex(ValueError, 'PNG_HASH_OR_SIZE'):
            m.verified_rows(self.report)

    def test_frame_binding_mismatch_is_rejected(self):
        row = copy.deepcopy(self.row); row['diagnostic']['frame'] = 150; self.write(row)
        with self.assertRaisesRegex(ValueError, 'GLOBAL_OR_GL'):
            m.verified_rows(self.report)

    def test_screenshot_without_direct_runtime_attestation_is_rejected(self):
        row = copy.deepcopy(self.row); row['directRendererOutput'] = False; self.write(row)
        with self.assertRaisesRegex(ValueError, 'DIRECT_RENDERER'):
            m.verified_rows(self.report)

    def test_factory_call_does_not_claim_national_or_flow_content(self):
        catalog, old = m.read_inputs(); by_id = {r['id']: r for r in catalog['features']}
        for fid in ('UNITS.NATIONAL_TABLETS', 'FLOW.MOVING_OBJECT', 'TERRITORY.COMPLEMENTARY_SCALAR_CONTROL'):
            state, _, reason = m.classify(by_id[fid], old[fid], self.row)
            self.assertEqual('BLOCKED_MISSING_VERIFIED_INPUT', state)
            self.assertTrue(reason)
        state, _, _ = m.classify(by_id['MAP.NATIVE_WEBGL_FACTORY'], old['MAP.NATIVE_WEBGL_FACTORY'], self.row)
        self.assertEqual('SOFTWARE_CONSUMER_OBSERVED', state)

    def test_upload_role_requires_explicit_selection_and_stays_partial(self):
        catalog, old = m.read_inputs(); by_id = {r['id']: r for r in catalog['features']}
        row = copy.deepcopy(self.row)
        row['diagnostic']['terrain'] = {'astra': {'actualMaterialFactorySelected': True,
            'gpuUploadExecuted': True, 'selectedSourceRoles': ['surfaceTexture']}}
        state, _, _ = m.classify(by_id['ASTRA.SURFACE_TEXTURE'], old['ASTRA.SURFACE_TEXTURE'], row)
        self.assertEqual('SOFTWARE_ROLE_SELECTED_PARTIAL_SUPPORT', state)
        state, _, _ = m.classify(by_id['ASTRA.BATHYMETRY_COLOR'], old['ASTRA.BATHYMETRY_COLOR'], row)
        self.assertEqual('NOT_ACTIVE_OR_NOT_WITNESSED_THIS_FRAME', state)

    def test_state_transition_does_not_claim_continuous_grow(self):
        catalog, old = m.read_inputs(); by_id = {r['id']: r for r in catalog['features']}
        row = copy.deepcopy(self.row); row['diagnostic']['area'] = {'controls': {'activeFeatures': ['STATE_TRANSITION']}}
        state, _, reason = m.classify(by_id['AREA.STATE_TRANSITION'], old['AREA.STATE_TRANSITION'], row)
        self.assertEqual('SOFTWARE_CONSUMER_OBSERVED', state)
        self.assertIn('not coordinate-interpolated', reason)
        self.assertEqual('BLOCKED_MISSING_VERIFIED_INPUT', m.classify(by_id['AREA.GROW'], old['AREA.GROW'], row)[0])


if __name__ == '__main__':
    unittest.main()
