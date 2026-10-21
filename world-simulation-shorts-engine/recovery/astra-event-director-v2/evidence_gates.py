"""Source-bound marker/audio gates; empty evidence never becomes an effect.

Existing flag artwork, participation gates and SFX owners are preserved. A city
context point is not a historical military position. New active effects require
their own independently reviewed evidence; this source review does not have it.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def build_evidence_manifests(profile_bytes):
    profile = json.loads(profile_bytes)
    identity = {"version": 2, "sourcePlanSHA256": profile["sourcePlanSHA256"],
                "eventProfileSHA256": sha(profile_bytes), "subjectId": profile["subjectId"]}
    # This implementation does not silently promote any future JSON to reviewed
    # coordinates or audio meaning. Add a source owner only with real evidence.
    if profile.get("markerEvidence"):
        raise ValueError("HISTORICAL_MARKER_EVIDENCE_OWNER_REVIEW_REQUIRED")
    audio = profile.get("audio", {})
    if (audio.get("enabled") is not False or type(audio.get("gain")) not in (int, float)
            or audio["gain"] != 0 or audio.get("cues") != []):
        raise ValueError("AUDIO_CUE_UNVERIFIED")
    markers = {"schema": "WORLD_ENGINE_EVENT_DIRECTOR_MARKER_EVIDENCE_V2", **identity,
        "markers": [], "status": "BLOCKED_HISTORICAL_MARKER_EVIDENCE_MISSING",
        "geographicContextOnly": True, "cityCoordinatesAreNotTroopPositions": True,
        "historicalMarkerDrawCount": 0, "existingArtOrMarkersChanged": False}
    sound = {"schema": "WORLD_ENGINE_EVENT_DIRECTOR_AUDIO_CUE_MANIFEST_V2", **identity,
        "enabled": False, "gain": 0, "cues": [], "exportWav": False,
        "status": "BLOCKED_AUDIO_SEMANTIC_REVIEW", "automaticCueGenerationAllowed": False,
        "referenceAudioMeaningVerified": False, "uiMayOverride": False}
    return markers, sound


def _validate(document, request, resolved_documents, family):
    raw = (HERE / "fixtures/HISTORY_EVENT_PROFILE_V2.json").read_bytes()
    profile = json.loads(raw)
    if (request.get("sourcePlanSha256") != profile["sourcePlanSHA256"]
            or resolved_documents.get("eventDirectorProfileRef") != profile):
        raise ValueError("DIRECTOR_EVIDENCE_SOURCE_PROFILE_MISMATCH")
    marker, audio = build_evidence_manifests(raw)
    expected = marker if family == "marker" else audio
    if document != expected:
        raise ValueError("DIRECTOR_EVIDENCE_ACTUAL_BYTES_OR_SETTINGS_CHANGED")
    code = "HISTORICAL_MARKER_EVIDENCE_MISSING" if family == "marker" else "AUDIO_CUE_UNVERIFIED"
    field = "markerEvidenceRef" if family == "marker" else "audioCueManifestRef"
    return {"ready": False, "reviewReady": request.get("purpose") == "QUALIFIED_SOURCE_REVIEW",
        "blockers": [{"code": code, "path": field, "status": "BLOCKED",
            "detail": "No source-qualified historical marker coordinates" if family == "marker"
                      else "Reference audio meaning and cue correspondence not verified; explicit silence retained"}],
        "eventProfileSHA256": sha(raw), "activeGraphicsOrCues": 0,
        "sourceBoundEmptyManifest": True, "effectsInferredFromCitiesOrChapters": False,
        "nvidiaHardwareVerified": False, "visualQualityApproved": False}


def validate_marker_evidence(document, request, resolved_documents):
    return _validate(document, request, resolved_documents, "marker")


def validate_audio_manifest(document, request, resolved_documents):
    return _validate(document, request, resolved_documents, "audio")


if __name__ == "__main__":
    documents = build_evidence_manifests((HERE / "fixtures/HISTORY_EVENT_PROFILE_V2.json").read_bytes())
    for name, document in zip(("MARKER_EVIDENCE.json", "AUDIO_CUE_MANIFEST.json"), documents):
        (HERE / "fixtures" / name).write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"markerCount": 0, "audioEnabled": False, "gain": 0, "cueCount": 0,
                      "status": "SOURCE_REVIEW_ONLY_NO_HISTORICAL_EFFECTS_APPROVED"}))
