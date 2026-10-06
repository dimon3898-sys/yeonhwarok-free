"""Provenance-only finalization using explicitly synthetic media evidence.

No video is rendered. Codec validation is mocked for fixtures; a negative test
requires its actual failure to block all writes. Existing exporter remains strict.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from deployment.resume_evidence import finalize_resume_evidence
from engine.storage import EngineError, canonical, plan_hash
from tools.deliverable_evidence import EvidenceError, load_completed_version, sha256


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
                     if isinstance(value, (dict, list)) else value)


class ResumeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.version = self.root / 'projects/project_abcdef123456/versions/v001'
        write(self.root / 'mobile-state.json', {'format': 'world-mobile-runtime-v1'})
        self.plan = {'project_id': 'project_abcdef123456', 'version': 'v001', 'duration': 2,
                     'synthetic_test_fixture': True,
                     'scenes': [{'scene_id': 'S001', 'duration': 1}, {'scene_id': 'S002', 'duration': 1}]}
        self.plan['plan_hash'] = plan_hash(self.plan)
        write(self.version / 'scene_plan.json', self.plan)
        write(self.version / 'approval.json', {'user_approval': True, 'plan_hash': self.plan['plan_hash']})
        entries = []
        for scene in self.plan['scenes']:
            sid = scene['scene_id']
            movie = self.version / f'renders/{sid}/scene.mp4'
            audit = movie.with_suffix('.audit.json')
            write(movie, b'SYNTHETIC_MEDIA_NOT_FOOTAGE_' + sid.encode())
            write(audit, [{'frame': i, 'webglError': False, 'textClipped': False} for i in range(30)])
            write(self.version / f'scene_json/{sid}.json', scene)
            entries.append({'scene_id': sid, 'complete': True, 'reused': True,
                            'reuse_reason': 'version_checkpoint', 'movie': str(movie), 'audit': str(audit),
                            'video_sha256': sha256(movie), 'audit_sha256': sha256(audit),
                            'cache_key': hashlib.sha256(sid.encode()).hexdigest(),
                            'scene_json_sha256': hashlib.sha256(canonical(scene)).hexdigest(),
                            'quality': {'output_width': 1080, 'output_height': 1920, 'fps': 30},
                            'renderer_version': 'synthetic', 'current_render_seconds': 0})
        final = self.version / 'final/final.mp4'
        muted = self.version / 'final/final_muted.mp4'
        write(final, b'SYNTHETIC_FINAL_NOT_FOOTAGE')
        write(muted, b'SYNTHETIC_MUTED_NOT_FOOTAGE')
        qc = {'passed': True, 'file': str(final), 'synthetic_test_fixture': True}
        write(self.version / 'qc/qc_report.json', qc)
        write(self.version / 'qc/qc_report.md', b'SYNTHETIC_QC')
        self.result = {'plan_hash': self.plan['plan_hash'], 'renderer_version': 'synthetic', 'scenes': entries,
                       'qc': qc, 'outputs': {'final': str(final), 'muted': str(muted),
                                             'qc_report': str(self.version / 'qc/qc_report.md')},
                       'final_sha256': {'final': sha256(final), 'muted': sha256(muted)}}
        self.manifest = {'plan_hash': self.plan['plan_hash'], 'renderer_version': 'synthetic',
                         'scenes': deepcopy(entries)}
        for entry in self.manifest['scenes']:
            entry['reuse_reason'] = 'scene_hash_asset_renderer_quality_cache'
        self.persist()
        write(self.version / 'renders/checkpoint.json', {'plan_hash': self.plan['plan_hash'], 'complete': True,
                                                        'qc_passed': True, 'completed_scenes': 2, 'total_scenes': 2})
        self.media = patch('deployment.resume_evidence.valid_scene_file', return_value=True)
        self.media.start()
        self.addCleanup(self.media.stop)

    def persist(self):
        write(self.version / 'renders/project_result.json', self.result)
        write(self.version / 'renders/scene_results.json', self.manifest)

    def files(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def finalize(self, **kwargs):
        return finalize_resume_evidence(self.root, self.version, expected_plan_hash=self.plan['plan_hash'], **kwargs)

    def assert_rejected_without_writes(self):
        before = self.files()
        with self.assertRaises((EngineError, EvidenceError, ValueError)):
            self.finalize()
        self.assertEqual(self.files(), before)

    def test_only_reason_change_reconciled_with_exact_backup_and_strict_exporter(self):
        original = (self.version / 'renders/scene_results.json').read_bytes()
        before = self.files()
        with self.assertRaisesRegex(EvidenceError, 'SCENE_RESULT_MANIFEST_MISMATCH'):
            load_completed_version(self.version)
        receipt = self.finalize(result=self.result)
        self.assertTrue(receipt['changed'] and receipt['strict_exporter_evidence_passed'])
        self.assertEqual(Path(receipt['backup']).read_bytes(), original)
        self.assertEqual(receipt['backup_sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual(json.loads(Path(receipt['manifest']).read_text())['scenes'], self.result['scenes'])
        self.assertEqual(len(receipt['changes']), 2)
        self.assertFalse(receipt['render_started'] or receipt['media_or_audits_modified'])
        load_completed_version(self.version)
        after = self.files()
        for path, data in before.items():
            if path != str((self.version / 'renders/scene_results.json').relative_to(self.root)):
                self.assertEqual(after[path], data)
        matched = self.files()
        self.assertFalse(self.finalize()['changed'])
        self.assertEqual(self.files(), matched)

    def test_hash_path_id_quality_or_other_difference_rejected_without_writes(self):
        original = deepcopy(self.manifest)
        mutations = [('video_sha256', '0' * 64), ('audit_sha256', '0' * 64), ('movie', '/outside/file.mp4'),
                     ('scene_id', 'S003'), ('cache_key', '0' * 64), ('current_render_seconds', 1),
                     ('reused', False), ('quality', {'output_width': 720, 'output_height': 1280, 'fps': 30}),
                     ('reuse_reason', 'unverified_reason')]
        for key, value in mutations:
            with self.subTest(field=key):
                self.manifest = deepcopy(original)
                self.manifest['scenes'][0][key] = value
                self.persist()
                self.assert_rejected_without_writes()

    def test_verified_native_completion_changes_only_reuse_provenance(self):
        native = {'complete': True, 'frames': 30, 'synthetic_test_fixture': True}
        self.result['scenes'][0]['native_manifest'] = deepcopy(native)
        self.manifest['scenes'][0] = deepcopy(self.result['scenes'][0])
        self.manifest['scenes'][0]['reused'] = False
        self.manifest['scenes'][0].pop('reuse_reason')
        self.persist()
        original = (self.version / 'renders/scene_results.json').read_bytes()
        before = self.files()
        receipt = self.finalize()
        self.assertEqual(Path(receipt['backup']).read_bytes(), original)
        first_changes = [c for c in receipt['changes'] if c['scene_id'] == 'S001']
        self.assertEqual([c['field'] for c in first_changes], ['reused', 'reuse_reason'])
        self.assertEqual(first_changes[0], {'scene_id': 'S001', 'field': 'reused', 'before': False, 'after': True})
        self.assertIsNone(first_changes[1]['before'])
        for path, value in before.items():
            if path != str((self.version / 'renders/scene_results.json').relative_to(self.root)):
                self.assertEqual(self.files()[path], value)
        load_completed_version(self.version)

    def test_native_requires_complete_manifest_and_all_other_fields_identical(self):
        original_result, original_manifest = deepcopy(self.result), deepcopy(self.manifest)
        for invalid in ('incomplete_native', 'absent_native', 'other_field', 'unknown_reason'):
            with self.subTest(case=invalid):
                self.result, self.manifest = deepcopy(original_result), deepcopy(original_manifest)
                self.result['scenes'][0]['native_manifest'] = {'complete': True}
                self.manifest['scenes'][0] = deepcopy(self.result['scenes'][0])
                self.manifest['scenes'][0]['reused'] = False
                self.manifest['scenes'][0].pop('reuse_reason')
                if invalid == 'incomplete_native':
                    for source in (self.result, self.manifest):
                        source['scenes'][0]['native_manifest']['complete'] = False
                elif invalid == 'absent_native':
                    for source in (self.result, self.manifest):
                        source['scenes'][0].pop('native_manifest')
                elif invalid == 'other_field':
                    self.manifest['scenes'][0]['current_render_seconds'] = 5
                else:
                    self.manifest['scenes'][0]['reuse_reason'] = 'unknown_reason'
                self.persist()
                self.assert_rejected_without_writes()

    def test_manifest_metadata_and_scene_order_rejected(self):
        original = deepcopy(self.manifest)
        for mutation in ('plan_hash', 'renderer_version', 'extra_key', 'order'):
            with self.subTest(field=mutation):
                self.manifest = deepcopy(original)
                if mutation == 'order':
                    self.manifest['scenes'].reverse()
                else:
                    self.manifest[mutation] = 'incorrect'
                self.persist()
                self.assert_rejected_without_writes()

    def test_matching_false_hash_or_altered_bytes_still_rejected(self):
        for kind in ('movie', 'audit', 'final'):
            with self.subTest(file=kind):
                item = self.result['scenes'][0] if kind != 'final' else self.result['outputs']
                path = Path(item[kind])
                original = path.read_bytes()
                path.write_bytes(b'ALTERED')
                self.assert_rejected_without_writes()
                path.write_bytes(original)
        self.result['scenes'][0]['video_sha256'] = '0' * 64
        self.manifest['scenes'][0]['video_sha256'] = '0' * 64
        self.persist()
        self.assert_rejected_without_writes()

    def test_approval_qc_and_scene_json_are_required_before_mutation(self):
        for path, replacement in [('approval.json', {'user_approval': False}),
                                  ('renders/checkpoint.json', {'complete': False}),
                                  ('scene_json/S001.json', {'scene_id': 'S001', 'duration': 3}),
                                  ('qc/qc_report.json', {'passed': False})]:
            with self.subTest(file=path):
                target = self.version / path
                original = target.read_bytes()
                write(target, replacement)
                self.assert_rejected_without_writes()
                target.write_bytes(original)

    def test_real_media_probe_rejection_blocks_writes(self):
        with patch('deployment.resume_evidence.valid_scene_file', return_value=False):
            self.assert_rejected_without_writes()

    def test_returned_result_cannot_replace_record_but_reused_final_flag_is_supported(self):
        altered = deepcopy(self.result)
        altered['scenes'][0]['current_render_seconds'] = 1
        before = self.files()
        with self.assertRaisesRegex(EngineError, '완료 증거'):
            self.finalize(result=altered)
        self.assertEqual(self.files(), before)
        reused = {**deepcopy(self.result), 'reused_final': True}
        self.assertTrue(self.finalize(result=reused)['changed'])

    def test_version_escape_or_missing_runtime_marker_rejected(self):
        marker = self.root / 'mobile-state.json'
        original = marker.read_bytes()
        marker.unlink()
        self.assert_rejected_without_writes()
        marker.write_bytes(original)
        before = self.files()
        with self.assertRaises(EngineError):
            finalize_resume_evidence(self.root, self.root.parent / 'old-project/versions/v001',
                                     expected_plan_hash=self.plan['plan_hash'])
        self.assertEqual(self.files(), before)


if __name__ == '__main__':
    unittest.main()
