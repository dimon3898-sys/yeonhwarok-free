"""Repair missing loader descriptors for existing provider-mounted NVIDIA libs.

This installs no drivers, touches no host paths, selects no GPU, and proves no
hardware rendering. Admission still requires a real NVIDIA WebGL2 pixel draw.
The only generated files live under the deployment's private runtime directory.
"""
from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import re
import stat
import tempfile


RUNTIME_DIRECTORY = Path("/run/world-engine")
DESCRIPTOR_DIRECTORIES = {
    "egl": (Path("/etc/glvnd/egl_vendor.d"), Path("/usr/share/glvnd/egl_vendor.d")),
    "vulkan": (Path("/etc/vulkan/icd.d"), Path("/usr/share/vulkan/icd.d")),
}
LIBRARY_DIRECTORIES = (Path("/usr/lib/x86_64-linux-gnu"), Path("/lib/x86_64-linux-gnu"),
                       Path("/usr/lib64"), Path("/lib64"),
                       Path("/usr/local/nvidia/lib64"), Path("/usr/local/nvidia/lib"))
_LIBRARY_NAMES = {"egl": "libEGL_nvidia.so.0", "vulkan": "libGLX_nvidia.so.0"}
_ENTRYPOINTS = {"egl": "__egl_Main", "vulkan": "vk_icdGetInstanceProcAddr"}


class GraphicsRuntimeError(ValueError):
    pass


def _load_driver(kind, loader):
    try:
        library = loader(_LIBRARY_NAMES[kind])
        getattr(library, _ENTRYPOINTS[kind])
        return library
    except (OSError, AttributeError):
        return None


def _contained_file(candidate, roots, *, allow_root_symlinks=False):
    """Canonical containment prevents env-selected .. and symlink escapes."""
    try:
        if not candidate.is_absolute():
            return False
        resolved = candidate.resolve(strict=True)
        if not resolved.is_file():
            return False
        for root in roots:
            # Trusted /lib ABI directories may themselves be system symlinks;
            # the resolved fixed root, rather than a lexical prefix, is used.
            try:
                if root.is_symlink() and not allow_root_symlinks:
                    continue
                if resolved.is_relative_to(root.resolve(strict=True)):
                    return True
            except OSError:
                continue
    except (OSError, RuntimeError):
        return False
    return False


def _descriptor_valid(path, kind, loader):
    try:
        if not path.is_file() or path.stat().st_size > 16384:
            return False
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("file_format_version") not in {"1.0.0", "1.0.1"}:
            return False
        name = value["ICD"]["library_path"]
        if not isinstance(name, str):
            return False
        expected = "libEGL_nvidia" if kind == "egl" else "libGLX_nvidia"
        if not re.fullmatch(re.escape(expected) + r"\.so\.[0-9.]+", Path(name).name):
            return False
        if "/" in name and not _contained_file(Path(name), LIBRARY_DIRECTORIES,
                                               allow_root_symlinks=True):
            return False
        # Never dlopen a path taken from JSON/environment as root. Only the
        # fixed provider driver's standard SONAME is eligible for loading.
        library = loader(_LIBRARY_NAMES[kind])
        getattr(library, _ENTRYPOINTS[kind])
        if kind == "vulkan" and not re.fullmatch(r"[1-9][0-9]*\.[0-9]+\.[0-9]+",
                                               value["ICD"].get("api_version", "")):
            return False
        return True
    except (OSError, ValueError, AttributeError, KeyError, TypeError):
        return False


def _existing_descriptor(kind, environ, loader):
    selector = (environ.get("__EGL_VENDOR_LIBRARY_FILENAMES") if kind == "egl" else
                environ.get("VK_DRIVER_FILES") or environ.get("VK_ICD_FILENAMES"))
    directories = DESCRIPTOR_DIRECTORIES[kind]
    if selector:
        # Provider JSON can be in its own NVIDIA mount. Do not inspect arbitrary
        # paths from environment variables or include their contents in facts.
        allowed = (*directories, Path("/usr/local/nvidia"), RUNTIME_DIRECTORY)
        candidates = []
        for name in selector.split(":")[:256]:
            candidate = Path(name)
            if _contained_file(candidate, allowed):
                candidates.append(candidate)
    else:
        candidates = []
        for directory in directories:
            try:
                if directory.is_symlink():
                    continue
                candidates.extend(path for path in sorted(directory.glob("*.json"))[:256]
                                  if _contained_file(path, (directory,)))
            except OSError:
                continue
    return any(_descriptor_valid(path, kind, loader) for path in candidates)


