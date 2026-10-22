"""Sequential evidence gate. No draw, source invention or approval side effect."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def assess_gates(capture_report, studio_execution):
    report = json.loads(Path(capture_report).read_bytes())
    execution = json.loads(Path(studio_execution).read_bytes())
    report_sha = hashlib.sha256(Path(capture_report).read_bytes()).hexdigest()
    frames = report.get("frames", [])
    checks = {
        "actualStudioAuthenticatedStart": execution.get("loginViaOriginalForm") is True and execution.get("sessionAuthenticated") is True,
        "sameJob": execution.get("jobId") == report.get("jobId") == execution.get("duplicateJobId"),
        "sourceAndTimeline": report.get("sourceSceneSHA256") == "aac147932d687f065469c224dbe2a02494f17c01a9be87383e771ada3f275159"
            and len(frames) == 150 and [r.get("frame") for r in frames] == list(range(150)),
        "freshDraw": report.get("newlyRenderedFrames") == 150 and report.get("reusedFrames") == 0 and report.get("oldCacheReused") is False,
        "originalRawAndPNGMatch": report.get("rawRgbaEqualFrames") == report.get("pngEqualFrames") == 150
            and all(r.get("originalRawRgbaEqual") is True and r.get("originalPngEqual") is True for r in frames),
        "videoFullDecode": report.get("fullDecode") == "PASS",
        "authAndCsrfRetained": execution.get("unauthStatus") == 401 and execution.get("missingCsrfStatus") == 403
            and execution.get("wrongOriginStatus") == 403,
        "connectionIndependent": execution.get("httpServerStoppedDuringRender") is True
            and execution.get("controllerRestartDuplicateJobId") == report.get("jobId")
            and execution.get("finalState", {}).get("state") == "COMPLETED",
    }
    g1 = all(checks.values())
    spec = importlib.util.spec_from_file_location("_gates_source_control", HERE / "control_provider.py")
    provider = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(provider)
    g2 = provider.validate_g2_history()
    allowed = g1 and g2.get("renderAllowed") is True
    return {"schema": "WORLD_ENGINE_SEQUENTIAL_GATE_RESULTS_V1", "g1": {
        "status": "G1_RENDER_PASS_CANDIDATE" if g1 else "G1_NEEDS_REWORK", "checks": checks,
        "captureReportSHA256": report_sha, "scope": "ACTUAL_AUTHENTICATED_STUDIO_SOURCE_CHECKOUT_SOFTWARE",
        "deployedImageVerified": False, "nvidiaVerified": False, "visualQualityApproved": False},
        "g2": g2, "g3": {"status": "READY_FOR_SEPARATE_REVIEW" if allowed else "NOT_EXECUTED_GATE_BLOCKED",
            "renderAllowed": allowed, "historicalFramesDrawn": 0},
        "full80SecondRenderAllowed": False, "productionReady": False,
        "userApproved": False, "next": "USER_REVIEW_REQUIRED"}
