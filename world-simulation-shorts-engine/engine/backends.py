"""Render backend contracts. GPU execution is deliberately fail-closed without an adapter."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import os
import json
import subprocess


@dataclass(frozen=True)
class RenderEstimate:
    backend: str
    measured: bool
    seconds: float | None
    cost_usd: float | None
    explanation: str


class RenderBackend(ABC):
    name: str

    @abstractmethod
    def run(self, command: list[str], cwd: Path, progress: Callable[[dict], None]) -> dict:
        """Run one scene. Implementations own and clean up only their worker."""

    def estimate(self, duration: float, quality: str) -> RenderEstimate:
        return RenderEstimate(self.name, False, None, None,
                              "No measured benchmark for this scene/quality combination yet.")


class CPULocalBackend(RenderBackend):
    name = "CPU_LOCAL"

    def run(self, command: list[str], cwd: Path, progress: Callable[[dict], None]) -> dict:
        # The browser renderer has its own no-frame watchdog. Pipes are continuously
        # drained here, so a full pipe cannot make a healthy renderer appear stalled.
        child = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, bufsize=1,
                                 start_new_session=True)
        tail: list[str] = []
        try:
            assert child.stdout is not None
            for line in child.stdout:
                tail.append(line.rstrip())
                tail = tail[-25:]
                if line.startswith("{"):
                    try:
                        value = json.loads(line)
                        if isinstance(value, dict):
                            progress(value)
                    except json.JSONDecodeError:
                        pass
                elif line.startswith("FRAME "):
                    progress({"stage": "scene_render", "message": line.strip()})
            code = child.wait()
            if code:
                raise RuntimeError(f"SCENE_RENDER_FAILED ({code}): " + "\n".join(tail))
            return {"backend": self.name, "log_tail": tail, "exit_code": code}
        except BaseException:
            if child.poll() is None:
                import signal
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait(timeout=10)
            raise


class GPUCloudBackend(RenderBackend):
    """Vendor-neutral lifecycle contract; no worker is provisioned implicitly."""
    name = "GPU_CLOUD"

    def __init__(self, adapter=None, *, maximum_cost_usd: float = 0,
                 approved_estimate: RenderEstimate | None = None):
        self.adapter = adapter
        self.maximum_cost_usd = maximum_cost_usd
        self.approved_estimate = approved_estimate

    def run(self, command: list[str], cwd: Path, progress: Callable[[dict], None]) -> dict:
        if self.adapter is None:
            raise RuntimeError("GPU_BACKEND_UNAVAILABLE: install a provider adapter; CPU_LOCAL remains usable")
        estimate = self.approved_estimate
        if estimate is None or estimate.cost_usd is None:
            raise RuntimeError("GPU_COST_APPROVAL_REQUIRED")
        if estimate.cost_usd > self.maximum_cost_usd:
            raise RuntimeError("GPU_COST_LIMIT_EXCEEDED")
        worker = None
        try:
            worker = self.adapter.start_worker(maximum_cost_usd=self.maximum_cost_usd)
            return self.adapter.run(worker, command=command, cwd=cwd, progress=progress)
        finally:
            if worker is not None:
                self.adapter.stop_worker(worker)


QUALITY_SETTINGS = {
    "FAST": {"internal_width": 540, "output_width": 540, "output_height": 960,
             "fps": 30, "preview_only": True, "description": "Half-size preview; not the publication quality gate"},
    "HIGH": {"internal_width": 2160, "output_width": 1080, "output_height": 1920,
             "fps": 30, "preview_only": False, "description": "V3 4K internal shader/asset baseline; 1080x1920 output"},
    "CINEMA": {"internal_width": 2160, "output_width": 1080, "output_height": 1920,
               "fps": 30, "preview_only": False, "temporal_samples": 2,
               "description": "V3 4K internal; two temporal scene samples with the same atmospheric shader"},
}


def quality_settings(quality: str, scene: dict | None = None) -> dict:
    name = quality.upper()
    if name not in QUALITY_SETTINGS:
        raise ValueError(f"UNKNOWN_RENDER_QUALITY: {quality}")
    settings = dict(QUALITY_SETTINGS[name])
    # Both publication modes retain the same V3 shaders and preserved 8K assets.
    # CINEMA integrates two actual scene times; HIGH uses the default single time.
    settings["quality"] = name
    settings["lighting"] = (scene or {}).get("lighting_preset", "GEOGRAPHY_READABILITY")
    return settings
