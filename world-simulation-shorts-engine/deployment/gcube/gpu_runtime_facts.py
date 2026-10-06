"""Bounded, read-only graphics inventory; file presence is never GPU proof.

Only counts, known-library booleans and environment selection semantics leave
this module. GPU UUIDs, environment values and filesystem paths are omitted.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import stat


_LIBRARY_DIRS = (
    '/usr/lib/x86_64-linux-gnu', '/lib/x86_64-linux-gnu',
    '/usr/local/nvidia/lib64', '/usr/local/nvidia/lib', '/usr/lib64',
)
_MANIFEST_DIRS = {
    'egl_vendor_manifest': ('/usr/share/glvnd/egl_vendor.d', '/etc/glvnd/egl_vendor.d'),
    'vulkan_nvidia_icd': ('/usr/share/vulkan/icd.d', '/etc/vulkan/icd.d'),
}
_LIBRARIES = {
    'egl': 'libEGL.so*', 'gles': 'libGLESv2.so*', 'opengl': 'libGL.so*',
    'vulkan': 'libvulkan.so*', 'nvidia_egl': 'libEGL_nvidia.so*',
    'nvidia_vulkan': 'libGLX_nvidia.so*',
}


def _selection(env, name):
    value = env.get(name)
    if value is None:
        return {'present': False, 'selection': 'unset'}
    selection = 'configured'
    if value in {'', 'none', 'void', '-1'}:
        selection = 'none'
    elif value == 'all':
        selection = 'all'
    elif isinstance(value, str) and re.fullmatch(r'\d+(?:,\d+)*', value):
        selection = 'index-list'
    return {'present': True, 'selection': selection}


def _device_count(folder, pattern):
    try:
        base = Path(folder).lstat()
        if not stat.S_ISDIR(base.st_mode) or stat.S_ISLNK(base.st_mode):
            return 0
        count = 0
        with os.scandir(folder) as entries:
            for index, entry in enumerate(entries):
                if index >= 256:
                    break
                if pattern.fullmatch(entry.name):
                    try:
                        count += int(stat.S_ISCHR(entry.stat(follow_symlinks=False).st_mode))
                    except OSError:
                        pass
        return count
    except OSError:
        return 0


def _library_present(pattern):
    for directory in _LIBRARY_DIRS:
        try:
            for index, candidate in enumerate(Path(directory).glob(pattern)):
                if index >= 32:
                    break
                if candidate.is_file():
                    return True
        except OSError:
            pass
    return False


def _nvidia_manifest_present(directories):
    for directory in directories:
        try:
            for index, manifest in enumerate(Path(directory).glob('*.json')):
                if index >= 32:
                    break
                if not manifest.is_file() or manifest.stat().st_size > 16384:
                    continue
                document = json.loads(manifest.read_text())
                icd = document.get('ICD', {}) if isinstance(document, dict) else {}
                library = icd.get('library_path', '') if isinstance(icd, dict) else ''
                if isinstance(library, str) and 'nvidia' in library.lower():
                    return True
        except (OSError, ValueError, TypeError):
            pass
    return False


def _prepared_manifest_present(environ, kind):
    """Read only known deployment-created descriptors, not arbitrary env paths."""
    selector = (environ.get('__EGL_VENDOR_LIBRARY_FILENAMES') if kind == 'egl' else
                environ.get('VK_DRIVER_FILES') or environ.get('VK_ICD_FILENAMES'))
    if not isinstance(selector, str) or len(selector) > 4096:
        return False
    filename = '10_nvidia.json' if kind == 'egl' else 'nvidia_icd.json'
    pattern = r'/run/world-engine/nvidia-graphics-[a-zA-Z0-9_-]+/' + re.escape(filename)
    for item in selector.split(':')[:16]:
        if not re.fullmatch(pattern, item):
            continue
        try:
            path = Path(item)
            if any(parent.is_symlink() for parent in (path, *path.parents)):
                continue
            if not path.is_file() or path.stat().st_size > 16384:
                continue
            document = json.loads(path.read_text())
            library = document.get('ICD', {}).get('library_path')
            expected = 'libEGL_nvidia.so.0' if kind == 'egl' else 'libGLX_nvidia.so.0'
            if library == expected:
                return True
        except (OSError, ValueError, AttributeError, TypeError):
            pass
    return False


def graphics_runtime_inventory(environ):
    """Use fixed image/device locations, never an input-controlled path."""
    return {
        'environment': {name: _selection(environ, name) for name in
                        ('NVIDIA_VISIBLE_DEVICES', 'CUDA_VISIBLE_DEVICES')},
        'devices': {
            'nvidia': _device_count('/dev', re.compile(r'nvidia(?:[0-9]+|ctl|modeset|-uvm(?:-tools)?)')),
            'dri': _device_count('/dev/dri', re.compile(r'(?:card[0-9]+|renderD[0-9]+)')),
        },
        'libraries': {name: _library_present(pattern) for name, pattern in _LIBRARIES.items()},
        'driver_delivery': {name: _nvidia_manifest_present(directories) or
                            _prepared_manifest_present(environ, 'egl' if name == 'egl_vendor_manifest' else 'vulkan')
                            for name, directories in _MANIFEST_DIRS.items()},
    }
