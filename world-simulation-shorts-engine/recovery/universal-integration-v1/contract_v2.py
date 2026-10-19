"""Strict, opt-in presentation metadata over the preserved Studio V1 contract.

The existing normalizer/backend remain the owners of the frozen Scene, source
binding, audio validation and output specification. This module neither admits
a render nor changes historical geometry. V1 submissions are delegated verbatim.
The separate integration runtime must explicitly consume the sibling metadata;
an older Studio/image cannot execute this contract.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math

from studio_contracts import StudioContractError, _bounded_json, _parse_json

PROMPT_SCHEMA = "WORLD_ENGINE_STUDIO_PROMPT_V2"
INTEGRATION_SCHEMA = "WORLD_ENGINE_UNIVERSAL_INTEGRATION_V1"
INTEGRATION_PROFILE = "VISUAL_UNIFIED_V1"
PRESET = "VERIFIED_FRONT_V4_80S"
PROFILE = "V4_ARCHIVAL_80S"
VISUAL_DEFAULTS = {
    "territoryOpacity": .62,
    "frontCoreWidthPixels": 4.8,
    "frontGlowRadiusPixels": 10,
    "frontGlowGain": .42,
    "cameraApproachFrames": 48,
}
VISUAL_LIMITS = {
    "territoryOpacity": (.24, .8),
    "frontCoreWidthPixels": (2.5, 7),
    "frontGlowRadiusPixels": (3, 16),
    "frontGlowGain": (.1, .65),
    "cameraApproachFrames": (12, 120),
}
_OUTER_FIELDS = {"prompt", "sceneJson", "durationSeconds", "profile", "sfx"}
_INNER_FIELDS = {"schema", "preset", "title", "durationSeconds", "profile", "sfx", "visualProfile"}


def _error(code, message, *fields):
    raise StudioContractError(code, message, fields)


def normalize_visual_profile(value=None):
    """Validate only the five knobs consumed by this versioned runtime."""
    if value is None:
        value = {}
    if not isinstance(value, dict) or set(value) - set(VISUAL_DEFAULTS):
        _error("STUDIO_V2_VISUAL_FIELD_UNSUPPORTED", "시각 설정은 지원되는 다섯 항목만 지정하세요.", "visualProfile")
    result = deepcopy(VISUAL_DEFAULTS)
    for name, number in value.items():
        low, high = VISUAL_LIMITS[name]
        if (type(number) not in (int, float) or (type(number) is float and not math.isfinite(number))
                or not low <= number <= high
                or (name == "cameraApproachFrames" and type(number) is not int)):
            _error("STUDIO_V2_VISUAL_VALUE_INVALID", "시각 설정의 자료형과 허용 범위를 확인하세요.", "visualProfile." + name)
        result[name] = number
    return result


def _v2_prompt(value):
    """Inspect valid JSON only; leave every non-V2 failure to the old parser."""
    if not isinstance(value, dict) or not isinstance(value.get("prompt"), str):
        return None
    try:
        parsed = _parse_json(value["prompt"])
    except StudioContractError:
        return None
    return parsed if isinstance(parsed, dict) and parsed.get("schema") == PROMPT_SCHEMA else None


def normalize_submission(value, *, image_digest, backend, parent_normalize):
    """Delegate V1 unchanged or add explicit integration metadata to V2.

    ``parent_normalize`` must be the preserved V1 normalizer, with the original
    backend. Its bound/validated ``videoPlan`` is returned without any edits.
    The Studio extension binds source hashes and chooses the independent runtime
    after this input-only step. This function is not a GPU approval gate.
    """
    structured = _v2_prompt(value)
    if structured is None:
        return parent_normalize(value, image_digest=image_digest, backend=backend)
    _bounded_json(value)
    if set(value) - _OUTER_FIELDS:
        _error("STUDIO_SUBMISSION_INVALID", "제작 입력 필드를 확인하세요.")
    if set(structured) - _INNER_FIELDS:
        _error("STUDIO_PROMPT_FIELD_UNSUPPORTED", "지원되지 않는 V2 제작 프롬프트 필드가 있습니다.", "prompt")
    # A direct Scene bypass must never discard the explicitly selected V2 path.
    if value.get("sceneJson") is not None:
        _error("STUDIO_V2_SCENE_CONFLICT", "V2는 보호된 자료 프리셋을 사용합니다. Scene 첨부와 함께 지정할 수 없습니다.", "sceneJson", "preset")
    if structured.get("preset") != PRESET:
        _error("STUDIO_V2_PRESET_REQUIRED", "현재 V2 경로는 검증된 V4 80초 자료 프리셋을 사용합니다.", "preset")
    if structured.get("profile", PROFILE) != PROFILE or value.get("profile", PROFILE) != PROFILE:
        _error("STUDIO_V2_PROFILE_CONFLICT", "V2 시각 경로는 V4 역사 전선 자료 프로필과 연결됩니다.", "profile")
    duration = structured.get("durationSeconds")
    if type(duration) is not int or duration != 80:
        _error("STUDIO_V2_DURATION_80_REQUIRED", "V2 보호 프리셋은 정수 durationSeconds: 80이 필요합니다.", "durationSeconds")
    if "durationSeconds" in value and (type(value["durationSeconds"]) is not int or value["durationSeconds"] != duration):
        _error("STUDIO_DURATION_CONFLICT", "화면 선택과 V2 프롬프트 길이가 다릅니다.", "durationSeconds")
    if "sfx" in value and "sfx" in structured and value["sfx"] != structured["sfx"]:
        _error("STUDIO_V2_SFX_CONFLICT", "화면과 프롬프트의 효과음 설정이 다릅니다. 한 곳에서만 지정하세요.", "sfx")
    if "visualProfile" in structured and structured["visualProfile"] is None:
        _error("STUDIO_V2_VISUAL_FIELD_UNSUPPORTED", "시각 설정은 JSON 객체여야 합니다.", "visualProfile")
    visual = normalize_visual_profile(structured.get("visualProfile"))
    lowered = {key: deepcopy(child) for key, child in structured.items() if key != "visualProfile"}
    lowered["schema"] = "WORLD_ENGINE_STUDIO_PROMPT_V1"
    outer = deepcopy(value)
    outer["prompt"] = json.dumps(lowered, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    result = parent_normalize(outer, image_digest=image_digest, backend=backend)
    if not isinstance(result, dict) or "integration" in result:
        _error("STUDIO_V2_PARENT_CONTRACT_INVALID", "보호된 기존 입력 검증 결과를 사용할 수 없습니다.")
    result = deepcopy(result)
    result["promptText"] = value["prompt"]
    result["integration"] = {"schema": INTEGRATION_SCHEMA, "profile": INTEGRATION_PROFILE,
                             "visualProfile": visual}
    return result
