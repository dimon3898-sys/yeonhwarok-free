"""Authenticated completion controller over the preserved Studio/V1 managers."""
from copy import deepcopy
from pathlib import Path
import importlib.util
import sys
HERE = Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


parent = _load('_completion_v1_controller', HERE.parent / 'universal-integration-v1/studio_controller.py')
contract = _load('_completion_studio_contract', HERE / 'contract_v2.py')
bridge = _load('_completion_studio_bridge', HERE / 'runtime_bridge.py')
revision = _load('_completion_studio_revision', HERE / 'revision_bridge.py')
StudioError = parent.StudioError


class StudioController(parent.StudioController):
    def __init__(self, *, control_root, export_root, image_digest, backend=None, bridge_module=None):
        self.original_control_root = Path(control_root)
        cache = parent.parent.load_original('cache')
        with cache.PrivateTree(self.original_control_root, create=True):
            pass
        super().__init__(control_root=Path(control_root) / 'universal-integration-completion-v2',
            export_root=export_root, image_digest=image_digest, backend=backend,
            bridge=bridge if bridge_module is None else bridge_module)

    def _normal(self, value):
        return contract.normalize_submission(value, image_digest=self.image_digest,
            backend=self.backend, parent_normalize=parent.parent.studio_contracts.normalize_submission)

    def _policy(self, root):
        if root.json('operator_policy.json', optional=True) is not None:
            return parent.parent.StudioController._policy(self, root)
        # Read only the exact existing operator authority, never a shared mount.
        with self._cache.PrivateTree(self.original_control_root) as original:
            return parent.parent.StudioController._policy(self, original)

    def _backend(self, name, *args, **kwargs):
        submission = self._context.get()
        if isinstance(submission, dict) and isinstance(submission.get('completionV2'), dict):
            if name == 'start_studio_revision':
                parent_job_id, _, request_id = args
                return bridge.start_studio_revision(parent_job_id, deepcopy(submission), request_id,
                    image_digest=self.image_digest, **kwargs)
        return super()._backend(name, *args, **kwargs)

    def revise(self, job_id, value):
        if not isinstance(value, dict) or set(value) - {'startSeconds', 'endSeconds', 'prompt', 'sfx'}:
            raise StudioError('STUDIO_REVISION_REQUEST_INVALID')
        submission = self._job_submission(job_id)
        if not isinstance(submission.get('completionV2'), dict):
            return super().revise(job_id, value)
        # Check metadata invariants before the unchanged controller writes a child.
        revision.plan_revision(submission, value.get('startSeconds'), value.get('endSeconds'),
            value.get('prompt', ''), value.get('sfx'),
            parent_revision=parent.parent.studio_contracts.plan_revision)
        return parent.parent.StudioController.revise(self, job_id, value)
