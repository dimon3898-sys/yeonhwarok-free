"""Preserve completion identity through the existing SFX-only revision engine.

No visual edits, GPU starts, cache deletion or new revision language are added.
The protected original planner already deep-copies sibling metadata; this bridge
checks that behavior and refuses an incomplete or downgraded child submission.
"""
from __future__ import annotations

from copy import deepcopy

from studio_contracts import StudioContractError, _bounded_json


def _error(code, message):
    raise StudioContractError(code, message, ["sfx"], status=422)


def plan_revision(parent_submission, startSeconds, endSeconds, prompt, sfx=None, *, parent_revision):
    """Return the preserved ``{submission, impact}`` contract after invariants."""
    _bounded_json(parent_submission)
    if not isinstance(parent_submission, dict):
        _error("STUDIO_REVISION_PARENT_INVALID", "검증된 기존 제작 입력이 필요합니다.")
    before = deepcopy(parent_submission)
    result = parent_revision(parent_submission, startSeconds, endSeconds, prompt, sfx)
    if parent_submission != before:
        _error("STUDIO_COMPLETION_REVISION_PARENT_MUTATED", "기존 제작 입력을 변경하는 수정 결과는 사용할 수 없습니다.")
    if not isinstance(result, dict) or not isinstance(result.get("submission"), dict) or not isinstance(result.get("impact"), dict):
        _error("STUDIO_COMPLETION_REVISION_RESULT_INVALID", "효과음 수정 결과를 검증하지 못했습니다.")
    child, impact = result["submission"], result["impact"]
    for field in ("videoPlan", "integration", "completionV2"):
        if (field in before) != (field in child) or (field in before and child[field] != before[field]):
            _error("STUDIO_COMPLETION_REVISION_METADATA_CHANGED", "효과음 수정 중 영상·통합 설정을 바꿀 수 없습니다.")
    if impact.get("requiresGpu") is not False or impact.get("invalidatedSceneIds") != []:
        _error("STUDIO_VISUAL_REVISION_UNSUPPORTED", "이 수정 경로는 영상 재렌더링을 지원하지 않습니다.")
    scenes = before.get("videoPlan", {}).get("scenes", [])
    expected = [scene.get("sceneId") for scene in scenes if isinstance(scene, dict)]
    if impact.get("reusedSceneIds") != expected:
        _error("STUDIO_COMPLETION_REVISION_REUSE_INVALID", "기존 영상 장면 재사용 범위를 확인할 수 없습니다.")
    _bounded_json(result)
    return result
