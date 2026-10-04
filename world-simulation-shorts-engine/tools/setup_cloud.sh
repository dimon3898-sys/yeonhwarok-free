#!/usr/bin/env bash
set -euo pipefail
world_engine_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
world_v3_root="$(cd -- "$world_engine_root/../cinematic-world-map" && pwd)"
for binary in python3 node ffmpeg ffprobe chromium dpkg-deb; do
  if ! command -v "$binary" >/dev/null; then
    printf 'Missing required system executable: %s\n' "$binary" >&2
    exit 1
  fi
done
# Never rewrite the preserved V3 dependency manifests or reinstall an existing tree.
if [ ! -f "$world_v3_root/node_modules/playwright/package.json" ] || [ ! -f "$world_v3_root/node_modules/three/package.json" ]; then
  (cd -- "$world_v3_root" && npm ci)
fi
if [ ! -x "$world_engine_root/.venv/bin/python" ]; then
  python3 -m venv "$world_engine_root/.venv"
fi
"$world_engine_root/.venv/bin/python" -m pip install -r "$world_engine_root/requirements.txt"
"$world_engine_root/.venv/bin/python" "$world_engine_root/tools/bootstrap_runtime.py"
(cd -- "$world_engine_root" && .venv/bin/python -m unittest discover -s tests -v)
