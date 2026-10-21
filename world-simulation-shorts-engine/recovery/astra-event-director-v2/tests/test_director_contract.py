"""CPU-only strict input/actual source-byte/Studio selector tests.

Small synthetic source documents are labelled fixtures. Real P0 artifacts are
checked separately. No test invokes a worker, GPU, HTTP service or paid action.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract = load('_test_astra_director_contract', HERE / 'director_contract.py')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='astra-director-contract-', dir='/workspace')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = {'schema': 'WORLD_ENGINE_UNIVERSAL_VIDEO_V2', 'fps': 30, 'totalFrames': 6,
            'legacyScenePlan': {'fixture': 'SYNTHETIC_NON_HISTORICAL'}, 'scenes': [
                {'renderProfile': {'nativePayload': {'fixture': True}}}],
            'productionV3': {'eventChapters': []}}
        self.plan_file = self.write('SOURCE.json', self.source)
        source_sha = digest(self.plan_file.read_bytes())
        self.chapters = [dict(chapterId='first', eventId='A', startFrame=0, endFrame=3,
            title='First fixture', displayLabel='2000-01-01', controlStartState='A', controlEndState='B'),
            dict(chapterId='second', eventId='B', startFrame=3, endFrame=6,
            title='Second fixture', displayLabel='2000-01-02', controlStartState='B', controlEndState='B')]
        self.schedule = [dict(chapterId='first', startFrame=0, endFrame=3, truthKind='schematic',
            stateId='A', sourceIds=['A'], sourceDate='2000-01-01'), dict(chapterId='second',
            startFrame=3, endFrame=6, truthKind='schematic', stateId='B', sourceIds=['B'], sourceDate='2000-01-02')]
        common = {'version': 1, 'sourcePlanSHA256': source_sha}
        self.docs = {
            'eventDirectorProfileRef': {**common, 'schema': 'TEST_PROFILE', 'subjectId': 'GLOBAL_FIXTURE',
                'fps': 30, 'totalFrames': 6, 'chapters': self.chapters, 'sourceSchedule': self.schedule},
            'sourceCatalogRef': {**common, 'schema': 'TEST_SOURCE_CATALOG', 'sources': {'A': {}, 'B': {}}},
            'cameraAdmissionRef': {**common, 'schema': 'TEST_CAMERA'},
            'controlTimelineRef': {**common, 'schema': 'TEST_CONTROL'},
            'markerEvidenceRef': {**common, 'schema': 'TEST_MARKERS', 'markers': []},
            'audioCueManifestRef': {**common, 'schema': 'TEST_AUDIO', 'enabled': False, 'gain': 0, 'cues': []}}
        self.request = {'schema': contract.SCHEMA, 'sourcePlanSha256': source_sha,
            'subjectId': 'GLOBAL_FIXTURE', 'fps': 30, 'totalFrames': 6,
            'requiredCapabilities': ['CAMERA.EVENT'], 'purpose': 'QUALIFIED_SOURCE_REVIEW'}
        self.trusted = {}
        for field, document in self.docs.items():
            file = self.write(field + '.json', document)
            ref = {'path': file.name, 'version': '1', 'sha256': digest(file.read_bytes())}
            self.request[field] = ref
            self.trusted[file.name] = {**ref, 'role': field}
        self.bindings = {'CAMERA.EVENT': {'available': True, 'sourcePath': str(HERE/'director_contract.py'),
            'sha256': digest((HERE/'director_contract.py').read_bytes()), 'symbol': 'normalize_request',
            'consumer': 'normalize_request', 'selector': 'EVENT_DIRECTOR_V1_EXPLICIT_CALLBACK'}}
        self.context = dict(source_plan_path=self.plan_file, source_root=self.root,
            trusted_refs=self.trusted, capability_bindings=self.bindings,
            component_validators={k: lambda doc, request, docs: {'ready': True, 'blockers': []}
                                  for k in ('cameraAdmissionRef', 'controlTimelineRef')})
        self.refresh_derivation()

    def write(self, name, document):
        path = self.root / name
        path.write_text(json.dumps(document, ensure_ascii=False, sort_keys=True) + '\n')
        return path

    def refresh_ref(self, field):
        path = self.write(field + '.json', self.docs[field])
        h = digest(path.read_bytes())
        self.request[field]['sha256'] = h
        self.trusted[path.name]['sha256'] = h

    def refresh_derivation(self):
        derived = deepcopy(self.source)
        derived['productionV3']['eventChapters'] = deepcopy(self.docs['eventDirectorProfileRef']['chapters'])
        scene = self.write('DERIVED.json', derived)
        front = self.write('FRONT.json', {'schema': 'TEST_PARTIAL_FRONT', 'fronts': []})
        compiler = self.root / 'compiler.mjs'
        compiler.write_text('// explicit synthetic compiler-source fixture only\n')
        receipt = self.write('RECEIPT.json', {'schema': 'WORLD_ENGINE_ASTRA_DERIVATION_RECEIPT_V2',
            'sourcePlanSHA256': self.request['sourcePlanSha256'],
            'eventProfileSHA256': self.request['eventDirectorProfileRef']['sha256'],
            'sourceCatalogSHA256': self.request['sourceCatalogRef']['sha256'],
            'derivedSceneSHA256': digest(scene.read_bytes()),
            'derivedFrontProfileSHA256': digest(front.read_bytes()), 'compilerSHA256': digest(compiler.read_bytes())})
        self.context['derivation_bindings'] = {'receiptPath': receipt, 'receiptSHA256': digest(receipt.read_bytes()),
            'scenePath': scene, 'frontProfilePath': front, 'compilerPath': compiler}

    def run_request(self, request=None, **overrides):
        return contract.normalize_request(self.request if request is None else request, **{**self.context, **overrides})

    def expect_error(self, code, request=None, **overrides):
        with self.assertRaises(contract.StudioContractError) as caught:
            self.run_request(request, **overrides)
        self.assertEqual(caught.exception.code, code)
        self.assertTrue(caught.exception.issues[0]['path'])
        self.assertIn('expected', caught.exception.issues[0])
        self.assertIn('actual', caught.exception.issues[0])

    def envelope(self, **outer):
        return {'prompt': json.dumps(self.request), **outer}

    @staticmethod
    def parent(value, **kwargs):
        # Explicit CPU callback fixture. No production admission or renderer.
        if value.get('sceneJson') is None:
            contract._parse_json(value['prompt'])
            return {'legacy': True}
        return {'schema': 'TEST_NORMALIZED_STUDIO_BASE', 'videoPlan': deepcopy(value['sceneJson']),
                'sfx': deepcopy(value.get('sfx')), 'profile': 'TEST_ONLY'}

    def normalize(self, value=None, **context):
        return contract.normalize_submission(self.envelope() if value is None else value,
            parent_normalize=self.parent, **{**self.context, **context})

    def test_valid_actual_source_binding_and_no_mutation(self):
        before = deepcopy(self.request)
        actual = self.run_request()
        self.assertTrue(actual['productionReady'])
        self.assertTrue(actual['reviewReady'])
        self.assertFalse(actual['renderAllowed'])
        self.assertEqual(actual['normalizedRequest'], before)
        self.assertEqual(self.request, before)
        self.assertEqual(actual['runtimeBindingManifest']['actualDerivation']['records']['scene']['sha256'],
                         digest((self.root/'DERIVED.json').read_bytes()))
        self.assertNotIn('derivedScene', actual)  # Compiler inputs are not a rendered Scene.

    def test_requested_blocked_capability_not_removed_for_review(self):
        self.bindings['CONTROL.MORPH'] = {'available': False, 'reason': 'SOURCE_GEOMETRY_MISSING'}
        self.request['requiredCapabilities'].append('CONTROL.MORPH')
        actual = self.run_request()
        self.assertFalse(actual['productionReady'])
        self.assertTrue(actual['reviewReady'])
        self.assertEqual(actual['normalizedRequest']['requiredCapabilities'], ['CAMERA.EVENT', 'CONTROL.MORPH'])
        self.assertFalse(actual['requiredCapabilitiesRemoved'])

    def test_null_reference_is_explicitly_blocked(self):
        self.request['cameraAdmissionRef'] = None
        actual = self.run_request()
        self.assertFalse(actual['productionReady'])
        self.assertFalse(actual['reviewReady'])
        self.assertIn('DIRECTOR_REFERENCE_UNRESOLVED', [x['code'] for x in actual['blockers']])

    def test_missing_or_extra_fields_and_nested_ref_fields_rejected(self):
        missing = deepcopy(self.request); del missing['markerEvidenceRef']
        self.expect_error('DIRECTOR_FIELD_REQUIRED', missing)
        extra = {**self.request, 'approved': True}
        self.expect_error('DIRECTOR_FIELD_UNSUPPORTED', extra)
        extra = deepcopy(self.request); extra['cameraAdmissionRef']['admitted'] = True
        self.expect_error('DIRECTOR_REFERENCE_FIELDS_INVALID', extra)

    def test_lexical_types_and_nonfinite_json_are_rejected(self):
        for name, value in (('fps', 30.0), ('totalFrames', True), ('purpose', [])):
            bad = {**self.request, name: value}
            self.expect_error('DIRECTOR_PURPOSE_UNSUPPORTED' if name == 'purpose' else 'DIRECTOR_TIME_VALUE_INVALID', bad)
        with self.assertRaises(contract.StudioContractError):
            self.normalize({'prompt': '{"schema":"x","bad":NaN}'})
        with self.assertRaises(contract.StudioContractError) as caught:
            self.normalize({'prompt': '{"schema":"x","schema":"y"}'})
        self.assertEqual(caught.exception.code, 'STUDIO_DUPLICATE_JSON_KEY')

    def test_original_plan_byte_sha_is_not_semantic_object_hash(self):
        with self.plan_file.open('a') as stream: stream.write(' ')
        self.expect_error('DIRECTOR_SOURCE_PLAN_SHA_MISMATCH')

    def test_untrusted_ref_and_changed_actual_source_ref_rejected(self):
        field = 'cameraAdmissionRef'
        self.request[field]['sha256'] = '0'*64
        self.expect_error('DIRECTOR_REFERENCE_NOT_AUTHORIZED')
        self.request[field]['sha256'] = self.trusted[self.request[field]['path']]['sha256']
        with (self.root/self.request[field]['path']).open('a') as stream: stream.write(' ')
        self.expect_error('DIRECTOR_REFERENCE_SHA_MISMATCH')

    def test_path_traversal_remote_url_and_symlink_are_rejected(self):
        field = 'cameraAdmissionRef'
        original = deepcopy(self.request[field])
        for path in ('../secret', '/etc/passwd', 'https://example.test/x', './file', 'a//b', 'a\\b'):
            self.request[field] = {**original, 'path': path}
            self.expect_error('DIRECTOR_REFERENCE_PATH_INVALID')
        link = self.root/'link.json'; link.symlink_to(original['path'])
        self.request[field] = {**original, 'path': 'link.json'}
        self.trusted['link.json'] = {**self.trusted[original['path']], 'path': 'link.json'}
        self.expect_error('DIRECTOR_REFERENCE_UNAVAILABLE')

    def test_version_mismatch_and_document_source_binding_fail(self):
        self.docs['cameraAdmissionRef']['version'] = 2; self.refresh_ref('cameraAdmissionRef')
        self.expect_error('DIRECTOR_REFERENCE_VERSION_MISMATCH')
        self.docs['cameraAdmissionRef']['version'] = 1
        self.docs['cameraAdmissionRef']['sourcePlanSHA256'] = '0'*64; self.refresh_ref('cameraAdmissionRef')
        self.expect_error('DIRECTOR_COMPONENT_SOURCE_PLAN_MISMATCH')

    def test_chapter_gaps_endpoint_mismatch_and_source_date_regression(self):
        self.docs['eventDirectorProfileRef']['chapters'][1]['startFrame'] = 4
        self.refresh_ref('eventDirectorProfileRef')
        self.expect_error('DIRECTOR_TIMELINE_GAP_OR_OVERLAP')
        self.docs['eventDirectorProfileRef']['chapters'][1]['startFrame'] = 3
        self.docs['eventDirectorProfileRef']['chapters'][1]['controlStartState'] = 'C'
        self.refresh_ref('eventDirectorProfileRef')
        self.expect_error('DIRECTOR_CHAPTER_STATE_DISCONTINUITY')
        self.docs['eventDirectorProfileRef']['chapters'][1]['controlStartState'] = 'B'
        self.docs['eventDirectorProfileRef']['sourceSchedule'][1]['sourceDate'] = '1999-12-31'
        self.refresh_ref('eventDirectorProfileRef')
        self.expect_error('DIRECTOR_SOURCE_DATE_REGRESSION')

    def test_unknown_state_is_null_and_production_blocked_not_previous_fallback(self):
        row = self.docs['eventDirectorProfileRef']['sourceSchedule'][0]
        row.update(truthKind='unknown', stateId=None, sourceIds=[], sourceDate=None)
        self.refresh_ref('eventDirectorProfileRef'); self.refresh_derivation()
        actual = self.run_request()
        self.assertFalse(actual['productionReady'])
        self.assertTrue(actual['reviewReady'])
        self.assertIsNone(actual['compilerInputs']['sourceSchedule'][0]['stateId'])
        row['stateId'] = 'A'; self.refresh_ref('eventDirectorProfileRef')
        self.expect_error('DIRECTOR_UNKNOWN_STATE_NOT_NULL')

    def test_capability_cannot_be_enabled_by_name_only_or_wrong_source(self):
        self.request['requiredCapabilities'] = ['UNKNOWN.CAP']
        self.expect_error('DIRECTOR_CAPABILITY_UNSUPPORTED')
        self.request['requiredCapabilities'] = ['CAMERA.EVENT']
        self.bindings['CAMERA.EVENT']['sha256'] = '0'*64
        self.expect_error('DIRECTOR_CAPABILITY_SOURCE_MISMATCH')

    def test_missing_owner_validation_and_missing_actual_derivation_block_review(self):
        actual = self.run_request(component_validators={})
        self.assertFalse(actual['reviewReady'])
        actual = self.run_request(derivation_bindings=None)
        self.assertFalse(actual['reviewReady'])
        self.assertIn('DIRECTOR_ACTUAL_RUNTIME_DERIVATION_UNBOUND', [x['code'] for x in actual['blockers']])

    def test_compiler_output_tampering_is_detected(self):
        with (self.root/'DERIVED.json').open('a') as stream: stream.write(' ')
        self.expect_error('DIRECTOR_DERIVATION_OUTPUT_SHA_MISMATCH')

    def test_disabled_audio_zero_gain_and_empty_cues_preserved_ui_conflicts_rejected(self):
        actual = self.normalize(self.envelope(sfx={'enabled': False, 'gain': 0.0, 'cues': []}))
        self.assertEqual(actual['sfx'], {'enabled': False, 'gain': 0, 'cues': []})
        for ui in ({'enabled': True}, {'gain': .5}, {'cues': [{'frame': 0}]}, {'gain': False}):
            with self.subTest(ui=ui), self.assertRaises(contract.StudioContractError) as caught:
                self.normalize(self.envelope(sfx=ui))
            self.assertEqual(caught.exception.code, 'DIRECTOR_SFX_UI_CONFLICT')

    def test_empty_marker_or_silent_audio_manifest_cannot_satisfy_requested_effect(self):
        for capability in ('UNITS.NATIONAL_TABLETS', 'SFX.EVENT_SYNC'):
            self.bindings[capability] = deepcopy(self.bindings['CAMERA.EVENT'])
        self.request['requiredCapabilities'] += ['UNITS.NATIONAL_TABLETS', 'SFX.EVENT_SYNC']
        actual = self.run_request()
        self.assertFalse(actual['productionReady'])
        self.assertTrue(actual['reviewReady'])
        self.assertGreaterEqual(len([x for x in actual['blockers']
            if x['code']=='DIRECTOR_REQUIRED_CAPABILITY_INPUT_MISSING']), 2)

    def test_parent_callback_remains_verbatim_for_legacy_v1_v2(self):
        for schema in ('WORLD_ENGINE_STUDIO_PROMPT_V1', 'WORLD_ENGINE_STUDIO_PROMPT_V2'):
            value = {'prompt': json.dumps({'schema': schema})}
            calls = []
            expected = {'identity': schema}
            def parent(actual, **_):
                calls.append(actual)
                return expected
            result = contract.normalize_submission(value, parent_normalize=parent)
            self.assertIs(result, expected)
            self.assertIs(calls[0], value)

    def test_explicit_runtime_callback_receives_verified_compiler_inputs(self):
        submission = self.normalize()
        calls = []
        expected = object()
        def selector(plan, inputs, manifest, documents):
            calls.append((plan, inputs, manifest, documents))
            return expected
        result = contract.select_runtime(submission, director_selector=selector,
            parent_selector=lambda _: self.fail('No legacy fallback allowed'))
        self.assertIs(result, expected)
        self.assertEqual(calls[0][0], self.source)
        self.assertEqual(calls[0][1]['schema'], 'WORLD_ENGINE_EVENT_DIRECTOR_COMPILER_INPUT_V1')
        self.assertTrue(calls[0][2]['actualDerivation']['compilerOutputsReadAndVerified'])
        with self.assertRaisesRegex(RuntimeError, 'DIRECTOR_RUNTIME_NOT_CONNECTED'):
            contract.select_runtime(submission, director_selector=None, parent_selector=lambda _: None)
        submission['eventDirector']['compilerInputs']['totalFrames'] = 7
        with self.assertRaisesRegex(RuntimeError, 'DIRECTOR_COMPILER_INPUT_CHANGED'):
            contract.select_runtime(submission, director_selector=selector, parent_selector=lambda _: None)

    def test_production_purpose_never_dispatches_free_review_or_gpu(self):
        self.request['purpose'] = 'PRODUCTION'
        submission = self.normalize()
        with self.assertRaisesRegex(RuntimeError, 'DIRECTOR_FREE_REVIEW_PREFLIGHT_BLOCKED'):
            contract.select_runtime(submission, director_selector=lambda *_: self.fail('No worker'), parent_selector=lambda _: None)

    def test_schema_is_strict_and_null_is_incomplete_not_a_fake_ref(self):
        import jsonschema
        schema = json.loads((HERE/'EVENT_DIRECTOR_REQUEST.schema.json').read_text())
        jsonschema.Draft202012Validator.check_schema(schema)
        validator = jsonschema.Draft202012Validator(schema)
        validator.validate(self.request)
        value = {**self.request, 'cameraAdmissionRef': None}
        validator.validate(value)
        self.assertTrue(list(validator.iter_errors({**self.request, 'approved': True})))


class ActualSourceAndControllerTests(unittest.TestCase):
    def test_real_p0_profile_catalog_and_original_canonical_sha(self):
        replay = json.loads((HERE/'reports/ORIGINAL_SOURCE_REPLAY.json').read_text())
        receipt_file = Path(replay['preparedPath'])
        prepared = json.loads(receipt_file.read_text())
        raw = Path(prepared['options']['planFile']).read_bytes()
        source = json.loads(raw)
        self.assertEqual(digest(raw), replay['originalPlanSHA256'])
        profile = json.loads((HERE/'fixtures/HISTORY_EVENT_PROFILE_V2.json').read_text())
        catalog = json.loads((HERE/'fixtures/HISTORY_SOURCE_CATALOG.json').read_text())
        request = {'subjectId': profile['subjectId'], 'fps': source['fps'], 'totalFrames': source['totalFrames']}
        chapters, schedule = contract._profile_semantics(profile, catalog, request)
        self.assertEqual(len(chapters), 12)
        self.assertEqual(sum(x['endFrame']-x['startFrame'] for x in schedule), 2400)
        self.assertEqual(sum(x['endFrame']-x['startFrame'] for x in schedule if x['truthKind']=='unknown'), 860)
        self.assertFalse(any(x['stateId']=='BUSAN' and x['chapterId']!='chapter-03' for x in schedule))

    def test_real_studio_constructor_and_legacy_normalizer_are_reused_no_worker(self):
        module = load('_test_astra_director_controller', HERE/'studio_controller.py')
        self.assertTrue(issubclass(module.StudioController, module.parent.StudioController))
        with tempfile.TemporaryDirectory(prefix='astra-controller-', dir='/workspace') as tmp:
            root = Path(tmp)
            instance = module.StudioController(control_root=root/'private', export_root=root/'exports',
                image_digest='sha256:'+'b'*64, backend=object())
            original_value, expected = {'prompt': 'legacy memo'}, {'legacy': True}
            from unittest.mock import patch
            with patch.object(module.parent.StudioController, '_normal', return_value=expected) as old:
                self.assertIs(instance._normal(original_value), expected)
                old.assert_called_once_with(original_value)
            for name in ('requests', 'runs', 'jobs'):
                self.assertEqual(list((instance.control_root/name).iterdir()), [])
            value = {'prompt': json.dumps({'schema': contract.SCHEMA})}
            result = instance.preflight(value)
            self.assertFalse(result['ready'])
            self.assertEqual(result['error']['code'], 'DIRECTOR_SOURCE_CONTEXT_REQUIRED')
            self.assertTrue(result['error']['issues'])


if __name__ == '__main__':
    unittest.main()
