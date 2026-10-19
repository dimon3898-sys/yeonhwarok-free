"""Strict completion opt-in over the unchanged, source-pinned V2 contract.

Presentation metadata remains outside the frozen historical videoPlan. This
normalizer does not approve a source, authorize GPU use, or assert rendering.
Absence of ``completion`` delegates to the saved V1/V2 adapter unchanged.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from studio_contracts import StudioContractError, _bounded_json, _parse_json

HERE = Path(__file__).resolve().parent
PRIOR = HERE.parent / "universal-integration-v1"
PRIOR_CONTRACT_SHA256 = "269ce1666093cbf2f2989b7dc2620bab8d51f497cb33b3e6db4ede47e754d237"
SCHEMA = "WORLD_ENGINE_UNIVERSAL_COMPLETION_V2"
PROFILE = "VISUAL_UNIFIED_COMPLETION_V2"
PROMPT_SCHEMA = "WORLD_ENGINE_STUDIO_PROMPT_V2"
DATA_POLICY = "QUALIFIED_SOURCE_ONLY"
CAMERA_DEFAULTS = {"mode": "V5_EVENT_TRACKING", "settleFrames": 18, "holdFrames": 24}
FRONTIER_DEFAULTS = {"profile": "AUTHORED_FRONT_MOTION_V2", "enabled": True,
                     "motionResponse": True, "settledStrength": .2, "settleFrames": 18}
EVENT_FLOW_DEFAULTS = {"schema": "WORLD_ENGINE_COMPLETION_EVENT_FLOW_V1", "events": [], "flows": [], "areas": []}


def _error(code, message, *fields):
    raise StudioContractError(code, message, fields)


def _load(name, path, sha256=None):
    path = Path(path)
    if not path.is_file() or any(item.is_symlink() for item in (path, *path.parents)):
        _error("STUDIO_COMPLETION_SOURCE_UNAVAILABLE", "별도 통합 검증 모듈을 사용할 수 없습니다.")
    if sha256 and hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
        _error("STUDIO_COMPLETION_PARENT_SOURCE_CHANGED", "보호된 이전 입력 계약의 무결성이 다릅니다.")
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


def preserved_contract():
    return _load("_completion_preserved_integration_contract", PRIOR / "contract_v2.py", PRIOR_CONTRACT_SHA256)


def normalize_camera(value=None):
    if value is None:
        value = {}
    if not isinstance(value, dict) or set(value) - {"mode", "settleFrames", "holdFrames"}:
        _error("STUDIO_COMPLETION_CAMERA_FIELD_UNSUPPORTED", "지원되는 카메라 프로필 필드를 확인하세요.", "completion.camera")
    mode = value.get("mode", CAMERA_DEFAULTS["mode"])
    if mode == "PRESERVE_PARENT":
        if set(value) - {"mode"}:
            _error("STUDIO_COMPLETION_CAMERA_SETTING_CONFLICT", "기존 카메라 유지 모드에는 사용되지 않는 접근·유지 설정을 지정할 수 없습니다.", "completion.camera")
        return {"mode": mode}
    if mode != "V5_EVENT_TRACKING":
        _error("STUDIO_COMPLETION_CAMERA_MODE_UNSUPPORTED", "지원되는 카메라 모드를 선택하세요.", "completion.camera.mode")
    result = deepcopy(CAMERA_DEFAULTS)
    result.update(value)
    for name, low, high in (("settleFrames", 6, 60), ("holdFrames", 0, 120)):
        if type(result[name]) is not int or not low <= result[name] <= high:
            _error("STUDIO_COMPLETION_CAMERA_VALUE_INVALID", "카메라 프레임 설정의 정수 범위를 확인하세요.", "completion.camera." + name)
    return result


def normalize_frontier(value=None):
    if value is None:
        value = {}
    fields = set(FRONTIER_DEFAULTS)
    if not isinstance(value, dict) or set(value) - fields:
        _error("STUDIO_COMPLETION_FRONTIER_FIELD_UNSUPPORTED", "지원되는 실제 전선 설정만 지정하세요.", "completion.frontier")
    result = deepcopy(FRONTIER_DEFAULTS)
    result.update(value)
    if result["profile"] != FRONTIER_DEFAULTS["profile"]:
        _error("STUDIO_COMPLETION_FRONTIER_PROFILE_UNSUPPORTED", "자료에 있는 전선의 발광 프로필만 지원합니다.", "completion.frontier.profile")
    for name in ("enabled", "motionResponse"):
        if type(result[name]) is not bool:
            _error("STUDIO_COMPLETION_FRONTIER_VALUE_INVALID", "전선 활성화 설정은 참·거짓이어야 합니다.", "completion.frontier." + name)
    if result["enabled"] is False:
        if set(value) - {"profile", "enabled"}:
            _error("STUDIO_COMPLETION_FRONTIER_SETTING_CONFLICT", "비활성 전선에는 사용되지 않는 움직임 설정을 지정할 수 없습니다.", "completion.frontier")
        return {"profile": result["profile"], "enabled": False}
    if result["motionResponse"] is False:
        if set(value) - {"profile", "enabled", "motionResponse"}:
            _error("STUDIO_COMPLETION_FRONTIER_SETTING_CONFLICT", "움직임 반응을 끈 상태에는 안정화 설정을 지정할 수 없습니다.", "completion.frontier")
        return {"profile": result["profile"], "enabled": True, "motionResponse": False}
    strength = result["settledStrength"]
    if type(strength) not in (int, float) or not 0 <= strength <= 1:
        _error("STUDIO_COMPLETION_FRONTIER_VALUE_INVALID", "정지 후 발광 강도는 0~1이어야 합니다.", "completion.frontier.settledStrength")
    if type(result["settleFrames"]) is not int or not 1 <= result["settleFrames"] <= 120:
        _error("STUDIO_COMPLETION_FRONTIER_VALUE_INVALID", "전선 안정화는 정수 1~120프레임이어야 합니다.", "completion.frontier.settleFrames")
    return result


def _event_flow(value):
    module = _load("_completion_event_flow_contract", HERE / "event_flow_contract.py")
    try:
        return module.normalize_event_flow(value)
    except StudioContractError:
        raise
    except Exception as error:
        code = getattr(error, "code", None)
        if not isinstance(code, str) or not code or any(ch not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for ch in code):
            code = "STUDIO_COMPLETION_EVENT_FLOW_INVALID"
        _error(code, "영역·사건·이동 입력의 원본 계약과 자료 참조를 확인하세요.", "completion.eventFlow")


def normalize_completion(value):
    """Validate named profiles and canonical data bindings, never source trust."""
    _bounded_json(value)
    fields = {"schema", "profile", "dataPolicy", "camera", "frontier", "eventFlow"}
    if not isinstance(value, dict) or set(value) - fields:
        _error("STUDIO_COMPLETION_FIELD_UNSUPPORTED", "지원되지 않는 통합 설정 필드가 있습니다.", "completion")
    if value.get("schema") != SCHEMA or value.get("profile") != PROFILE:
        _error("STUDIO_COMPLETION_PROFILE_REQUIRED", "버전이 고정된 통합 프로필을 지정하세요.", "completion.schema", "completion.profile")
    if value.get("dataPolicy", DATA_POLICY) != DATA_POLICY:
        _error("STUDIO_COMPLETION_DATA_POLICY_UNSUPPORTED", "검증된 자료 범위를 유지하는 정책만 지원합니다.", "completion.dataPolicy")
    for field in ("camera", "frontier", "eventFlow"):
        if field in value and value[field] is None:
            _error("STUDIO_COMPLETION_FIELD_INVALID", "통합 설정은 JSON 객체여야 합니다.", "completion." + field)
    return {"schema": SCHEMA, "profile": PROFILE, "dataPolicy": DATA_POLICY,
            "camera": normalize_camera(value.get("camera")),
            "frontier": normalize_frontier(value.get("frontier")),
            "eventFlow": _event_flow(deepcopy(value.get("eventFlow", EVENT_FLOW_DEFAULTS)))}


def normalize_submission(value, *, image_digest, backend, parent_normalize):
    """Reuse original V1 and saved V2; completion is an explicit sibling only."""
    old = preserved_contract()
    structured = old._v2_prompt(value)
    if structured is None or "completion" not in structured:
        return old.normalize_submission(value, image_digest=image_digest, backend=backend,
                                        parent_normalize=parent_normalize)
    _bounded_json(value)
    completion = normalize_completion(structured["completion"])
    lowered = deepcopy(structured)
    lowered.pop("completion")
    outer = deepcopy(value)
    outer["prompt"] = json.dumps(lowered, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    result = old.normalize_submission(outer, image_digest=image_digest, backend=backend,
                                      parent_normalize=parent_normalize)
    if not isinstance(result, dict) or "completionV2" in result:
        _error("STUDIO_COMPLETION_PARENT_CONTRACT_INVALID", "보호된 기존 입력 검증 결과를 사용할 수 없습니다.")
    result = deepcopy(result)
    result["promptText"] = value["prompt"]
    result["completionV2"] = completion
    return result
