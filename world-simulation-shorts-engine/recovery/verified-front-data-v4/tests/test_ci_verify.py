"""Focused V4 free-CI and isolation contract checks; no Docker/GPU execution."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('front_v4_ci_contract', Path(__file__).parents[1] / 'ci_verify.py')
ci = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ci)


class FreeCpuWorkflowTests(unittest.TestCase):
    def test_only_new_additions_are_allowed(self):
        for name in (ci.NAMESPACE + '/source_acquisition.py', ci.WORKFLOW):
            self.assertEqual(ci.validate_changes('A\t' + name + '\n')['preexistingFilesChanged'], 0)
        for row in ('M\t' + ci.NAMESPACE + '/source_acquisition.py',
                    'A\tworld-simulation-shorts-engine/recovery/universal-production-v3/new.py',
                    'M\told-renderer.mjs', 'D\told-final.json',
                    'R100\told-path\t' + ci.NAMESPACE + '/moved.py'):
            with self.subTest(row=row), self.assertRaisesRegex(RuntimeError, 'PREEXISTING_SOURCE'):
                ci.validate_changes(row)

    def test_isolation_and_pinned_parent_image(self):
        command = ci.container_command(Path('/tmp/synthetic-v4-input'))
        for value in ('--network=none', '--read-only', '--user=1000:1000', '--cap-drop=ALL',
                      '--security-opt=no-new-privileges', '--restart=no', ci.PARENT_IMAGE):
            self.assertIn(value, command)
        self.assertTrue(any(value.endswith('target=/front-v4,readonly') for value in command))
        self.assertEqual(command[-1], 'container-test')
        self.assertNotIn('--gpus', command)
        self.assertNotIn('--privileged', command)
        self.assertEqual(command.count('--mount'), 1)

    def test_bounded_identifiers_reject_paths_and_shell_syntax(self):
        self.assertEqual(ci.identifier('12345'), '12345')
        for value in ('../123', '0', '1; rm -rf /', '', None, '9' * 21):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                ci.identifier(value)

    def test_new_focused_module_inventory_does_not_name_old_suites(self):
        self.assertEqual(set(ci.REQUIRED_TEST_FILES),
                         {'test_source_acquisition.py', 'test_georeference.py', 'test_front_evidence.py'})
        self.assertEqual(ci.SCANNER_VERSION, '8.24.3')
        self.assertEqual(len(ci.SCANNER_SHA), 64)


class ArtifactReadinessAuditTests(unittest.TestCase):
    """Actual blocked records and pinned plan, plus negative tamper cases."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='front-v4-audit-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'v4'
        self.parent = Path(temporary.name) / 'parent-v3'
        self.root.mkdir()
        for name in ('SOURCE_CATALOG.json', 'EVENT_EVIDENCE_MATRIX.json', *ci.EVIDENCE_FILES):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ci.HERE / name).read_bytes())
        for relative, _ in ci.PARENT_ARTIFACTS.values():
            target = self.parent / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ci.explicit_parent_root() / relative).read_bytes())

    def edit(self, name, callback):
        path = self.root / name
        value = json.loads(path.read_text())
        callback(value)
        path.write_text(json.dumps(value))

    def audit(self):
        return ci.audit_artifacts(evidence_root=self.root, parent_root=self.parent)

    def test_actual_eleven_source_records_and_unchanged_plan_remain_unadmitted(self):
        report = self.audit()
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['sourceRecords'], 11)
        self.assertEqual(report['acquisitionEvidenceReferencesChecked'], 13)
        self.assertEqual(report['newHistoricalFrontCoordinates'], 0)
        self.assertEqual((report['chapters'], report['totalFrames']), (12, 2400))
        self.assertEqual(report['sceneConnection'], 'NOT_CHANGED_NO_NEW_ADMITTED_GEOMETRY')
        self.assertEqual(report['runtimeActualDraw'], 'SKIP_REQUIRED_REAL_SOURCE')
        self.assertFalse(report['historicalFrontVerified'])

    def test_evidence_file_hash_tamper_is_rejected(self):
        path = self.root / 'evidence/INITIAL_ACCESS.json'
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaisesRegex(RuntimeError, 'ACQUISITION_EVIDENCE_SHA_MISMATCH'):
            self.audit()

    def test_evidence_record_index_cannot_point_at_another_source(self):
        self.edit('SOURCE_CATALOG.json', lambda value: value['sources'][0]['evidenceReferences'][0].update(recordIndex0=1))
        with self.assertRaisesRegex(RuntimeError, 'ACQUISITION_EVIDENCE_URL_MISMATCH'):
            self.audit()

    def test_error_body_hash_cannot_be_used_as_original_hash(self):
        self.edit('SOURCE_CATALOG.json', lambda value: value['sources'][0].update(originalSHA256='a' * 64))
        with self.assertRaisesRegex(RuntimeError, 'SOURCE_DENIAL_CANNOT_CERTIFY_ORIGINAL_MAP'):
            self.audit()

    def test_original_source_count_cannot_be_inflated(self):
        self.edit('SOURCE_CATALOG.json', lambda value: value.update(newOriginalHistoricalSourceBodiesAcquired=1))
        with self.assertRaisesRegex(RuntimeError, 'NO_ORIGINAL_MAP_ADMISSION'):
            self.audit()

    def test_future_or_changed_event_date_is_not_parent_chronology(self):
        self.edit('EVENT_EVIDENCE_MATRIX.json', lambda value: value['rows'][6]['eventDate'].update(value='1950-11-24'))
        with self.assertRaisesRegex(RuntimeError, 'EVENT_DATE_AND_SOURCE_DATE'):
            self.audit()

    def test_chapter_gap_is_not_a_valid_2400_frame_plan(self):
        self.edit('EVENT_EVIDENCE_MATRIX.json', lambda value: value['rows'][3].update(startFrame=601))
        with self.assertRaisesRegex(RuntimeError, 'CHAPTER_FRAME_RANGE'):
            self.audit()

    def test_false_verified_map_flag_is_rejected(self):
        self.edit('EVENT_EVIDENCE_MATRIX.json', lambda value: value['rows'][0].update(eventDateOfficialBodyVerified=True))
        with self.assertRaisesRegex(RuntimeError, 'UNRETRIEVED_FRONT_CANNOT_GAIN_ADMISSION'):
            self.audit()

    def test_parent_plan_and_geometry_hashes_are_fixed(self):
        path = self.parent / 'fixtures/PLAN_80S.json'
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaisesRegex(RuntimeError, 'IMMUTABLE_V3_ARTIFACT_SHA'):
            self.audit()

    def test_supplied_schematic_geometry_binding_cannot_be_swapped(self):
        self.edit('EVENT_EVIDENCE_MATRIX.json', lambda value: value['rows'][0]['existingSchematicContexts'][0]['geometryHashes'][0].update(sha256='a' * 64))
        with self.assertRaisesRegex(RuntimeError, 'EXISTING_GEOMETRY_SOURCE_BINDING'):
            self.audit()

    def test_catalog_cannot_add_arbitrary_evidence_path(self):
        self.edit('SOURCE_CATALOG.json', lambda value: value['sources'][0]['evidenceReferences'][0].update(path='../../sensitive'))
        with self.assertRaisesRegex(RuntimeError, 'EXPLICIT_LOCAL_EVIDENCE_PATH'):
            self.audit()

    def test_snapshot_date_disclosure_cannot_be_disabled(self):
        self.edit('EVENT_EVIDENCE_MATRIX.json', lambda value: value['rows'][0]['videoUse'].update(sourceSnapshotDateMustRemainVisible=False))
        with self.assertRaisesRegex(RuntimeError, 'EXISTING_SCHEMATIC_DISCLOSURE'):
            self.audit()


if __name__ == '__main__':
    unittest.main()
