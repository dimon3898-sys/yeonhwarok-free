"""Render backend contracts. GPU execution is deliberately fail-closed without an adapter."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import os
import json
import subprocess
import queue
import threading
import time
from .failures import RenderProcessError, safe_tail


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
        started = time.monotonic()
        # Add strict transport diagnostics without modifying the certified visual
        # code/certificate or invalidating already completed, identical pixels.
        command = list(command)
        approved = Path(__file__).resolve().parents[1] / 'tools/render_production_scene.mjs'
        if len(command) > 1 and command[0] == 'node' and Path(command[1]).resolve() == approved:
            command[1] = str(approved.with_name('render_production_stable_scene.mjs'))
        try:
            child = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1,
                                     encoding='utf-8', errors='replace', start_new_session=True)
        except OSError as error:
            raise RenderProcessError(returncode=None, duration=time.monotonic()-started,
                                     stderr=[type(error).__name__]) from error
        tails = {'stdout': [], 'stderr': []}
        messages = queue.Queue(maxsize=64)
        stopping = threading.Event()
        def enqueue(value):
            while not stopping.is_set():
                try:
                    messages.put(value, timeout=.1)
                    return
                except queue.Full:
                    pass
        def drain(name, stream):
            try:
                for line in stream:
                    if stopping.is_set():
                        break
                    enqueue((name, line))
            finally:
                enqueue((name, None))
        readers = [threading.Thread(target=drain, args=(name, stream), daemon=True)
                   for name, stream in [('stdout', child.stdout), ('stderr', child.stderr)]]
        for reader in readers:
            reader.start()
        try:
            finished = set()
            while len(finished) < 2:
                name, line = messages.get()
                if line is None:
                    finished.add(name)
                    continue
                tails[name].append(line.rstrip()[:8192])
                tails[name] = tails[name][-25:]
                if name == 'stdout' and line.startswith("{"):
                    try:
                        value = json.loads(line)
                        if isinstance(value, dict):
                            progress(value)
                    except json.JSONDecodeError:
                        pass
                elif name == 'stdout' and line.startswith("FRAME "):
                    progress({"stage": "scene_render", "message": line.strip()})
            code = child.wait()
            if code:
                raise RenderProcessError(returncode=code, duration=time.monotonic()-started,
                                         stdout=tails['stdout'], stderr=tails['stderr'])
            return {"backend": self.name, "log_tail": safe_tail(tails['stdout']+tails['stderr']),
                    "exit_code": code, "duration_seconds": time.monotonic()-started}
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
        finally:
            stopping.set()
            for reader in readers:
                reader.join(timeout=2)
            for stream in (child.stdout, child.stderr):
                stream.close()


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
