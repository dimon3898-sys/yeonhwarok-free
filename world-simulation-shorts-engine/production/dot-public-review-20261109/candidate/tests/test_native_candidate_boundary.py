"""Focused routing units only. No renderer, source admission, browser, or GPU run.

Load the actual changed method ASTs with compiler/I/O seams stubbed. This checks
protocol routing and rejection, not deployment or full Studio integration.
"""
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
UP = ROOT / 'recovery/universal-presentation-v2/studio_adapter.py'
NV = ROOT / 'recovery/codex-to-gcube-handoff-v1/controller/nvidia_controller.py'
NATIVE = 'WORLD_ENGINE_PRESENTATION_SOURCES_V2'
TIMELINE = 'WORLD_ENGINE_PRESENTATION_TIMELINE_SOURCES_V1'
REGISTRY_ENV = ('WORLD_ENGINE_OFFICIAL_CANDIDATE_REGISTRY_FILE', 'WORLD_ENGINE_OFFICIAL_CANDIDATE_REGISTRY_SHA256')

class ContractError(Exception):
    def __init__(self, code, *args, **kwargs):
        self.code = code
        super().__init__(code)

def canonical(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()

def sha(v):
    return hashlib.sha256(v).hexdigest()

def load_class(path, class_name, method_names, namespace):
    source = ast.parse(path.read_text())
    original = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    methods = [deepcopy(n) for n in original.body if isinstance(n, ast.FunctionDef) and n.name in method_names]
    node = ast.ClassDef(name=class_name, bases=[], keywords=[], body=methods, decorator_list=[])
    tree = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
    exec(compile(tree, str(path), 'exec'), namespace)
    return namespace[class_name]

def receipt(frames, timeline=False):
    q = {'schema': TIMELINE if timeline else NATIVE, 'totalFrames': frames}
    wire = json.dumps(q, separators=(',', ':'))
    r = {'status': 'PASS', 'sourceQualification': q, 'sourceQualificationWireJSON': wire,
         'sourceQualificationSHA256': sha(wire.encode())}
    if timeline:
        r.update(candidateSourceAdmitted=False, chunkPlan={'chunks': [0, 1]})
    return r

def source_controller(frames=300, candidate=False):
    calls = []
    rows = [{'sceneId': 's1', 'startFrame': 0, 'endFrame': frames,
             'scene': {'metadata': {'schema': 'PLANNER_SCENE_JSON_V1',
                       'output': {'width': 1080, 'height': 1920, 'fps': 30, 'audio': False}},
                       'timing': {'total_frames': frames}}}]
    namespace = dict(json=json, deepcopy=deepcopy, sha=sha, canonical=canonical,
        StudioError=ContractError, REQUEST_SCHEMA='REQUEST', SCHEMA='SUBMISSION', PROFILE='CPU', HERE=UP.parent,
        compile_prompt=lambda *a, **k: {'simulationType': 'GENERAL', 'inputSHA256': 'a'*64},
        selected_segments=lambda *a, **k: (rows, frames, []), runtime_segment=deepcopy,
        source_bindings=lambda **k: [{'timeline': k.get('timeline', False)}],
        node_json=lambda *a, **k: calls.append('wire') or ['chunk-wire'])
    C = load_class(UP, 'StudioController', {'_normal', '_verify_qualification', '_admit_timeline_sources'}, namespace)
    c = C(); c.allow_ten_second_sample = True; c.allow_candidate_timeline = candidate; c.registry_pin = None
    c._registry = lambda: {}
    c._admit_sources = lambda *a: calls.append('native') or receipt(frames)
    c._admit_timeline_sources = lambda *a: calls.append('timeline') or receipt(frames, True)
    c._seal_candidate_activation = lambda *a: calls.append('seal') or {'sealed': True}
    c._verify_candidate_activation = lambda a: calls.append('verify-activation') or a
    return c, calls, C

REQUEST = {'schema': 'REQUEST', 'prompt': {'prompt': 'fixture'}, 'sceneId': '__timeline__'}

def native_pipeline():
    c, _, _ = source_controller()
    return c._normal(deepcopy(REQUEST))['sourcePipeline']

def nvidia_controller(*, capable=True, pipeline=None):
    calls = []; received = []
    pipeline = deepcopy(pipeline or native_pipeline())
    class Source:
        def __init__(self, *, control_root, export_root, allow_free_data_review, allow_ten_second_sample, **kwargs):
            if not capable and kwargs:
                raise TypeError('legacy constructor received new options')
            received.append(kwargs)
        def _normal(self, value):
            return {'sourcePipeline': deepcopy(pipeline), 'title': 'fixture'}
    module = SimpleNamespace(StudioController=Source, REQUEST_SCHEMA='REQUEST', StudioError=ContractError)
    if capable:
        module.CANDIDATE_TIMELINE_SERVER_OPTION = True
    namespace = dict(deepcopy=deepcopy, json=json, os=os, re=__import__('re'), subprocess=__import__('subprocess'),
        sys=SimpleNamespace(modules={'_handoff_preserved_cpu_source_normalizer': module}),
        base=SimpleNamespace(studio_contracts=SimpleNamespace(StudioContractError=ContractError)),
        REQUEST='NVIDIA_REQUEST', PLAN='NVIDIA_PLAN', PROFILE='NVIDIA', RECOVERY=ROOT/'recovery', HERE=NV.parent,
        verify_manifest=lambda *a: calls.append('manifest'), load=lambda *a: module,
        _normal_with_up2_diagnostic=lambda fn, value: fn(value), duration_contract=lambda p: calls.append('duration'))
    C = load_class(NV, 'NvidiaPresentationController', {'_normal'}, namespace)
    c = C(); c._source_normalizer = None; c.source_manifest = '/fixture'; c.source_sha = 'b'*64
    c.control_root = Path('/private-fixture'); c.export_root = Path('/export-fixture'); c.image_digest = 'sha256:'+'c'*64
    return c, received, calls

NVIDIA_REQUEST = {**REQUEST, 'schema': 'NVIDIA_REQUEST'}

class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {k: '' for k in REGISTRY_ENV})
        self.environment.start()
    def tearDown(self):
        self.environment.stop()
    def test_native_300_keeps_source_preparer(self):
        c, calls, _ = source_controller()
        p = c._normal(deepcopy(REQUEST))['sourcePipeline']
        self.assertEqual(calls, ['native'])
        self.assertEqual(p['sourceAdmission']['sourceQualification']['schema'], NATIVE)
        self.assertEqual(p['durationSeconds'], 10)
        self.assertNotIn('candidateActivation', p)
        c._verify_qualification(p['sourceAdmission'], 300)
    def test_candidate_300_retains_sealed_chunks(self):
        c, calls, _ = source_controller(candidate=True)
        p = c._normal(deepcopy(REQUEST))['sourcePipeline']
        self.assertEqual(calls, ['timeline', 'seal', 'wire'])
        self.assertEqual(p['candidateActivation'], {'sealed': True})
        self.assertEqual(p['sourceAdmission']['chunkCaptureWires'], ['chunk-wire'])
        c._verify_qualification(p['sourceAdmission'], 300)
    def test_native_180_route_remains_native(self):
        c, calls, _ = source_controller(frames=180, candidate=True)
        p = c._normal(deepcopy(REQUEST))['sourcePipeline']
        self.assertEqual(calls, ['native'])
        c._verify_qualification(p['sourceAdmission'], 180)
    def test_request_cannot_select_server_mode(self):
        c, _, _ = source_controller()
        with self.assertRaises(ContractError):
            c._normal({**REQUEST, 'allow_candidate_timeline': True})
    def test_sealed_candidate_cannot_cross_native_mode(self):
        c, calls, _ = source_controller()
        with self.assertRaises(ContractError) as caught:
            c._normal(REQUEST, preserve_candidate_activation=True, sealed_candidate_activation={'sealed': True})
        self.assertEqual(caught.exception.code, 'UP2_CANDIDATE_TIMELINE_SERVER_SCOPE_REQUIRED')
        self.assertEqual(calls, [])
    def test_native_rejects_timeline_qualification(self):
        c, _, _ = source_controller()
        with self.assertRaises(ContractError): c._verify_qualification(receipt(300, True), 300)
    def test_candidate_rejects_native_qualification(self):
        c, _, _ = source_controller(candidate=True)
        with self.assertRaises(ContractError): c._verify_qualification(receipt(300), 300)
    def test_qualification_tampering_stays_rejected(self):
        for mode in (False, True):
            with self.subTest(candidate=mode):
                c, _, _ = source_controller(candidate=mode)
                r = receipt(300, mode); r['sourceQualification']['totalFrames'] = 299
                with self.assertRaises(ContractError): c._verify_qualification(r, 300)
    def test_timeline_admission_disabled_before_io(self):
        c, _, C = source_controller()
        with self.assertRaises(ContractError) as caught:
            C._admit_timeline_sources(c, {'totalFrames': 300, 'durationSeconds': 10}, [])
        self.assertEqual(caught.exception.code, 'UP2_TIMELINE_SERVER_SCOPE_REQUIRED')
    def test_nvidia_new_adapter_explicitly_selects_native(self):
        c, received, calls = nvidia_controller()
        r = c._normal(deepcopy(NVIDIA_REQUEST))
        self.assertEqual(received, [{'allow_candidate_timeline': False}])
        self.assertEqual(r['videoPlan']['totalFrames'], 300)
        self.assertEqual(r['videoPlan']['sourceQualification']['schema'], NATIVE)
        self.assertEqual(calls, ['manifest', 'duration'])
    def test_nvidia_legacy_constructor_unchanged(self):
        c, received, _ = nvidia_controller(capable=False)
        c._normal(deepcopy(NVIDIA_REQUEST))
        self.assertEqual(received, [{}])
    def test_configured_candidate_blocks_before_source_processing(self):
        for key in REGISTRY_ENV:
            with self.subTest(key=key), patch.dict(os.environ, {key: 'fixture'}):
                c, received, calls = nvidia_controller()
                with self.assertRaises(ContractError) as caught: c._normal(NVIDIA_REQUEST)
                self.assertEqual(caught.exception.code, 'HANDOFF_CANDIDATE_NVIDIA_BRIDGE_REQUIRED')
                self.assertEqual(calls, []); self.assertEqual(received, [])
    def test_nvidia_never_silently_discards_candidate_authority(self):
        for variant in ('activation', 'activationHash', 'chunkPlan', 'chunkWires', 'timeline'):
            with self.subTest(variant=variant):
                p = native_pipeline()
                if variant == 'activation': p['candidateActivation'] = None
                elif variant == 'activationHash': p['candidateActivationSHA256'] = 'd'*64
                elif variant == 'chunkPlan': p['sourceAdmission']['chunkPlan'] = {}
                elif variant == 'chunkWires': p['sourceAdmission']['chunkCaptureWires'] = []
                else: p['sourceAdmission']['sourceQualification']['schema'] = TIMELINE
                c, _, calls = nvidia_controller(pipeline=p)
                with self.assertRaises(ContractError) as caught: c._normal(NVIDIA_REQUEST)
                self.assertEqual(caught.exception.code, 'HANDOFF_CANDIDATE_NVIDIA_BRIDGE_REQUIRED')
                self.assertNotIn('duration', calls)

if __name__ == '__main__':
    unittest.main(verbosity=2)
