"""Fail-closed, canvas-free semantic visibility certification before rendering.

The certificate forecasts the frozen Three.js renderer's primitive eligibility.
It is not final rendered-frame QC and never replaces that check.
"""
from __future__ import annotations

import hashlib
import json
import copy
from collections import OrderedDict
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


APP_ROOT = Path(__file__).resolve().parents[1]
TOOL = APP_ROOT / "tools" / "semantic_preflight.mjs"
_CERTIFICATES: OrderedDict[str, dict[str, Any]] = OrderedDict()


def _source_fingerprint() -> str:
    legacy = APP_ROOT.parent / "cinematic-world-map"
    paths = [TOOL, Path(__file__), APP_ROOT / "web" / "earth_adapter.js", APP_ROOT / "engine" / "retention.py",
             APP_ROOT / "engine" / "assets.py", APP_ROOT / "engine" / "rendering.py",
             legacy / "src" / "renderer_v3.js", legacy / "src" / "aircraft_v3.js",
             legacy / "node_modules" / "three" / "build" / "three.module.js",
             legacy / "assets" / "v3" / "fonts" / "OpenSans-Light.ttf",
             APP_ROOT / "web" / "fonts" / "NotoSansCJKkr-Regular.otf"]
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path).encode())
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def semantic_input_hash(plan: dict[str, Any]) -> str:
    """Exclude gate/certificate metadata so recording a report cannot invalidate it."""
    inputs = {key: plan[key] for key in ("scenes", "story", "story_plan", "hook", "render_context")
              if key in plan}
    return hashlib.sha256(json.dumps(inputs, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def certify_semantic_visibility(plan: dict[str, Any], *, scene_ids: list[str] | None = None,
                                timeout_seconds: float = 45) -> dict[str, Any]:
    """Return an explicit failed certificate for tool/runtime/layout errors.

    scene_ids enables scoped revision preflight; it deliberately does not assert
    opening-hook coverage for a fragment. Cinematic clips delegate to their actual
    annotation/source validator, never accept unverified physical map events.
    """
    digest = semantic_input_hash(plan)
    try:
        if not TOOL.is_file():
            raise FileNotFoundError("Semantic visibility tool is missing")
        source_fingerprint = _source_fingerprint()
        # User-provided bytes can change at an identical path. Mixed clip plans
        # always recheck actual scoped media/bytes/license/metadata, without cache.
        contains_clip = any(scene.get("scene_type") == "CINEMATIC_CLIP" for scene in plan.get("scenes", []))
        key = hashlib.sha256(json.dumps([digest, source_fingerprint, sorted(scene_ids or [])],
                                        separators=(",", ":")).encode()).hexdigest()
        if not contains_clip and key in _CERTIFICATES:
            _CERTIFICATES.move_to_end(key)
            cached = copy.deepcopy(_CERTIFICATES[key])
            cached["certificate_cache_hit"] = True
            return cached
        with tempfile.TemporaryDirectory(prefix="wss_visibility_") as directory:
            plan_path = Path(directory) / "scene_plan.json"
            plan_path.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            command = ["node", str(TOOL), "--plan", str(plan_path), "--python", sys.executable]
            if scene_ids:
                command.extend(["--scene", ",".join(scene_ids)])
            result = subprocess.run(command, cwd=APP_ROOT, text=True, capture_output=True,
                                    timeout=timeout_seconds, check=False)
            if result.returncode not in (0, 2):
                raise RuntimeError(f"Certifier exited {result.returncode}: {result.stderr[-1800:]}")
            report = json.loads(result.stdout)
            if (not isinstance(report, dict) or not isinstance(report.get("passed"), bool)
                    or not isinstance(report.get("failures"), list)
                    or result.returncode == 0 and not report["passed"]
                    or result.returncode == 2 and report["passed"]):
                raise ValueError("Invalid semantic certificate contract")
            report.pop("plan_path", None)  # Temporary path is not a deliverable.
            report["semantic_input_sha256"] = digest
            # The meaningful-input hash, not metadata/gate formatting, identifies
            # a reusable certificate. Preserve the initial forensic byte hash.
            report["certified_plan_bytes_sha256"] = report.pop("plan_sha256", None)
            report["certificate_source_fingerprint"] = source_fingerprint
            report["certificate_cache_hit"] = False
            if not contains_clip:
                _CERTIFICATES[key] = copy.deepcopy(report)
            while len(_CERTIFICATES) > 64:
                _CERTIFICATES.popitem(last=False)
            return report
    except (OSError, subprocess.TimeoutExpired, ValueError, RuntimeError) as error:
        return {"schema_version": 1, "passed": False, "semantic_input_sha256": digest,
                "scoped_scene_ids": scene_ids, "events": [],
                "failures": [{"code": "SEMANTIC_CERTIFICATION_FAILED", "detail": str(error)}],
                "scope": "Pre-render visibility certification failed closed; rendering must not start."}
