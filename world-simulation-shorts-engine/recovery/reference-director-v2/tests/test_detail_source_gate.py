"""Read-only provenance checks; passing does not make absent detail available."""
import hashlib
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


class PartialDetailInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.input = json.loads((HERE / 'REFERENCE_DIRECTOR_INPUT_V2.json').read_text())
        cls.gate = json.loads((HERE / 'reports/DATA_DETAIL_GATE.json').read_text())
        cls.original = json.loads((HERE.parent / 'reference-director-v1/REFERENCE_DIRECTOR_INPUT.json').read_text())

    def test_partial_input_preserves_prior_source_and_render_geometries(self):
        previous = HERE.parent / 'reference-director-v1/REFERENCE_DIRECTOR_INPUT.json'
        self.assertEqual(hashlib.sha256(previous.read_bytes()).hexdigest(), self.input['priorInputSHA256'])
        self.assertEqual(self.input['sourceBindings'], self.original['sourceBindings'])
        for original in self.original['dataRecords']['geometries']:
            current = next(r for r in self.input['dataRecords']['geometries'] if r['id'] == original['id'])
            self.assertEqual(current['geometry'], original['geometry'])
            self.assertEqual(current['source'], original['source'])

    def test_every_explicit_style_binding_resolves_exact_source_geometry(self):
        selectors = self.input['dataRecords']['contextBoundarySourceSelectors']
        available = {row['geometryId']: row for row in selectors}
        for group in self.input['dataBindings']['contextBoundaryGroups']:
            self.assertEqual(group['selectionStatus'], 'EXPLICIT_AUTHORED_DATA_MAPPING')
            for identity in group['geometryIds']:
                source = available[identity]
                raw = (REPO / source['sourcePath']).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), source['sourceSHA256'])
                feature = json.loads(raw)['features'][source['sourceFeatureIndex']]
                self.assertEqual(feature['properties'][source['sourceProperty']], source['sourcePropertyValue'])
                self.assertEqual(canonical(feature['geometry']), source['canonicalGeometrySHA256'])

    def test_component_framing_does_not_delete_parent_render_parts(self):
        subject = self.input['dataRecords']['framingSubjects'][0]
        parent = next(r for r in self.input['dataRecords']['geometries'] if r['id'] == subject['parentGeometryId'])
        self.assertTrue(subject['fullParentRenderGeometryPreserved'])
        self.assertEqual(subject['geometry']['coordinates'], parent['geometry']['coordinates'][subject['componentIndex']])
        self.assertEqual(canonical(parent['geometry']), subject['source']['parentCanonicalGeometrySHA256'])
        self.assertEqual(canonical(subject['geometry']), subject['source']['canonicalDerivedComponentSHA256'])
        original = next(r for r in self.original['dataRecords']['geometries'] if r['id'] == parent['id'])
        self.assertEqual(len(parent['geometry']['coordinates']), len(original['geometry']['coordinates']))

    def test_missing_detail_and_observed_metric_cannot_enable_render(self):
        self.assertEqual(self.gate['status'], 'DATA_DETAIL_BLOCKED')
        self.assertFalse(self.gate['renderAllowed'])
        self.assertFalse(self.input['gate']['renderAllowed'])
        self.assertFalse(self.input['gate']['cameraCompilationAllowed'])
        for key in ('detailLocationId', 'detailGeometryId', 'detailBoundaryGeometryId'):
            self.assertIsNone(self.input['dataBindings'][key])
        self.assertEqual(self.input['dataBindings']['basemapSourceIds'], [])
        self.assertEqual(self.gate['metric']['truth'], 'OBSERVED_REFERENCE_TEXT_ONLY')
        self.assertFalse(self.gate['metric']['surveyClaimAllowed'])
        self.assertFalse(self.gate['newDetailedAssetsAcquired'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
