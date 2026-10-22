"""Structural contracts only; semantic/source/render admission is tested separately."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parents[1]
SCHEMA=json.loads((ROOT/'PRESENTATION_PROMPT.schema.json').read_text())
VALIDATOR=Draft202012Validator(SCHEMA)
def case(name='NEW_REGION_JAPAN_NL'):
    return json.loads((ROOT/'examples'/f'{name}.json').read_text())

class PresentationSchemaTests(unittest.TestCase):
    def test_schema_is_draft202012_valid(self):
        Draft202012Validator.check_schema(SCHEMA)
    def test_existing_facts_definitions_reused_without_edits(self):
        old_path=ROOT.parent/'universal-data-pipeline-v1/PROMPT_INPUT.schema.json'
        old=json.loads(old_path.read_text())
        self.assertEqual(SCHEMA['$defs']['attachedData']['$defs'],old['$defs'])
        self.assertEqual(SCHEMA['x-reusedFactsSchema']['sha256'],hashlib.sha256(old_path.read_bytes()).hexdigest())
    def test_five_positive_envelopes_structurally_validate(self):
        for name in ['AVIATION_EUROPE_NL','TRADE_SOUTH_AMERICA_NL','FICTIONAL_AFRICA_NL','NEW_REGION_JAPAN_NL','NEW_REGION_AUSTRALIA_NL']:
            with self.subTest(name=name):
                self.assertEqual(list(VALIDATOR.iter_errors(case(name))),[])
    def test_missing_scalar_can_be_resolved_by_bounded_language(self):
        value=case()
        for key in ['topic','durationSeconds','fps','resolution']:
            value['data'].pop(key,None)
        self.assertEqual(list(VALIDATOR.iter_errors(value)),[])
    def test_custom_coordinate_region_is_not_five_name_enum(self):
        value=case();value['region']={'center':[43.1,-12.2],'bbox':[38,-20,48,-4],'sourceId':'AUTO','crs':'EPSG:4326'}
        self.assertEqual(list(VALIDATOR.iter_errors(value)),[])
    def test_prompt_text_and_data_are_both_required(self):
        for field in ['prompt','data']:
            value=case();del value[field]
            self.assertTrue(list(VALIDATOR.iter_errors(value)))
    def test_unknown_top_level_field_rejected(self):
        value=case();value['secret']='do-not-use'
        self.assertTrue(list(VALIDATOR.iter_errors(value)))
    def test_unknown_camera_field_rejected(self):
        value=case();value['presentation']['camera']['orbit']=True
        self.assertTrue(list(VALIDATOR.iter_errors(value)))
    def test_keyframe_coordinate_shape_is_explicit_lon_lat(self):
        value=case();value['presentation']['camera']['keyframes'][0]['center']=[10,20,30]
        self.assertTrue(list(VALIDATOR.iter_errors(value)))
    def test_source_latitude_structural_range_is_preserved(self):
        value=case();value['region']['center']=[10,91]
        self.assertTrue(list(VALIDATOR.iter_errors(value)))
    def test_only_connected_cut_transition_shape_accepts(self):
        value=case();value['presentation']['transitions']=[{'type':'FADE','frame':90}]
        self.assertTrue(list(VALIDATOR.iter_errors(value)))
    def test_only_explicit_area_initial_state_modes_accept(self):
        value=case('FICTIONAL_AFRICA_NL');value['presentation']['initialStateVisibility']='PRESERVE_PROVIDED'
        self.assertEqual(list(VALIDATOR.iter_errors(value)),[])
        value['presentation']['initialStateVisibility']='FORCE_VISIBLE'
        self.assertTrue(list(VALIDATOR.iter_errors(value)))
    def test_unknown_fact_field_still_rejected(self):
        value=case();value['data']['scenes'][0]['facts']['fabricatedEvent']=True
        self.assertTrue(list(VALIDATOR.iter_errors(value)))
    def test_route_follow_needs_supplied_id_shape(self):
        value=case();value['presentation']['camera']={'mode':'ROUTE_FOLLOW','zoom':.8}
        self.assertTrue(list(VALIDATOR.iter_errors(value)))
    def test_palette_alpha_budget_is_explicit(self):
        value=case();value['presentation']['territoryColors']={'state':[1,0,0,.9]}
        self.assertTrue(list(VALIDATOR.iter_errors(value)))

if __name__=='__main__':
    unittest.main(verbosity=2)
