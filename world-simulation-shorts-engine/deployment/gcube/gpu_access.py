"""Retain only supplementary groups belonging to exposed graphics devices.

Provider GPU nodes may be 0660 with a non-root ``video``/``render`` group.
Dropping every supplementary group before Chromium starts can remove access.
This helper grants no new device, changes no mode/owner, follows no symlink,
and never retains GID 0 or groups from arbitrary files. It is not GPU proof.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat


_NVIDIA = re.compile(r"nvidia(?:[0-9]+|ctl|modeset|-uvm(?:-tools)?)")
_CAPS = re.compile(r"nvidia-cap[0-9]+")
_DRI = re.compile(r"(?:card[0-9]+|renderD[0-9]+)")
_MAX_ENTRIES = 256


def _character_device_groups(folder, pattern):
    try:
        directory = folder.lstat()
    except OSError:
        return set()
    if not stat.S_ISDIR(directory.st_mode) or stat.S_ISLNK(directory.st_mode):
        return set()
    groups = set()
    try:
        with os.scandir(folder) as entries:
            for index, entry in enumerate(entries):
                if index >= _MAX_ENTRIES:
                    break
                if not pattern.fullmatch(entry.name):
                    continue
                try:
                    node = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if (stat.S_ISCHR(node.st_mode) and node.st_gid > 0 and
                        node.st_mode & (stat.S_IRGRP | stat.S_IWGRP)):
                    groups.add(node.st_gid)
    except OSError:
        return set()
    return groups


def collect_device_groups(dev_root="/dev"):
    """Return sorted non-root groups from fixed, real graphics-device locations.

    ``dev_root`` supports isolated tests; production calls use /dev and do not
    accept a path from user input or environment. Device access still has to
    pass the existing hardware + actual WebGL drawing probe afterwards.
    """
    base = Path(dev_root)
    if not base.is_absolute() or ".." in base.parts:
        raise ValueError("GPU_DEVICE_ROOT_INVALID")
    try:
        root = base.lstat()
    except OSError:
        return []
    if not stat.S_ISDIR(root.st_mode) or stat.S_ISLNK(root.st_mode):
        return []
    groups = _character_device_groups(base, _NVIDIA)
    groups.update(_character_device_groups(base / "nvidia-caps", _CAPS))
    groups.update(_character_device_groups(base / "dri", _DRI))
    return sorted(groups)
