"""Production integration preserves old masters and independently keys new pixels."""
import copy
import json
from pathlib import Path
import unittest
from engine.assets import renderer_version
from engine.rendering import scene_cache_key
from engine.visibility import _source_fingerprint

ROOT = Path(__file__).resolve().parents[1]

class ProductionVisualCache(unittest.TestCase):
    def test_legacy_earth_and_flat_hashes_are_unchanged(self):
        self.assertEqual(renderer_version(), '2225c34373166e87f4ab1101e7d15756d2a82526668e64b1e1fb1f2184271646')
        self.assertEqual(renderer_version({'render_mode':'FLAT_MAP_PREMIUM'}), '0236dad924312c6fdb8234a60263ec8befe576a7d104ff7acaad0567209b3064')

    def test_new_policy_invalidates_only_tagged_scene_and_includes_source(self):
        scene={'render_mode':'FLAT_MAP_PREMIUM','visual_polish':{'version':'v004','entity_separation':'v1'},'duration':3}
        original=copy.deepcopy(scene)
        old=renderer_version(scene)
        scene['production_defaults']={'version':'v1'}
        new=renderer_version(scene)
        self.assertNotEqual(new,old)
        self.assertEqual(renderer_version(original),old)
        self.assertNotEqual(scene_cache_key(scene,{'assets':[]},{'fps':30},new),scene_cache_key(original,{'assets':[]},{'fps':30},old))

    def test_story_global_default_does_not_invalidate_unchanged_approved_earth(self):
        scene=json.loads((ROOT.parent/'deliverables/WORLD_SIMULATION_ENGINE/PREMIUM_FLAT_MAP_15S_v004/scene_plan.json').read_text())['scenes'][-1]
        baseline=copy.deepcopy(scene)
        # Production plans cannot claim to remove this cached banner. Only the
        # actually changed new Earth scene gets a new render policy/hash.
        old=renderer_version(scene)
        self.assertEqual(renderer_version(baseline),old)
        changed=copy.deepcopy(scene)
        changed['production_defaults']={'version':'v1'}
        self.assertNotEqual(renderer_version(changed),old)
        self.assertEqual(scene,baseline)

    def test_visibility_certificate_hash_includes_production_adapter(self):
        old=_source_fingerprint({'scenes':[]})
        new=_source_fingerprint({'scenes':[{'production_defaults':{'version':'v1'}}]})
        self.assertNotEqual(new,old)

    def test_audio_only_revision_reuses_production_pixels_but_visual_changes_do_not(self):
        scene={'render_mode':'FLAT_MAP_PREMIUM', 'visual_polish':{'version':'v004','entity_separation':'v1'},
               'production_defaults':{'version':'v1'}, 'duration':3, 'music_energy':.5,
               'sfx_intensity':'LOW', 'sound_events':[{'time':.5,'sound':'soft_pulse'}],
               'visual_events':[{'id':'E1','time':.5,'kind':'city_reveal','sfx_variant':'A'}],
               'labels':[{'text':'SEOUL'}], 'motion_timing':{'camera_travel_duration':1.2}}
        renderer=renderer_version(scene)
        key=lambda value:scene_cache_key(value,{'assets':[]},{'fps':30},renderer)
        audio=copy.deepcopy(scene)
        audio['sound_events']=[{'time':.5,'sound':'cinematic_hit'}]
        audio['music_energy']=.9
        audio['sfx_intensity']='HIGH'
        audio['visual_events'][0]['sfx_variant']='B'
        self.assertEqual(key(audio),key(scene))
        old_audio_asset={'id':'production-sfx-library','actual_sha256':'a','asset_role':'audio_source'}
        new_audio_asset={**old_audio_asset,'actual_sha256':'b'}
        self.assertEqual(scene_cache_key(scene,{'assets':[old_audio_asset]},{'fps':30},renderer),
                         scene_cache_key(scene,{'assets':[new_audio_asset]},{'fps':30},renderer))
        for visual in ['timing','label','event']:
            changed=copy.deepcopy(scene)
            if visual=='timing':changed['motion_timing']['camera_travel_duration']=.8
            elif visual=='label':changed['labels'][0]['text']='TOKYO'
            else:changed['visual_events'][0]['time']=.7
            self.assertNotEqual(key(changed),key(scene))
        legacy=copy.deepcopy(scene)
        legacy.pop('production_defaults')
        legacy_audio=copy.deepcopy(legacy)
        legacy_audio['sound_events'][0]['sound']='cinematic_hit'
        self.assertNotEqual(key(legacy),key(legacy_audio))

if __name__=='__main__':
    unittest.main()
