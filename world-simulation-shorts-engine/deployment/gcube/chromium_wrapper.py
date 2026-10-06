#!/usr/bin/env python3
"""Select hardware WebGL outside the preserved rendering tools.

CHROMIUM_PATH points to this executable. GPU startup admission is performed by
gpu.py; this executable only selects browser arguments and never claims a GPU
exists. The explicit cpu mode retains the certified SwiftShader path.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys


class BrowserProfileError(ValueError):
    pass


def browser_profile(environ=None):
    env = os.environ if environ is None else environ
    mode = env.get("WORLD_ENGINE_RENDER_MODE", "gpu-required")
    profile = env.get("WORLD_ENGINE_GPU_PROFILE", "egl")
    if mode not in {"gpu-required", "cpu"} or profile not in {"egl", "vulkan"}:
        raise BrowserProfileError("GPU_PROFILE_INVALID")
    return mode, profile


def browser_arguments(arguments, environ=None):
    """Preserve all unrelated flags; select exactly one GL implementation."""
    mode, profile = browser_profile(environ)
    if not all(isinstance(value, str) and "\x00" not in value for value in arguments):
        raise BrowserProfileError("GPU_PROFILE_INVALID")
    stripped = {"--enable-unsafe-swiftshader", "--disable-gpu", "--enable-gpu",
                "--disable-software-rasterizer"}
    if mode == "gpu-required":
        # Playwright/headless defaults or caller flags must not disable the
        # hardware compositor while startup admission verifies a hardware draw.
        stripped.update({"--disable-gpu-compositing", "--disable-gpu-rasterization",
                         "--disable-webgl", "--disable-webgl2"})
    enabled_features, disabled_features = [], []
    result, index = [], 0
    while index < len(arguments):
        value = arguments[index]
        flag = value.partition("=")[0]
        if flag in {"--use-angle", "--use-gl"} or (
                mode == "gpu-required" and flag == "--use-vulkan"):
            if "=" not in value:
                if index + 1 >= len(arguments) or arguments[index + 1].startswith("--"):
                    raise BrowserProfileError("GPU_PROFILE_INVALID")
                index += 1
        elif (mode == "gpu-required" and profile == "vulkan" and
              flag in {"--enable-features", "--disable-features"}):
            features = value.partition("=")[2]
            if "=" not in value:
                if index + 1 >= len(arguments) or arguments[index + 1].startswith("--"):
                    raise BrowserProfileError("GPU_PROFILE_INVALID")
                index += 1
                features = arguments[index]
            target = enabled_features if flag == "--enable-features" else disabled_features
            target.extend(item for item in features.split(",") if item)
        elif flag not in stripped:
            result.append(value)
        index += 1
    if mode == "cpu":
        return result + ["--enable-unsafe-swiftshader", "--use-angle=swiftshader"]
    angle = "gl-egl" if profile == "egl" else "vulkan"
    result += ["--enable-gpu", "--use-gl=angle", "--use-angle=" + angle,
               "--disable-software-rasterizer"]
    if profile == "vulkan":
        # Chromium's server-side NVIDIA guide enables native Vulkan without an
        # X11 surface. This is a WebGL route, not an unsafe-WebGPU enablement.
        # Merge existing feature lists: duplicate enable-features switches can
        # otherwise discard Playwright's unrelated defaults.
        def other_features(items):
            return list(dict.fromkeys(item for item in items
                                      if item.partition("<")[0].partition(":")[0] != "Vulkan"))
        enabled = other_features(enabled_features) + ["Vulkan"]
        disabled = other_features(disabled_features)
        if disabled:
            result.append("--disable-features=" + ",".join(disabled))
        result += ["--enable-features=" + ",".join(enabled),
                   "--use-vulkan=native", "--disable-vulkan-surface"]
    return result


def browser_executable(environ=None):
    env = os.environ if environ is None else environ
    path = Path(env.get("WORLD_ENGINE_CHROMIUM_REAL", "/usr/bin/chromium"))
    if (not path.is_absolute() or not path.is_file() or not os.access(path, os.X_OK) or
            path.resolve() == Path(__file__).resolve()):
        raise BrowserProfileError("GPU_BROWSER_UNAVAILABLE")
    return str(path)


def main():
    try:
        executable = browser_executable()
        arguments = browser_arguments(sys.argv[1:])
    except BrowserProfileError as error:
        print(str(error), file=sys.stderr)
        return 2
    os.execv(executable, [executable, *arguments])
    return 0


if __name__ == "__main__":
    sys.exit(main())
