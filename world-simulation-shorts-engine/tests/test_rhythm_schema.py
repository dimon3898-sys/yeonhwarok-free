"""Additive rhythm contracts and validation before renderer certification."""
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jsonschema import Draft202012Validator

from engine.schema import SCHEMA_PATH, validate_plan


ROOT=Path(__file__).resolve().parents[1]
APPROVED=ROOT.parent/'deliverables/WORLD_SIMULATION_ENGINE/PREMIUM_FLAT_MAP_15S_v004/scene_plan.json'
NEW_CATEGORIES='CAMERA_SOFT_MOVE CAMERA_FAST_MOVE ZOOM_IN ZOOM_OUT COUNTRY_REVEAL REGION_REVEAL CITY_REVEAL ENTITY_SPAWN ENTITY_MOVE AIRCRAFT_PASS SHIP_PASS ROUTE_START ROUTE_PROGRESS ROUTE_COMPLETE ROUTE_BLOCK ROUTE_REROUTE RADAR SCAN WARNING ALERT IMPACT_LIGHT IMPACT_MEDIUM IMPACT_HEAVY SHOCKWAVE NETWORK_EXPAND NEW_VARIABLE COUNTER_RESPONSE TRANSITION_LIGHT TRANSITION_FAST TRANSITION_HEAVY MID_PEAK FINAL_PEAK FINAL_REVEAL'.split()
LEGACY_CATEGORIES='CAMERA_MOVE FAST_ZOOM COUNTRY_REVEAL CITY_REVEAL ENTITY_SPAWN AIRCRAFT_PASS SHIP_PASS ROUTE_START ROUTE_PROGRESS ROUTE_BLOCK REROUTE RADAR WARNING IMPACT SHOCKWAVE NETWORK_EXPAND NEW_VARIABLE MID_PEAK FINAL_PEAK FINAL_REVEAL TRANSITION'.split()


class RhythmSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=json.loads(APPROVED.read_text())
        cls.schema=json.loads(SCHEMA_PATH.read_text())
        cls.validator=Draft202012Validator(cls.schema)
        cls.scene_schema=cls.schema['properties']['scenes']['items']['properties']

    def sample(self):
        plan=deepcopy(self.original)
        scene=plan['scenes'][0]
        event=scene['visual_events'][0]
        plan['rhythm_policy']={
            'version':'v1','sfx_core_onset_offset_frames':1,'bgm_sidechain':True,
            'micro_pauses':[{'id':'P1','time':scene['start_time']+.1,'duration':.1,
                             'scene_id':scene['scene_id'],'event_id':event['id']}],
            'reference_pattern':'unequal beats and readable release',
        }
        scene['rhythm_micro_beats']=[{'id':'B1','time':event['time'],'duration':.15,
                                     'kind':'REVEAL','music_energy':.3,
                                     'visual_event_id':event['id']}]
        knots=[{'phase':0,'speed':1},{'phase':1,'speed':1}]
        scene['rhythm_visual']={'version':'v1','camera':{'knots':deepcopy(knots)},
                                'zoom':{'knots':deepcopy(knots)},
                                'routes':[{'route_id':scene['routes'][0]['route_id'],
                                           'knots':deepcopy(knots)}]}
        return plan

    def assert_schema_invalid(self,plan):
        self.assertTrue(list(self.validator.iter_errors(plan)))

    def test_legacy_and_complete_rhythm_plan_remain_schema_valid(self):
        Draft202012Validator.check_schema(self.schema)
        self.assertFalse(list(self.validator.iter_errors(self.original)))
        self.assertFalse(list(self.validator.iter_errors(self.sample())))

    def test_new_pace_and_sound_values_extend_every_existing_enum(self):
        pace_paths=[self.schema['properties']['options']['properties']['pace'],
                    self.schema['properties']['production_defaults']['properties']['pace'],
                    self.scene_schema['production_defaults']['properties']['pace'],
                    self.scene_schema['pace']]
        for enum in pace_paths:
            self.assertEqual(enum['enum'],['FAST','NORMAL','CINEMATIC','FAST_PLUS'])
        for events in ['visual_events','sound_events']:
            props=self.scene_schema[events]['items']['properties']
            self.assertEqual(props['sfx_category']['enum'][:len(LEGACY_CATEGORIES)],LEGACY_CATEGORIES)
            self.assertTrue(set(NEW_CATEGORIES)<=set(props['sfx_category']['enum']))
            self.assertEqual(props['sfx_intensity']['enum'],['LOW','MEDIUM','HIGH','PEAK','SUBTLE'])
        self.assertEqual(self.scene_schema['sfx_intensity']['enum'],['LOW','MEDIUM','HIGH','PEAK','SUBTLE'])
        # Rendering quality is a different contract despite also having FAST.
        self.assertEqual(self.scene_schema['render_quality']['enum'],['FAST','HIGH','CINEMA'])

    def test_policy_types_and_short_pause_bounds_are_enforced(self):
        for value in [-1,2,.5,True,'1']:
            with self.subTest(offset=value):
                plan=self.sample();plan['rhythm_policy']['sfx_core_onset_offset_frames']=value
                self.assert_schema_invalid(plan)
        for key,value in [('time',-.001),('duration',0),('duration',.301),
                          ('scene_id',None),('event_id',1),('id',False)]:
            with self.subTest(pause=(key,value)):
                plan=self.sample();plan['rhythm_policy']['micro_pauses'][0][key]=value
                self.assert_schema_invalid(plan)
        for key,value in [('version','v2'),('bgm_sidechain','true'),('reference_pattern',None)]:
            with self.subTest(policy=(key,value)):
                plan=self.sample();plan['rhythm_policy'][key]=value
                self.assert_schema_invalid(plan)

    def test_micro_beat_kind_clock_and_energy_are_typed(self):
        for key,value in [('kind','CAPTION_SWAP'),('time',-.001),('duration',0),
                          ('music_energy',-.01),('music_energy',1.01),
                          ('music_energy',True),('visual_event_id',None)]:
            with self.subTest(beat=(key,value)):
                plan=self.sample();plan['scenes'][0]['rhythm_micro_beats'][0][key]=value
                self.assert_schema_invalid(plan)

    def test_optional_sound_pin_and_authored_choice_policy_are_typed(self):
        plan=self.sample()
        plan['rhythm_policy'].update(sfx_library_content_sha256='a0'*32,
                                     preserve_authored_sfx_choices=True)
        self.assertFalse(list(self.validator.iter_errors(plan)))
        for key,value in [('sfx_library_content_sha256','a0'*31),
                          ('sfx_library_content_sha256','z'*64),
                          ('sfx_library_content_sha256',None),
                          ('preserve_authored_sfx_choices','false')]:
            with self.subTest(sound_policy=(key,value)):
                invalid=deepcopy(plan);invalid['rhythm_policy'][key]=value
                self.assert_schema_invalid(invalid)

    def test_knots_have_bounded_count_phase_and_speed(self):
        for count in [1,17]:
            with self.subTest(count=count):
                plan=self.sample()
                plan['scenes'][0]['rhythm_visual']['camera']['knots']=[{'phase':i/max(1,count-1),'speed':1} for i in range(count)]
                self.assert_schema_invalid(plan)
        for key,value in [('phase',-.01),('phase',1.01),('speed',-.01),
                          ('speed',4.01),('speed','1'),('phase',False)]:
            with self.subTest(knot=(key,value)):
                plan=self.sample();plan['scenes'][0]['rhythm_visual']['zoom']['knots'][0][key]=value
                self.assert_schema_invalid(plan)

    def test_new_objects_reject_unknown_properties_and_missing_required_keys(self):
        for path in [('rhythm_policy',),('rhythm_policy','micro_pauses',0),
                     ('scenes',0,'rhythm_micro_beats',0),('scenes',0,'rhythm_visual'),
                     ('scenes',0,'rhythm_visual','camera'),
                     ('scenes',0,'rhythm_visual','camera','knots',0),
                     ('scenes',0,'rhythm_visual','routes',0)]:
            with self.subTest(path=path):
                plan=self.sample();target=plan
                for key in path:target=target[key]
                target['unconsumed_setting']=True
                self.assert_schema_invalid(plan)
        plan=self.sample();del plan['rhythm_policy']['version']
        self.assert_schema_invalid(plan)
        plan=self.sample();del plan['scenes'][0]['rhythm_micro_beats'][0]['music_energy']
        self.assert_schema_invalid(plan)
        plan=self.sample();del plan['scenes'][0]['rhythm_visual']['routes'][0]['route_id']
        self.assert_schema_invalid(plan)

    def validate_with_report(self,plan,rhythm_report):
        validator=Mock(return_value=rhythm_report)
        with patch.dict(sys.modules,{'engine.rhythm':SimpleNamespace(validate_rhythm_plan=validator)}), \
             patch('engine.visibility.certify_semantic_visibility',return_value={'passed':True,'failures':[]}) as certifier:
            result=validate_plan(plan)
        return result,validator,certifier

    def test_rhythm_errors_are_exposed_and_block_visibility(self):
        rhythm={'passed':False,'errors':[{'code':'RHYTHM_INVALID_RAMP','message':'nonincreasing phase'}],
                'warnings':[{'code':'RHYTHM_REVIEW','message':'short breath'}],'metrics':{'ramps':1}}
        result,validator,certifier=self.validate_with_report(self.sample(),rhythm)
        validator.assert_called_once()
        self.assertFalse(result['passed'])
        self.assertEqual(result['rhythm_validation'],rhythm)
        self.assertIn(rhythm['errors'][0],result['errors'])
        self.assertIn(rhythm['warnings'][0],result['warnings'])
        self.assertIsNone(result['semantic_visibility'])
        certifier.assert_not_called()

    def test_successful_rhythm_validation_runs_visibility(self):
        rhythm={'passed':True,'errors':[],'warnings':[],'metrics':{'micro_beats':1}}
        result,validator,certifier=self.validate_with_report(self.sample(),rhythm)
        self.assertTrue(result['passed'],result['errors'])
        self.assertEqual(result['rhythm_validation'],rhythm)
        validator.assert_called_once()
        certifier.assert_called_once()

    def test_legacy_plan_does_not_invoke_rhythm_validator(self):
        result,validator,certifier=self.validate_with_report(deepcopy(self.original),None)
        self.assertTrue(result['passed'],result['errors'])
        self.assertNotIn('rhythm_validation',result)
        validator.assert_not_called()
        certifier.assert_called_once()

    def semantic_sample(self):
        knots=[{'phase':0,'speed':1},{'phase':1,'speed':1}]
        return {
            'rhythm_policy':{'version':'v1','sfx_core_onset_offset_frames':1,
                             'micro_pauses':[],'bgm_sidechain':True},
            'scenes':[{
                'scene_id':'S1','start_time':0,'duration':3,'render_mode':'FLAT_MAP_PREMIUM',
                'visual_events':[{'id':'E1','time':1,'kind':'route_start'},
                                 {'id':'E2','time':2,'kind':'response'}],
                'routes':[{'route_id':'R1','start_time':1,'end_time':2,
                           'progress_start':0,'progress_end':1},
                          {'route_id':'R_HELD','start_time':0,'end_time':3,
                           'progress_start':1,'progress_end':1}],
                'rhythm_micro_beats':[{'id':'B1','time':1,'duration':.5,'kind':'MOVE',
                                      'music_energy':.4,'visual_event_id':'E1'}],
                'rhythm_visual':{'version':'v1','camera':{'knots':deepcopy(knots)},
                                 'zoom':{'knots':deepcopy(knots)},
                                 'routes':[{'route_id':'R1','knots':deepcopy(knots)}]},
            }],
        }

    def test_semantic_ramp_requires_order_endpoints_and_positive_speed_area(self):
        from engine.rhythm import validate_rhythm_plan
        self.assertTrue(validate_rhythm_plan(self.semantic_sample())['passed'])
        cases=[
            ('RHYTHM_KNOT_ORDER',[{'phase':0,'speed':1},{'phase':.5,'speed':1},
                                  {'phase':.5,'speed':1},{'phase':1,'speed':1}]),
            ('RHYTHM_KNOT_ENDPOINTS',[{'phase':.1,'speed':1},{'phase':1,'speed':1}]),
            ('RHYTHM_ZERO_SPEED_AREA',[{'phase':0,'speed':0},{'phase':1,'speed':0}]),
        ]
        for code,knots in cases:
            with self.subTest(code=code):
                plan=self.semantic_sample();plan['scenes'][0]['rhythm_visual']['camera']['knots']=knots
                report=validate_rhythm_plan(plan)
                self.assertFalse(report['passed'])
                self.assertIn(code,{error['code'] for error in report['errors']})

    def test_semantic_beats_bind_real_scene_events_without_inflating_story_count(self):
        from engine.rhythm import validate_rhythm_plan
        plan=self.semantic_sample();report=validate_rhythm_plan(plan)
        self.assertTrue(report['passed'])
        self.assertEqual(report['metrics']['visual_events'],2)
        self.assertEqual(report['metrics']['micro_beats'],1)
        self.assertFalse(report['metrics']['micro_beats_counted_as_new_story_events'])
        plan['scenes'][0]['rhythm_micro_beats'][0]['visual_event_id']='MISSING'
        report=validate_rhythm_plan(plan)
        self.assertFalse(report['passed'])
        self.assertIn('RHYTHM_UNKNOWN_BEAT_EVENT',{error['code'] for error in report['errors']})

    def test_semantic_route_ramps_reject_held_unknown_and_duplicate_routes(self):
        from engine.rhythm import validate_rhythm_plan
        for route_id,code in [('R_HELD','RHYTHM_HELD_ROUTE_RAMP'),
                              ('MISSING','RHYTHM_UNKNOWN_OR_DUPLICATE_ROUTE'),
                              ('R1','RHYTHM_UNKNOWN_OR_DUPLICATE_ROUTE')]:
            with self.subTest(route_id=route_id):
                plan=self.semantic_sample()
                ramp=deepcopy(plan['scenes'][0]['rhythm_visual']['routes'][0])
                ramp['route_id']=route_id
                plan['scenes'][0]['rhythm_visual']['routes'].append(ramp)
                report=validate_rhythm_plan(plan)
                self.assertFalse(report['passed'])
                self.assertIn(code,{error['code'] for error in report['errors']})


if __name__=='__main__':unittest.main()
