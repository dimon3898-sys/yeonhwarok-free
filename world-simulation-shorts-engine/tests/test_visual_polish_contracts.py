"""Opt-in appearance must not invalidate the preserved masters' cache identity."""
import copy
import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator
from engine.assets import renderer_version
from engine.schema import SCHEMA_PATH
from engine.rendering import scene_cache_key

ROOT = Path(__file__).resolve().parents[1]

class VisualPolishContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads((ROOT/'tests/fixtures/shipping75_v002_label_readability_original.json').read_text())
        cls.validator = Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))

    def test_legacy_master_digest_and_cache_key_remain_identical(self):
        scene = copy.deepcopy(self.plan['scenes'][0])
        expected = '2225c34373166e87f4ab1101e7d15756d2a82526668e64b1e1fb1f2184271646'
        self.assertEqual(renderer_version(scene), expected)
        assets = {'assets':[]}
        quality = {'quality':'HIGH', 'fps':30}
        self.assertEqual(scene_cache_key(scene, assets, quality, expected),
                         scene_cache_key(scene, assets, quality, renderer_version(scene)))
        scene['visual_polish'] = {'version':'v004'}
        self.assertNotEqual(renderer_version(scene), expected)
        self.assertNotEqual(scene_cache_key(scene, assets, quality, expected),
                            scene_cache_key(scene, assets, quality, renderer_version(scene)))

    def test_original_flat_digest_is_unchanged(self):
        self.assertEqual(renderer_version({'render_mode':'FLAT_MAP_PREMIUM'}),
                         '0236dad924312c6fdb8234a60263ec8befe576a7d104ff7acaad0567209b3064')

    def test_polish_is_explicit_versioned_and_not_a_clip_fallback(self):
        plan = copy.deepcopy(self.plan)
        scene = plan['scenes'][0]
        scene['visual_polish'] = {'version':'v004'}
        scene['render_mode'] = 'MASTER_V3_EARTH'
        self.assertFalse(list(self.validator.iter_errors(plan)))
        scene['visual_polish']['version'] = 'unknown'
        self.assertTrue(list(self.validator.iter_errors(plan)))
        scene['visual_polish']['version'] = 'v004'
        scene['scene_type'] = 'CINEMATIC_CLIP'
        self.assertTrue(list(self.validator.iter_errors(plan)))

    def test_separation_only_invalidates_the_explicit_flat_scene(self):
        scenes = [
            {'render_mode':'FLAT_MAP_PREMIUM','visual_polish':{'version':'v004'}},
            {'render_mode':'MASTER_V3_EARTH','visual_polish':{'version':'v004'}},
        ]
        previous = [renderer_version(scene) for scene in scenes]
        revised = copy.deepcopy(scenes)
        revised[0]['visual_polish']['entity_separation'] = 'v1'
        self.assertNotEqual(renderer_version(revised[0]), previous[0])
        self.assertEqual(renderer_version(revised[1]), previous[1])
        plan = copy.deepcopy(self.plan)
        plan['scenes'][0]['render_mode'] = 'MASTER_V3_EARTH'
        plan['scenes'][0]['visual_polish'] = {'version':'v004','entity_separation':'v1'}
        self.assertTrue(list(self.validator.iter_errors(plan)))

if __name__ == '__main__':
    unittest.main()
