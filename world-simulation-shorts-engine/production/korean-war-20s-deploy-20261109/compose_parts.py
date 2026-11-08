"""Join the two user-rendered Studio outputs through the unchanged composer.

This program does not start a renderer, browser, container, or GPU. Input hashes
must come from each Studio result's SHA256SUMS, in PART01/PART02 order.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys

COMPOSER_SHA256 = "d4478f758988923a18620a07b0dcf0e0883c99b6ef419d4bffac5999e65d5245"
HASH = re.compile(r"[0-9a-f]{64}\Z")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--part01", type=Path, required=True)
    parser.add_argument("--part01-sha256", required=True)
    parser.add_argument("--part02", type=Path, required=True)
    parser.add_argument("--part02-sha256", required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args(argv)
    if not all(HASH.fullmatch(v) for v in (args.part01_sha256, args.part02_sha256)):
        parser.error("Use each Studio result's actual 64-character SHA256SUMS value.")
    if not all(shutil.which(binary) for binary in ("ffmpeg", "ffprobe")):
        parser.error("The CPU host needs its existing ffmpeg and ffprobe commands.")
    composer = Path(__file__).resolve().with_name("compose.py")
    if hashlib.sha256(composer.read_bytes()).hexdigest() != COMPOSER_SHA256:
        parser.error("The preserved WORLD ENGINE composer does not match its pinned hash.")
    spec = importlib.util.spec_from_file_location("world_engine_preserved_compose", composer)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    parts = [("PART01", args.part01, args.part01_sha256),
             ("PART02", args.part02, args.part02_sha256)]
    if args.part01.absolute() == args.part02.absolute():
        parser.error("PART01 and PART02 must be distinct downloaded files.")
    plan = {"durationSeconds": 20, "fps": 30,
            "resolution": {"width": 1080, "height": 1920},
            "scenes": [{"sceneId": name, "startFrame": i * 300,
                        "endFrame": (i + 1) * 300}
                       for i, (name, _, _) in enumerate(parts)]}
    segments = [{**scene, "path": str(path.absolute()), "sha256": digest}
                for scene, (_, path, digest) in zip(plan["scenes"], parts)]
    result = module.compose_segments(plan, segments, args.destination.absolute())
    print(json.dumps({"status": result["status"], "frames": result["frames"],
                      "sha256": result["sha256"], "path": result["path"],
                      "technical": result["technical"], "quality": result["quality"],
                      "gpuStarts": 0, "rendererInvoked": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
