"""Additive Studio controller; frozen auth, Scene validation and claims remain.

Only this independent entry selects V2. Original Studio stays byte unchanged.
Submissions use a new private namespace; existing jobs/claims are never reset.
No constructor, validation, GET, or reconnect can launch a render.
"""
from __future__ import annotations

from contextvars import ContextVar
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PARENT = (Path('/opt/world-engine-production-studio') if HERE.is_relative_to('/opt')
          else HERE.parent / 'production-studio-mvp-v1')


def _load(name, path, expected=None):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('STUDIO_INTEGRATION_SOURCE_SYMLINK_FORBIDDEN')
    if expected and hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError('STUDIO_INTEGRATION_PARENT_CHANGED')
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    return sys.modules[name]


sys.path.insert(0, str(PARENT))
parent = _load('_unified_preserved_studio_controller', PARENT / 'studio_controller.py',
               'c2e0d94a31cd90569d29f944da1a538c9efcf77d15cd0f2bfacbe99396ae053c')
contract = _load('_unified_contract_v2', HERE / 'contract_v2.py')
runtime = _load('_unified_backend_dispatch', HERE / 'runtime_backend.py')
StudioError = parent.StudioError


def _integrated(submission):
    return isinstance(submission, dict) and isinstance(submission.get('integration'), dict)


class StudioController(parent.StudioController):
    def __init__(self, *, control_root, export_root, image_digest, backend=None, bridge=None):
        self.legacy_control_root = Path(control_root)
        self._context = ContextVar('world_unified_submission_' + str(id(self)), default=None)
        if backend is None:
            import studio_runtime
            backend = studio_runtime
        dispatch = runtime.RuntimeBackend(backend, image_digest=image_digest, bridge=bridge)
        # A fresh Studio has no production directory yet. Validate/create only
        # this owned parent, without repairing any existing permissions/files.
        cache = parent.load_original('cache')
        with cache.PrivateTree(self.legacy_control_root, create=True):
            pass
        super().__init__(control_root=self.legacy_control_root / 'universal-integration-v1',
                         export_root=export_root, image_digest=image_digest, backend=dispatch)

    def _normal(self, value):
        return contract.normalize_submission(value, image_digest=self.image_digest,
            backend=self.backend, parent_normalize=parent.studio_contracts.normalize_submission)

    def _policy(self, root):
        # Preserve an already configured private policy. No copy, reset, or
        # promotion of untrusted mounted storage to a private control tree.
        if root.json('operator_policy.json', optional=True) is not None:
            return super()._policy(root)
        if self.legacy_control_root.is_dir():
            with self._cache.PrivateTree(self.legacy_control_root) as legacy:
                return super()._policy(legacy)
        return super()._policy(root)

    def _backend(self, name, *args, **kwargs):
        submission = self._context.get()
        if _integrated(submission):
            if name == 'preflight':
                return super()._backend('integration_preflight', submission, **kwargs)
            if name == 'start_studio_job':
                _, _, approval_path, sfx, request_id = args
                return super()._backend('integration_start', submission, approval_path, sfx, request_id, **kwargs)
            if name == 'start_studio_recovery':
                return super()._backend('integration_recover', *args, **kwargs)
        return super()._backend(name, *args, **kwargs)

    def _integration_gate(self, root, submission):
        try:
            context = self._backend('integration_context', submission, control_root=self.control_root)
            gate = _load('_unified_quality_gate', HERE / 'quality_gate.py')
            policy = self._policy(root)
            return gate.evaluate_render_gate(context, phase='FULL_VIDEO',
                operator_policy=policy, policy_validator=lambda value: self._policy(root),
                receipt_path=self.control_root / 'quality_receipts' / 'approval.json',
                trusted_receipt_root=self.control_root / 'quality_receipts')
        except Exception as error:
            return {'allowed': False, 'phase': 'FULL_VIDEO',
                    'blockers': [{'code': parent._safe_error(error)}]}

    def _preflight_record(self, root, record):
        submission = record['submission']
        if not _integrated(submission):
            # Preserve V1 input semantics, but this NEW execution profile cannot
            # use V1 to bypass the user's mandatory integrated 5s quality gate.
            return {'valid': True, 'ready': False, 'requiresGpu': True,
                    'checks': [{'name': 'INTEGRATED_PRODUCTION_PROFILE', 'status': 'BLOCKED',
                        'code': 'INTEGRATION_PROFILE_REQUIRED_BEFORE_80S'}],
                    'gpuRenderingVerified': False, 'providerBillingStopControlled': False}
        quality = self._integration_gate(root, submission)
        if quality.get('allowed') is not True:
            rows = quality.get('blockers', [])
            return {'valid': True, 'ready': False, 'requiresGpu': True,
                'checks': [{'name': 'INTEGRATION_QUALITY_GATE', 'status': 'BLOCKED',
                            'code': item.get('code', 'STUDIO_UNIFIED_GATE_BLOCKED')}
                           for item in rows if isinstance(item, dict)] or
                          [{'name': 'INTEGRATION_QUALITY_GATE', 'status': 'BLOCKED',
                            'code': 'STUDIO_UNIFIED_GATE_BLOCKED'}],
                'gpuRenderingVerified': False, 'providerBillingStopControlled': False}
        token = self._context.set(deepcopy(submission))
        try:
            result = super()._preflight_record(root, record)
            result['checks'].append({'name': 'INTEGRATION_QUALITY_GATE', 'status': 'PASS'})
            return result
        finally:
            self._context.reset(token)

    def _job_submission(self, job_id):
        with self._cache.PrivateTree(self.control_root) as root:
            job = self._job_record(root, job_id)
            return self._read_submission(root, job['submissionId'])['submission']

    def start(self, submission_id, idempotency_key, *, consent=False):
        with self._cache.PrivateTree(self.control_root) as root:
            submission = self._read_submission(root, submission_id)['submission']
        token = self._context.set(deepcopy(submission))
        try:
            return super().start(submission_id, idempotency_key, consent=consent)
        finally:
            self._context.reset(token)

    def resume(self, job_id, idempotency_key, *, consent=False):
        submission = self._job_submission(job_id)
        with self._cache.PrivateTree(self.control_root) as root:
            if not _integrated(submission) or self._integration_gate(root, submission).get('allowed') is not True:
                raise StudioError('STUDIO_UNIFIED_RECOVERY_GATE_BLOCKED')
        token = self._context.set(deepcopy(submission))
        try:
            return super().resume(job_id, idempotency_key, consent=consent)
        finally:
            self._context.reset(token)

    def revise(self, job_id, value):
        if _integrated(self._job_submission(job_id)):
            # The frozen SFX-only revision normalizer does not preserve new
            # integration metadata; do not silently downgrade its child job.
            raise StudioError('STUDIO_UNIFIED_REVISION_NOT_CONNECTED', status=422)
        return super().revise(job_id, value)
