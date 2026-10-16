"""Synthetic numerical/provenance tests; none is a historical-front verification."""
from copy import deepcopy
import hashlib
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from front_evidence import FrontEvidenceError, validate_front_candidate
from georeference import fit_reference


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class FrontEvidenceSyntheticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='front-evidence-synthetic-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        raster = Image.new('RGB', (128, 128), (31, 65, 91))
        buffer = io.BytesIO()
        raster.save(buffer, format='PNG')
        self.image = buffer.getvalue()
        self.raster_ref = self.write('SYNTHETIC_MAP.png', self.image, mediaType='image/png')
        coordinates = lambda p: [-10 + p[0] * .01, p[1] * .01]
        def control(identifier, pixel):
            return {'id': identifier, 'pixel': pixel, 'coordinate': coordinates(pixel),
                    'sourceReference': 'SYNTHETIC independent fixture coordinate construction'}
        self.spec = {'mapId': 'SYNTHETIC_MAP', 'mode': 'SYNTHETIC', 'originalSHA256': sha(self.image),
            'raster': {'width': 128, 'height': 128},
            'sourceCRS': {'definition': 'EPSG:4326', 'status': 'KNOWN_FROM_MAP',
                          'sourceReference': 'SYNTHETIC fixture explicitly declares WGS84'},
            'pixelConvention': 'PIXEL_CENTER',
            'sourceScale': {'denominator': 100000, 'sourceReference': 'SYNTHETIC declared fixture scale'},
            'sourceUncertaintyMeters': 25,
            'qualityLimits': {'maxFitResidualMeters': 1, 'maxCheckResidualMeters': 1,
                              'maxCombinedUncertaintyMeters': 30},
            'controls': [control('FIT_' + str(index), list(point)) for index, point in enumerate([(0, 0), (127, 0), (127, 127), (0, 127)])],
            'checkControls': [control('CHECK_' + str(index), list(point)) for index, point in enumerate([(16, 16), (111, 16), (111, 111), (16, 111)])],
            'independentCheckDeclaration': 'SYNTHETIC held-out independently constructed fixture coordinates'}
        self.report = fit_reference(self.root / 'SYNTHETIC_MAP.png', self.spec)
        self.report_ref = self.write_json('SYNTHETIC_GEOREFERENCE.json', self.report)
        self.geojson = self.collection([[[25., 30.], [45., 50.], [65., 70.]]])
        self.geo_ref = self.write_json('SYNTHETIC_DIGITIZATION.geojson', self.geojson)
        self.manifest = {'schema': 'WORLD_ENGINE_FRONT_EVIDENCE_CANDIDATE_V1', 'dataMode': 'SYNTHETIC_TEST',
            'source': {'sourceId': 'SYNTHETIC_SOURCE', 'sourceURL': 'synthetic://fixture/map',
                'publisher': 'SYNTHETIC fixture author', 'documentTitle': 'SYNTHETIC arbitrary nonhistorical map',
                'retrievedAt': '2026-10-16T00:00:00Z', 'original': deepcopy(self.raster_ref),
                'license': {'status': 'SYNTHETIC_TEST', 'basis': 'SYNTHETIC self-created fixture only',
                    'reference': 'SYNTHETIC fixture manifest', 'attribution': 'SYNTHETIC_TEST', 'scope': 'THIS_SYNTHETIC_FIXTURE'}},
            'map': {'mapId': 'SYNTHETIC_MAP', 'mapDate': '2000-01-02',
                'locator': {'pdfPageIndex0': None, 'printedPage': None, 'caption': 'SYNTHETIC nonhistorical front test'},
                'lineMeaning': 'OBSERVED_FRONT_POSITION',
                'classificationEvidence': {'legendExcerpt': 'SYNTHETIC observed front fixture',
                    'legendLocator': 'SYNTHETIC legend at pixel (0,0)', 'interpretationRationale': 'SYNTHETIC test semantics only'},
                'raster': deepcopy(self.raster_ref)},
            'georeferenceReport': deepcopy(self.report_ref), 'digitization': deepcopy(self.geo_ref),
            'eventBindings': [{'eventId': 'SYNTHETIC_EVENT', 'eventDate': '2000-01-02',
                'eventDateEvidenceReference': 'SYNTHETIC declared event date', 'displayMapDate': '2000-01-02',
                'usage': 'SAME_DATE_SNAPSHOT', 'exactEventFrontClaimed': False}],
            'reviewRecord': {'reviewId': 'SYNTHETIC_REVIEW', 'reviewer': 'SYNTHETIC_TEST_REVIEWER',
                'reviewedAt': '2026-10-16T00:00:00Z', 'mapInterpretationNotes': 'SYNTHETIC test only; no real map was reviewed',
                'uncertaintyNotes': 'SYNTHETIC 25m fixture uncertainty, no historical precision claim',
                'decision': 'TECHNICAL_CANDIDATE_ONLY', 'originalDocumentSHA256': sha(self.image),
                'mapRasterSHA256': sha(self.image), 'georeferenceReportSHA256': self.report_ref['sha256'],
                'digitizationSHA256': self.geo_ref['sha256'], 'checkedFeatureIds': ['SYNTHETIC_FRONT'], 'unresolvedIssues': []}}

    def write(self, name, raw, **extra):
        (self.root / name).write_bytes(raw)
        return {'path': name, 'sha256': sha(raw), **extra}

    def write_json(self, name, value):
        return self.write(name, (json.dumps(value, sort_keys=True, allow_nan=False) + '\n').encode())

    def collection(self, pixel_parts):
        parts = [[[-10 + col * .01, row * .01] for col, row in pixels] for pixels in pixel_parts]
        geometry = {'type': 'LineString', 'coordinates': parts[0]} if len(parts) == 1 else {'type': 'MultiLineString', 'coordinates': parts}
        return {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'id': 'SYNTHETIC_FRONT', 'geometry': geometry,
            'properties': {'sourceId': 'SYNTHETIC_SOURCE', 'mapId': 'SYNTHETIC_MAP', 'mapDate': '2000-01-02',
                'lineMeaning': 'OBSERVED_FRONT_POSITION', 'coverage': 'PARTIAL_OBSERVED_FRONT_ONLY',
                'wholeFrontClaimed': False, 'inferredCoordinates': False, 'createsTerritory': False, 'enemyComplementAllowed': False,
                'digitizedParts': [{'partIndex': index, 'sourcePixels': pixels, 'observedSegmentIndices': list(range(len(pixels) - 1)),
                    'sourceRegionReference': 'SYNTHETIC region part ' + str(index), 'sourceLineWidthPixels': 2.}
                    for index, pixels in enumerate(pixel_parts)]}}]}

    def sync_geo(self):
        self.manifest['digitization'] = self.write_json('SYNTHETIC_DIGITIZATION.geojson', self.geojson)
        self.manifest['reviewRecord']['digitizationSHA256'] = self.manifest['digitization']['sha256']

    def assert_rejected(self, code):
        with self.assertRaises(FrontEvidenceError) as raised:
            validate_front_candidate(self.manifest, root=self.root)
        self.assertEqual(raised.exception.code, code)

    def test_technical_candidate_never_authorizes_historical_truth_or_rendering(self):
        result = validate_front_candidate(self.manifest, root=self.root)
        self.assertEqual(result['status'], 'TECHNICAL_CANDIDATE_REVIEW_REQUIRED')
        self.assertEqual(result['runtimeAdmission'], 'NOT_ADMITTED')
        self.assertFalse(result['historicalTruthVerified'])
        self.assertFalse(result['humanIdentityOrCertificationVerified'])
        self.assertFalse(result['runtimeConnected'])
        self.assertFalse(result['gpuExecuted'])
        self.assertEqual(result['geojson']['features'][0]['geometry'], self.geojson['features'][0]['geometry'])

    def test_pdf_document_and_page_raster_are_distinct_bound_originals(self):
        buffer = io.BytesIO()
        Image.new('RGB', (128, 128), (31, 65, 91)).save(buffer, format='PDF')
        pdf = buffer.getvalue()
        self.manifest['source']['original'] = self.write('SYNTHETIC_DOCUMENT.pdf', pdf, mediaType='application/pdf')
        self.manifest['map']['locator'].update(pdfPageIndex0=0, printedPage='SYNTHETIC 1')
        self.manifest['map']['rasterDerivation'] = {'originalDocumentSHA256': sha(pdf),
            'derivedRasterSHA256': sha(self.image), 'pdfPageIndex0': 0, 'tool': 'SYNTHETIC fixture generator',
            'toolVersion': 'SYNTHETIC fixture version 1', 'recipe': 'SYNTHETIC separate PDF and raster fixture; not a performed extraction',
            'sourcePageSelection': 'SYNTHETIC PDF page index 0'}
        self.manifest['reviewRecord']['originalDocumentSHA256'] = sha(pdf)
        result = validate_front_candidate(self.manifest, root=self.root)
        self.assertNotEqual(result['originalDocumentSHA256'], result['mapRasterSHA256'])
        self.assertFalse(result['sourceRasterDerivationReproduced'])
        self.assertEqual(result['runtimeAdmission'], 'NOT_ADMITTED')

    def test_html_403_with_pdf_mime_and_valid_hash_is_not_original_map(self):
        self.manifest['source']['original'] = self.write('BLOCKED.pdf', b'<html><body>403 access denied</body></html>', mediaType='application/pdf')
        self.assert_rejected('HTML_OR_ACCESS_ERROR_NOT_SOURCE_MAP')

    def test_hash_mismatch_is_rejected_before_parsing(self):
        (self.root / 'SYNTHETIC_MAP.png').write_bytes(self.image + b'corrupt')
        self.assert_rejected('SOURCE_SHA256_MISMATCH')

    def test_license_boolean_or_unknown_status_is_not_documented_reuse_basis(self):
        self.manifest['source']['license'] = {'verified': True}
        self.assert_rejected('LICENSE_REUSE_BASIS_REQUIRED')

    def test_unknown_map_meaning_is_not_occupation_front(self):
        self.manifest['map']['lineMeaning'] = 'PLANNED_ATTACK_LINE'
        self.assert_rejected('OBSERVED_FRONT_MEANING_REQUIRED')

    def test_legend_citation_is_required_independent_of_source_domain(self):
        self.manifest['map']['classificationEvidence']['legendExcerpt'] = ''
        self.assert_rejected('CLASSIFICATION_LEGENDEXCERPT_REQUIRED')

    def test_future_map_cannot_be_presented_as_earlier_event_front(self):
        self.manifest['eventBindings'][0]['eventDate'] = '2000-01-01'
        self.assert_rejected('FUTURE_MAP_AS_EVENT_FRONT_FORBIDDEN')

    def test_event_date_and_snapshot_date_are_separate(self):
        self.manifest['eventBindings'][0]['eventDate'] = '2000-01-03'
        self.assert_rejected('EVENT_DATE_NOT_MAP_DATE')
        self.manifest['eventBindings'][0]['usage'] = 'SOURCE_DATED_CONTEXT'
        result = validate_front_candidate(self.manifest, root=self.root)
        self.assertEqual(result['mapDate'], '2000-01-02')
        self.assertEqual(result['eventBindings'][0]['eventDate'], '2000-01-03')

    def test_exact_event_front_claim_is_rejected_even_for_matching_dates(self):
        self.manifest['eventBindings'][0]['exactEventFrontClaimed'] = True
        self.assert_rejected('EXACT_EVENT_FRONT_CLAIM_FORBIDDEN')

    def test_source_date_cannot_be_hidden_by_event_label(self):
        self.manifest['eventBindings'][0]['displayMapDate'] = '2000-01-03'
        self.assert_rejected('SOURCE_MAP_DATE_DISCLOSURE_REQUIRED')

    def test_polygon_cannot_be_admitted_from_open_line_candidate(self):
        self.geojson['features'][0]['geometry'] = {'type': 'Polygon', 'coordinates': [[[0., 0.], [1., 0.], [0., 1.], [0., 0.]]]}
        self.sync_geo()
        self.assert_rejected('OPEN_FRONT_LINE_GEOMETRY_REQUIRED')

    def test_closed_line_does_not_implicitly_create_territory(self):
        self.geojson = self.collection([[[25., 30.], [45., 50.], [25., 30.]]])
        self.sync_geo()
        self.assert_rejected('CLOSED_FRONT_TERRITORY_INFERENCE_FORBIDDEN')

    def test_enemy_complement_and_inferred_coordinates_are_rejected(self):
        for key in ('enemyComplementAllowed', 'inferredCoordinates', 'createsTerritory', 'wholeFrontClaimed'):
            with self.subTest(key=key):
                original = deepcopy(self.geojson)
                self.geojson['features'][0]['properties'][key] = True
                self.sync_geo()
                self.assert_rejected('PARTIAL_OBSERVED_LINE_ONLY_REQUIRED')
                self.geojson = original
        self.sync_geo()

    def test_every_supplied_vertex_is_recomputed_from_source_pixels(self):
        self.geojson['features'][0]['geometry']['coordinates'][1][0] += .001
        self.sync_geo()
        self.assert_rejected('GEOMETRY_NOT_DERIVED_FROM_SOURCE_PIXELS')

    def test_missing_observed_segment_cannot_be_interpolated(self):
        self.geojson['features'][0]['properties']['digitizedParts'][0]['observedSegmentIndices'] = [0]
        self.sync_geo()
        self.assert_rejected('EVERY_SEGMENT_OBSERVATION_REQUIRED')

    def test_vertex_without_source_pixel_is_rejected(self):
        self.geojson['features'][0]['properties']['digitizedParts'][0]['sourcePixels'].pop()
        self.sync_geo()
        self.assert_rejected('ONE_SOURCE_PIXEL_PER_VERTEX_REQUIRED')

    def test_source_pixels_outside_check_control_hull_are_not_extrapolated(self):
        self.geojson = self.collection([[[10., 30.], [45., 50.]]])
        self.sync_geo()
        with self.assertRaises(FrontEvidenceError) as raised:
            validate_front_candidate(self.manifest, root=self.root)
        self.assertIn('EXTRAPOLATION', raised.exception.code)

    def test_multiline_and_long_line_split_preserves_every_edge_without_gap_bridge(self):
        long_part = [[20. + index * .3, 40. + math.sin(index * .03)] for index in range(260)]
        second_part = [[30., 80.], [40., 85.], [50., 90.]]
        self.geojson = self.collection([long_part, second_part])
        self.sync_geo()
        result = validate_front_candidate(self.manifest, root=self.root)
        output = result['geojson']['features']
        self.assertEqual([len(feature['geometry']['coordinates']) for feature in output], [129, 129, 4, 3])
        source_parts = self.geojson['features'][0]['geometry']['coordinates']
        actual_edges = [(feature['properties']['sourcePartIndex'], a, b) for feature in output
                        for a, b in zip(feature['geometry']['coordinates'], feature['geometry']['coordinates'][1:])]
        expected_edges = [(index, a, b) for index, part in enumerate(source_parts) for a, b in zip(part, part[1:])]
        self.assertEqual(actual_edges, expected_edges)
        self.assertFalse(result['unobservedGapsBridged'])
        self.assertTrue(all(feature['properties']['simplificationApplied'] is False for feature in output))

    def test_report_must_bind_raster_not_different_document(self):
        self.report['originalSHA256'] = '1' * 64
        self.manifest['georeferenceReport'] = self.write_json('SYNTHETIC_GEOREFERENCE.json', self.report)
        self.assert_rejected('MAP_GEOREFERENCE_BINDING_MISMATCH')

    def test_synthetic_fit_cannot_be_relabeled_real_source_data(self):
        self.report['mode'] = 'SOURCE_MAP'
        self.manifest['georeferenceReport'] = self.write_json('SYNTHETIC_GEOREFERENCE.json', self.report)
        self.assert_rejected('GEOREFERENCE_DATA_MODE_MISMATCH')

    def test_self_declared_review_boolean_does_not_replace_bound_record(self):
        self.manifest['reviewRecord'] = {'verified': True}
        self.assert_rejected('REVIEW_REVIEWID_REQUIRED')

    def test_review_is_bound_to_actual_geojson_bytes(self):
        self.manifest['reviewRecord']['digitizationSHA256'] = '1' * 64
        self.assert_rejected('REVIEW_EVIDENCE_BINDING_REQUIRED')

    def test_review_scope_cannot_omit_feature(self):
        self.manifest['reviewRecord']['checkedFeatureIds'] = ['SOME_OTHER_SYNTHETIC_FRONT']
        self.assert_rejected('REVIEW_FEATURE_SCOPE_MISMATCH')

    def test_date_line_wrapping_is_rejected_without_changing_shape(self):
        self.geojson['features'][0]['geometry']['coordinates'] = [[179., 1.], [-179., 1.], [-178., 1.]]
        self.sync_geo()
        self.assert_rejected('WRAPPED_FRONT_UNSUPPORTED')

    def test_rehashed_nan_geojson_is_rejected(self):
        raw = b'{"type":"FeatureCollection","features":NaN}'
        self.manifest['digitization'] = self.write('SYNTHETIC_DIGITIZATION.geojson', raw)
        self.assert_rejected('VALID_FINITE_JSON_REQUIRED')

    def test_duplicate_keys_cannot_ambiguously_reinterpret_hashed_evidence(self):
        raw = b'{"type":"FeatureCollection","type":"Polygon","features":[]}'
        self.manifest['digitization'] = self.write('SYNTHETIC_DIGITIZATION.geojson', raw)
        self.assert_rejected('VALID_FINITE_JSON_REQUIRED')

    def test_malformed_review_scope_fails_closed_with_stable_code(self):
        self.manifest['reviewRecord']['checkedFeatureIds'] = [{'verified': True}]
        self.assert_rejected('REVIEW_SCOPE_REQUIRED')

    def test_boolean_segment_indices_are_not_numerical_provenance(self):
        self.geojson['features'][0]['properties']['digitizedParts'][0]['observedSegmentIndices'] = [False, 1]
        self.sync_geo()
        self.assert_rejected('EVERY_SEGMENT_OBSERVATION_REQUIRED')

    def test_symlinked_source_is_rejected(self):
        (self.root / 'map-alias.png').symlink_to(self.root / 'SYNTHETIC_MAP.png')
        self.manifest['source']['original']['path'] = 'map-alias.png'
        self.assert_rejected('SOURCE_SYMLINK_FORBIDDEN')

    def test_path_traversal_is_rejected(self):
        self.manifest['source']['original']['path'] = '../SYNTHETIC_MAP.png'
        self.assert_rejected('CANONICAL_RELATIVE_PATH_REQUIRED')


if __name__ == '__main__':
    unittest.main()
