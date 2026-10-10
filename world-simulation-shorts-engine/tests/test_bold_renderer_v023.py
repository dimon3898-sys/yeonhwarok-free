"""Native inheritance/selection regression; never launches a GPU renderer."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from engine.infographic_planner import generate_infographic_qa
from engine.bold_infographic import prepare_bold_infographic

ROOT = Path(__file__).resolve().parents[1]


class BoldNativeRendererTests(unittest.TestCase):
    def test_native_all_720_camera_material_layout_and_state_preserved(self):
        plan = prepare_bold_infographic(generate_infographic_qa())
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'plan.json'
            source.write_text(json.dumps(plan, ensure_ascii=False))
            try:
                completed = subprocess.run(
                    ['node', str(ROOT / 'tools/test_bold_renderer_v023.mjs'), str(source)],
                    cwd=ROOT, text=True, capture_output=True, timeout=180, check=True)
            except subprocess.CalledProcessError as error:
                # Test fixture contains no credentials; bound the dynamic-module
                # stack so a failure cannot dump the entire inherited harness.
                self.fail((error.stderr or error.stdout or str(error))[-4000:])
            result = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertTrue(result['passed'])
        self.assertEqual(result['frames'], 720)
        for field in ('camera_trajectory', 'material', 'wide', 'marker',
                      'text_layout', 'canal_event_state'):
            self.assertEqual(result[field], 'UNCHANGED')
        self.assertEqual(result['overlay_off'], 'EXACT_V022')
        self.assertEqual(result['additional_texture_uploads'], 0)
        self.assertEqual(result['GPU'], 'NOT_RUN')


if __name__ == '__main__':
    unittest.main()
