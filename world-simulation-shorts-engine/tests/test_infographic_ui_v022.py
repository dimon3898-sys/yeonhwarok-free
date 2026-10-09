"""Actual mobile DOM selection/request regressions; no video or GPU rendering."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InfographicUISelection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = subprocess.run(
            ['node', str(ROOT / 'tests/infographic_ui_v022.mjs')],
            cwd=ROOT, capture_output=True, text=True, timeout=180,
        )
        if result.returncode:
            raise AssertionError(result.stderr[-6000:])
        cls.report = json.loads(result.stdout)
        if cls.report.get('gpu_draw') != 'NOT_RUN' or cls.report.get('video_render') != 'NOT_RUN':
            raise AssertionError('UI verification must not invoke a renderer or GPU')

    def check(self, name):
        self.assertTrue(self.report['passed'])
        self.assertEqual(self.report['checks'][name], 'PASS')
        self.assertEqual(self.report['transport'], 'ACTUAL_LOCAL_HTTP')

    def test_render_plan_preserves_reference_master_and_next_request(self):
        self.check('render_plan_preserves_reference_master_and_next_request')

    def test_explicit_legacy_choice_is_not_inferred_from_scene_direction(self):
        self.check('explicit_legacy_choice_is_not_overwritten_by_scene_direction')

    def test_named_qa_submission_forces_declared_24_second_settings(self):
        self.check('named_qa_actual_submission_and_fixed_controls')

    def test_production_submits_exact_authored_record_without_ordinary_options(self):
        self.check('production_authored_file_actual_submission_has_no_ordinary_options')

    def test_scene_version_mismatch_blocks_approve_and_resume(self):
        self.check('mismatched_scene_versions_visible_and_block_approve_resume')

    def test_named_qa_without_actual_metadata_is_a_visible_error(self):
        self.check('named_qa_missing_metadata_is_not_shown_as_success')

    def test_saved_and_historical_plans_do_not_mutate_creation_choices(self):
        self.check('saved_plan_and_history_do_not_change_explicit_creation_choices')

    def test_failed_creation_preserves_saved_plan_version_and_approval(self):
        self.check('failed_creation_keeps_saved_plan_version_and_approval')

    def test_explicit_profile_and_mode_persist_reload(self):
        self.check('explicit_profile_and_mode_persist_reload_without_plan_inference')

    def test_short_qa_preserved_and_new_24_second_qa_submits(self):
        self.check('short_qa_12_15_preserved_and_new_qa_24_is_not_browser_blocked')

    def test_ordinary_control_values_restore_after_mode_changes(self):
        self.check('ordinary_options_restore_after_explicit_mode_change')

    def test_actual_helpers_reject_partial_forged_and_unknown_selection(self):
        self.check('actual_exported_helpers_reject_partial_forged_or_unknown_selection')

    def test_invalid_authored_json_is_not_posted_or_replaced_with_content(self):
        self.check('invalid_authored_json_is_not_posted_and_no_script_is_invented')


if __name__ == '__main__':
    unittest.main()
