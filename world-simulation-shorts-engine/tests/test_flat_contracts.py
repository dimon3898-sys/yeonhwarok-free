"""Backward compatibility and fail-closed geographic contracts for opt-in maps."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator
from engine.assets import renderer_version, project_renderer_version
from engine.gis import resolve_location
from engine.presets import CAMERA_PRESETS, FLAT_CAMERA_PRESETS, scene_render_mode
from engine.schema import SCHEMA_PATH, validate_flat_scene
from engine.rendering import scene_cache_key
from engine.storage import canonical

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT/'tests/fixtures/shipping75_v002_label_readability_original.json'

class FlatContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan=json.loads(FIXTURE.read_text())
        cls.validator=Draft202012Validator(json.loads(SCHEMA_PATH.read_text()))

    def flat_scene(self):
        scene=copy.deepcopy(self.plan['scenes'][0])
        scene.update(render_mode='FLAT_MAP_PREMIUM',camera_preset='FLAT_COUNTRY_FOCUS')
        c=resolve_location('seoul')['coordinates']
        scene['flat_map']={'projection':'LOCAL_MERCATOR','country_highlights':[{'country':'KOR','source_id':'natural_earth_countries','start_time':0.,'end_time':scene['duration'],'opacity':.18}],
                           'focus':[{'target_id':'seoul','coordinates':c,'start_time':0.,'end_time':scene['duration'],'radius_degrees':5,'strength':.16}]}
        scene['entity_actions']=[];scene['effects']=[]
        return scene

    def test_original_earth_version_and_camera_grammar_are_preserved(self):
        self.assertEqual(renderer_version(),'2225c34373166e87f4ab1101e7d15756d2a82526668e64b1e1fb1f2184271646')
        self.assertEqual(scene_render_mode(self.plan['scenes'][0]),'MASTER_V3_EARTH')
        self.assertEqual(len(FLAT_CAMERA_PRESETS),8)
        self.assertEqual(CAMERA_PRESETS['GLOBAL_ESTABLISH']['height'],1.8)
        self.assertEqual(project_renderer_version(self.plan),renderer_version())

    def test_old_scene_cache_key_is_identical(self):
        scene=copy.deepcopy(self.plan['scenes'][0]);scene.pop('render_time_offset',None)
        assets={'assets':[{'id':'original','actual_sha256':'a'*64}]};quality={'fps':30};context={'lighting_anchor':scene['coordinates']}
        expected=hashlib.sha256(canonical({'scene_json':scene,'assets':{'original':'a'*64},'renderer_version':renderer_version(),'quality_preset':quality,'scene_render_context':context})).hexdigest()
        self.assertEqual(scene_cache_key(scene,assets,quality,renderer_version(),context),expected)
        flat=copy.deepcopy(scene);flat['render_mode']='FLAT_MAP_PREMIUM';flat['flat_map']={'projection':'LOCAL_MERCATOR'}
        first=scene_cache_key(flat,assets,quality,renderer_version(flat),context)
        flat['flat_map']['projection']='LOCAL_EQUIRECTANGULAR'
        self.assertNotEqual(first,scene_cache_key(flat,assets,quality,renderer_version(flat),context))

    def test_preview_lower_bound_requires_explicit_mode_and_flag(self):
        plan=copy.deepcopy(self.plan);plan['duration']=15
        self.assertTrue(list(self.validator.iter_errors(plan)))
        plan['metadata']['flat_map_preview']=True
        self.assertTrue(list(self.validator.iter_errors(plan)))
        plan['scenes'][0]=self.flat_scene()
        self.assertFalse(list(self.validator.iter_errors(plan)))
        plan['duration']=9
        self.assertTrue(list(self.validator.iter_errors(plan)))

    def test_new_projection_is_rejected_on_implicit_earth_scene(self):
        plan=copy.deepcopy(self.plan);plan['scenes'][0]['flat_map']={'projection':'LOCAL_MERCATOR'}
        self.assertTrue(list(self.validator.iter_errors(plan)))
        plan['scenes'][0]['render_mode']='UNKNOWN'
        self.assertTrue(list(self.validator.iter_errors(plan)))

    def test_real_country_shape_and_verified_focus_are_required(self):
        scene=self.flat_scene();sources={s['id'] for s in self.plan['sources']}|{'natural_earth_countries','natural_earth_places'}
        self.assertFalse(validate_flat_scene(scene,sources))
        scene['flat_map']['country_highlights'][0]['country']='XXX'
        self.assertIn('UNKNOWN_GIS_COUNTRY',{e['code'] for e in validate_flat_scene(scene,sources)})
        scene['flat_map']['country_highlights'][0]['country']='KOR'
        scene['flat_map']['focus'][0]['coordinates']['lon']+=.1
        self.assertIn('UNVERIFIED_FLAT_GIS_COORDINATE',{e['code'] for e in validate_flat_scene(scene,sources)})

    def test_next_event_camera_is_bound_to_a_real_later_event(self):
        scene=self.flat_scene();c=resolve_location('tokyo')['coordinates'];scene['visual_events'].append({'id':'NEXT','kind':'new_variable','time':2.,'coordinates':c})
        scene['flat_map']['next_event']={'event_id':'NEXT','coordinates':copy.deepcopy(c),'event_time':2.,'lead_time':.65}
        sources={s['id'] for s in self.plan['sources']}|{'natural_earth_countries','natural_earth_places'}
        self.assertFalse(validate_flat_scene(scene,sources))
        scene['flat_map']['next_event']['event_time']=2.2
        self.assertIn('NEXT_EVENT_CAMERA_BINDING_MISMATCH',{e['code'] for e in validate_flat_scene(scene,sources)})
        scene['flat_map']['next_event']['event_time']=2.;scene['flat_map']['next_event']['lead_time']=2.1
        self.assertIn('NEXT_EVENT_CAMERA_NO_LEAD_WINDOW',{e['code'] for e in validate_flat_scene(scene,sources)})

    def test_actions_cannot_target_missing_entities_or_routes(self):
        scene=self.flat_scene();scene['entity_actions']=[{'entity_id':'missing','action':'reroute','route_id':'invented','time':1}]
        errors={e['code'] for e in validate_flat_scene(scene,{s['id'] for s in self.plan['sources']})}
        self.assertIn('UNKNOWN_FLAT_ACTION_ENTITY',errors);self.assertIn('MISSING_FLAT_ACTION_ROUTE',errors)

    def test_new_network_event_rejects_early_or_continued_connection(self):
        scene=self.flat_scene();sources={s['id'] for s in self.plan['sources']}|{'natural_earth_countries','natural_earth_places'}
        route=scene['routes'][0];route.update(start_time=1.05,progress_start=0.)
        # Reproduce the actual 15s sample's early-connection defect on the
        # checked-in verified route fixture; no generated project is required.
        event={'id':'NETWORK','kind':'network_expand','time':1.7,'target_id':route['route_id'],'meaningful':True}
        scene['visual_events'].append(event)
        self.assertIn('FLAT_NETWORK_EVENT_TIMING_MISMATCH',{e['code'] for e in validate_flat_scene(scene,sources)})
        route['start_time']=event['time'];route['progress_start']=.1
        self.assertIn('FLAT_NETWORK_ROUTE_ALREADY_ACTIVE',{e['code'] for e in validate_flat_scene(scene,sources)})
        route['progress_start']=0;event['target_id']='missing'
        self.assertIn('FLAT_NETWORK_NEW_ROUTE_REQUIRED',{e['code'] for e in validate_flat_scene(scene,sources)})

    def test_new_network_event_alignment_and_existing_overviews_are_compatible(self):
        scene=self.flat_scene();sources={s['id'] for s in self.plan['sources']}|{'natural_earth_countries','natural_earth_places'}
        route=scene['routes'][0];route['progress_start']=0.
        event={'id':'NETWORK','kind':'network_expand','time':1.7,'target_id':route['route_id'],'meaningful':True}
        scene['visual_events'].append(event)
        for kind in ['network_expand','network_expansion']:
            with self.subTest(kind=kind):
                event['kind']=kind;route['start_time']=event['time']
                self.assertFalse(validate_flat_scene(scene,sources))
                route['start_time']=event['time']-1/30
                self.assertFalse(validate_flat_scene(scene,sources))
                route['start_time']=event['time']-2/30
                self.assertIn('FLAT_NETWORK_EVENT_TIMING_MISMATCH',{e['code'] for e in validate_flat_scene(scene,sources)})
        event['kind']='final_reveal';route['progress_start']=.9
        self.assertFalse(validate_flat_scene(scene,sources))
        event['kind']='network_expand';event['meaningful']=False
        self.assertFalse(validate_flat_scene(scene,sources))
        scene.pop('render_mode');scene['camera_preset']='GLOBAL_ESTABLISH';event['meaningful']=True
        self.assertFalse(validate_flat_scene(scene,sources))

    def test_registered_cached_terrain_url_is_scoped_and_provenance_checked(self):
        rows=json.loads((ROOT/'assets/flat/SOURCES.json').read_text())
        if isinstance(rows,dict):rows=rows.get('assets',[])
        asset=next(item for item in rows if item['file'].startswith('web/flat_assets/cache/'))
        bounds=asset['geographic_bounds'];terrain={'url':'/static/'+asset['file'].removeprefix('web/'),'bounds':[bounds[k] for k in ['west','south','east','north']]}
        scene=self.flat_scene();scene['flat_map']['terrain_texture']=terrain
        plan=copy.deepcopy(self.plan);plan['scenes'][0]=scene
        self.assertFalse(list(self.validator.iter_errors(plan)))
        sources={s['id'] for s in self.plan['sources']}|{'natural_earth_countries','natural_earth_places'}
        self.assertFalse(validate_flat_scene(scene,sources))
        scene['flat_map']['terrain_texture']['url']='/static/flat_assets/cache/../../private.png'
        self.assertTrue(list(self.validator.iter_errors(plan)))
        scene['flat_map']['terrain_texture']['url']='/static/flat_assets/cache/terrain_'+('f'*64)+'.png'
        self.assertFalse(list(self.validator.iter_errors(plan)))
        self.assertIn('UNREGISTERED_OR_MISLOCATED_FLAT_TERRAIN',{e['code'] for e in validate_flat_scene(scene,sources)})

    def test_transition_backend_does_not_invalidate_normal_earth(self):
        scene=copy.deepcopy(self.plan['scenes'][0]);scene['transition_in']='FLAT_TO_EARTH'
        self.assertNotEqual(renderer_version(scene),renderer_version())
        self.assertNotEqual(project_renderer_version({'scenes':[scene]}),renderer_version())

class FlatExecutedEvidence(unittest.TestCase):
    def test_caption_cannot_prove_physical_reroute(self):
        from engine.qc import analyze_rendered_retention
        event={'id':'NEW_ROUTE','kind':'route_reroute','time':1.,'duration':1.,'target_id':'R2','role':'response','caused_by':None,'meaningful':True}
        scene={'scene_id':'S001','start_time':0.,'duration':3.,'render_mode':'FLAT_MAP_PREMIUM','camera_start':{'lon':0},'camera_end':{'lon':1},'motion_start':0,'visual_events':[event]}
        plan={'duration':3.,'story':{'hook':'A route changes?'},'scenes':[scene]}
        audit={'scene_id':'S001','t':1.,'labels':[],'meaningfulEventsRendered':[{'event_id':'NEW_ROUTE','kind':'route_reroute','actual_time':1.,'visible':True,'rendered_primitive':'information','text':'A new route'}]}
        report=analyze_rendered_retention(plan,[audit])
        self.assertIn('PHYSICAL_EVENT_REQUIRES_PHYSICAL_PRIMITIVE',{e['code'] for e in report['errors']})

    def test_camera_only_events_remain_excluded(self):
        from engine.retention import analyze_retention
        scene={'scene_id':'S001','start_time':0.,'duration':15.,'camera_start':{'lon':0},'camera_end':{'lon':1},'motion_start':0,'visual_events':[{'id':f'P{i}','kind':'pan','time':i,'meaningful':True} for i in range(15)]}
        report=analyze_retention({'duration':15.,'story':{'hook':'Where next?'},'scenes':[scene]})
        self.assertEqual(report['metrics']['meaningful_event_count'],0)
        self.assertFalse(report['metrics']['camera_events_counted'])

class PreservedClipCache(unittest.TestCase):
    def test_unchanged_clip_uses_actual_preserved_source_sha(self):
        from engine.rendering import legacy_clip_source_hash
        from engine.assets import sha256_file
        preserved=ROOT/'engine/rendering_before_flat_preserved.py'
        self.assertEqual(legacy_clip_source_hash(),sha256_file(preserved))
        self.assertEqual(legacy_clip_source_hash(),'66d841bad30fcf89bdd1b0d5fd2287e7be45047e389cc1e5114ce282d88ccd48')

    def test_actual_old_clip_key_is_preserved(self):
        from engine.assets import sha256_file
        # Cache hashing precedes media validation; this existing immutable local
        # source file supplies verifiable bytes without rendering or writing media.
        source=ROOT/'web/render.html'
        scene={'scene_type':'CINEMATIC_CLIP','clip':{'path':str(source),'user_owned':True}}
        assets={'assets':[]};quality={'fps':30};renderer=renderer_version()
        expected=hashlib.sha256(canonical({'scene_json':scene,'assets':{},'renderer_version':renderer,
                 'quality_preset':quality,'external_clip_sha256':sha256_file(source),
                 'clip_renderer_version':sha256_file(ROOT/'engine/rendering_before_flat_preserved.py')})).hexdigest()
        self.assertEqual(scene_cache_key(scene,assets,quality,renderer),expected)

    def test_clip_body_or_referenced_import_change_invalidates_compatibility(self):
        from engine.rendering import legacy_clip_source_hash
        original=(ROOT/'engine/rendering.py').read_text()
        altered=original.replace('clip = scene.get("cinematic_clip", scene.get("clip", {}))','clip = scene.get("clip", scene.get("cinematic_clip", {}))')
        self.assertNotEqual(legacy_clip_source_hash(altered),legacy_clip_source_hash(original))
        self.assertEqual(legacy_clip_source_hash(altered),hashlib.sha256(altered.encode()).hexdigest())
        imported=original.replace('from .qc import probe_video,','from .qc import probe_video_changed as probe_video,')
        self.assertEqual(legacy_clip_source_hash(imported),hashlib.sha256(imported.encode()).hexdigest())

    def test_additive_flat_dispatch_does_not_invalidate_clip(self):
        from engine.rendering import legacy_clip_source_hash
        original=(ROOT/'engine/rendering.py').read_text()
        self.assertEqual(legacy_clip_source_hash(original+'\n# Independent flat routing changes.\n'),legacy_clip_source_hash(original))

if __name__=='__main__':unittest.main()
