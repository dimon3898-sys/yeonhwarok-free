"""Independent authenticated Studio controller selector, no GPU worker added.

The inherited HTTPS/login/Origin/CSRF service may inject this controller through
its existing controller_factory. This module is not proof of deployed support.
"""
from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent


def _load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


parent = _load("_astra_director_preserved_studio_controller",
               HERE.parent / "universal-integration-completion-v2/studio_controller.py")
contract = _load("_astra_director_studio_contract", HERE / "director_contract.py")
StudioError = parent.StudioError


class StudioController(parent.StudioController):
    def __init__(self, *, director_context=None, **kwargs):
        # Caller-owned immutable source context; never accept it from HTTP body.
        self.director_context = dict(director_context or {})
        self.director_operator_root = Path(kwargs["control_root"])
        cache = parent.parent.parent.load_original('cache')
        with cache.PrivateTree(self.director_operator_root, create=True):
            pass
        kwargs["control_root"] = Path(kwargs["control_root"]) / "astra-event-director-v2"
        super().__init__(**kwargs)

    def _policy(self, root):
        if root.json('operator_policy.json', optional=True) is not None:
            return super()._policy(root)
        with self._cache.PrivateTree(self.director_operator_root) as original:
            return super()._policy(original)

    def _normal(self, value):
        preserved = super()._normal
        def normalize_parent(item, **_):
            return preserved(item)
        return contract.normalize_submission(value, parent_normalize=normalize_parent,
            image_digest=self.image_digest, backend=self.backend, **self.director_context)

    def _preflight_record(self, root, record):
        director = record["submission"].get("eventDirector")
        if not isinstance(director, dict):
            return super()._preflight_record(root, record)
        checks = [{"name": "EVENT_DIRECTOR_DATA", "status": "BLOCKED", "code": row["code"]}
                  for row in director["blockers"]]
        checks.append({"name": "EVENT_DIRECTOR_FREE_INPUT", "status": "PASS"})
        # CPU preview selection never approves paid production or a full movie.
        checks.append({"name": "FULL_VIDEO_APPROVAL", "status": "BLOCKED",
                       "code": "DIRECTOR_NVIDIA_IMAGE_AND_USER_REVIEW_REQUIRED"})
        try:
            self._policy(root)
            checks.append({"name": "OWNER_BUDGET_POLICY", "status": "PASS"})
        except Exception as error:
            checks.append({"name": "OWNER_BUDGET_POLICY", "status": "BLOCKED",
                           "code": getattr(error, "code", "STUDIO_OPERATOR_POLICY_REQUIRED")})
        return {"valid": True, "ready": False, "requiresGpu": True,
                "checks": checks, "reviewReady": director["reviewReady"],
                "requiredCapabilitiesRemoved": False, "renderAllowed": False,
                "gpuRenderingVerified": False, "providerBillingStopControlled": False}

    def preflight(self, value):
        try:
            submission = self._normal(value)
        except contract.StudioContractError as error:
            return {"valid": False, "ready": False, "renderAllowed": False,
                    "error": {"code": error.code, "fields": error.fields,
                              "issues": deepcopy(getattr(error, "issues", []))}}
        with self._cache.PrivateTree(self.control_root) as root:
            return self._preflight_record(root, {"submission": submission, "lineage": None})

    def validate_director(self, value):
        """Authenticated caller's CPU validation details, never a render API."""
        try:
            submission = self._normal(value)
        except contract.StudioContractError as error:
            return {"valid": False, "ready": False, "renderAllowed": False,
                    "error": {"code": error.code, "fields": error.fields,
                              "issues": deepcopy(getattr(error, "issues", []))}}
        director = submission.get("eventDirector")
        return {"valid": True, "ready": False, "renderAllowed": False,
                "directorSelected": isinstance(director, dict),
                "reviewReady": bool(director and director["reviewReady"]),
                "blockers": deepcopy(director["blockers"]) if director else [],
                "runtimeBindingManifest": deepcopy(director["runtimeBindingManifest"]) if director else None}

    def select_review_runtime(self, submission, *, director_selector, parent_selector):
        return contract.select_runtime(submission, director_selector=director_selector,
                                       parent_selector=parent_selector)