def _vulkan_api_version(library):
    """Read the actual driver's maximum API; never invent a modern API level."""
    function = library.vk_icdGetInstanceProcAddr
    function.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    function.restype = ctypes.c_void_p
    address = function(None, b"vkEnumerateInstanceVersion")
    if not address:
        # Vulkan 1.0 ICDs do not provide this Vulkan 1.1 entrypoint.
        return "1.0.0"
    enumerate_version = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.POINTER(ctypes.c_uint32))(address)
    version = ctypes.c_uint32()
    if enumerate_version(ctypes.byref(version)) != 0:
        raise GraphicsRuntimeError("GPU_GRAPHICS_DRIVER_API_UNAVAILABLE")
    variant = version.value >> 29
    major, minor, patch = ((version.value >> 22) & 0x7f,
                           (version.value >> 12) & 0x3ff, version.value & 0xfff)
    if variant != 0 or major < 1:
        raise GraphicsRuntimeError("GPU_GRAPHICS_DRIVER_API_UNAVAILABLE")
    return f"{major}.{minor}.{patch}"


def prepare_graphics_runtime(environ=None, *, loader=None, runtime_directory=None,
                             descriptor_checker=None, vulkan_version_reader=None):
    """Return (browser environment updates, safe facts); never change os.environ.

    Startup applies updates before both its unprivileged admission probe and the
    actual engine. Injectable parameters exist only for deterministic CPU tests.
    Generated directories are 0755/files 0644 beneath a private 0700 engine
    runtime parent so the UID 1000 browser can read root-created descriptors.
    """
    env = os.environ if environ is None else environ
    facts = {"schema_version": 1, "driver_installation_performed": False,
             "hardware_verification_performed": False, "descriptors_created": [],
             "egl": {}, "vulkan": {}}
    if env.get("WORLD_ENGINE_RENDER_MODE", "gpu-required") == "cpu":
        facts["status"] = "explicit_cpu_mode"
        return {}, facts
    load = ctypes.CDLL if loader is None else loader
    check = _existing_descriptor if descriptor_checker is None else descriptor_checker
    read_version = _vulkan_api_version if vulkan_version_reader is None else vulkan_version_reader
    updates, pending = {}, {}
    for kind in ("egl", "vulkan"):
        library = _load_driver(kind, load)
        exists = bool(check(kind, env, load)) if library is not None else False
        facts[kind] = {"nvidia_library_loadable": library is not None,
                       "driver_entrypoint_available": library is not None,
                       "usable_vendor_descriptor_present": exists}
        if library is None or exists:
            continue
        descriptor = {"file_format_version": "1.0.0",
                      "ICD": {"library_path": _LIBRARY_NAMES[kind]}}
        if kind == "vulkan":
            try:
                descriptor["ICD"]["api_version"] = read_version(library)
            except (OSError, GraphicsRuntimeError, TypeError, ValueError):
                facts[kind]["descriptor_status"] = "driver_api_query_failed"
                continue
        pending[kind] = descriptor
    if pending:
        parent = RUNTIME_DIRECTORY if runtime_directory is None else Path(runtime_directory)
        try:
            metadata = parent.lstat()
            if (not stat.S_ISDIR(metadata.st_mode) or parent.is_symlink() or
                    metadata.st_mode & 0o077):
                raise GraphicsRuntimeError("GPU_GRAPHICS_RUNTIME_PATH_UNSAFE")
            directory = Path(tempfile.mkdtemp(prefix="nvidia-graphics-", dir=parent))
            directory.chmod(0o755)
            for kind, descriptor in pending.items():
                filename = directory / ("10_nvidia.json" if kind == "egl" else "nvidia_icd.json")
                descriptor_fd = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                                        getattr(os, "O_NOFOLLOW", 0), 0o644)
                with os.fdopen(descriptor_fd, "w", encoding="utf-8") as handle:
                    json.dump(descriptor, handle, sort_keys=True)
                    handle.write("\n")
                filename.chmod(0o644)
                if kind == "egl":
                    updates["__EGL_VENDOR_LIBRARY_FILENAMES"] = str(filename)
                else:
                    updates["VK_DRIVER_FILES"] = str(filename)
                    updates["VK_ICD_FILENAMES"] = str(filename)
                facts["descriptors_created"].append(kind)
                facts[kind]["descriptor_status"] = "created_from_loaded_nvidia_driver"
        except OSError as error:
            raise GraphicsRuntimeError("GPU_GRAPHICS_RUNTIME_PATH_UNWRITABLE") from error
    facts["status"] = "prepared" if updates else "unchanged"
    return updates, facts
