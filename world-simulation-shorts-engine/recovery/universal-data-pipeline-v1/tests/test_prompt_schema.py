"""Structural JSON Schema tests; semantics and engine admission run separately in Node."""
from pathlib import Path
import copy
import json
import unittest

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / 'PROMPT_INPUT.schema.json').read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())


class PromptSchemaTests(unittest.TestCase):
    def test_schema_definition_is_valid(self):
        Draft202012Validator.check_schema(SCHEMA)


def valid_test(name):
    def check(self):
        value = json.loads((ROOT / 'examples' / (name + '.json')).read_text())
        self.assertEqual([], [str(error) for error in VALIDATOR.iter_errors(value)])
    return check


for name in ['FICTIONAL_NAMIBIA', 'AVIATION_GERMANY', 'TRADE_CHILE']:
    setattr(PromptSchemaTests, 'test_actual_' + name.lower(), valid_test(name))


def invalid_test(mutate):
    def check(self):
        value = json.loads((ROOT / 'examples' / 'AVIATION_GERMANY.json').read_text())
        mutate(value)
        self.assertTrue(list(VALIDATOR.iter_errors(value)))
    return check


def remove_facts(value):
    del value['scenes'][0]['facts']


INVALID_CASES = {
    'unknown_top_field': lambda x: x.update({'hidden_override': True}),
    'wrong_mode': lambda x: x.update({'simulationType': 'UNKNOWN'}),
    'scalar_render_settings': lambda x: x.update({'renderSettings': 'not object'}),
    'unknown_source_region': lambda x: x['scenes'][0]['renderSettings'].update({'sourceRegionId': '../secret'}),
    'missing_facts': remove_facts,
    'invalid_latitude': lambda x: x['scenes'][0]['facts']['locations'][0].update({'anchor': [0, 91]}),
    'unknown_native_context': lambda x: x['scenes'][0]['facts']['native_context'].update({'skip': True}),
    'unknown_source_field': lambda x: x['scenes'][0]['facts']['source_notes'][0].update({'auto_verify': True}),
    'invalid_date': lambda x: x['scenes'][0]['facts']['time_range'].update({'start': '2026-02-30'}),
    'zero_fps': lambda x: x.update({'fps': 0}),
}
for name, mutate in INVALID_CASES.items():
    setattr(PromptSchemaTests, 'test_reject_' + name, invalid_test(mutate))


if __name__ == '__main__':
    unittest.main(verbosity=2)
