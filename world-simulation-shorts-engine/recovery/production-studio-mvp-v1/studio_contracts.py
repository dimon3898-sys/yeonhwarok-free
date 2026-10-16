"""Bounded production input and honest interval revisions over existing plans.

This is a structured-input adapter, not a historical research or language model.
The backend is the only owner of protected renderer/data admission.  SFX-only
revisions keep the full video plan byte-semantically unchanged and reuse all
video scenes; visual requests require a separately validated replacement plan.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import json
import math
from pathlib import Path
import re

from studio_audio import AudioError, audio_revision_impact, normalize_sfx

HERE = Path(__file__).resolve().parent
PROFILES = {"V4_ARCHIVAL_80S", "UNIVERSAL_V3"}
DURATIONS = {80, 120, 180, 300, 600}
SCHEMA = "WORLD_ENGINE_STUDIO_SUBMISSION_V1"
MAX_PROMPT_BYTES = 4 * 1024 * 1024
HASH_DIGEST = re.compile(r"sha256:[a-f0-9]{64}\Z")


class StudioContractError(ValueError):
    def __init__(self, code, message, fields=None, status=400):
        super().__init__(message)
        self.code, self.message = code, message
        self.fields = list(fields or [])
        self.status = status


def _error(code, message, *fields):
    raise StudioContractError(code, message, fields)


def _bounded_json(value):
    """Reject non-JSON, non-finite and unbounded input without interpreting it."""
    nodes = 0
    def visit(item, depth):
        nonlocal nodes
        nodes += 1
        if nodes > 200000 or depth > 64:
            _error("STUDIO_INPUT_COMPLEXITY_LIMIT", "입력 JSON이 너무 크거나 깊습니다.", "sceneJson")
        if item is None or type(item) in (bool, int):
            return
        if type(item) is float and math.isfinite(item):
            return
        if isinstance(item, str):
            try:
                if len(item.encode("utf-8")) <= MAX_PROMPT_BYTES:
                    return
            except UnicodeEncodeError:
                _error("STUDIO_JSON_VALUE_INVALID", "올바른 UTF-8 문자열이 필요합니다.", "sceneJson")
        if isinstance(item, list):
            for child in item:
                visit(child, depth + 1)
            return
        if isinstance(item, dict) and all(isinstance(key, str) for key in item):
            for key, child in item.items():
                visit(key, depth + 1)
                visit(child, depth + 1)
            return
        _error("STUDIO_JSON_VALUE_INVALID", "유한한 JSON 값만 허용됩니다.", "sceneJson")
    visit(value, 0)
    try:
        size = len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (ValueError, TypeError, OverflowError, RecursionError):
        _error("STUDIO_JSON_VALUE_INVALID", "유효한 JSON 값을 제공하세요.", "sceneJson")
    if size > MAX_PROMPT_BYTES:
        _error("STUDIO_INPUT_SIZE_LIMIT", "입력은 4 MiB 이하여야 합니다.", "sceneJson")
    return value


def _parse_json(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_PROMPT_BYTES:
        _error("STUDIO_PROMPT_SIZE_LIMIT", "제작 프롬프트는 4 MiB 이하여야 합니다.", "prompt")
    text = text.strip()
    if text.startswith("```"):
        match = re.fullmatch(r"```(?:json)?\s*\n([\s\S]*)\n```", text)
        if not match:
            _error("STUDIO_STRUCTURED_PROMPT_REQUIRED", "JSON 또는 JSON 코드 블록 전체를 붙여넣으세요.", "prompt")
        text = match.group(1)
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _error("STUDIO_DUPLICATE_JSON_KEY", "중복 JSON 키는 허용되지 않습니다.", "prompt")
            result[key] = value
        return result
    try:
        result = json.loads(text, object_pairs_hook=pairs,
                            parse_constant=lambda _: _error("STUDIO_JSON_VALUE_INVALID", "NaN/Infinity는 허용되지 않습니다.", "prompt"))
    except StudioContractError:
        raise
    except (ValueError, TypeError, RecursionError):
        _error("STUDIO_STRUCTURED_PROMPT_REQUIRED", "자유 문장은 실행하지 않습니다. 검증된 Scene JSON이나 구조화 제작 프롬프트를 제공하세요.", "prompt", "sceneJson")
    return _bounded_json(result)


def _title(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 180 or any(ord(c) < 32 for c in value):
        _error("STUDIO_TITLE_INVALID", "영상 제목은 제어문자 없는 1~180자여야 합니다.", "title")
    return value.strip()


def _duration(value):
    if type(value) is not int or value not in DURATIONS:
        _error("STUDIO_DURATION_UNSUPPORTED", "영상 길이는 80·120·180·300·600초 중 선택하세요.", "durationSeconds")
    return value


def _profile(value):
    if not isinstance(value, str) or value not in PROFILES:
        _error("STUDIO_PROFILE_UNSUPPORTED", "지원되는 제작 프로필을 선택하세요.", "profile")
    return value


def _safe_backend(backend, name, *args):
    method = getattr(backend, name, None)
    if not callable(method):
        _error("STUDIO_BACKEND_UNAVAILABLE", "보호된 제작 검증 경로를 사용할 수 없습니다.", "profile")
    try:
        return method(*args)
    except StudioContractError:
        raise
    except Exception:
        # File paths and arbitrary upstream exceptions belong in private logs.
        _error("STUDIO_RENDER_PLAN_REJECTED", "Scene·소스·렌더 프로필 검증에 실패했습니다. 검증된 원본 Scene JSON을 확인하세요.", "sceneJson", "sourceManifest", "renderProfile")


def _preset_plan(backend):
    method = getattr(backend, "default_plan", None)
    if callable(method):
        return _safe_backend(backend, "default_plan", "V4_ARCHIVAL_80S")
    # A preserved data file only. The backend independently verifies its source
    # closure and exact V4 parent equality before admitting this plan.
    path = HERE.parent / "verified-front-data-v4-recovery/VIDEO_PLAN_80S.json"
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_PROMPT_BYTES:
            raise ValueError()
        return _parse_json(path.read_text(encoding="utf-8"))
    except StudioContractError:
        raise
    except Exception:
        _error("STUDIO_PRESET_UNAVAILABLE", "검증된 80초 데이터 프리셋이 없습니다.", "preset")


def normalize_submission(value, *, image_digest, backend):
    """Normalize an explicitly supplied plan or the frozen 80-second preset.

    Direct Scene JSON bypasses prompt interpretation. Apart from protected
    explicit image/source binding, the backend must preserve its semantics.
    """
    if not isinstance(value, dict) or set(value) - {"prompt", "sceneJson", "durationSeconds", "profile", "sfx"}:
        _error("STUDIO_SUBMISSION_INVALID", "제작 입력 필드를 확인하세요.")
    _bounded_json(value)
    if not isinstance(image_digest, str) or not HASH_DIGEST.fullmatch(image_digest):
        _error("STUDIO_IMAGE_DIGEST_REQUIRED", "검증된 고정 실행 이미지가 필요합니다.", "imageDigest")
    prompt = value.get("prompt", "")
    if not isinstance(prompt, str) or len(prompt.encode("utf-8")) > MAX_PROMPT_BYTES:
        _error("STUDIO_PROMPT_SIZE_LIMIT", "제작 프롬프트는 4 MiB 이하여야 합니다.", "prompt")
    supplied_plan = value.get("sceneJson")
    structured = {}
    if supplied_plan is None:
        if not prompt.strip():
            _error("STUDIO_SCENE_OR_PROMPT_REQUIRED", "검증된 Scene JSON 또는 구조화 제작 프롬프트를 제공하세요.", "prompt", "sceneJson")
        parsed = _parse_json(prompt)
        if not isinstance(parsed, dict):
            _error("STUDIO_STRUCTURED_PROMPT_REQUIRED", "제작 프롬프트는 JSON 객체여야 합니다.", "prompt")
        if parsed.get("schema") == "WORLD_ENGINE_STUDIO_PROMPT_V1":
            structured = parsed
            if set(parsed) - {"schema", "preset", "title", "durationSeconds", "profile", "sceneJson", "sfx"}:
                _error("STUDIO_PROMPT_FIELD_UNSUPPORTED", "지원되지 않는 제작 프롬프트 필드가 있습니다.", "prompt")
            supplied_plan = parsed.get("sceneJson")
            if parsed.get("preset"):
                if parsed["preset"] != "VERIFIED_FRONT_V4_80S" or supplied_plan is not None:
                    _error("STUDIO_PRESET_CONFLICT", "지원되는 단일 데이터 프리셋만 선택하세요.", "preset", "sceneJson")
                supplied_plan = _preset_plan(backend)
                if parsed.get("profile", "V4_ARCHIVAL_80S") != "V4_ARCHIVAL_80S":
                    _error("STUDIO_PRESET_PROFILE_CONFLICT", "자료 프리셋은 V4 역사 전선 프로필만 지원합니다.", "profile")
        else:
            supplied_plan = parsed
    if not isinstance(supplied_plan, dict):
        _error("STUDIO_SCENE_REQUIRED", "Scene JSON 또는 VERIFIED_FRONT_V4_80S 프리셋이 필요합니다.", "sceneJson", "preset")
    profile = _profile(value.get("profile", structured.get("profile", "V4_ARCHIVAL_80S")))
    if "profile" in structured and structured["profile"] != profile:
        _error("STUDIO_PROFILE_CONFLICT", "화면 선택과 제작 프롬프트 프로필이 다릅니다.", "profile")
    duration = _duration(value.get("durationSeconds", structured.get("durationSeconds", supplied_plan.get("durationSeconds"))))
    if structured.get("durationSeconds", duration) != duration or supplied_plan.get("durationSeconds") != duration:
        _error("STUDIO_DURATION_CONFLICT", "선택한 길이와 검증된 Scene 길이가 다릅니다. 역사 데이터를 자동 늘이지 않습니다.", "durationSeconds", "sceneJson.durationSeconds")
    if profile == "V4_ARCHIVAL_80S" and duration != 80:
        _error("STUDIO_ARCHIVAL_PRESET_80S_ONLY", "V4 역사 자료 프리셋은 80초입니다. 다른 길이는 해당 길이의 검증된 V3 Scene JSON이 필요합니다.", "durationSeconds", "profile")
    plan = _safe_backend(backend, "bind_render_image", deepcopy(supplied_plan), profile, image_digest)
    if not isinstance(plan, dict):
        _error("STUDIO_RENDER_PLAN_REJECTED", "렌더 실행 계획이 생성되지 않았습니다.", "sceneJson")
    _safe_backend(backend, "validate_render_plan", plan, profile, image_digest)
    if (plan.get("durationSeconds") != duration or plan.get("fps") != 30
            or plan.get("totalFrames") != duration * 30
            or plan.get("resolution") != {"width": 1080, "height": 1920}
            or plan.get("aspectRatio") != "9:16"):
        _error("STUDIO_OUTPUT_SPEC_CONFLICT", "이번 제작 프로필은 1080×1920·30fps·9:16 규격만 지원합니다.", "sceneJson")
    _bounded_json(plan)
    title = structured.get("title")
    if title is None:
        titles = plan.get("titleCandidates")
        title = titles[0] if isinstance(titles, list) and titles else plan.get("topic")
    settings = value["sfx"] if "sfx" in value else structured.get("sfx")
    try:
        audio = normalize_sfx(settings, plan)
    except AudioError:
        _error("STUDIO_SFX_INVALID", "효과음의 이벤트 ID·프레임·종류·음량을 확인하세요.", "sfx")
    return {"schema": SCHEMA, "title": _title(title), "profile": profile,
            "durationSeconds": duration, "videoPlan": deepcopy(plan),
            "sfx": audio, "promptText": prompt}


def _time_frame(value, fps, maximum, field):
    if type(value) not in (int, float, str):
        _error("STUDIO_REVISION_TIME_INVALID", "수정 구간은 프레임 경계의 초 단위여야 합니다.", field)
    try:
        parsed = Decimal(str(value))
        exact = parsed * fps
        if not parsed.is_finite() or not 0 <= exact <= maximum or exact != exact.to_integral_value():
            raise ValueError()
        return int(exact)
    except (InvalidOperation, ValueError, OverflowError):
        _error("STUDIO_REVISION_TIME_INVALID", "수정 구간은 영상 안의 정확한 프레임 경계여야 합니다.", field)


def _revision_command(prompt, sfx):
    if not isinstance(prompt, str):
        _error("STUDIO_REVISION_PROMPT_REQUIRED", "수정 프롬프트는 문자열이어야 합니다.", "prompt")
    if sfx is not None:
        if prompt and prompt.strip() and not re.fullmatch(r"(?i)\s*(sfx|효과음)(?:\s*(?:만|only))?\s*", prompt):
            _error("STUDIO_REVISION_REQUEST_CONFLICT", "효과음 설정과 함께 다른 변경을 요청할 수 없습니다.", "prompt", "sfx")
        return deepcopy(sfx)
    if not isinstance(prompt, str) or not prompt.strip():
        _error("STUDIO_REVISION_PROMPT_REQUIRED", "수정 프롬프트 또는 효과음 설정이 필요합니다.", "prompt")
    clean = prompt.strip()
    if clean.startswith(("{", "```")):
        command = _parse_json(clean)
        if (not isinstance(command, dict) or set(command) != {"schema", "sfx"}
                or command.get("schema") != "WORLD_ENGINE_STUDIO_REVISION_V1"):
            _error("STUDIO_REVISION_COMMAND_INVALID", "수정 JSON은 schema와 sfx만 지원합니다.", "prompt")
        return command["sfx"]
    if re.fullmatch(r"(?i)\s*(?:sfx\s*(?:off|mute)|효과음\s*(?:끄기|꺼줘|꺼|제거))\s*[.!]?", clean):
        return {"enabled": False}
    if re.fullmatch(r"(?i)\s*(?:sfx\s*on|효과음\s*(?:켜기|켜줘|켜))\s*[.!]?", clean):
        return {"enabled": True}
    match = re.fullmatch(r"(?i)(?:sfx\s*(?:volume|gain)|효과음\s*음량)\s*(\d{1,3}(?:\.\d+)?)\s*%?", clean)
    if match:
        return {"gain": float(match.group(1)) / 100}
    raise StudioContractError("STUDIO_VISUAL_REVISION_UNSUPPORTED",
        "이 MVP의 시간 구간 수정은 효과음 ON/OFF·음량·검증된 이벤트 큐를 지원합니다. 카메라·영토·전선 수정은 새로 검증된 Scene JSON으로 새 제작을 요청하세요. 자유 문장으로 보호된 카메라를 임의 변경하지 않습니다.",
        ["sfx.enabled", "sfx.gain", "sfx.cues"], 422)


def plan_revision(parent_submission, startSeconds, endSeconds, prompt, sfx=None):
    """A new SFX revision with [start,end) exact frame semantics, no GPU edits.

    A cue belongs to the interval by its event frame; a short sound already
    started before the interval is retained. Changed cue tails and bounded
    neighboring authored-cue admission effects may extend beyond the requested
    interval; all such audio support is reported, including adjacent scenes.
    Revisions never move a cue, alter event data, or modify the parent object.
    """
    _bounded_json(parent_submission)
    if not isinstance(parent_submission, dict) or parent_submission.get("schema") != SCHEMA:
        _error("STUDIO_REVISION_PARENT_INVALID", "검증된 기존 제작 결과가 필요합니다.")
    plan = parent_submission.get("videoPlan")
    if not isinstance(plan, dict) or type(plan.get("fps")) is not int or type(plan.get("totalFrames")) is not int:
        _error("STUDIO_REVISION_PARENT_INVALID", "기존 영상 시간축이 올바르지 않습니다.")
    start = _time_frame(startSeconds, plan["fps"], plan["totalFrames"], "startSeconds")
    end = _time_frame(endSeconds, plan["fps"], plan["totalFrames"], "endSeconds")
    if end <= start:
        _error("STUDIO_REVISION_RANGE_EMPTY", "수정 종료 시간은 시작 시간보다 커야 합니다.", "startSeconds", "endSeconds")
    settings = _revision_command(prompt, sfx)
    if not isinstance(settings, dict) or set(settings) - {"enabled", "gain", "cues"} or not settings:
        _error("STUDIO_REVISION_SFX_INVALID", "구간 효과음은 enabled·gain·cues만 지원합니다.", "sfx")
    try:
        old = normalize_sfx(parent_submission.get("sfx"), plan)
        # Represent global gain/toggle as per-cue gains in the revised timeline,
        # preserving every cue outside the requested half-open interval.
        cues = []
        for cue in old["cues"]:
            item = deepcopy(cue)
            item["gain"] *= old["gain"] if old["enabled"] else 0.
            cues.append(item)
        if "cues" in settings:
            replacement = normalize_sfx({"enabled": True, "gain": 1., "cues": settings["cues"]}, plan)["cues"]
            if any(not start <= c["frame"] < end for c in replacement):
                _error("STUDIO_REVISION_CUE_OUTSIDE_RANGE", "새 효과음 큐는 선택 구간 안에 있어야 합니다.", "sfx.cues")
            cues = [c for c in cues if not start <= c["frame"] < end] + replacement
        enabled = settings.get("enabled", True)
        if type(enabled) is not bool:
            raise AudioError("SFX_TOGGLE_INVALID")
        gain = settings.get("gain")
        if "gain" in settings and (type(gain) not in (float, int) or not math.isfinite(gain) or not 0 <= gain <= 1):
            raise AudioError("SFX_GAIN_INVALID")
        for cue in cues:
            if start <= cue["frame"] < end:
                if enabled is False:
                    cue["gain"] = 0.
                elif gain is not None:
                    cue["gain"] = gain
                elif settings.get("enabled") is True and cue["gain"] == 0:
                    cue["gain"] = old["gain"]
        revised_audio = normalize_sfx({"enabled": True, "gain": 1., "exportWav": old["exportWav"], "cues": cues}, plan)
    except AudioError:
        _error("STUDIO_REVISION_SFX_INVALID", "구간 효과음 이벤트·프레임·음량 설정이 잘못되었습니다.", "sfx")
    scenes = plan.get("scenes")
    if not isinstance(scenes, list) or any(not isinstance(s, dict) or not isinstance(s.get("sceneId"), str)
            or type(s.get("startFrame")) is not int or type(s.get("endFrame")) is not int for s in scenes):
        _error("STUDIO_REVISION_PARENT_INVALID", "검증된 장면 분할 계획이 필요합니다.")
    affected = [s["sceneId"] for s in scenes if s["startFrame"] < end and start < s["endFrame"]]
    try:
        audio_impact = audio_revision_impact(old, revised_audio, plan)
    except AudioError:
        _error("STUDIO_REVISION_AUDIO_IMPACT_INVALID", "효과음 수정 영향 구간을 검증하지 못했습니다.", "sfx")
    sample_rate = audio_impact["sampleRate"]
    changed_intervals = audio_impact["changedSampleIntervals"]
    def intersects_audio(scene):
        # The supported Studio output is 30 fps / 48 kHz: every global frame
        # boundary is exactly representable on this sample grid.
        left = scene["startFrame"] * sample_rate // plan["fps"]
        right = scene["endFrame"] * sample_rate // plan["fps"]
        return any(a < right and left < b for a, b in changed_intervals)
    audio_affected = [s["sceneId"] for s in scenes if intersects_audio(s)]
    adjacent = [scene_id for scene_id in audio_affected if scene_id not in affected]
    result = deepcopy(parent_submission)
    result["sfx"] = revised_audio
    return {"submission": result, "impact": {"requestedFrames": [start, end],
            "affectedSceneIds": affected, "adjacentSceneIds": adjacent, "invalidatedSceneIds": [],
            "audioAffectedSceneIds": audio_affected, "audioImpact": audio_impact,
            "audioRequestedSamples": [start * sample_rate // plan["fps"], end * sample_rate // plan["fps"]],
            "audioChangedSampleIntervals": changed_intervals,
            "reusedSceneIds": [s["sceneId"] for s in scenes], "requiresGpu": False,
            "scope": "SFX_ONLY_RECOMPOSE", "reason": "VIDEO_PLAN_UNCHANGED_ALL_VERIFIED_VIDEO_SCENES_REUSABLE",
            "audioIntervalPolicy": "CUE_ONSET_EDIT_WITH_REPORTED_TAIL_AND_LOCAL_ADMISSION_IMPACT",
            "gpuPartialRevisionVerified": False}}
