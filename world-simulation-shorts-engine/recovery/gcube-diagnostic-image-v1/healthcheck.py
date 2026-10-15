"""Mode-aware liveness: diagnostic liveness never means GPU readiness."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from records import SCHEMA


def check_health(payload, mode):
    if not isinstance(payload, dict):
        return False
    if mode == "diagnostic":
        return (payload.get("schema") == SCHEMA and payload.get("startupMode") == "diagnostic"
                and payload.get("status") in {"BLOCKED", "DIAGNOSTIC_ONLY"}
                and payload.get("diagnosticServiceAlive") is True
                and payload.get("gpuRenderingVerified") is False and payload.get("renderAllowed") is False
                and isinstance(payload.get("exitCode"), int) and not isinstance(payload["exitCode"], bool)
                and 0 <= payload["exitCode"] <= 255
                and ((payload["status"] == "BLOCKED" and payload["exitCode"] > 0)
                     or (payload["status"] == "DIAGNOSTIC_ONLY" and payload["exitCode"] == 0)))
    if mode == "normal":
        return (payload.get("status") == "GPU_VERIFIED" and payload.get("testOnly") is False
                and payload.get("gpuRenderingVerified") is True and payload.get("renderMode") == "gpu-required"
                and payload.get("verificationScope") == "STARTUP_NATIVE_GPU_PIXEL_DRAW")
    return False


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main():
    mode = os.environ.get("WORLD_ENGINE_STARTUP_MODE", "normal")
    try:
        port = int(os.environ.get("WORLD_ENGINE_DIAGNOSTIC_PORT", "8000")) if mode == "diagnostic" else 8000
        if mode not in {"normal", "diagnostic"} or not 1024 <= port <= 65535:
            return 1
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        with opener.open(f"http://127.0.0.1:{port}/healthz", timeout=3) as response:
            data = response.read(131073)
            if response.status != 200 or len(data) > 131072:
                return 1
            body = json.loads(data)
        return 0 if check_health(body, mode) else 1
    except (OSError, ValueError, TypeError, urllib.error.URLError):
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
