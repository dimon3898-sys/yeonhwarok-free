"""Versioned GPU profile over unchanged Studio auth/consent/budget/claims."""
from copy import deepcopy
from pathlib import Path
import sys
import re
import subprocess
import json

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from common import PLAN, PROFILE, REQUEST, RECOVERY, canonical, duration_contract, load, mvp, sha, verify_manifest

base = mvp()


class NvidiaPresentationController(base.StudioController):
    """Only normalize a new profile; inherited start owns policy and claims.

    Its CPU source normalizer is reused without calling the FREE profile's
    submit/start/worker. A free-review preflight is never a GPU approval.
    """
    def __init__(self, *, control_root, export_root, image_digest,
                 source_manifest, expected_manifest_sha256, backend=None):
        control, exports = Path(control_root), Path(export_root)
        if (not control.is_absolute() or not exports.is_absolute()
                or '..' in control.parts or '..' in exports.parts
                or any(p.is_symlink() for p in (control, *control.parents, exports, *exports.parents))
                or control.resolve().is_relative_to(exports.resolve())
                or exports.resolve().is_relative_to(control.resolve())):
            raise base.StudioError('HANDOFF_PRIVATE_PUBLIC_ROOTS_MUST_BE_DISJOINT')
        self.source_manifest = Path(source_manifest)
        self.source_sha = expected_manifest_sha256
        verify_manifest(self.source_manifest, self.source_sha)
        if backend is None:
            from nvidia_backend import NvidiaPresentationBackend
            backend = NvidiaPresentationBackend(self.source_manifest, self.source_sha, image_digest)
        super().__init__(control_root=control_root, export_root=export_root,
                         image_digest=image_digest, backend=backend)
        self._source_normalizer = None

    def _normal(self, value):
        def invalid(code):
            raise base.studio_contracts.StudioContractError(code, code)
        if (not isinstance(value, dict) or set(value) != {'schema', 'prompt', 'sceneId'}
                or value.get('schema') != REQUEST or not isinstance(value.get('prompt'), dict)
                or not isinstance(value.get('sceneId'), str)):
            invalid('HANDOFF_EXPLICIT_NVIDIA_PRESENTATION_REQUEST_REQUIRED')
        verify_manifest(self.source_manifest, self.source_sha)
        if self._source_normalizer is None:
            module = load('_handoff_preserved_cpu_source_normalizer',
                          RECOVERY / 'universal-presentation-v2/studio_adapter.py')
            def node_profile_json(script, payload, *, timeout=90):
                raw = module.canonical(payload)
                if len(raw) > 8 * 1024**2:
                    raise module.StudioError('UP2_INPUT_SIZE_LIMIT', status=400)
                try:
                    completed = subprocess.run(['node', '--input-type=module', '-e', script], input=raw,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=timeout)
                except (OSError, subprocess.TimeoutExpired):
                    raise module.StudioError('UP2_DATA_PROCESSOR_UNAVAILABLE') from None
                if completed.returncode or len(completed.stdout) > 24 * 1024**2:
                    codes = re.findall(rb'\b(?:HANDOFF|GCUBE|UP2|REGION|PLANNER|AREA|FLOW|EVENT|CAMERA)_[A-Z0-9_]{2,100}\b', completed.stderr)
                    error = module.StudioError(codes[-1].decode() if codes else 'UP2_DATA_PROCESSOR_FAILED')
                    error._private_profile_stderr = completed.stderr[:128 * 1024]
                    raise error
                try:
                    value = json.loads(completed.stdout)
                    if not isinstance(value, dict):
                        raise ValueError()
                    return value
                except (ValueError, TypeError):
                    raise module.StudioError('UP2_DATA_PROCESSOR_RESULT_INVALID') from None
            # Same finite JSON limits and closed-code errors, with the new
            # profile's codes retained instead of being hidden as generic UP2.
            module.node_json = node_profile_json
            def prepare_profile_sources(request, cache_root):
                # Only this private module instance selects the versioned
                # source preparer. Original FREE source files/instances retain
                # their literal /workspace-only behavior and their paid gate.
                return module.node_json("import{readFileSync}from'node:fs';"
                    "const p=JSON.parse(readFileSync(0,'utf8'));"
                    "const{prepareNvidiaRuntimeRequest}=await import(p.module);"
                    "process.stdout.write(JSON.stringify(await prepareNvidiaRuntimeRequest({...p.input,request:JSON.parse(p.requestWireJSON)})));",
                    {'module': (HERE.parent / 'backend/capture_nvidia.mjs').as_uri(),
                     'requestWireJSON': json.dumps(request, ensure_ascii=False, separators=(',', ':'), allow_nan=False),
                     'input': {'cacheRoot': str(cache_root),
                        'privateWorkspaceRoot': str(self.control_root),
                        'publicExportRoot': str(self.export_root)}}, timeout=150)
            module.prepare_runtime = prepare_profile_sources
            def verify_profile_sources(prepared, admission=None, prepared_wire=None):
                # Exact existing Python aggregate and member-order checks are
                # retained; only this version's qualified cache-root transport
                # is selected for the unchanged geographic/source verifier.
                if (not isinstance(prepared, dict) or admission is not None and any(
                        prepared.get(key) != admission.get(key) for key in (
                            'sourceQualification', 'sourceQualificationSHA256', 'sourceQualificationWireJSON'))):
                    raise module.StudioError('UP2_STORED_SOURCE_AGGREGATE_CHANGED')
                wire = prepared_wire if prepared_wire is not None else json.dumps(
                    prepared, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
                try:
                    wire_matches = isinstance(wire, str) and json.loads(wire) == prepared
                except (ValueError, TypeError):
                    wire_matches = False
                if not wire_matches:
                    raise module.StudioError('UP2_STORED_SOURCE_WIRE_CHANGED')
                result = module.node_json("import{readFileSync}from'node:fs';"
                    "const p=JSON.parse(readFileSync(0,'utf8'));"
                    "const{verifyNvidiaPreparedRuntimeRequest}=await import(p.module);"
                    "process.stdout.write(JSON.stringify(await verifyNvidiaPreparedRuntimeRequest({...p.input,prepared:JSON.parse(p.preparedWireJSON)})));",
                    {'module': (HERE.parent / 'backend/capture_nvidia.mjs').as_uri(),
                     'preparedWireJSON': wire,
                     'input': {'privateWorkspaceRoot': str(self.control_root),
                        'publicExportRoot': str(self.export_root)}}, timeout=150)
                if result.get('status') != 'PASS':
                    raise module.StudioError('UP2_STORED_SOURCE_QUALIFICATION_INVALID',
                                             fields=[{'code': result.get('code')}])
                return result
            module.verify_prepared_sources = verify_profile_sources
            self._source_normalizer = module.StudioController(
                control_root=self.control_root / 'handoff-source-normalization',
                export_root=self.export_root, allow_free_data_review=True,
                allow_ten_second_sample=True)
        module = sys.modules['_handoff_preserved_cpu_source_normalizer']
        cpu = self._source_normalizer._normal({**deepcopy(value), 'schema': module.REQUEST_SCHEMA})
        pipeline = cpu['sourcePipeline']
        if (pipeline.get('simulationType') not in {'GENERAL', 'FICTIONAL'}
                or pipeline.get('totalFrames') not in {180, 300} or pipeline.get('fps') != 30
                or (pipeline.get('totalFrames') == 300 and pipeline.get('durationSeconds') != 10)
                or pipeline.get('ready') is not True
                or pipeline.get('sourceAdmission', {}).get('status') != 'PASS'):
            invalid('HANDOFF_QUALIFIED_NONHISTORICAL_180_FRAMES_REQUIRED')
        frames = pipeline['totalFrames']
        plan = {'schema': PLAN, 'totalFrames': frames, 'durationSeconds': frames // 30, 'fps': 30,
            'resolution': {'width': 1080, 'height': 1920}, 'aspectRatio': '9:16',
            'audioSettings': {'enabled': False, 'mode': 'SILENT'},
            'simulationType': pipeline['simulationType'],
            'renderProfile': {'profileId': PROFILE, 'backend': 'vulkan',
                'imageDigest': self.image_digest, 'sourceClosureSHA256': self.source_sha},
            'runtime': deepcopy(pipeline['runtimePayload']),
            'runtimeWireJSON': pipeline['runtimeRequestWireJSON'],
            'runtimeWireSHA256': pipeline['runtimeWireSHA256'],
            'sourceQualificationSHA256': pipeline['sourceAdmission']['sourceQualificationSHA256'],
            'sourceBindings': deepcopy(pipeline['sourceBindings']),
            'sourceQualification': deepcopy(pipeline['sourceAdmission']['sourceQualification']),
            'originalInputSHA256': pipeline['compilerInputSHA256']}
        duration_contract(plan)
        return {'schema': 'WORLD_ENGINE_NVIDIA_STUDIO_SUBMISSION_V1',
                'title': cpu['title'], 'profile': PROFILE, 'videoPlan': plan,
                'sfx': {'enabled': False}, 'sourceTrace': {'cpuSourceQualificationReused': True,
                    'freeProfileStartCalled': False, 'sourceInputSHA256': pipeline['compilerInputSHA256']}}

    def _preflight_record(self, root, record):
        result = super()._preflight_record(root, record)
        timing = duration_contract(record['submission']['videoPlan'])
        if timing['durationSeconds'] == 10:
            # The preserved coordinator deliberately drops backend timing facts.
            # Surface only this new sample's validated duration for owner consent.
            result.update(durationSeconds=10, totalFrames=300)
        return result

    def resume(self, *args, **kwargs):
        # No new GPU work is silently reauthorized or restarted in this bounded
        # first-review profile; failed/old claims and outputs remain untouched.
        raise base.StudioError('HANDOFF_EXPLICIT_RECOVERY_NOT_SUPPORTED')

    def revise(self, *args, **kwargs):
        raise base.StudioError('HANDOFF_REVISION_NOT_SUPPORTED')
